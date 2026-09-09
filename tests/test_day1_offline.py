from __future__ import annotations

import binascii
import json
import struct
import zlib
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
from host.ditoo_pixel_coloring import (
    DIAGNOSTIC_FRAME_SHA256,
    diagnostic_frame,
    drawing_pad_packet,
    encode_rgb888_static_image,
    sha256_hex as pixel_sha256_hex,
)
from host.png16 import Png16Error, decode_png16_rgb
from host.ditoo_candidate_codec import (
    CandidateStreamDecoder,
    FrameDecodeError,
    decode_candidate_normal,
    decode_candidate_wrapped,
    encode_candidate_normal,
)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def _write_rgb_png16(path: Path, rgb: bytes) -> None:
    if len(rgb) != 16 * 16 * 3:
        raise ValueError("fixture RGB must be exactly 768 bytes")
    rows = b"".join(b"\x00" + rgb[y * 48:(y + 1) * 48] for y in range(16))
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(rows))
        + _png_chunk(b"IEND", b"")
    )



def _write_png16(path: Path, color_type: int, channels: int, rows_payload: bytes, *, palette: bytes | None = None, transparency: bytes | None = None) -> None:
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, color_type, 0, 0, 0)
    data = bytearray(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr))
    if palette is not None:
        data.extend(_png_chunk(b"PLTE", palette))
    if transparency is not None:
        data.extend(_png_chunk(b"tRNS", transparency))
    data.extend(_png_chunk(b"IDAT", zlib.compress(rows_payload)))
    data.extend(_png_chunk(b"IEND", b""))
    path.write_bytes(bytes(data))


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
        self.assertNotIn('"--target"', src)
        self.assertNotIn('"--packet"', src)

    def test_runtime_host_is_fixed_target_typed_image_only(self) -> None:
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs").read_text(encoding="utf-8")
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        self.assertIn('const int Port = 8796;', program)
        self.assertIn('masterTransmitEnabled = true', program)
        self.assertIn('transportConfigured = true', program)
        self.assertIn('targetBound = true', program)
        self.assertIn('rawSendEnabled = false', program)
        self.assertIn('app.MapPost("/v1/image/show"', program)
        self.assertIn('ShowImageRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256)', program)
        self.assertNotIn('TargetMac', program.split('sealed record ShowImageRequest', 1)[1])
        self.assertNotIn('packetHex', program, msg="Host API must not accept a raw packet field")
        self.assertNotIn('send_hex', program.lower())
        self.assertIn('TargetMac = "11:75:58:CE:DE:C7"', protocol)
        self.assertIn('TargetRfcommChannel = 1', protocol)
        self.assertEqual(transport.count('connect(socketHandle, ref remote, layoutSize)'), 1)
        self.assertEqual(transport.count('send(socketHandle, packets[index], packets[index].Length, 0)'), 1)
        self.assertIn('NO_RETRY', transport)
        self.assertNotIn('8779', program)

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

    def test_refresh_script_owns_only_openditoo_runtime(self) -> None:
        src = (ROOT / "runtime/windows/refresh_openditoo_day1_host.ps1").read_text(encoding="utf-8")
        self.assertIn("$TaskName = 'OpenDitoo Day1 Host'", src)
        self.assertIn("Get-ScheduledTask -TaskName 'OpenTivoo Product Runtime'", src)
        self.assertIn("Stop-ScheduledTask -TaskName $TaskName", src)
        self.assertNotIn("Stop-ScheduledTask -TaskName 'OpenTivoo Product Runtime'", src)
        self.assertNotIn("Stop-Process", src)
        self.assertIn("rawSendEnabled -ne $false", src)
        self.assertIn("PASS_TYPED_IMAGE", src)
        self.assertIn("$Backup", src)
        self.assertIn("Copy-Item -Path (Join-Path $backupRoot '*') -Destination $WindowsRoot", src)

    def test_completed_m4_transport_is_archived_and_runner_disarmed(self) -> None:
        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooM4FileVersionProtocol.cs").read_text(encoding="utf-8")
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommBoundedM4Transport.cs").read_text(encoding="utf-8")
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        runner = (ROOT / "runtime/windows/OpenDitoo.M4.Runner/Program.cs").read_text(encoding="utf-8")

        self.assertIn('TargetMac = "11:75:58:CE:DE:C7"', protocol)
        self.assertIn('TargetRfcommChannel = 1', protocol)
        self.assertIn('01040097009B0002', protocol)
        self.assertEqual(transport.count('var connectResult = connect(socketHandle, ref remote, layoutSize);'), 1)
        self.assertEqual(transport.count('var sent = send(socketHandle, request, request.Length, 0);'), 1)
        self.assertNotIn('DitooM4FileVersionProtocol', program)
        self.assertNotIn('WindowsRfcommBoundedM4Transport', program)
        self.assertIn('M4_AUTHORITY_CONSUMED', runner)
        self.assertNotIn('ExchangeFrozenFileVersionOnce', runner)
        self.assertNotIn('RequireAuthenticatedExactTarget', runner)

    def test_completed_m4_manifest_records_pass_and_consumed_authority(self) -> None:
        manifest = ROOT / "experiments/DAY1-M4-QUERY-PENDING.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "completed_pass_authority_consumed")
        self.assertFalse(data["authority"]["transmission_authorized"])
        self.assertTrue(data["authority"]["authorization_consumed"])
        self.assertEqual(data["operation"]["application_tx_hex"], "01040097009b0002")
        self.assertEqual(data["result"]["status"], "pass")
        self.assertEqual(data["result"]["decoded_version"], 42012)
        self.assertEqual(data["result"]["requests_sent"], 1)
        self.assertEqual(data["result"]["connections_attempted"], 1)

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


class PixelColoringEvidenceTests(unittest.TestCase):
    def test_exact_stock_drawing_pad_examples(self) -> None:
        self.assertEqual(drawing_pad_packet((255, 255, 255), [0x6A, 0x7A]).hex(), "01090058ffffff026a7a440402")
        self.assertEqual(drawing_pad_packet((255, 0, 0), [0x00]).hex(), "01080058ff00000100600102")
        self.assertEqual(drawing_pad_packet((0, 255, 87), [0x0F]).hex(), "0108005800ff57010fc60102")
        self.assertEqual(drawing_pad_packet((0, 102, 255), [0xE1]).hex(), "010800580066ff01e1a70202")
        self.assertEqual(drawing_pad_packet((90, 90, 90), [0x78]).hex(), "010800585a5a5a0178e70102")
        self.assertEqual(drawing_pad_packet((255, 255, 255), [0xFF]).hex(), "01080058ffffff01ff5d0402")

    def test_frozen_m5_diagnostic_wire(self) -> None:
        wire = diagnostic_frame()
        self.assertEqual(len(wire), 132)
        self.assertEqual(pixel_sha256_hex(wire), DIAGNOSTIC_FRAME_SHA256)
        self.assertEqual(DIAGNOSTIC_FRAME_SHA256, "db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b")
        self.assertEqual(wire[:14].hex(), "01800044000a0a04aa7900f40100")


class Png16Tests(unittest.TestCase):
    def test_rgb_png_roundtrip_and_static_encoder(self) -> None:
        raw = build_diagnostic_rgb()
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "diagnostic.png"
            _write_rgb_png16(png, raw)
            decoded = decode_png16_rgb(png)
            self.assertEqual(decoded, raw)
            wire, palette_colors = encode_rgb888_static_image(decoded)
            self.assertEqual(palette_colors, 6)
            self.assertEqual(pixel_sha256_hex(wire), "08520cb02dc7f448dfbad0457873444cbed7b48e5f302c123ad0657451c9773a")

    def test_cli_image_prepare_is_offline_and_exact(self) -> None:
        raw = build_diagnostic_rgb()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            png = tmp_path / "diagnostic.png"
            out = tmp_path / "out"
            _write_rgb_png16(png, raw)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "cli/openditoo.py"), "image-prepare", "--png", str(png), "--output-dir", str(out)],
                text=True, capture_output=True, check=True,
            )
            result = json.loads(proc.stdout)
            self.assertFalse(result["device_io"])
            self.assertEqual(result["rgb_bytes"], 768)
            self.assertEqual(result["palette_colors"], 6)
            self.assertEqual(result["image_packet_sha256"], "08520cb02dc7f448dfbad0457873444cbed7b48e5f302c123ad0657451c9773a")
            self.assertEqual((out / "image.rgb888").read_bytes(), raw)
            self.assertEqual(pixel_sha256_hex((out / "image.packet.bin").read_bytes()), "08520cb02dc7f448dfbad0457873444cbed7b48e5f302c123ad0657451c9773a")

    def test_committed_sample_is_frozen(self) -> None:
        path = ROOT / "examples/openditoo-smile-16.png"
        rgb = decode_png16_rgb(path)
        wire, palette_colors = encode_rgb888_static_image(rgb)
        self.assertEqual(palette_colors, 4)
        self.assertEqual(pixel_sha256_hex(rgb), "fbed71941831927c926c15f897f3335de45d9becc53c28793c9fefa146f96067")
        self.assertEqual(pixel_sha256_hex(wire), "e4fe7ff42632495cdcb5eceb9131a720eb77fccad2183dc98dcf0e881b2e37ea")

    def test_rgba_alpha_composites_to_black(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rgba.png"
            pixels = bytearray()
            for y in range(16):
                row = bytearray()
                for x in range(16):
                    row.extend((255, 0, 0, 0))
                if y == 0:
                    row[0:4] = bytes((0, 255, 0, 255))
                pixels.extend(b"\x00" + row)
            _write_png16(path, 6, 4, bytes(pixels))
            rgb = decode_png16_rgb(path)
            self.assertEqual(rgb[:3], bytes((0, 255, 0)))
            self.assertEqual(rgb[3:6], bytes((0, 0, 0)))

    def test_indexed_png_palette_decodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "indexed.png"
            palette = bytes((0, 0, 0, 255, 0, 255))
            rows = bytearray()
            for y in range(16):
                row = bytes([1 if (x == y) else 0 for x in range(16)])
                rows.extend(b"\x00" + row)
            _write_png16(path, 3, 1, bytes(rows), palette=palette)
            rgb = decode_png16_rgb(path)
            self.assertEqual(rgb[:3], bytes((255, 0, 255)))
            self.assertEqual(rgb[3:6], bytes((0, 0, 0)))
            self.assertEqual(rgb[(17 * 3):(18 * 3)], bytes((255, 0, 255)))

    def test_static_encoder_rejects_256_distinct_colors(self) -> None:
        rgb = bytearray()
        for value in range(256):
            rgb.extend((value, value ^ 0x55, value ^ 0xAA))
        with self.assertRaises(ValueError):
            encode_rgb888_static_image(bytes(rgb))

    def test_png_wrong_geometry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.png"
            ihdr = struct.pack(">IIBBBBB", 15, 16, 8, 2, 0, 0, 0)
            rows = b"".join(b"\x00" + bytes(15 * 3) for _ in range(16))
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(rows)) + _png_chunk(b"IEND", b""))
            with self.assertRaises(Png16Error):
                decode_png16_rgb(path)


if __name__ == "__main__":
    unittest.main()
