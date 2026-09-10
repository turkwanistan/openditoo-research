"""Page-generic interactive state for OpenDitoo successor runtimes.

This module is deliberately transport-free. It gives a page a durable state object, preserves
button events across Host/profile transitions, and adapts a high-rate page to the renderer
contract used by ``frame_stream.stream_session``. Runtime 006 stays untouched on main.

The important input rule is that ``ButtonEvents.poll()`` may return more than one already-
consumed NDJSON event at once. A navigation event ends the current page session, so any later
events from the same batch must be buffered in memory and handed to the next page rather than
silently lost or incorrectly applied to the old page.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Callable, Protocol

from host import frame_stream

RATE_ACTIVITY = frame_stream.SESSION_PROFILE_ACTIVITY
RATE_STREAMING = frame_stream.SESSION_PROFILE_STREAMING
RATE_MODES = (RATE_ACTIVITY, RATE_STREAMING)
NAVIGATION_TYPES = {"nav_left": -1, "nav_right": 1}
LEVER_TYPE = "lever_candidate"


class EventSource(Protocol):
    def poll(self) -> list[dict]: ...


class InteractivePage(Protocol):
    name: str
    rate_mode: str

    def on_enter(self) -> None: ...
    def on_exit(self) -> None: ...
    def render(self, now_ms: int) -> bytes: ...
    def handle_input(self, event: dict) -> str | None: ...
    def frame_sent(self) -> None: ...
    def telemetry(self) -> dict: ...


@dataclass(frozen=True)
class NavigationRequest:
    direction: int
    event: dict
    observed_at_monotonic: float


class BufferedButtonEvents:
    """At-most-once event mailbox that survives page/profile boundaries.

    The underlying cursor remains authoritative for epoch/sequence/replay handling. This
    wrapper only retains events the cursor already accepted but the current page must not
    consume after it has requested navigation.
    """

    def __init__(self, source: EventSource) -> None:
        self.source = source
        self.pending: deque[dict] = deque()
        self.batches = 0

    def fill(self) -> None:
        if self.pending:
            return
        fresh = list(self.source.poll())
        if fresh:
            self.pending.extend(fresh)
            self.batches += 1

    def pop_buffered(self) -> dict | None:
        return self.pending.popleft() if self.pending else None

    @property
    def pending_count(self) -> int:
        return len(self.pending)


class InteractivePageDriver:
    """Own one page's input/render lifecycle while keeping transport concerns outside it."""

    def __init__(self, page: InteractivePage, events: BufferedButtonEvents,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        if page.rate_mode not in RATE_MODES:
            raise ValueError(f"unknown page rate mode {page.rate_mode!r}")
        self.page = page
        self.events = events
        self.monotonic = monotonic
        self.navigation: NavigationRequest | None = None
        self.actions: list[dict] = []
        self.inputs_consumed = 0
        self.entered = False

    def enter(self) -> None:
        if not self.entered:
            self.page.on_enter()
            self.entered = True

    def exit(self) -> None:
        if self.entered:
            self.page.on_exit()
            self.entered = False

    def pump_inputs(self) -> None:
        """Apply ordered page-local events until navigation creates a profile boundary."""
        if self.navigation is not None:
            return
        # One pump corresponds to one observation opportunity. Fill from the underlying
        # cursor at most once, then consume only that accepted batch. This prevents a tight
        # renderer from pulling a later physical event forward into the same frame.
        self.events.fill()
        while self.events.pending_count:
            event = self.events.pop_buffered()
            assert event is not None
            kind = event.get("type")
            if kind in NAVIGATION_TYPES:
                self.inputs_consumed += 1
                self.navigation = NavigationRequest(
                    NAVIGATION_TYPES[kind], dict(event), self.monotonic())
                return  # later accepted events remain buffered for the next page
            self.inputs_consumed += 1
            if kind == LEVER_TYPE:
                result = self.page.handle_input(event)
                self.actions.append({
                    "seq": event.get("seq"),
                    "epoch": event.get("epoch"),
                    "type": kind,
                    "raw_button": event.get("raw_button"),
                    "result": result,
                    "applied_at_monotonic": self.monotonic(),
                })
                del self.actions[:-50]

    def transition_requested(self) -> bool:
        self.pump_inputs()
        return self.navigation is not None

    def take_navigation(self) -> NavigationRequest | None:
        navigation = self.navigation
        self.navigation = None
        return navigation

    def render(self, now_ms: int) -> bytes:
        self.enter()
        # Input is pumped explicitly by the session/orchestrator before rendering. Keeping
        # render pure avoids two source polls in one ACK opportunity.
        rgb = self.page.render(now_ms)
        if len(rgb) != frame_stream.FRAME_BYTES:
            raise frame_stream.SessionError(
                "INTERACTIVE_PAGE_FRAME_LENGTH",
                f"page {self.page.name!r} returned {len(rgb)} bytes")
        return rgb

    def frame_sent(self) -> None:
        self.page.frame_sent()

    def snapshot(self) -> dict:
        return {
            "page": self.page.name,
            "rate_mode": self.page.rate_mode,
            "inputs_consumed": self.inputs_consumed,
            "buffered_inputs": self.events.pending_count,
            "navigation": None if self.navigation is None else {
                "direction": self.navigation.direction,
                "seq": self.navigation.event.get("seq"),
                "epoch": self.navigation.event.get("epoch"),
                "type": self.navigation.event.get("type"),
                "observed_at_monotonic": self.navigation.observed_at_monotonic,
            },
            "recent_actions": self.actions[-5:],
            "page_state": self.page.telemetry(),
        }


class InteractiveStreamRenderer:
    """Adapter from an interactive page to ``frame_stream.stream_session``.

    Motion is ACK-advanced by the page's ``frame_sent`` callback. That gives games a direct
    relationship between state advancement and frames the Host actually acknowledged, while
    still allowing an input to change state before the next render opportunity.
    """

    def __init__(self, driver: InteractivePageDriver,
                 playback_interval_ms: int = frame_stream.STREAMING_MIN_PLAYBACK_INTERVAL_MS,
                 background_tick: Callable[[int], object] | None = None) -> None:
        if driver.page.rate_mode != RATE_STREAMING:
            raise ValueError("InteractiveStreamRenderer requires a streaming_ack_clock page")
        if playback_interval_ms < frame_stream.STREAMING_MIN_PLAYBACK_INTERVAL_MS:
            raise ValueError("playback interval is below the accepted streaming Host floor")
        self.driver = driver
        self.playback_interval_ms = playback_interval_ms
        self.background_tick = background_tick
        self.last_index = -1

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        if self.background_tick is not None:
            self.background_tick(now_ms)
        return self.driver.render(now_ms), False

    def frame_sent(self) -> None:
        self.driver.frame_sent()
        self.last_index += 1
