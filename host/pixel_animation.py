"""ACK-driven authored animation for the reusable OpenDitoo Pixel Animation Lab."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random

from host.pixel_art import PixelArtError, PixelSprite, canonical_json, changed_pixels, load_sprite

ANIMATION_SCHEMA = "openditoo.pixel-animation.v1"
CADENCE_PROFILES = {
    "ideal18": {"kind": "fixed", "interval_ms": 55.556},
    "measured16": {"kind": "fixed", "interval_ms": 61.5},
    "fps10": {"kind": "fixed", "interval_ms": 100.0},
    "fps5": {"kind": "fixed", "interval_ms": 200.0},
    "jitter": {"kind": "jitter", "base_ms": 61.5, "spread_ms": 24.0, "stall_every": 17, "stall_ms": 145.0},
}
MAX_HOLD_ACKS = 600


@dataclass(frozen=True)
class AnimationStep:
    sprite_ref: str
    hold_acks: int
    phase: str


@dataclass(frozen=True)
class PixelAnimation:
    id: str
    loop: bool
    steps: tuple[AnimationStep, ...]
    sprites: dict[str, PixelSprite]
    source_path: Path

    def __post_init__(self) -> None:
        if not self.id or not self.steps:
            raise PixelArtError("animation requires id and at least one step")
        for step in self.steps:
            if step.sprite_ref not in self.sprites:
                raise PixelArtError(f"animation references unknown sprite {step.sprite_ref!r}")
            if step.hold_acks <= 0 or step.hold_acks > MAX_HOLD_ACKS:
                raise PixelArtError(f"invalid hold_acks {step.hold_acks} for {step.sprite_ref}")

    @property
    def total_acks(self) -> int:
        return sum(step.hold_acks for step in self.steps)

    @property
    def canonical_sha256(self) -> str:
        raw = {
            "schema": ANIMATION_SCHEMA, "id": self.id, "loop": self.loop,
            "steps": [[s.sprite_ref, s.hold_acks, s.phase] for s in self.steps],
            "sprites": {key: sprite.canonical_sha256 for key, sprite in sorted(self.sprites.items())},
        }
        return hashlib.sha256(canonical_json(raw).encode()).hexdigest()

    def expanded_step_indices(self) -> list[int]:
        out = []
        for index, step in enumerate(self.steps):
            out.extend([index] * step.hold_acks)
        return out

    def unique_frames(self) -> list[PixelSprite]:
        seen, out = set(), []
        for step in self.steps:
            sprite = self.sprites[step.sprite_ref]
            if sprite.rgb_sha256 not in seen:
                seen.add(sprite.rgb_sha256)
                out.append(sprite)
        return out


def load_animation(path: Path | str) -> PixelAnimation:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PixelArtError(f"{path}: unreadable animation: {exc}") from exc
    if raw.get("schema") != ANIMATION_SCHEMA:
        raise PixelArtError(f"{path}: expected schema {ANIMATION_SCHEMA!r}")
    if raw.get("canvas") != [16, 16]:
        raise PixelArtError(f"{path}: canvas must be [16,16]")
    sequence = raw.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        raise PixelArtError(f"{path}: sequence must be non-empty")
    steps = []
    sprites: dict[str, PixelSprite] = {}
    for item in sequence:
        if not isinstance(item, dict):
            raise PixelArtError(f"{path}: sequence entries must be objects")
        ref = str(item.get("sprite") or "")
        if not ref:
            raise PixelArtError(f"{path}: sequence sprite is required")
        hold = int(item.get("hold_acks", 0))
        phase = str(item.get("phase") or "")
        sprite_path = (path.parent / ref).resolve()
        sprite = load_sprite(sprite_path)
        sprites[ref] = sprite
        steps.append(AnimationStep(ref, hold, phase))
    return PixelAnimation(str(raw.get("id") or ""), bool(raw.get("loop")), tuple(steps), sprites, path)


class AckAnimationPlayer:
    """One authored progression step per ACK opportunity; time never causes catch-up."""

    def __init__(self, animation: PixelAnimation) -> None:
        self.animation = animation
        self.ack_index = 0
        self.loop_count = 0
        self.finished = False

    def reset(self) -> None:
        self.ack_index = self.loop_count = 0
        self.finished = False

    def _logical_index(self) -> int:
        total = self.animation.total_acks
        if self.animation.loop:
            return self.ack_index % total
        return min(self.ack_index, total - 1)

    def step_index(self) -> int:
        logical = self._logical_index()
        cursor = 0
        for index, step in enumerate(self.animation.steps):
            cursor += step.hold_acks
            if logical < cursor:
                return index
        return len(self.animation.steps) - 1

    @property
    def step(self) -> AnimationStep:
        return self.animation.steps[self.step_index()]

    @property
    def sprite(self) -> PixelSprite:
        return self.animation.sprites[self.step.sprite_ref]

    def ack(self) -> None:
        if self.finished:
            return
        before = self.ack_index
        self.ack_index += 1
        total = self.animation.total_acks
        if self.animation.loop:
            if self.ack_index // total > before // total:
                self.loop_count += 1
        elif self.ack_index >= total:
            self.finished = True
            self.ack_index = total - 1

    def snapshot(self) -> dict:
        return {
            "animation": self.animation.id, "ack_index": self.ack_index,
            "step_index": self.step_index(), "sprite": self.sprite.id,
            "phase": self.step.phase, "loop_count": self.loop_count, "finished": self.finished,
        }


def cadence_intervals(profile: str, count: int, *, seed: int = 1) -> list[float]:
    if profile not in CADENCE_PROFILES:
        raise PixelArtError(f"unknown cadence profile {profile!r}")
    if count < 0:
        raise PixelArtError("cadence count must be non-negative")
    spec = CADENCE_PROFILES[profile]
    if spec["kind"] == "fixed":
        return [float(spec["interval_ms"])] * count
    rng = random.Random(seed)
    out = []
    for index in range(count):
        interval = float(spec["base_ms"]) + rng.uniform(-float(spec["spread_ms"]), float(spec["spread_ms"]))
        if spec.get("stall_every") and (index + 1) % int(spec["stall_every"]) == 0:
            interval += float(spec["stall_ms"])
        out.append(round(max(1.0, interval), 3))
    return out


def animation_quality(animation: PixelAnimation) -> dict:
    warnings: list[dict] = []
    adjacent = []
    anchors = []
    for index, step in enumerate(animation.steps):
        sprite = animation.sprites[step.sprite_ref]
        anchors.append(sprite.anchor)
        if index:
            prev = animation.sprites[animation.steps[index - 1].sprite_ref]
            delta = len(changed_pixels(prev, sprite))
            adjacent.append(delta)
            if delta == 0:
                warnings.append({"code": "DUPLICATE_CONSECUTIVE_FRAME", "step": index,
                                 "detail": "use a longer hold instead"})
            if delta > 154:
                warnings.append({"code": "HIGH_FRAME_CHURN", "step": index, "changed_pixels": delta})
            if prev.anchor is not None and sprite.anchor is not None:
                jump = abs(prev.anchor[0] - sprite.anchor[0]) + abs(prev.anchor[1] - sprite.anchor[1])
                if jump > 2:
                    warnings.append({"code": "ANCHOR_JUMP", "step": index, "manhattan": jump})
        if step.hold_acks == 1:
            warnings.append({"code": "ONE_ACK_STEP", "step": index,
                             "detail": "review at slow cadence for accidental flash"})
    seam_delta = None
    if animation.loop and len(animation.steps) > 1:
        last = animation.sprites[animation.steps[-1].sprite_ref]
        first = animation.sprites[animation.steps[0].sprite_ref]
        seam_delta = len(changed_pixels(last, first))
        if seam_delta > 100:
            warnings.append({"code": "LARGE_LOOP_SEAM", "changed_pixels": seam_delta})
    # A->B->A one-step return: report changed coordinates as potential one-frame flicker.
    flickers = []
    for index in range(1, len(animation.steps) - 1):
        a = animation.sprites[animation.steps[index - 1].sprite_ref]
        b = animation.sprites[animation.steps[index].sprite_ref]
        c = animation.sprites[animation.steps[index + 1].sprite_ref]
        if a.rgb888 == c.rgb888 and animation.steps[index].hold_acks == 1:
            flickers.append({"step": index, "pixels": changed_pixels(a, b)})
    if flickers:
        warnings.append({"code": "POTENTIAL_ONE_FRAME_FLICKER", "instances": flickers})
    return {
        "total_authored_steps": len(animation.steps), "total_hold_acks": animation.total_acks,
        "unique_frame_count": len(animation.unique_frames()), "adjacent_changed_pixels": adjacent,
        "loop_seam_changed_pixels": seam_delta, "warnings": warnings,
    }
