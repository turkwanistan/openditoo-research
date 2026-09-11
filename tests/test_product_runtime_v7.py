"""Runtime 013 Pocket Moss v4 art/animation successor offline gates. No Host/device I/O."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from cli import openditoo
from host import product_runtime_v7 as v7
from host.moss_page import MODE_SELECTOR, MossPage
from host.slots_page import SlotsPage
from scripts.interactive_hf3 import FakeClock, FakeHost, PacedEvents
from tests.test_product_runtime_v3 import DryDashboard


def ev(seq, kind, raw):
    return {"epoch":"r013", "seq":seq, "type":kind, "raw_button":raw, "at_utc":None}


class Runtime013PolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads(v7.TEMPLATE.read_text(encoding="utf-8"))
        self.old = json.loads(v7.R012_TEMPLATE.read_text(encoding="utf-8"))

    def test_template_is_unauthorized_art_only_successor(self):
        p = v7.load_policy(v7.TEMPLATE, require_authority=False, verify_hashes=False)
        self.assertEqual(v7.RUNTIME_REVISION, 8)
        for key in ("pages", "session", "target", "behavior", "product_id", "install"):
            self.assertEqual(self.template[key], self.old[key], key)
        self.assertEqual(self.template["build"]["host_dll_sha256"], self.old["build"]["host_dll_sha256"])
        self.assertEqual(self.template["build"]["button_probe_sha256"], self.old["build"]["button_probe_sha256"])
        self.assertEqual(v7.authority_blockers(v7.TEMPLATE),
                         ["PRODUCT_AUTHORITY_MISSING", "PRODUCT_AUTHORITY_UNATTRIBUTED", "PRODUCT_AUTHORITY_SCOPE_MISMATCH"])
        self.assertEqual(self.template["authority"]["required_grant_text"], v7.GRANT_TEXT)
        self.assertEqual(self.template["authority"]["supersedes"], "OPENDITOO-PRODUCT-RUNTIME-012")
        self.assertEqual((p.session_lifetime_seconds, p.max_frames_per_session), (600, 15000))

    def test_policy_hashes_pin_v4_assets_and_not_v3_assets(self):
        expected = v7.code_hashes()
        self.assertEqual(self.template["build"]["code_sha256"], expected)
        self.assertIn("product_runtime_v7_sha256", expected)
        self.assertIn("moss_page_sha256", expected)
        asset_files = sorted(Path("assets/pocket_moss/v4").rglob("*.json"))
        asset_keys = [k for k in expected if k.startswith("moss_v4_asset_")]
        self.assertEqual(len(asset_keys), len(asset_files))
        self.assertFalse(any(k.startswith("moss_asset_") for k in expected))

    def test_cli_routes_revision_8_to_runtime_v7(self):
        self.assertIs(openditoo._product_runtime_module(v7.TEMPLATE), v7)

    def test_cutover_is_exact_grant_gated_and_rolls_back_to_runtime_012(self):
        import subprocess
        shell = Path("scripts/cutover_runtime_013.sh").read_text(encoding="utf-8")
        self.assertIn('BRANCH=feat/pocket-moss-v4-polish\n', shell)
        self.assertIn('Grant OPENDITOO-PRODUCT-RUNTIME-013', shell)
        self.assertIn('OPENDITOO-PRODUCT-RUNTIME-012', shell)
        self.assertIn('rollback-runtime-012', shell)
        self.assertIn('product_check 8', shell)
        self.assertIn('product_check 7', shell)
        self.assertIn('R013_ROLLED_BACK_TO_RUNTIME_012', shell)
        self.assertIn('product_runtime_v7 as v7', shell)
        self.assertIn('assert raw[\"runtime_revision\"] == 8', shell)
        self.assertNotIn('assert raw[\"runtime_revision\"] == 7', shell)
        proc = subprocess.run(["bash", "-n", "scripts/cutover_runtime_013.sh"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_granted_copy_requires_exact_runtime_013_grant_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            doc = copy.deepcopy(self.template); a = doc["authority"]
            a.update(persistent_runtime_authorized=True, grant_text=v7.GRANT_TEXT,
                     granted_by="owner, in-session", grant_scope=a["grant_scope_requested"])
            path.write_text(json.dumps(doc))
            self.assertEqual(v7.authority_blockers(path), [])
            v7.load_policy(path, require_authority=True, verify_hashes=False)
            a["grant_text"] = "Grant OPENDITOO-PRODUCT-RUNTIME-012"
            path.write_text(json.dumps(doc))
            self.assertIn("PRODUCT_AUTHORITY_UNATTRIBUTED", v7.authority_blockers(path))


class Runtime013SupervisorTests(unittest.TestCase):
    def test_three_page_runtime_v2_moss_executes_dance_in_one_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); clock = FakeClock(); invalidations = []
            schedule = [
                (500, ev(1, "nav_right", "Next")),
                (1000, ev(2, "nav_right", "Next")),
                (1500, ev(3, "lever_candidate", "Pause")),
                (1800, ev(4, "nav_right", "Next")),
                (2100, ev(5, "lever_candidate", "Pause")),
            ]
            events = PacedEvents(schedule, clock, invalidations); hosts = []
            def factory():
                host = FakeHost(clock, invalidations); hosts.append(host); return host
            moss = MossPage(seed=3, asset_root=Path("assets/pocket_moss/v4"))
            policy = v7.load_policy(v7.TEMPLATE, require_authority=False, verify_hashes=False)
            state = v7.run_product(policy, factory, stop_requested=lambda: clock.ms >= 7000,
                monotonic=lambda: clock.ms / 1000.0, sleep=lambda s: clock.sleep(s * 1000),
                config={}, activity_state={}, events=events,
                pages=[DryDashboard(), SlotsPage(seed=2), moss], waiting_collector=lambda: None,
                state_file=tmp / "runtime.json", pages_state_file=tmp / "pages.json")
            pages = json.loads((tmp / "pages.json").read_text())
            self.assertEqual(pages["current_page"], "moss")
            self.assertEqual(moss.idle.id, "moss.v4.idle")
            self.assertEqual(moss.completed_actions, 1)
            self.assertEqual(moss.mode, MODE_SELECTOR)
            self.assertEqual(moss.selected_action, "dance")
            self.assertEqual(state["reconnects"], 0); self.assertEqual(state["reclaims"], 0)
            self.assertEqual(len(hosts), 1)


if __name__ == "__main__":
    unittest.main()
