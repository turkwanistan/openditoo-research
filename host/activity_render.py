"""16x16 renderer for the approved three-MCP activity page.

The layout is the operator-approved design: an activity crown across rows 0-2, identity
letters L / O / W on rows 5-9, and 5x5 mushroom / bunny / skull icons on rows 11-15, one
5-pixel column per source with x=15 spare.

Every pixel and colour comes from `host/activity_ui_data.py`, which is *derived* from the
approved mockups in `assets/ui/reference/` rather than transcribed. The offline suite
re-derives it and also re-renders each reference frame, so the mockups are executable
acceptance criteria: if a pixel moves, a test fails.

Status is one colour per source -- green under 5 minutes, yellow to 20, red beyond, grey
for no usable data. During activity that column's crown, letter and icon accent all take
the blue override together, then fall back to the status colour. See `LEGEND`.
"""
from __future__ import annotations

import binascii
from datetime import datetime, timedelta
from pathlib import Path
import struct
import zlib

from host.activity_ui_data import (CROWN, FIXED, OVERRIDE_RGB, ROLE_COLORS, ROLE_PIXELS,
                                   SIZE, SLOTS)
from host.mcp_activity import SOURCE_IDS, parse_timestamp, utc_now

BLACK = (0, 0, 0)
SLOT_WIDTH = 5

RECENT_LIMIT = timedelta(minutes=5)
WARM_LIMIT = timedelta(minutes=20)

# A source we could not read has no usable "last activity", so it renders grey rather
# than as a stale-but-fine colour. The approved spec merges idle and disconnected into
# grey and lists splitting them as an open question; `describe()` therefore keeps the
# health separately in JSON so the merge is never load-bearing for diagnosis.
UNUSABLE_HEALTH = {"unavailable", "stale", "unknown"}

# Which pixel index belongs to which source column, precomputed once.
_SLOT_OF = {}
for _source_id, _base in SLOTS.items():
    for _index in range(SIZE * SIZE):
        if _base <= _index % SIZE < _base + SLOT_WIDTH:
            _SLOT_OF[_index] = _source_id
_ROLE_OF = {index: role for role, pixels in ROLE_PIXELS.items() for index in pixels}


def status_for(source: dict, now: datetime) -> str:
    """Derive one status colour name for one source."""
    if source.get("source_health", "unknown") in UNUSABLE_HEALTH:
        return "grey"
    last_activity_at = source.get("last_activity_at")
    if not last_activity_at:
        return "grey"
    age = now - parse_timestamp(last_activity_at)
    if age < timedelta(0):
        return "grey"  # a future stamp is clock skew, not fresh activity
    if age < RECENT_LIMIT:
        return "green"
    if age < WARM_LIMIT:
        return "yellow"
    return "red"


def describe(state: dict, now: datetime | None = None, pulses: set[str] | None = None) -> dict:
    now = now or utc_now()
    pulses = pulses or set()
    out = {}
    for source_id in SOURCE_IDS:
        source = state["sources"][source_id]
        health = source.get("source_health", "unknown")
        out[source_id] = {
            "status": status_for(source, now),
            "activity_pulse": source_id in pulses,
            # Kept separate from `status` on purpose: the approved page shows an
            # unreachable collector and a merely idle one with the same grey, and that
            # ambiguity must not reach anyone reading the JSON.
            "source_health": health,
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

    for index, color in FIXED:
        pixels[index] = color

    for index, role in _ROLE_OF.items():
        source_id = _SLOT_OF[index]
        if summary[source_id]["activity_pulse"]:
            pixels[index] = OVERRIDE_RGB
        else:
            pixels[index] = ROLE_COLORS[role][summary[source_id]["status"]]

    # Crowns are per-column and cannot overlap, so simultaneous activity simply shows
    # more than one crown. Nothing is queued and nothing is shown late.
    for source_id, base in SLOTS.items():
        if not summary[source_id]["activity_pulse"]:
            continue
        for dx, dy, color in CROWN:
            pixels[dy * SIZE + base + dx] = color

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
    "columns": "x0-4 OptiPlex Lab (L, mushroom), x5-9 OptiPlex MCP (O, bunny), x10-14 WSL MCP (W, skull), x15 spare",
    "rows": "0-2 activity crown, 3-4 spacer, 5-9 identity letter, 10 divider, 11-15 icon",
    "status": {"green": "last activity under 5 min", "yellow": "5-20 min", "red": "over 20 min",
               "grey": "no usable data: idle, unreadable or disconnected"},
    "activity": "the active column's crown, letter and icon accent all take the blue override together, then fall back to its status colour",
    "accents": "mushroom cap recolours as a whole; bunny and skull recolour their eyes only",
    "known_ambiguity": "grey merges idle with unreachable, per the approved spec; activity-status reports source_health separately",
    "animation": "the crown is shown while activity is fresh. The approved four-stage blue pulse is NOT animated: at the accepted ~1118 ms per frame it would be decimated to noise, so the crown is static and the blue override is the visible activity signal.",
}
