"""Interactive high-rate page dispatch over OpenDitoo's existing ACK-clock stream path.

This is a thin successor seam: transport semantics remain in ``frame_stream.stream_session``;
this module supplies a page renderer, pumps buffered physical input between ACKs, and asks the
stream loop to stop cleanly when Left/Right requests a page/profile transition.
"""
from __future__ import annotations

from host import frame_stream
from host.interactive_pages import InteractivePageDriver, InteractiveStreamRenderer


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

    result = frame_stream.stream_session(
        manifest,
        None,
        stream,
        transport,
        clock,
        sleep,
        claim=claim,
        renderer=renderer,
        stop_requested=should_stop,
        stop_reason="page_transition",
    )
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
