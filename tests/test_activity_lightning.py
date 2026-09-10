from __future__ import annotations

import hashlib
import unittest

from host import activity_lightning
from host.activity_ui_data import SIZE, SLOTS


class ActivityLightningTests(unittest.TestCase):
    def setUp(self):
        self.base = bytes(SIZE * SIZE * 3)

    def test_all_ten_stages_are_distinct(self):
        frames = [activity_lightning.apply_stage(self.base, "wsl_mcp", stage)
                  for stage in range(activity_lightning.STAGE_COUNT)]
        hashes = {hashlib.sha256(frame).hexdigest() for frame in frames}
        self.assertEqual(len(hashes), activity_lightning.STAGE_COUNT)

    def test_animation_never_leaves_active_five_pixel_column(self):
        source = "optiplex_mcp"
        base_x = SLOTS[source]
        for stage in range(activity_lightning.STAGE_COUNT):
            out = activity_lightning.apply_stage(self.base, source, stage)
            changed = activity_lightning.changed_pixels(self.base, out)
            self.assertTrue(changed)
            self.assertTrue(all(base_x <= x < base_x + 5 for x, _y in changed), stage)

    def test_faulted_source_does_not_animate(self):
        for stage in range(activity_lightning.STAGE_COUNT):
            self.assertEqual(
                activity_lightning.apply_stage(self.base, "optiplex_lab", stage, faulted=True),
                self.base,
            )

    def test_simultaneous_sources_compose_independently(self):
        stages = {"optiplex_lab": 4, "wsl_mcp": 7}
        combined = activity_lightning.compose(self.base, stages)
        changed = activity_lightning.changed_pixels(self.base, combined)
        lab = SLOTS["optiplex_lab"]
        wsl = SLOTS["wsl_mcp"]
        self.assertTrue(any(lab <= x < lab + 5 for x, _y in changed))
        self.assertTrue(any(wsl <= x < wsl + 5 for x, _y in changed))
        self.assertTrue(all((lab <= x < lab + 5) or (wsl <= x < wsl + 5) for x, _y in changed))

    def test_fault_wins_for_one_source_while_other_source_animates(self):
        combined = activity_lightning.compose(
            self.base,
            {"optiplex_lab": 4, "wsl_mcp": 4},
            faulted={"optiplex_lab"},
        )
        changed = activity_lightning.changed_pixels(self.base, combined)
        wsl = SLOTS["wsl_mcp"]
        self.assertTrue(changed)
        self.assertTrue(all(wsl <= x < wsl + 5 for x, _y in changed))

    def test_descent_reaches_icon_boundary_before_flare(self):
        early = activity_lightning.changed_pixels(
            self.base, activity_lightning.apply_stage(self.base, "wsl_mcp", 0))
        impact = activity_lightning.changed_pixels(
            self.base, activity_lightning.apply_stage(self.base, "wsl_mcp", 4))
        self.assertEqual(max(y for _x, y in early), 0)
        self.assertGreaterEqual(max(y for _x, y in impact), 5)


if __name__ == "__main__":
    unittest.main()

class LightningRendererTests(unittest.TestCase):
    def _state(self):
        from host import mcp_activity
        state = mcp_activity.blank_state()
        for source in state["sources"].values():
            source["source_health"] = "healthy"
            source["last_activity_at"] = "2026-09-10T17:00:00Z"
            source["last_observed_at"] = "2026-09-10T17:00:00Z"
            source["history_complete"] = True
        return state

    def test_no_pulse_matches_accepted_renderer_exactly(self):
        from host import activity_render
        from host.activity_lightning_renderer import LightningActivityRenderer
        state = self._state()
        renderer = LightningActivityRenderer({"poll_seconds": 2}, state)
        renderer.next_collect_ms = 999999
        got, pulse = renderer(1)
        self.assertFalse(pulse)
        self.assertEqual(got, activity_render.render_rgb888(state))

    def test_pulse_advances_only_after_frame_sent(self):
        from host.activity_lightning_renderer import LightningActivityRenderer
        state = self._state()
        renderer = LightningActivityRenderer({"poll_seconds": 2}, state)
        renderer.next_collect_ms = 999999
        renderer.pulse_sources = {"wsl_mcp"}
        renderer.pulse_step = 0
        first, pulse = renderer(1)
        again, _ = renderer(2)
        self.assertTrue(pulse)
        self.assertEqual(first, again)
        renderer.frame_sent()
        second, _ = renderer(3)
        self.assertNotEqual(first, second)

    def test_ten_acks_complete_the_lightning_program(self):
        from host.activity_lightning_renderer import LightningActivityRenderer
        state = self._state()
        renderer = LightningActivityRenderer({"poll_seconds": 2}, state)
        renderer.next_collect_ms = 999999
        renderer.pulse_sources = {"wsl_mcp"}
        renderer.pulse_step = 0
        frames = []
        for _ in range(activity_lightning.STAGE_COUNT):
            frame, pulse = renderer(1)
            self.assertTrue(pulse)
            frames.append(frame)
            renderer.frame_sent()
        self.assertIsNone(renderer.pulse_step)
        self.assertFalse(renderer.pulse_sources)
        self.assertEqual(len({hashlib.sha256(f).digest() for f in frames}), activity_lightning.STAGE_COUNT)

class DashboardBackgroundCollectionTests(unittest.TestCase):
    class Inner:
        def __init__(self):
            self.next_collect_ms = 0
            self.pulse_step = None
            self.pulse_sources = set()
            self.calls = 0
        def __call__(self, now_ms):
            self.calls += 1
            self.next_collect_ms = now_ms + 2000
            self.pulse_step = 0
            self.pulse_sources = {"wsl_mcp"}
            return bytes(16 * 16 * 3), True
        def frame_sent(self): pass

    def test_hidden_collection_consumes_status_but_drops_visual_pulse(self):
        from host.dashboard_page import DashboardPage
        inner = self.Inner()
        page = DashboardPage({}, {}, renderer=inner)
        self.assertTrue(page.background_tick(100))
        self.assertEqual(inner.calls, 1)
        self.assertIsNone(inner.pulse_step)
        self.assertFalse(inner.pulse_sources)
        self.assertEqual(page.hidden_pulses_dropped, 1)
        # Not due: zero extra collector/render work.
        self.assertFalse(page.background_tick(101))
        self.assertEqual(inner.calls, 1)

    def test_page_exit_never_leaves_a_pulse_to_replay_on_return(self):
        from host.dashboard_page import DashboardPage
        inner = self.Inner()
        page = DashboardPage({}, {}, renderer=inner)
        inner.pulse_step = 4
        inner.pulse_sources = {"optiplex_mcp"}
        page.on_enter()
        page.on_exit()
        self.assertIsNone(inner.pulse_step)
        self.assertFalse(inner.pulse_sources)
        self.assertEqual(page.hidden_pulses_dropped, 1)
