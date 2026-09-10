"""Interactive high-rate page dispatch over OpenDitoo's existing ACK-clock stream path.

This is a thin successor seam: transport semantics remain in ``frame_stream.stream_session``;
this module supplies a page renderer, pumps buffered physical input between ACKs, and asks the
stream loop to stop cleanly when Left/Right requests a page/profile transition.
"""
from __future__ import annotations

import json
import urllib.error

from host import frame_stream
from host.interactive_pages import InteractivePageDriver, InteractiveStreamRenderer

# HF3-004 (exact unit): a simple Slots frame ACKed in 21 ms, so dispatching on the ACK put the next
# frame inside the Host's 40 ms floor -> terminal HTTP 429. W8/W10 proved a 50 ms client dispatch
# floor over the 40 ms Host floor; the interactive path now uses the same margin.
CLIENT_MIN_DISPATCH_MS = 50


class HostConfirmedYield(Exception):
    """A send hit the Host's SESSION_CANVAS_INVALIDATED and the Host's own record confirms it."""


class InteractiveTransport:
    """Client dispatch floor + the webcam Studio's Host-confirmed stock-yield rule.

    A Play-direction lever pull (0xBD) usually lands while a frame is in flight at ACK-clock rates,
    so the Host answers the send with 409 SESSION_CANVAS_INVALIDATED. Exactly as the accepted W10
    Studio does, that is the known canvas yield only if the Host then reports the session ended
    canvas_invalidated / stopped_yielded_to_stock; anything else stays an ambiguous fault.
    """

    def __init__(self, inner, clock, sleep, min_dispatch_ms: int = CLIENT_MIN_DISPATCH_MS) -> None:
        self.inner, self.clock, self.sleep, self.min_dispatch_ms = inner, clock, sleep, min_dispatch_ms
        self.last_dispatch_ms = None
        self.confirmed_yield = False

    def open(self, manifest):
        return self.inner.open(manifest)

    def poll_reports(self):
        return self.inner.poll_reports()

    def close(self, reason):
        return self.inner.close(reason)

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        if self.last_dispatch_ms is not None:
            wait = self.last_dispatch_ms + self.min_dispatch_ms - self.clock()
            if wait > 0:
                self.sleep(wait)
        self.last_dispatch_ms = self.clock()
        try:
            return self.inner.send_frame(rgb, expected_packet_sha256)
        except urllib.error.HTTPError as exc:
            if exc.code == 409 and _error_code(exc) == "SESSION_CANVAS_INVALIDATED" and any(
                    r.get("kind") == "session_ended" and r.get("reason") == "canvas_invalidated"
                    and r.get("outcome") == "stopped_yielded_to_stock" for r in self._reports()):
                self.confirmed_yield = True
                raise HostConfirmedYield("SESSION_CANVAS_INVALIDATED;host_confirmed") from exc
            raise

    def _reports(self) -> list[dict]:
        try:
            return self.inner.poll_reports()
        except Exception:
            return []  # cannot confirm -> stays unknown


def _error_code(exc: urllib.error.HTTPError) -> str | None:
    try:
        return json.loads(exc.read(4096) or b"{}").get("errorCode")
    except (ValueError, OSError):
        return None


def run_interactive_stream(manifest, stream: dict, transport, clock, sleep,
                           driver: InteractivePageDriver, claim=None,
                           stop_requested=None, background_tick=None) -> dict:
    if driver.page.rate_mode != frame_stream.SESSION_PROFILE_STREAMING:
        raise frame_stream.SessionError(
            "INTERACTIVE_PAGE_RATE_MODE",
            f"page {driver.page.name!r} is not streaming_ack_clock")
    if stream.get("session_profile") != frame_stream.SESSION_PROFILE_STREAMING:
        raise frame_stream.SessionError(
            "INTERACTIVE_STREAM_PROFILE",
            "interactive high-rate pages require streaming_ack_clock")

    # A stationary game/result screen still polls inputs and Host state, but it does not need
    # the generic stream loop's 10 ms idle heartbeat. 50 ms keeps button response snappy while
    # reducing no-pixel-change control traffic roughly fivefold. Moving-frame ACK cadence is
    # unchanged.
    stream = {**stream, "idle_poll_interval_ms": max(50, int(stream.get("idle_poll_interval_ms", 50)))}
    renderer = InteractiveStreamRenderer(
        driver,
        playback_interval_ms=int(stream.get(
            "playback_interval_ms", frame_stream.STREAMING_MIN_PLAYBACK_INTERVAL_MS)),
        background_tick=background_tick,
    )
    # Page selection lifetime is intentionally above Host-session lifetime. A canvas
    # invalidation or bounded session rollover may reopen the same page and must not fire
    # page-level on_exit/on_enter hooks or reset game state. The outer orchestrator owns
    # those hooks when navigation actually changes the selected page.
    driver.enter()
    def should_stop() -> bool:
        return driver.transition_requested() or bool(stop_requested and stop_requested())

    paced = InteractiveTransport(transport, clock, sleep)
    result = frame_stream.stream_session(
        manifest,
        None,
        stream,
        paced,
        clock,
        sleep,
        claim=claim,
        renderer=renderer,
        stop_requested=should_stop,
        stop_reason="page_transition",
    )
    if paced.confirmed_yield and result.get("terminal_reason") == "transport_fault":
        # The exact known canvas yield, confirmed by the Host's own session record.
        result.update(terminal_reason="canvas_invalidated", outcome="stopped_yielded_to_stock",
                      detail="host-confirmed yield during send: " + str(result.get("detail")))
    if result.get("terminal_reason") == "page_transition" and driver.navigation is None:
        result["terminal_reason"] = "operator_stop"
        result["detail"] = "external stop requested"

    result["page"] = driver.page.name
    result["page_state"] = driver.page.telemetry()
    result["input_state"] = driver.snapshot()
    if driver.navigation is not None:
        result["navigation"] = {
            "direction": driver.navigation.direction,
            "seq": driver.navigation.event.get("seq"),
            "epoch": driver.navigation.event.get("epoch"),
            "type": driver.navigation.event.get("type"),
        }
    else:
        result["navigation"] = None
    return result
