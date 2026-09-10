"""Transport-agnostic profile/page orchestration for the OpenDitoo successor runtime.

The orchestrator is intentionally small and injectable: low-rate and high-rate session runners
remain separate, but they share one buffered physical-input mailbox and durable page objects.
A Host session can end/reopen without becoming a page lifecycle event; only actual Left/Right
navigation fires page on_exit/on_enter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from host.interactive_pages import BufferedButtonEvents, InteractivePageDriver, RATE_MODES

SessionRunner = Callable[[InteractivePageDriver], dict]

RENEW_SAME_PAGE = {
    "lifetime_expired": {"stopped_clean"},
    "budget_exhausted": {"stopped_clean"},
    # Exact-unit BTN-2/BTN-7 evidence: arrow 0x09 / lever 0xBD may make the Host yield
    # the canvas. Runtime 006 already reclaims this exact terminal pair. Preserve page
    # state and open a fresh child session; no other non-clean outcome is renewable.
    "canvas_invalidated": {"stopped_clean", "stopped_yielded_to_stock"},
}
CLEAN_STOPS = {"operator_stop", "outer_budget_exhausted", "outer_lifetime_expired"}


@dataclass(frozen=True)
class SessionRecord:
    sequence: int
    page: str
    rate_mode: str
    terminal_reason: str | None
    outcome: str | None
    navigation_direction: int | None


class ProfilePageOrchestrator:
    """Sequentially run exactly one page/profile session at a time."""

    def __init__(self, pages: list, events: BufferedButtonEvents,
                 runners: dict[str, SessionRunner], *, monotonic=None) -> None:
        if not pages:
            raise ValueError("at least one page is required")
        names = [page.name for page in pages]
        if len(set(names)) != len(names):
            raise ValueError("page names must be unique")
        missing = {page.rate_mode for page in pages} - set(runners)
        unknown = {page.rate_mode for page in pages} - set(RATE_MODES)
        if unknown:
            raise ValueError(f"unknown page rate modes: {sorted(unknown)}")
        if missing:
            raise ValueError(f"missing session runners for: {sorted(missing)}")

        self.pages = pages
        self.events = events
        self.runners = dict(runners)
        driver_kwargs = {} if monotonic is None else {"monotonic": monotonic}
        self.drivers = [InteractivePageDriver(page, events, **driver_kwargs) for page in pages]
        self.index = 0
        self.records: list[SessionRecord] = []
        self.session_sequence = 0
        self.profile_transitions = 0
        self.page_transitions = 0
        self.session_reclaims = 0
        self.status = "ready"
        self.last_error: str | None = None

    @property
    def driver(self) -> InteractivePageDriver:
        return self.drivers[self.index]

    @property
    def page(self):
        return self.pages[self.index]

    def _navigate(self, direction: int) -> None:
        old_index = self.index
        old = self.driver
        old.exit()
        self.index = (self.index + direction) % len(self.pages)
        new = self.driver
        if self.index != old_index:
            self.page_transitions += 1
            if old.page.rate_mode != new.page.rate_mode:
                self.profile_transitions += 1
        new.enter()

    def run(self, *, max_sessions: int = 100,
            stop_requested: Callable[[], bool] = lambda: False) -> dict:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self.status = "running"
        self.driver.enter()

        while self.session_sequence < max_sessions and not stop_requested():
            self.session_sequence += 1
            driver = self.driver
            runner = self.runners[driver.page.rate_mode]
            result = runner(driver)
            reason = result.get("terminal_reason")
            outcome = result.get("outcome")
            navigation = driver.navigation
            self.records.append(SessionRecord(
                sequence=self.session_sequence,
                page=driver.page.name,
                rate_mode=driver.page.rate_mode,
                terminal_reason=reason,
                outcome=outcome,
                navigation_direction=None if navigation is None else navigation.direction,
            ))
            del self.records[:-100]

            if reason == "page_transition":
                navigation = driver.take_navigation()
                if navigation is None:
                    self.status = "failed"
                    self.last_error = "PAGE_TRANSITION_WITHOUT_NAVIGATION"
                    break
                self._navigate(navigation.direction)
                continue

            if reason in RENEW_SAME_PAGE and outcome in RENEW_SAME_PAGE[reason]:
                # Session boundary only. The page object and its driver remain selected and
                # entered, so game state survives a normal rollover or exact known canvas yield.
                if reason == "canvas_invalidated":
                    self.session_reclaims += 1
                continue

            if reason in CLEAN_STOPS and outcome == "stopped_clean":
                self.status = "stopped"
                break

            self.status = "failed"
            self.last_error = result.get("detail") or reason or "SESSION_FAILED"
            break
        else:
            self.status = "stopped" if stop_requested() else "session_ceiling"

        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "current_page": self.page.name,
            "current_rate_mode": self.page.rate_mode,
            "session_sequence": self.session_sequence,
            "page_transitions": self.page_transitions,
            "profile_transitions": self.profile_transitions,
            "session_reclaims": self.session_reclaims,
            "buffered_inputs": self.events.pending_count,
            "last_error": self.last_error,
            "page_state": self.page.telemetry(),
            "recent_sessions": [record.__dict__ for record in self.records[-10:]],
        }
