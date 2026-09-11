"""Runtime 010 Pocket Moss successor offline gates. No Host/device I/O."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from cli import openditoo
from host import product_runtime_v4 as v4
from host.moss_page import MODE_SELECTOR, MossPage
from host.slots_page import SlotsPage
from scripts.interactive_hf3 import FakeClock, FakeHost, PacedEvents
from tests.test_product_runtime_v3 import DryDashboard


def ev(seq, kind, raw):
    return {"epoch":"r010", "seq":seq, "type":kind, "raw_button":raw, "at_utc":None}


class Runtime010PolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads(v4.TEMPLATE.read_text(encoding="utf-8"))

    def test_template_is_unauthorized_three_page_successor_with_same_envelope_host_and_probe(self):
        p = v4.load_policy(v4.TEMPLATE, require_authority=False, verify_hashes=False)
        self.assertEqual(v4.RUNTIME_REVISION, 5)
        self.assertEqual([x["name"] for x in self.template["pages"]], ["dashboard", "slots", "moss"])
        self.assertEqual(self.template["session"], json.loads(v4.R009_TEMPLATE.read_text())["session"])
        old = json.loads(v4.R009_TEMPLATE.read_text())
        self.assertEqual(self.template["build"]["host_dll_sha256"], old["build"]["host_dll_sha256"])
        self.assertEqual(self.template["build"]["button_probe_sha256"], old["build"]["button_probe_sha256"])
        self.assertEqual(v4.authority_blockers(v4.TEMPLATE),
                         ["PRODUCT_AUTHORITY_MISSING", "PRODUCT_AUTHORITY_UNATTRIBUTED", "PRODUCT_AUTHORITY_SCOPE_MISMATCH"])
        self.assertEqual((p.session_lifetime_seconds, p.max_frames_per_session), (600, 15000))

    def test_policy_hashes_pin_runtime_lab_moss_code_and_every_v1_json_asset(self):
        expected = v4.code_hashes()
        self.assertEqual(self.template["build"]["code_sha256"], expected)
        self.assertIn("product_runtime_v4_sha256", expected)
        self.assertIn("moss_page_sha256", expected)
        self.assertIn("pixel_art_sha256", expected)
        self.assertIn("pixel_animation_sha256", expected)
        asset_files = sorted(Path("assets/pocket_moss/v1").rglob("*.json"))
        asset_keys = [k for k in expected if k.startswith("moss_asset_")]
        self.assertEqual(len(asset_keys), len(asset_files))

    def test_cli_routes_revision_5_to_runtime_v4(self):
        self.assertIs(openditoo._product_runtime_module(v4.TEMPLATE), v4)

    def test_cutover_is_exact_grant_gated_and_rolls_back_to_runtime_009(self):
        import subprocess
        shell = Path("scripts/cutover_runtime_010.sh").read_text(encoding="utf-8")
        self.assertIn('BRANCH=feat/pocket-moss-pixel-lab', shell)
        self.assertIn('Grant OPENDITOO-PRODUCT-RUNTIME-010', shell)
        self.assertIn('OPENDITOO-PRODUCT-RUNTIME-009', shell)
        self.assertIn('rollback-runtime-009', shell)
        self.assertIn('product_check 5', shell)
        self.assertIn('product_check 4', shell)
        self.assertIn('R010_ROLLED_BACK_TO_RUNTIME_009', shell)
        self.assertNotIn('restore the Runtime 008 source tree', shell)
        order = [shell.index(marker) for marker in (
            'R010_EXACT_GRANT_REQUIRED', 'R010_ROLLBACK_SAVED', 'R010_HOST_IDLE',
            'R010_MAIN_FAST_FORWARDED', 'R010_MAIN_OFFLINE_PASS', 'R010_LOCAL_POLICY_WRITTEN')]
        order.append(shell.index('start_and_confirm ||'))
        self.assertEqual(order, sorted(order))
        proc = subprocess.run(["bash", "-n", "scripts/cutover_runtime_010.sh"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_granted_copy_requires_exact_runtime_010_grant_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            doc = copy.deepcopy(self.template); a = doc["authority"]
            a.update(persistent_runtime_authorized=True, grant_text=v4.GRANT_TEXT,
                     granted_by="owner, in-session", grant_scope=a["grant_scope_requested"])
            path.write_text(json.dumps(doc))
            self.assertEqual(v4.authority_blockers(path), [])
            v4.load_policy(path, require_authority=True, verify_hashes=False)
            a["grant_text"] = "Grant OPENDITOO-PRODUCT-RUNTIME-009"
            path.write_text(json.dumps(doc))
            self.assertIn("PRODUCT_AUTHORITY_UNATTRIBUTED", v4.authority_blockers(path))


class Runtime010SupervisorTests(unittest.TestCase):
    def test_three_page_runtime_reaches_moss_executes_dance_and_stays_single_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clock = FakeClock(); invalidations = []
            schedule = [
                (500, ev(1, "nav_right", "Next")),       # dashboard -> slots
                (1000, ev(2, "nav_right", "Next")),      # slots -> moss
                (1500, ev(3, "lever_candidate", "Pause")), # enter selector
                (1800, ev(4, "nav_right", "Next")),      # Pet -> Dance (page consumes)
                (2100, ev(5, "lever_candidate", "Pause")), # execute Dance
            ]
            events = PacedEvents(schedule, clock, invalidations)
            hosts = []
            def factory():
                host = FakeHost(clock, invalidations); hosts.append(host); return host
            moss = MossPage(seed=3)
            policy = v4.load_policy(v4.TEMPLATE, require_authority=False, verify_hashes=False)
            state = v4.run_product(
                policy, factory,
                stop_requested=lambda: clock.ms >= 7000,
                monotonic=lambda: clock.ms / 1000.0,
                sleep=lambda s: clock.sleep(s * 1000),
                config={}, activity_state={}, events=events,
                pages=[DryDashboard(), SlotsPage(seed=2), moss],
                waiting_collector=lambda: None,
                state_file=tmp / "runtime.json", pages_state_file=tmp / "pages.json")
            pages = json.loads((tmp / "pages.json").read_text())
            self.assertEqual(pages["current_page"], "moss")
            self.assertEqual(pages["page_transitions"], 2)
            self.assertEqual(pages["inputs_applied"], 5)
            self.assertEqual(moss.interaction_count, 1)
            self.assertEqual(moss.completed_actions, 1)
            self.assertEqual(moss.mode, MODE_SELECTOR)
            self.assertEqual(moss.selected_action, "dance")
            self.assertEqual(pages["moss"]["mode"], MODE_SELECTOR)
            self.assertEqual(state["reconnects"], 0)
            self.assertEqual(state["reclaims"], 0)
            self.assertEqual(len(hosts), 1, "page changes and modal navigation must not reopen the Host")


if __name__ == "__main__":
    unittest.main()
