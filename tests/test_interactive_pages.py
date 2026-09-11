from __future__ import annotations

from pathlib import Path
import unittest

from host import activity_session, frame_stream
from host.interactive_pages import BufferedButtonEvents, InteractivePageDriver
from host.interactive_stream import run_interactive_stream
from host import slots_page
from host.slots_page import SlotsPage


class SequenceEvents:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    def poll(self):
        self.calls += 1
        return self.batches.pop(0) if self.batches else []


class FakeClock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms

    def sleep(self, ms):
        self.ms += max(0, int(ms))


class AckTimedTransport(activity_session.FakeSessionTransport):
    def __init__(self, clock: FakeClock, ack_ms: int = 60, reports=None):
        super().__init__(reports=reports)
        self.clock = clock
        self.ack_ms = ack_ms

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        result = super().send_frame(rgb, expected_packet_sha256)
        self.clock.ms += self.ack_ms
        return result


class LeverPage:
    name = "lever"
    rate_mode = frame_stream.SESSION_PROFILE_STREAMING

    def __init__(self):
        self.levers = 0
        self.entered = 0
        self.exited = 0
        self.sent = 0

    def on_enter(self): self.entered += 1
    def on_exit(self): self.exited += 1
    def render(self, _now): return bytes([self.sent % 256, 0, 0]) * 256
    def handle_input(self, _event):
        self.levers += 1
        return f"lever_{self.levers}"
    def frame_sent(self): self.sent += 1
    def telemetry(self): return {"levers": self.levers, "sent": self.sent}


def event(seq, kind, raw=None):
    return {"epoch": "e1", "seq": seq, "type": kind, "raw_button": raw or kind}


def manifest(max_frames=50, lifetime=10):
    return activity_session.SessionManifest(
        experiment_id="TEST-INTERACTIVE",
        lifetime_seconds=lifetime,
        min_frame_interval_ms=frame_stream.STREAMING_HOST_FLOOR_MS,
        pulse_freshness_seconds=30,
        poll_interval_ms=10,
        max_frames=max_frames,
        max_application_packets=max_frames * 3,
        max_tx_bytes=max_frames * frame_stream.worst_case_frame_tx_bytes(),
        ack_timeout_ms_per_frame=5000,
        activation_source="offline interactive test",
        host_build_sha256="0" * 64,
        code_hashes={},
        stop_conditions=("transport_fault",),
        acceptance_profile=None,
        path=Path("TEST-INTERACTIVE.json"),
        raw={},
    )


def stream_spec():
    return {
        "session_profile": frame_stream.SESSION_PROFILE_STREAMING,
        "playback_interval_ms": frame_stream.STREAMING_HOST_FLOOR_MS,
        "source_kind": frame_stream.SOURCE_KIND_LIVE,
    }


class BufferedInputTests(unittest.TestCase):
    def test_event_after_navigation_survives_for_next_page(self):
        source = SequenceEvents([[
            event(1, "lever_candidate", "Pause"),
            event(2, "nav_right", "Next"),
            event(3, "lever_candidate", "Play"),
        ]])
        mailbox = BufferedButtonEvents(source)
        first = LeverPage()
        first_driver = InteractivePageDriver(first, mailbox, monotonic=lambda: 1.0)

        self.assertTrue(first_driver.transition_requested())
        self.assertEqual(first.levers, 1)
        self.assertEqual(first_driver.navigation.direction, 1)
        self.assertEqual(mailbox.pending_count, 1)

        second = LeverPage()
        second_driver = InteractivePageDriver(second, mailbox, monotonic=lambda: 2.0)
        second_driver.pump_inputs()
        self.assertEqual(second.levers, 1)
        self.assertIsNone(second_driver.navigation)
        self.assertEqual(mailbox.pending_count, 0)


class SlotsPageTests(unittest.TestCase):
    MAX_BUSY_FRAMES = 8 + max(slots_page.ANIM_FRAMES.values())

    @staticmethod
    def reel_slice(rgb: bytes, reel: int) -> bytes:
        out = bytearray()
        x0 = reel * 5
        for y in range(16):
            for x in range(x0, x0 + 5):
                i = (y * 16 + x) * 3
                out.extend(rgb[i:i + 3])
        return bytes(out)

    @staticmethod
    def tick(page, frames=1, last=None):
        """Drive the page like the stream: an unchanged frame is never sent, so never ACKed."""
        for _ in range(frames):
            rgb = page.render(0)
            if rgb != last:
                page.frame_sent()
                last = rgb
        return last

    def settle(self, page):
        last = None
        for n in range(self.MAX_BUSY_FRAMES + 1):
            if not page.busy():
                return n
            last = self.tick(page, 1, last)
        self.fail("slots result never finished under change-only sending (ACK stall)")

    def play(self, page, gaps):
        for gap in gaps:
            for _ in range(gap):
                page.frame_sent()  # spinning reels change pixels every frame
            page.handle_input(event(0, "lever_candidate"))

    def test_slots_are_true_16x16_and_small_palette(self):
        page = SlotsPage(seed=7)
        rgb = page.render(0)
        self.assertEqual(len(rgb), 16 * 16 * 3)
        colors = {rgb[i:i + 3] for i in range(0, len(rgb), 3)}
        self.assertLessEqual(len(colors), frame_stream.MAX_PALETTE_COLORS)

    def test_symbol_art_is_5x5_shaded_and_never_near_black(self):
        for name, (palette, rows) in slots_page.SYMBOLS.items():
            self.assertEqual([len(r) for r in rows], [5] * 5, name)
            self.assertLessEqual(set("".join(rows)) - {"."}, set(palette), name)
            self.assertGreaterEqual(len(palette), 3, f"{name} needs highlight/base/shade")
            for rgb in palette.values():
                self.assertGreaterEqual(max(rgb), 100, f"{name} {rgb} collapses on the LED panel")
        for strip in slots_page.STRIPS:
            self.assertEqual(sorted(strip), sorted(("cherry",) * 3 + ("seven",) * 2 + ("bar", "diamond", "star")))

    def test_three_levers_stop_exactly_one_reel_each(self):
        page = SlotsPage(seed=7)
        self.assertEqual(page.telemetry()["stopped_reels"], 0)
        self.assertEqual(page.handle_input(event(1, "lever_candidate")), "stopped_reel_1")
        self.assertEqual(page.telemetry()["stopped_reels"], 1)
        self.assertEqual(page.handle_input(event(2, "lever_candidate")), "stopped_reel_2")
        self.assertEqual(page.telemetry()["stopped_reels"], 2)
        self.assertEqual(page.handle_input(event(3, "lever_candidate")), "stopped_reel_3")
        self.assertEqual(page.telemetry()["stopped_reels"], 3)
        self.assertEqual(page.telemetry()["state"], "result")
        self.assertIsNotNone(page.telemetry()["result"])

    def test_every_stop_snaps_to_the_payline_with_a_bounded_brake(self):
        for start in range(slots_page.STRIP_HEIGHT):
            for reel, speed in enumerate(slots_page.REEL_SPEEDS):
                slip = slots_page.SLIP_BACK[reel]
                steps = slots_page.brake_steps(start, speed, slip)
                self.assertLessEqual(len(steps), 8)
                if start % slots_page.SYMBOL_PITCH <= slip:  # just-passed symbol wins
                    self.assertLessEqual(-sum(steps), slip)
                    self.assertGreaterEqual(-sum(steps), 0)
                self.assertTrue(all(abs(step) <= speed for step in steps), steps)  # no catch-up burst
                self.assertEqual((start + sum(steps)) % slots_page.SYMBOL_PITCH, 0)
                self.assertEqual(steps[-2:], [1, -1])  # 1 px overshoot + settle back
        page = SlotsPage(seed=11)
        self.play(page, [9, 5, 4])
        result = page.last_result
        self.settle(page)
        self.assertEqual([p % slots_page.SYMBOL_PITCH for p in page.positions], [0, 0, 0])
        self.assertEqual(tuple(slots_page.symbol_at(r, page.positions[r]) for r in range(3)), result)

    def test_every_reel_spins_a_steady_1px_per_frame(self):
        # Alternating 1/2 px steps juddered on the panel when an ACK arrived late (Runtime 015).
        self.assertEqual(slots_page.REEL_SPEEDS, (1, 1, 1))
        page = SlotsPage(seed=4)
        page.delays = [0, 0, 0]
        for _ in range(60):
            before = list(page.positions)
            page.frame_sent()
            self.assertEqual([(a - b) % slots_page.STRIP_HEIGHT for a, b in zip(page.positions, before)], [1, 1, 1])

    def test_aimed_pull_lands_the_symbol_seen_on_the_payline_despite_input_lag(self):
        # The owner sees a symbol centred on the payline and pulls; the pull lands 1-3 ACKs later.
        # Left reel (1 px/frame) always lands it; the 1.5 px/frame reels mostly do.
        for reel in range(3):
            hits = trials = 0
            for start in range(0, slots_page.STRIP_HEIGHT, slots_page.SYMBOL_PITCH):
                for lag in (1, 2, 3):
                    page = SlotsPage(seed=1)
                    page.positions = [start] * 3
                    page.delays = [0, 0, 0]
                    page.spinning = [i >= reel for i in range(3)]
                    seen = slots_page.symbol_at(reel, start)
                    for _ in range(lag):
                        page.frame_sent()
                    page.handle_input(event(0, "lever_candidate"))
                    hits += slots_page.symbol_at(reel, page._final_position(reel)) == seen
                    trials += 1
            self.assertGreaterEqual(hits / trials, 1.0 if reel == 0 else 0.6, (reel, hits, trials))

    def test_stopped_reel_stays_pixel_stable_while_others_move(self):
        page = SlotsPage(seed=11)
        page.handle_input(event(1, "lever_candidate"))
        for _ in range(8):
            page.frame_sent()
        self.assertFalse(page.plans[0])
        before = self.reel_slice(page.render(0), 0)
        moving_before = self.reel_slice(page.render(0), 1)
        for _ in range(5):
            page.frame_sent()
        self.assertEqual(before, self.reel_slice(page.render(100), 0))
        self.assertNotEqual(moving_before, self.reel_slice(page.render(100), 1))

    def test_result_animates_then_holds_and_next_lever_waits_for_it(self):
        page = SlotsPage(seed=3)
        for seq in range(1, 4):
            page.handle_input(event(seq, "lever_candidate"))
        self.assertTrue(page.busy())
        self.assertEqual(page.handle_input(event(4, "lever_candidate")), "result_hold")
        self.settle(page)
        frozen = page.render(0)
        for _ in range(20):
            page.frame_sent()
        self.assertEqual(frozen, page.render(5000))
        old_round = page.round
        self.assertEqual(page.handle_input(event(5, "lever_candidate")), "new_round")
        self.assertEqual(page.round, old_round + 1)
        self.assertTrue(all(page.spinning))

    def test_page_exit_and_reentry_preserve_round_state(self):
        page = SlotsPage(seed=5)
        page.handle_input(event(1, "lever_candidate"))
        positions = list(page.positions)
        spinning = list(page.spinning)
        page.on_enter()
        page.on_exit()
        page.on_enter()
        self.assertEqual(page.positions, positions)
        self.assertEqual(page.spinning, spinning)
        self.assertEqual(page.telemetry()["stopped_reels"], 1)

    def test_1000_rounds_obey_three_stop_state_machine_under_change_only_sending(self):
        import random
        rng = random.Random(1234)
        page = SlotsPage(seed=1234)
        for round_index in range(1000):
            self.assertTrue(any(page.spinning), round_index)
            for reel in range(3):
                self.tick(page, rng.randrange(0, 12))
                self.assertEqual(page.handle_input(event(round_index * 4 + reel + 1, "lever_candidate")),
                                 f"stopped_reel_{reel + 1}")
                self.assertEqual(page.telemetry()["stopped_reels"], reel + 1)
            self.assertFalse(any(page.spinning))
            self.settle(page)
            self.assertEqual(page.handle_input(event(round_index * 4 + 4, "lever_candidate")), "new_round")

    def test_outcome_rules(self):
        self.assertEqual(slots_page.outcome(("seven",) * 3), "jackpot")
        self.assertEqual(slots_page.outcome(("bar",) * 3), "big")
        self.assertEqual(slots_page.outcome(("cherry", "cherry", "star")), "small")
        self.assertEqual(slots_page.outcome(("star", "cherry", "cherry")), "lose")

    def test_specific_lever_timings_win_and_lose(self):
        # Deterministic from seed 7: frames of spin before each of the three pulls.
        for gaps, want in (([32, 29, 23], "jackpot"), ([22, 29, 13], "big"), ([38, 10, 20], "small"),
                           ([37, 16, 28], "lose")):
            page = SlotsPage(seed=7)
            self.play(page, gaps)
            self.assertEqual(page.outcome, want, gaps)
            self.assertEqual(page.telemetry()["outcome"], want)

    def test_seeded_simulation_win_rates_are_fair(self):
        import random
        rng = random.Random(1)
        page = SlotsPage(seed=1)
        tally = {"lose": 0, "small": 0, "big": 0, "jackpot": 0}
        rounds = 20000
        for _ in range(rounds):
            self.play(page, [rng.randrange(4, 40) for _ in range(3)])
            tally[page.outcome] += 1
            while page.busy():
                page.frame_sent()
            page.handle_input(event(0, "lever_candidate"))
        rate = {k: v / rounds for k, v in tally.items()}
        # Strip math: small 17.6%, three of a kind 7.4% (jackpot 1.6%), any win ~25%.
        self.assertTrue(0.22 <= 1 - rate["lose"] <= 0.28, rate)
        self.assertTrue(0.06 <= rate["big"] + rate["jackpot"] <= 0.09, rate)
        self.assertTrue(0.010 <= rate["jackpot"] <= 0.022, rate)


class InteractiveStreamTests(unittest.TestCase):
    def test_navigation_stops_stream_cleanly_without_extra_send(self):
        clock = FakeClock()
        source = SequenceEvents([[], [], [event(1, "nav_right", "Next")]])
        mailbox = BufferedButtonEvents(source)
        page = LeverPage()
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=60)

        result = run_interactive_stream(
            manifest(), stream_spec(), transport, clock, clock.sleep, driver)

        self.assertEqual(result["terminal_reason"], "page_transition")
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertEqual(result["frames_sent"], 2)
        self.assertEqual(len(transport.frames), 2)
        self.assertEqual(result["navigation"]["direction"], 1)
        self.assertEqual(page.entered, 1)
        self.assertEqual(page.exited, 0)  # session end is not page deselection

    def test_lever_changes_state_before_next_acked_frame(self):
        clock = FakeClock()
        source = SequenceEvents([[event(1, "lever_candidate", "Pause")], [event(2, "nav_left", "Previous")]])
        mailbox = BufferedButtonEvents(source)
        page = LeverPage()
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=70)

        result = run_interactive_stream(
            manifest(), stream_spec(), transport, clock, clock.sleep, driver)

        self.assertEqual(page.levers, 1)
        self.assertEqual(result["frames_sent"], 1)
        self.assertEqual(result["navigation"]["direction"], -1)
        self.assertEqual(result["input_state"]["recent_actions"][0]["result"], "lever_1")

    def test_slow_ack_lowers_rate_without_catchup_sleep_burst(self):
        clock = FakeClock()
        # No navigation: max-frame budget ends the bounded test.
        mailbox = BufferedButtonEvents(SequenceEvents([[]] * 20))
        page = LeverPage()
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=100)
        result = run_interactive_stream(
            manifest(max_frames=5), stream_spec(), transport, clock, clock.sleep, driver)
        self.assertEqual(result["terminal_reason"], "budget_exhausted")
        self.assertEqual(result["frames_sent"], 5)
        self.assertAlmostEqual(result["realized_fps"], 10.0, places=1)
        self.assertEqual(clock.ms, 500)


if __name__ == "__main__":
    unittest.main()

from host.interactive_runtime import ProfilePageOrchestrator
from host.interactive_pages import RATE_ACTIVITY, RATE_STREAMING


class CountingPage:
    def __init__(self, name, rate_mode):
        self.name = name
        self.rate_mode = rate_mode
        self.levers = 0
        self.entered = 0
        self.exited = 0
        self.acked = 0

    def on_enter(self): self.entered += 1
    def on_exit(self): self.exited += 1
    def render(self, _now): return bytes([self.acked % 255, 1, 2]) * 256
    def handle_input(self, _event):
        self.levers += 1
        return f"lever_{self.levers}"
    def frame_sent(self): self.acked += 1
    def telemetry(self): return {"levers": self.levers, "acked": self.acked}


class ProfileOrchestratorTests(unittest.TestCase):
    @staticmethod
    def transition_runner(driver):
        if driver.transition_requested():
            return {"terminal_reason": "page_transition", "outcome": "stopped_clean"}
        driver.render(0)
        driver.frame_sent()
        return {"terminal_reason": "lifetime_expired", "outcome": "stopped_clean"}

    def test_100_profile_transitions_wrap_without_losing_state(self):
        batches = [[event(i + 1, "nav_right", "Next")] for i in range(100)]
        mailbox = BufferedButtonEvents(SequenceEvents(batches))
        low = CountingPage("dashboard", RATE_ACTIVITY)
        high = CountingPage("game", RATE_STREAMING)
        runtime = ProfilePageOrchestrator(
            [low, high], mailbox,
            {RATE_ACTIVITY: self.transition_runner, RATE_STREAMING: self.transition_runner},
        )
        result = runtime.run(max_sessions=100)
        self.assertEqual(result["page_transitions"], 100)
        self.assertEqual(result["profile_transitions"], 100)
        self.assertEqual(result["current_page"], "dashboard")
        self.assertEqual(result["buffered_inputs"], 0)
        self.assertEqual(low.entered, 51)  # initial + every return
        self.assertEqual(low.exited, 50)
        self.assertEqual(high.entered, 50)
        self.assertEqual(high.exited, 50)

    def test_1000_mixed_events_are_consumed_exactly_once(self):
        batches = []
        seq = 0
        for _ in range(500):
            seq += 1
            lever = event(seq, "lever_candidate", "Play")
            seq += 1
            nav = event(seq, "nav_right", "Next")
            batches.append([lever, nav])
        mailbox = BufferedButtonEvents(SequenceEvents(batches))
        low = CountingPage("dashboard", RATE_ACTIVITY)
        high = CountingPage("game", RATE_STREAMING)
        runtime = ProfilePageOrchestrator(
            [low, high], mailbox,
            {RATE_ACTIVITY: self.transition_runner, RATE_STREAMING: self.transition_runner},
        )
        result = runtime.run(max_sessions=500)
        self.assertEqual(result["page_transitions"], 500)
        self.assertEqual(low.levers + high.levers, 500)
        self.assertEqual(sum(d.inputs_consumed for d in runtime.drivers), 1000)
        self.assertEqual(mailbox.pending_count, 0)

    def test_canvas_invalidation_reopens_same_page_without_page_lifecycle_reset(self):
        mailbox = BufferedButtonEvents(SequenceEvents([[], []]))
        slots = SlotsPage(seed=99)
        calls = {"n": 0}
        positions_after_first = []

        def runner(driver):
            calls["n"] += 1
            if calls["n"] == 1:
                for _ in range(3):
                    driver.render(0)
                    driver.frame_sent()
                positions_after_first[:] = slots.positions
                return {"terminal_reason": "canvas_invalidated", "outcome": "stopped_clean"}
            self.assertEqual(slots.positions, positions_after_first)
            return {"terminal_reason": "operator_stop", "outcome": "stopped_clean"}

        runtime = ProfilePageOrchestrator([slots], mailbox, {RATE_STREAMING: runner})
        result = runtime.run(max_sessions=2)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(slots.enter_count, 1)
        self.assertEqual(slots.exit_count, 0)
        self.assertEqual(result["page_transitions"], 0)
        self.assertEqual(result["status"], "stopped")

    def test_ambiguous_transport_failure_is_not_retried(self):
        mailbox = BufferedButtonEvents(SequenceEvents([[]]))
        page = CountingPage("game", RATE_STREAMING)
        calls = {"n": 0}

        def runner(_driver):
            calls["n"] += 1
            return {"terminal_reason": "transport_fault", "outcome": "unknown", "detail": "ambiguous"}

        runtime = ProfilePageOrchestrator([page], mailbox, {RATE_STREAMING: runner})
        result = runtime.run(max_sessions=20)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["last_error"], "ambiguous")

class HF1AcceptanceTests(unittest.TestCase):
    def test_120_dynamic_acked_frames_run_in_ack_clock_envelope(self):
        clock = FakeClock()
        mailbox = BufferedButtonEvents(SequenceEvents([[]] * 200))
        page = LeverPage()
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=55)
        result = run_interactive_stream(
            manifest(max_frames=120, lifetime=20), stream_spec(), transport, clock, clock.sleep, driver)
        self.assertEqual(result["terminal_reason"], "budget_exhausted")
        self.assertEqual(result["frames_sent"], 120)
        self.assertEqual(len(transport.frames), 120)
        self.assertGreater(result["realized_fps"], 18.0)
        self.assertLess(result["realized_fps"], 18.5)

    def test_stationary_slots_result_sends_once_then_holds(self):
        clock = FakeClock()
        slots = SlotsPage(seed=17)
        for seq in range(1, 4):
            slots.handle_input(event(seq, "lever_candidate"))
        # Slots v2: the snap/bounce and outcome animation finish inside the real change-only
        # stream loop (an unchanged frame is never ACKed, so a stalled animation would hang here).
        mailbox = BufferedButtonEvents(SequenceEvents([[]] * 400))
        driver = InteractivePageDriver(slots, mailbox, monotonic=lambda: clock.ms / 1000)
        self.assertTrue(slots.busy())
        animated = run_interactive_stream(
            manifest(max_frames=100, lifetime=4), stream_spec(), AckTimedTransport(clock, ack_ms=60),
            clock, clock.sleep, driver)
        self.assertFalse(slots.busy())
        self.assertLessEqual(animated["frames_sent"], 8 + 24 + 1)
        transport = AckTimedTransport(clock, ack_ms=60)
        result = run_interactive_stream(
            manifest(max_frames=50, lifetime=1), stream_spec(), transport, clock, clock.sleep, driver)
        self.assertEqual(result["terminal_reason"], "lifetime_expired")
        self.assertEqual(result["frames_sent"], 1)
        self.assertEqual(len(transport.frames), 1)
        holds = result["holds"].get("unchanged", 0)
        self.assertGreaterEqual(holds, 15)
        self.assertLessEqual(holds, 25)  # 50 ms interactive idle poll, not the generic 10 ms loop

    def test_slots_state_survives_real_stream_loop_invalidation_and_reopen(self):
        clock = FakeClock()
        slots = SlotsPage(seed=23)
        mailbox = BufferedButtonEvents(SequenceEvents([[]] * 50))
        driver = InteractivePageDriver(slots, mailbox, monotonic=lambda: clock.ms / 1000)
        first_transport = AckTimedTransport(
            clock, ack_ms=60,
            reports={3: [{"kind": "session_ended", "reason": "canvas_invalidated",
                          "outcome": "stopped_clean"}]},
        )
        first = run_interactive_stream(
            manifest(max_frames=20), stream_spec(), first_transport, clock, clock.sleep, driver)
        self.assertEqual(first["terminal_reason"], "canvas_invalidated")
        self.assertEqual(first["frames_sent"], 3)
        positions = list(slots.positions)
        self.assertEqual(slots.enter_count, 1)

        second_transport = AckTimedTransport(clock, ack_ms=60)
        second = run_interactive_stream(
            manifest(max_frames=2), stream_spec(), second_transport, clock, clock.sleep, driver)
        self.assertEqual(second["terminal_reason"], "budget_exhausted")
        self.assertEqual(second["frames_sent"], 2)
        self.assertNotEqual(slots.positions, positions)
        self.assertEqual(slots.enter_count, 1)  # Host reopen is not page re-entry
        self.assertEqual(slots.exit_count, 0)

from host.interactive_activity import run_interactive_activity


def activity_manifest(max_frames=10, lifetime=10):
    return activity_session.SessionManifest(
        experiment_id="TEST-ACTIVITY-INTERACTIVE",
        lifetime_seconds=lifetime,
        min_frame_interval_ms=activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS,
        pulse_freshness_seconds=30,
        poll_interval_ms=50,
        max_frames=max_frames,
        max_application_packets=max_frames * 3,
        max_tx_bytes=max_frames * frame_stream.worst_case_frame_tx_bytes(),
        ack_timeout_ms_per_frame=5000,
        activation_source="offline activity interactive test",
        host_build_sha256="0" * 64,
        code_hashes={},
        stop_conditions=("transport_fault",),
        acceptance_profile=None,
        path=Path("TEST-ACTIVITY-INTERACTIVE.json"),
        raw={},
    )


class ActivityPageAdapterTests(unittest.TestCase):
    def test_activity_page_navigation_becomes_clean_page_transition(self):
        clock = FakeClock()
        mailbox = BufferedButtonEvents(SequenceEvents([[], [event(1, "nav_right", "Next")]]))
        page = CountingPage("dashboard", RATE_ACTIVITY)
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=40)
        result = run_interactive_activity(
            activity_manifest(), transport, clock, clock.sleep, driver)
        self.assertEqual(result["terminal_reason"], "page_transition")
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertEqual(result["frames_sent"], 1)
        self.assertEqual(driver.navigation.direction, 1)
        self.assertEqual(page.entered, 1)
        self.assertEqual(page.exited, 0)

    def test_activity_adapter_preserves_page_until_outer_orchestrator_exits_it(self):
        clock = FakeClock()
        mailbox = BufferedButtonEvents(SequenceEvents([[]] * 100))
        page = CountingPage("dashboard", RATE_ACTIVITY)
        driver = InteractivePageDriver(page, mailbox, monotonic=lambda: clock.ms / 1000)
        transport = AckTimedTransport(clock, ack_ms=40)
        result = run_interactive_activity(
            activity_manifest(max_frames=2, lifetime=2), transport, clock, clock.sleep, driver)
        self.assertEqual(result["terminal_reason"], "budget_exhausted")
        self.assertEqual(page.entered, 1)
        self.assertEqual(page.exited, 0)
