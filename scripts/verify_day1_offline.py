#!/usr/bin/env python3
"""Offline Day-1 readiness verifier. Never performs network or device I/O."""
from __future__ import annotations

import hashlib
import json
import re
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


def run_tests() -> int:
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
    match = re.search(r"^Ran (\d+) tests", proc.stderr, re.MULTILINE)
    if not match:
        fail("offline unit test count is unreadable")
    return int(match.group(1))


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
    protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs").read_text(encoding="utf-8")
    transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
    cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
    if 'HOST_ORIGIN = "http://127.0.0.1:8796"' not in cli:
        fail("CLI origin is not fixed to OpenDitoo 8796")
    required_program = (
        'masterTransmitEnabled = true',
        'transportConfigured = true',
        'targetBound = true',
        'rawSendEnabled = false',
        'app.MapPost("/v1/image/show"',
        'ShowImageRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256)',
    )
    for needle in required_program:
        if needle not in program:
            fail(f"typed image Host boundary missing {needle}")
    if 'TargetMac = "11:75:58:CE:DE:C7"' not in protocol or 'TargetRfcommChannel = 1' not in protocol:
        fail("typed image Host target/channel is not fixed")
    if transport.count('connect(socketHandle, ref remote, layoutSize)') != 1:
        fail("typed image Host connect-call source count drifted")
    if transport.count('send(socketHandle, packets[index], packets[index].Length, 0)') != 1:
        fail("typed image Host send-call source count drifted")
    if 'NO_RETRY' not in transport:
        fail("typed image Host lost no-retry boundary")
    combined = program + "\n" + cli
    for forbidden in ("send_hex", "packetHex", "127.0.0.1:8779"):
        if forbidden.lower() in combined.lower():
            fail(f"typed image surface exposes forbidden escape/collision: {forbidden}")


def verify_activation_boundary() -> None:
    """The M9 session surface must stay bounded, one-use and unauthorized."""
    manifest_path = ROOT / "experiments" / "DAY1-M9-ACTIVATION-001-PENDING.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authority = manifest.get("authority", {})
    if authority.get("transmission_authorized") is not False:
        fail("M9 activation manifest is armed; it must stay pending until an operator grants it")
    if authority.get("authorization_consumed") is not False:
        fail("M9 activation manifest consumption flag drifted")
    if authority.get("experiment_id") != manifest.get("experiment_id"):
        fail("M9 grant does not name its own experiment")
    session = manifest.get("session", {})
    if session.get("min_frame_interval_ms") != 1118:
        fail("M9 pacing floor drifted from the accepted ceiling")
    for flag in ("automatic_retry", "automatic_reconnect", "stock_screen_reclaim",
                 "replay_after_interruption"):
        if session.get(flag) is not False:
            fail(f"M9 activation manifest permits {flag}")

    host = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs").read_text(encoding="utf-8")
    session_py = (ROOT / "host/activity_session.py").read_text(encoding="utf-8")
    if "AcceptedMinFrameIntervalMs = 1118;" not in host:
        fail("Host pacing floor drifted from the accepted ceiling")
    if "ACCEPTED_MIN_FRAME_INTERVAL_MS = 1118" not in session_py:
        fail("CLI pacing floor drifted from the accepted ceiling")
    if "AUTHORITY_ALREADY_CONSUMED" not in host or "AUTHORITY_ALREADY_CONSUMED" not in session_py:
        fail("one-use authority enforcement is missing on one side")
    # Authority must be consumed before the socket exists, on both sides.
    if host.index('Append("open"') > host.index("DitooLink.Connect"):
        fail("Host opens a link before consuming the experiment id")
    for forbidden in ("def release", "def unclaim", "authorization_consumed = False"):
        if forbidden in session_py:
            fail(f"a consumed claim must never be releasable: {forbidden}")

    transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
    if "PollIdle()" not in transport:
        fail("the link no longer observes the device while idle")
    if "DitooTakeoverException" not in transport:
        fail("an unsolicited state report no longer ends the session")
    for forbidden in ("Reconnect(", "Reopen(", "Resend(", "ReclaimScreen"):
        if forbidden in transport or forbidden in host:
            fail(f"session surface gained a forbidden recovery path: {forbidden}")


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
    test_count = run_tests()
    verify_manifests()
    verify_host_boundary()
    verify_activation_boundary()
    verify_consumed_runner()
    verify_m5_runner_disarmed()
    print(
        "DAY1_OFFLINE_PASS "
        f"artifacts={artifact_count} tests={test_count} host=typed_image port=8796 "
        "device_io=false m4_completed=true m4_authorized=false m5_authorized=false "
        "m9_activation_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
