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


def _s1_stream_armed() -> bool:
    for path in sorted((ROOT / "experiments").glob("DAY1-S*-STREAM-*.json")):
        authority = json.loads(path.read_text(encoding="utf-8")).get("authority", {})
        if authority.get("transmission_authorized") is True and \
                authority.get("authorization_consumed") is not True:
            return True
    return False


def _m9_armed() -> bool:
    manifest = json.loads((ROOT / "experiments" / "DAY1-M9-ACTIVATION-001.json").read_text(encoding="utf-8"))
    return manifest.get("authority", {}).get("transmission_authorized") is True


def verify_activity_ui() -> None:
    """The rendered page must still be the approved design, derived not transcribed."""
    proc = subprocess.run([sys.executable, "scripts/generate_activity_ui_data.py", "--check"],
                          cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0 or "ACTIVITY_UI_DATA_OK" not in proc.stdout:
        sys.stderr.write(proc.stdout + proc.stderr)
        fail("generated activity UI data no longer matches assets/ui/reference")
    for name in ("all_green_16x16.png", "all_yellow_16x16.png", "all_red_16x16.png",
                 "all_grey_16x16.png", "mixed_state_16x16.png",
                 "left_activity_blue_override_16x16.png",
                 "mid_activity_blue_override_16x16.png",
                 "right_activity_blue_override_16x16.png"):
        if not (ROOT / "assets/ui/reference" / name).is_file():
            fail(f"approved UI reference frame missing: {name}")


def verify_collection_worker() -> None:
    """The installed collection worker must be structurally incapable of transmitting."""
    unit = (ROOT / "runtime/wsl/openditoo-collect.service").read_text(encoding="utf-8")
    exec_lines = [line for line in unit.splitlines() if line.startswith("ExecStart")]
    if len(exec_lines) != 1 or "activity-status --collect" not in exec_lines[0]:
        fail("the collection worker runs something other than activity-status --collect")
    for forbidden in ("activity-session", "image-show", "sequence-run", "session/open"):
        if forbidden in unit:
            fail(f"the collection worker could reach the device: {forbidden}")
    if any(line.strip().startswith("PrivateTmp") for line in unit.splitlines()):
        fail("PrivateTmp breaks ssh to the remote activity sources")


def verify_activation_boundary() -> None:
    """The M9 session surface must stay bounded, one-use and unauthorized."""
    manifest_path = ROOT / "experiments" / "DAY1-M9-ACTIVATION-001.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authority = manifest.get("authority", {})
    if authority.get("experiment_id") != manifest.get("experiment_id"):
        fail("M9 grant does not name its own experiment")
    consumed = authority.get("authorization_consumed") is True
    if consumed:
        # A consumed manifest must carry its result, including its honest partials.
        if authority.get("transmission_authorized") is not False:
            fail("M9 activation manifest is consumed but still armed")
        result = manifest.get("result") or {}
        if not result.get("acceptance"):
            fail("M9 activation manifest is consumed without recorded acceptance")
        if not result.get("root_cause") and result.get("status") != "pass":
            fail("a non-pass M9 result must record its root cause")
    armed = authority.get("transmission_authorized") is True
    if armed:
        # An armed manifest is allowed, but only fully attributed and only while the
        # routing documents say so. This is stricter than the pending case, not looser.
        if authority.get("authorization_consumed") is True:
            fail("M9 activation manifest is armed AND consumed; a consumed grant is never re-armed")
        for field in ("granted_by", "grant_text", "expires_at", "grant_scope"):
            if not authority.get(field):
                fail(f"M9 activation manifest is armed without {field}")
        if not manifest.get("build", {}).get("installed_dll_sha256_verified"):
            fail("M9 activation manifest is armed without a verified installed Host identity")
        handoff = (ROOT / "notes/OPENDITOO-HANDOFF-2026-09-09.md").read_text(encoding="utf-8")
        if manifest["experiment_id"] not in handoff:
            fail("a live grant must be named in the handoff; the routing docs are stale")
        if "nothing is currently authorized" in handoff.lower():
            fail("the handoff claims nothing is authorized while a manifest is armed")
    session = manifest.get("session", {})
    interval = session.get("min_frame_interval_ms")
    if not isinstance(interval, int) or interval < 150:
        fail("M9 manifest attempts to beat the 150 ms product operating floor")
    for flag in ("automatic_retry", "automatic_reconnect", "stock_screen_reclaim",
                 "replay_after_interruption"):
        if session.get(flag) is not False:
            fail(f"M9 activation manifest permits {flag}")

    host = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs").read_text(encoding="utf-8")
    session_py = (ROOT / "host/activity_session.py").read_text(encoding="utf-8")
    if "AcceptedMinFrameIntervalMs = 150;" not in host:
        fail("Host pacing floor drifted from the measured product operating rate")
    if "ActivitySendSpacingMs = 10;" not in host:
        fail("Host activity-session packet spacing drifted from the R2b/R3/R4 accepted value")
    if "ACCEPTED_MIN_FRAME_INTERVAL_MS = 150" not in session_py:
        fail("CLI pacing floor drifted from the measured product operating rate")
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


def verify_product_runtime_boundary() -> None:
    """Persistent product mode is a separate, disabled-by-default authority shape."""
    historical_path = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-001.json"
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    if historical.get("authority", {}).get("persistent_runtime_authorized") is not False:
        fail("historical Runtime 001 committed template gained authority")
    policy_path = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-002.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("runtime_revision") != 2:
        fail("current product policy is not Runtime 002")
    if policy.get("product_id") != "OPENDITOO-MCP-DASHBOARD-V1":
        fail("product policy id drifted")
    target = policy.get("target", {})
    if target.get("exact_unit_id") != "11:75:58:CE:DE:C7" or target.get("rfcomm_channel") != 1:
        fail("product policy target/channel is not exact-unit bound")
    behavior = policy.get("behavior", {})
    if behavior.get("automatic_reconnect") is not True or behavior.get("reclaim_on_canvas_invalidated") is not True:
        fail("product policy lost plug-and-play reconnect/reclaim semantics")
    if behavior.get("raw_send_enabled") is not False or behavior.get("target_override_enabled") is not False:
        fail("product policy exposes raw send or target override")
    authority = policy.get("authority", {})
    if authority.get("persistent_runtime_authorized") is not False or authority.get("grant_scope") is not None:
        fail("committed product policy must never carry standing authority")

    product_py = (ROOT / "host/product_runtime_v2.py").read_text(encoding="utf-8")
    if "activity_session.run_session" not in product_py:
        fail("product supervisor no longer reuses bounded activity sessions")
    if "canvas_invalidated" not in product_py or "reconnect_backoff_seconds" not in product_py:
        fail("product supervisor lost reclaim/backoff recovery")
    for forbidden in ("import socket", "BluetoothAddress", "send_hex", "packetHex"):
        if forbidden in product_py:
            fail(f"product supervisor gained a transport/raw-send escape: {forbidden}")

    cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
    if "_product_runtime_module" not in cli or "runtime_revision" not in cli:
        fail("CLI lost frozen product runtime revision selection")

    unit = (ROOT / "runtime/wsl/openditoo-product.service").read_text(encoding="utf-8")
    exec_lines = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    if len(exec_lines) != 1 or "product-runtime" not in exec_lines[0] or "product-runtime-policy.json" not in exec_lines[0]:
        fail("product systemd service does not run exactly the typed product runtime")
    for required in ("Restart=on-failure", "KillSignal=SIGTERM", "NoNewPrivileges=true", "UMask=0077"):
        if required not in unit:
            fail(f"product systemd hardening missing: {required}")
    if any(line.strip().startswith("PrivateTmp=") for line in unit.splitlines()):
        fail("PrivateTmp breaks ssh-backed MCP activity sources in product mode")

    wsl_install = (ROOT / "runtime/wsl/install_openditoo_product.sh").read_text(encoding="utf-8")
    for required in ('--prepare)', '--rollback)', '--uninstall)', 'restore_collector',
                     'disable --now "$COLLECT_TIMER"', 'persistent_runtime_authorized'):
        if required not in wsl_install:
            fail(f"product WSL lifecycle lost transactional boundary: {required}")
    prepare = wsl_install[wsl_install.index('--prepare)'):wsl_install.index('--start)')]
    if 'systemctl --user start "$PRODUCT_SERVICE"' in prepare:
        fail("product PREPARE may start transmission before Windows task registration")

    ps = (ROOT / "runtime/windows/install_openditoo_product_runtime.ps1").read_text(encoding="utf-8")
    for required in ("$TaskName = 'OpenDitoo Product Runtime'", "$HostTaskName = 'OpenDitoo Day1 Host'",
                     "$OpenTivooTaskName = 'OpenTivoo Product Runtime'", "New-ScheduledTaskTrigger -AtLogOn",
                     "Invoke-WslProduct '--prepare'", "Invoke-WslProduct '--rollback'"):
        if required not in ps:
            fail(f"Windows product bootstrap missing boundary: {required}")
    for forbidden in ("Stop-ScheduledTask -TaskName $HostTaskName",
                      "Unregister-ScheduledTask -TaskName $HostTaskName",
                      "Stop-ScheduledTask -TaskName $OpenTivooTaskName",
                      "Unregister-ScheduledTask -TaskName $OpenTivooTaskName"):
        if forbidden in ps:
            fail(f"product bootstrap may mutate preserved runtime: {forbidden}")


def verify_stream_boundary() -> None:
    """The general frame-streaming path reuses the accepted transport, and is unarmed."""
    manifests = sorted((ROOT / "experiments").glob("DAY1-S*-STREAM-*.json"))
    if not manifests:
        fail("the stream milestone has no experiment manifest")
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        authority = data.get("authority", {})
        if data.get("kind") != "frame_stream":
            fail(f"{path.name} is not a frame_stream manifest")
        # An armed manifest is REPORTED, not failed: a grant is session-local and the
        # verifier must still pass while an authorized trial is actually being run.
        # Structural boundaries below are the hard failures.
    # The streaming pacing profile must stay a NAME the Host resolves, never caller timing,
    # and must not disturb the activity dashboard's constants.
    host_cs = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs").read_text(encoding="utf-8")
    for needed in ('ProfileActivity = "activity"', 'ProfileStreamingAckClock = "streaming_ack_clock"',
                   "AcceptedMinFrameIntervalMs = 150;", "ActivitySendSpacingMs = 10;",
                   "StreamingMinFrameIntervalMs = 40;", "StreamingSendSpacingMs = 0;",
                   'SESSION_PROFILE_UNKNOWN',
                   "if (string.IsNullOrWhiteSpace(requested)) return ProfileActivity;",
                   "SendFrameGroup(packets, null, framesSent, SpacingFor(profile))"):
        if needed not in host_cs:
            fail(f"Host session profile boundary missing: {needed}")
    program_cs = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
    for forbidden in ("request.SendSpacingMs, request.SessionProfile", "SpacingFor(request.MinFrame"):
        if forbidden in program_cs:
            fail(f"session open exposes caller-supplied timing: {forbidden}")
    module = (ROOT / "host/frame_stream.py").read_text(encoding="utf-8")
    # The client's streaming floor must equal the Host's, or a stream earns a terminal
    # pacing refusal instead of a slow frame. This is what OPENDITOO-S2-STREAM-RATE-001 cost.
    import re as _re
    match = _re.search(r"StreamingMinFrameIntervalMs = (\d+);", host_cs)
    if not match:
        fail("Host streaming floor is unreadable")
    if f"STREAMING_HOST_FLOOR_MS = {match.group(1)}" not in module:
        fail(f"client streaming floor disagrees with the Host's {match.group(1)} ms")
    # Streaming must not grow a second Bluetooth stack, route or authority path: it
    # renders frames and hands them to the one existing typed session client.
    for forbidden in ("socket", "urllib", "http", "subprocess", "def release", "def unclaim"):
        if forbidden in module:
            fail(f"frame_stream reaches past the typed session transport: {forbidden}")
    for needed in ("MAX_PALETTE_COLORS", "authority_blockers", "SessionClaim"):
        if needed not in module:
            fail(f"frame_stream lost a required boundary: {needed}")
    cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
    block = cli[cli.index('sub.add_parser("stream-prepare"'):cli.index('sub.add_parser("product-check"')]
    for forbidden in ("--lifetime", "--rate", "--interval", "--frames", "--target", "--force",
                      "--loop"):
        if forbidden in block:
            fail(f"the stream CLI exposes a free-form operating argument: {forbidden}")


def verify_webcam_sidecar_boundary() -> None:
    """The camera sidecar is a frame source and must stay unable to reach the Ditoo."""
    probe = ROOT / "runtime/windows/OpenDitoo.Webcam.Probe"
    if not probe.is_dir():
        return
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(probe.glob("*.cs")))
    for forbidden in ("8796", "host.token", "Bearer", "Rfcomm", "Bluetooth", "11:75:58",
                      "/v1/session", "/v1/image", "HttpClient"):
        if forbidden in source:
            fail(f"webcam sidecar reaches past its boundary: {forbidden}")
    csproj = (probe / "OpenDitoo.Webcam.Probe.csproj").read_text(encoding="utf-8")
    if "ProjectReference" in csproj:
        fail("webcam sidecar must not reference the Host project")


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
    verify_activity_ui()
    verify_collection_worker()
    verify_activation_boundary()
    verify_product_runtime_boundary()
    verify_stream_boundary()
    verify_webcam_sidecar_boundary()
    verify_consumed_runner()
    verify_m5_runner_disarmed()
    print(
        "DAY1_OFFLINE_PASS "
        f"artifacts={artifact_count} tests={test_count} host=typed_image port=8796 "
        "device_io=false m4_completed=true m4_authorized=false m5_authorized=false ui=approved_mcp_page "
        f"m9_activation_authorized={str(_m9_armed()).lower()} "
        f"s1_stream_authorized={str(_s1_stream_armed()).lower()} "
        "committed_product_template_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
