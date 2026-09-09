"""16x16 renderer for the three-MCP activity display.

Three fixed indicators, one per source, in horizontal bands separated by black
rows so no two icons touch. Age and health are separate dimensions: the age
field never hides an unavailable collector, and red is reserved for the error
state rather than for elapsed time.
"""
from __future__ import annotations

import binascii
from datetime import datetime, timedelta
from pathlib import Path
import struct
import zlib

from host.mcp_activity import SOURCE_IDS, parse_timestamp, utc_now

SIZE = 16
BLACK = (0, 0, 0)

# Band rows per source; rows 0, 5, 10 and 15 stay black separators.
BANDS = {"optiplex_mcp": 1, "optiplex_lab": 6, "wsl_mcp": 11}

GLYPH_COLUMNS = range(0, 4)
FIELD_COLUMNS = range(5, 14)
HEALTH_COLUMN = 15

IDENTITY_COLOR = {
    "optiplex_mcp": (0, 150, 255),
    "optiplex_lab": (190, 110, 255),
    "wsl_mcp": (255, 170, 40),
}

GLYPH = {
    "optiplex_mcp": ("1111", "1001", "1001", "1111"),   # server box
    "optiplex_lab": ("0110", "0110", "1001", "1111"),   # flask
    "wsl_mcp":      ("1001", "1001", "1011", "0110"),   # W
}

AGE_COLOR = {
    "new": (255, 255, 255),
    "recent": (0, 230, 70),
    "warm": (235, 200, 0),
    "idle": (35, 35, 55),
    "no_data": (70, 70, 70),
}

HEALTH_COLOR = {
    "healthy": BLACK,
    "stale": (255, 60, 0),
    "unavailable": (255, 0, 0),
    "unknown": (120, 120, 120),
}

RECENT_LIMIT = timedelta(minutes=5)
WARM_LIMIT = timedelta(minutes=20)


def age_category(last_activity_at: str | None, now: datetime) -> str:
    if not last_activity_at:
        return "no_data"
    age = now - parse_timestamp(last_activity_at)
    if age < timedelta(0):
        return "no_data"  # a future stamp is skew, not fresh activity
    if age < RECENT_LIMIT:
        return "recent"
    if age < WARM_LIMIT:
        return "warm"
    return "idle"


def describe(state: dict, now: datetime | None = None, pulses: set[str] | None = None) -> dict:
    now = now or utc_now()
    pulses = pulses or set()
    out = {}
    for source_id in SOURCE_IDS:
        source = state["sources"][source_id]
        category = "new" if source_id in pulses else age_category(source["last_activity_at"], now)
        health = source.get("source_health", "unknown")
        out[source_id] = {
            "age_category": category,
            "source_health": health if health in HEALTH_COLOR else "unknown",
            "last_activity_at": source["last_activity_at"],
            "last_observed_at": source["last_observed_at"],
            "last_outcome": source["last_outcome"],
            "history_complete": source["history_complete"],
            "error_code": source["error_code"],
        }
    return out


def render_rgb888(state: dict, now: datetime | None = None, pulses: set[str] | None = None) -> bytes:
    summary = describe(state, now, pulses)
    pixels = [BLACK] * (SIZE * SIZE)

    def put(x: int, y: int, color: tuple[int, int, int]) -> None:
        pixels[y * SIZE + x] = color

    for source_id, top in BANDS.items():
        view = summary[source_id]
        age = AGE_COLOR[view["age_category"]]
        health = HEALTH_COLOR[view["source_health"]]
        for row, bits in enumerate(GLYPH[source_id]):
            y = top + row
            for x in GLYPH_COLUMNS:
                if bits[x] == "1":
                    put(x, y, IDENTITY_COLOR[source_id])
            for x in FIELD_COLUMNS:
                if view["age_category"] == "no_data":
                    # explicit unknown pattern, not a dim "idle" lie
                    put(x, y, age if (x + y) % 2 == 0 else BLACK)
                else:
                    put(x, y, age)
            put(HEALTH_COLUMN, y, health)

    return b"".join(bytes(color) for color in pixels)


# --------------------------------------------------------------------------
# PNG output (stdlib only; nearest-neighbour enlargement for review)
# --------------------------------------------------------------------------

def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, rgb: bytes, width: int, height: int) -> None:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB888 buffer does not match the given geometry")
    stride = width * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def scale_nearest(rgb: bytes, factor: int) -> bytes:
    if factor < 1:
        raise ValueError("scale factor must be >= 1")
    out = bytearray()
    for y in range(SIZE):
        row = bytearray()
        for x in range(SIZE):
            offset = (y * SIZE + x) * 3
            row.extend(rgb[offset:offset + 3] * factor)
        out.extend(bytes(row) * factor)
    return bytes(out)


def write_previews(output_dir: Path, rgb: bytes, scale: int = 16) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exact = output_dir / "activity-16.png"
    large = output_dir / f"activity-{SIZE * scale}.png"
    write_png(exact, rgb, SIZE, SIZE)
    write_png(large, scale_nearest(rgb, scale), SIZE * scale, SIZE * scale)
    return {"exact_png": str(exact), "preview_png": str(large)}


LEGEND = {
    "bands": "rows 1-4 OptiPlex MCP (blue server glyph), rows 6-9 OptiPlex Lab (violet flask), rows 11-14 WSL MCP (amber W); rows 0/5/10/15 are black separators",
    "identity_columns": "0-3",
    "age_field_columns": "5-13",
    "health_column": "15",
    "age": {"new": "white pulse", "recent": "green, <5 min", "warm": "yellow, 5-20 min",
            "idle": "dim blue-grey, >=20 min", "no_data": "grey checkerboard, no reliable history"},
    "health": {"healthy": "black", "stale": "red-orange", "unavailable": "red", "unknown": "grey"},
}
