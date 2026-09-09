"""Offline envelope validation and one camera-ready-before-claim Windows launch."""
import json
from pathlib import Path
import re
import select
import subprocess

from host import activity_session, frame_stream

ROOT = frame_stream.ROOT
RUNNER = ROOT / "runtime/windows/OpenDitoo.Webcam.Runner"
PROBE = ROOT / "runtime/windows/OpenDitoo.Webcam.Probe"


def windows_path(path: Path) -> str:
    return subprocess.check_output(["wslpath", "-w", str(path.resolve())], text=True).strip()


def executable_path(windows: str) -> Path:
    if not re.fullmatch(r"C:\\[^\r\n]+\\OpenDitoo.Webcam.Runner.exe", windows) or ".." in windows.split("\\"):
        raise ValueError("ADAPTER_WINDOWS_PATH_INVALID")
    return Path("/mnt/c") / windows[3:].replace("\\", "/")


def review(path: Path, *, authority: bool = False):
    manifest, _, stream = frame_stream.load_stream_manifest(path, require_authority=authority)
    doc = manifest.raw
    if not re.fullmatch(r"OPENDITOO-WEBCAM-N980P-[0-9]{3}", manifest.experiment_id):
        raise ValueError("WEBCAM_EXPERIMENT_ID_INVALID")
    if (stream["source_kind"], stream["session_profile"], stream["playback_interval_ms"],
        manifest.lifetime_seconds, manifest.min_frame_interval_ms, manifest.max_frames,
        manifest.max_tx_bytes) != ("live", "streaming_ack_clock", 90, 10, 40, 112, 118048):
        raise ValueError("WEBCAM_ENVELOPE_MISMATCH")
    producer = stream["live_source"]
    camera, transform = producer["camera"], producer["transform"]
    for key, expected in {"usb_vid": "0C45", "usb_pid": "2690", "subtype": "NV12", "width": 640,
                          "height": 480, "requested_fps": 60, "acquisition_mode": "Realtime"}.items():
        if camera.get(key) != expected:
            raise ValueError(f"CAMERA_ENVELOPE_MISMATCH:{key}")
    for key, expected in {"preset": "srgb_area", "linear_light": False, "zoom": 1, "offset_x": 0,
                          "offset_y": 0, "mirror": True, "quarter_turns": 0}.items():
        if transform.get(key) != expected:
            raise ValueError(f"TRANSFORM_ENVELOPE_MISMATCH:{key}")
    hashes = producer["producer_code_sha256"]
    required = list(RUNNER.glob("*.cs")) + list(RUNNER.glob("*.csproj"))
    required += [PROBE / name for name in ("WebcamFrames.cs", "LatestFrameSlot.cs", "FrameTransform.cs", "DitooEncoder.cs")]
    required += [ROOT / "host/webcam_trial.py", ROOT / "cli/webcam.py"]
    if not {str(p.relative_to(ROOT)) for p in required} <= hashes.keys():
        raise ValueError("WEBCAM_SOURCE_HASHES_INCOMPLETE")
    for relative, expected in hashes.items():
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or not (ROOT / candidate).is_file():
            raise ValueError(f"PRODUCER_ARTIFACT_MISSING:{relative}")
        if activity_session.sha256_file(ROOT / candidate) != expected:
            raise ValueError(f"PRODUCER_HASH_DRIFT:{relative}")
    if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != manifest.host_build_sha256:
        raise ValueError("HOST_BUILD_HASH_DRIFT")
    exe = executable_path(doc["adapter"]["windows_executable"])
    binary_root = RUNNER / "bin/Release/net8.0-windows10.0.19041.0"
    binary_files = [p for p in binary_root.iterdir() if p.suffix in (".dll", ".exe", ".json")]
    if not binary_files or not (binary_root / "OpenDitoo.Webcam.Runner.dll").is_file():
        raise ValueError("ADAPTER_BUILD_MISSING")
    for binary in binary_files:
        expected = hashes.get(str(binary.relative_to(ROOT)))
        if not expected or activity_session.sha256_file(exe.parent / binary.name) != expected:
            raise ValueError(f"DEPLOYED_ADAPTER_HASH_DRIFT:{binary.name}")
    if authority:
        if doc["authority"].get("grant_text") != "Grant " + manifest.experiment_id:
            raise ValueError("EXACT_NAMED_GRANT_REQUIRED")
        if not doc["readiness"]["grant_ready"] or doc["readiness"]["blockers"]:
            raise ValueError("WEBCAM_NOT_READY")
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
    digest = activity_session.sha256_file(path)
    claimed = False
    result = {"outcome": "unknown", "terminalReason": "runner_failed"}
    with subprocess.Popen([str(exe), "live", windows_path(path), windows_path(ROOT)],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as process:
        try:
            if not select.select([process.stdout], [], [], 20)[0]:
                raise ValueError("CAMERA_READY_TIMEOUT")
            ready = json.loads(process.stdout.readline(16384))
            nonce = ready.get("nonce", "")
            if (ready.get("kind") != "camera_ready" or ready.get("experiment_id") != manifest.experiment_id
                    or ready.get("manifest_sha256") != digest or not re.fullmatch(r"[a-f0-9]{32}", nonce)):
                raise ValueError("CAMERA_NOT_READY")
            # Revalidate after potentially slow camera startup, still before consumption.
            review(path, authority=True)
            if activity_session.sha256_file(path) != digest:
                raise ValueError("MANIFEST_CHANGED_DURING_PREFLIGHT")
            claim.claim({"manifest_sha256": digest, "nonce": nonce,
                         "host_build_sha256": manifest.host_build_sha256})
            claimed = True
            output, _ = process.communicate("execute:" + nonce + "\n", timeout=40)
            messages = [json.loads(line) for line in output.splitlines() if line.strip()]
            if len(messages) == 1 and messages[0].get("kind") == "result":
                result = messages[0]["result"]
            return {"experiment_id": manifest.experiment_id, "claim_created": True, **result}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if claimed:
                claim.finish(result.get("outcome", "unknown"), {"result": result})
