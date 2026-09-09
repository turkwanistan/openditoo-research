from __future__ import annotations

import binascii
import hashlib
from pathlib import Path
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
WIDTH = 16
HEIGHT = 16
RGB_BYTES = WIDTH * HEIGHT * 3


class Png16Error(ValueError):
    pass


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, row_bytes: int, bpp: int) -> list[bytes]:
    expected = HEIGHT * (row_bytes + 1)
    if len(raw) != expected:
        raise Png16Error(f"decompressed PNG size mismatch: expected {expected}, got {len(raw)}")
    rows: list[bytes] = []
    prior = bytearray(row_bytes)
    offset = 0
    for y in range(HEIGHT):
        filter_type = raw[offset]
        offset += 1
        source = raw[offset:offset + row_bytes]
        offset += row_bytes
        recon = bytearray(row_bytes)
        for x, value in enumerate(source):
            left = recon[x - bpp] if x >= bpp else 0
            up = prior[x]
            up_left = prior[x - bpp] if x >= bpp else 0
            if filter_type == 0:
                decoded = value
            elif filter_type == 1:
                decoded = (value + left) & 0xFF
            elif filter_type == 2:
                decoded = (value + up) & 0xFF
            elif filter_type == 3:
                decoded = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                decoded = (value + _paeth(left, up, up_left)) & 0xFF
            else:
                raise Png16Error(f"unsupported PNG filter type {filter_type} on row {y}")
            recon[x] = decoded
        rows.append(bytes(recon))
        prior = recon
    return rows


def _composite_black(channel: int, alpha: int) -> int:
    return (channel * alpha + 127) // 255


def decode_png16_rgb(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise Png16Error("input is not a PNG file")

    offset = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    transparency: bytes | None = None
    idat = bytearray()
    saw_iend = False

    while offset < len(data):
        if offset + 12 > len(data):
            raise Png16Error("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        crc_end = end + 4
        if crc_end > len(data):
            raise Png16Error("truncated PNG chunk")
        chunk_data = data[start:end]
        observed_crc = struct.unpack(">I", data[end:crc_end])[0]
        expected_crc = binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if observed_crc != expected_crc:
            raise Png16Error(f"PNG CRC mismatch in {chunk_type.decode('ascii', 'replace')}")
        offset = crc_end

        if chunk_type == b"IHDR":
            if ihdr is not None:
                raise Png16Error("multiple IHDR chunks")
            ihdr = chunk_data
        elif chunk_type == b"PLTE":
            palette = chunk_data
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            saw_iend = True
            break

    if ihdr is None or len(ihdr) != 13 or not saw_iend or not idat:
        raise Png16Error("PNG is missing required IHDR/IDAT/IEND data")

    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (width, height) != (WIDTH, HEIGHT):
        raise Png16Error(f"PNG must be exactly 16x16; got {width}x{height}")
    if bit_depth != 8:
        raise Png16Error(f"PNG must use 8-bit channels/indices; got bit depth {bit_depth}")
    if compression != 0 or filter_method != 0 or interlace != 0:
        raise Png16Error("PNG must use standard compression/filtering and be non-interlaced")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise Png16Error(f"unsupported PNG color type {color_type}")
    channels = channels_by_type[color_type]
    row_bytes = WIDTH * channels
    try:
        decompressed = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise Png16Error(f"invalid PNG compressed data: {exc}") from exc
    rows = _unfilter(decompressed, row_bytes, channels)

    palette_rgb: list[tuple[int, int, int]] = []
    if color_type == 3:
        if palette is None or not palette or len(palette) % 3:
            raise Png16Error("indexed PNG requires a valid PLTE chunk")
        if len(palette) > 256 * 3:
            raise Png16Error("PNG palette exceeds 256 colors")
        palette_rgb = [tuple(palette[i:i + 3]) for i in range(0, len(palette), 3)]  # type: ignore[misc]

    rgb = bytearray()
    for row in rows:
        for x in range(WIDTH):
            pos = x * channels
            if color_type == 0:
                gray = row[pos]
                alpha = 0 if transparency is not None and len(transparency) == 2 and gray == int.from_bytes(transparency, "big") else 255
                rgb.extend((_composite_black(gray, alpha),) * 3)
            elif color_type == 2:
                r, g, b = row[pos:pos + 3]
                alpha = 255
                if transparency is not None and len(transparency) == 6:
                    tr, tg, tb = struct.unpack(">HHH", transparency)
                    if (r, g, b) == (tr, tg, tb):
                        alpha = 0
                rgb.extend((_composite_black(r, alpha), _composite_black(g, alpha), _composite_black(b, alpha)))
            elif color_type == 3:
                index = row[pos]
                if index >= len(palette_rgb):
                    raise Png16Error(f"palette index {index} exceeds PLTE size")
                r, g, b = palette_rgb[index]
                alpha = transparency[index] if transparency is not None and index < len(transparency) else 255
                rgb.extend((_composite_black(r, alpha), _composite_black(g, alpha), _composite_black(b, alpha)))
            elif color_type == 4:
                gray, alpha = row[pos:pos + 2]
                value = _composite_black(gray, alpha)
                rgb.extend((value, value, value))
            else:  # color_type == 6
                r, g, b, alpha = row[pos:pos + 4]
                rgb.extend((_composite_black(r, alpha), _composite_black(g, alpha), _composite_black(b, alpha)))

    if len(rgb) != RGB_BYTES:
        raise Png16Error(f"decoded RGB size mismatch: {len(rgb)}")
    return bytes(rgb)


def png_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
