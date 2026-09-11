from __future__ import annotations

import unittest

from host.interactive_pages import BufferedButtonEvents, InteractivePageDriver, PageCarousel
from host.moss_page import ACTIONS, MODE_ACTION, MODE_NORMAL, MODE_SELECTOR, MossPage
from host import frame_stream


def event(seq: int, kind: str) -> dict:
    return {"epoch": "moss-test", "seq": seq, "type": kind, "raw_button": kind}


class SequenceEvents:
    def __init__(self, batches): self.batches = list(batches)
    def poll(self): return self.batches.pop(0) if self.batches else []


class DummyPage:
    rate_mode = frame_stream.SESSION_PROFILE_STREAMING
    def __init__(self, name): self.name, self.entered, self.exited = name, 0, 0
    def on_enter(self): self.entered += 1
    def on_exit(self): self.exited += 1
    def render(self, _now): return bytes([1, 2, 3]) * 256
    def handle_input(self, _event): return None
    def frame_sent(self): pass
    def telemetry(self): return {}


class MossPageTests(unittest.TestCase):
    def setUp(self):
        self.page = MossPage(seed=7)

    def test_frame_is_exact_rgb888_and_idle_is_stable(self):
        a = self.page.render(0)
        b = self.page.render(4000)
        self.assertEqual(len(a), 768)
        self.assertEqual(a, b)
        self.assertEqual(self.page.telemetry()["mode"], MODE_NORMAL)

    def test_selector_uses_only_reserved_three_by_three_corner(self):
        base = self.page.render(0)
        self.assertEqual(self.page.handle_input(event(1, "lever_candidate")), "selector_enter")
        shown = self.page.render(1)
        changed = []
        for i in range(256):
            if base[i*3:i*3+3] != shown[i*3:i*3+3]: changed.append((i % 16, i // 16))
        self.assertTrue(changed)
        self.assertTrue(all(x >= 13 and y <= 2 for x, y in changed), changed)
        self.assertEqual(self.page.selected_action, "pet")

    def test_selector_cycles_and_back_restores_normal(self):
        self.page.handle_input(event(1, "lever_candidate"))
        self.assertTrue(self.page.handle_navigation(1, event(2, "nav_right")))
        self.assertEqual(self.page.selected_action, "dance")
        self.page.handle_navigation(-1, event(3, "nav_left"))
        self.assertEqual(self.page.selected_action, "pet")
        for i in range(3): self.page.handle_navigation(1, event(4+i, "nav_right"))
        self.assertEqual(self.page.selected_action, "back")
        self.assertEqual(self.page.handle_input(event(9, "lever_candidate")), "selector_back")
        self.assertEqual(self.page.mode, MODE_NORMAL)
        self.assertFalse(self.page.handle_navigation(1, event(10, "nav_right")))

    def _finish_action(self, action: str):
        self.page.handle_input(event(1, "lever_candidate"))
        while self.page.selected_action != action:
            self.page.handle_navigation(1, event(2, "nav_right"))
        self.assertEqual(self.page.handle_input(event(3, "lever_candidate")), f"action_{action}")
        self.assertEqual(self.page.mode, MODE_ACTION)
        now = 0
        last = None
        for _ in range(30):
            rgb = self.page.render(now)
            if rgb != last:
                self.page.frame_sent()
                last = rgb
            now += 2000
            if self.page.mode == MODE_SELECTOR:
                break
        self.assertEqual(self.page.mode, MODE_SELECTOR)
        self.assertEqual(self.page.completed_actions, 1)
        self.assertEqual(len(self.page.render(now)), 768)

    def test_all_three_actions_complete_back_to_selector(self):
        for action in ("pet", "dance", "kisses"):
            with self.subTest(action=action):
                self.page = MossPage(seed=7)
                self._finish_action(action)

    def test_navigation_is_swallowed_during_action(self):
        self.page.handle_input(event(1, "lever_candidate"))
        self.page.handle_input(event(2, "lever_candidate"))  # pet
        self.assertEqual(self.page.mode, MODE_ACTION)
        self.assertTrue(self.page.handle_navigation(1, event(3, "nav_right")))
        self.assertEqual(self.page.mode, MODE_ACTION)

    def test_passive_behavior_starts_only_after_quiet_window(self):
        self.assertIsNone(self.page.telemetry()["active_animation"])
        self.page.render(4499)
        self.assertIsNone(self.page.telemetry()["active_animation"])
        self.page.render(4500)
        self.assertIn(self.page.telemetry()["active_animation"], {"look", "loaf", "sleep-wake"})
        self.assertEqual(self.page.passive_sequences, 1)

    def test_page_lifecycle_does_not_reset_character_state(self):
        self.page.handle_input(event(1, "lever_candidate"))
        self.page.handle_navigation(1, event(2, "nav_right"))
        selected = self.page.selected_action
        self.page.on_enter(); self.page.on_exit(); self.page.on_enter()
        self.assertEqual(self.page.mode, MODE_SELECTOR)
        self.assertEqual(self.page.selected_action, selected)


class MossCarouselTests(unittest.TestCase):
    def test_normal_navigation_moves_global_carousel(self):
        moss, other = MossPage(seed=1), DummyPage("other")
        carousel = PageCarousel([moss, other])
        self.assertEqual(carousel.handle_navigation(1, event(1, "nav_right")), "navigate")
        self.assertEqual(carousel.page.name, "other")

    def test_selector_navigation_is_consumed_without_page_move(self):
        moss, other = MossPage(seed=1), DummyPage("other")
        carousel = PageCarousel([moss, other])
        moss.handle_input(event(1, "lever_candidate"))
        self.assertEqual(carousel.handle_navigation(1, event(2, "nav_right")), "page_consumed")
        self.assertEqual(carousel.page.name, "moss")
        self.assertEqual(moss.selected_action, "dance")
        self.assertEqual(carousel.page_transitions, 0)

    def test_buffered_selector_nav_then_lever_stays_on_moss_and_orders_inputs_once(self):
        moss, other = MossPage(seed=1), DummyPage("other")
        moss.handle_input(event(0, "lever_candidate"))
        source = SequenceEvents([[event(1, "nav_right"), event(2, "lever_candidate")]])
        driver = InteractivePageDriver(PageCarousel([moss, other]), BufferedButtonEvents(source), monotonic=lambda: 1.0)
        driver.pump_inputs()
        self.assertEqual(driver.page.page.name, "moss")
        self.assertEqual(moss.mode, MODE_ACTION)
        self.assertEqual(moss.telemetry()["active_animation"], "dance")
        self.assertEqual(driver.inputs_consumed, 2)
        self.assertEqual([a["seq"] for a in driver.actions], [1, 2])
        self.assertEqual(driver.events.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
