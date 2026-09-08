"""Deterministic Day-1 16x16 RGB diagnostic frame; no device transport."""
from __future__ import annotations

import hashlib
from pathlib import Path

WIDTH = 16
HEIGHT = 16
RGB_BYTES = WIDTH * HEIGHT * 3
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
WHITE = (255, 255, 255)
DIM_GRAY = (64, 64, 64)


def build_diagnostic_rgb() -> bytes:
    pixels = [BLACK] * (WIDTH * HEIGHT)

    def put(x: int, y: int, color: tuple[int, int, int]) -> None:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise ValueError("coordinate outside 16x16 frame")
        pixels[y * WIDTH + x] = color

    # Exact plan geometry: unique corner shapes expose rotation/mirroring.
    put(0, 0, RED)
    put(1, 0, RED)
    put(15, 0, GREEN)
    put(15, 1, GREEN)
    put(15, 2, GREEN)
    for y in (14, 15):
        for x in (0, 1):
            put(x, y, BLUE)
    put(15, 15, WHITE)
    put(7, 7, DIM_GRAY)

    raw = bytes(channel for pixel in pixels for channel in pixel)
    if len(raw) != RGB_BYTES:
        raise AssertionError("diagnostic RGB frame is not exactly 768 bytes")
    return raw


def frame_sha256(rgb: bytes | None = None) -> str:
    return hashlib.sha256(build_diagnostic_rgb() if rgb is None else bytes(rgb)).hexdigest()


def write_artifacts(directory: Path) -> dict[str, object]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rgb = build_diagnostic_rgb()
    rgb_path = directory / "day1_diagnostic_16x16.rgb"
    ppm_path = directory / "day1_diagnostic_16x16.ppm"
    rgb_path.write_bytes(rgb)
    ppm_path.write_bytes(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + rgb)
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "source_format": "RGB888",
        "rgb_bytes": len(rgb),
        "rgb_sha256": frame_sha256(rgb),
        "rgb_path": str(rgb_path),
        "ppm_path": str(ppm_path),
        "quantization": "none; device packing intentionally unresolved",
    }
