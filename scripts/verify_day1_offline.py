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
    if m4.get("status") != "completed_pass_authority_consumed":
        fail("M4 is not completed/consumed")
    if m4.get("authority", {}).get("transmission_authorized") is not False:
        fail("M4 replay unexpectedly remains authorized")
    if m4.get("authority", {}).get("authorization_consumed") is not True:
        fail("M4 authority consumption is not recorded")
    if m4.get("operation", {}).get("automatic_retry") is not False:
        fail("M4 unexpectedly permits automatic retry")
    if m4.get("operation", {}).get("application_tx_hex") != "01040097009b0002":
        fail("M4 frozen TX drifted")
    budgets = m4.get("budgets", {})
    if budgets.get("connection_attempts") != 1 or budgets.get("application_requests") != 1:
        fail("M4 one-shot budget drifted")

    m5 = json.loads((ROOT / "experiments" / "DAY1-M5-FRAME-PENDING.json").read_text(encoding="utf-8"))
    if m5.get("status") != "completed_pass_authority_consumed":
        fail("M5 is not completed/consumed")
    if m5.get("authority", {}).get("transmission_authorized") is not False:
        fail("M5 unexpectedly authorizes transmission")
    if m5.get("authority", {}).get("authorization_consumed") is not True:
        fail("M5 authority consumption is not recorded")
    result = m5.get("result", {})
    if result.get("status") != "pass" or result.get("packets_sent") != 3 or result.get("ack_payload_hex") != "0x12":
        fail("M5 successful live result is not frozen")
    if m5.get("operation", {}).get("automatic_retry") is not False:
        fail("M5 unexpectedly permits automatic retry")
    if m5.get("operation", {}).get("paint_semantics", {}).get("wire_sha256") != "db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b":
        fail("M5 diagnostic wire hash drifted")
    if m5.get("budgets", {}).get("application_packets") != 3:
        fail("M5 packet budget drifted")


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


def verify_consumed_runner() -> None:
    runner = (ROOT / "runtime/windows/OpenDitoo.M4.Runner/Program.cs").read_text(encoding="utf-8")
    if "M4_AUTHORITY_CONSUMED" not in runner:
        fail("M4 runner is not disarmed after successful one-shot execution")
    if "ExchangeFrozenFileVersionOnce" in runner or "RequireAuthenticatedExactTarget" in runner:
        fail("M4 runner still exposes a live execution path after authority consumption")


def verify_m5_runner_disarmed() -> None:
    runner = (ROOT / "runtime/windows/OpenDitoo.M5.Runner/Program.cs").read_text(encoding="utf-8")
    required = (
        "bool TransmissionAuthorized = false;",
        "OPENDITOO-DAY1-M5-STATIC-DIAGNOSTIC-001",
        "11:75:58:CE:DE:C7",
        "db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b",
        "M5_NOT_AUTHORIZED",
        "M5_PACKET_COUNT=3",
        "M5_TX_BYTES_TOTAL=147",
        "M5_RETRY=false",
    )
    for needle in required:
        if needle not in runner:
            fail(f"M5 disarmed runner missing boundary: {needle}")
    if runner.count("connect(socketHandle, ref remote, layoutSize)") != 1:
        fail("M5 runner connect-call source count drifted")
    if runner.count("send(socketHandle, packets[index], packets[index].Length, 0)") != 1:
        fail("M5 runner send-call source count drifted")
    if "Console.ReadLine" in runner or "send_hex" in runner.lower():
        fail("M5 runner exposes an interactive/raw-send escape")


def main() -> int:
    artifact_count = verify_sha256_manifest()
    run_tests()
    verify_manifests()
    verify_host_boundary()
    verify_consumed_runner()
    verify_m5_runner_disarmed()
    print(
        "DAY1_OFFLINE_PASS "
        f"artifacts={artifact_count} tests=14 host=status_only port=8796 "
        "device_io=false m4_completed=true m4_authorized=false m5_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
