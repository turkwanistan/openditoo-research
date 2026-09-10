"""W10 webcam Studio: offline envelope review and one camera-ready-before-claim live launch.

Same authority shape as the W7-W9 trials (fresh manifest, exact named grant, durable one-use
claim taken only against the Studio's camera-ready nonce), a different producer: the Studio
window, whose framing the operator may adjust while it runs. Framing changes pixels only; the
budgets already assume the encoder's worst-case frame, so the reviewed envelope does not move.
"""
import argparse
import json
from pathlib import Path
import re
import select
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import activity_session, frame_stream, webcam_trial

ROOT = frame_stream.ROOT
STUDIO = ROOT / "runtime/windows/OpenDitoo.Webcam.Studio"
STUDIO_BIN = STUDIO / "bin/Release/net8.0-windows10.0.19041.0"
# The Studio links these read-only; they are frozen by the parked W9B-007 manifest too.
LINKED = [ROOT / "runtime/windows/OpenDitoo.Webcam.Probe" / name
          for name in ("WebcamFrames.cs", "LatestFrameSlot.cs", "FrameTransform.cs", "DitooEncoder.cs")]
LINKED += [ROOT / "runtime/windows/OpenDitoo.Webcam.Runner" / name
           for name in ("Trial.cs", "TypedSession.cs", "OfflineTests.cs")]
INTERVALS_MS = (50, 100, 200)  # StudioModes: max / 10fps / 5fps
SESSION_SLACK_SECONDS = 30


def producer_sources() -> list[Path]:
    return sorted(STUDIO.glob("*.cs")) + sorted(STUDIO.glob("*.csproj")) + LINKED + [Path(__file__).resolve()]


def producer_binaries() -> list[Path]:
    return sorted(p for p in STUDIO_BIN.iterdir() if p.suffix in (".dll", ".exe", ".json"))


def executable_path(windows: str) -> Path:
    if not re.fullmatch(r"C:\\[^\r\n]+\\OpenDitoo.Webcam.Studio.exe", windows) or ".." in windows.split("\\"):
        raise ValueError("STUDIO_WINDOWS_PATH_INVALID")
    return Path("/mnt/c") / windows[3:].replace("\\", "/")


def review(path: Path, *, authority: bool = False):
    manifest, _, stream = frame_stream.load_stream_manifest(path, require_authority=authority)
    doc = manifest.raw
    if not re.fullmatch(r"OPENDITOO-WEBCAM-W10-[0-9]{3}", manifest.experiment_id):
        raise ValueError("W10_EXPERIMENT_ID_INVALID")
    interval = stream["playback_interval_ms"]
    if interval not in INTERVALS_MS:
        raise ValueError("W10_SLOT_INTERVAL_NOT_REVIEWED")
    if (stream["source_kind"], stream["session_profile"], manifest.min_frame_interval_ms) != (
            "live", "streaming_ack_clock", 40):
        raise ValueError("W10_ENVELOPE_MISMATCH")
    if doc["session"].get("handover_settle_seconds") != 8:
        raise ValueError("W10_HANDOVER_SETTLE_MISSING")
    camera = stream["live_source"]["camera"]
    for key, expected in {"usb_vid": "0C45", "usb_pid": "2690", "subtype": "NV12", "width": 640,
                          "height": 480, "requested_fps": 60, "acquisition_mode": "Realtime"}.items():
        if camera.get(key) != expected:
            raise ValueError(f"CAMERA_ENVELOPE_MISMATCH:{key}")
    if stream["live_source"]["transform"].get("preset") != "srgb_area":
        raise ValueError("TRANSFORM_ENVELOPE_MISMATCH:preset")
    if "/v1/session/heartbeat" not in doc["adapter"]["routes"]:
        raise ValueError("W10_HEARTBEAT_ROUTE_UNDECLARED")
    hashes = stream["live_source"]["producer_code_sha256"]
    required = {str(p.relative_to(ROOT)) for p in producer_sources() + producer_binaries()}
    if not required <= hashes.keys():
        raise ValueError("W10_PRODUCER_HASHES_INCOMPLETE:" + ",".join(sorted(required - hashes.keys())))
    for relative, expected in hashes.items():
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or not (ROOT / candidate).is_file():
            raise ValueError(f"PRODUCER_ARTIFACT_MISSING:{relative}")
        if activity_session.sha256_file(ROOT / candidate) != expected:
            raise ValueError(f"PRODUCER_HASH_DRIFT:{relative}")
    if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != manifest.host_build_sha256:
        raise ValueError("HOST_BUILD_HASH_DRIFT")
    exe = executable_path(doc["adapter"]["windows_executable"])
    for binary in producer_binaries():
        if activity_session.sha256_file(exe.parent / binary.name) != hashes[str(binary.relative_to(ROOT))]:
            raise ValueError(f"DEPLOYED_STUDIO_HASH_DRIFT:{binary.name}")
    if authority:
        if doc["authority"].get("grant_text") != "Grant " + manifest.experiment_id:
            raise ValueError("EXACT_NAMED_GRANT_REQUIRED")
        if not doc["readiness"]["grant_ready"] or doc["readiness"]["blockers"]:
            raise ValueError("W10_NOT_READY")
    return manifest, stream, exe


def run(path: Path) -> dict:
    manifest, _, exe = review(path, authority=True)
    claim = activity_session.SessionClaim(manifest.experiment_id)
    if claim.path.exists():
        raise ValueError("AUTHORITY_ALREADY_CONSUMED")
    service = subprocess.run(["systemctl", "--user", "is-active", "openditoo-product.service"],
                             capture_output=True, text=True, timeout=5)
    if service.stdout.strip() != "inactive":
        raise ValueError("PRODUCT_CONTROLLER_MUST_BE_STOPPED")
    webcam_trial._host_preclaim_status()  # read-only; refuses a non-idle Host before any claim
    digest = activity_session.sha256_file(path)
    claimed = False
    result = {"outcome": "unknown", "terminalReason": "studio_failed"}
    with subprocess.Popen([str(exe), "live", webcam_trial.windows_path(path), webcam_trial.windows_path(ROOT)],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as process:
        try:
            if not select.select([process.stdout], [], [], 30)[0]:
                raise ValueError("CAMERA_READY_TIMEOUT")
            ready = json.loads(process.stdout.readline(16384))
            nonce = ready.get("nonce", "")
            if (ready.get("kind") != "camera_ready" or ready.get("experiment_id") != manifest.experiment_id
                    or ready.get("manifest_sha256") != digest or not re.fullmatch(r"[a-f0-9]{32}", nonce)):
                raise ValueError("CAMERA_NOT_READY:" + json.dumps(ready)[:300])
            review(path, authority=True)  # revalidate after camera startup, still before consumption
            if activity_session.sha256_file(path) != digest:
                raise ValueError("MANIFEST_CHANGED_DURING_PREFLIGHT")
            claim.claim({"manifest_sha256": digest, "nonce": nonce,
                         "host_build_sha256": manifest.host_build_sha256})
            claimed = True
            output, _ = process.communicate("execute:" + nonce + "\n",
                                            timeout=manifest.lifetime_seconds + SESSION_SLACK_SECONDS)
            messages = [json.loads(line) for line in output.splitlines() if line.strip()]
            if len(messages) == 1 and messages[0].get("kind") == "result":
                result = messages[0]["result"]
            elif messages:
                result = {**result, "studio_messages": messages}
            return {"experiment_id": manifest.experiment_id, "claim_created": True, **result}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if claimed:
                claim.finish(result.get("outcome", "unknown"), {"result": result})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One W10 Studio live session. No target, timing, raw-send or retry switches.")
    parser.add_argument("command", choices=("review", "run"))
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        if args.command == "review":
            manifest, stream, exe = review(Path(args.manifest))
            print(json.dumps({"ok": True, "experiment_id": manifest.experiment_id,
                              "blockers": frame_stream.authority_blockers(Path(args.manifest)),
                              "lifetime_seconds": manifest.lifetime_seconds, "max_frames": manifest.max_frames,
                              "slot_interval_ms": stream["playback_interval_ms"], "device_io": False}))
            raise SystemExit(0)
        outcome = run(Path(args.manifest))
        print(json.dumps(outcome, sort_keys=True))
        raise SystemExit(0 if outcome["outcome"] == "stopped_clean" else 2)
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none is retried
        print(json.dumps({"ok": False, "error": str(exc), "outcome": "unknown"}))
        raise SystemExit(2)
