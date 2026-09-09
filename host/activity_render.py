"""16x16 renderer for the approved three-MCP activity page.

The layout is the operator-approved design with one operator change: an activity crown
across rows 0-2, the 5x5 mushroom / bunny / skull icons on rows 5-9, and the identity
letters L / O / W on rows 11-15, one 5-pixel column per source with x=15 spare. The
supplied mockups place the letters above the icons; the two blocks are swapped, as an
explicit transform in the generator rather than by editing pixels.

Every pixel and colour comes from `host/activity_ui_data.py`, which is *derived* from the
approved mockups in `assets/ui/reference/` rather than transcribed. The offline suite
re-derives it and also re-renders each reference frame, so the mockups are executable
acceptance criteria: if a pixel moves, a test fails.

Status is one colour per source -- green under 5 minutes, yellow to 20, red beyond, grey
for no usable data. During activity that column's crown, letter and icon accent all take
the blue override together, then fall back to the status colour.

A source the collector could not read, or has stopped reading, additionally shows a dim
red fault bar in its crown row. The approved spec renders idle and unreachable alike in
grey and lists splitting them as an open question; this splits them without touching the
approved letters or icons, because an unreachable source can never produce activity and
its crown row is therefore free by construction. See `LEGEND`.

The palette is plain RGB888, which is what the exact unit's stock `0x44` path uses: all
8/8 captured stock snapshots re-encoded byte-for-byte from an RGB888 palette. The RGB222
values in the supplied artwork are an inherited design choice, never a device limit.
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
# than as a stale-but-fine colour.
UNUSABLE_HEALTH = {"unavailable", "stale", "unknown"}

# ...and of those, these are actual faults worth showing on the panel. `unknown` is NOT
# one: it is the state before the first poll, where grey with no marker is the honest
# answer rather than three fault bars at startup.
FAULT_HEALTH = {"unavailable", "stale"}

# Dim red bar across the middle of the column's top row. Deliberately reuses a red
# already in the design's palette, so it costs no extra palette entry.
FAULT_MARKER = ((1, 0), (2, 0), (3, 0))
FAULT_RGB = (170, 0, 0)

# The operator-approved four-stage activity pulse. The Host hard floor is 150 ms, while
# the MCP client nominally dispatches at 200 ms for cross-process jitter headroom, making
# this a ~0.80 s blue/cyan shimmer. The static reference mockups
# remain the stage-agnostic acceptance baseline; live animation passes an explicit stage.
PULSE_COLORS = ((0, 255, 255), (0, 170, 255), (85, 170, 255), (0, 255, 255))

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


def describe(state: dict, now: datetime | None = None, pulses: set[str] | None = None,
             pulse_stage: int | None = None) -> dict:
    now = now or utc_now()
    pulses = pulses or set()
    out = {}
    for source_id in SOURCE_IDS:
        source = state["sources"][source_id]
        health = source.get("source_health", "unknown")
        out[source_id] = {
            "status": status_for(source, now),
            "activity_pulse": source_id in pulses,
            "activity_pulse_stage": pulse_stage if source_id in pulses else None,
            "fault": health in FAULT_HEALTH,
            # `status` alone cannot distinguish idle from unreachable -- both are grey.
            # The fault bar does that on the panel; this does it in JSON.
            "source_health": health,
            "last_activity_at": source["last_activity_at"],
            "last_observed_at": source["last_observed_at"],
            "last_outcome": source["last_outcome"],
            "history_complete": source["history_complete"],
            "error_code": source["error_code"],
        }
    return out


def render_rgb888(state: dict, now: datetime | None = None, pulses: set[str] | None = None,
                  pulse_stage: int | None = None) -> bytes:
    if pulse_stage is not None and not 0 <= pulse_stage < len(PULSE_COLORS):
        raise ValueError(f"pulse_stage must be 0..{len(PULSE_COLORS) - 1}")
    summary = describe(state, now, pulses, pulse_stage)
    pulse_rgb = PULSE_COLORS[pulse_stage] if pulse_stage is not None else OVERRIDE_RGB
    pixels = [BLACK] * (SIZE * SIZE)

    for index, color in FIXED:
        pixels[index] = color

    for index, role in _ROLE_OF.items():
        source_id = _SLOT_OF[index]
        if summary[source_id]["activity_pulse"]:
            pixels[index] = pulse_rgb
        else:
            pixels[index] = ROLE_COLORS[role][summary[source_id]["status"]]

    # Crowns are per-column and cannot overlap, so simultaneous activity simply shows
    # more than one crown. Nothing is queued and nothing is shown late.
    #
    # A crown and a fault bar cannot collide: the collector zeroes the new-event count
    # for any source it failed to read, so a faulted source never pulses. Fault still
    # wins explicitly rather than resting on that invariant holding forever.
    for source_id, base in SLOTS.items():
        view = summary[source_id]
        if view["fault"]:
            for dx, dy in FAULT_MARKER:
                pixels[dy * SIZE + base + dx] = FAULT_RGB
        elif view["activity_pulse"]:
            for dx, dy, color in CROWN:
                pixels[dy * SIZE + base + dx] = pulse_rgb if pulse_stage is not None else color

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
    "columns": "x0-4 OptiPlex Lab (mushroom over L), x5-9 OptiPlex MCP (bunny over O), x10-14 WSL MCP (skull over W), x15 spare",
    "rows": "0-2 activity crown, 3-4 spacer, 5-9 icon, 10 divider, 11-15 identity letter",
    "status": {"green": "last activity under 5 min", "yellow": "5-20 min", "red": "over 20 min",
               "grey": "no usable data: idle, unreadable or disconnected"},
    "activity": "the active column's crown, letter and icon accent all take the blue override together, then fall back to its status colour",
    "accents": "mushroom cap recolours as a whole; bunny and skull recolour their eyes only",
    "fault": "a dim red bar in the crown row means the collector could not read that source (unavailable) or has stopped reading it (stale) -- as opposed to grey, which means it read fine and there was simply nothing to report. A source that has never been polled shows neither.",
    "color_model": "RGB888, as the exact unit's stock 0x44 path uses. The artwork's RGB222 values are inherited design, not a device limit.",
    "animation": "live activity uses three visible cyan/blue/light-blue/cyan sweeps per event. Duplicate cyan boundaries are collapsed, yielding 10 distinct ACK-gated frames at the 200 ms MCP client cadence (~2.0 s total); the active column's crown, letter and icon accent change together, then return to status color. Static previews without a stage retain the approved reference-frame blue override.",
}
