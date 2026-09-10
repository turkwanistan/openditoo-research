"""W9B offline analysis: true scene-to-visible latency from high-speed footage.

The setup this decodes is one high-speed video frame containing BOTH the stimulus monitor and
the Ditoo. That is deliberate, and it is what makes the measurement honest: the two are on the
same exposure and therefore the same clock, so no camera/host clock alignment is required and
none can drift.

Both regions decode with the same 4x4 cell code from `host.motion_truth`:

* the MONITOR shows the stimulus directly, so it decodes unmirrored;
* the DITOO shows what the production transform produced, so it decodes MIRRORED.

Latency for counter N is then simply (first frame the Ditoo shows N) - (first frame the monitor
shows N), divided by the footage frame rate. Nothing here talks to a device, and nothing here
is transport evidence: this measures the PHYSICAL display, which is exactly the category W8's
16.285 fps of ACKed transport could not speak to.

Frame extraction stays external, because ffmpeg already does it better than a wrapper would:

    ffmpeg -i slowmo.mov -vsync 0 frames/%%06d.png

The operator supplies each region as four corner points in image coordinates, clockwise from
the top-left of the SOURCE orientation. Auto-detecting them was rejected: a wrong auto-detect
produces a confident wrong latency, while a wrong hand-marked corner fails to decode and is
visible immediately.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import statistics

import numpy as np

from host import motion_truth

Quad = Sequence[tuple[float, float]]
# Warp to a multiple of the panel before area-averaging down to it. Warping straight to 16x16
# would resample a whole filmed region through a handful of samples and lose the cell interiors
# the decode depends on.
WARP_SIDE = motion_truth.SIZE * 4


def _perspective_coefficients(quad: Quad, side: int) -> list[float]:
    """PIL's PERSPECTIVE coefficients mapping the OUTPUT square back into the input quad."""
    if len(quad) != 4:
        raise ValueError("a quad needs exactly 4 corners")
    target = [(0, 0), (side, 0), (side, side), (0, side)]
    rows, values = [], []
    for (tx, ty), (sx, sy) in zip(target, quad):
        rows.append([tx, ty, 1, 0, 0, 0, -sx * tx, -sx * ty])
        rows.append([0, 0, 0, tx, ty, 1, -sy * tx, -sy * ty])
        values += [sx, sy]
    solved, *_ = np.linalg.lstsq(np.asarray(rows, dtype=np.float64),
                                 np.asarray(values, dtype=np.float64), rcond=None)
    return solved.tolist()


def warp_to_panel(image: np.ndarray, quad: Quad) -> bytes:
    """Rectify one filmed region into exactly one 16x16 RGB888 frame."""
    from PIL import Image

    warped = Image.fromarray(np.ascontiguousarray(image[:, :, :3].astype(np.uint8)), "RGB").transform(
        (WARP_SIDE, WARP_SIDE), Image.Transform.PERSPECTIVE,
        _perspective_coefficients(quad, WARP_SIDE), Image.Resampling.BICUBIC)
    block = np.asarray(warped, dtype=np.float64)
    scale = WARP_SIDE // motion_truth.SIZE
    # Area average, matching the character of the production transform rather than point-sampling.
    small = block.reshape(motion_truth.SIZE, scale, motion_truth.SIZE, scale, 3).mean(axis=(1, 3))
    return np.rint(small).astype(np.uint8).tobytes()


def decode_region(image: np.ndarray, quad: Quad, *, mirrored: bool) -> int | None:
    """Counter visible in one region of one video frame, or None if it is not decodable."""
    return motion_truth.decode(warp_to_panel(image, quad), mirrored=mirrored)


def read_frame(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as handle:
        return np.asarray(handle.convert("RGB"), dtype=np.uint8)


def first_appearances(counters: Sequence[int | None]) -> dict[int, int]:
    """Counter -> index of the first footage frame in which it became visible.

    "First" is what latency is measured from, so a value held across several frames contributes
    one appearance, not several. A 12-bit counter wraps every 4096 values; at 240 fps footage of
    a 10 s trial that cannot happen, and a repeated value is recorded once rather than guessed
    at, so a wrap would show up as a missing transition instead of a fabricated one.
    """
    seen: dict[int, int] = {}
    for index, value in enumerate(counters):
        if value is not None and value not in seen:
            seen[value] = index
    return seen


def _summary(values: Sequence[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}
    return {"count": len(ordered), "min": ordered[0], "max": ordered[-1],
            "p50": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
            "mean": statistics.fmean(ordered)}


def analyse(monitor: Sequence[int | None], ditoo: Sequence[int | None], fps: float) -> dict:
    """Correlate the two decoded series into scene-to-visible latency and visible cadence.

    Takes already-decoded series rather than a video, so the arithmetic is testable without
    footage and the decode step can be inspected separately when a real clip disappoints.
    """
    if len(monitor) != len(ditoo):
        raise ValueError("the two series come from the same frames and must be the same length")
    if fps <= 0:
        raise ValueError("footage fps must be positive")

    shown = first_appearances(monitor)
    visible = first_appearances(ditoo)
    matched = sorted(set(shown) & set(visible))
    # Only forward-in-time matches are latency. A Ditoo appearance BEFORE the monitor showed the
    # same value means a decode error or a wrapped counter, never a negative latency, so it is
    # counted and excluded rather than averaged in.
    latencies_ms, impossible = [], 0
    for counter in matched:
        delta = visible[counter] - shown[counter]
        if delta < 0:
            impossible += 1
            continue
        latencies_ms.append(delta * 1000.0 / fps)

    ditoo_values = [value for value in ditoo if value is not None]
    repeats = sum(1 for previous, current in zip(ditoo_values, ditoo_values[1:]) if previous == current)
    ordered_visible = [counter for counter, _ in sorted(visible.items(), key=lambda item: item[1])]
    # Gaps between consecutively VISIBLE counters: stimulus frames that were never displayed.
    skipped = sum(max(0, later - earlier - 1)
                  for earlier, later in zip(ordered_visible, ordered_visible[1:]))

    return {
        "footage_fps": fps,
        "frames_analysed": len(monitor),
        "monitor_undecodable": sum(1 for value in monitor if value is None),
        "ditoo_undecodable": sum(1 for value in ditoo if value is None),
        "monitor_unique_counters": len(shown),
        "visible_unique_transitions": len(visible),
        "correlated_transitions": len(latencies_ms),
        "uncorrelated_visible": len(visible) - len(matched),
        "impossible_negative_matches": impossible,
        "visible_repeat_frames": repeats,
        "skipped_between_visible": skipped,
        "scene_to_visible_latency_ms": _summary(latencies_ms),
        # W9B's own acceptance bar. Reported, never silently enforced.
        "meets_minimum_transitions": len(latencies_ms) >= 30,
        "caveat": ("Latency is scene->visible on the physical panel. It is not ACK timing, and "
                   "visible cadence is not transport FPS."),
    }


def analyse_frames(frames: Sequence[Path], monitor_quad: Quad, ditoo_quad: Quad, fps: float) -> dict:
    """Decode every extracted footage frame and correlate. One pass, no frame retained."""
    monitor, ditoo = [], []
    for path in frames:
        image = read_frame(path)
        monitor.append(decode_region(image, monitor_quad, mirrored=False))
        ditoo.append(decode_region(image, ditoo_quad, mirrored=True))
    report = analyse(monitor, ditoo, fps)
    report["frames"] = len(frames)
    return report


def correlate_with_trial(report: dict, trial_result: dict) -> dict:
    """Line the optical result up against the trial's own source-identity evidence.

    Deliberately reports the four cadences side by side instead of reducing them to one number.
    Collapsing them is the exact mistake W9A and W9B exist to prevent.
    """
    identity = trial_result.get("sourceIdentity", {})
    return {
        "source_acquired": identity.get("lastAcquiredSourceId"),
        "scheduler_selected": identity.get("selectedCount"),
        "scheduler_skipped": identity.get("skippedBetweenSelections"),
        "scheduler_duplicate_selections": identity.get("duplicateSelections"),
        "transport_frames_acked": trial_result.get("frames"),
        "transport_fps": trial_result.get("effectiveFps"),
        "visible_unique_transitions": report.get("visible_unique_transitions"),
        "visible_repeat_frames": report.get("visible_repeat_frames"),
        "scene_to_visible_latency_ms": report.get("scene_to_visible_latency_ms"),
        "caveat": ("Four separate cadences: camera/source, scheduler selection, transport "
                   "completion and physical display. Never infer panel refresh from ACK rate."),
    }
