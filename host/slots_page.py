"""Tiny procedural three-reel slots page for high-FPS interactive acceptance.

No image generation or external assets are required: every symbol is an explicit 5x5 matrix.
The page advances motion only after an ACKed frame, stops exactly one reel per short lever
input, and owns its state independently of any Host session so a profile rollover/reclaim does
not reset the game.
"""
from __future__ import annotations

import random

from host import frame_stream

WIDTH = HEIGHT = 16
REEL_WIDTH = 5
REEL_COUNT = 3
SPARE_X = 15
SYMBOL_HEIGHT = 5
SYMBOL_PITCH = 6  # one blank scanline between symbols in the cyclic strip

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
GREEN = (0, 255, 85)
GREY = (85, 85, 85)

# Deliberately chunky 5x5 glyphs that survive the Ditoo's 16x16 scale.
SYMBOLS = (
    ("seven", RED, (
        "#####",
        "...##",
        "..##.",
        ".##..",
        ".##..",
    )),
    ("diamond", CYAN, (
        "..#..",
        ".###.",
        "#####",
        ".###.",
        "..#..",
    )),
    ("bar", YELLOW, (
        "#####",
        "#...#",
        "#####",
        "#...#",
        "#####",
    )),
    ("cherry", MAGENTA, (
        "...#.",
        "..#..",
        ".#.#.",
        "##.##",
        ".#.#.",
    )),
    ("star", WHITE, (
        "..#..",
        "#####",
        ".###.",
        "#.#.#",
        "..#..",
    )),
)
STRIP_HEIGHT = len(SYMBOLS) * SYMBOL_PITCH


def _strip_pixel(strip_y: int, x: int) -> tuple[int, int, int]:
    strip_y %= STRIP_HEIGHT
    symbol_index, local_y = divmod(strip_y, SYMBOL_PITCH)
    if local_y >= SYMBOL_HEIGHT:
        return BLACK
    _name, color, rows = SYMBOLS[symbol_index]
    return color if rows[local_y][x] == "#" else BLACK


class SlotsPage:
    """ACK-paced three-reel slots state machine.

    Initial entry is already spinning, matching the intended physical interaction: page over
    to slots, see three moving reels, then pull the lever three times to stop them left-to-
    right. Once all reels are stopped, the next short pull starts a fresh round.
    """

    name = "slots"
    rate_mode = frame_stream.SESSION_PROFILE_STREAMING

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.round = 0
        self.positions = [0, 0, 0]
        # Different integer scanline steps keep the reels visibly independent without using
        # wall-clock catch-up or subpixel state that cannot be represented on 16x16.
        self.steps = [1, 2, 3]
        self.spinning = [False, False, False]
        self.enter_count = 0
        self.exit_count = 0
        self.frames_acked = 0
        self.last_result: tuple[str, str, str] | None = None
        self.start_round()

    def start_round(self) -> None:
        self.round += 1
        self.positions = [self._rng.randrange(STRIP_HEIGHT) for _ in range(REEL_COUNT)]
        self.spinning = [True] * REEL_COUNT
        self.last_result = None

    def on_enter(self) -> None:
        self.enter_count += 1

    def on_exit(self) -> None:
        self.exit_count += 1

    def handle_input(self, event: dict) -> str:
        if event.get("type") != "lever_candidate":
            return "ignored"
        for index, active in enumerate(self.spinning):
            if active:
                self.spinning[index] = False
                if not any(self.spinning):
                    self.last_result = tuple(self._symbol_at_center(i) for i in range(REEL_COUNT))
                return f"stopped_reel_{index + 1}"
        self.start_round()
        return "new_round"

    def _symbol_at_center(self, reel: int) -> str:
        # Use the panel center scanline as the deterministic visible stop result.
        strip_y = (self.positions[reel] + HEIGHT // 2) % STRIP_HEIGHT
        symbol_index = (strip_y // SYMBOL_PITCH) % len(SYMBOLS)
        return SYMBOLS[symbol_index][0]

    def render(self, _now_ms: int) -> bytes:
        pixels = [BLACK] * (WIDTH * HEIGHT)
        for reel in range(REEL_COUNT):
            base_x = reel * REEL_WIDTH
            position = self.positions[reel]
            for y in range(HEIGHT):
                strip_y = position + y
                for x in range(REEL_WIDTH):
                    pixels[y * WIDTH + base_x + x] = _strip_pixel(strip_y, x)

        # Three tiny state lamps in the spare right-most column. Grey = spinning, green =
        # stopped. They make one-at-a-time stopping obvious without consuming reel width.
        for reel, y in enumerate((2, 7, 12)):
            pixels[y * WIDTH + SPARE_X] = GREEN if not self.spinning[reel] else GREY
        return b"".join(bytes(rgb) for rgb in pixels)

    def frame_sent(self) -> None:
        self.frames_acked += 1
        for index in range(REEL_COUNT):
            if self.spinning[index]:
                self.positions[index] = (self.positions[index] + self.steps[index]) % STRIP_HEIGHT

    def telemetry(self) -> dict:
        return {
            "round": self.round,
            "state": "spinning" if any(self.spinning) else "result",
            "stopped_reels": sum(not value for value in self.spinning),
            "positions": list(self.positions),
            "frames_acked": self.frames_acked,
            "result": list(self.last_result) if self.last_result is not None else None,
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
        }
