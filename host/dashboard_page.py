"""Low-rate MCP dashboard adapter for the interactive page/profile successor.

The accepted activity renderer remains the pixel/source authority. This wrapper only exposes it
through the page contract so the outer orchestrator can treat Dashboard and high-rate pages as
peer selections without changing dashboard collection or pulse semantics.
"""
from __future__ import annotations

from host import activity_session, frame_stream


class DashboardPage:
    name = "dashboard"
    rate_mode = frame_stream.SESSION_PROFILE_ACTIVITY

    def __init__(self, config: dict, state: dict, renderer=None) -> None:
        self.inner = renderer or activity_session.LiveActivityRenderer(config, state)
        self.last_from_pulse = False
        self.enter_count = 0
        self.exit_count = 0
        self.background_polls = 0
        self.hidden_pulses_dropped = 0

    def on_enter(self) -> None:
        self.enter_count += 1
        # Returning from another page should collect fresh state on the first dashboard tick.
        # This does not increase steady-state collection cadence.
        self.inner.next_collect_ms = 0

    def on_exit(self) -> None:
        self.exit_count += 1
        # A pulse is an ephemeral visual event, not durable page state. If navigation hides
        # the dashboard mid-pulse, never resume that old animation on a later return.
        self.drop_pulse()

    def drop_pulse(self) -> None:
        """Discard an in-flight pulse (hidden page, or a multi-second device outage)."""
        if getattr(self.inner, "pulse_step", None) is not None:
            self.hidden_pulses_dropped += 1
        if hasattr(self.inner, "pulse_step"):
            self.inner.pulse_step = None
        if hasattr(self.inner, "pulse_sources"):
            self.inner.pulse_sources.clear()

    def background_tick(self, now_ms: int) -> bool:
        """Keep source cursors/current status fresh while another page owns the display.

        The inner renderer already owns the multi-second collection cadence. Avoid even the
        render work when its next collection is not due. Any activity discovered while hidden
        is intentionally consumed into status/history but its visual pulse is dropped, matching
        Runtime 006's no-stale-pulse-on-return behavior.
        """
        if now_ms < int(getattr(self.inner, "next_collect_ms", 0)):
            return False
        _rgb, from_pulse = self.inner(now_ms)
        self.background_polls += 1
        if from_pulse:
            self.drop_pulse()
        return bool(from_pulse)

    def render(self, now_ms: int) -> bytes:
        rgb, from_pulse = self.inner(now_ms)
        self.last_from_pulse = bool(from_pulse)
        return rgb

    def handle_input(self, _event: dict) -> None:
        return None

    def frame_sent(self) -> None:
        self.inner.frame_sent()

    def telemetry(self) -> dict:
        return {
            "pulse_step": self.inner.pulse_step,
            "pulse_sources": sorted(self.inner.pulse_sources),
            "next_collect_ms": self.inner.next_collect_ms,
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
            "background_polls": self.background_polls,
            "hidden_pulses_dropped": self.hidden_pulses_dropped,
        }
