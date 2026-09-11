"""Three-reel slots page (v2) for the interactive carousel.

Every symbol is a literal 5x5 pixel matrix with its own shaded palette. Motion advances only
after an ACKed frame. A short lever pull locks the next reel (left, middle, right) onto the next
symbol that will reach the payline; the reel then brakes over a few frames, bounces 1 px and
rests centred, so all three reels always end aligned. The result is fixed at the pull, so the
state machine/telemetry are synchronous; the bounded outcome animation plays once every reel has
settled, and a lever pull only starts the next round after it. Page state is independent of any
Host session, so a profile rollover/reclaim does not reset a round.
"""
from __future__ import annotations

import random

from host import frame_stream

WIDTH = HEIGHT = 16
REEL_WIDTH = 5
REEL_COUNT = 3
SPARE_X = 15
SYMBOL_HEIGHT = 5
SYMBOL_PITCH = 6  # one blank scanline between symbols
PAYLINE_TOP = 6   # payline symbol occupies y6..y10, centred on scanline 8
# Left reel is slow enough to aim ("a little skill"); middle/right are mostly luck.
REEL_SPEEDS = (1, 2, 2)
START_STAGGER = (0, 2, 4)
DIM_OFF_PAYLINE = 0.45

BLACK = (0, 0, 0)

# name -> (palette, rows). h = highlight, # = base, s = shade, g = stem. No outlines, no
# near-black fill: every tone stays bright enough to light an LED (Moss v1 "brown blob").
SYMBOLS = {
    "seven": ({"h": (255, 190, 150), "#": (250, 60, 50), "s": (190, 40, 70)}, (
        "hhhhh",
        "...#s",
        "..#s.",
        ".#s..",
        ".#s..",
    )),
    "diamond": ({"h": (225, 255, 255), "#": (40, 215, 245), "s": (40, 125, 230)}, (
        "..h..",
        ".h#s.",
        "h##ss",
        ".#ss.",
        "..s..",
    )),
    "bar": ({"h": (255, 255, 255), "#": (185, 200, 225), "s": (125, 140, 190)}, (
        "hhhhh",
        "####s",
        ".....",
        "hhhhh",
        "####s",
    )),
    "cherry": ({"g": (120, 225, 70), "h": (255, 160, 200), "#": (240, 45, 120), "s": (175, 35, 105)}, (
        "..gg.",
        ".g..g",
        "h#.h#",
        "##.#s",
        ".s..s",
    )),
    "star": ({"h": (255, 255, 190), "#": (255, 215, 40), "s": (230, 150, 30)}, (
        "..h..",
        "hh#ss",
        ".##s.",
        ".#.s.",
        "#...s",
    )),
}
# 8 stops per reel: 3 cherry, 2 seven, 1 bar/diamond/star, in a different order per reel.
STRIPS = (
    ("seven", "cherry", "bar", "cherry", "diamond", "seven", "star", "cherry"),
    ("cherry", "seven", "diamond", "cherry", "star", "cherry", "seven", "bar"),
    ("star", "cherry", "seven", "bar", "cherry", "diamond", "cherry", "seven"),
)
STRIP_HEIGHT = len(STRIPS[0]) * SYMBOL_PITCH

GOLD = (255, 200, 40)
GOLD_HI = (255, 245, 170)
LAMP_OFF = (90, 90, 110)
LAMP_ON = (60, 235, 110)
LOSE_RED = (230, 60, 60)
LOSE_DIM = (150, 45, 45)
SPARKLE = (255, 255, 220)
COIN = (255, 210, 50)
# The stream never sends an unchanged frame, so an ACK-advanced animation would stall forever on
# two identical consecutive frames: every animation frame differs from the one before it.
ANIM_FRAMES = {"lose": 4, "small": 10, "big": 16, "jackpot": 24}
TIER = {"lose": 0, "small": 1, "big": 2, "jackpot": 3}


def _scale(rgb, k: float):
    return tuple(int(c * k) for c in rgb)


def _lift(rgb, k: float = 0.5):
    return tuple(int(c + (255 - c) * k) for c in rgb)


def symbol_at(reel: int, position: int, y: int = PAYLINE_TOP) -> str:
    """Strip symbol whose rows cover panel scanline ``y`` at reel ``position``."""
    return STRIPS[reel][((y - position) % STRIP_HEIGHT) // SYMBOL_PITCH]


def outcome(symbols) -> str:
    a, b, c = symbols
    if a == b == c:
        return "jackpot" if a == "seven" else "big"
    return "small" if a == b else "lose"


def brake_steps(position: int, speed: int) -> list[int]:
    """Bounded ACK-paced stop plan: run to the next alignment, ease to 1 px, bounce 1 px."""
    remaining = (-position) % SYMBOL_PITCH
    steps = []
    while remaining:
        step = 1 if remaining <= 2 else min(speed, remaining)
        steps.append(step)
        remaining -= step
    return steps + [1, -1]


class SlotsPage:
    """ACK-paced three-reel slots state machine (entry is already spinning)."""

    name = "slots"
    rate_mode = frame_stream.SESSION_PROFILE_STREAMING

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.round = 0
        self.positions = [self._rng.randrange(STRIP_HEIGHT) for _ in range(REEL_COUNT)]
        self.spinning = [False] * REEL_COUNT  # True until the reel's stop is committed
        self.plans: list[list[int] | None] = [None] * REEL_COUNT  # remaining brake steps
        self.delays = [0] * REEL_COUNT
        self.enter_count = 0
        self.exit_count = 0
        self.frames_acked = 0
        self.last_result: tuple[str, str, str] | None = None
        self.outcome: str | None = None
        self.near_miss: tuple[int, int] | None = None
        self.anim_frame = 0
        self.start_round()

    def start_round(self) -> None:
        # Reels restart from where they rested (no teleport), staggered left to right.
        self.round += 1
        self.spinning = [True] * REEL_COUNT
        self.plans = [None] * REEL_COUNT
        self.delays = list(START_STAGGER)
        self.last_result = None
        self.outcome = None
        self.near_miss = None
        self.anim_frame = 0

    def on_enter(self) -> None:
        self.enter_count += 1

    def on_exit(self) -> None:
        self.exit_count += 1

    def settled(self) -> bool:
        return not any(self.spinning) and not any(self.plans)

    def busy(self) -> bool:
        """All stops committed but reels still settling or the outcome still animating."""
        return not any(self.spinning) and (
            not self.settled() or self.anim_frame < ANIM_FRAMES[self.outcome])

    def handle_input(self, event: dict) -> str:
        if event.get("type") != "lever_candidate":
            return "ignored"
        for index, active in enumerate(self.spinning):
            if active:
                self.spinning[index] = False
                self.delays[index] = 0
                self.plans[index] = brake_steps(self.positions[index], REEL_SPEEDS[index])
                if not any(self.spinning):
                    self._resolve()
                return f"stopped_reel_{index + 1}"
        if self.busy():
            return "result_hold"
        self.start_round()
        return "new_round"

    def _final_position(self, reel: int) -> int:
        return self.positions[reel] + sum(self.plans[reel] or ())

    def _resolve(self) -> None:
        finals = [self._final_position(r) for r in range(REEL_COUNT)]
        self.last_result = tuple(symbol_at(r, finals[r]) for r in range(REEL_COUNT))
        self.outcome = outcome(self.last_result)
        # Near miss: left+middle matched and the right reel's very next symbol would have made
        # three (one stop later). Reels move down, so that symbol rests just above the payline.
        alt = self.last_result[:2] + (symbol_at(2, finals[2] + SYMBOL_PITCH),)
        if self.outcome == "small" and outcome(alt) in ("big", "jackpot"):
            self.near_miss = (2, 1)

    def frame_sent(self) -> None:
        self.frames_acked += 1
        for reel in range(REEL_COUNT):
            if self.spinning[reel]:
                if self.delays[reel]:
                    self.delays[reel] -= 1
                else:
                    self.positions[reel] += REEL_SPEEDS[reel]
            elif self.plans[reel]:
                self.positions[reel] += self.plans[reel].pop(0)
            self.positions[reel] %= STRIP_HEIGHT
        if self.settled() and self.outcome is not None and self.anim_frame < ANIM_FRAMES[self.outcome]:
            self.anim_frame += 1

    # -- rendering -------------------------------------------------------------------------
    def _reel_rgb(self, reel: int, x: int, y: int, bright: bool):
        strip_y = (y - self.positions[reel]) % STRIP_HEIGHT
        slot, local_y = divmod(strip_y, SYMBOL_PITCH)
        if local_y >= SYMBOL_HEIGHT:
            return BLACK
        palette, rows = SYMBOLS[STRIPS[reel][slot]]
        ch = rows[local_y][x]
        if ch == ".":
            return BLACK
        rgb = palette[ch]
        return rgb if bright else _scale(rgb, DIM_OFF_PAYLINE)

    def render(self, _now_ms: int) -> bytes:
        px = [BLACK] * (WIDTH * HEIGHT)
        showing = self.settled() and self.outcome is not None
        f = self.anim_frame
        animating = showing and f < ANIM_FRAMES[self.outcome]
        pulse = animating and f % 2 == 0
        win_reels = {"small": (0, 1), "big": (0, 1, 2), "jackpot": (0, 1, 2)}.get(self.outcome, ())
        for reel in range(REEL_COUNT):
            x0 = reel * REEL_WIDTH
            for y in range(HEIGHT):
                on_payline = PAYLINE_TOP <= y < PAYLINE_TOP + SYMBOL_HEIGHT
                bright = on_payline
                if animating and self.near_miss and self.near_miss[0] == reel and f % 2 == 0:
                    # the "one stop away" symbol blinks: +1 = the one above, -1 = the one below
                    bright = bright or (y < PAYLINE_TOP - 1 if self.near_miss[1] == 1 else y > PAYLINE_TOP + SYMBOL_HEIGHT)
                for x in range(REEL_WIDTH):
                    rgb = self._reel_rgb(reel, x, y, bright)
                    if on_payline and reel in win_reels and pulse and rgb != BLACK:
                        rgb = _lift(rgb)
                    px[y * WIDTH + x0 + x] = rgb

        if animating and self.outcome in ("big", "jackpot"):
            for i in range(3):  # sparkles twinkle in the gap rows around the payline
                x = (f * 7 + i * 5) % 15
                y = (PAYLINE_TOP - 1, PAYLINE_TOP + SYMBOL_HEIGHT)[(f + i) % 2]
                px[y * WIDTH + x] = SPARKLE
        if animating and self.outcome == "jackpot":
            for i in range(6):  # coin fountain: each coin rises then falls, staggered
                t = (f + i * 3) % 10
                y = PAYLINE_TOP + 2 - t * (9 - t) // 3
                x = (i * 5 + 2 + (t if i % 2 else -t) // 3) % 15
                if 0 <= y < HEIGHT:
                    px[y * WIDTH + x] = COIN

        # Spare column: three reel lamps on top, gold payline chevron, lamps echo below.
        for reel, y in enumerate((1, 2, 3)):
            px[y * WIDTH + SPARE_X] = LAMP_OFF if self.spinning[reel] or self.plans[reel] else LAMP_ON
        chevron = (GOLD, GOLD_HI, GOLD)
        if animating and self.outcome == "lose":
            chevron = ((LOSE_RED, LOSE_DIM)[f % 2],) * 3
        elif animating and self.outcome != "lose" and pulse:
            chevron = (GOLD_HI, (255, 255, 255), GOLD_HI)
        for i, y in enumerate((7, 8, 9)):
            px[y * WIDTH + SPARE_X] = chevron[i]
        if animating and self.outcome == "jackpot":
            for y in range(11, 16):  # lamp chase under the chevron
                px[y * WIDTH + SPARE_X] = COIN if (y + f) % 3 == 0 else BLACK
        return b"".join(bytes(rgb) for rgb in px)

    def telemetry(self) -> dict:
        return {
            "round": self.round,
            "state": "spinning" if any(self.spinning) else "result",
            "stopped_reels": sum(not value for value in self.spinning),
            "positions": list(self.positions),
            "frames_acked": self.frames_acked,
            "result": list(self.last_result) if self.last_result is not None else None,
            "outcome": self.outcome,
            "busy": self.busy(),
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
        }
