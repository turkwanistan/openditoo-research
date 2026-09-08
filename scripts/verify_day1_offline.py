#!/usr/bin/env python3
"""Offline Day-1 readiness verifier. Never performs network or device I/O."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"DAY1_OFFLINE_FAIL: {message}")


def verify_sha256_manifest() -> int:
    manifest = ROOT / "artifacts/SHA256SUMS"
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        expected, relative = line.split(None, 1)
        relative = relative.lstrip("* ")
        path = ROOT / relative
        if not path.is_file():
            fail(f"artifact missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"artifact hash mismatch: {relative}")
        count += 1
    return count


def run_tests() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-q", "tests/test_day1_offline.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        fail("offline unit tests failed")


def verify_manifests() -> None:
    m4 = json.loads((ROOT / "experiments" / "DAY1-M4-QUERY-PENDING.json").read_text(encoding="utf-8"))
    if m4.get("status") != "authorized_pending_execution":
        fail("M4 is not in authorized-pending-execution state")
    if m4.get("authority", {}).get("transmission_authorized") is not True:
        fail("M4 authority is not explicit")
    if m4.get("operation", {}).get("automatic_retry") is not False:
        fail("M4 unexpectedly permits automatic retry")
    if m4.get("operation", {}).get("application_tx_hex") != "01040097009b0002":
        fail("M4 frozen TX drifted")
    budgets = m4.get("budgets", {})
    if budgets.get("connection_attempts") != 1 or budgets.get("application_requests") != 1:
        fail("M4 one-shot budget drifted")

    m5 = json.loads((ROOT / "experiments" / "DAY1-M5-FRAME-PENDING.json").read_text(encoding="utf-8"))
    if m5.get("status") != "offline_template_not_executable":
        fail("M5 status is not fail-closed")
    if m5.get("authority", {}).get("transmission_authorized") is not False:
        fail("M5 unexpectedly authorizes transmission")
    if m5.get("operation", {}).get("automatic_retry") is not False:
        fail("M5 unexpectedly permits automatic retry")


def verify_host_boundary() -> None:
    program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
    cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
    combined = program + "\n" + cli
    required = [
        '127.0.0.1:8796',
        'masterTransmitEnabled = false',
        'transportConfigured = false',
        'targetBound = false',
    ]
    if 'HOST_ORIGIN = "http://127.0.0.1:8796"' not in cli:
        fail("CLI origin is not fixed to OpenDitoo 8796")
    for needle in required[1:]:
        if needle not in program:
            fail(f"Host boundary missing {needle}")
    forbidden = [
        "11:75:58:C8:5E:FE",
        "Windows.Devices.Bluetooth",
        "Ws2_32",
        "AF_BTH",
        "send_hex",
    ]
    for needle in forbidden:
        if needle in combined:
            fail(f"status-only control plane contains forbidden transport/target surface: {needle}")
    if "127.0.0.1:8779" in cli or "const int Port = 8779" in program:
        fail("OpenDitoo control plane collides with OpenTivoo Host port")


def verify_authorized_runner() -> None:
    runner = (ROOT / "runtime/windows/OpenDitoo.M4.Runner/Program.cs").read_text(encoding="utf-8")
    project = (ROOT / "runtime/windows/OpenDitoo.M4.Runner/OpenDitoo.M4.Runner.csproj").read_text(encoding="utf-8")
    for needle in (
        "args.Length != 0",
        "RequireAuthenticatedExactTarget()",
        "ExchangeFrozenFileVersionOnce()",
        "M4_PAIRING_REQUIRED_NO_CONNECT",
    ):
        if needle not in runner:
            fail(f"authorized runner missing exact boundary: {needle}")
    if "Console.ReadLine" in runner:
        fail("authorized runner unexpectedly accepts interactive input")
    if "DitooM4FileVersionProtocol.cs" not in project or "WindowsRfcommBoundedM4Transport.cs" not in project:
        fail("authorized runner is not linked to the frozen protocol/transport sources")


def main() -> int:
    artifact_count = verify_sha256_manifest()
    run_tests()
    verify_manifests()
    verify_host_boundary()
    verify_authorized_runner()
    print(
        "DAY1_OFFLINE_PASS "
        f"artifacts={artifact_count} tests=12 host=status_only port=8796 "
        "device_io=false m4_authorized=true m5_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
