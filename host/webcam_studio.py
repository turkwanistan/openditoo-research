"""W10 webcam Studio: offline envelope review and one camera-ready-before-claim live launch.

Same authority shape as the W7-W9 trials (fresh manifest, exact named grant, durable one-use
claim taken only against the Studio's camera-ready nonce), a different producer: the Studio
window, whose framing the operator may adjust while it runs. Framing changes pixels only; the
budgets already assume the encoder's worst-case frame, so the reviewed envelope does not move.
"""
import argparse
import json
import os
import secrets
import stat
import time
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


# -- W10C: standing on-demand webcam policy -------------------------------------------------------
#
# Same shape as Runtime 003 for the dashboard: a committed template that stays unauthorized, and a
# local mode-0600 copy materialized only after the owner's exact grant. It authorizes one thing:
# while the owner has the Studio window open, back-to-back bounded sessions, each under a fresh
# one-use id claimed against the Studio's nonce. The next session starts only after a clean budget
# or lifetime end; anything else ends the launch with no retry. Runtime 003 is not widened.

POLICY_ID = "OPENDITOO-WEBCAM-PRODUCT-005"
POLICY_TEMPLATE = ROOT / "product/OPENDITOO-WEBCAM-PRODUCT-005.json"
LOCAL_POLICY = ROOT / ".openditoo-local/webcam-product-policy.json"
# 002: one connection per launch. 001 rolled 60 s / 500-frame sessions over and the fourth reopen
# hit IMAGE_RX_RECV_TIMEOUT (run 8f36a6d3); the Runtime 004 Host gives streaming its own 1800 s /
# 45000-frame ceiling, so a launch no longer reopens at all.
ENVELOPE = {"session_profile": "streaming_ack_clock", "host_floor_ms": 40, "slot_interval_ms": 50,
            "session_lifetime_seconds": 1800, "max_frames": 36001, "max_application_packets": 108003,
            "max_tx_bytes": 36001 * 1054, "ack_timeout_ms_per_frame": 5000, "handover_settle_seconds": 8,
            "max_sessions_per_launch": 1, "max_launch_seconds": 1800}
CONTINUE_ONLY_AFTER = ["budget_exhausted", "lifetime_expired"]
CLEAN_OUTCOMES = ("stopped_clean", "stopped_yielded_to_stock")


def load_policy(path: Path = LOCAL_POLICY, *, authority: bool = True, verify: bool = True) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("policy_id") != POLICY_ID:
        raise ValueError("WEBCAM_PRODUCT_POLICY_ID_MISMATCH")
    if doc.get("target") != {"exact_unit_id": activity_session.EXACT_UNIT_ID,
                             "installed_firmware": activity_session.INSTALLED_FIRMWARE}:
        raise ValueError("WEBCAM_PRODUCT_TARGET_MISMATCH")
    if doc.get("envelope") != ENVELOPE:
        raise ValueError("WEBCAM_PRODUCT_ENVELOPE_MISMATCH")
    behavior = doc.get("behavior") or {}
    if any(behavior.get(flag) is not False for flag in
           ("automatic_retry", "automatic_reconnect", "stock_screen_reclaim", "raw_send_enabled",
            "target_override_enabled", "start_at_logon")):
        raise ValueError("WEBCAM_PRODUCT_BEHAVIOR_FORBIDDEN")
    if behavior.get("continue_only_after") != CONTINUE_ONLY_AFTER or behavior.get("restore_dashboard_on_exit") is not True:
        raise ValueError("WEBCAM_PRODUCT_CONTINUATION_RULE_MISMATCH")
    grant = doc.get("authority") or {}
    if authority:
        info = Path(path).stat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("WEBCAM_PRODUCT_POLICY_MODE_INVALID")
        if not (grant.get("webcam_product_authorized") is True and grant.get("revoked") is False
                and grant.get("grant_text") == "Grant " + POLICY_ID and grant.get("granted_by")
                and grant.get("grant_scope") == grant.get("grant_scope_requested")):
            raise ValueError("WEBCAM_PRODUCT_GRANT_REQUIRED")
    if verify:
        hashes = doc["build"]["producer_code_sha256"]
        required = {str(p.relative_to(ROOT)) for p in producer_sources() + producer_binaries()}
        if not hashes or not required <= hashes.keys():
            raise ValueError("WEBCAM_PRODUCT_HASHES_INCOMPLETE")
        for relative, expected in hashes.items():
            if activity_session.sha256_file(ROOT / relative) != expected:
                raise ValueError(f"PRODUCER_HASH_DRIFT:{relative}")
        exe = executable_path(doc["adapter"]["windows_executable"])
        for binary in producer_binaries():
            if activity_session.sha256_file(exe.parent / binary.name) != hashes[str(binary.relative_to(ROOT))]:
                raise ValueError(f"INSTALLED_STUDIO_HASH_DRIFT:{binary.name}")
        if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != doc["build"]["host_dll_sha256"]:
            raise ValueError("HOST_BUILD_HASH_DRIFT")
    return doc


def grant_policy(grant_text: str, granted_by: str) -> Path:
    """Materialize the local policy from the committed template after the owner's exact grant."""
    if grant_text != "Grant " + POLICY_ID:
        raise ValueError("EXACT_NAMED_GRANT_REQUIRED")
    if LOCAL_POLICY.exists():
        raise ValueError("WEBCAM_PRODUCT_POLICY_ALREADY_PRESENT")
    doc = load_policy(POLICY_TEMPLATE, authority=False)
    if doc["authority"]["webcam_product_authorized"] is not False:
        raise ValueError("COMMITTED_TEMPLATE_MUST_STAY_UNAUTHORIZED")
    doc["authority"].update({"webcam_product_authorized": True, "revoked": False, "grant_text": grant_text,
                             "granted_by": granted_by, "grant_scope": doc["authority"]["grant_scope_requested"]})
    fd = os.open(LOCAL_POLICY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
    load_policy(LOCAL_POLICY)
    return LOCAL_POLICY


def revoke_policy() -> Path:
    doc = json.loads(LOCAL_POLICY.read_text(encoding="utf-8"))
    doc["authority"].update({"webcam_product_authorized": False, "revoked": True})
    target = ROOT / ".openditoo-local/revoked" / time.strftime("webcam-product-policy-%Y%m%dT%H%M%S.json")
    target.parent.mkdir(mode=0o700, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    LOCAL_POLICY.unlink()
    return target


def run_sessions(process, policy_sha: str, *, claim_dir: Path = activity_session.CLAIM_DIR,
                 max_sessions: int = ENVELOPE["max_sessions_per_launch"],
                 max_seconds: float = ENVELOPE["max_launch_seconds"], host_build_sha256: str = "") -> dict:
    """The per-session claim protocol with the Studio. `process` has unbuffered binary pipes:
    a buffered reader could hold the next message while select() waits on the empty fd."""
    run_nonce = secrets.token_hex(4)
    started = time.monotonic()
    sessions, final, pending = [], None, None

    def send(text: str) -> None:
        process.stdin.write((text + "\n").encode())
        process.stdin.flush()

    try:
        while True:
            if not select.select([process.stdout], [], [], ENVELOPE["session_lifetime_seconds"] + SESSION_SLACK_SECONDS)[0]:
                raise ValueError("STUDIO_SILENT")
            line = process.stdout.readline(1 << 20)
            if not line:
                break
            message = json.loads(line)
            kind = message.get("kind")
            if kind == "session_ready":
                nonce = message.get("nonce", "")
                if pending or message.get("policy_sha256") != policy_sha or not re.fullmatch(r"[a-f0-9]{32}", nonce):
                    raise ValueError("STUDIO_PROTOCOL_VIOLATION")
                if len(sessions) >= max_sessions or time.monotonic() - started >= max_seconds:
                    send("end")
                    continue
                experiment_id = f"OPENDITOO-WEBCAM-LIVE-{run_nonce}-{len(sessions) + 1:03d}"
                claim = activity_session.SessionClaim(experiment_id, claim_dir)
                claim.claim({"policy_sha256": policy_sha, "nonce": nonce, "host_build_sha256": host_build_sha256})
                pending = (claim, experiment_id)
                send(f"execute:{experiment_id}:{nonce}")
            elif kind == "session_result":
                if not pending or message.get("experiment_id") != pending[1]:
                    raise ValueError("STUDIO_PROTOCOL_VIOLATION")
                result = message["result"]
                pending[0].finish(result.get("outcome", "unknown"), {"result": result})
                sessions.append({key: result.get(key) for key in (
                    "experimentId", "outcome", "terminalReason", "frames", "packets", "bytes", "ackedTransportFps")})
                pending = None
            elif kind in ("done", "error"):
                final = message
    finally:
        if pending:
            pending[0].finish("unknown", {"result": {"terminalReason": "studio_ended_without_result"}})
    return {"policy_id": POLICY_ID, "run_nonce": run_nonce, "sessions": sessions, "final": final,
            # A Host-confirmed stock yield (Ditoo button press) is a clean end, not a fault.
            "outcome": "stopped_clean" if sessions and all(s["outcome"] in CLEAN_OUTCOMES for s in sessions)
            and (final or {}).get("kind") == "done" else "unknown"}


def run_policy(path: Path = LOCAL_POLICY) -> dict:
    doc = load_policy(path)
    exe = executable_path(doc["adapter"]["windows_executable"])
    service = subprocess.run(["systemctl", "--user", "is-active", "openditoo-product.service"],
                             capture_output=True, text=True, timeout=5)
    if service.stdout.strip() != "inactive":
        raise ValueError("PRODUCT_CONTROLLER_MUST_BE_STOPPED")
    webcam_trial._host_preclaim_status()
    with subprocess.Popen([str(exe), "live-policy", webcam_trial.windows_path(path), webcam_trial.windows_path(ROOT)],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          bufsize=0) as process:
        try:
            return run_sessions(process, activity_session.sha256_file(path),
                                host_build_sha256=doc["build"]["host_dll_sha256"])
        finally:
            if process.poll() is None:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One W10 Studio live session. No target, timing, raw-send or retry switches.")
    parser.add_argument("command", choices=("review", "run", "policy-check", "policy-run", "policy-grant", "policy-revoke"))
    parser.add_argument("--manifest")
    parser.add_argument("--grant-text")
    parser.add_argument("--granted-by")
    args = parser.parse_args()
    try:
        if args.command == "policy-check":
            doc = load_policy()
            print(json.dumps({"ok": True, "policy_id": POLICY_ID, "envelope": doc["envelope"], "device_io": False}))
            raise SystemExit(0)
        if args.command == "policy-grant":
            print(json.dumps({"ok": True, "policy": str(grant_policy(args.grant_text or "", args.granted_by or ""))}))
            raise SystemExit(0)
        if args.command == "policy-revoke":
            print(json.dumps({"ok": True, "revoked_record": str(revoke_policy())}))
            raise SystemExit(0)
        if args.command == "policy-run":
            outcome = run_policy()
            print(json.dumps(outcome, sort_keys=True))
            raise SystemExit(0 if outcome["outcome"] == "stopped_clean" else 2)
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
