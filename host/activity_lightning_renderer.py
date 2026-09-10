"""Successor MCP live renderer using the side-by-side lightning choreography.

Collection cadence and persisted activity state are intentionally identical to the accepted
LiveActivityRenderer. Only the already-detected pulse's local 10-frame visual program changes.
"""
from __future__ import annotations

from pathlib import Path

from host import activity_lightning, activity_render, mcp_activity


class LightningActivityRenderer:
    def __init__(self, config: dict, state: dict, *, state_path: Path | None = None) -> None:
        self.config = config
        self.state = state
        self.state_path = mcp_activity.STATE_FILE if state_path is None else Path(state_path)
        self.source_poll_ms = max(100, int(float(config.get("poll_seconds", 2.0)) * 1000))
        self.next_collect_ms = 0
        self.pulse_sources: set[str] = set()
        self.pulse_step: int | None = None

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        if now_ms >= self.next_collect_ms:
            try:
                counts = mcp_activity.collect_once(
                    self.config, self.state, poll_seconds=self.source_poll_ms / 1000.0)
            except mcp_activity.SourceError:
                counts = {}
            mcp_activity.save_state(self.state, self.state_path)
            new_pulses = {key for key, value in counts.items() if value}
            if new_pulses:
                self.pulse_sources = new_pulses
                self.pulse_step = 0
            self.next_collect_ms = now_ms + self.source_poll_ms

        base = activity_render.render_rgb888(self.state)
        if self.pulse_step is not None:
            faulted = {
                source_id for source_id in self.pulse_sources
                if self.state["sources"][source_id].get("source_health", "unknown")
                in activity_render.FAULT_HEALTH
            }
            return (
                activity_lightning.compose(
                    base,
                    {source_id: self.pulse_step for source_id in self.pulse_sources},
                    faulted=faulted,
                ),
                True,
            )
        self.pulse_sources.clear()
        return base, False

    def frame_sent(self) -> None:
        if self.pulse_step is None:
            return
        self.pulse_step += 1
        if self.pulse_step >= activity_lightning.STAGE_COUNT:
            self.pulse_step = None
            self.pulse_sources.clear()


def live_renderer(config: dict, state: dict, _manifest=None, *, state_path: Path | None = None) -> LightningActivityRenderer:
    return LightningActivityRenderer(config, state, state_path=state_path)
