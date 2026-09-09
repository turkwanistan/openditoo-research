from __future__ import annotations

import binascii
import itertools
import json
import dataclasses
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
from host.png16 import Png16Error, decode_png16_rgb, png_sha256
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
        # Every frame group is still exactly preamble A, preamble B, image. The
        # sequence refactor renamed the variable; the invariant is unchanged.
        self.assertIn('if (group.Length != 3)', transport)
        self.assertIn('IMAGE_TRANSACTION_PACKET_COUNT_REJECTED', transport)
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

    def test_m8_ab_fixtures_are_frozen_and_asymmetric(self) -> None:
        manifest = json.loads((ROOT / "experiments/DAY1-M8-AB-SEQUENCE-PENDING.json").read_text(encoding="utf-8"))
        corners = {"a": (0, 0), "b": (15, 15)}
        for key, source in manifest["operation"]["source_frames"].items():
            if key == "why_these":
                continue
            path = ROOT / source["file"]
            rgb = decode_png16_rgb(path)
            wire, palette_colors = encode_rgb888_static_image(rgb)
            self.assertEqual(png_sha256(path), source["png_sha256"])
            self.assertEqual(pixel_sha256_hex(rgb), source["rgb_sha256"])
            self.assertEqual(pixel_sha256_hex(wire), source["packet_sha256"])
            self.assertEqual(palette_colors, source["palette_colors"])
            row, column = corners[key]
            lit = (row * 16 + column) * 3
            self.assertEqual(rgb[lit:lit + 3], b"\xff\xff\xff", msg=f"frame {key} corner must be lit")
        a = decode_png16_rgb(ROOT / manifest["operation"]["source_frames"]["a"]["file"])
        b = decode_png16_rgb(ROOT / manifest["operation"]["source_frames"]["b"]["file"])
        self.assertNotEqual(a, b)
        self.assertEqual(a[:3], b"\xff\xff\xff")
        self.assertEqual(b[:3], b"\x00\x00\x00", msg="A and B must be distinguishable at the first pixel")

    def test_m8_manifest_is_executed_and_its_authority_consumed(self) -> None:
        path = ROOT / "experiments/DAY1-M8-AB-SEQUENCE-PENDING.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(manifest["authority"]["transmission_authorized"])
        self.assertTrue(manifest["authority"]["authorization_consumed"])
        result = manifest["result"]
        self.assertEqual(result["connections_attempted"], 1)
        self.assertEqual(result["packets_sent_complete"], manifest["budgets"]["application_packets"])
        self.assertEqual(result["tx_bytes_sent_complete"], manifest["budgets"]["application_tx_bytes_total"])
        self.assertEqual(result["frames_acked"], 2)
        self.assertFalse(result["in_flight_packet_bytes_unknown"])
        self.assertFalse(result["retry"])
        self.assertFalse(result["reconnect"])
        self.assertEqual(len(set(result["ack_payload_hex_ordered"])), 2,
                         msg="the two ACKs in one session differed; the payload is not a success constant")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(manifest["status"], "completed_pass_authority_consumed")
        # Physical render order was observed, but which frame came first was not
        # reported; that stays an explicit residual rather than an assumption.
        self.assertIn("residual", result)
        for flag in ("automatic_retry", "automatic_reconnect", "target_override", "raw_packet_override"):
            self.assertFalse(manifest["operation"][flag])
        budgets = manifest["budgets"]
        self.assertEqual(budgets["connection_attempts"], 1)
        self.assertEqual(budgets["application_packets"], 6)
        preambles = sum(step["bytes"] for step in manifest["operation"]["application_tx_sequence"]
                        if step.get("bytes") and step["name"].startswith("preamble"))
        images = sum(step["bytes"] for step in manifest["operation"]["application_tx_sequence"]
                     if step.get("bytes") and step["name"].startswith("image"))
        self.assertEqual(preambles + images, budgets["application_tx_bytes_total"])
        self.assertIn("does not test that", manifest["persistence_analysis"]["not_claimed"])
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli/openditoo.py"), "manifest-check", "--file", str(path)],
            text=True, capture_output=True, check=True,
        )
        checked = json.loads(proc.stdout)
        self.assertFalse(checked["execution_ready"], msg="a consumed manifest must not be executable again")
        self.assertEqual(checked["execution_blockers"], ["transmission_authority_missing"])
        self.assertEqual(checked["missing_fields"], [])

    def test_sequence_route_validates_every_frame_before_any_device_io(self) -> None:
        program = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/Program.cs").read_text(encoding="utf-8")
        route = program[program.index('app.MapPost("/v1/image/sequence"'):]
        # A bad second frame must never be discovered halfway through a live sequence.
        self.assertLess(route.index("IMAGE_ENCODER_HASH_MISMATCH"), route.index("RequireAuthenticatedExactTarget"))
        self.assertLess(route.index("IMAGE_ENCODER_HASH_MISMATCH"), route.index("ExchangeSequenceOnce"))
        self.assertIn("IMAGE_SEQUENCE_FRAMES_IDENTICAL", route)
        self.assertIn("imageGate.Wait(0)", route)
        self.assertIn("retry = false", route)
        self.assertIn("reconnect = false", route)
        self.assertNotIn("TargetMac =", route, msg="the sequence route must not rebind the target")

    def test_sequence_transport_keeps_one_connection_and_no_retry(self) -> None:
        transport = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        # Refactoring image-show onto the sequence core must not add a second connect
        # or send call site; the existing boundary counts still have to hold.
        self.assertEqual(transport.count("connect(socketHandle, ref remote, layoutSize)"), 1)
        self.assertEqual(transport.count("send(socketHandle, packets[index], packets[index].Length, 0)"), 1)
        self.assertIn("ExchangeOnce(byte[][] packets, ImageOperation? operation = null)\n        => ExchangeSequenceOnce([packets], 0, operation)[0];", transport)
        self.assertIn("IMAGE_SEQUENCE_FRAME_COUNT_REJECTED", transport)
        self.assertIn("IMAGE_SEQUENCE_DELAY_REJECTED", transport)
        self.assertNotIn("Reconnect", transport)
        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs").read_text(encoding="utf-8")
        # The floor tracks measured evidence, and each step down must cite the run that
        # earned the previous one. 0 is the absolute floor: with no inter-frame sleep the
        # ACK is the clock, and going faster would mean abandoning one ACK per frame.
        self.assertIn("MinInterFrameDelayMs = 0;", protocol)
        self.assertNotIn("MinInterFrameDelayMs = -", protocol, msg="there is nothing below zero")
        # Send spacing may be lowered by a reviewed manifest to measure whether the
        # stock-derived 40 ms is load-bearing; it may never be raised above it.
        self.assertIn("DefaultSendSpacingMs = 40", protocol)
        self.assertIn("MaxSendSpacingMs = 40", protocol)
        self.assertIn("IMAGE_SEND_SPACING_REJECTED", transport)
        for earned_by in ("OPENDITOO-R1-RATE-250MS", "OPENDITOO-R2A-DELAY-50MS", "OPENDITOO-R5-NOSLEEP"):
            self.assertIn(earned_by, protocol,
                          msg=f"each step down in the floor must cite its experiment: {earned_by}")

    def test_sequence_cli_is_manifest_driven_with_no_free_form_arguments(self) -> None:
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index("def sequence_run("):cli.index("def capture_parse(")]
        self.assertIn("TRANSMISSION_AUTHORITY_MISSING", block)
        self.assertIn("AUTHORITY_ALREADY_CONSUMED", block)
        self.assertIn("FROZEN_FRAME_DRIFT", block)
        self.assertIn("BUDGET_OR_RESULT_MISMATCH", block)
        parser = cli[cli.index('sub.add_parser("sequence-run"'):]
        parser = parser[:parser.index("set_defaults")]
        self.assertIn('"--manifest"', parser)
        for forbidden in ('"--png"', '"--frames"', '"--delay"', '"--target"', '"--packet"'):
            self.assertNotIn(forbidden, parser, msg="sequence parameters come from the reviewed manifest only")

    def test_sequence_run_refuses_a_manifest_without_live_authority(self) -> None:
        source = json.loads((ROOT / "experiments/DAY1-M8-AB-SEQUENCE-PENDING.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            for label, mutate, expected in (
                ("ungranted", {"transmission_authorized": False, "authorization_consumed": False}, "TRANSMISSION_AUTHORITY_MISSING"),
                ("consumed", {"transmission_authorized": True, "authorization_consumed": True}, "AUTHORITY_ALREADY_CONSUMED"),
            ):
                manifest = json.loads(json.dumps(source))
                manifest["authority"].update(mutate)
                path = Path(tmp) / f"{label}.json"
                path.write_text(json.dumps(manifest), encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "cli/openditoo.py"), "sequence-run", "--manifest", str(path)],
                    text=True, capture_output=True,
                )
                self.assertEqual(proc.returncode, 30, msg=label)
                self.assertEqual(json.loads(proc.stdout)["error_code"], expected)

    def test_finite_loop_manifest_is_internally_consistent(self) -> None:
        path = ROOT / "experiments/DAY1-M8-FINITE-LOOP-PENDING.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        budgets = manifest["budgets"]
        order = manifest["operation"]["frame_order"]
        self.assertEqual(len(order), budgets["application_requests"])
        self.assertEqual(budgets["application_packets"], len(order) * 3)
        # 3 packets per frame: preamble A (7) + preamble B (8) + image (56) = 71 bytes.
        self.assertEqual(budgets["application_tx_bytes_total"], len(order) * 71)
        self.assertEqual(budgets["expected_rx_frames"], len(order))
        # The one changed variable is repetition: the rate must match the proven step.
        proven = json.loads((ROOT / "experiments/DAY1-M8-AB-SEQUENCE-PENDING.json").read_text(encoding="utf-8"))
        self.assertEqual(budgets["inter_frame_delay_ms"], proven["budgets"]["inter_frame_delay_ms"])
        for key in ("a", "b"):
            self.assertEqual(manifest["operation"]["source_frames"][key]["packet_sha256"],
                             proven["operation"]["source_frames"][key]["packet_sha256"])

    def test_host_frame_ceiling_matches_a_reviewed_manifest(self) -> None:
        # The cap tracks the largest reviewed manifest rather than being an arbitrary
        # number: 2 while only the A->B sequence was proven, 10 for the finite loop, 512
        # for the sustained motion run. Raising it must require a manifest that needs it.
        protocol = (ROOT / "runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs").read_text(encoding="utf-8")
        requests = {}
        for path in sorted((ROOT / "experiments").glob("DAY1-*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            frames = (data.get("budgets") or {}).get("application_requests")
            if isinstance(frames, int) and (data.get("operation") or {}).get("frame_order"):
                requests[path.name] = frames
        self.assertTrue(requests, msg="no sequence manifest found to justify any cap")
        largest = max(requests.values())
        self.assertIn(f"MaxSequenceFrames = {largest};", protocol,
                      msg=f"cap must equal the largest reviewed request ({largest}); saw {requests}")
        # And that manifest must be a real reviewed experiment, not a stub.
        owner = max(requests, key=requests.get)
        data = json.loads((ROOT / "experiments" / owner).read_text(encoding="utf-8"))
        self.assertIn("authority", data)
        self.assertEqual(data["authority"]["experiment_id"], data["experiment_id"])

    def test_finite_loop_measurements_back_the_accepted_ceiling(self) -> None:
        manifest = json.loads((ROOT / "experiments/DAY1-M8-FINITE-LOOP-PENDING.json").read_text(encoding="utf-8"))
        run = manifest["attempts"][1]
        budgets = manifest["budgets"]
        self.assertEqual(run["outcome"], "transport_pass")
        self.assertEqual(run["packets_sent_complete"], budgets["application_packets"])
        self.assertEqual(run["tx_bytes_sent_complete"], budgets["application_tx_bytes_total"])
        self.assertEqual(run["frames_acked"], budgets["application_requests"])
        self.assertLessEqual(run["elapsed_ms"], budgets["total_wall_clock_ms"])
        self.assertEqual(len(run["frame_timings"]), budgets["application_requests"])
        # Every ACK arrived; a missing one would invalidate the rate claim.
        measured = manifest["measurements"]
        self.assertEqual(measured["ack_latency_ms"]["missing"], 0)
        self.assertEqual(measured["errors"], 0)
        # The accepted rate is the measured one, never the fastest imaginable.
        self.assertGreater(measured["achieved_inter_frame_interval_ms"]["mean"],
                           measured["requested_inter_frame_delay_ms"])
        self.assertIn("not the fastest possible", manifest["accepted_operating_ceiling"]["scope"])
        # The ACK-increment observation must stay a LEAD, not a semantic.
        lead = [f for f in manifest["findings"] if f["id"] == "ACK-PAYLOAD-INCREMENTS-MONOTONICALLY"][0]
        self.assertEqual(lead["confidence"], "LEAD")
        self.assertIn("not_claimed", lead)

    def test_rerun_reproduces_the_ceiling_and_narrows_the_ack_lead(self) -> None:
        first = json.loads((ROOT / "experiments/DAY1-M8-FINITE-LOOP-PENDING.json").read_text(encoding="utf-8"))
        rerun = json.loads((ROOT / "experiments/DAY1-M8-FINITE-LOOP-002-RERUN.json").read_text(encoding="utf-8"))
        self.assertEqual(rerun["experiment_id"], "OPENDITOO-M8-FINITE-LOOP-002")
        self.assertNotEqual(rerun["experiment_id"], first["experiment_id"],
                            msg="a repeat gets its own manifest; a consumed grant is never un-consumed")
        self.assertTrue(first["authority"]["authorization_consumed"])
        self.assertTrue(rerun["authority"]["authorization_consumed"])
        # Same reviewed shape: nothing about packets, rate or budgets may differ.
        self.assertEqual(rerun["budgets"], first["budgets"])
        self.assertEqual(rerun["operation"]["frame_order"], first["operation"]["frame_order"])
        result = rerun["result"]
        self.assertEqual(result["frames_acked"], rerun["budgets"]["application_requests"])
        self.assertLessEqual(result["elapsed_ms"], rerun["budgets"]["total_wall_clock_ms"])
        # The time-derivation hypothesis is now a measured negative, not a shrug.
        finding = rerun["findings"][0]
        self.assertEqual(finding["confidence"], "MATCHED_NEGATIVE")
        self.assertIn("RULED OUT", finding["statement"])
        self.assertIn("not_claimed", finding)
        # Two independent sessions started from different ACK values.
        self.assertNotEqual(result["ack_payload_hex_ordered"][0],
                            first["attempts"][1]["ack_payload_hex_ordered"][0])

    def test_finite_loop_attempt_1_failed_before_transmitting_anything(self) -> None:
        manifest = json.loads((ROOT / "experiments/DAY1-M8-FINITE-LOOP-PENDING.json").read_text(encoding="utf-8"))
        attempt = manifest["attempts"][0]
        self.assertEqual(attempt["outcome"], "failed_before_transmission")
        self.assertEqual(attempt["last_completed_stage"], "target_precheck")
        self.assertEqual(attempt["packets_sent_complete"], 0)
        self.assertEqual(attempt["tx_bytes_sent_complete"], 0)
        self.assertFalse(attempt["ambiguous"])
        self.assertFalse(attempt["in_flight_packet_bytes_unknown"])
        self.assertIn("No automatic retry", attempt["action_taken"])
        # The failed attempt is preserved alongside the successful one, not overwritten.
        self.assertEqual(len(manifest["attempts"]), 2)
        self.assertFalse(manifest["authority"]["transmission_authorized"])
        self.assertTrue(manifest["authority"]["authorization_consumed"])

    def test_m7_sweep_evidence_separates_state_reports_from_keystrokes(self) -> None:
        data = json.loads((ROOT / "captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json").read_text(encoding="utf-8"))
        self.assertFalse(data["device_io"])
        self.assertFalse(data["privacy"]["raw_bugreport_committed"])
        ids = {finding["id"]: finding for finding in data["findings"]}
        # The central discipline: these are state reports, never synthesised keystrokes.
        self.assertIn("REPORTS-ARE-STATE-NOT-KEYSTROKES", ids)
        self.assertIn("must never be synthesised", ids["REPORTS-ARE-STATE-NOT-KEYSTROKES"]["consequence"])
        # A silent control is "not observed here", never "handled internally".
        self.assertIn("NOT proof of internal-only handling", data["silent_controls"]["explicit_limit"])
        self.assertEqual(ids["NAVIGATION-KEYS-ARE-SILENT"]["confidence"], "MATCHED_UNDER_TESTED_CONTEXT")
        # Tivoo 0x46 semantics must not be imported on the strength of a shared number.
        self.assertIn("No OpenTivoo 0x46 semantics are imported", ids["DITOO-0X46-IS-NATIVE-EVIDENCE-NOT-INHERITED"]["not_claimed"])
        self.assertIn("decisive_trial", data["open_question"])
        reported = {report["reported_command"] for report in data["unsolicited_reports"]}
        self.assertEqual(reported, {"0x09", "0x46", "0xBD"})

    def test_m7_report_fields_are_derived_from_the_captured_wire(self) -> None:
        # An earlier hand-transcribed payload silently dropped a byte. Every derived
        # field is now re-derived from wire_hex so transcription cannot drift again.
        data = json.loads((ROOT / "captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json").read_text(encoding="utf-8"))
        for report in data["unsolicited_reports"]:
            decoded = decode_candidate_normal(bytes.fromhex(report["wire_hex"]))
            self.assertEqual(decoded.command, 0x04)
            self.assertEqual(decoded.payload[1], 0x55, msg="wrapped report tag")
            self.assertEqual(report["reported_command"], f"0x{decoded.payload[0]:02X}")
            self.assertEqual(report["data_hex"], decoded.payload[2:].hex())
            self.assertEqual(report["data_bytes"], len(decoded.payload) - 2)
        widths = {r["reported_command"]: r["data_bytes"] for r in data["unsolicited_reports"]}
        self.assertEqual(widths["0x09"], 1)
        self.assertEqual(widths["0x46"], 22)

    def test_m8_sequence_visual_order_is_resolved(self) -> None:
        result = json.loads((ROOT / "experiments/DAY1-M8-AB-SEQUENCE-PENDING.json").read_text(encoding="utf-8"))["result"]
        self.assertEqual(result["operator_visual_order"], "confirmed_a_then_b")
        self.assertIn("RESOLVED", result["residual"])
        self.assertIn("bounded by stock takeover", result["frame_lifetime_note"])

    def test_handoff_and_routing_match_the_real_authority_state(self) -> None:
        # A stale handoff is how a physical experiment gets repeated. Pin the claims
        # that would cause that to the actual manifests.
        handoff = (ROOT / "notes/OPENDITOO-HANDOFF-2026-09-09.md").read_text(encoding="utf-8")
        start_here = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
        self.assertIn("OPENDITOO-HANDOFF-2026-09-09.md", start_here)
        # The contract is that routing matches one-shot experimental manifests in BOTH
        # directions. Persistent product authority is intentionally local/git-ignored and
        # is therefore NOT inferable from committed manifests; routing must send readers
        # to the local product policy/status rather than claiming that no authority of any
        # kind exists.
        armed = []
        for path in sorted((ROOT / "experiments").glob("DAY1-M*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            authority = manifest.get("authority")
            if authority is None:
                continue
            if authority["transmission_authorized"]:
                armed.append(manifest["experiment_id"])
                self.assertFalse(authority["authorization_consumed"],
                                 msg=f"{path.name} is armed and consumed at once")
        for document in (handoff, start_here):
            if armed:
                self.assertNotIn("nothing is currently authorized", document.lower(),
                                 msg="a grant is live but the routing still says nothing is authorized")
                for experiment_id in armed:
                    self.assertIn(experiment_id, document,
                                  msg=f"live grant {experiment_id} is not named in the routing")
            else:
                lowered = document.lower()
                self.assertIn("001–009", lowered)
                self.assertIn("consumed", lowered)
                self.assertIn("runtime 001", lowered)
                self.assertIn("runtime 002", lowered)
                self.assertIn("grant openditoo-product-runtime-002", lowered)
                self.assertNotIn("currently authorized for one", lowered,
                                 msg="routing still advertises a consumed one-shot grant")
        # Every note the routing sends a reader to must exist.
        for name in ("OPENDITOO-M6-RUNTIME-ACCEPTANCE-2026-09-09.md",
                     "OPENDITOO-M7-CONTROL-WORKSHEET-2026-09-09.md",
                     "OPENDITOO-M7-OPENTIVOO-COMPARISON-2026-09-09.md",
                     "OPENDITOO-M8-SEQUENCE-EVIDENCE-2026-09-09.md",
                     "OPENDITOO-M9-SOURCE-DISCOVERY-2026-09-09.md",
                     "OPENDITOO-HANDOFF-2026-09-09.md"):
            self.assertTrue((ROOT / "notes" / name).is_file(), msg=f"routing points at a missing note: {name}")
        self.assertTrue((ROOT / "captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json").is_file())

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


class _FailingAdapter:
    """Always unreadable, so a failed poll can be asserted end to end."""

    kind = "stub"

    def __init__(self, source_id: str, config: dict) -> None:
        pass

    def poll(self, cursor):
        raise mcp_activity.SourceError("SOURCE_READ_FAILED")


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
    """The approved three-MCP page: L/mushroom, O/bunny, W/skull, blue activity override.

    The design arrived as mockups, so the mockups are the acceptance criteria: the pixel
    data is derived from them, and these tests re-derive it and re-render every reference
    frame. Nothing here is hand-transcribed.
    """

    REFERENCE = ROOT / "assets/ui/reference"
    AGE = {"green": timedelta(minutes=1), "yellow": timedelta(minutes=10), "red": timedelta(hours=1)}
    MIXED = {"optiplex_lab": "green", "optiplex_mcp": "yellow", "wsl_mcp": "red"}

    def setUp(self) -> None:
        self.now = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)

    def _state(self, statuses: dict, health: str = "healthy") -> dict:
        state = mcp_activity.blank_state()
        for source_id, status in statuses.items():
            source = state["sources"][source_id]
            if status == "grey":
                source["source_health"] = "unknown"
                source["last_activity_at"] = None
            else:
                source["source_health"] = health
                source["last_activity_at"] = mcp_activity.iso(self.now - self.AGE[status])
        return state

    def test_the_generated_pixel_data_still_matches_the_reference_frames(self) -> None:
        # If the mockups or the derivation change, the committed data must be regenerated
        # rather than edited. This is the guard that makes that true.
        proc = subprocess.run([sys.executable, "scripts/generate_activity_ui_data.py", "--check"],
                              cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("ACTIVITY_UI_DATA_OK", proc.stdout)

    @staticmethod
    def _flip(rgb: bytes) -> bytes:
        """Apply the operator's letter/icon swap to an approved mockup.

        Imported from the generator so there is exactly ONE definition of the transform:
        this asserts the renderer reproduces the approved artwork with precisely that
        change applied, and nothing else drifting alongside it.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_ui", ROOT / "scripts/generate_activity_ui_data.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        out = bytearray(len(rgb))
        for index in range(256):
            target = gen.flip_index(index)
            out[target * 3:target * 3 + 3] = rgb[index * 3:index * 3 + 3]
        return bytes(out)

    def test_every_approved_mockup_is_reproduced_pixel_for_pixel(self) -> None:
        cases = [(f"all_{s}_16x16.png", {k: s for k in mcp_activity.SOURCE_IDS}, set())
                 for s in ("green", "yellow", "red", "grey")]
        cases.append(("mixed_state_16x16.png", self.MIXED, set()))
        for prefix, source_id in (("left", "optiplex_lab"), ("mid", "optiplex_mcp"),
                                  ("right", "wsl_mcp")):
            cases.append((f"{prefix}_activity_blue_override_16x16.png", self.MIXED, {source_id}))
        for name, statuses, pulses in cases:
            with self.subTest(name):
                expected = self._flip(decode_png16_rgb(self.REFERENCE / name))
                actual = activity_render.render_rgb888(self._state(statuses), self.now, pulses)
                self.assertEqual(actual, expected)

    def test_status_boundaries_are_deterministic(self) -> None:
        for minutes, expected in ((0, "green"), (4.99, "green"), (5, "yellow"),
                                  (19.99, "yellow"), (20, "red"), (600, "red")):
            source = {"source_health": "healthy",
                      "last_activity_at": mcp_activity.iso(self.now - timedelta(minutes=minutes))}
            self.assertEqual(activity_render.status_for(source, self.now), expected,
                             msg=f"{minutes} min")
        self.assertEqual(activity_render.status_for(
            {"source_health": "healthy", "last_activity_at": None}, self.now), "grey")

    def test_status_transition_acceptance_uses_production_colours_on_a_virtual_clock(self) -> None:
        from host import activity_session as session_mod
        class Manifest:
            acceptance_profile = session_mod.STATUS_TRANSITION_ACCEPTANCE_PROFILE

        persisted = self._state(self.MIXED)
        original = json.loads(json.dumps(persisted))
        renderer = session_mod.live_renderer({}, persisted, Manifest())
        expected_times = (
            (0, "green"), (2999, "green"),
            (3000, "yellow"), (5999, "yellow"),
            (6000, "red"), (8999, "red"),
            (9000, "grey"), (12000, "grey"),
        )
        for now_ms, status in expected_times:
            with self.subTest(now_ms=now_ms, status=status):
                rgb, from_pulse = renderer(now_ms)
                self.assertFalse(from_pulse)
                expected = activity_render.render_rgb888(
                    self._state({sid: status for sid in mcp_activity.SOURCE_IDS}), self.now)
                self.assertEqual(rgb, expected)
        self.assertEqual(persisted, original, msg="acceptance profile must not mutate persisted activity state")

    def test_status_transition_acceptance_never_collects_or_saves_sources(self) -> None:
        from host import activity_session as session_mod
        class Manifest:
            acceptance_profile = session_mod.STATUS_TRANSITION_ACCEPTANCE_PROFILE

        original_collect = mcp_activity.collect_once
        original_save = mcp_activity.save_state
        try:
            mcp_activity.collect_once = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not collect"))
            mcp_activity.save_state = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not save"))
            renderer = session_mod.live_renderer({}, self._state(self.MIXED), Manifest())
            for now_ms in (0, 3000, 6000, 9000):
                rgb, pulse = renderer(now_ms)
                self.assertEqual(len(rgb), 16 * 16 * 3)
                self.assertFalse(pulse)
        finally:
            mcp_activity.collect_once = original_collect
            mcp_activity.save_state = original_save

    def test_a_future_stamp_is_skew_and_never_renders_as_fresh(self) -> None:
        ahead = {"source_health": "healthy",
                 "last_activity_at": mcp_activity.iso(self.now + timedelta(minutes=5))}
        self.assertEqual(activity_render.status_for(ahead, self.now), "grey")

    def test_an_unreadable_source_greys_out_despite_recent_history(self) -> None:
        # Its status colour is grey like any quiet source -- the fault bar, not the
        # status colour, is what separates unreachable from idle, and the health still
        # survives separately in the JSON.
        state = self._state({"optiplex_mcp": "green"})
        state["sources"]["optiplex_mcp"]["source_health"] = "unavailable"
        view = activity_render.describe(state, self.now)["optiplex_mcp"]
        self.assertEqual(view["status"], "grey")
        self.assertTrue(view["fault"])
        self.assertEqual(view["source_health"], "unavailable")
        self.assertIn("fault", activity_render.LEGEND)

    def test_letters_are_on_the_bottom_and_icons_in_the_middle(self) -> None:
        # Operator change: the approved mockups put letters above icons; the two 5-row
        # blocks are swapped. The crown, spacer and divider rows are untouched.
        import importlib
        data = importlib.import_module("host.activity_ui_data")
        letter_rows = {i // 16 for i in data.ROLE_PIXELS["accent"]}
        cap_rows = {i // 16 for r in ("cap_base", "cap_dark", "cap_light")
                    for i in data.ROLE_PIXELS[r]}
        self.assertTrue(cap_rows <= {5, 6, 7}, msg=f"mushroom cap should be mid-band, got {cap_rows}")
        self.assertTrue({11, 12, 13, 14, 15} <= letter_rows, msg="letters should occupy rows 11-15")
        # Row 7 is the bunny/skull eyes, which share the accent role and live with the icons.
        self.assertEqual(letter_rows - {11, 12, 13, 14, 15}, {7})
        self.assertIn("5-9 icon", activity_render.LEGEND["rows"])
        self.assertIn("11-15 identity letter", activity_render.LEGEND["rows"])

    def test_the_layout_keeps_its_approved_geometry(self) -> None:
        rgb = activity_render.render_rgb888(self._state(self.MIXED), self.now)
        self.assertEqual(len(rgb), 16 * 16 * 3)

        def row(y):
            return rgb[y * 48:(y + 1) * 48]

        for y in (3, 4, 10):
            self.assertEqual(row(y), bytes(48), msg=f"row {y} is a spacer or divider")
        for y in (0, 1, 2):
            self.assertEqual(row(y), bytes(48), msg="no crown without activity")
        # x=15 is spare in every state.
        for y in range(16):
            self.assertEqual(rgb[(y * 16 + 15) * 3:(y * 16 + 15) * 3 + 3], b"\x00\x00\x00")

    def test_activity_lights_the_crown_only_over_its_own_column(self) -> None:
        rgb = activity_render.render_rgb888(self._state(self.MIXED), self.now, {"optiplex_mcp"})
        lit = {(i % 16) for i in range(16 * 3)
               if rgb[i * 3:i * 3 + 3] != b"\x00\x00\x00"}
        self.assertEqual(lit, {5, 6, 7, 8, 9})

    def test_simultaneous_activity_merges_and_is_never_queued(self) -> None:
        # Crowns are per column and cannot collide, so concurrent events show together.
        # Nothing is deferred to a later frame, which is what "no replay" requires.
        rgb = activity_render.render_rgb888(self._state(self.MIXED), self.now,
                                            set(mcp_activity.SOURCE_IDS))
        lit = {(i % 16) for i in range(16 * 3) if rgb[i * 3:i * 3 + 3] != b"\x00\x00\x00"}
        self.assertEqual(lit, set(range(15)))

    def test_activity_overrides_only_the_active_column(self) -> None:
        state = self._state(self.MIXED)
        rgb = activity_render.render_rgb888(state, self.now, {"optiplex_lab"})
        override = bytes(activity_render.OVERRIDE_RGB)
        letter_l = (11 * 16 + 1) * 3       # L stem on the bottom band, active column
        letter_o = (11 * 16 + 6) * 3       # O, untouched column
        self.assertEqual(rgb[letter_l:letter_l + 3], override)
        self.assertEqual(rgb[letter_o:letter_o + 3], bytes((255, 255, 0)))

    def test_the_four_live_pulse_stages_use_the_approved_color_family(self) -> None:
        state = self._state(self.MIXED)
        letter_o = (11 * 16 + 6) * 3
        crown_o = (0 * 16 + 5) * 3
        for stage, color in enumerate(activity_render.PULSE_COLORS):
            with self.subTest(stage=stage):
                rgb = activity_render.render_rgb888(
                    state, self.now, {"optiplex_mcp"}, pulse_stage=stage)
                self.assertEqual(rgb[letter_o:letter_o + 3], bytes(color))
                self.assertEqual(rgb[crown_o:crown_o + 3], bytes(color))
        with self.assertRaises(ValueError):
            activity_render.render_rgb888(state, self.now, {"optiplex_mcp"}, pulse_stage=4)

    def test_live_renderer_polls_sources_slowly_but_runs_three_acked_color_sweeps(self) -> None:
        from host import activity_session as session_mod
        state = self._state(self.MIXED)
        config = {"poll_seconds": 2.0, "sources": {sid: {} for sid in mcp_activity.SOURCE_IDS}}
        calls = []
        original_collect = mcp_activity.collect_once
        original_save = mcp_activity.save_state
        try:
            def fake_collect(_config, _state, poll_seconds=2.0):
                calls.append(poll_seconds)
                return {"optiplex_lab": 0, "optiplex_mcp": 1 if len(calls) == 1 else 0, "wsl_mcp": 0}
            mcp_activity.collect_once = fake_collect
            mcp_activity.save_state = lambda _state: None
            renderer = session_mod.live_renderer(config, state)
            letter_o = (11 * 16 + 6) * 3
            program = session_mod.ACTIVITY_PULSE_PROGRAM
            self.assertEqual(program, (0, 1, 2, 3, 1, 2, 3, 1, 2, 3))
            for step, stage in enumerate(program):
                rgb, from_pulse = renderer(step * 200)
                self.assertTrue(from_pulse)
                self.assertEqual(rgb[letter_o:letter_o + 3], bytes(activity_render.PULSE_COLORS[stage]))
                renderer.frame_sent()
            base, from_pulse = renderer(len(program) * 200)
            self.assertFalse(from_pulse)
            expected_base = activity_render.render_rgb888(state)
            self.assertEqual(base, expected_base, msg="after three sweeps the display must return to current status colors")
            self.assertEqual(calls, [2.0, 2.0], msg="fast display ticks must not become fast source polling")
        finally:
            mcp_activity.collect_once = original_collect
            mcp_activity.save_state = original_save

    def test_every_state_health_and_activity_combination_encodes_for_the_device(self) -> None:
        worst = 0
        for combo in itertools.product(("green", "yellow", "red", "grey"), repeat=3):
            statuses = dict(zip(mcp_activity.SOURCE_IDS, combo))
            for healths in itertools.product(("healthy", "unavailable", "stale", "unknown"), repeat=3):
                state = self._state(statuses)
                for sid, health in zip(mcp_activity.SOURCE_IDS, healths):
                    state["sources"][sid]["source_health"] = health
                for count in range(4):
                    for pulses in itertools.combinations(mcp_activity.SOURCE_IDS, count):
                        rgb = activity_render.render_rgb888(state, self.now, set(pulses))
                        wire, palette_colors = encode_rgb888_static_image(rgb)
                        self.assertLessEqual(palette_colors, 255)
                        worst = max(worst, len(wire))
        # Pinned so a budget derived from it cannot silently go stale. The fault red
        # reuses a colour already in the design, so adding it cost nothing.
        self.assertEqual(worst, 188)

    def test_the_display_path_is_not_constrained_to_the_artwork_palette(self) -> None:
        # RGB222 came in with the Tivoo artwork, not from this device: all 8/8 captured
        # stock 0x44 snapshots re-encoded byte-for-byte from an RGB888 palette. Prove it
        # behaviourally -- colours the artwork never uses must survive the whole encode
        # path untouched, so nothing downstream quantises them.
        off_palette = [(1, 2, 3), (17, 200, 99), (254, 128, 7), (85, 86, 87)]
        rgb = bytearray()
        for index in range(256):
            rgb += bytes(off_palette[index % len(off_palette)])
        wire, palette_colors = encode_rgb888_static_image(bytes(rgb))
        self.assertEqual(palette_colors, len(off_palette))
        self.assertEqual(_decode_static_image_packet(wire), bytes(rgb))
        self.assertIn("RGB888", activity_render.LEGEND["color_model"])

    def test_an_unreadable_source_shows_a_fault_bar_in_its_own_crown_row(self) -> None:
        for health, expected in (("unavailable", True), ("stale", True),
                                 ("unknown", False), ("healthy", False)):
            with self.subTest(health):
                state = self._state(self.MIXED)
                state["sources"]["optiplex_mcp"]["source_health"] = health
                view = activity_render.describe(state, self.now)["optiplex_mcp"]
                self.assertEqual(view["fault"], expected)
                rgb = activity_render.render_rgb888(state, self.now)
                bar = {rgb[(0 * 16 + x) * 3:(0 * 16 + x) * 3 + 3] for x in (6, 7, 8)}
                self.assertEqual(bar == {bytes(activity_render.FAULT_RGB)}, expected)

    def test_a_source_never_polled_shows_no_fault_bar(self) -> None:
        # Otherwise a cold start would light three fault bars before the first poll.
        rgb = activity_render.render_rgb888(mcp_activity.blank_state(), self.now)
        self.assertEqual(rgb[:48], bytes(48))

    def test_the_fault_bar_and_the_activity_crown_cannot_both_be_drawn(self) -> None:
        state = self._state(self.MIXED)
        state["sources"]["optiplex_mcp"]["source_health"] = "unavailable"
        rgb = activity_render.render_rgb888(state, self.now, {"optiplex_mcp"})
        # Fault wins, and the crown's rows 1-2 in that column stay dark.
        self.assertEqual(rgb[(0 * 16 + 7) * 3:(0 * 16 + 7) * 3 + 3], bytes(activity_render.FAULT_RGB))
        for y in (1, 2):
            for x in range(5, 10):
                self.assertEqual(rgb[(y * 16 + x) * 3:(y * 16 + x) * 3 + 3], b"\x00\x00\x00")

    def test_the_collector_never_pulses_a_source_it_failed_to_read(self) -> None:
        # This is why fault and crown cannot collide in practice; the renderer does not
        # rely on it, but if it ever broke the display would start lying.
        config = {"sources": {sid: {} for sid in mcp_activity.SOURCE_IDS}}
        state = mcp_activity.blank_state()
        for sid in mcp_activity.SOURCE_IDS:
            state["sources"][sid]["cursor"] = {"offset": 0}
        original = dict(mcp_activity.ADAPTERS)
        try:
            for sid in mcp_activity.SOURCE_IDS:
                mcp_activity.ADAPTERS[sid] = _FailingAdapter
            counts = mcp_activity.collect_once(config, state)
        finally:
            mcp_activity.ADAPTERS.clear()
            mcp_activity.ADAPTERS.update(original)
        self.assertEqual(set(counts.values()), {0})
        for sid in mcp_activity.SOURCE_IDS:
            self.assertEqual(state["sources"][sid]["source_health"], "unavailable")

    def test_a_fault_bar_does_not_disturb_the_approved_letters_or_icons(self) -> None:
        clean = self._state(self.MIXED)
        faulted = self._state(self.MIXED)
        faulted["sources"]["optiplex_mcp"]["source_health"] = "unavailable"
        a = activity_render.render_rgb888(clean, self.now)
        b = activity_render.render_rgb888(faulted, self.now)
        # Rows 5-15 differ only because that column greyed out; rows 3-4 and 10 stay clear.
        for y in (3, 4, 10):
            self.assertEqual(b[y * 48:(y + 1) * 48], bytes(48))
        # Columns other than the faulted one are untouched from rows 3 down.
        for y in range(3, 16):
            for x in list(range(0, 5)) + list(range(10, 16)):
                i = (y * 16 + x) * 3
                self.assertEqual(a[i:i + 3], b[i:i + 3], msg=f"({x},{y}) changed outside the faulted column")

    def test_preview_pngs_are_written_and_decode_back_to_the_exact_frame(self) -> None:
        rgb = activity_render.render_rgb888(self._state(self.MIXED), self.now)
        with tempfile.TemporaryDirectory() as tmp:
            outputs = activity_render.write_previews(Path(tmp), rgb, scale=4)
            self.assertEqual(decode_png16_rgb(Path(outputs["exact_png"])), rgb)
            self.assertTrue(Path(outputs["preview_png"]).is_file())

    def test_the_outbound_opentivoo_note_is_sanitised(self) -> None:
        """It is written to leave this repository, so it must carry nothing private."""
        note = (ROOT / "notes/SHARED-RATE-FINDINGS-FOR-OPENTIVOO-2026-09-09.md").read_text(encoding="utf-8")
        for secret in ("11:75:58:CE:DE:C7", "11:75:58", "192.168.", "/home/", "C:\\Users",
                       ".openditoo-local", "host.token", "Bearer ", "@192", "8796"):
            self.assertNotIn(secret, note, msg=f"outbound note leaks {secret!r}")
        # And it must not invite OpenTivoo to inherit numbers that were never measured there.
        self.assertIn("does not transfer", note.lower())
        self.assertIn("hypothesis", note.lower())
        self.assertIn("What we did not establish", note)

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

    def test_accepts_a_bugreport_zip_and_records_both_hashes(self) -> None:
        import zipfile as _zipfile

        wire = encode_candidate_normal(0x58, bytes.fromhex("ffffff016a"))
        records = self._open_rfcomm(1, 0x0041, 0x0044)
        records.append(("tx", _h4_acl(self.HANDLE, 2, _l2cap(0x0044, _rfcomm_uih(2, wire)))))
        blob = self._capture(records)
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bugreport-test.zip"
            with _zipfile.ZipFile(archive, "w") as handle:
                handle.writestr(btsnoop.BUGREPORT_SNOOP_CURRENT, blob)
                handle.writestr(btsnoop.BUGREPORT_SNOOP_PREVIOUS, b"btsnoop\x00" + b"\x00" * 8)
            view, frames, _ = btsnoop.read(archive, peer_bdaddr=self.PEER, reveal_commands={0x58})
        self.assertEqual([frame.hex for frame in frames], [wire.hex()])
        provenance = view.provenance
        self.assertEqual(provenance["container"], "android_bugreport_zip")
        self.assertEqual(provenance["zip_entry"], btsnoop.BUGREPORT_SNOOP_CURRENT)
        # Both hashes matter: the archive for provenance, the log for evidence identity.
        self.assertEqual(provenance["btsnoop_sha256"], __import__("hashlib").sha256(blob).hexdigest())
        self.assertNotEqual(provenance["source_sha256"], provenance["btsnoop_sha256"])
        self.assertEqual(provenance["other_btsnoop_entries"], [btsnoop.BUGREPORT_SNOOP_PREVIOUS])

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


# --------------------------------------------------------------------------
# N2/N3 — bounded activation authority, takeover-aware receive, change-only sending
# --------------------------------------------------------------------------

from host import activity_session  # noqa: E402
from host import product_runtime  # noqa: E402
from host import product_runtime_v2  # noqa: E402
from host import frame_stream  # noqa: E402

HOST_DIR = ROOT / "runtime/windows/OpenDitoo.Day1.Host"


def _valid_manifest(**overrides) -> dict:
    """The smallest manifest that passes, so each test can break exactly one thing."""
    session = {"lifetime_seconds": 300, "min_frame_interval_ms": 150,
               "pulse_freshness_seconds": 30, "poll_interval_ms": 150,
               "activation_source": "three MCP audit sources",
               "automatic_retry": False, "automatic_reconnect": False,
               "stock_screen_reclaim": False, "replay_after_interruption": False}
    budgets = {"max_frames": 60, "max_application_packets": 180, "max_tx_bytes": 60 * 2000,
               "connection_attempts": 1, "ack_timeout_ms_per_frame": 5000}
    data = {
        "schema_version": 2,
        "experiment_id": "OPENDITOO-TEST-001",
        "milestone": "test",
        "target": {"exact_unit_id": "11:75:58:CE:DE:C7", "installed_firmware": "v42012"},
        "transport": {"measured_endpoint": "Windows Classic serial channel 1"},
        "session": session,
        "budgets": budgets,
        "build": {"code_sha256": activity_session.module_hashes(), "host_dll_sha256": "a" * 64},
        "stop_policy": {"stop_immediately_on": ["unexpected state report"],
                        "on_ambiguous_outcome_resend": False,
                        "collection_continues_after_display_stop": True},
        "authority": {"transmission_authorized": True, "authorization_consumed": False,
                      "experiment_id": "OPENDITOO-TEST-001", "granted_by": "operator",
                      "grant_text": "test", "expires_at": "2999-01-01T00:00:00Z"},
    }
    for path, value in overrides.items():
        section, _, key = path.partition(".")
        if key:
            data[section][key] = value
        else:
            data[section] = value
    return data


class N2SessionManifestTests(unittest.TestCase):
    def _load(self, **overrides):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps(_valid_manifest(**overrides)), encoding="utf-8")
            return activity_session.load_session_manifest(path)

    def _refuses(self, code: str, **overrides) -> None:
        with self.assertRaises(activity_session.SessionError) as caught:
            self._load(**overrides)
        self.assertEqual(caught.exception.code, code)

    def test_a_complete_manifest_loads_with_its_budgets_intact(self) -> None:
        manifest = self._load()
        self.assertEqual(manifest.experiment_id, "OPENDITOO-TEST-001")
        self.assertEqual(manifest.max_application_packets, manifest.max_frames * 3)
        self.assertGreaterEqual(manifest.min_frame_interval_ms,
                                activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS)

    def test_missing_or_consumed_or_expired_authority_all_refuse(self) -> None:
        self._refuses("TRANSMISSION_AUTHORITY_MISSING",
                      **{"authority": {**_valid_manifest()["authority"], "transmission_authorized": False}})
        self._refuses("AUTHORITY_ALREADY_CONSUMED",
                      **{"authority": {**_valid_manifest()["authority"], "authorization_consumed": True}})
        self._refuses("AUTHORITY_EXPIRED",
                      **{"authority": {**_valid_manifest()["authority"], "expires_at": "2020-01-01T00:00:00Z"}})

    def test_a_grant_must_name_the_experiment_it_authorizes(self) -> None:
        self._refuses("AUTHORITY_EXPERIMENT_ID_MISMATCH",
                      **{"authority": {**_valid_manifest()["authority"], "experiment_id": "SOMETHING-ELSE"}})

    def test_pacing_faster_than_the_product_operating_floor_is_refused(self) -> None:
        # R4 sustained 131 ms / 7.63 fps and R5 reached 54.2 ms / 18.46 fps, but the
        # product deliberately operates at 150 ms / 6.67 fps for jitter headroom.
        self._refuses("SESSION_PACING_BELOW_ACCEPTED_CEILING", **{"session.min_frame_interval_ms": 149})

    def test_budgets_must_be_derived_not_asserted(self) -> None:
        self._refuses("BUDGET_PACKETS_NOT_DERIVED", **{"budgets.max_application_packets": 61})
        self._refuses("BUDGET_FRAMES_EXCEED_LIFETIME",
                      **{"session": {**_valid_manifest()["session"], "lifetime_seconds": 1},
                         "budgets": {**_valid_manifest()["budgets"], "max_frames": 8,
                                     "max_application_packets": 24}})
        self._refuses("BUDGET_CONNECTION_ATTEMPTS_INVALID", **{"budgets.connection_attempts": 2})

    def test_a_lifetime_beyond_the_supervised_ceiling_is_refused(self) -> None:
        self._refuses("SESSION_LIFETIME_INVALID", **{"session.lifetime_seconds": 100_000})

    def test_only_the_named_status_transition_acceptance_profile_is_allowed(self) -> None:
        self._refuses("SESSION_ACCEPTANCE_PROFILE_INVALID",
                      **{"acceptance_profile": "invented_profile"})
        manifest = self._load(**{"acceptance_profile": activity_session.STATUS_TRANSITION_ACCEPTANCE_PROFILE})
        self.assertEqual(manifest.acceptance_profile, activity_session.STATUS_TRANSITION_ACCEPTANCE_PROFILE)

    def test_retry_reconnect_reclaim_and_replay_must_all_be_disabled(self) -> None:
        for field, code in (("automatic_retry", "SESSION_RETRY_NOT_DISABLED"),
                            ("automatic_reconnect", "SESSION_RECONNECT_NOT_DISABLED"),
                            ("stock_screen_reclaim", "SESSION_RECLAIM_NOT_DISABLED"),
                            ("replay_after_interruption", "SESSION_REPLAY_NOT_DISABLED")):
            self._refuses(code, **{f"session.{field}": True})

    def test_a_fault_policy_that_stops_collection_or_resends_is_refused(self) -> None:
        self._refuses("STOP_POLICY_PERMITS_RESEND",
                      **{"stop_policy": {**_valid_manifest()["stop_policy"], "on_ambiguous_outcome_resend": True}})
        self._refuses("STOP_POLICY_STOPS_COLLECTION",
                      **{"stop_policy": {**_valid_manifest()["stop_policy"],
                                         "collection_continues_after_display_stop": False}})

    def test_renderer_or_collector_drift_invalidates_the_reviewed_envelope(self) -> None:
        # A dynamic session cannot freeze future pixels, so it freezes the code that
        # produces them instead. Change the renderer and the manifest is no longer it.
        drifted = {**activity_session.module_hashes(), "renderer_sha256": "0" * 64}
        self._refuses("BUILD_CODE_HASH_DRIFT",
                      **{"build": {"code_sha256": drifted, "host_dll_sha256": "a" * 64}})

    def test_the_target_is_the_exact_purchased_unit_and_firmware(self) -> None:
        self._refuses("MANIFEST_TARGET_MISMATCH",
                      **{"target": {"exact_unit_id": "11:75:58:C8:5E:FE", "installed_firmware": "v42012"}})
        self._refuses("MANIFEST_FIRMWARE_MISMATCH",
                      **{"target": {"exact_unit_id": "11:75:58:CE:DE:C7", "installed_firmware": "v1"}})


class N2SessionClaimTests(unittest.TestCase):
    def test_one_claim_per_experiment_id_and_no_release_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claim = activity_session.SessionClaim("E-1", Path(tmp))
            claim.claim({"manifest_file": "m.json"})
            twin = activity_session.SessionClaim("E-1", Path(tmp))
            with self.assertRaises(activity_session.SessionError) as caught:
                twin.claim({"manifest_file": "m.json"})
            self.assertEqual(caught.exception.code, "AUTHORITY_ALREADY_CONSUMED")

    def test_a_crash_leaves_an_unknown_outcome_that_still_refuses_re_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            activity_session.SessionClaim("E-2", Path(tmp)).claim({})
            # No finish() call: the worker died here.
            record = activity_session.SessionClaim("E-2", Path(tmp)).read()
            self.assertEqual((record["state"], record["outcome"]), ("claimed", "unknown"))
            with self.assertRaises(activity_session.SessionError):
                activity_session.SessionClaim("E-2", Path(tmp)).claim({})

    def test_a_terminal_result_is_recorded_over_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claim = activity_session.SessionClaim("E-3", Path(tmp))
            claim.claim({})
            claim.finish("stopped_clean", {"terminal_reason": "lifetime_expired", "frames_sent": 4})
            record = claim.read()
            self.assertEqual(record["state"], "finished")
            self.assertEqual(record["outcome"], "stopped_clean")
            self.assertEqual(record["frames_sent"], 4)

    def test_no_source_path_un_consumes_authority(self) -> None:
        src = (ROOT / "host/activity_session.py").read_text(encoding="utf-8")
        for forbidden in ("def release", "def unclaim", "def reset", "authorization_consumed = False",
                          "os.remove", "os.unlink", "unlink()"):
            self.assertNotIn(forbidden, src, msg=f"a claim must never be releasable: {forbidden}")


class N3SchedulerTests(unittest.TestCase):
    RED = bytes([255, 0, 0]) * 256
    BLUE = bytes([0, 0, 255]) * 256
    GREEN = bytes([0, 255, 0]) * 256

    def _scheduler(self, interval: int = 150, freshness: int = 30_000):
        return activity_session.ChangeOnlyScheduler(interval, freshness)

    def test_an_unchanged_scene_sends_nothing_ever(self) -> None:
        s = self._scheduler()
        s.observe(0, self.RED)
        self.assertEqual(s.next_action(0), ("send", "changed"))
        s.sending(0); s.sent()
        for now in range(1000, 60_000, 1000):
            s.observe(now, self.RED)
            self.assertEqual(s.next_action(now), ("hold", "unchanged"))
        self.assertEqual(s.frames_sent, 1)

    def test_the_accepted_interval_is_a_ceiling_not_a_heartbeat(self) -> None:
        s = self._scheduler()
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.observe(50, self.BLUE)
        self.assertEqual(s.next_action(50), ("hold", "pacing"))
        self.assertEqual(s.next_action(149), ("hold", "pacing"))
        self.assertEqual(s.next_action(150), ("send", "changed"))

    def test_a_burst_coalesces_to_the_newest_frame_and_queues_nothing(self) -> None:
        s = self._scheduler()
        s.observe(0, self.RED); s.sending(0); s.sent()
        for now, frame in ((100, self.BLUE), (200, self.GREEN), (300, self.BLUE)):
            s.observe(now, frame)
        self.assertEqual(s.next_action(1200)[0], "send")
        self.assertEqual(s.sending(1200).rgb, self.BLUE)  # newest only; nothing replayed

    def test_a_pulse_that_misses_its_window_is_dropped_not_replayed_later(self) -> None:
        s = self._scheduler(freshness=5_000)
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.observe(100, self.BLUE, from_pulse=True)
        self.assertEqual(s.next_action(120), ("hold", "pacing"))
        self.assertEqual(s.next_action(20_000), ("hold", "pulse_expired"))
        # It is gone, not deferred: a later slot must not resurrect it.
        self.assertEqual(s.next_action(30_000), ("hold", "no_render_yet"))
        self.assertEqual(s.dropped_expired_pulses, 1)

    def test_a_pulse_survives_to_the_next_permitted_slot_inside_its_window(self) -> None:
        s = self._scheduler(freshness=30_000)
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.observe(50, self.BLUE, from_pulse=True)   # arrives while pacing forbids sending
        self.assertEqual(s.next_action(100), ("hold", "pacing"))
        self.assertEqual(s.next_action(150), ("send", "changed"))

    def test_a_persisting_scene_cannot_renew_a_pulse_window_indefinitely(self) -> None:
        s = self._scheduler(freshness=5_000)
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.observe(100, self.BLUE, from_pulse=True)
        for now in range(200, 9_000, 200):
            s.observe(now, self.BLUE, from_pulse=True)  # same image, re-observed
        self.assertEqual(s.next_action(9_000), ("hold", "pulse_expired"))

    def test_age_or_health_change_sends_without_any_new_activity(self) -> None:
        # Not every legitimate frame change comes from a pulse.
        s = self._scheduler()
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.observe(60_000, self.GREEN, from_pulse=False)
        self.assertEqual(s.next_action(60_000), ("send", "changed"))

    def test_an_invalidated_canvas_holds_forever_and_never_reclaims(self) -> None:
        s = self._scheduler()
        s.observe(0, self.RED); s.sending(0); s.sent()
        s.invalidate_canvas("state_report")
        self.assertEqual(s.display_state(), "unknown_not_ours")
        s.observe(5_000, self.BLUE)
        self.assertEqual(s.next_action(5_000), ("hold", "canvas_invalidated"))
        self.assertEqual(s.next_action(500_000), ("hold", "canvas_invalidated"))


class N3ReceiveFramingTests(unittest.TestCase):
    """The shared fixture. The Host's C# assembler runs these same cases via --selftest."""

    FIXTURE = ROOT / "tests/receive_assembler_cases.json"

    def test_every_shared_receive_case_agrees_with_the_fixture(self) -> None:
        cases = json.loads(self.FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 9)
        for case in cases:
            with self.subTest(case["name"]):
                assembler = activity_session.ReportAssembler()
                kinds, error = [], None
                try:
                    for chunk in case["chunks"]:
                        kinds += assembler.feed(bytes.fromhex(chunk))
                except activity_session.ReportFramingError as exc:
                    error = str(exc).split(" ")[0]
                self.assertEqual(kinds, case["expect_kinds"])
                self.assertEqual(error, case.get("expect_error"))

    def test_an_ack_is_only_our_exact_wrapped_shape(self) -> None:
        from host.ditoo_candidate_codec import encode_candidate_normal
        self.assertEqual(activity_session.classify_report(
            encode_candidate_normal(0x04, bytes([0x44, 0x55, 0x12]))), "ack")
        # M7's unsolicited reports share the wrapper but not the command.
        for inner in (0x46, 0xBD, 0x09):
            self.assertEqual(activity_session.classify_report(
                encode_candidate_normal(0x04, bytes([inner, 0x55, 0x01]))), "state_report")

    def test_the_ack_payload_byte_is_never_validated_as_a_constant(self) -> None:
        from host.ditoo_candidate_codec import encode_candidate_normal
        for payload in (0x12, 0x75, 0xF0, 0xE5, 0x33, 0x00):
            self.assertEqual(activity_session.classify_report(
                encode_candidate_normal(0x04, bytes([0x44, 0x55, payload]))), "ack")


class ProductRuntimeTests(unittest.TestCase):
    def _policy_raw(self, authorized: bool = False) -> dict:
        scope = ("Persistent unattended MCP dashboard on exact Ditoo 11:75:58:CE:DE:C7; "
                 "automatic reconnect; reclaim MCP screen after stock takeover; typed activity-session only; "
                 "no raw send, target override, firmware, or generic Bluetooth surface.")
        return {
            "schema_version": 1,
            "product_id": product_runtime.PRODUCT_ID,
            "target": {"exact_unit_id": activity_session.EXACT_UNIT_ID,
                       "installed_firmware": activity_session.INSTALLED_FIRMWARE},
            "build": {"code_sha256": product_runtime.runtime_hashes(),
                      "host_dll_sha256": activity_session.sha256_file(activity_session.HOST_BUILD_DLL)},
            "session": {"lifetime_seconds": 60, "min_frame_interval_ms": 150,
                        "poll_interval_ms": 50, "pulse_freshness_seconds": 30,
                        "max_frames": 401, "max_tx_bytes": 81403},
            "behavior": {"automatic_reconnect": True, "reclaim_on_canvas_invalidated": True,
                         "raw_send_enabled": False, "target_override_enabled": False,
                         "start_at_windows_logon": True,
                         "reconnect_backoff_seconds": [1, 2, 5, 10, 30]},
            "authority": {"persistent_runtime_authorized": authorized, "revoked": False,
                          "granted_by": "operator" if authorized else None,
                          "grant_text": "Grant OPENDITOO-PRODUCT-RUNTIME-001" if authorized else None,
                          "grant_scope_requested": scope,
                          "grant_scope": scope if authorized else None},
        }

    def test_product_policy_is_fail_closed_until_persistent_authority_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(self._policy_raw(False)), encoding="utf-8")
            reviewed = product_runtime.load_policy(path, require_authority=False)
            self.assertEqual(reviewed.product_id, product_runtime.PRODUCT_ID)
            self.assertIn("PRODUCT_AUTHORITY_MISSING", product_runtime.authority_blockers(path))
            with self.assertRaises(product_runtime.ProductPolicyError) as blocked:
                product_runtime.load_policy(path, require_authority=True)
            self.assertEqual(blocked.exception.code, "PRODUCT_AUTHORITY_MISSING")
            path.write_text(json.dumps(self._policy_raw(True)), encoding="utf-8")
            armed = product_runtime.load_policy(path, require_authority=True)
            self.assertTrue(armed.automatic_reconnect)
            self.assertTrue(armed.reclaim_on_canvas_invalidated)

    def test_product_policy_cannot_change_target_or_enable_raw_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            raw = self._policy_raw(True)
            raw["target"]["exact_unit_id"] = "00:00:00:00:00:00"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(product_runtime.ProductPolicyError) as wrong_target:
                product_runtime.load_policy(path)
            self.assertEqual(wrong_target.exception.code, "PRODUCT_TARGET_MISMATCH")
            raw = self._policy_raw(True)
            raw["behavior"]["raw_send_enabled"] = True
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(product_runtime.ProductPolicyError) as raw_send:
                product_runtime.load_policy(path)
            self.assertEqual(raw_send.exception.code, "PRODUCT_RAW_SEND_FORBIDDEN")

    def test_supervisor_reclaims_immediately_but_backs_off_on_transport_failure(self) -> None:
        policy = product_runtime.ProductPolicy(
            path=Path("policy.json"), product_id=product_runtime.PRODUCT_ID,
            session_lifetime_seconds=60, min_frame_interval_ms=150, poll_interval_ms=50,
            pulse_freshness_seconds=30, max_frames_per_session=401,
            max_tx_bytes_per_session=81403, reconnect_backoff_seconds=(1, 2, 5, 10, 30),
            reclaim_on_canvas_invalidated=True, automatic_reconnect=True,
            start_at_windows_logon=True, code_hashes={}, host_build_sha256="0" * 64,
            authority_grant_text="Grant OPENDITOO-PRODUCT-RUNTIME-001")
        clock = {"s": 0.0}
        starts = []
        transports = [
            activity_session.FakeSessionTransport(reports={1: [{"kind": "session_ended",
                "reason": "canvas_invalidated", "outcome": "stopped_yielded_to_stock"}]}),
            activity_session.FakeSessionTransport(fail_on_frame=1),
            activity_session.FakeSessionTransport(),
        ]

        def factory():
            starts.append(clock["s"])
            return transports[len(starts) - 1]

        class StaticRenderer:
            def __call__(self, _now):
                return bytes([0, 255, 0]) * 256, False
            def frame_sent(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            result = product_runtime.run_product(
                policy, factory, max_sessions=3,
                config={"poll_seconds": 2.0, "sources": {}},
                activity_state=mcp_activity.blank_state(),
                state_file=Path(tmp) / "state.json",
                renderer_factory=lambda _c, _s, _m: StaticRenderer(),
                waiting_collector=lambda _c, _s: None,
                monotonic=lambda: clock["s"],
                sleep=lambda sec: clock.__setitem__("s", clock["s"] + sec),
            )
        self.assertEqual(result["reclaims"], 1)
        self.assertEqual(result["reconnects"], 1)
        self.assertEqual(result["connected_sessions"], 2)
        self.assertLess(starts[1] - starts[0], 1.0, msg="button takeover should reclaim without disconnect backoff")
        self.assertGreaterEqual(starts[2] - starts[1], 1.0, msg="transport failure must use bounded backoff")
        self.assertEqual(result["status"], "stopped")

    def test_run_session_honors_supervisor_stop_and_closes_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            raw = _valid_manifest()
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = activity_session.load_session_manifest(path)
            transport = activity_session.FakeSessionTransport()
            clock = {"ms": 0}
            result = activity_session.run_session(
                manifest, transport, lambda _now: (bytes([0, 255, 0]) * 256, False),
                lambda: clock["ms"],
                lambda ms: clock.__setitem__("ms", clock["ms"] + ms),
                stop_requested=lambda: clock["ms"] >= 200,
            )
            self.assertEqual(result["terminal_reason"], "operator_stop")
            self.assertEqual(result["outcome"], "stopped_clean")
            self.assertEqual(transport.closed_reason, "operator_stop")


class ProductRuntimeV2Tests(unittest.TestCase):
    def _policy_raw(self, authorized: bool = False) -> dict:
        raw = json.loads((ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-002.json").read_text(encoding="utf-8"))
        raw["build"]["code_sha256"] = product_runtime_v2.runtime_hashes()
        if authorized:
            scope = raw["authority"]["grant_scope_requested"]
            raw["authority"].update({
                "persistent_runtime_authorized": True,
                "granted_by": "operator",
                "grant_text": "Grant OPENDITOO-PRODUCT-RUNTIME-002",
                "grant_scope": scope,
            })
        return raw

    def test_runtime_001_source_remains_hash_stable_while_002_is_side_by_side(self) -> None:
        historical = json.loads((ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-001.json").read_text(encoding="utf-8"))
        self.assertEqual(historical["build"]["code_sha256"], product_runtime.runtime_hashes())
        self.assertFalse(historical["authority"]["persistent_runtime_authorized"])

    def test_runtime_002_policy_is_disabled_and_hash_complete(self) -> None:
        path = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-002.json"
        reviewed = product_runtime_v2.load_policy(path, require_authority=False)
        self.assertEqual(reviewed.product_id, product_runtime_v2.PRODUCT_ID)
        self.assertIn("PRODUCT_AUTHORITY_MISSING", product_runtime_v2.authority_blockers(path))
        with self.assertRaises(product_runtime_v2.ProductPolicyError) as blocked:
            product_runtime_v2.load_policy(path, require_authority=True)
        self.assertEqual(blocked.exception.code, "PRODUCT_AUTHORITY_MISSING")

    def test_observed_transport_reports_open_and_acks_without_changing_transport(self) -> None:
        events = []
        inner = activity_session.FakeSessionTransport()
        observed = product_runtime_v2.ObservedSessionTransport(
            inner,
            on_open=lambda opened: events.append(("open", opened["sessionId"])),
            on_frame=lambda ack, count: events.append(("ack", count, ack["ackPayloadHex"])),
        )
        policy = product_runtime_v2.load_policy(
            self._write_policy(self._policy_raw(True)), require_authority=True)
        manifest = product_runtime_v2.product_session_manifest(policy, "TELEMETRY-TEST")
        opened = observed.open(manifest)
        ack = observed.send_frame(bytes([0, 255, 0]) * 256, "0" * 64)
        observed.close("done")
        self.assertEqual(opened["sessionId"], "fake")
        self.assertEqual(ack["frame"], 1)
        self.assertEqual(events, [("open", "fake"), ("ack", 1, "0x00")])
        self.assertEqual(len(inner.frames), 1)
        self.assertEqual(inner.closed_reason, "done")

    def _write_policy(self, raw: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        try:
            json.dump(raw, tmp)
            tmp.close()
            return Path(tmp.name)
        finally:
            pass

    def test_runtime_002_successful_session_clears_stale_error_and_records_ack_time(self) -> None:
        raw = self._policy_raw(True)
        path = self._write_policy(raw)
        policy = product_runtime_v2.load_policy(path, require_authority=True)
        clock = {"s": 0.0}
        transports = [
            activity_session.FakeSessionTransport(fail_on_frame=1),
            activity_session.FakeSessionTransport(),
        ]
        starts = []
        def factory():
            starts.append(clock["s"])
            return transports[len(starts)-1]
        class StaticRenderer:
            def __call__(self, _now):
                return bytes([0, 255, 0]) * 256, False
            def frame_sent(self):
                pass
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "state.json"
            result = product_runtime_v2.run_product(
                policy, factory, max_sessions=2,
                config={"poll_seconds": 2.0, "sources": {}},
                activity_state=mcp_activity.blank_state(), state_file=state_file,
                renderer_factory=lambda _c, _s, _m: StaticRenderer(),
                waiting_collector=lambda _c, _s: None,
                monotonic=lambda: clock["s"],
                sleep=lambda sec: clock.__setitem__("s", clock["s"] + sec),
            )
        self.assertEqual(result["reconnects"], 1)
        self.assertEqual(result["connected_sessions"], 1)
        self.assertIsNone(result["last_error"])
        self.assertIsNotNone(result["last_frame_acked_at"])
        self.assertGreaterEqual(starts[1]-starts[0], 1.0)


class ProductInstallationBoundaryTests(unittest.TestCase):
    def test_committed_product_policy_is_disabled_but_hash_complete(self) -> None:
        path = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-001.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(raw["authority"]["persistent_runtime_authorized"])
        self.assertIsNone(raw["authority"]["grant_scope"])
        self.assertEqual(raw["target"]["exact_unit_id"], activity_session.EXACT_UNIT_ID)
        self.assertFalse(raw["behavior"]["raw_send_enabled"])
        self.assertFalse(raw["behavior"]["target_override_enabled"])
        reviewed = product_runtime.load_policy(path, require_authority=False)
        self.assertTrue(reviewed.automatic_reconnect)
        self.assertTrue(reviewed.reclaim_on_canvas_invalidated)
        self.assertIn("PRODUCT_AUTHORITY_MISSING", product_runtime.authority_blockers(path))

    def test_runtime_002_committed_template_is_disabled_and_hash_complete(self) -> None:
        path = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-002.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw["runtime_revision"], 2)
        self.assertFalse(raw["authority"]["persistent_runtime_authorized"])
        self.assertIsNone(raw["authority"]["grant_scope"])
        reviewed = product_runtime_v2.load_policy(path, require_authority=False)
        self.assertTrue(reviewed.automatic_reconnect)
        self.assertTrue(reviewed.reclaim_on_canvas_invalidated)

    def test_product_systemd_service_is_narrow_and_restartable(self) -> None:
        unit = (ROOT / "runtime/wsl/openditoo-product.service").read_text(encoding="utf-8")
        exec_lines = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
        self.assertEqual(len(exec_lines), 1)
        self.assertIn("product-runtime", exec_lines[0])
        self.assertIn(".openditoo-local/product-runtime-policy.json", exec_lines[0])
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("KillSignal=SIGTERM", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("UMask=0077", unit)
        self.assertFalse(any(line.strip().startswith("PrivateTmp=")
                             for line in unit.splitlines()))
        for forbidden in ("image-show", "sequence-run", "send_hex", "packetHex", "--target"):
            self.assertNotIn(forbidden, exec_lines[0])

    def test_wsl_product_installer_is_transactional_and_restores_collector(self) -> None:
        script = (ROOT / "runtime/wsl/install_openditoo_product.sh").read_text(encoding="utf-8")
        self.assertIn('systemctl --user disable --now "$COLLECT_TIMER"', script)
        self.assertIn('restore_collector', script)
        self.assertIn('--prepare)', script)
        self.assertIn('--rollback)', script)
        self.assertIn('--uninstall)', script)
        prepare = script[script.index('--prepare)'):script.index('--start)')]
        self.assertIn('systemctl --user enable "$PRODUCT_SERVICE"', prepare)
        self.assertNotIn('systemctl --user start "$PRODUCT_SERVICE"', prepare,
                         msg="prepare must perform zero product transmission")
        uninstall = script[script.index('--uninstall)'):]
        self.assertIn("persistent_runtime_authorized", uninstall)
        self.assertIn("revoked", uninstall)

    def test_windows_bootstrap_owns_only_its_task_and_preserves_host_and_opentivoo(self) -> None:
        ps = (ROOT / "runtime/windows/install_openditoo_product_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn("$TaskName = 'OpenDitoo Product Runtime'", ps)
        self.assertIn("$HostTaskName = 'OpenDitoo Day1 Host'", ps)
        self.assertIn("$OpenTivooTaskName = 'OpenTivoo Product Runtime'", ps)
        self.assertIn("New-ScheduledTaskTrigger -AtLogOn", ps)
        self.assertIn("-StartWhenAvailable", ps)
        self.assertIn("Invoke-WslProduct '--prepare'", ps)
        self.assertIn("Invoke-WslProduct '--rollback'", ps)
        self.assertIn("Start-ScheduledTask -TaskName $TaskName", ps)
        self.assertNotIn("Stop-ScheduledTask -TaskName $HostTaskName", ps)
        self.assertNotIn("Unregister-ScheduledTask -TaskName $HostTaskName", ps)
        self.assertNotIn("Stop-ScheduledTask -TaskName $OpenTivooTaskName", ps)
        self.assertNotIn("Unregister-ScheduledTask -TaskName $OpenTivooTaskName", ps)


class N3SessionRunTests(unittest.TestCase):
    def _manifest(self, tmp: str, **overrides):
        path = Path(tmp) / "m.json"
        path.write_text(json.dumps(_valid_manifest(**overrides)), encoding="utf-8")
        return activity_session.load_session_manifest(path)

    def _run(self, frames, transport=None, **overrides):
        """Drive a fixed list of rendered frames on a fake clock and fake transport."""
        session = {**_valid_manifest()["session"]}
        session.update(overrides.pop("session", {}))
        poll_ms = session["poll_interval_ms"]
        # Cover every scripted tick, then let the next loop observe the lifetime bound.
        session["lifetime_seconds"] = max(1, (len(frames) * poll_ms + 999) // 1000)
        overrides["session"] = session
        cap = session["lifetime_seconds"] * 1000 // session["min_frame_interval_ms"] + 1
        overrides.setdefault("budgets", {**_valid_manifest()["budgets"], "max_frames": min(cap, 500),
                                         "max_application_packets": min(cap, 500) * 3})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(tmp, **overrides)
            transport = transport or activity_session.FakeSessionTransport()
            clock = {"ms": 0}
            index = {"i": 0}

            def render(_now):
                frame = frames[min(index["i"], len(frames) - 1)]
                index["i"] += 1
                return frame if isinstance(frame, tuple) else (frame, False)

            result = activity_session.run_session(
                manifest, transport, render, lambda: clock["ms"],
                lambda ms: clock.__setitem__("ms", clock["ms"] + ms),
                max_iterations=len(frames) + 8)
            return result, transport

    RED = bytes([255, 0, 0]) * 256
    BLUE = bytes([0, 0, 255]) * 256

    def test_an_unchanged_session_dispatches_exactly_one_frame(self) -> None:
        result, transport = self._run([self.RED] * 40)
        self.assertEqual(len(transport.frames), 1)
        self.assertEqual(result["frames_sent"], 1)
        self.assertGreater(result["holds"]["unchanged"], 20)

    def test_an_alternating_scene_is_paced_by_the_product_interval(self) -> None:
        result, transport = self._run(
            [self.RED, self.BLUE] * 20,
            **{"session": {**_valid_manifest()["session"], "poll_interval_ms": 100}})
        # 40 render ticks at 100 ms cannot admit more frame starts than 150 ms allows.
        self.assertLessEqual(len(transport.frames), 4_000 // 150 + 1)
        self.assertIn("pacing", result["holds"])

    def test_status_transition_acceptance_dispatches_only_four_changed_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(tmp,
                **{"acceptance_profile": activity_session.STATUS_TRANSITION_ACCEPTANCE_PROFILE,
                   "session": {**_valid_manifest()["session"], "lifetime_seconds": 15,
                               "poll_interval_ms": 50},
                   "budgets": {**_valid_manifest()["budgets"], "max_frames": 8,
                               "max_application_packets": 24, "max_tx_bytes": 8 * 203}})
            transport = activity_session.FakeSessionTransport()
            renderer = activity_session.StatusTransitionAcceptanceRenderer()
            clock = {"ms": 0}
            result = activity_session.run_session(
                manifest, transport, renderer, lambda: clock["ms"],
                lambda ms: clock.__setitem__("ms", clock["ms"] + ms),
                max_iterations=400)
            self.assertEqual(result["outcome"], "stopped_clean")
            self.assertEqual(result["terminal_reason"], "lifetime_expired")
            self.assertEqual(result["frames_sent"], 4)
            self.assertEqual(len(transport.frames), 4)
            self.assertGreater(result["holds"].get("unchanged", 0), 200)

    def test_live_dashboard_adds_cross_process_pacing_headroom_above_the_host_floor(self) -> None:
        # 003 proved that dispatching exactly at the Host's 150 ms arrival floor can race:
        # variable HTTP latency made the second request arrive too soon and the Host 429'd it.
        # The product client therefore schedules at 200 ms while the Host still enforces 150 ms.
        self.assertEqual(activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS, 150)
        self.assertEqual(activity_session.MCP_CLIENT_FRAME_INTERVAL_MS, 200)
        self.assertGreater(activity_session.MCP_CLIENT_FRAME_INTERVAL_MS,
                           activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS)

    def test_slow_source_collection_cannot_backdate_the_frame_start(self) -> None:
        # 003/004 exposed this exact race. The tick timestamp was captured before render;
        # the live renderer may spend hundreds of ms collecting remote activity sources.
        # A frame must be paced from its actual dispatch time, not that stale tick start.
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(tmp,
                **{"session": {**_valid_manifest()["session"], "lifetime_seconds": 2,
                               "poll_interval_ms": 50},
                   "budgets": {**_valid_manifest()["budgets"], "max_frames": 11,
                               "max_application_packets": 33}})
            clock = {"ms": 0}
            starts = []

            class RecordingFake(activity_session.FakeSessionTransport):
                def send_frame(inner_self, rgb, expected_packet_sha256):
                    starts.append(clock["ms"])
                    return super().send_frame(rgb, expected_packet_sha256)

            frames = [self.RED, self.BLUE] * 12
            index = {"i": 0}
            def render(_now):
                # First source collection is expensive, matching the real remote probe.
                if index["i"] == 0:
                    clock["ms"] += 350
                frame = frames[index["i"] % len(frames)]
                index["i"] += 1
                return frame, False

            activity_session.run_session(
                manifest, RecordingFake(), render, lambda: clock["ms"],
                lambda ms: clock.__setitem__("ms", clock["ms"] + ms), max_iterations=20)
            self.assertGreaterEqual(len(starts), 2)
            self.assertEqual(starts[0], 350)
            self.assertGreaterEqual(starts[1] - starts[0],
                                    activity_session.MCP_CLIENT_FRAME_INTERVAL_MS)

    def test_transport_time_consumes_the_tick_budget_instead_of_adding_to_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._manifest(tmp,
                **{"session": {**_valid_manifest()["session"], "lifetime_seconds": 1},
                   "budgets": {**_valid_manifest()["budgets"], "max_frames": 7,
                               "max_application_packets": 21}})
            clock = {"ms": 0}
            starts = []

            class SlowFake(activity_session.FakeSessionTransport):
                def send_frame(inner_self, rgb, expected_packet_sha256):
                    starts.append(clock["ms"])
                    clock["ms"] += 70  # stand in for HTTP + Bluetooth send/ACK work
                    return super().send_frame(rgb, expected_packet_sha256)

            index = {"i": 0}
            frames = [self.RED, self.BLUE] * 4
            def render(_now):
                frame = frames[index["i"] % len(frames)]
                index["i"] += 1
                return frame, False

            # A 50 ms render tick plus the 200 ms MCP dispatch cadence keeps the intended
            # 0/200/400/... frame starts even though each send/ACK consumes 70 ms.
            manifest = dataclasses.replace(manifest, poll_interval_ms=50)
            activity_session.run_session(
                manifest, SlowFake(), render, lambda: clock["ms"],
                lambda ms: clock.__setitem__("ms", clock["ms"] + ms), max_iterations=24)
            self.assertEqual(starts[:4], [0, 200, 400, 600])

    def test_an_unsolicited_state_report_stops_the_session_and_yields(self) -> None:
        transport = activity_session.FakeSessionTransport(
            reports={1: [{"kind": "state_report", "inner": "0x46"}]})
        result, transport = self._run([self.RED, self.BLUE] * 10, transport=transport)
        self.assertEqual(result["terminal_reason"], "canvas_invalidated")
        self.assertEqual(result["outcome"], "stopped_yielded_to_stock")
        self.assertEqual(result["display_state"], "unknown_not_ours")
        self.assertEqual(len(transport.frames), 1)  # nothing after the takeover
        self.assertEqual(transport.closed_reason, "canvas_invalidated")

    def test_a_transport_fault_stops_sending_with_an_honestly_unknown_outcome(self) -> None:
        transport = activity_session.FakeSessionTransport(fail_on_frame=2)
        result, transport = self._run([self.RED, self.BLUE] * 10, transport=transport)
        self.assertEqual(result["terminal_reason"], "transport_fault")
        self.assertEqual(result["outcome"], "unknown")
        self.assertEqual(len(transport.frames), 1)  # no resend of the frame that failed
        self.assertTrue(transport.closed_reason)

    def test_the_frame_budget_stops_the_session_before_it_is_exceeded(self) -> None:
        result, transport = self._run(
            [self.RED, self.BLUE] * 40,
            **{"budgets": {**_valid_manifest()["budgets"], "max_frames": 3,
                           "max_application_packets": 9}})
        self.assertEqual(result["terminal_reason"], "budget_exhausted")
        self.assertLessEqual(len(transport.frames), 3)

    def test_a_clean_run_ends_at_its_lifetime_with_a_terminal_record(self) -> None:
        result, _ = self._run([self.RED] * 5)
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertEqual(result["terminal_reason"], "lifetime_expired")
        self.assertEqual(result["packets_sent"], result["frames_sent"] * 3)

    def test_a_source_failure_renders_but_never_stops_the_display(self) -> None:
        # An unreadable source is an unavailable indicator, not a Bluetooth fault.
        state = mcp_activity.blank_state()
        state["sources"]["wsl_mcp"]["source_health"] = "unavailable"
        state["sources"]["wsl_mcp"]["error_code"] = "SOURCE_READ_FAILED"
        unavailable = activity_render.render_rgb888(state)
        result, transport = self._run([self.RED] + [unavailable] * 20)
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertEqual(len(transport.frames), 2)


class N5PostTrialRegressionTests(unittest.TestCase):
    """Pinned from the OPENDITOO-M9-ACTIVATION-001 trial. Both were real failures."""

    def test_a_quiet_change_only_session_is_not_mistaken_for_a_dead_worker(self) -> None:
        # The trial ended at 30.4 s with reason `worker_silent` because liveness was
        # inferred from FRAMES, and a change-only display legitimately sends none.
        # Liveness is now a heartbeat that performs no device I/O.
        host = (HOST_DIR / "ActivitySessionHost.cs").read_text(encoding="utf-8")
        self.assertIn("internal static object Heartbeat(string sessionId)", host)
        self.assertIn("lastWorkerContact = DateTimeOffset.UtcNow;", host)
        program = (HOST_DIR / "Program.cs").read_text(encoding="utf-8")
        self.assertIn('app.MapPost("/v1/session/heartbeat"', program)
        heartbeat = program[program.index('app.MapPost("/v1/session/heartbeat"'):]
        heartbeat = heartbeat[:heartbeat.index("app.MapPost", 10)]
        self.assertIn("deviceIo = false", heartbeat)
        for forbidden in ("SendFrame", "BuildTransaction", "DitooLink.Connect"):
            self.assertNotIn(forbidden, heartbeat, msg="a heartbeat must never touch the device")

    def test_the_worker_learns_a_session_ended_without_having_to_send(self) -> None:
        # In the trial the worker polled for 127 s believing the display was live,
        # because only a send revealed the state.
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index("    def poll_reports("):cli.index("    def close(")]
        self.assertIn("SESSION_HEARTBEAT_URL", block)
        self.assertIn('"kind": "session_ended"', block)
        self.assertIn("terminalReason", block)

    def test_a_host_terminal_is_adopted_not_reported_as_an_inferred_fault(self) -> None:
        manifest_dir = Path(tempfile.mkdtemp())
        path = manifest_dir / "m.json"
        path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
        manifest = activity_session.load_session_manifest(path)

        class _EndsItself:
            def __init__(self) -> None:
                self.frames, self.closed_reason, self.polls = [], None, 0

            def open(self, _manifest): return {"sessionId": "x"}

            def send_frame(self, rgb, sha):
                self.frames.append(sha)
                return {"ackPayloadHex": "0x01"}

            def poll_reports(self):
                self.polls += 1
                if self.polls < 3:
                    return []
                return [{"kind": "session_ended", "reason": "worker_silent",
                         "outcome": "stopped_clean", "display_state": "ours_last_acked"}]

            def close(self, reason): self.closed_reason = reason

        transport = _EndsItself()
        clock = {"ms": 0}
        result = activity_session.run_session(
            manifest, transport, lambda _n: (bytes([1, 2, 3]) * 256, False),
            lambda: clock["ms"], lambda ms: clock.__setitem__("ms", clock["ms"] + ms),
            max_iterations=20)
        self.assertEqual(result["terminal_reason"], "worker_silent")
        self.assertEqual(result["outcome"], "stopped_clean")   # not an inferred fault
        self.assertEqual(len(transport.frames), 1)

    def test_a_response_too_large_to_read_is_not_reported_as_a_dead_host(self) -> None:
        # A 512-frame sequence returns ~90 KB of per-frame timings, ACKs and hashes. The
        # old fixed 64 KB read truncated it, json.loads raised, and the caller reported
        # HOST_UNAVAILABLE -- a fully successful run misreported as a transport failure.
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        self.assertIn("MAX_RESPONSE_BYTES", cli)
        self.assertIn("RESPONSE_TOO_LARGE", cli)
        block = cli[cli.index("def read_json_response("):cli.index("def emit(")]
        self.assertIn("MAX_RESPONSE_BYTES + 1", block, msg="must read one past the cap to detect overrun")
        # No response-body read may still use the old fixed cap.
        for line in cli.splitlines():
            if ".read(65537)" in line and "exc.read" not in line:
                self.fail(f"fixed 64 KB response read remains: {line.strip()}")

    def test_sequence_run_now_claims_authority_durably_before_dispatch(self) -> None:
        # The documented enforcement-depth gap: sequence-run used to check only the
        # manifest's own flags, so a crash mid-run left the authority looking re-usable
        # and consumption was manual bookkeeping after the fact.
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index("def sequence_run("):cli.index("def capture_parse(")]
        self.assertIn("activity_session.SessionClaim(experiment_id)", block)
        # Claimed before the Host is contacted, like the session route.
        self.assertLess(block.index("claim.claim("), block.index("urllib.request.urlopen"))
        # Every exit after the claim records a terminal, success or not.
        self.assertGreaterEqual(block.count("claim.finish("), 4)
        self.assertIn('claim.finish("stopped_clean"', block)
        self.assertIn('claim.finish("unknown"', block)

    def test_closing_an_already_terminated_session_is_not_an_error(self) -> None:
        # A session that runs its full lifetime is terminated Host-side a moment before
        # the worker calls close, so the 409 means "already closed cleanly". Recording it
        # as a close error made trial 002's clean run look ambiguous.
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index("    def close(self, reason: str) -> dict:"):]
        block = block[:block.index("\ndef ")]
        self.assertIn("exc.code == 409", block)
        self.assertIn('"already_terminated": True', block)

    def test_the_byte_budget_counts_the_whole_three_packet_group(self) -> None:
        # The trial recorded 132 bytes locally against the Host's 147: the local counter
        # omitted the two stock preambles while sharing the Host's ceiling.
        from host.ditoo_pixel_coloring import IMAGE_PREAMBLE_A, IMAGE_PREAMBLE_B
        manifest_dir = Path(tempfile.mkdtemp())
        path = manifest_dir / "m.json"
        path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
        manifest = activity_session.load_session_manifest(path)
        transport = activity_session.FakeSessionTransport()
        clock = {"ms": 0}
        rgb = bytes([9, 9, 9]) * 256
        activity_session.run_session(
            manifest, transport, lambda _n: (rgb, False), lambda: clock["ms"],
            lambda ms: clock.__setitem__("ms", clock["ms"] + ms), max_iterations=3)
        wire, _ = encode_rgb888_static_image(rgb)
        self.assertEqual(len(IMAGE_PREAMBLE_A) + len(IMAGE_PREAMBLE_B), 15)
        # The Host's own accounting, reproduced locally before the send is authorized.
        self.assertEqual(transport.tx_bytes, len(wire) + 15)


class N3HostBoundaryTests(unittest.TestCase):
    def test_the_host_enforces_the_same_pacing_floor_as_the_cli(self) -> None:
        src = (HOST_DIR / "ActivitySessionHost.cs").read_text(encoding="utf-8")
        self.assertIn(f"AcceptedMinFrameIntervalMs = {activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS};", src)
        self.assertIn(f"MaxLifetimeSeconds = {activity_session.MAX_SESSION_LIFETIME_SECONDS};", src)
        self.assertIn(f"MaxFrames = {activity_session.MAX_SESSION_FRAMES};", src)
        self.assertIn("SESSION_PACING_BELOW_ACCEPTED_CEILING", src)
        self.assertIn("ActivitySendSpacingMs = 10;", src)
        self.assertIn("SendFrameGroup(packets, null, framesSent, ActivitySendSpacingMs)", src)

    def test_the_host_bounds_a_session_without_the_worker(self) -> None:
        src = (HOST_DIR / "ActivitySessionHost.cs").read_text(encoding="utf-8")
        # A watchdog the caller cannot cancel is the whole point: a dropped HTTP client
        # must not leave a live link running to its own schedule.
        self.assertIn("watchdog = new Timer(_ => Tick()", src)
        self.assertIn('Terminate("lifetime_expired"', src)
        self.assertIn('Terminate("worker_silent"', src)
        self.assertIn("WorkerSilenceGraceMs", src)

    def test_the_host_consumes_the_experiment_id_before_it_opens_anything(self) -> None:
        src = (HOST_DIR / "ActivitySessionHost.cs").read_text(encoding="utf-8")
        claim = src.index('Append("open"')
        self.assertLess(claim, src.index("RequireAuthenticatedExactTarget"))
        self.assertLess(claim, src.index("DitooLink.Connect"))
        self.assertIn("AUTHORITY_ALREADY_CONSUMED", src)
        # A ledger line we cannot read must never be taken as "this id is free".
        self.assertIn("catch (JsonException)", src)

    def test_the_host_session_never_retries_reconnects_or_reclaims(self) -> None:
        src = (HOST_DIR / "ActivitySessionHost.cs").read_text(encoding="utf-8")
        self.assertIn("retry = false", src)
        self.assertIn("reconnect = false", src)
        self.assertIn("reclaim = false", src)
        for forbidden in ("Reconnect(", "Reopen(", "Resend(", "ReclaimScreen", "RestoreStock"):
            self.assertNotIn(forbidden, src)

    def test_a_takeover_ends_the_session_even_if_the_ack_arrived_first(self) -> None:
        transport = (HOST_DIR / "WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        self.assertIn("throw new DitooTakeoverException(report, ack is not null)", transport)
        report = (HOST_DIR / "DitooSessionReport.cs").read_text(encoding="utf-8")
        self.assertIn("AckAlreadyReceived", report)
        self.assertIn("NO_RECLAIM", report)

    def test_the_link_observes_the_device_while_idle(self) -> None:
        transport = (HOST_DIR / "WindowsRfcommStaticImageTransport.cs").read_text(encoding="utf-8")
        self.assertIn("internal List<DitooReport> PollIdle()", transport)
        # The link stays armed for read after send-readiness, so an unsolicited report
        # is seen even when the scene is unchanged and nothing is being sent.
        self.assertIn('SelectEvents(socketHandle, eventHandle, FdRead | FdClose, "IMAGE_RX")', transport)

    def test_one_gate_still_covers_show_sequence_and_session(self) -> None:
        program = (HOST_DIR / "Program.cs").read_text(encoding="utf-8")
        self.assertIn("ActivitySessionHost.OnRelease = () => imageGate.Release();", program)
        self.assertEqual(program.count("imageGate.Wait(0)"), 3)
        self.assertIn('"activity-session"', program)

    def test_the_session_cli_takes_no_free_form_operating_arguments(self) -> None:
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index('sub.add_parser("activity-session"'):cli.index('sub.add_parser("manifest-check"')]
        self.assertIn('p.add_argument("--manifest", required=True)', block)
        for forbidden in ("--lifetime", "--rate", "--interval", "--frames", "--target", "--force"):
            self.assertNotIn(forbidden, block)


class A1CollectionWorkerTests(unittest.TestCase):
    """The installed worker collects and can never transmit."""

    WSL = ROOT / "runtime/wsl"

    def test_the_unit_can_only_run_the_collect_command(self) -> None:
        unit = (self.WSL / "openditoo-collect.service").read_text(encoding="utf-8")
        exec_lines = [l for l in unit.splitlines() if l.startswith("ExecStart")]
        self.assertEqual(len(exec_lines), 1)
        self.assertIn("activity-status --collect", exec_lines[0])
        # Startup runs collection only. Nothing that reaches the device may appear.
        for forbidden in ("activity-session", "image-show", "sequence-run",
                          "image/show", "image/sequence", "session/open"):
            self.assertNotIn(forbidden, unit, msg=f"the worker must never be able to {forbidden}")

    def test_the_installer_refuses_to_install_a_transmitting_unit(self) -> None:
        script = (self.WSL / "install_openditoo_collector.sh").read_text(encoding="utf-8")
        self.assertIn("refusing to install", script)
        self.assertIn("collection must never transmit", script)
        for forbidden in ("activity-session", "image-show", "sequence-run"):
            self.assertIn(forbidden, script, msg="the installer's guard list must cover " + forbidden)

    def test_uninstall_preserves_evidence_and_opentivoo(self) -> None:
        script = (self.WSL / "install_openditoo_collector.sh").read_text(encoding="utf-8")
        block = script[script.index("--uninstall)"):script.index("install) ;;")]
        # It removes its own two units and nothing else.
        self.assertIn("rm -f \"$UNIT_DIR/$TIMER\" \"$UNIT_DIR/$SERVICE\"", block)
        for preserved in (".openditoo-local", "captures/", "OpenTivoo"):
            self.assertIn(preserved, block, msg=f"uninstall must state it preserves {preserved}")
        for forbidden in ("rm -rf", "session-claims", "session-ledger"):
            self.assertNotIn(forbidden, block,
                             msg="uninstalling a poller must never destroy evidence or un-consume authority")

    def test_private_tmp_stays_off_with_its_reason_recorded(self) -> None:
        # It reads as free hardening and is not: under PrivateTmp the unit gets its own
        # mount namespace, where ssh rejects /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf
        # -- a symlink into /usr/lib -- and both remote sources go unavailable.
        unit = (self.WSL / "openditoo-collect.service").read_text(encoding="utf-8")
        active = [l for l in unit.splitlines() if l.strip().startswith("PrivateTmp")]
        self.assertEqual(active, [], msg="PrivateTmp breaks ssh to the OptiPlex sources")
        self.assertIn("Bad owner or permissions", unit, msg="the reason must stay recorded")

    def test_the_timer_polls_without_claiming_it_cannot_miss_events(self) -> None:
        timer = (self.WSL / "openditoo-collect.timer").read_text(encoding="utf-8")
        self.assertIn("OnUnitActiveSec=", timer)
        self.assertIn("cursor-based", timer)


class N4SessionPreviewTests(unittest.TestCase):
    def test_the_offline_preview_dispatches_nothing_and_claims_no_authority(self) -> None:
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        block = cli[cli.index("def session_preview("):cli.index("def activity_session_run(")]
        self.assertIn("FakeSessionTransport", block)
        self.assertIn('"dispatched": False', block)
        self.assertNotIn("read_token", block)
        self.assertNotIn("SessionClaim", block)

    def test_the_scenario_fixtures_cover_change_idle_source_failure_and_takeover(self) -> None:
        bounded = json.loads((ROOT / "tests/session_scenario_bounded.json").read_text(encoding="utf-8"))
        takeover = json.loads((ROOT / "tests/session_scenario_takeover.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(bounded["steps"]), 12)
        self.assertTrue(any(step.get("pulses") for step in bounded["steps"]))
        self.assertTrue(any(view.get("source_health") == "unavailable"
                            for step in bounded["steps"] for view in step["sources"].values()))
        # The two differ only in whether someone touched the unit, so the difference in
        # outcome is attributable to the takeover and to nothing else.
        self.assertEqual(bounded["steps"], takeover["steps"])
        self.assertEqual(bounded["reports_after_frame"], {})
        self.assertTrue(takeover["reports_after_frame"])

    def test_the_activation_manifest_authority_is_fully_attributed(self) -> None:
        path = ROOT / "experiments/DAY1-M9-ACTIVATION-001.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        authority = manifest["authority"]
        self.assertEqual(authority["experiment_id"], manifest["experiment_id"])
        if authority["authorization_consumed"]:
            # Consumed: the record of what happened outranks re-runnability. It must be
            # disarmed, and it must not be quietly reported as a clean pass.
            self.assertFalse(authority["transmission_authorized"])
            result = manifest["result"]
            self.assertIn("acceptance", result)
            self.assertIn("visual_acceptance", result["acceptance"])
            self.assertIn("NOT TESTED", result["acceptance"]["stock_yield_acceptance"])
            self.assertTrue(result["root_cause"])
            return
        if authority["transmission_authorized"]:
            # Armed: every attribution field must be filled, and the scope must exclude
            # the things a bounded pass never implies.
            for field in ("granted_by", "grant_text", "expires_at", "grant_scope"):
                self.assertTrue(authority[field], msg=f"armed without {field}")
            self.assertEqual(activity_session.authority_blockers(path), [])
            for excluded in ("higher rate", "unattended", "second attempt"):
                self.assertIn(excluded, authority["grant_scope"].lower())
        else:
            self.assertIn("TRANSMISSION_AUTHORITY_MISSING", activity_session.authority_blockers(path))
        # Structurally complete either way: the grant is the only
        # thing missing, so nothing else has to be decided under time pressure later.
        reviewed = activity_session.load_session_manifest(path, require_authority=False,
                                                          verify_code_hashes=False)
        self.assertEqual(reviewed.min_frame_interval_ms,
                         activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS)
        self.assertEqual(reviewed.max_application_packets, reviewed.max_frames * 3)

    def test_the_activation_manifest_budgets_match_their_stated_derivation(self) -> None:
        manifest = json.loads((ROOT / "experiments/DAY1-M9-ACTIVATION-001.json")
                              .read_text(encoding="utf-8"))
        lifetime = manifest["session"]["lifetime_seconds"]
        interval = manifest["session"]["min_frame_interval_ms"]
        budgets = manifest["budgets"]
        self.assertEqual(budgets["max_frames"], lifetime * 1000 // interval + 1)
        # The per-frame figure is whatever the renderer's worst case was WHEN IT RAN.
        # The design has since changed, so this checks internal consistency, not the
        # current renderer -- a consumed manifest records history and must not be
        # retro-fitted to today's code. The live worst case is pinned separately in
        # M9RendererTests.test_every_state_and_activity_combination_encodes_for_the_device.
        self.assertEqual(budgets["max_tx_bytes"] % budgets["max_frames"], 0)
        per_frame = budgets["max_tx_bytes"] // budgets["max_frames"]
        self.assertEqual(per_frame, 191)
        self.assertIn("worst-case frame", budgets["derivation"])

    def test_an_armed_manifest_freezes_the_hash_of_the_installed_binary(self) -> None:
        # Build verified and installed identity verified are different claims. Once armed
        # they must agree, and the frozen hash must be the one actually installed --
        # two Release builds of identical source produced different hashes.
        manifest = json.loads((ROOT / "experiments/DAY1-M9-ACTIVATION-001.json")
                              .read_text(encoding="utf-8"))
        build = manifest["build"]
        self.assertIn("preconditions", manifest)
        if manifest["authority"]["authorization_consumed"]:
            # The frozen hashes record what RAN. They are history, not a live assertion,
            # so they are allowed to differ from the working tree afterwards.
            self.assertIn("code_hashes_note", build)
            self.assertEqual(build["host_dll_sha256"], build["installed_dll_sha256_verified"])
        elif manifest["authority"]["transmission_authorized"]:
            self.assertEqual(build["host_dll_sha256"], build["installed_dll_sha256_verified"])
            self.assertNotEqual(build["host_dll_sha256"], build["previous_installed_dll_sha256"])
            self.assertIn("HOST_SELFTEST_PASS", build["installed_identity_note"])
        else:
            self.assertIn("refresh_openditoo_day1_host.ps1 -Apply", build["installed_identity_note"])


class S1FrameStreamTests(unittest.TestCase):
    """The general bounded frame-streaming primitive, offline."""

    MANIFEST = ROOT / "experiments/DAY1-S1-STREAM-SWEEP-001.json"
    DEMO = ROOT / "examples/stream-demo/sweep-bar.rgb888"

    # -- frame sets ----------------------------------------------------

    def test_a_frame_blob_round_trips_and_a_misaligned_one_is_refused(self) -> None:
        frames = frame_stream.frames_from_source(self.DEMO)
        self.assertEqual(len(frames), 48)
        self.assertTrue(all(len(f) == frame_stream.FRAME_BYTES for f in frames))
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "short.rgb888"
            bad.write_bytes(b"\x00" * (frame_stream.FRAME_BYTES + 1))
            with self.assertRaises(frame_stream.SessionError) as caught:
                frame_stream.frames_from_source(bad)
            self.assertEqual(caught.exception.code, "STREAM_SOURCE_NOT_FRAME_ALIGNED")

    def test_a_png_directory_is_ordered_by_filename(self) -> None:
        from host.activity_render import write_previews
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "frames"
            for index, color in enumerate(((10, 0, 0), (0, 20, 0), (0, 0, 30))):
                write_previews(source, bytes(color) * 256, scale=1)
                (source / "activity-16.png").rename(source / f"{index:03d}.png")
            frames = frame_stream.frames_from_source(source)
        self.assertEqual([f[:3] for f in frames],
                         [bytes((10, 0, 0)), bytes((0, 20, 0)), bytes((0, 0, 30))])

    def test_an_over_full_palette_is_quantized_offline_not_at_send_time(self) -> None:
        # 256 distinct colours is one more than the stock-derived encoder can carry, and
        # any photographic 16x16 frame lands here.
        rgb = bytes(itertools.chain.from_iterable((i, 255 - i, (i * 7) % 256) for i in range(256)))
        with self.assertRaises(frame_stream.SessionError) as caught:
            frame_stream.build_frame_set([rgb])
        self.assertEqual(caught.exception.code, "STREAM_FRAME_NOT_ENCODABLE")
        reduced, colors = frame_stream.quantize_to_palette_limit(rgb)
        self.assertLessEqual(colors, frame_stream.MAX_PALETTE_COLORS)
        self.assertEqual(len(reduced), frame_stream.FRAME_BYTES)
        # Deterministic from the source bytes alone, and already-small frames are untouched.
        self.assertEqual(reduced, frame_stream.quantize_to_palette_limit(rgb)[0])
        flat = bytes((1, 2, 3)) * 256
        self.assertEqual(frame_stream.quantize_to_palette_limit(flat), (flat, 1))

    def test_worst_case_frame_bytes_include_both_stock_preambles(self) -> None:
        frame_set = frame_stream.build_frame_set(frame_stream.frames_from_source(self.DEMO))
        widest = max(len(encode_rgb888_static_image(f)[0]) for f in frame_set.frames)
        self.assertEqual(frame_set.max_frame_tx_bytes,
                         widest + len(IMAGE_PREAMBLE_A) + len(IMAGE_PREAMBLE_B))

    # -- playback ------------------------------------------------------

    def _renderer(self, count: int = 3, interval: int = 200, loop: bool = False):
        frames = [bytes((index + 1, 0, 0)) * 256 for index in range(count)]
        return frame_stream.FrameSetRenderer(frame_stream.build_frame_set(frames), interval, loop)

    def test_playback_follows_the_clock_and_holds_the_last_frame(self) -> None:
        renderer = self._renderer()
        self.assertEqual(renderer(0)[0][:1], b"\x01")
        self.assertEqual(renderer(199)[0][:1], b"\x01")
        self.assertEqual(renderer(200)[0][:1], b"\x02")
        # A slow transport drops frames rather than stretching the clip.
        self.assertEqual(renderer(400)[0][:1], b"\x03")
        self.assertEqual(renderer(5_000)[0][:1], b"\x03")

    def test_looping_playback_wraps(self) -> None:
        renderer = self._renderer(loop=True)
        self.assertEqual(renderer(600)[0][:1], b"\x01")
        self.assertEqual(renderer(800)[0][:1], b"\x02")

    def test_an_ack_advances_nothing_so_a_repeated_frame_cannot_stall_playback(self) -> None:
        # An ACK-gated cursor would deadlock on two identical consecutive frames: the
        # scheduler holds them as unchanged, so no ACK ever arrives to advance it.
        frames = [bytes((1, 0, 0)) * 256, bytes((1, 0, 0)) * 256, bytes((2, 0, 0)) * 256]
        renderer = frame_stream.FrameSetRenderer(frame_stream.build_frame_set(frames), 200)
        renderer(0)
        renderer.frame_sent()
        self.assertEqual(renderer(400)[0][:1], b"\x02")

    def test_no_frame_is_a_pulse_so_nothing_can_expire(self) -> None:
        self.assertFalse(self._renderer()(0)[1])

    # -- the reviewed manifest -----------------------------------------

    def _raw(self) -> dict:
        return json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def _load(self, mutate=None):
        data = self._raw()
        if mutate is not None:
            mutate(data)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return frame_stream.load_stream_manifest(path, require_authority=False)

    def _refuses(self, code: str, mutate) -> None:
        with self.assertRaises(frame_stream.SessionError) as caught:
            self._load(mutate)
        self.assertEqual(caught.exception.code, code)

    def test_the_committed_stream_manifest_reviews_but_is_not_authorized(self) -> None:
        manifest, frame_set, stream = self._load()
        self.assertEqual(manifest.experiment_id, "OPENDITOO-S1-STREAM-001")
        self.assertEqual(frame_set.count, stream["frame_count"])
        self.assertEqual(manifest.max_application_packets, manifest.max_frames * 3)
        self.assertIn("TRANSMISSION_AUTHORITY_MISSING",
                      frame_stream.authority_blockers(self.MANIFEST))
        with self.assertRaises(frame_stream.SessionError) as caught:
            frame_stream.load_stream_manifest(self.MANIFEST)
        self.assertEqual(caught.exception.code, "TRANSMISSION_AUTHORITY_MISSING")

    def test_the_declared_frame_set_must_be_the_one_on_disk(self) -> None:
        self._refuses("STREAM_FRAME_SET_HASH_DRIFT",
                      lambda d: d["stream"].__setitem__("frame_set_sha256", "0" * 64))
        self._refuses("STREAM_FRAME_COUNT_MISMATCH",
                      lambda d: d["stream"].__setitem__("frame_count", 47))
        self._refuses("STREAM_SOURCE_MISSING",
                      lambda d: d["stream"].__setitem__("frame_set_file", "examples/nope.rgb888"))

    def test_budgets_are_derived_from_the_content_and_the_lifetime(self) -> None:
        self._refuses("BUDGET_FRAMES_EXCEED_CONTENT",
                      lambda d: d["budgets"].update(max_frames=49, max_application_packets=147))
        self._refuses("BUDGET_FRAMES_BELOW_CONTENT",
                      lambda d: d["budgets"].update(max_frames=47, max_application_packets=141))
        self._refuses("BUDGET_TX_BYTES_NOT_DERIVED",
                      lambda d: d["budgets"].__setitem__("max_tx_bytes", 999_999))
        self._refuses("BUDGET_PACKETS_NOT_DERIVED",
                      lambda d: d["budgets"].__setitem__("max_application_packets", 48))
        self._refuses("BUDGET_CONNECTION_ATTEMPTS_INVALID",
                      lambda d: d["budgets"].__setitem__("connection_attempts", 2))

    def test_a_cadence_the_shared_runner_would_round_up_is_refused(self) -> None:
        # run_session dispatches no faster than MCP_CLIENT_FRAME_INTERVAL_MS, so a
        # manifest may not claim a rate it would not actually get.
        self._refuses("STREAM_PLAYBACK_INTERVAL_INVALID",
                      lambda d: d["stream"].__setitem__("playback_interval_ms", 150))
        self._refuses("SESSION_PACING_BELOW_ACCEPTED_CEILING",
                      lambda d: d["session"].__setitem__("min_frame_interval_ms", 149))

    def test_retry_reconnect_reclaim_and_replay_must_all_be_disabled(self) -> None:
        for field, code in (("automatic_retry", "SESSION_RETRY_NOT_DISABLED"),
                            ("automatic_reconnect", "SESSION_RECONNECT_NOT_DISABLED"),
                            ("stock_screen_reclaim", "SESSION_RECLAIM_NOT_DISABLED"),
                            ("replay_after_interruption", "SESSION_REPLAY_NOT_DISABLED")):
            self._refuses(code, lambda d, f=field: d["session"].__setitem__(f, True))

    def test_the_target_and_the_stream_code_identity_are_both_frozen(self) -> None:
        self._refuses("MANIFEST_TARGET_MISMATCH",
                      lambda d: d["target"].__setitem__("exact_unit_id", "11:75:58:C8:5E:FE"))
        self._refuses("BUILD_CODE_HASH_DRIFT",
                      lambda d: d["build"]["code_sha256"].__setitem__("encoder_sha256", "0" * 64))
        self._refuses("BUILD_CODE_HASHES_INCOMPLETE",
                      lambda d: d["build"]["code_sha256"].pop("frame_stream_sha256"))
        self._refuses("MANIFEST_KIND_MISMATCH", lambda d: d.__setitem__("kind", "activity"))
        self._refuses("AUTHORITY_EXPERIMENT_ID_MISMATCH",
                      lambda d: d["authority"].__setitem__("experiment_id", "SOMETHING-ELSE"))

    # -- the whole replayed stream -------------------------------------

    def test_the_offline_replay_sends_exactly_what_the_budget_states(self) -> None:
        manifest, frame_set, stream = self._load()
        clock = {"ms": 0}
        transport = activity_session.FakeSessionTransport()
        result = activity_session.run_session(
            manifest, transport, frame_stream.renderer_for(frame_set, stream),
            lambda: clock["ms"], lambda ms: clock.__setitem__("ms", clock["ms"] + max(ms, 1)),
            claim=None, max_iterations=manifest.lifetime_ms // manifest.poll_interval_ms + 8)
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertEqual(result["terminal_reason"], "lifetime_expired")
        self.assertEqual(result["frames_sent"], manifest.max_frames)
        self.assertEqual(result["packets_sent"], manifest.max_application_packets)
        self.assertEqual(result["tx_bytes_sent"], transport.tx_bytes)
        self.assertLessEqual(result["tx_bytes_sent"], manifest.max_tx_bytes)

    def test_a_transport_fault_mid_stream_is_unknown_and_never_resent(self) -> None:
        manifest, frame_set, stream = self._load()
        clock = {"ms": 0}
        transport = activity_session.FakeSessionTransport(fail_on_frame=5)
        result = activity_session.run_session(
            manifest, transport, frame_stream.renderer_for(frame_set, stream),
            lambda: clock["ms"], lambda ms: clock.__setitem__("ms", clock["ms"] + max(ms, 1)),
            claim=None, max_iterations=200)
        self.assertEqual((result["terminal_reason"], result["outcome"]), ("transport_fault", "unknown"))
        self.assertEqual(len(transport.frames), 4)

    # -- boundary ------------------------------------------------------

    def test_the_stream_surface_exposes_no_override_and_no_second_stack(self) -> None:
        cli = (ROOT / "cli/openditoo.py").read_text(encoding="utf-8")
        module = (ROOT / "host/frame_stream.py").read_text(encoding="utf-8")
        for forbidden in ("--target", "--mac", "--raw", "--hex-send", "--rate", "--fps",
                          "--frames", "--lifetime\"", "--no-authority", "--force"):
            self.assertNotIn(forbidden, cli, msg=f"stream CLI must not expose {forbidden}")
        # Live dispatch happens through the one existing typed session client only.
        self.assertIn("_HostSessionTransport(token)", cli)
        for forbidden in ("socket", "urllib", "http", "SESSION_FRAME_URL", "subprocess"):
            self.assertNotIn(forbidden, module,
                             msg=f"frame_stream must not reach the device itself: {forbidden}")
        for forbidden in ("def release", "def unclaim", "def reset", "os.remove", "os.unlink"):
            self.assertNotIn(forbidden, module)
