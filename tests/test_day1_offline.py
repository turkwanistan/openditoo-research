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
    IMAGE_PREAMBLE_A,
    IMAGE_PREAMBLE_B,
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
        # The CLI must contain no Bluetooth transport vocabulary or API. Offline
        # capture analysis names the transport in host/btsnoop.py instead, so this
        # guard stays strict rather than gaining exemptions.
        self.assertNotIn("RFCOMM", src)
        self.assertNotIn("BTPROTO", src)
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


def _decode_static_image_packet(wire: bytes) -> bytes:
    """Rebuild RGB888 from a 0x44 static-image packet, independent of the encoder."""
    if wire[0] != 0x01 or wire[-1] != 0x02 or wire[3] != 0x44:
        raise ValueError("not a 0x44 static image packet")
    payload = wire[4:-3]
    if payload[:5] != bytes.fromhex("000a0a04aa") or payload[7:10] != bytes.fromhex("f40100"):
        raise ValueError("unexpected static image payload header")
    count = payload[10]
    palette_end = 11 + count * 3
    palette = [tuple(payload[i:i + 3]) for i in range(11, palette_end, 3)]
    packed = payload[palette_end:]
    bits_per_pixel = max(1, (count - 1).bit_length())
    out = bytearray()
    for pixel in range(256):
        index = 0
        for bit in range(bits_per_pixel):
            offset = pixel * bits_per_pixel + bit
            index |= ((packed[offset // 8] >> (offset % 8)) & 1) << bit
        out.extend(palette[index])
    return bytes(out)


class M6RuntimeAcceptanceTests(unittest.TestCase):
    """M6.3 — encoder/CLI boundaries and honest Host diagnostics."""

    def test_asymmetric_image_survives_png_and_encoder_round_trip(self) -> None:
        # Distinct corner/edge marks: any transpose, flip or row/column swap fails.
        rgb = bytearray(768)
        for pixel, color in {
            0: (255, 0, 0),        # top-left
            15: (0, 255, 0),       # top-right
            240: (0, 0, 255),      # bottom-left
            255: (255, 255, 255),  # bottom-right
            1: (255, 255, 0),      # second column of first row
            16: (0, 255, 255),     # first column of second row
        }.items():
            rgb[pixel * 3:pixel * 3 + 3] = bytes(color)
        rgb = bytes(rgb)
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "asymmetric.png"
            _write_rgb_png16(png, rgb)
            decoded = decode_png16_rgb(png)
        self.assertEqual(decoded, rgb)
        wire, palette_colors = encode_rgb888_static_image(decoded)
        self.assertEqual(palette_colors, 7)
        self.assertEqual(_decode_static_image_packet(wire), rgb)

    def test_malformed_png_crc_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "corrupt.png"
            _write_rgb_png16(png, bytes(768))
            data = bytearray(png.read_bytes())
            data[-5] ^= 0xFF  # flip a byte inside the IEND CRC
            png.write_bytes(bytes(data))
            with self.assertRaises(Png16Error):
                decode_png16_rgb(png)

    def test_transaction_is_exactly_three_packets_with_stock_preambles(self) -> None:
        from host.ditoo_pixel_coloring import IMAGE_PREAMBLE_A, IMAGE_PREAMBLE_B

        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs").read_text(encoding="utf-8")
        self.assertIn(f'ImagePreambleA = Convert.FromHexString("{IMAGE_PREAMBLE_A.hex().upper()}")', protocol)
        self.assertIn(f'ImagePreambleB = Convert.FromHexString("{IMAGE_PREAMBLE_B.hex().upper()}")', protocol)
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        self.assertIn('if (packets.Length != 3)', transport)
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        self.assertIn('"packetCount": 3', cli)
        self.assertIn('"retry": False', cli)

    def test_host_hash_gate_precedes_any_device_touch(self) -> None:
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        hash_gate = program.index("IMAGE_ENCODER_HASH_MISMATCH")
        self.assertLess(hash_gate, program.index("RequireAuthenticatedExactTarget"))
        self.assertLess(hash_gate, program.index("ExchangeOnce"))

    def test_cli_does_not_treat_the_ack_payload_as_a_success_constant(self) -> None:
        # Observed payloads for successful sends: 0x12, 0x75, 0xF0 - two of those for
        # a byte-identical image packet. Requiring a fixed value would be wrong.
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        required = cli[cli.index('    required = {\n        "apiVersion": 1,\n        "command": "image-show"'):]
        required = required[:required.index("}")]
        self.assertNotIn("ackPayloadHex", required)
        self.assertIn('"imagePacketSha256": expected_packet_sha', required)

    def test_m6_acceptance_capture_is_frozen(self) -> None:
        data = json.loads((ROOT / "captures/OPENDITOO-M6-IMAGE-SHOW-ACCEPTANCE-2026-09-09.json").read_text(encoding="utf-8"))
        self.assertEqual(data["milestone"], "M6.4")
        self.assertFalse(data["authority"]["transmission_authorized"])
        self.assertTrue(data["authority"]["authorization_consumed"])
        self.assertEqual(data["target"]["exact_unit_id"], "11:75:58:CE:DE:C7")
        self.assertEqual(data["source_image"]["image_packet_sha256"],
                         "e4fe7ff42632495cdcb5eceb9131a720eb77fccad2183dc98dcf0e881b2e37ea")
        acks = set()
        for operation in data["operations"]:
            self.assertEqual(operation["result"], "ok")
            self.assertEqual(operation["connections_attempted"], 1)
            self.assertEqual(operation["packets_sent_complete"], 3)
            self.assertFalse(operation["automatic_retry"])
            self.assertFalse(operation["in_flight_packet_bytes_unknown"])
            acks.add(operation["ack_payload_hex"])
        self.assertGreater(len(acks), 1, msg="the differing ACK payloads are the point of this record")
        self.assertEqual(data["operator_observation"]["orientation_confirmed"], "confirmed")
        self.assertEqual(data["operator_observation"]["persistence_after_power_cycle"], "not_retained")
        volatility = [f for f in data["findings"] if f["id"] == "STATIC-FRAME-DISPLAY-VOLATILE-ACROSS-POWER-CYCLE"][0]
        self.assertIn("does NOT prove the absence of persistent side effects", volatility["not_claimed"])
        self.assertIn("PIXEL-GEOMETRY-ROW-MAJOR-TOP-LEFT-ORIGIN",
                      [finding["id"] for finding in data["findings"]])

    def test_status_reports_host_health_not_device_connectivity(self) -> None:
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        status = program[program.index('app.MapGet("/v1/status"'):program.index('app.MapPost("/v1/image/show"')]
        self.assertIn('statusPerformsDeviceIo = false', status)
        self.assertIn('deviceIo = false', status)
        self.assertIn('deviceConnectivity = "unknown"', status)
        self.assertIn('operationHistoryScope = "volatile_since_host_start"', status)
        self.assertIn('diagnostics = ImageOperationLog.Snapshot()', status)
        self.assertNotIn('ExchangeOnce', status)
        self.assertNotIn('RequireAuthenticatedExactTarget', status)

    def test_diagnostics_are_bounded_volatile_and_secret_free(self) -> None:
        src = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/ImageOperationDiagnostics.cs").read_text(encoding="utf-8")
        self.assertIn('const int RecentLimit = 5', src)
        self.assertIn('while (Recent.Count > RecentLimit) Recent.Dequeue();', src)
        self.assertIn('inFlightPacketBytesUnknown', src)
        self.assertIn('retry = false', src)
        for forbidden in ("token", "Authorization", "PixelsRgb888Hex", "File.Write", "AppendAllText"):
            self.assertNotIn(forbidden, src, msg=f"diagnostics must not expose or persist {forbidden}")

    def test_transport_records_stage_progress_and_unknown_in_flight_bytes(self) -> None:
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        self.assertIn('ExchangeOnce(byte[][] packets, ImageOperation? operation = null)', transport)
        for stage in ('operation?.StageCompleted("connect")', 'operation?.StageCompleted("send_ready")',
                      'operation?.StageCompleted("ack")', 'operation?.PacketSent(sent)',
                      'operation?.SendOutcomeUnknown()', 'operation?.SocketWasClosed()'):
            self.assertIn(stage, transport)
        # An incomplete send must be flagged before the throw that abandons the transaction.
        send_block = transport[transport.index("if (sent != packets[index].Length)"):]
        self.assertLess(send_block.index("SendOutcomeUnknown"), send_block.index("IMAGE_SEND_FAILED"))


# --------------------------------------------------------------------------
# M9 — three-MCP activity collector and 16x16 renderer
# --------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

from host import mcp_activity  # noqa: E402
from host import activity_render  # noqa: E402


def _wsl_record(ts: str, request_id: str, result: str = "exit_0") -> str:
    return json.dumps({"ts": ts, "request_id": request_id, "tool": "run_command",
                       "project": "p", "result": result, "duration_ms": 5})


def _optiplex_record(ts: str, ok: bool = True) -> str:
    return json.dumps({"ts": ts, "tool": "run_command", "project": "p", "ok": ok, "duration_ms": 5})


class _StubAdapter:
    """In-memory adapter so collector tests never touch a real source."""

    kind = "stub"
    scripted: list = []

    def __init__(self, source_id: str, config: dict) -> None:
        self.source_id = source_id

    def poll(self, cursor):
        step = _StubAdapter.scripted.pop(0) if _StubAdapter.scripted else ([], {"n": 0}, True, 0)
        if isinstance(step, mcp_activity.SourceError):
            raise step
        return step


class M9ActivityCollectorTests(unittest.TestCase):
    """M9.2-M9.4 — honest activity semantics, cursors, rotation, skew."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "audit.jsonl"
        self.now = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)

    def _adapter(self):
        return mcp_activity.WslMcpAdapter("wsl_mcp", {"path": str(self.log), "timeout_seconds": 5})

    def test_seed_establishes_history_without_replaying_it(self) -> None:
        self.log.write_text(_wsl_record("2026-09-09T11:59:00Z", "a") + "\n", encoding="utf-8")
        adapter = self._adapter()
        events, cursor, complete, failures = adapter.poll(None)
        self.assertEqual([event.event_id for event in events], ["a"])
        self.assertTrue(complete)
        self.assertEqual(failures, 0)
        # A second poll with that cursor must produce nothing new.
        self.assertEqual(adapter.poll(cursor)[0], [])

    def test_incremental_read_and_partial_final_line(self) -> None:
        self.log.write_text(_wsl_record("2026-09-09T11:59:00Z", "a") + "\n", encoding="utf-8")
        adapter = self._adapter()
        _, cursor, _, _ = adapter.poll(None)
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(_wsl_record("2026-09-09T11:59:30Z", "b") + "\n")
            handle.write('{"ts": "2026-09-09T11:59:40Z", "request_i')  # torn write
        events, cursor, _, failures = adapter.poll(cursor)
        self.assertEqual([event.event_id for event in events], ["b"])
        self.assertEqual(failures, 0, "an incomplete final line is buffered, not a parse failure")
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write('d": "c", "tool": "t", "project": "p", "result": "exit_0"}\n')
        events, _, _, _ = adapter.poll(cursor)
        self.assertEqual([event.event_id for event in events], ["c"])

    def test_malformed_line_does_not_block_later_records(self) -> None:
        self.log.write_text("not json\n" + _wsl_record("2026-09-09T11:59:00Z", "a") + "\n", encoding="utf-8")
        events, _, _, failures = self._adapter().poll(None)
        self.assertEqual([event.event_id for event in events], ["a"])
        self.assertEqual(failures, 1)

    def test_truncation_reports_a_gap_and_resumes(self) -> None:
        self.log.write_text("".join(_wsl_record("2026-09-09T11:59:00Z", f"a{i}") + "\n" for i in range(5)),
                            encoding="utf-8")
        adapter = self._adapter()
        _, cursor, _, _ = adapter.poll(None)
        self.log.write_text(_wsl_record("2026-09-09T11:59:50Z", "fresh") + "\n", encoding="utf-8")
        events, cursor, complete, _ = adapter.poll(cursor)
        self.assertFalse(complete, "truncation must be reported as an incomplete history")
        self.assertEqual([event.event_id for event in events], ["fresh"])

    def test_failed_calls_count_as_activity_with_their_own_outcome(self) -> None:
        self.log.write_text(_wsl_record("2026-09-09T11:59:00Z", "bad", result="exit_1") + "\n", encoding="utf-8")
        events, _, _, _ = self._adapter().poll(None)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].outcome, "failure")

    def test_dispatch_only_results_are_not_claimed_as_completions(self) -> None:
        self.log.write_text(_wsl_record("2026-09-09T11:59:00Z", "job", result="started") + "\n", encoding="utf-8")
        self.assertEqual(self._adapter().poll(None)[0][0].outcome, "unknown")

    def test_optiplex_adapter_parses_offset_timestamps_and_ok_flag(self) -> None:
        adapter = mcp_activity.OptiplexMcpAdapter("optiplex_mcp", {"path": str(self.log)})
        self.log.write_text(_optiplex_record("2026-09-09T11:59:00.123456+00:00", ok=False) + "\n", encoding="utf-8")
        events, _, _, _ = adapter.poll(None)
        self.assertEqual(events[0].outcome, "failure")
        self.assertEqual(events[0].at, datetime(2026, 9, 9, 11, 59, 0, 123456, tzinfo=timezone.utc))

    def test_lab_journal_parses_dispatch_and_upstream_error_only(self) -> None:
        adapter = mcp_activity.LabTunnelAdapter("optiplex_lab", {"journal_unit": "u"})
        lines = [
            json.dumps({"__CURSOR": "s=1", "MESSAGE": json.dumps({
                "time": "2026-09-09T07:59:00.5-04:00", "msg": adapter.FORWARDED, "request_id": "cmd_1"})}),
            json.dumps({"__CURSOR": "s=2", "MESSAGE": json.dumps({
                "time": "2026-09-09T07:59:01.5-04:00", "msg": adapter.UPSTREAM_ERROR, "request_id": "cmd_2"})}),
            json.dumps({"__CURSOR": "s=3", "MESSAGE": json.dumps({
                "time": "2026-09-09T07:59:02.5-04:00", "msg": "poller recovered; polling operational"})}),
        ]
        events, cursor, anchored, failures = adapter.parse_journal("\n".join(lines), {"journal_cursor": "s=0"})
        self.assertEqual([event.event_id for event in events], ["cmd_1", "cmd_2"])
        self.assertEqual([event.outcome for event in events], ["unknown", "failure"])
        self.assertEqual(events[0].at, datetime(2026, 9, 9, 11, 59, 0, 500000, tzinfo=timezone.utc))
        self.assertEqual(cursor["journal_cursor"], "s=3", "cursor advances past non-qualifying entries")
        self.assertTrue(anchored)
        self.assertEqual(failures, 0)
        self.assertEqual(adapter.kind, "transport_forwarded_command",
                         msg="the lab signal is transport dispatch, not a completed tool call")

    def test_future_timestamp_is_flagged_as_skew_not_fresh_activity(self) -> None:
        state = mcp_activity.blank_state()
        source = state["sources"]["wsl_mcp"]
        ahead = self.now + timedelta(hours=1)
        mcp_activity._apply(source, [mcp_activity.Event("x", ahead, "success", "k")], {}, True, 0, self.now)
        self.assertIsNone(source["last_activity_at"])
        self.assertEqual(source["error_code"], "SOURCE_CLOCK_SKEW")

    def test_unreachable_source_is_unavailable_and_others_continue(self) -> None:
        original = dict(mcp_activity.ADAPTERS)
        self.addCleanup(lambda: mcp_activity.ADAPTERS.update(original))
        for source_id in mcp_activity.SOURCE_IDS:
            mcp_activity.ADAPTERS[source_id] = _StubAdapter
        config = {"sources": {sid: {} for sid in mcp_activity.SOURCE_IDS}}
        state = mcp_activity.blank_state()
        for sid in mcp_activity.SOURCE_IDS:
            state["sources"][sid]["cursor"] = {"n": 0}  # already seeded, so events pulse
        event = mcp_activity.Event("e1", self.now - timedelta(seconds=5), "success", "k")
        _StubAdapter.scripted = [
            mcp_activity.SourceError("SOURCE_READ_TIMEOUT"),
            ([event], {"n": 1}, True, 0),
            ([event], {"n": 1}, True, 0),
        ]
        counts = mcp_activity.collect_once(config, state, now=self.now)
        healths = {sid: state["sources"][sid]["source_health"] for sid in mcp_activity.SOURCE_IDS}
        self.assertEqual(sorted(healths.values()), ["healthy", "healthy", "unavailable"])
        failed = [sid for sid, value in healths.items() if value == "unavailable"][0]
        self.assertEqual(counts[failed], 0)
        self.assertIsNone(state["sources"][failed]["last_activity_at"],
                          msg="an unreachable source must not be shown as idle with invented history")
        self.assertEqual(state["sources"][failed]["error_code"], "SOURCE_READ_TIMEOUT")
        self.assertEqual(sum(counts.values()), 2)

    def test_seeding_never_pulses_but_later_events_do(self) -> None:
        original = dict(mcp_activity.ADAPTERS)
        self.addCleanup(lambda: mcp_activity.ADAPTERS.update(original))
        for source_id in mcp_activity.SOURCE_IDS:
            mcp_activity.ADAPTERS[source_id] = _StubAdapter
        config = {"sources": {sid: {} for sid in mcp_activity.SOURCE_IDS}}
        state = mcp_activity.blank_state()
        event = mcp_activity.Event("old", self.now - timedelta(minutes=1), "success", "k")
        _StubAdapter.scripted = [([event], {"n": 1}, True, 0)] * 3
        self.assertEqual(sum(mcp_activity.collect_once(config, state, now=self.now).values()), 0)
        self.assertIsNotNone(state["sources"]["wsl_mcp"]["last_activity_at"])
        _StubAdapter.scripted = [([mcp_activity.Event("new", self.now, "success", "k")], {"n": 2}, True, 0)] * 3
        self.assertEqual(sum(mcp_activity.collect_once(config, state, now=self.now).values()), 3)

    def test_state_round_trips_atomically_and_rejects_a_foreign_version(self) -> None:
        path = Path(self.tmp.name) / "state.json"
        state = mcp_activity.blank_state()
        state["sources"]["wsl_mcp"]["last_activity_at"] = "2026-09-09T11:00:00Z"
        mcp_activity.save_state(state, path)
        self.assertEqual(mcp_activity.load_state(path)["sources"]["wsl_mcp"]["last_activity_at"],
                         "2026-09-09T11:00:00Z")
        path.write_text(json.dumps({"version": 999, "sources": {}}), encoding="utf-8")
        self.assertEqual(mcp_activity.load_state(path), mcp_activity.blank_state())

    def test_stale_read_is_not_reported_as_idle_activity(self) -> None:
        state = mcp_activity.blank_state()
        source = state["sources"]["wsl_mcp"]
        source.update({"source_health": "healthy", "last_observed_at": mcp_activity.iso(self.now - timedelta(minutes=5))})
        mcp_activity.age_out_stale(state, self.now, poll_seconds=2.0)
        self.assertEqual(source["source_health"], "stale")

    def test_collector_never_issues_an_mcp_call(self) -> None:
        src = (ROOT / "host/mcp_activity.py").read_text(encoding="utf-8")
        for forbidden in ("mcp", "jsonrpc", "tools/call", "requests.", "urllib"):
            if forbidden == "mcp":
                continue  # the module name itself
            self.assertNotIn(forbidden, src.lower())
        # Only these external programs may be run, all read-only.
        self.assertEqual(sorted({'"stat"', '"tail"', '"journalctl"', '"ssh"'}),
                         sorted({token for token in ('"stat"', '"tail"', '"journalctl"', '"ssh"') if token in src}))
        for forbidden in ('"rm"', '"curl"', '"wget"', "shell=True"):
            self.assertNotIn(forbidden, src)


class M9RendererTests(unittest.TestCase):
    """M9.5 — separated icons, age and health as independent dimensions."""

    def setUp(self) -> None:
        self.now = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
        self.state = mcp_activity.blank_state()

    def _state_with(self, source_id: str, minutes_ago: float | None, health: str = "healthy") -> dict:
        source = self.state["sources"][source_id]
        source["last_activity_at"] = None if minutes_ago is None else mcp_activity.iso(
            self.now - timedelta(minutes=minutes_ago))
        source["source_health"] = health
        return self.state

    def test_age_boundaries_are_deterministic(self) -> None:
        for minutes, expected in ((0, "recent"), (4.99, "recent"), (5, "warm"), (19.99, "warm"), (20, "idle")):
            stamp = mcp_activity.iso(self.now - timedelta(minutes=minutes))
            self.assertEqual(activity_render.age_category(stamp, self.now), expected, msg=f"{minutes} min")
        self.assertEqual(activity_render.age_category(None, self.now), "no_data")

    def test_future_activity_stamp_renders_as_no_data_not_fresh(self) -> None:
        ahead = mcp_activity.iso(self.now + timedelta(minutes=5))
        self.assertEqual(activity_render.age_category(ahead, self.now), "no_data")

    def test_icons_are_separated_and_frame_is_exactly_16x16(self) -> None:
        rgb = activity_render.render_rgb888(self._state_with("wsl_mcp", 1), self.now)
        self.assertEqual(len(rgb), 16 * 16 * 3)
        for row in (0, 5, 10, 15):
            band = rgb[row * 48:(row + 1) * 48]
            self.assertEqual(band, bytes(48), msg=f"row {row} must stay a black separator")
        occupied = {y for y in range(16) for x in range(16) if rgb[(y * 16 + x) * 3:(y * 16 + x) * 3 + 3] != b"\x00\x00\x00"}
        self.assertTrue(occupied.isdisjoint({0, 5, 10, 15}))

    def test_unavailable_health_survives_a_recent_historical_activity(self) -> None:
        state = self._state_with("optiplex_mcp", 1, health="unavailable")
        view = activity_render.describe(state, self.now)["optiplex_mcp"]
        self.assertEqual(view["age_category"], "recent")
        self.assertEqual(view["source_health"], "unavailable")
        rgb = activity_render.render_rgb888(state, self.now)
        top = activity_render.BANDS["optiplex_mcp"]
        marker = (top * 16 + activity_render.HEALTH_COLUMN) * 3
        self.assertEqual(rgb[marker:marker + 3], bytes(activity_render.HEALTH_COLOR["unavailable"]))

    def test_every_age_and_health_combination_encodes_for_the_device(self) -> None:
        for minutes in (None, 1, 10, 30):
            for health in activity_render.HEALTH_COLOR:
                for pulses in (set(), {"wsl_mcp"}):
                    state = mcp_activity.blank_state()
                    for source_id in mcp_activity.SOURCE_IDS:
                        state["sources"][source_id]["source_health"] = health
                        state["sources"][source_id]["last_activity_at"] = None if minutes is None else \
                            mcp_activity.iso(self.now - timedelta(minutes=minutes))
                    rgb = activity_render.render_rgb888(state, self.now, pulses)
                    _, palette_colors = encode_rgb888_static_image(rgb)
                    self.assertLessEqual(palette_colors, 255)

    def test_pulse_only_affects_the_source_that_saw_activity(self) -> None:
        state = self._state_with("wsl_mcp", 30)
        view = activity_render.describe(state, self.now, pulses={"wsl_mcp"})
        self.assertEqual(view["wsl_mcp"]["age_category"], "new")
        self.assertEqual(view["optiplex_mcp"]["age_category"], "no_data")

    def test_preview_pngs_are_written_and_decode_back_to_the_exact_frame(self) -> None:
        rgb = activity_render.render_rgb888(self._state_with("wsl_mcp", 1), self.now)
        with tempfile.TemporaryDirectory() as tmp:
            outputs = activity_render.write_previews(Path(tmp), rgb, scale=4)
            self.assertEqual(decode_png16_rgb(Path(outputs["exact_png"])), rgb)
            self.assertTrue(Path(outputs["preview_png"]).is_file())

    def test_example_source_config_carries_no_real_endpoints(self) -> None:
        example = json.loads((ROOT / "examples/activity-sources.example.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(example["sources"]), sorted(mcp_activity.SOURCE_IDS))
        blob = json.dumps(example)
        self.assertNotIn("192.168.", blob, msg="no private host addresses in committed files")
        self.assertNotIn("@192", blob)
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".openditoo-local/", gitignore)


# --------------------------------------------------------------------------
# btsnoop capture parsing (M7 tooling)
# --------------------------------------------------------------------------

from host import btsnoop  # noqa: E402

PRIVATE_CAPTURES = ROOT / "captures/private"


def _h4_acl(handle: int, boundary: int, l2cap: bytes) -> bytes:
    return b"\x02" + struct.pack("<HH", handle | (boundary << 12), len(l2cap)) + l2cap


def _l2cap(cid: int, payload: bytes) -> bytes:
    return struct.pack("<HH", len(payload), cid) + payload


def _sig(code: int, identifier: int, body: bytes) -> bytes:
    return _l2cap(1, bytes((code, identifier)) + struct.pack("<H", len(body)) + body)


def _rfcomm_uih(dlci: int, payload: bytes) -> bytes:
    address = (dlci << 2) | 0x03
    header = bytes((address, btsnoop.RFCOMM_UIH, (len(payload) << 1) | 1))
    return header + payload + bytes((btsnoop.rfcomm_fcs(header[:2]),))


def _connection_complete(handle: int, bdaddr: str) -> bytes:
    raw = bytes(int(part, 16) for part in reversed(bdaddr.split(":")))
    return b"\x04" + bytes((0x03, 11, 0x00)) + struct.pack("<H", handle) + raw + bytes((0x01, 0x00))


def _btsnoop(records: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(b"btsnoop\x00" + struct.pack(">II", 1, 1002))
    for index, (direction, blob) in enumerate(records):
        flags = 0x01 if direction == "rx" else 0x00
        stamp = btsnoop.EPOCH_DELTA_US + 1_757_000_000_000_000 + index * 1000
        out += struct.pack(">IIIIq", len(blob), len(blob), flags, 0, stamp) + blob
    return bytes(out)


class BtsnoopParserTests(unittest.TestCase):
    PEER = "11:75:58:CE:DE:C7"
    HANDLE = 0x000B

    def _capture(self, extra: list[tuple[str, bytes]]) -> bytes:
        return _btsnoop([("rx", _connection_complete(self.HANDLE, self.PEER))] + extra)

    def _open_rfcomm(self, identifier: int, scid: int, dcid: int) -> list[tuple[str, bytes]]:
        request = _sig(btsnoop.SIG_CONNECTION_REQUEST, identifier, struct.pack("<HH", 0x0003, scid))
        response = _sig(btsnoop.SIG_CONNECTION_RESPONSE, identifier, struct.pack("<HHHH", dcid, scid, 0, 0))
        return [("tx", _h4_acl(self.HANDLE, 2, request)), ("rx", _h4_acl(self.HANDLE, 2, response))]

    def test_round_trip_of_an_application_frame(self) -> None:
        wire = encode_candidate_normal(0x58, bytes.fromhex("ffffff016a"))
        records = self._open_rfcomm(1, 0x0041, 0x0044)
        records.append(("tx", _h4_acl(self.HANDLE, 2, _l2cap(0x0044, _rfcomm_uih(2, wire)))))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            view, frames, errors = btsnoop.read(path, peer_bdaddr=self.PEER, reveal_commands={0x58})
        self.assertEqual(view.handles, {self.HANDLE: self.PEER})
        self.assertEqual(view.fcs_failures, 0)
        self.assertEqual([frame.hex for frame in frames], [wire.hex()])
        self.assertEqual(errors, {"tx": [], "rx": []})

    def test_application_frame_split_across_acl_fragments(self) -> None:
        wire = encode_candidate_normal(0x44, bytes(60))
        pdu = _l2cap(0x0044, _rfcomm_uih(2, wire))
        records = self._open_rfcomm(1, 0x0041, 0x0044)
        records.append(("tx", _h4_acl(self.HANDLE, 2, pdu[:20])))
        records.append(("tx", _h4_acl(self.HANDLE, 1, pdu[20:])))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            _, frames, _ = btsnoop.read(path, peer_bdaddr=self.PEER, reveal_commands={0x44})
        self.assertEqual([frame.hex for frame in frames], [wire.hex()])

    def test_a_reused_signalling_identifier_does_not_adopt_another_psm(self) -> None:
        # Regression: matching a response on identifier alone claimed an AVDTP channel
        # as RFCOMM and mis-framed its data into phantom application frames.
        decoy_request = _sig(btsnoop.SIG_CONNECTION_REQUEST, 1, struct.pack("<HH", 0x0019, 0x0050))
        decoy_response = _sig(btsnoop.SIG_CONNECTION_RESPONSE, 1, struct.pack("<HHHH", 0x0051, 0x0050, 0, 0))
        records = [("tx", _h4_acl(self.HANDLE, 2, decoy_request)), ("rx", _h4_acl(self.HANDLE, 2, decoy_response))]
        records.append(("tx", _h4_acl(self.HANDLE, 2, _l2cap(0x0051, bytes.fromhex("deadbeefcafe")))))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            view, frames, _ = btsnoop.read(path, peer_bdaddr=self.PEER)
        self.assertEqual(view.rfcomm_cids, set())
        self.assertEqual(frames, [])

    def test_a_recycled_cid_stops_being_rfcomm_after_disconnect(self) -> None:
        # Regression: CIDs are reassigned to other PSMs once a channel closes.
        records = self._open_rfcomm(1, 0x0041, 0x0044)
        records.append(("tx", _h4_acl(self.HANDLE, 2,
                                      _sig(btsnoop.SIG_DISCONNECTION_REQUEST, 2, struct.pack("<HH", 0x0044, 0x0041)))))
        records.append(("tx", _h4_acl(self.HANDLE, 2, _l2cap(0x0044, bytes.fromhex("deadbeefcafe")))))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            view, frames, _ = btsnoop.read(path, peer_bdaddr=self.PEER)
        self.assertEqual(frames, [])
        self.assertEqual(view.fcs_failures, 0, msg="post-disconnect traffic must be ignored, not FCS-tested")

    def test_traffic_from_another_device_is_excluded(self) -> None:
        other = "AA:BB:CC:DD:EE:FF"
        wire = encode_candidate_normal(0x58, b"\x01\x02\x03\x01\x00")
        records = [("rx", _connection_complete(0x0020, other))]
        records += [("tx", _h4_acl(0x0020, 2, _sig(btsnoop.SIG_CONNECTION_REQUEST, 1, struct.pack("<HH", 0x0003, 0x0041)))),
                    ("rx", _h4_acl(0x0020, 2, _sig(btsnoop.SIG_CONNECTION_RESPONSE, 1, struct.pack("<HHHH", 0x0044, 0x0041, 0, 0))))]
        records.append(("tx", _h4_acl(0x0020, 2, _l2cap(0x0044, _rfcomm_uih(2, wire)))))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            _, frames, _ = btsnoop.read(path, peer_bdaddr=self.PEER, reveal_commands={0x58})
        self.assertEqual(frames, [], msg="only the exact unit's ACL handle may contribute evidence")

    def test_payloads_are_withheld_unless_explicitly_revealed(self) -> None:
        wire = encode_candidate_normal(0x58, bytes.fromhex("ffffff016a"))
        records = self._open_rfcomm(1, 0x0041, 0x0044)
        records.append(("tx", _h4_acl(self.HANDLE, 2, _l2cap(0x0044, _rfcomm_uih(2, wire)))))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.btsnoop"
            path.write_bytes(self._capture(records))
            view, frames, errors = btsnoop.read(path, peer_bdaddr=self.PEER)
        self.assertEqual(len(frames), 1)
        self.assertIsNone(frames[0].hex, msg="payload bytes must not leak without an explicit reveal")
        self.assertEqual(frames[0].sha256, __import__("hashlib").sha256(wire).hexdigest())
        summary = btsnoop.summarize(view, frames, errors)
        self.assertTrue(summary["payloads_withheld_by_default"])
        self.assertNotIn(wire.hex(), json.dumps(summary))

    def test_rejects_a_file_that_is_not_btsnoop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.bin"
            path.write_bytes(b"not a capture at all")
            with self.assertRaises(btsnoop.BtsnoopError):
                btsnoop.read(path)


@unittest.skipUnless((PRIVATE_CAPTURES / "capture2.btsnoop").is_file(),
                     "raw btsnoop captures are private and absent from this checkout")
class BtsnoopAgainstFrozenEvidenceTests(unittest.TestCase):
    """Validates the parser against the exact captures the frozen evidence came from."""

    PEER = "11:75:58:CE:DE:C7"

    def test_stock_rfcomm_capture_reproduces_the_recorded_transport(self) -> None:
        view, frames, errors = btsnoop.read(PRIVATE_CAPTURES / "capture1.btsnoop", peer_bdaddr=self.PEER)
        recorded = json.loads((ROOT / "captures/OPENDITOO-DAY1-STOCK-RFCOMM-2026-09-08.json").read_text(encoding="utf-8"))
        transport = recorded["transport"]
        self.assertIn(int(transport["l2cap_rfcomm"]["local_scid"], 16), view.rfcomm_cids)
        self.assertIn(int(transport["l2cap_rfcomm"]["remote_dcid"], 16), view.rfcomm_cids)
        self.assertEqual(view.handles.get(int(transport["hci_connection_complete"]["handle"], 16)), self.PEER)
        self.assertIn(transport["rfcomm"]["application_dlci"], view.dlcis_seen)
        self.assertEqual(errors, {"tx": [], "rx": []})

    def test_pixel_coloring_capture_reproduces_every_frozen_stock_frame(self) -> None:
        _, frames, errors = btsnoop.read(PRIVATE_CAPTURES / "capture2.btsnoop", peer_bdaddr=self.PEER,
                                         reveal_commands={0x58, 0x9F, 0xBD})
        seen = {frame.hex for frame in frames if frame.hex}
        for expected in ("01090058ffffff026a7a440402", "01080058ff00000100600102",
                         "0108005800ff57010fc60102", "010800580066ff01e1a70202",
                         "010800585a5a5a0178e70102", "01080058ffffff01ff5d0402"):
            self.assertIn(expected, seen, msg="frozen exact-unit drawing evidence must be reproducible")
        self.assertIn(IMAGE_PREAMBLE_A.hex(), seen)
        self.assertIn(IMAGE_PREAMBLE_B.hex(), seen)
        self.assertEqual(errors, {"tx": [], "rx": []})

    def test_drawing_pad_count_field_always_matches_its_index_list(self) -> None:
        _, frames, _ = btsnoop.read(PRIVATE_CAPTURES / "capture2.btsnoop", peer_bdaddr=self.PEER,
                                    reveal_commands={0x58})
        drawing = [frame for frame in frames if frame.command == 0x58]
        self.assertGreater(len(drawing), 100)
        for frame in drawing:
            payload = bytes.fromhex(frame.hex)[4:-3]
            self.assertEqual(len(payload), 4 + payload[3],
                             msg="RGB888[3] | count:u8 | index[count] must be self-consistent")


if __name__ == "__main__":
    unittest.main()
