#!/usr/bin/env python3
"""Render exact/scaled offline previews for UI-1 lightning and GAME-1 slots.

Stdlib/project-only: no Pillow and no device I/O. Outputs are review aids, not authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host import activity_lightning, activity_render, mcp_activity
from host.slots_page import SlotsPage

SIZE = 16


def scale(rgb: bytes, width: int, height: int, factor: int) -> bytes:
    out = bytearray()
    for y in range(height):
        row = bytearray()
        for x in range(width):
            i = (y * width + x) * 3
            row.extend(rgb[i:i + 3] * factor)
        out.extend(bytes(row) * factor)
    return bytes(out)


def sheet(frames: list[bytes]) -> tuple[bytes, int, int]:
    width, height = SIZE * len(frames), SIZE
    out = bytearray(width * height * 3)
    for frame_index, frame in enumerate(frames):
        for y in range(SIZE):
            src = y * SIZE * 3
            dst = (y * width + frame_index * SIZE) * 3
            out[dst:dst + SIZE * 3] = frame[src:src + SIZE * 3]
    return bytes(out), width, height


def representative_state() -> dict:
    now = datetime(2026, 9, 10, 17, 0, 0, tzinfo=timezone.utc)
    state = mcp_activity.blank_state()
    for source in state["sources"].values():
        source["source_health"] = "healthy"
        source["last_activity_at"] = mcp_activity.iso(now)
        source["last_observed_at"] = mcp_activity.iso(now)
        source["history_complete"] = True
    return state


def render_lightning(out: Path, factor: int) -> None:
    state = representative_state()
    base = activity_render.render_rgb888(
        state, now=datetime(2026, 9, 10, 17, 0, 1, tzinfo=timezone.utc))
    frames = [activity_lightning.apply_stage(base, "wsl_mcp", stage)
              for stage in range(activity_lightning.STAGE_COUNT)]
    directory = out / "lightning"
    directory.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        activity_render.write_png(directory / f"stage-{index:02d}-16.png", frame, SIZE, SIZE)
        activity_render.write_png(
            directory / f"stage-{index:02d}-{SIZE * factor}.png",
            scale(frame, SIZE, SIZE, factor), SIZE * factor, SIZE * factor)
    rgb, width, height = sheet(frames)
    activity_render.write_png(directory / "lightning-sheet-16.png", rgb, width, height)
    activity_render.write_png(
        directory / "lightning-sheet-large.png", scale(rgb, width, height, factor),
        width * factor, height * factor)


def render_slots(out: Path, factor: int) -> None:
    page = SlotsPage(seed=20260910)
    frames = []
    lever_at = {8, 14, 20}
    for ack in range(24):
        if ack in lever_at:
            page.handle_input({"type": "lever_candidate", "seq": ack, "epoch": "preview"})
        frames.append(page.render(ack * 60))
        page.frame_sent()
    directory = out / "slots"
    directory.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        activity_render.write_png(directory / f"frame-{index:02d}-16.png", frame, SIZE, SIZE)
        activity_render.write_png(
            directory / f"frame-{index:02d}-{SIZE * factor}.png",
            scale(frame, SIZE, SIZE, factor), SIZE * factor, SIZE * factor)
    rgb, width, height = sheet(frames)
    activity_render.write_png(directory / "slots-sheet-16.png", rgb, width, height)
    activity_render.write_png(
        directory / "slots-sheet-large.png", scale(rgb, width, height, factor),
        width * factor, height * factor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".openditoo-local/previews/interactive-pages"))
    parser.add_argument("--scale", type=int, default=12)
    args = parser.parse_args()
    if args.scale < 1 or args.scale > 32:
        parser.error("--scale must be 1..32")
    render_lightning(args.output, args.scale)
    render_slots(args.output, args.scale)
    print(f"INTERACTIVE_PAGE_PREVIEWS=PASS output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
