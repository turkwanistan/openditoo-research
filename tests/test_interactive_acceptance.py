from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from host import activity_session, frame_stream
from host.interactive_acceptance import (
    AcceptanceManifest, OuterBudget, child_manifest, run_acceptance,
)
from host.interactive_pages import BufferedButtonEvents, PageCarousel, RATE_ACTIVITY, RATE_STREAMING
from host.slots_page import SlotsPage


class FakeClock:
    def __init__(self):
        self.ms = 0
    def __call__(self):
        return self.ms
    def sleep(self, ms):
        self.ms += max(1, int(ms))


class SequenceEvents:
    def __init__(self, batches):
        self.batches = list(batches)
        self.index = 0
    def poll(self):
        if self.index >= len(self.batches):
            return []
        batch = self.batches[self.index]
        self.index += 1
        return list(batch)
    @property
    def done(self):
        return self.index >= len(self.batches)


class DryDashboard:
    name = "dashboard"
    rate_mode = RATE_ACTIVITY
    def __init__(self):
        self.enter_count = 0
        self.exit_count = 0
        self.frames = 0
        self.background = 0
        self.last_from_pulse = False
    def on_enter(self): self.enter_count += 1
    def on_exit(self): self.exit_count += 1
    def render(self, _now): return bytes([0, 85, 0]) * 256
    def handle_input(self, _event): return None
    def frame_sent(self): self.frames += 1
    def background_tick(self, _now): self.background += 1
    def telemetry(self): return {"frames": self.frames, "background": self.background}


class FakeHost:
    def __init__(self, clock, *, ack_ms=55):
        self.clock = clock
        self.ack_ms = ack_ms
        self.child = None
        self.frames = 0
        self.closed = False
    def open(self, child):
        self.child = child
        return {"sessionId": child.experiment_id,
                "sessionProfile": (child.raw.get("stream") or {}).get("session_profile", RATE_ACTIVITY)}
    def send_frame(self, _rgb, expected_packet_sha256):
        self.clock.sleep(self.ack_ms)
        self.frames += 1
        return {"ok": True, "imagePacketSha256": expected_packet_sha256, "ackPayloadHex": "0x00"}
    def poll_reports(self): return []
    def close(self, _reason):
        self.closed = True
        return {"closed": True}


class InvalidatingHost(FakeHost):
    def __init__(self, clock, invalidate_after=2):
        super().__init__(clock)
        self.invalidate_after = invalidate_after
        self.reported = False
    def poll_reports(self):
        if self.frames >= self.invalidate_after and not self.reported:
            self.reported = True
            return [{"kind": "session_ended", "reason": "canvas_invalidated",
                     "outcome": "stopped_yielded_to_stock"}]
        return []


def event(seq, kind, raw="Play"):
    return {"epoch": "dry", "seq": seq, "type": kind, "raw_button": raw, "at_utc": None}


def manifest(tmp: Path | None = None, *, max_sessions=28, max_frames=500, lifetime=90,
             streaming_child=120):
    path = (tmp or Path(".")) / "HF3.json"
    return AcceptanceManifest(
        path=path, raw={}, experiment_id="OPENDITOO-INTERACTIVE-HF3-004",
        lifetime_seconds=lifetime, max_child_sessions=max_sessions,
        max_frames=max_frames,
        max_tx_bytes=max_frames * frame_stream.worst_case_frame_tx_bytes(),
        activity_child_max_frames=20, streaming_child_max_frames=streaming_child,
        target_profile_cycles=10, host_dll_sha256="0" * 64,
        button_probe_sha256={"a": "1" * 64, "b": "2" * 64},
    )


def choreography(cycles=10):
    batches = []
    seq = 0
    for _ in range(cycles):
        seq += 1; batches.append([event(seq, "nav_right", "Next")])
        batches.append([])
        for raw in ("Pause", "Play", "Pause", "Play"):
            seq += 1; batches.append([event(seq, "lever_candidate", raw)])
            batches.append([])
        seq += 1; batches.append([event(seq, "nav_left", "Previous")])
    batches.extend([[], []])
    return batches


class AcceptanceEnvelopeTests(unittest.TestCase):
    def test_child_ids_and_profile_budgets_are_deterministic(self):
        m = manifest()
        high = child_manifest(m, 7, RATE_STREAMING, 500, m.max_tx_bytes, 90)
        low = child_manifest(m, 8, RATE_ACTIVITY, 500, m.max_tx_bytes, 90)
        self.assertEqual(high.experiment_id, "OPENDITOO-INTERACTIVE-HF3-004-S007")
        self.assertEqual(high.max_frames, 120)
        self.assertEqual(high.raw["stream"]["session_profile"], RATE_STREAMING)
        self.assertEqual(low.max_frames, 20)
        self.assertEqual(low.raw, {})

    def test_outer_budget_counts_attempt_before_open_and_ack_after_success(self):
        m = manifest(max_sessions=4, max_frames=2)
        b = OuterBudget(m)
        b.before_open(m.child_experiment_id(1), profile=RATE_ACTIVITY, at_monotonic=1.0)
        self.assertEqual((b.child_attempts, b.child_opens, b.frames_acked), (1, 0, 0))
        b.session_opened(m.child_experiment_id(1), at_monotonic=1.1)
        b.frame_acked(100, child_experiment_id=m.child_experiment_id(1),
                      profile=RATE_ACTIVITY, at_monotonic=1.2)
        self.assertEqual((b.child_attempts, b.child_opens, b.frames_acked), (1, 1, 1))
        self.assertEqual(b.ack_events[0]["application_bytes"], 100)

    def test_ten_cycle_dry_run_meets_profile_target_and_correlates_inputs(self):
        clock = FakeClock()
        source = SequenceEvents(choreography())
        mailbox = BufferedButtonEvents(source)
        created = []
        def factory():
            host = FakeHost(clock)
            created.append(host)
            return host
        dashboard = DryDashboard()
        result = run_acceptance(
            manifest(), [PageCarousel([dashboard, SlotsPage(seed=20260910)])], mailbox,
            factory, clock, clock.sleep,
            stop_requested=lambda: source.done and mailbox.pending_count == 0,
        )
        self.assertEqual(result["outcome"], "stopped_clean")
        self.assertTrue(result["cycle_target_met"])
        self.assertEqual(result["completed_profile_cycles"], 10)
        self.assertEqual(result["orchestrator"]["page_state"]["profile_transitions"], 20)
        # HF3-002 lesson: 20 page transitions, ONE Host session -- navigation never closes it.
        self.assertEqual(result["budget"]["child_attempts"], 1)
        self.assertEqual(len(created), 1)
        # 6 physical events/cycle (right, 3 stops, new-round lever, left), each represented once.
        latency = result["input_to_first_later_ack"]
        self.assertEqual(len(latency), 60)
        self.assertEqual(len({(item["epoch"], item["seq"]) for item in latency}), 60)
        self.assertTrue(all(item["first_later_ack_ms"] is not None for item in latency))
        self.assertGreater(dashboard.background, 0)

    def _paced(self, m):
        from scripts import interactive_hf3 as entry
        clock, invalidations = FakeClock(), []
        schedule, last_left = entry.paced_schedule(m.target_profile_cycles)
        source = entry.PacedEvents(schedule, clock, invalidations)
        return run_acceptance(
            m, [PageCarousel([DryDashboard(), SlotsPage(seed=7)])], BufferedButtonEvents(source),
            lambda: entry.FakeHost(clock, invalidations), clock, clock.sleep,
            stop_requested=lambda: clock() >= last_left + 12000)

    def test_hf3_003_envelope_fits_ten_human_paced_cycles_with_lever_reclaims(self):
        r = self._paced(manifest(max_sessions=32, max_frames=1500, lifetime=150, streaming_child=1500))
        self.assertEqual((r["outcome"], r["terminal_reason"]), ("stopped_clean", "operator_stop"))
        self.assertTrue(r["cycle_target_met"])
        self.assertEqual(r["orchestrator"]["session_reclaims"], 20)
        # Only device-ended 0xBD yields start a new session: 1 + 20 reclaims.
        self.assertEqual(r["budget"]["child_attempts"], 21)
        self.assertTrue(all(i["first_later_ack_ms"] is not None for i in r["input_to_first_later_ack"]))

    def test_hf3_001_envelope_could_not_fit_ten_human_paced_cycles(self):
        # Negative control for the HF3-001 finding: 90 s / 28 children / 500 frames is too small.
        r = self._paced(manifest())
        self.assertFalse(r["cycle_target_met"])

    def test_carousel_holds_low_rate_page_to_its_cadence_inside_streaming_session(self):
        class Changing(DryDashboard):
            n = 0
            def render(self, _now):
                self.n += 1
                return bytes([self.n % 256, 0, 0]) * 256
        clock, dash = FakeClock(), Changing()
        sent_at = []
        class Host(FakeHost):
            def send_frame(self, rgb, sha):
                sent_at.append(clock.ms)
                return super().send_frame(rgb, sha)
        run_acceptance(manifest(streaming_child=500), [PageCarousel([dash, SlotsPage(seed=1)])],
                       BufferedButtonEvents(SequenceEvents([])), lambda: Host(clock),
                       clock, clock.sleep, stop_requested=lambda: clock() >= 3000)
        gaps = [b - a for a, b in zip(sent_at, sent_at[1:])]
        self.assertGreater(len(sent_at), 5)
        self.assertTrue(all(g >= 200 for g in gaps), gaps)

    def test_known_canvas_yield_reopens_same_slots_page_without_reset(self):
        clock = FakeClock()
        # no navigation: first child invalidates after two frames, second is externally stopped
        source = SequenceEvents([[], [], [], []])
        mailbox = BufferedButtonEvents(source)
        slots = SlotsPage(seed=5)
        hosts = [InvalidatingHost(clock, 2), FakeHost(clock)]
        calls = {"n": 0}
        # Run the generic orchestrator directly because HF-3 exact page set always starts dashboard.
        from host.interactive_runtime import ProfilePageOrchestrator
        from host.interactive_stream import run_interactive_stream
        from host.interactive_pages import InteractivePageDriver
        def runner(driver: InteractivePageDriver):
            host = hosts[calls["n"]]
            calls["n"] += 1
            m = activity_session.SessionManifest(
                experiment_id=f"T-{calls['n']}", lifetime_seconds=5, min_frame_interval_ms=40,
                pulse_freshness_seconds=30, poll_interval_ms=10, max_frames=5,
                max_application_packets=15, max_tx_bytes=5 * frame_stream.worst_case_frame_tx_bytes(),
                ack_timeout_ms_per_frame=5000, activation_source="test", host_build_sha256="0" * 64,
                code_hashes={}, stop_conditions=("x",), acceptance_profile=None,
                path=Path("x"), raw={"stream": {"session_profile": RATE_STREAMING}},
            )
            if calls["n"] == 1:
                return run_interactive_stream(m, {"session_profile": RATE_STREAMING, "playback_interval_ms": 40},
                                              host, clock, clock.sleep, driver)
            return {"terminal_reason": "operator_stop", "outcome": "stopped_clean"}
        runtime = ProfilePageOrchestrator([slots], mailbox, {RATE_STREAMING: runner},
                                          monotonic=lambda: clock.ms / 1000)
        out = runtime.run(max_sessions=2)
        self.assertEqual(out["status"], "stopped")
        self.assertEqual(out["session_reclaims"], 1)
        self.assertEqual(slots.enter_count, 1)
        self.assertEqual(slots.exit_count, 0)


if __name__ == "__main__":
    unittest.main()

class LiveCoordinatorStaticBoundaryTests(unittest.TestCase):
    def test_outer_claim_is_after_final_host_idle_check(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/interactive_hf3.py").read_text()
        live = source[source.index("def live_run()") : source.index("def main()")]
        self.assertLess(live.index("host_idle_status(token)"), live.index("claim = hf3.claim_outer"))
        self.assertIn("verify_button_probe=True", live)
        self.assertNotIn("raw_send", live.lower())

    def test_shell_refuses_before_stopping_runtime_when_not_execution_ready(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/run_interactive_hf3.sh").read_text()
        self.assertLess(source.index("execution_ready"), source.index('systemctl --user stop "$SERVICE"'))
        self.assertIn("HF3_DASHBOARD_CONNECTED_RESTORED", source)
        self.assertIn("trap - EXIT INT TERM", source)

    def test_all_live_behavior_surfaces_are_hash_frozen(self):
        from host import interactive_acceptance as hf3
        required = {
            "cli_transport_sha256", "hf3_entry_sha256", "hf3_coordinator_sha256",
            "pagination_input_sha256", "interactive_acceptance_sha256",
        }
        self.assertTrue(required <= set(hf3.HASHED_MODULES))
