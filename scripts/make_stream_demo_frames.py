#!/usr/bin/env python3
"""Generate the deterministic 16x16 sweep-bar demo frame set for stream trials.

A vertical bar crosses the panel left to right, once per colour, on black. Every frame
is distinct, so a stream is unmistakably a stream rather than one static image, and the
direction/cadence are readable by eye on the real panel.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.frame_stream import FRAME_BYTES, build_frame_set  # noqa: E402

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


if __name__ == "__main__":
    output = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "examples/stream-demo/sweep-bar.rgb888")
    built = build_frame_set(frames())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"".join(built.frames))
    assert len(set(built.packet_sha256)) == built.count, "demo frames must all be distinct"
    print(f"{output} frames={built.count} sha256={built.sha256} "
          f"max_frame_bytes={built.max_frame_tx_bytes}")
