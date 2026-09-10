#!/usr/bin/env python3
"""Prepare OPENDITOO-WEBCAM-W10-<NNN> (default 001) to grant-ready. Zero device I/O, no claim, no Host session.

Builds and stages the Studio under C:\\temp (WinRT capture fails from the WSL share), runs its
selftest and both parity fixtures from the staged copy, checks the Host identity read-only, then
freezes every producer hash into the manifest. The only Host contact is GET /v1/status.
"""
import json
import re
from pathlib import Path
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import activity_session, frame_stream, webcam_studio, webcam_trial

ROOT = frame_stream.ROOT
ATTEMPT = sys.argv[1] if len(sys.argv) > 1 else "001"
if not re.fullmatch(r"[0-9]{3}", ATTEMPT):
    raise SystemExit("W10_PREP_ATTEMPT_INVALID")
MANIFEST = ROOT / f"experiments/DAY1-WEBCAM-W10-{ATTEMPT}.json"
EVIDENCE = ROOT / f"captures/OPENDITOO-WEBCAM-W10-{ATTEMPT}-PREPARATION-2026-09-10.json"
STAGE = r"C:\temp\openditoo-webcam-studio-w10"
INSTALLED_HOST = Path("/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo/Day1Host/OpenDitoo.Day1.Host.dll")


def powershell(script: str) -> str:
    done = subprocess.run(["powershell.exe", "-NoProfile", "-Command", "$ErrorActionPreference='Stop'; " + script],
                          capture_output=True, text=True, timeout=600)
    output = done.stdout.replace("\r", "")
    print(output, end="")
    if done.returncode != 0:
        raise SystemExit(f"W10_PREP_POWERSHELL_FAILED rc={done.returncode} {done.stderr[-2000:]}")
    return output


def host_identity() -> dict:
    """Read-only identity check. The dashboard may legitimately own the Host right now."""
    token = (ROOT / ".openditoo-local/host.token").read_text(encoding="utf-8").strip()
    request = urllib.request.Request("http://127.0.0.1:8796/v1/status",
                                     headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=3.0) as response:
        body = json.loads(response.read(1024 * 1024))
    idle_view = {**body, "activitySession": {}, "diagnostics": {}}
    webcam_trial._validate_host_preclaim_status(idle_view)  # identity fields only
    return {"target": body["target"], "raw_send_enabled": body["rawSendEnabled"],
            "activity_session_active": body.get("activitySession", {}).get("active")}


def main() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = doc["authority"]
    if authority["transmission_authorized"] or authority["authorization_consumed"]:
        raise SystemExit("W10_PREP_REFUSES_AUTHORIZED_OR_CONSUMED_MANIFEST")
    if activity_session.SessionClaim(doc["experiment_id"]).path.exists():
        raise SystemExit("W10_PREP_CLAIM_ALREADY_EXISTS")
    print("W10_PREP_BEGIN experiment_id=%s device_io=false host_session_io=false claim_created=false" % doc["experiment_id"])
    project = webcam_trial.windows_path(webcam_studio.STUDIO / "OpenDitoo.Webcam.Studio.csproj")
    release = webcam_trial.windows_path(webcam_studio.STUDIO_BIN)
    exe = STAGE + r"\OpenDitoo.Webcam.Studio.exe"
    transform_cases = webcam_trial.windows_path(ROOT / "tests/frame_transform_cases.json")
    encoder_cases = webcam_trial.windows_path(ROOT / "tests/ditoo_encoder_cases.json")
    output = powershell(
        f"dotnet build '{project}' -c Release --nologo -v q; if ($LASTEXITCODE) {{ throw 'BUILD' }}; "
        f"if (Test-Path '{STAGE}') {{ Remove-Item '{STAGE}' -Recurse -Force }}; "
        f"New-Item -ItemType Directory '{STAGE}' | Out-Null; Copy-Item '{release}\\*' '{STAGE}' -Recurse; "
        f"& '{exe}' selftest; if ($LASTEXITCODE) {{ throw 'SELFTEST' }}; "
        f"& '{exe}' transform-selftest '{transform_cases}'; if ($LASTEXITCODE) {{ throw 'TRANSFORM' }}; "
        f"& '{exe}' encoder-selftest '{encoder_cases}'; if ($LASTEXITCODE) {{ throw 'ENCODER' }}")
    for marker in ("STUDIO_SELFTEST_PASS", "TRANSFORM_SELFTEST_PASS", "ENCODER_SELFTEST_PASS"):
        if marker not in output:
            raise SystemExit("W10_PREP_MARKER_MISSING " + marker)
    identity = host_identity()
    host_dll = activity_session.sha256_file(activity_session.HOST_BUILD_DLL)
    if activity_session.sha256_file(INSTALLED_HOST) != host_dll:
        raise SystemExit("W10_PREP_INSTALLED_HOST_DRIFT")
    doc["stream"]["live_source"]["producer_code_sha256"] = {
        str(p.relative_to(ROOT)): activity_session.sha256_file(p)
        for p in webcam_studio.producer_sources() + webcam_studio.producer_binaries()}
    doc["build"]["host_dll_sha256"] = host_dll
    doc["build"]["code_sha256"] = frame_stream.module_hashes()
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    doc["build"]["source_checkpoint"] = head + " + Studio build staged at " + STAGE
    evidence = {
        "schema_version": 1, "experiment_id": doc["experiment_id"], "status": "pass",
        "prepared_from_git_head": head, "staged_executable": exe,
        "checks": {"studio_selftest": "pass", "transform_parity": "pass", "encoder_parity": "pass",
                   "host_identity_read_only": identity, "installed_host_dll_sha256": host_dll},
        "selftest_lines": [line for line in output.splitlines() if line.startswith(("STUDIO_", "TRANSFORM_", "ENCODER_"))],
        "operation": {"claim_created": False, "host_session_io": False, "device_io": False},
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=1) + "\n", encoding="utf-8")
    doc["status"] = "grant_ready_awaiting_named_grant"
    doc["readiness"].update({"grant_ready": True, "blockers": []})
    doc["adapter"]["deployment_state"] = (
        f"PASS preparation at {head}: Studio built, staged to {STAGE}, selftest + transform/encoder parity passed "
        "from the staged copy, Host identity checked read-only. No claim, session or device I/O.")
    MANIFEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    manifest, _, _ = webcam_studio.review(MANIFEST)  # the WSL review must pass as prepared
    print(json.dumps({"W10_PREP_PASS": manifest.experiment_id, "grant_ready": True,
                      "blockers_until_grant": frame_stream.authority_blockers(MANIFEST),
                      "manifest_sha256": activity_session.sha256_file(MANIFEST), "device_io": False}))


if __name__ == "__main__":
    main()
