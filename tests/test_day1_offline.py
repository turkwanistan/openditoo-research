from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.diagnostic_frame import (
    BLACK,
    BLUE,
    DIM_GRAY,
    GREEN,
    RED,
    WHITE,
    build_diagnostic_rgb,
    frame_sha256,
)
from host.ditoo_candidate_codec import (
    CandidateStreamDecoder,
    FrameDecodeError,
    decode_candidate_normal,
    decode_candidate_wrapped,
    encode_candidate_normal,
)


class DiagnosticFrameTests(unittest.TestCase):
    def test_exact_geometry(self) -> None:
        raw = build_diagnostic_rgb()
        self.assertEqual(len(raw), 16 * 16 * 3)
        pixels = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        at = lambda x, y: pixels[y * 16 + x]
        self.assertEqual(at(0, 0), RED)
        self.assertEqual(at(1, 0), RED)
        self.assertEqual([at(15, y) for y in range(3)], [GREEN, GREEN, GREEN])
        self.assertEqual([at(x, y) for y in (14, 15) for x in (0, 1)], [BLUE] * 4)
        self.assertEqual(at(15, 15), WHITE)
        self.assertEqual(at(7, 7), DIM_GRAY)
        marked = {(0,0),(1,0),(15,0),(15,1),(15,2),(0,14),(1,14),(0,15),(1,15),(15,15),(7,7)}
        for y in range(16):
            for x in range(16):
                if (x, y) not in marked:
                    self.assertEqual(at(x, y), BLACK)
        self.assertEqual(len(frame_sha256(raw)), 64)


class CandidateCodecTests(unittest.TestCase):
    def test_normal_roundtrip(self) -> None:
        wire = encode_candidate_normal(0x80, b"\x12\x34")
        frame = decode_candidate_normal(wire)
        self.assertEqual(frame.command, 0x80)
        self.assertEqual(frame.payload, b"\x12\x34")

    def test_fragmented_and_concatenated_stream(self) -> None:
        a = encode_candidate_normal(0x80)
        b = encode_candidate_normal(0x10, b"\x01")
        d = CandidateStreamDecoder()
        self.assertEqual(d.feed(a[:2]), [])
        frames = d.feed(a[2:] + b)
        self.assertEqual([(f.command, f.payload) for f in frames], [(0x80, b""), (0x10, b"\x01")])
        self.assertEqual(d.buffered_bytes, b"")

    def test_bad_checksum_is_negative_evidence(self) -> None:
        wire = bytearray(encode_candidate_normal(0x80))
        wire[-3] ^= 0x01
        with self.assertRaises(FrameDecodeError):
            decode_candidate_normal(bytes(wire))
        d = CandidateStreamDecoder()
        self.assertEqual(d.feed(bytes(wire)), [])
        self.assertTrue(any("checksum mismatch" in error for error in d.errors))

    def test_truncated_frame_stays_buffered(self) -> None:
        wire = encode_candidate_normal(0x80, b"abc")
        d = CandidateStreamDecoder()
        self.assertEqual(d.feed(wire[:-1]), [])
        self.assertEqual(d.buffered_bytes, wire[:-1])

    def test_wrapped_comparison_shape(self) -> None:
        payload = bytes((0x80, 0x55, 0xAA, 0xBB))
        wire = encode_candidate_normal(0x04, payload)
        wrapped = decode_candidate_wrapped(wire)
        self.assertEqual((wrapped.outer_command, wrapped.command, wrapped.tag, wrapped.payload), (0x04, 0x80, 0x55, b"\xAA\xBB"))


class BoundaryTests(unittest.TestCase):
    def test_cli_has_separate_fixed_origin_and_no_target_escape(self) -> None:
        src = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        self.assertIn('HOST_ORIGIN = "http://127.0.0.1:8796"', src)
        self.assertNotIn("11:75:58:C8:5E:FE", src)
        self.assertNotIn("127.0.0.1:8779", src)
        self.assertNotIn("send_hex", src.lower())
        self.assertNotIn("socket.socket", src)
        self.assertNotIn("AF_BTH", src)
        self.assertNotIn("RFCOMM", src)

    def test_status_host_source_is_transport_free(self) -> None:
        src = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        self.assertIn('const int Port = 8796;', src)
        self.assertIn('masterTransmitEnabled = false', src)
        self.assertIn('transportConfigured = false', src)
        self.assertIn('targetBound = false', src)
        self.assertNotIn("using Windows.Devices.Bluetooth", src)
        self.assertNotIn("using System.Net.Sockets", src)
        self.assertNotIn("Ws2_32", src)
        self.assertNotIn("AF_BTH", src)
        self.assertNotIn("8779", src)

    def test_windows_installer_preserves_opentivoo(self) -> None:
        src = (ROOT / "runtime/windows/install_openditoo_day1_host.ps1").read_text(encoding="utf-8")
        self.assertIn("$TaskName = 'OpenDitoo Day1 Host'", src)
        self.assertIn("$Port = 8796", src)
        self.assertIn("Get-ScheduledTask -TaskName 'OpenTivoo Product Runtime'", src)
        self.assertIn("[System.Security.Principal.WindowsIdentity]::GetCurrent()", src)
        self.assertIn("$trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUserName", src)
        self.assertIn("New-ScheduledTaskPrincipal -UserId $TaskUserName -LogonType Interactive -RunLevel Limited", src)
        self.assertNotIn("New-ScheduledTaskPrincipal -UserId $env:USERNAME", src)
        self.assertNotIn("Stop-ScheduledTask -TaskName 'OpenTivoo Product Runtime'", src)
        self.assertNotIn("Unregister-ScheduledTask -TaskName 'OpenTivoo Product Runtime'", src)
        self.assertNotIn("Stop-Process", src)
        self.assertNotIn("$Port = 8779", src)

    def test_frozen_m4_transport_is_typed_one_shot_and_unreachable(self) -> None:
        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooM4FileVersionProtocol.cs").read_text(encoding="utf-8")
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommBoundedM4Transport.cs").read_text(encoding="utf-8")
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")

        self.assertIn('TargetMac = "11:75:58:CE:DE:C7"', protocol)
        self.assertIn('TargetBluetoothAddress = 0x117558CEDEC7', protocol)
        self.assertIn('TargetRfcommChannel = 1', protocol)
        self.assertIn('01040097009B0002', protocol)
        self.assertIn('010900049755001CA400B90102', protocol)
        self.assertIn('ExpectedInstalledVersion = 42012', protocol)
        self.assertIn('MaxResponseWireBytes = 13', protocol)
        self.assertIn('ConnectBudgetMs = 15_000', protocol)
        self.assertIn('ResponseBudgetMs = 5_000', protocol)
        self.assertIn('TotalBudgetMs = 20_000', protocol)

        self.assertEqual(transport.count('var connectResult = connect(socketHandle, ref remote, layoutSize);'), 1)
        self.assertEqual(transport.count('var sent = send(socketHandle, request, request.Length, 0);'), 1)
        self.assertIn('NO_RETRY', transport)
        self.assertNotIn('for (var attempt', transport)
        self.assertNotIn('while (attempt', transport)
        self.assertNotIn('DitooM4FileVersionProtocol', program)
        self.assertNotIn('WindowsRfcommBoundedM4Transport', program)
        self.assertNotIn('/v1/m4', program.lower())

    def test_pending_manifest_fails_closed(self) -> None:
        manifest = ROOT / "experiments/DAY1-M4-QUERY-PENDING.json"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli/openditoo.py"), "manifest-check", "--file", str(manifest)],
            text=True,
            capture_output=True,
            check=True,
        )
        result = json.loads(proc.stdout)
        self.assertFalse(result["execution_ready"])
        self.assertNotIn("exact_unit_id_unbound", result["execution_blockers"])
        self.assertNotIn("measured_endpoint_unbound", result["execution_blockers"])
        self.assertNotIn("installed_firmware_unbound", result["execution_blockers"])
        self.assertNotIn("semantic_evidence_missing", result["execution_blockers"])
        self.assertNotIn("application_tx_unfrozen", result["execution_blockers"])
        self.assertEqual(result["execution_blockers"], ["transmission_authority_missing"])

    def test_frame_preview_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "cli/openditoo.py"), "frame-preview", "--output-dir", tmp],
                text=True,
                capture_output=True,
                check=True,
            )
            result = json.loads(proc.stdout)
            self.assertFalse(result["device_io"])
            self.assertEqual(result["rgb_bytes"], 768)
            self.assertEqual(Path(result["rgb_path"]).read_bytes(), build_diagnostic_rgb())


if __name__ == "__main__":
    unittest.main()
