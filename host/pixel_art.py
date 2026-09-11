"""Deterministic text-first 16x16 pixel-art primitives for OpenDitoo.

The authored source is literal device geometry. Review PNG/HTML files are derived artifacts;
the canonical compiled frame is always 768 bytes of row-major RGB888.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib
from typing import Iterable

from host import ditoo_pixel_coloring, frame_stream

SPRITE_SCHEMA = "openditoo.pixel-sprite.v1"
WIDTH = HEIGHT = 16
BACKGROUND_KEY = "."


class PixelArtError(ValueError):
    pass


def _rgb(value, *, name: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise PixelArtError(f"{name}: palette color must be an RGB triplet")
    out = tuple(int(x) for x in value)
    if any(x < 0 or x > 255 for x in out):
        raise PixelArtError(f"{name}: RGB channel outside 0..255")
    return out


@dataclass(frozen=True)
class PixelSprite:
    id: str
    palette: dict[str, tuple[int, int, int]]
    rows: tuple[str, ...]
    anchor: tuple[int, int] | None = None
    mirroring: str | None = None
    tags: tuple[str, ...] = ()
    source_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise PixelArtError("sprite id is required")
        if len(self.rows) != HEIGHT or any(len(row) != WIDTH for row in self.rows):
            raise PixelArtError("sprite rows must be exactly 16x16")
        if BACKGROUND_KEY not in self.palette:
            raise PixelArtError("sprite palette must define '.' background")
        if self.palette[BACKGROUND_KEY] != (0, 0, 0):
            raise PixelArtError("v1 background '.' must be black (0,0,0)")
        used = {ch for row in self.rows for ch in row}
        missing = sorted(used - set(self.palette))
        if missing:
            raise PixelArtError(f"undefined palette keys: {missing}")
        if len(self.palette) > 255:
            raise PixelArtError("Ditoo encoder supports at most 255 colors")
        if self.anchor is not None:
            x, y = self.anchor
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                raise PixelArtError("anchor must be on the 16x16 canvas")
        if self.mirroring not in (None, "horizontal"):
            raise PixelArtError("mirroring must be null or 'horizontal'")

    @property
    def rgb888(self) -> bytes:
        return bytes(c for row in self.rows for key in row for c in self.palette[key])

    @property
    def rgb_sha256(self) -> str:
        return hashlib.sha256(self.rgb888).hexdigest()

    @property
    def canonical_sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode()).hexdigest()

    def to_dict(self) -> dict:
        meta: dict = {"tags": list(self.tags)}
        if self.anchor is not None:
            meta["anchor"] = list(self.anchor)
        if self.mirroring is not None:
            meta["mirroring"] = self.mirroring
        return {
            "schema": SPRITE_SCHEMA, "id": self.id, "width": WIDTH, "height": HEIGHT,
            "palette": {k: list(v) for k, v in self.palette.items()},
            "rows": list(self.rows), "meta": meta,
        }

    def mirrored(self, *, new_id: str | None = None) -> "PixelSprite":
        anchor = None if self.anchor is None else (WIDTH - 1 - self.anchor[0], self.anchor[1])
        return PixelSprite(new_id or f"{self.id}.mirror", dict(self.palette),
                           tuple(row[::-1] for row in self.rows), anchor,
                           self.mirroring, self.tags, self.source_path)

    def translated(self, dx: int, dy: int, *, new_id: str | None = None) -> tuple["PixelSprite", int]:
        grid = [[BACKGROUND_KEY] * WIDTH for _ in range(HEIGHT)]
        clipped = 0
        for y, row in enumerate(self.rows):
            for x, key in enumerate(row):
                if key == BACKGROUND_KEY:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                    grid[ny][nx] = key
                else:
                    clipped += 1
        anchor = None
        if self.anchor is not None:
            ax, ay = self.anchor[0] + dx, self.anchor[1] + dy
            anchor = (ax, ay) if 0 <= ax < WIDTH and 0 <= ay < HEIGHT else None
        return PixelSprite(new_id or f"{self.id}.translate.{dx}.{dy}", dict(self.palette),
                           tuple("".join(r) for r in grid), anchor, self.mirroring,
                           self.tags, self.source_path), clipped


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_sprite(path: Path | str) -> PixelSprite:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PixelArtError(f"{path}: unreadable sprite: {exc}") from exc
    if raw.get("schema") != SPRITE_SCHEMA:
        raise PixelArtError(f"{path}: expected schema {SPRITE_SCHEMA!r}")
    if raw.get("width") != WIDTH or raw.get("height") != HEIGHT:
        raise PixelArtError(f"{path}: width/height must be 16")
    palette_raw = raw.get("palette")
    if not isinstance(palette_raw, dict) or not palette_raw:
        raise PixelArtError(f"{path}: palette must be a non-empty object")
    palette: dict[str, tuple[int, int, int]] = {}
    for key, value in palette_raw.items():
        if not isinstance(key, str) or len(key) != 1:
            raise PixelArtError(f"{path}: palette keys must be one character")
        palette[key] = _rgb(value, name=f"{path}:{key}")
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list) or any(not isinstance(row, str) for row in rows_raw):
        raise PixelArtError(f"{path}: rows must be a string list")
    meta = raw.get("meta") or {}
    anchor_raw = meta.get("anchor")
    anchor = None
    if anchor_raw is not None:
        if not isinstance(anchor_raw, list) or len(anchor_raw) != 2:
            raise PixelArtError(f"{path}: anchor must be [x,y]")
        anchor = (int(anchor_raw[0]), int(anchor_raw[1]))
    sprite = PixelSprite(str(raw.get("id") or ""), palette, tuple(rows_raw), anchor,
                         meta.get("mirroring"), tuple(str(t) for t in meta.get("tags", [])), path)
    if len(sprite.rgb888) != frame_stream.FRAME_BYTES:
        raise PixelArtError(f"{path}: compiled frame length drifted")
    ditoo_pixel_coloring.palette_and_indices_from_rgb888(sprite.rgb888)
    return sprite


def sprite_from_rows(sprite_id: str, palette: dict[str, tuple[int, int, int]], rows: Iterable[str],
                     *, anchor: tuple[int, int] | None = None, mirroring: str | None = None,
                     tags: Iterable[str] = ()) -> PixelSprite:
    return PixelSprite(sprite_id, palette, tuple(rows), anchor, mirroring, tuple(tags))


def geometry(sprite: PixelSprite) -> dict:
    coords = [(x, y) for y, row in enumerate(sprite.rows) for x, key in enumerate(row)
              if key != BACKGROUND_KEY]
    usage = {key: sum(row.count(key) for row in sprite.rows) for key in sprite.palette}
    usage = {key: count for key, count in usage.items() if count}
    if not coords:
        bbox = center = None
        width = height = 0
    else:
        xs, ys = [c[0] for c in coords], [c[1] for c in coords]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        width, height = bbox[2] - bbox[0] + 1, bbox[3] - bbox[1] + 1
        center = [round(sum(xs) / len(xs), 3), round(sum(ys) / len(ys), 3)]
    occupied = set(coords)
    singletons = 0
    seen: set[tuple[int, int]] = set()
    for start in occupied:
        if start in seen:
            continue
        stack, component = [start], []
        while stack:
            point = stack.pop()
            if point in seen:
                continue
            seen.add(point)
            component.append(point)
            x, y = point
            for nxt in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nxt in occupied and nxt not in seen:
                    stack.append(nxt)
        if len(component) == 1:
            singletons += 1
    edge_touches = set()
    for x, y in coords:
        if x == 0: edge_touches.add("left")
        if x == 15: edge_touches.add("right")
        if y == 0: edge_touches.add("top")
        if y == 15: edge_touches.add("bottom")
    colors = {tuple(sprite.rgb888[i:i+3]) for i in range(0, 768, 3)}
    return {
        "bbox": bbox, "bbox_width": width, "bbox_height": height,
        "occupied_pixels": len(coords), "occupancy_percent": round(len(coords) / 256 * 100, 2),
        "center_of_mass": center, "edge_touches": sorted(edge_touches),
        "palette_usage": usage, "distinct_rgb_colors": len(colors),
        "single_pixel_islands": singletons,
        "anchor": None if sprite.anchor is None else list(sprite.anchor),
    }


def changed_pixels(a: PixelSprite | bytes, b: PixelSprite | bytes) -> list[tuple[int, int]]:
    ar = a.rgb888 if isinstance(a, PixelSprite) else a
    br = b.rgb888 if isinstance(b, PixelSprite) else b
    if len(ar) != 768 or len(br) != 768:
        raise PixelArtError("changed_pixels requires two 768-byte frames")
    return [(i % 16, i // 16) for i in range(256)
            if ar[i * 3:i * 3 + 3] != br[i * 3:i * 3 + 3]]


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def png_bytes(rgb: bytes, width: int, height: int, *, scale: int = 1) -> bytes:
    if len(rgb) != width * height * 3 or scale < 1:
        raise PixelArtError("invalid RGB dimensions/scale")
    if scale != 1:
        enlarged = bytearray()
        for y in range(height):
            row = rgb[y * width * 3:(y + 1) * width * 3]
            expanded = b"".join(row[x * 3:x * 3 + 3] * scale for x in range(width))
            for _ in range(scale):
                enlarged.extend(expanded)
        rgb = bytes(enlarged)
        width *= scale
        height *= scale
    scan = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(scan, 9)) + _png_chunk(b"IEND", b""))


def write_png(path: Path | str, rgb: bytes, width: int = WIDTH, height: int = HEIGHT,
              *, scale: int = 1) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(rgb, width, height, scale=scale))
    return path


def contact_sheet(frames: list[bytes], *, scale: int = 12, gap: int = 2) -> tuple[bytes, int, int]:
    if not frames:
        raise PixelArtError("contact sheet needs at least one frame")
    tile = WIDTH * scale
    width = len(frames) * tile + max(0, len(frames) - 1) * gap
    height = HEIGHT * scale
    canvas = bytearray(width * height * 3)
    for index, frame in enumerate(frames):
        if len(frame) != 768:
            raise PixelArtError("contact sheet frame length must be 768")
        x0 = index * (tile + gap)
        for sy in range(HEIGHT):
            for sx in range(WIDTH):
                color = frame[(sy * WIDTH + sx) * 3:(sy * WIDTH + sx + 1) * 3]
                for py in range(scale):
                    start = ((sy * scale + py) * width + x0 + sx * scale) * 3
                    canvas[start:start + scale * 3] = color * scale
    return bytes(canvas), width, height
