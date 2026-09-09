#!/usr/bin/env python3
"""Generate deterministic 16x16 frame sets for stream trials.

`sweep` — a vertical bar crosses the panel left to right, once per colour, on black.
Every frame is distinct, so a stream is unmistakably a stream rather than one static
image, and the direction/cadence are readable by eye on the real panel.

`fullcolour` — a rotating hue/brightness field where nearly every pixel is a distinct
colour. This is the payload a webcam actually produces: ~230-250 palette entries and
~1000 application bytes per frame, against the sweep set's 2 colours and 71 bytes. Rate
measurements must use this, because wire time scales with the packet, not the frame count.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.frame_stream import (FRAME_BYTES, build_frame_set,  # noqa: E402
                               quantize_to_palette_limit)

COLORS = ((200, 0, 0), (0, 200, 0), (0, 80, 255))


def frames() -> list[bytes]:
    out = []
    for color in COLORS:
        for x in range(16):
            frame = bytearray(FRAME_BYTES)
            for y in range(16):
                offset = (y * 16 + x) * 3
                frame[offset:offset + 3] = bytes(color)
            out.append(bytes(frame))
    return out


def fullcolour_frames(count: int = 60) -> list[bytes]:
    """A rotating near-full-palette field, integer-only so it reproduces anywhere.

    Sized to match the payload the accepted rate ladder actually measured: R4 and R5 both
    sent 1048 application bytes per frame. 250 distinct colours over 256 pixels forces
    8 bits per pixel and a 750-byte palette, which lands in the same place -- and is the
    worst case a 16x16 webcam frame can reach, since 256 pixels cannot exceed 256 colours.
    """
    palette = [((i * 7) % 256, (i * 29 + 40) % 256, (i * 53 + 90) % 256) for i in range(250)]
    out = []
    for step in range(count):
        frame = bytearray(FRAME_BYTES)
        for index in range(256):
            colour = palette[(index * 3 + step * 11) % len(palette)]
            frame[index * 3:index * 3 + 3] = bytes(colour)
        out.append(bytes(frame))
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    default = {"sweep": "examples/stream-demo/sweep-bar.rgb888",
               "fullcolour": "examples/stream-demo/fullcolour-field.rgb888"}[mode]
    output = Path(sys.argv[2] if len(sys.argv) > 2 else ROOT / default)
    built = build_frame_set(frames() if mode == "sweep" else fullcolour_frames())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"".join(built.frames))
    assert len(set(built.packet_sha256)) == built.count, "demo frames must all be distinct"
    print(f"{output} frames={built.count} sha256={built.sha256} "
          f"max_frame_bytes={built.max_frame_tx_bytes} "
          f"palette={min(built.palette_colors)}-{max(built.palette_colors)}")
