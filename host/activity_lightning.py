"""Side-by-side MCP activity lightning choreography for successor runtime design.

This module intentionally does not modify Runtime 006's hash-bound renderer. It accepts an
already-rendered 16x16 dashboard frame and overlays one of ten deterministic activity stages
inside the active source's five-pixel column. A later successor revision can integrate the
same pure transform after offline/physical acceptance.
"""
from __future__ import annotations

from host.activity_ui_data import ROLE_PIXELS, SIZE, SLOTS

BLACK = (0, 0, 0)
CYAN = (0, 255, 255)
BLUE = (0, 170, 255)
LIGHT_BLUE = (85, 170, 255)
WHITE = (255, 255, 255)

STAGE_COUNT = 10

# Relative bolt geometry within one 5-pixel source column. It descends through the top
# crown/spacer rows and reaches the icon's top edge at y=5. Every prefix is visually unique.
_BOLT = ((2, 0), (1, 1), (2, 2), (1, 3), (2, 4), (2, 5))

# Stage plan: (bolt prefix length, role/accent colour or None, impact pixels, bolt colour).
# Stages 0-3 are descent, 4 is impact, 5-9 are ACK-gated flare/aftershock frames.
_PROGRAM = (
    (1, None, (), CYAN),
    (2, None, (), CYAN),
    (4, None, (), BLUE),
    (5, None, (), LIGHT_BLUE),
    (6, CYAN, ((0, 5), (4, 5), (1, 4), (3, 4)), WHITE),
    (0, CYAN, ((1, 4), (3, 4)), CYAN),
    (0, BLUE, (), BLUE),
    (0, LIGHT_BLUE, ((2, 4),), LIGHT_BLUE),
    (0, CYAN, (), CYAN),
    (0, BLUE, ((2, 4),), BLUE),
)


def _role_indices_for_source(source_id: str) -> tuple[int, ...]:
    if source_id not in SLOTS:
        raise ValueError(f"unknown source {source_id!r}")
    base = SLOTS[source_id]
    indices = []
    for group in ROLE_PIXELS.values():
        for index in group:
            x = index % SIZE
            if base <= x < base + 5:
                indices.append(index)
    return tuple(sorted(set(indices)))


_ROLE_INDICES = {source_id: _role_indices_for_source(source_id) for source_id in SLOTS}


def apply_stage(base_rgb: bytes, source_id: str, stage: int, *, faulted: bool = False) -> bytes:
    """Overlay one lightning stage; a faulted source deliberately does not animate."""
    if len(base_rgb) != SIZE * SIZE * 3:
        raise ValueError("dashboard frame must be exactly 16x16 RGB888")
    if source_id not in SLOTS:
        raise ValueError(f"unknown source {source_id!r}")
    if not 0 <= stage < STAGE_COUNT:
        raise ValueError(f"stage must be 0..{STAGE_COUNT - 1}")
    if faulted:
        return base_rgb

    pixels = [tuple(base_rgb[i:i + 3]) for i in range(0, len(base_rgb), 3)]
    base_x = SLOTS[source_id]
    bolt_len, accent, impact, bolt_color = _PROGRAM[stage]

    if accent is not None:
        for index in _ROLE_INDICES[source_id]:
            pixels[index] = accent

    for dx, dy in _BOLT[:bolt_len]:
        pixels[dy * SIZE + base_x + dx] = bolt_color
    for dx, dy in impact:
        pixels[dy * SIZE + base_x + dx] = bolt_color if stage != 4 else WHITE

    return b"".join(bytes(rgb) for rgb in pixels)


def compose(base_rgb: bytes, stages: dict[str, int], *, faulted: set[str] | None = None) -> bytes:
    """Compose independent simultaneous source pulses without crossing source columns."""
    out = base_rgb
    faults = faulted or set()
    for source_id in sorted(stages, key=lambda source: SLOTS[source]):
        out = apply_stage(out, source_id, stages[source_id], faulted=source_id in faults)
    return out


def changed_pixels(before: bytes, after: bytes) -> set[tuple[int, int]]:
    """Small test/preview helper: coordinates whose RGB triplet changed."""
    if len(before) != len(after) or len(before) != SIZE * SIZE * 3:
        raise ValueError("frames must both be 16x16 RGB888")
    changed = set()
    for index in range(SIZE * SIZE):
        start = index * 3
        if before[start:start + 3] != after[start:start + 3]:
            changed.add((index % SIZE, index // SIZE))
    return changed
