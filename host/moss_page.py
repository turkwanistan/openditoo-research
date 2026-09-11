"""Pocket Moss: a small WSL-owned character page; Runtime 013 uses the v4 art/animation pass.

All character pixels come from text-authored Pixel Animation Lab assets. The page owns only
presentation state: passive behavior, selector state, current authored sequence and bounded
telemetry. It has no Bluetooth, Host, persistence, needs/health or Terrarium dependency.
"""
from __future__ import annotations

from pathlib import Path
import random

from host import frame_stream
from host.pixel_animation import PixelAnimation, load_animation
from host.pixel_art import load_sprite

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets/pocket_moss/v4"
NOMINAL_ACK_MS = 62  # timing display/hold floor only; physical panel FPS remains unmeasured
MODE_NORMAL = "normal"
MODE_SELECTOR = "selector"
MODE_ACTION = "action_animation"
ACTIONS = ("pet", "dance", "kisses", "back")

# Tiny 3x3 selector glyphs, one visible at a time in the otherwise-unused upper-right corner.
GLYPHS = {
    "pet": (("#.#", ".#.", "#.#"), (245, 217, 171)),
    "dance": ((".##", ".#.", "##."), (85, 255, 255)),
    "kisses": (("#.#", "###", ".#."), (255, 85, 170)),
    "back": (("#..", "###", "#.."), (170, 170, 170)),
}


class MossPage:
    name = "moss"
    rate_mode = frame_stream.SESSION_PROFILE_STREAMING

    def __init__(self, *, seed: int = 1, asset_root: Path = ASSET_ROOT) -> None:
        self.asset_root = Path(asset_root)
        self._rng = random.Random(seed)
        self.idle = load_sprite(self.asset_root / "sprites/idle.json")
        self.animations: dict[str, PixelAnimation] = {
            name: load_animation(self.asset_root / "animations" / f"{name}.json")
            for name in ("look", "loaf", "sleep-wake", "pet", "dance", "kisses")
        }
        self.mode = MODE_NORMAL
        self.selector_index = 0
        self._active_name: str | None = None
        self._active: PixelAnimation | None = None
        self._step_index = 0
        self._step_acked = False
        self._step_due_ms: int | None = None
        self._last_render_ms = 0
        self._next_passive_ms = 4500
        self._passive_state = "idle"
        self.enter_count = 0
        self.exit_count = 0
        self.frames_acked = 0
        self.interaction_count = 0
        self.navigation_consumed = 0
        self.passive_sequences = 0
        self.completed_actions = 0

    def on_enter(self) -> None:
        self.enter_count += 1

    def on_exit(self) -> None:
        self.exit_count += 1

    @property
    def selected_action(self) -> str:
        return ACTIONS[self.selector_index]

    def _schedule_passive(self, now_ms: int) -> None:
        # Moss should often simply sit there. The long quiet interval is deliberate.
        self._next_passive_ms = now_ms + self._rng.randint(4500, 11000)
        self._passive_state = "idle"

    def _start(self, name: str) -> None:
        self._active_name = name
        self._active = self.animations[name]
        self._step_index = 0
        self._step_acked = False
        self._step_due_ms = None
        phase = self._active.steps[0].phase
        self._passive_state = phase if self.mode == MODE_NORMAL else self._passive_state

    def _finish_active(self, now_ms: int) -> None:
        was_action = self.mode == MODE_ACTION
        self._active_name = None
        self._active = None
        self._step_index = 0
        self._step_acked = False
        self._step_due_ms = None
        if was_action:
            self.mode = MODE_SELECTOR
            self.completed_actions += 1
        else:
            self._schedule_passive(now_ms)

    def _advance_if_due(self, now_ms: int) -> None:
        if self._active is None or not self._step_acked or self._step_due_ms is None:
            return
        if now_ms < self._step_due_ms:
            return
        if self._step_index + 1 >= len(self._active.steps):
            self._finish_active(now_ms)
            return
        # Never catch up multiple authored poses after a stall: one due transition per render.
        self._step_index += 1
        self._step_acked = False
        self._step_due_ms = None
        if self.mode == MODE_NORMAL:
            self._passive_state = self._active.steps[self._step_index].phase

    def _maybe_begin_passive(self, now_ms: int) -> None:
        if self.mode != MODE_NORMAL or self._active is not None or now_ms < self._next_passive_ms:
            return
        roll = self._rng.random()
        name = "look" if roll < 0.62 else "loaf" if roll < 0.90 else "sleep-wake"
        self.passive_sequences += 1
        self._start(name)

    def _base_rgb(self) -> bytes:
        if self._active is None:
            return self.idle.rgb888
        step = self._active.steps[self._step_index]
        return self._active.sprites[step.sprite_ref].rgb888

    @staticmethod
    def _glyph_overlay(rgb: bytes, action: str) -> bytes:
        rows, color = GLYPHS[action]
        out = bytearray(rgb)
        for gy, row in enumerate(rows):
            for gx, value in enumerate(row):
                if value != "#":
                    continue
                x, y = 13 + gx, gy
                offset = (y * 16 + x) * 3
                out[offset:offset + 3] = bytes(color)
        return bytes(out)

    def render(self, now_ms: int) -> bytes:
        self._last_render_ms = int(now_ms)
        self._advance_if_due(self._last_render_ms)
        self._maybe_begin_passive(self._last_render_ms)
        rgb = self._base_rgb()
        if self.mode == MODE_SELECTOR:
            rgb = self._glyph_overlay(rgb, self.selected_action)
        if len(rgb) != frame_stream.FRAME_BYTES:
            raise RuntimeError(f"Moss frame length drifted: {len(rgb)}")
        return rgb

    def frame_sent(self) -> None:
        self.frames_acked += 1
        if self._active is None or self._step_acked:
            return
        step = self._active.steps[self._step_index]
        self._step_acked = True
        self._step_due_ms = self._last_render_ms + max(1, step.hold_acks) * NOMINAL_ACK_MS

    def handle_navigation(self, direction: int, _event: dict) -> bool:
        if self.mode == MODE_NORMAL:
            return False
        self.navigation_consumed += 1
        if self.mode == MODE_SELECTOR:
            self.selector_index = (self.selector_index + (1 if direction > 0 else -1)) % len(ACTIONS)
        # During an action the arrows are deliberately swallowed so they can never leak to
        # the global carousel while the bounded reaction is in progress.
        return True

    def handle_input(self, event: dict) -> str:
        if event.get("type") != "lever_candidate":
            return "ignored"
        if self.mode == MODE_NORMAL:
            self.mode = MODE_SELECTOR
            self.selector_index = 0
            return "selector_enter"
        if self.mode == MODE_ACTION:
            return "action_busy"
        action = self.selected_action
        if action == "back":
            self.mode = MODE_NORMAL
            self._schedule_passive(self._last_render_ms)
            return "selector_back"
        self.mode = MODE_ACTION
        self.interaction_count += 1
        self._start(action)
        return f"action_{action}"

    def telemetry(self) -> dict:
        step = None
        phase = None
        if self._active is not None:
            authored = self._active.steps[self._step_index]
            step, phase = self._step_index, authored.phase
        return {
            "mode": self.mode,
            "behavior_state": self._passive_state,
            "active_animation": self._active_name,
            "step": step,
            "phase": phase,
            "selected_action": self.selected_action if self.mode == MODE_SELECTOR else None,
            "frames_acked": self.frames_acked,
            "interactions": self.interaction_count,
            "completed_actions": self.completed_actions,
            "passive_sequences": self.passive_sequences,
            "navigation_consumed": self.navigation_consumed,
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
        }
