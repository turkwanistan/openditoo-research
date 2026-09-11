"""Runtime 011 Pocket Moss v2 art successor offline gates. No Host/device I/O."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cli import openditoo
from host import product_runtime_v5 as v5
from host.moss_page import ASSET_ROOT, MODE_SELECTOR, MossPage
from host.slots_page import SlotsPage
from scripts.interactive_hf3 import FakeClock, FakeHost, PacedEvents
from tests.test_product_runtime_v3 import DryDashboard


def ev(seq, kind, raw):
    return {"epoch":"r011", "seq":seq, "type":kind, "raw_button":raw, "at_utc":None}


class Runtime011PolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads(v5.TEMPLATE.read_text(encoding="utf-8"))
        self.old = json.loads(v5.R010_TEMPLATE.read_text(encoding="utf-8"))

    def test_template_is_unauthorized_art_only_successor(self):
        p = v5.load_policy(v5.TEMPLATE, require_authority=False, verify_hashes=False)
        self.assertEqual(v5.RUNTIME_REVISION, 6)
        for key in ("pages", "session", "target", "behavior", "product_id", "install"):
            self.assertEqual(self.template[key], self.old[key], key)
        self.assertEqual(self.template["build"]["host_dll_sha256"], self.old["build"]["host_dll_sha256"])
        self.assertEqual(self.template["build"]["button_probe_sha256"], self.old["build"]["button_probe_sha256"])
        self.assertEqual(v5.authority_blockers(v5.TEMPLATE),
                         ["PRODUCT_AUTHORITY_MISSING", "PRODUCT_AUTHORITY_UNATTRIBUTED", "PRODUCT_AUTHORITY_SCOPE_MISMATCH"])
        self.assertEqual(self.template["authority"]["required_grant_text"], v5.GRANT_TEXT)
        self.assertEqual(self.template["authority"]["supersedes"], "OPENDITOO-PRODUCT-RUNTIME-010")
        self.assertEqual((p.session_lifetime_seconds, p.max_frames_per_session), (600, 15000))

    def test_policy_hashes_pin_v2_assets_and_not_v1_assets(self):
        stored = self.template["build"]["code_sha256"]
        self.assertIn("product_runtime_v5_sha256", stored)
        self.assertIn("moss_page_sha256", stored)
        self.assertEqual(stored["product_runtime_v5_sha256"], hashlib.sha256(Path("host/product_runtime_v5.py").read_bytes()).hexdigest())
        asset_files = sorted(Path("assets/pocket_moss/v2").rglob("*.json"))
        asset_keys = [k for k in stored if k.startswith("moss_v2_asset_")]
        self.assertEqual(len(asset_keys), len(asset_files))
        for key, path in v5.HASHED_MODULES.items():
            if key.startswith("moss_v2_asset_"):
                self.assertEqual(stored[key], hashlib.sha256(path.read_bytes()).hexdigest(), key)
        self.assertFalse(any(k.startswith("moss_asset_") for k in stored))
        if ASSET_ROOT.name == "v2":
            self.assertEqual(stored, v5.code_hashes())
        else:
            self.assertNotEqual(stored, v5.code_hashes())

    def test_cli_routes_revision_6_to_runtime_v5(self):
        self.assertIs(openditoo._product_runtime_module(v5.TEMPLATE), v5)

    def test_cutover_is_exact_grant_gated_and_rolls_back_to_runtime_010(self):
        import subprocess
        shell = Path("scripts/cutover_runtime_011.sh").read_text(encoding="utf-8")
        self.assertIn('BRANCH=feat/pocket-moss-v2-art-r2\n', shell)
        self.assertIn('Grant OPENDITOO-PRODUCT-RUNTIME-011', shell)
        self.assertIn('OPENDITOO-PRODUCT-RUNTIME-010', shell)
        self.assertIn('rollback-runtime-010', shell)
        self.assertIn('product_check 6', shell)
        self.assertIn('product_check 5', shell)
        self.assertIn('R011_ROLLED_BACK_TO_RUNTIME_010', shell)
        self.assertIn('product_runtime_v5 as v5', shell)
        proc = subprocess.run(["bash", "-n", "scripts/cutover_runtime_011.sh"], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_granted_copy_requires_exact_runtime_011_grant_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            doc = copy.deepcopy(self.template); a = doc["authority"]
            a.update(persistent_runtime_authorized=True, grant_text=v5.GRANT_TEXT,
                     granted_by="owner, in-session", grant_scope=a["grant_scope_requested"])
            path.write_text(json.dumps(doc))
            self.assertEqual(v5.authority_blockers(path), [])
            v5.load_policy(path, require_authority=True, verify_hashes=False)
            a["grant_text"] = "Grant OPENDITOO-PRODUCT-RUNTIME-010"
            path.write_text(json.dumps(doc))
            self.assertIn("PRODUCT_AUTHORITY_UNATTRIBUTED", v5.authority_blockers(path))


class Runtime011SupervisorTests(unittest.TestCase):
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
            moss = MossPage(seed=3, asset_root=Path("assets/pocket_moss/v2"))
            policy = v5.load_policy(v5.TEMPLATE, require_authority=False, verify_hashes=False)
            state = v5.run_product(policy, factory, stop_requested=lambda: clock.ms >= 7000,
                monotonic=lambda: clock.ms / 1000.0, sleep=lambda s: clock.sleep(s * 1000),
                config={}, activity_state={}, events=events,
                pages=[DryDashboard(), SlotsPage(seed=2), moss], waiting_collector=lambda: None,
                state_file=tmp / "runtime.json", pages_state_file=tmp / "pages.json")
            pages = json.loads((tmp / "pages.json").read_text())
            self.assertEqual(pages["current_page"], "moss")
            self.assertEqual(moss.idle.id, "moss.v2.idle")
            self.assertEqual(moss.completed_actions, 1)
            self.assertEqual(moss.mode, MODE_SELECTOR)
            self.assertEqual(moss.selected_action, "dance")
            self.assertEqual(state["reconnects"], 0); self.assertEqual(state["reclaims"], 0)
            self.assertEqual(len(hosts), 1)


if __name__ == "__main__":
    unittest.main()
