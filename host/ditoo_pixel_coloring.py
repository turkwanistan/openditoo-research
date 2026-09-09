from __future__ import annotations

import hashlib
import math

START = 0x01
END = 0x02
CMD_IMAGE = 0x44
CMD_DRAWING_PAD_CTRL = 0x58
CMD_IMAGE_PREAMBLE_A = 0x9F
CMD_EXTERN = 0xBD
IMAGE_PREAMBLE_A = bytes.fromhex("0103009fa20002")
IMAGE_PREAMBLE_B = bytes.fromhex("010400bd31f20002")


def build_packet(command: int, payload: bytes = b"") -> bytes:
    inner_length = len(payload) + 3
    body = inner_length.to_bytes(2, "little") + bytes((command,)) + payload
    checksum = sum(body) & 0xFFFF
    return bytes((START,)) + body + checksum.to_bytes(2, "little") + bytes((END,))


def pack_palette_indices_lsb(indices: list[int], bits_per_pixel: int) -> bytes:
    if len(indices) != 256:
        raise ValueError("Ditoo Day-1 static image requires exactly 256 row-major indices")
    if bits_per_pixel <= 0 or bits_per_pixel > 8:
        raise ValueError("invalid bits_per_pixel")
    bits: list[int] = []
    limit = 1 << bits_per_pixel
    for value in indices:
        if value < 0 or value >= limit:
            raise ValueError(f"palette index {value} does not fit in {bits_per_pixel} bits")
        for bit in range(bits_per_pixel):
            bits.append((value >> bit) & 1)
    while len(bits) % 8:
        bits.append(0)
    packed = bytearray()
    for offset in range(0, len(bits), 8):
        packed.append(sum(bits[offset + bit] << bit for bit in range(8)))
    return bytes(packed)


def encode_static_image(palette: list[tuple[int, int, int]], indices: list[int]) -> bytes:
    if not 1 <= len(palette) <= 255:
        raise ValueError("Day-1 encoder supports 1..255 palette colors")
    for color in palette:
        if len(color) != 3 or any(channel < 0 or channel > 255 for channel in color):
            raise ValueError(f"invalid RGB888 color {color!r}")
    bits_per_pixel = max(1, math.ceil(math.log2(len(palette))))
    pixel_data = pack_palette_indices_lsb(indices, bits_per_pixel)
    palette_data = b"".join(bytes(color) for color in palette)
    # Exact purchased-unit Pixel Coloring captures use:
    # 00 0A 0A 04 | AA | frameSizeLE | F4 01 00 | colorCount | palette | packed indices
    frame_size = 1 + 2 + 3 + 1 + len(palette_data) + len(pixel_data)
    payload = (
        bytes.fromhex("000a0a04")
        + bytes((0xAA,))
        + frame_size.to_bytes(2, "little")
        + bytes.fromhex("f40100")
        + bytes((len(palette),))
        + palette_data
        + pixel_data
    )
    return build_packet(CMD_IMAGE, payload)



def palette_and_indices_from_rgb888(rgb: bytes) -> tuple[list[tuple[int, int, int]], list[int]]:
    if len(rgb) != 16 * 16 * 3:
        raise ValueError(f"Ditoo static image requires exactly 768 RGB888 bytes; got {len(rgb)}")
    palette: list[tuple[int, int, int]] = []
    lookup: dict[tuple[int, int, int], int] = {}
    indices: list[int] = []
    for offset in range(0, len(rgb), 3):
        color = tuple(rgb[offset:offset + 3])
        index = lookup.get(color)
        if index is None:
            if len(palette) >= 255:
                raise ValueError("Ditoo static image supports at most 255 distinct RGB888 colors")
            index = len(palette)
            lookup[color] = index
            palette.append(color)
        indices.append(index)
    return palette, indices


def encode_rgb888_static_image(rgb: bytes) -> tuple[bytes, int]:
    palette, indices = palette_and_indices_from_rgb888(rgb)
    return encode_static_image(palette, indices), len(palette)

def diagnostic_frame() -> bytes:
    # Six RGB888 colors; exact 16x16 row-major geometry from Day-1 plan.
    palette = [
        (0, 0, 0),       # 0 black background
        (255, 0, 0),     # 1 red
        (0, 255, 0),     # 2 green
        (0, 0, 255),     # 3 blue
        (255, 255, 255), # 4 white
        (90, 90, 90),    # 5 dim gray
    ]
    indices = [0] * 256
    for index in (0x00, 0x01):
        indices[index] = 1
    for index in (0x0F, 0x1F, 0x2F):
        indices[index] = 2
    for index in (0xE0, 0xE1, 0xF0, 0xF1):
        indices[index] = 3
    indices[0xFF] = 4
    indices[0x77] = 5
    return encode_static_image(palette, indices)


def drawing_pad_packet(rgb: tuple[int, int, int], row_major_indices: list[int]) -> bytes:
    if not 1 <= len(row_major_indices) <= 255:
        raise ValueError("drawing-pad packet requires 1..255 indices")
    if any(index < 0 or index > 255 for index in row_major_indices):
        raise ValueError("drawing-pad index outside 0..255")
    if any(channel < 0 or channel > 255 for channel in rgb):
        raise ValueError("RGB channel outside 0..255")
    payload = bytes(rgb) + bytes((len(row_major_indices),)) + bytes(row_major_indices)
    return build_packet(CMD_DRAWING_PAD_CTRL, payload)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


DIAGNOSTIC_FRAME_SHA256 = "db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b"


def verify_frozen_diagnostic() -> None:
    wire = diagnostic_frame()
    if len(wire) != 132:
        raise RuntimeError(f"diagnostic wire length drifted: {len(wire)}")
    if sha256_hex(wire) != DIAGNOSTIC_FRAME_SHA256:
        raise RuntimeError("diagnostic wire hash drifted")
