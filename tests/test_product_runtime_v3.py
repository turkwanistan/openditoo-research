"""Runtime 008 (HF-4) offline gates: supervisor soak, rollover, backoff, reclaim, input, pulse, policy."""
from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from host import product_runtime_v2, product_runtime_v3 as v3
from host.dashboard_page import DashboardPage
from host.interactive_pages import RATE_ACTIVITY
from host.slots_page import SlotsPage
from scripts.interactive_hf3 import FakeClock, FakeHost, PacedEvents, paced_schedule

ROOT = Path(__file__).resolve().parents[1]


class DryDashboard:
    name = "dashboard"; rate_mode = RATE_ACTIVITY
    def __init__(self): self.frames = 0; self.ticks = 0
    def on_enter(self): pass
    def on_exit(self): pass
    def render(self, _now): return bytes([0, 85, 0]) * 256
    def handle_input(self, _event): return None
    def frame_sent(self): self.frames += 1
    def background_tick(self, _now): self.ticks += 1
    def telemetry(self): return {"frames": self.frames}


class RecordingSlots(SlotsPage):
    def __init__(self):
        super().__init__(seed=20260910); self.applied = []
    def handle_input(self, event):
        self.applied.append(event["seq"]); return super().handle_input(event)


class Events:
    """PacedEvents plus an explicit ledger of everything the cursor delivered."""
    def __init__(self, schedule, clock, invalidations):
        self.inner = PacedEvents(schedule, clock, invalidations); self.delivered = []
    def poll(self):
        out = self.inner.poll(); self.delivered.extend(out); return out


class NoOpenHost:
    def open(self, _manifest): raise OSError("device unavailable")
    def poll_reports(self): return []
    def close(self, _reason): return {}


class Harness:
    def __init__(self, tmp: Path, schedule=(), policy=None):
        self.clock = FakeClock(); self.invalidations: list = []
        self.events = Events(list(schedule), self.clock, self.invalidations)
        self.hosts: list[FakeHost] = []
        self.policy = policy or v3.load_policy(v3.TEMPLATE, require_authority=False, verify_hashes=False)
        self.tmp = tmp; self.failing_sessions: set[int] = set(); self.opens = 0

    def factory(self):
        self.opens += 1
        if self.opens in self.failing_sessions:
            return NoOpenHost()
        host = FakeHost(self.clock, self.invalidations); self.hosts.append(host); return host

    def run(self, pages, stop, **kw):
        kw.setdefault("waiting_collector", lambda: None)
        return v3.run_product(
            self.policy, kw.pop("factory", self.factory), stop_requested=stop,
            monotonic=lambda: self.clock.ms / 1000.0, sleep=lambda s: self.clock.sleep(s * 1000),
            config={"poll_seconds": 2.0}, activity_state={}, events=self.events, pages=pages,
            state_file=self.tmp / "state.json", pages_state_file=self.tmp / "pages.json", **kw)

    @property
    def frames(self): return sum(h.sends - getattr(h, "yields", 0) for h in self.hosts)
    @property
    def yields(self): return sum(getattr(h, "yields", 0) for h in self.hosts)
    def pages_state(self): return json.loads((self.tmp / "pages.json").read_text(encoding="utf-8"))


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(); self.tmp = Path(self._tmp.name)
    def tearDown(self):
        self._tmp.cleanup()

    def test_fake_host_soak_survives_rollovers_yields_and_open_failures(self):
        # Play pulls reclaim a busy session every few seconds, so rollover at the real 600 s envelope
        # happens while the owner leaves the dashboard up: 60 cycles, 25 idle minutes, 60 cycles.
        block, block_ms = paced_schedule(60)
        gap_ms = block_ms + 25 * 60 * 1000
        schedule = block + [(t + gap_ms, dict(e, seq=e["seq"] + len(block))) for t, e in block]
        cycles, end_ms = 120, gap_ms + block_ms
        h = Harness(self.tmp, schedule)
        h.failing_sessions = {5, 6, 7, 40}  # 3 consecutive (backoff 1, 2, 5) + one isolated
        slots = RecordingSlots()
        state = h.run([DryDashboard(), slots], lambda: h.clock() >= end_ms + 3000)
        self.assertGreater(h.frames, 10000, "thousands of ACKed frames")
        self.assertEqual(state["reconnects"], 4, "only the injected open failures; no 429 or fault")
        self.assertGreaterEqual(state["renewals"], 2)
        self.assertEqual(state["reclaims"], h.yields)
        self.assertEqual(h.yields, 2 * cycles, "every Play pull yielded, mid-send and watchdog races alternate")
        self.assertEqual(state["status"], "stopped")
        levers = [e["seq"] for e in h.events.delivered if e["type"] == "lever_candidate"]
        self.assertEqual(slots.applied, levers, "every lever applied exactly once, in order")
        self.assertEqual(slots.round, cycles + 1)
        pages = h.pages_state()
        self.assertEqual(pages["current_page"], "dashboard")
        self.assertEqual(pages["page_transitions"], 2 * cycles)
        self.assertEqual(pages["inputs_applied"], len(h.events.delivered))

    def test_rollover_renews_without_resetting_page_or_game(self):
        h = Harness(self.tmp, [(1000, _ev(1, "nav_right", "Next")), (2000, _ev(2, "lever_candidate", "Pause"))])
        h.policy = dataclasses.replace(h.policy, session_lifetime_seconds=5)
        slots = RecordingSlots()
        state = h.run([DryDashboard(), slots], lambda: h.clock() >= 21000)
        self.assertGreaterEqual(state["renewals"], 3)
        self.assertEqual((state["reclaims"], state["reconnects"]), (0, 0))
        self.assertEqual((slots.enter_count, slots.exit_count, slots.round), (1, 0, 1))
        self.assertEqual(slots.telemetry()["stopped_reels"], 1)
        self.assertEqual(h.pages_state()["current_page"], "slots")
        self.assertEqual(len({host for host in h.hosts}), state["session_sequence"])

    def test_backoff_is_bounded_monotonic_and_resets_after_a_connected_session(self):
        h = Harness(self.tmp)
        h.failing_sessions = {1, 2, 3, 4, 5, 6, 8}
        h.policy = dataclasses.replace(h.policy, session_lifetime_seconds=1)
        waits = []
        real = product_runtime_v2.save_runtime_state
        def spy(state, path):
            if state["status"] == "waiting_for_host_or_device":
                waits.append(state["retry_in_seconds"])
            real(state, path)
        with mock.patch.object(product_runtime_v2, "save_runtime_state", spy):
            state = h.run([DryDashboard(), SlotsPage()], lambda: False, max_sessions=8)
        self.assertEqual(waits, [1, 2, 5, 10, 30, 30, 1])
        self.assertEqual(state["reconnects"], 7)
        self.assertEqual(state["connected_sessions"], 1)

    def test_reclaim_is_immediate_until_the_storm_guard_cools_down(self):
        class Always(list):
            def __bool__(self): return True
            def pop(self, *_a): return 1
        h = Harness(self.tmp); h.invalidations = Always()
        cooldowns = []
        def sleep(s):
            if s == 1: cooldowns.append(h.clock())
            h.clock.sleep(s * 1000)
        state = v3.run_product(h.policy, h.factory, monotonic=lambda: h.clock.ms / 1000.0, sleep=sleep,
                               max_sessions=12, config={}, activity_state={}, events=h.events,
                               pages=[DryDashboard(), SlotsPage()], waiting_collector=lambda: None,
                               state_file=self.tmp / "s.json", pages_state_file=self.tmp / "p.json")
        self.assertEqual((state["reclaims"], state["reconnects"]), (12, 0))
        self.assertEqual(len(cooldowns), 12 - product_runtime_v2.MAX_RECLAIMS_IN_WINDOW)

    def test_inputs_in_one_batch_across_a_yield_apply_once_and_in_order(self):
        burst = [(1000, _ev(1, "nav_right", "Next"))] + [
            (1500, _ev(seq, "lever_candidate", raw)) for seq, raw in ((2, "Play"), (3, "Pause"), (4, "Play"))] + [
            (1500, _ev(5, "nav_left", "Previous")), (1500, _ev(6, "nav_right", "Next")),
            (2500, _ev(7, "lever_candidate", "Pause"))]
        h = Harness(self.tmp, burst)
        slots = RecordingSlots()
        state = h.run([DryDashboard(), slots], lambda: h.clock() >= 5000)
        self.assertEqual(slots.applied, [2, 3, 4, 7])
        self.assertEqual(state["reclaims"], 2)
        self.assertEqual(h.pages_state()["inputs_applied"], 7)
        self.assertEqual(slots.round, 2, "3 stops + new round from the four pulls")

    def test_first_ack_after_an_input_is_published_while_running(self):
        h = Harness(self.tmp, [(1000, _ev(1, "nav_right", "Next"))])
        seen = {}
        def stop():
            if h.clock() >= 1300 and not seen:
                seen.update(h.pages_state())
            return h.clock() >= 2000
        state = h.run([DryDashboard(), SlotsPage()], stop)
        self.assertEqual(seen["last_input"]["type"], "nav_right")
        self.assertIsNotNone(seen["last_input"]["first_ack_ms"])
        self.assertLess(seen["last_input"]["first_ack_ms"], 150)
        self.assertEqual(state["last_input_to_first_ack_ms"], seen["last_input"]["first_ack_ms"])
        self.assertIn("realized_fps_5s", json.loads((self.tmp / "state.json").read_text()))

    def test_a_sessions_first_ack_is_persisted_even_within_the_throttle(self):
        h = Harness(self.tmp)
        seen = {}
        def stop():
            if h.clock() >= 400 and not seen:
                seen.update(json.loads((self.tmp / "state.json").read_text()))
            return h.clock() >= 600
        h.run([DryDashboard(), SlotsPage()], stop)  # static dashboard: exactly one frame is sent
        self.assertEqual(sum(host.sends for host in h.hosts), 1)
        self.assertEqual(seen["current_session_frames_acked"], 1)

    def test_pulse_in_flight_at_an_outage_is_dropped_not_replayed(self):
        class PulseInner:
            def __init__(self): self.pulse_step = None; self.pulse_sources = set(); self.next_collect_ms = 0; self.n = 0
            def __call__(self, now):
                if now >= self.next_collect_ms:
                    self.n += 1; self.next_collect_ms = now + 2000
                    if self.n == 1: self.pulse_step, self.pulse_sources = 0, {"wsl_mcp"}
                if self.pulse_step is not None:
                    return bytes([255, 0, self.pulse_step]) * 256, True
                return bytes([0, 0, 255]) * 256, False
            def frame_sent(self):
                if self.pulse_step is not None:
                    self.pulse_step += 1
                    if self.pulse_step >= 10: self.pulse_step = None
        h = Harness(self.tmp)
        sent: list[list[bytes]] = []
        class Dropping:
            def __init__(self, host, fail_after): self.host, self.fail_after, self.rgb = host, fail_after, []
            def open(self, m): return self.host.open(m)
            def poll_reports(self): return self.host.poll_reports()
            def close(self, r): return self.host.close(r)
            def send_frame(self, rgb, sha):
                if len(self.rgb) == self.fail_after: raise TimeoutError("device went away")
                self.rgb.append(rgb); return self.host.send_frame(rgb, sha)
        def factory():
            t = Dropping(FakeHost(h.clock, []), 2 if not sent else 10 ** 6); sent.append(t.rgb); return t
        dashboard = DashboardPage({}, {}, renderer=PulseInner())
        state = h.run([dashboard, SlotsPage()], lambda: h.clock() >= 4000, factory=factory)
        self.assertEqual(state["reconnects"], 1)
        self.assertEqual([rgb[0] for rgb in sent[0]], [255, 255], "pulse was on screen before the outage")
        self.assertTrue(sent[1] and all(rgb[0] == 0 for rgb in sent[1]), "no stale pulse after reconnect")
        self.assertEqual(dashboard.hidden_pulses_dropped, 1)

    def test_stop_ends_the_session_cleanly_and_releases_the_probe(self):
        class Broker:
            alive, starts, stopped = True, 1, 0
            def ensure(self): pass
            def stop(self): Broker.stopped += 1; Broker.alive = False
        h = Harness(self.tmp)
        closes = []
        def factory():
            host = h.factory(); real = host.close
            host.close = lambda r: (closes.append(r), real(r))[1]; return host
        state = h.run([DryDashboard(), SlotsPage()], lambda: h.clock() >= 1000, factory=factory, broker=Broker())
        self.assertEqual((state["last_terminal_reason"], state["status"]), ("operator_stop", "stopped"))
        self.assertEqual(len(closes), 1, "exactly one Host close, no reopen")
        self.assertEqual(Broker.stopped, 1)
        self.assertFalse(h.pages_state()["input_broker_alive"])


def _ev(seq, kind, raw):
    return {"epoch": "r008", "seq": seq, "type": kind, "raw_button": raw, "at_utc": None}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(); self.tmp = Path(self._tmp.name)
        self.template = json.loads(v3.TEMPLATE.read_text(encoding="utf-8"))
    def tearDown(self):
        self._tmp.cleanup()

    def _load(self, doc, *, template=False, **kw):
        path = self.tmp / "p.json"; path.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(product_runtime_v2.ProductPolicyError) as caught:
            v3.load_policy(path, require_authority=False, template_path=path if template else v3.TEMPLATE, **kw)
        return caught.exception.code

    def test_template_is_unauthorized_and_pins_pages_envelope_host_and_probe(self):
        policy = v3.load_policy(v3.TEMPLATE, require_authority=False, verify_hashes=False)
        self.assertEqual((policy.session_lifetime_seconds, policy.max_frames_per_session), (600, 15000))
        self.assertEqual([p["name"] for p in self.template["pages"]], ["dashboard", "slots"])
        self.assertEqual(self.template["session"]["client_min_dispatch_ms"], 50)
        self.assertEqual(self.template["session"]["host_anchored_gap_ms"], 45)
        self.assertLessEqual(self.template["session"]["lifetime_seconds"], 1800, "Host streaming ceiling")
        self.assertLessEqual(self.template["session"]["max_frames"], 45000, "Host streaming ceiling")
        self.assertEqual(v3.authority_blockers(v3.TEMPLATE),
                         ["PRODUCT_AUTHORITY_MISSING", "PRODUCT_AUTHORITY_UNATTRIBUTED", "PRODUCT_AUTHORITY_SCOPE_MISMATCH"])
        self.assertIsNone(self.template["authority"]["grant_text"])
        r007 = json.loads(v3.R007_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(self.template["build"]["host_dll_sha256"], r007["build"]["host_dll_sha256"])
        self.assertEqual(self.template["authority"]["supersedes"], "OPENDITOO-PRODUCT-RUNTIME-008")
        self.assertNotIn("spiral", json.dumps(self.template["pages"]))

    def test_loader_refuses_drift_even_in_an_edited_template(self):
        t = self.template
        self.assertEqual(self._load({**t, "runtime_revision": 3}), "PRODUCT_RUNTIME_REVISION_MISMATCH")
        self.assertEqual(self._load({**t, "description": "x"}), "PRODUCT_POLICY_DRIFTED_FROM_TEMPLATE")
        self.assertEqual(self._load({**t, "pages": t["pages"][:1]}, template=True), "PRODUCT_008_PAGES_MISMATCH")
        for key, value in (("client_min_dispatch_ms", 40), ("host_anchored_gap_ms", 0), ("lifetime_seconds", 1801)):
            self.assertEqual(self._load({**t, "session": {**t["session"], key: value}}, template=True),
                             "PRODUCT_008_ENVELOPE_MISMATCH", key)
        self.assertEqual(self._load({**t, "behavior": {**t["behavior"], "raw_send_enabled": True}}, template=True),
                         "PRODUCT_008_WIDENS_007")
        self.assertEqual(self._load({**t, "build": {**t["build"], "host_dll_sha256": "0" * 64}}, template=True),
                         "PRODUCT_008_CHANGES_INPUT_OR_HOST")
        hashes = {**t["build"]["code_sha256"], "slots_page_sha256": "0" * 64}
        self.assertEqual(self._load({**t, "build": {**t["build"], "code_sha256": hashes}}, template=True),
                         "PRODUCT_CODE_HASH_MISMATCH")

    def test_granted_local_copy_is_execution_ready_and_cli_dispatches_revision_4(self):
        doc = copy.deepcopy(self.template); a = doc["authority"]
        a.update(persistent_runtime_authorized=True, grant_text=v3.GRANT_TEXT, granted_by="owner, in-session",
                 grant_scope=a["grant_scope_requested"])
        path = self.tmp / "local.json"; path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(v3.authority_blockers(path), [])
        v3.load_policy(path, require_authority=True, verify_hashes=False)
        a["grant_text"] = "Grant OPENDITOO-PRODUCT-RUNTIME-007"
        path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertIn("PRODUCT_AUTHORITY_UNATTRIBUTED", v3.authority_blockers(path))
        from cli import openditoo
        self.assertIs(openditoo._product_runtime_module(v3.TEMPLATE), v3)

    def test_cutovers_gate_before_restart_and_roll_back_exactly(self):
        for rev, prev, prev_rev in (("008", "007", 3), ("009", "008", 4)):
            path = ROOT / f"scripts/cutover_runtime_{rev}.sh"
            shell = path.read_text(encoding="utf-8")
            r = f"R{rev}_"
            self.assertIn(f'"${{1:-}}" == "Grant OPENDITOO-PRODUCT-RUNTIME-{rev}"', shell)
            self.assertIn(f'== OPENDITOO-PRODUCT-RUNTIME-{prev} ]]', shell)
            self.assertIn(f"rollback-runtime-{prev}", shell)
            self.assertIn(f"product_check {prev_rev} && echo {r}ROLLBACK_PRODUCT_CHECK_PASS", shell)
            order = [shell.index(r + m) for m in ("EXACT_GRANT_REQUIRED", "ROLLBACK_SAVED", "HOST_IDLE",
                                                   "MAIN_FAST_FORWARDED", "MAIN_OFFLINE_PASS", "LOCAL_POLICY_WRITTEN")]
            order.append(shell.index("start_and_confirm ||"))
            self.assertEqual(order, sorted(order), rev)
            self.assertIn("offline-gate.log", shell)
            # A merged range can hold merge commits, which `git revert A..B` refuses; the rollback
            # restores the exact previous tree as a forward commit and proves the tree hash.
            self.assertIn('git read-tree -u --reset "$pre"', shell)
            self.assertLess(shell.index(r + "ROLLBACK_TREE_MISMATCH"), shell.index(f"{r}ROLLED_BACK_TO_RUNTIME_{prev}"))
            for forbidden in ("--force", "reset --hard", "Copy-Item", "refresh_openditoo_day1_host", "policy-grant"):
                self.assertNotIn(forbidden, shell, forbidden)
            proc = subprocess.run(["bash", "-n", str(path)], capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_runtime_009_is_runtime_008_plus_the_two_owner_review_fixes_only(self):
        old = json.loads((ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-008.json").read_text(encoding="utf-8"))
        new = self.template
        self.assertEqual({k for k in new if new[k] != old.get(k)}, {"authority", "build", "description"})
        self.assertEqual({k for k in new["build"] if new["build"][k] != old["build"][k]}, {"code_sha256"})
        self.assertEqual({k for k, v in new["build"]["code_sha256"].items() if v != old["build"]["code_sha256"][k]},
                         {"activity_lightning_sha256", "product_runtime_v3_sha256"})


if __name__ == "__main__":
    unittest.main()
