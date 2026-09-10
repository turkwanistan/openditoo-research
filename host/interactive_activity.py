"""Interactive low-rate page dispatch using the accepted activity-session runner."""
from __future__ import annotations

from host import activity_session, frame_stream
from host.interactive_pages import InteractivePageDriver


class ActivityPageRenderer:
    def __init__(self, driver: InteractivePageDriver) -> None:
        if driver.page.rate_mode != frame_stream.SESSION_PROFILE_ACTIVITY:
            raise ValueError("ActivityPageRenderer requires an activity-profile page")
        self.driver = driver

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        rgb = self.driver.render(now_ms)
        return rgb, bool(getattr(self.driver.page, "last_from_pulse", False))

    def frame_sent(self) -> None:
        self.driver.frame_sent()


def run_interactive_activity(manifest, transport, clock, sleep,
                             driver: InteractivePageDriver, claim=None,
                             stop_requested=None) -> dict:
    if driver.page.rate_mode != frame_stream.SESSION_PROFILE_ACTIVITY:
        raise activity_session.SessionError(
            "INTERACTIVE_PAGE_RATE_MODE", f"page {driver.page.name!r} is not activity")
    driver.enter()
    def should_stop() -> bool:
        return driver.transition_requested() or bool(stop_requested and stop_requested())

    result = activity_session.run_session(
        manifest,
        transport,
        ActivityPageRenderer(driver),
        clock,
        sleep,
        claim=claim,
        stop_requested=should_stop,
    )
    # The shared accepted runner calls every external stop `operator_stop`. In the successor
    # the same stop callback is also the clean profile-boundary fence; normalize it only when
    # an actual buffered navigation request proves that is what happened. No inner claim is
    # used for standing/outer-coordinated sub-sessions, so this does not rewrite claim evidence.
    if result.get("terminal_reason") == "operator_stop" and driver.navigation is not None:
        result["terminal_reason"] = "page_transition"
        result["detail"] = "physical navigation requested profile/page transition"
    result["page"] = driver.page.name
    result["page_state"] = driver.page.telemetry()
    result["input_state"] = driver.snapshot()
    return result
