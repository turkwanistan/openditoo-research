"""W9A deterministic motion-truth stimulus: a counter that survives the 16x16 transform.

W8 measured 16.285 fps of ACKed transport and the owner confirmed the picture looked right.
Neither fact says how many DISTINCT scene samples reached the panel, because nothing in the
frame identifies which moment it came from. W9B needs to film a monitor and the Ditoo together
and line the two up, so the thing on the monitor has to carry a decodable timestamp.

Almost nothing survives 640x480 -> centred 480x480 crop -> 16x16 area average. Digits do not.
Thin lines do not. Large solid blocks do, exactly, because the grid divides evenly: a 4x4 grid
over a 480 px square is 120 px per cell, which is 4 output pixels per cell with no partial
coverage at any boundary. So the counter is drawn as a 4x4 grid of black/white cells.

Layout, in SOURCE orientation:

    S . . S      S = sync marker, . = counter bit
    . . . .      corners are fixed (white, black, white, black reading TL, TR, BL, BR)
    . . . .      the remaining 12 cells are a 12-bit GRAY-CODED counter, MSB first, row-major
    S . . S

The corner pattern is deliberately asymmetric under a horizontal flip, so a decode that
forgets the transform's mirror fails loudly instead of returning a plausible wrong number.
12 bits wraps at 4096, which is 68 s at 60 fps -- far longer than a 10 s trial.

Nothing here transmits, and nothing here is a frame source: this generates a stimulus to point
a camera at, and decodes what comes back. The live webcam path stays live.
"""
from __future__ import annotations

import numpy as np

GRID = 4                     # cells per side
CELL_PIXELS = 4              # transformed pixels per cell (16 / GRID)
SIZE = GRID * CELL_PIXELS    # 16, the Ditoo panel side
COUNTER_BITS = 12
COUNTER_MODULUS = 1 << COUNTER_BITS

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# (row, col) -> expected bit, in source orientation. Asymmetric under a horizontal flip.
SYNC_CELLS = {(0, 0): True, (0, GRID - 1): False, (GRID - 1, 0): True, (GRID - 1, GRID - 1): False}
# MSB first, row-major, skipping the corners.
DATA_CELLS = tuple((row, col) for row in range(GRID) for col in range(GRID)
                   if (row, col) not in SYNC_CELLS)
assert len(DATA_CELLS) == COUNTER_BITS, len(DATA_CELLS)


def to_gray(value: int) -> int:
    """Plain binary -> reflected Gray code, so consecutive counters differ in ONE cell.

    This exists because of a measured failure, not theory. A phone still of the stimulus
    decoded as 1255 while the screen's own readout said 1252, with the disagreement confined
    to the two cells holding the lowest bits: a rolling-shutter capture exposes the top and
    bottom of the grid at slightly different times, so a frame can straddle a counter change.

    Under plain binary a straddle is unbounded, because a carry flips many cells at once
    (1255 -> 1256 flips four). Under Gray code exactly one cell changes per step, so a
    straddled read can only resolve to the old value or the new one -- an error of at most
    one count. That converts an arbitrary wrong latency into a bounded one.
    """
    return value ^ (value >> 1)


def from_gray(gray: int) -> int:
    value = gray
    shift = 1
    while shift < COUNTER_BITS:
        value ^= value >> shift
        shift <<= 1
    return value


def cell_bits(counter: int) -> dict[tuple[int, int], bool]:
    """The full 4x4 cell map for one counter value, in source orientation."""
    if counter < 0:
        raise ValueError("counter must not be negative")
    value = to_gray(counter % COUNTER_MODULUS)
    cells = dict(SYNC_CELLS)
    for index, position in enumerate(DATA_CELLS):
        cells[position] = bool(value >> (COUNTER_BITS - 1 - index) & 1)
    return cells


def render_source(counter: int, side: int = 480) -> np.ndarray:
    """One stimulus frame as (side, side, 3) uint8 RGB, ready to display or transform.

    `side` must divide evenly by the grid, so every cell lands on whole pixels. A monitor
    filmed by a real camera will not align this cleanly; the decoder samples cell interiors
    precisely so that it tolerates the misalignment W9B will actually have.
    """
    if side % GRID:
        raise ValueError(f"side {side} must be a multiple of {GRID}")
    step = side // GRID
    frame = np.zeros((side, side, 3), dtype=np.uint8)
    for (row, col), lit in cell_bits(counter).items():
        frame[row * step:(row + 1) * step, col * step:(col + 1) * step] = WHITE if lit else BLACK
    return frame


def _cell_luma(pixels: np.ndarray, row: int, col: int) -> float:
    """Mean luma of a cell's interior, ignoring its outer ring.

    The outer ring is where a misaligned monitor bleeds its neighbour in. Dropping it costs
    nothing here (the centre is a solid block by construction) and is what makes the decode
    survive a camera that is not pixel-aligned to the panel.
    """
    inset = CELL_PIXELS // 4
    block = pixels[row * CELL_PIXELS + inset:(row + 1) * CELL_PIXELS - inset,
                   col * CELL_PIXELS + inset:(col + 1) * CELL_PIXELS - inset]
    return float(block @ np.array([0.2126, 0.7152, 0.0722]) @ np.ones(1) if block.ndim == 1
                 else (block.astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722])).mean())


def decode(frame: bytes, *, mirrored: bool = True, threshold: float = 128.0) -> int | None:
    """Recover the counter from one transformed 768-byte RGB888 frame, or None.

    `mirrored` matches the production transform preset, which mirrors horizontally so a webcam
    facing the user reads correctly. None means the sync corners did not match, which is the
    honest answer for a frame that is mid-transition, misaligned, or not the stimulus at all --
    W9B must count those rather than guess through them.
    """
    if len(frame) != SIZE * SIZE * 3:
        raise ValueError(f"expected {SIZE * SIZE * 3} bytes, got {len(frame)}")
    pixels = np.frombuffer(frame, dtype=np.uint8).reshape(SIZE, SIZE, 3)
    if mirrored:
        # Undo the preset's horizontal flip so cell coordinates are source orientation again.
        pixels = pixels[:, ::-1]

    lit = {position: _cell_luma(pixels, *position) >= threshold
           for position in list(SYNC_CELLS) + list(DATA_CELLS)}
    if any(lit[position] != expected for position, expected in SYNC_CELLS.items()):
        return None
    gray = 0
    for position in DATA_CELLS:
        gray = gray << 1 | int(lit[position])
    return from_gray(gray)


def round_trip(counter: int, preset=None, side: int = 480) -> int | None:
    """Render a counter, push it through the real production transform, and decode it back.

    Uses the same `host.frame_transform` the sidecar mirrors, so this proves the stimulus
    survives the actual pipeline rather than an idealised model of it.
    """
    from host import frame_transform

    preset = frame_transform.DEFAULT if preset is None else preset
    return decode(frame_transform.transform(render_source(counter, side), preset),
                  mirrored=preset.mirror)
