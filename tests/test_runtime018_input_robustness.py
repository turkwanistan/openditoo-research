"""Runtime 018 offline gates: hidden BTVS window + one rebind renewal per sidecar epoch. No Host/device I/O."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from cli import openditoo
from host import product_runtime_v11 as v11
from host import product_runtime_v12 as v12
from host import raw_avrcp_input
from host.slots_page import SlotsPage
from scripts.interactive_hf3 import FakeClock, FakeHost
from tests.test_product_runtime_v3 import DryDashboard

ROOT = Path(__file__).resolve().parents[1]


class _Raw(raw_avrcp_input.RawAvrcpEvents):
    """A real RawAvrcpEvents (so the runtime's isinstance checks apply) whose broker state the test drives."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.capture_ready, self.bound, self.epoch = True, False, "e1"

    def poll(self) -> list[dict]:
        return []


class Runtime018PolicyTests(unittest.TestCase):
    def setUp(self):
        self.new = json.loads(v12.TEMPLATE.read_text(encoding="utf-8"))
        self.old = json.loads(v12.R017_TEMPLATE.read_text(encoding="utf-8"))

    def test_changes_only_the_sidecar_install_identity_over_017(self):
        self.assertEqual((v12.RUNTIME_REVISION, self.new["runtime_revision"]), (13, 13))
        for key in ("target", "session", "behavior", "product_id", "install", "pages"):
            self.assertEqual(self.new[key], self.old[key], key)
        for key in ("host_dll_sha256", "button_probe_sha256"):
            self.assertEqual(self.new["build"][key], self.old["build"][key], key)
        nb, ob = self.new["pagination"]["broker"], self.old["pagination"]["broker"]
        for key in ("kind", "sink_status", "port", "operations", "tshark_exe", "device_attribution", "media_keys"):
            self.assertEqual(nb[key], ob[key], key)
        # Own admin-only root, task and data dir: installing 018 never touches 017's pinned bytes.
        self.assertEqual(nb["launch"]["task_name"], "OpenDitoo Raw AVRCP Broker 018")
        self.assertNotEqual(nb["launch"]["task_name"], ob["launch"]["task_name"])
        self.assertEqual(nb["launch"]["install_root"], v12.RAW_AVRCP_INSTALL_ROOT)
        self.assertFalse(set(self.new["build"]["raw_avrcp_broker_sha256"]) & set(self.old["build"]["raw_avrcp_broker_sha256"]))
        self.assertNotEqual(nb["events_windows_path"], ob["events_windows_path"])
        self.assertNotEqual(nb["launch"]["lease_windows_path"], ob["launch"]["lease_windows_path"])
        # Sink copies are still the exact 016/017-pinned ButtonProbe bytes.
        root = v12.RAW_AVRCP_INSTALL_ROOT + "\\"
        for path, digest in self.new["build"]["button_probe_sha256"].items():
            self.assertEqual(self.new["build"]["raw_avrcp_broker_sha256"][root + "sink\\" + path.rsplit("\\", 1)[1]], digest)

    def test_template_is_unauthorized_hash_complete_and_supersedes_017(self):
        a = self.new["authority"]
        self.assertFalse(a["persistent_runtime_authorized"])
        self.assertIsNone(a["grant_text"])
        self.assertEqual(a["required_grant_text"], "Grant OPENDITOO-PRODUCT-RUNTIME-018")
        self.assertEqual(a["supersedes"], "OPENDITOO-PRODUCT-RUNTIME-017")
        self.assertEqual(self.new["build"]["code_sha256"], v12.code_hashes())
        self.assertIn("product_runtime_v12_sha256", self.new["build"]["code_sha256"])
        v12.load_policy(v12.TEMPLATE, require_authority=False, verify_hashes=False)
        self.assertIn("PRODUCT_AUTHORITY_MISSING", v12.authority_blockers(v12.TEMPLATE))

    def test_policy_rejects_reusing_the_017_install_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "policy.json"
            doc = copy.deepcopy(self.new)
            doc["pagination"]["broker"]["btvs_exe"] = self.old["pagination"]["broker"]["btvs_exe"]
            p.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(Exception) as ctx:
                v12.load_policy(p, require_authority=False, verify_hashes=False, template_path=p)
            self.assertEqual(getattr(ctx.exception, "code", None), "PRODUCT_018_ELEVATED_LAUNCH_MISMATCH")

    def test_granted_copy_requires_exact_018_grant_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            doc = copy.deepcopy(self.new); a = doc["authority"]
            a.update(persistent_runtime_authorized=True, grant_text=v12.GRANT_TEXT,
                     granted_by="owner, in-session", grant_scope=a["grant_scope_requested"])
            path.write_text(json.dumps(doc))
            self.assertEqual(v12.authority_blockers(path), [])
            a["grant_text"] = "Grant OPENDITOO-PRODUCT-RUNTIME-017"
            path.write_text(json.dumps(doc))
            self.assertIn("PRODUCT_AUTHORITY_UNATTRIBUTED", v12.authority_blockers(path))

    def test_cli_routes_revision_13_without_changing_12(self):
        self.assertIs(openditoo._product_runtime_module(v12.TEMPLATE), v12)
        self.assertIs(openditoo._product_runtime_module(v11.TEMPLATE), v11)


class Runtime018RebindTests(unittest.TestCase):
    def _run(self, events, until_ms):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); clock = FakeClock(); hosts = []
            def factory():
                host = FakeHost(clock, []); hosts.append(host); return host
            policy = v12.load_policy(v12.TEMPLATE, require_authority=False, verify_hashes=False)
            state = v12.run_product(policy, factory, stop_requested=lambda: clock.ms >= until_ms,
                monotonic=lambda: clock.ms / 1000.0, sleep=lambda s: clock.sleep(s * 1000),
                config={}, activity_state={}, events=events, pages=[DryDashboard(), SlotsPage(seed=2)],
                waiting_collector=lambda: None, state_file=tmp / "runtime.json", pages_state_file=tmp / "pages.json")
            return state, hosts, json.loads((tmp / "pages.json").read_text()), clock

    def test_unbound_capture_renews_exactly_once_per_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _Raw(Path(tmp) / "events.ndjson")  # capture ready, never bound
            state, hosts, pages, _ = self._run(events, 20000)
        self.assertEqual(len(hosts), 2)            # one renewal, not a loop
        self.assertEqual(state["renewals"], 1)
        self.assertEqual((state["reconnects"], state["reclaims"]), (0, 0))
        self.assertEqual(pages["input_rebind_renewals"], 1)

    def test_bound_or_not_ready_capture_never_renews(self):
        for ready, bound in ((True, True), (False, False)):
            with tempfile.TemporaryDirectory() as tmp:
                events = _Raw(Path(tmp) / "events.ndjson")
                events.capture_ready, events.bound = ready, bound
                state, hosts, _, _ = self._run(events, 20000)
            self.assertEqual((len(hosts), state["renewals"]), (1, 0), (ready, bound))

    def test_guard_waits_the_threshold_latches_and_rearms_only_for_a_new_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _Raw(Path(tmp) / "events.ndjson")
            now = [0.0]
            guard = v12._RebindGuard(events, lambda: now[0])
            self.assertFalse(guard.due())                      # starts the unbound timer
            now[0] = v12.REBIND_UNBOUND_SECONDS - 0.01
            self.assertFalse(guard.due())
            now[0] = v12.REBIND_UNBOUND_SECONDS + 0.01
            self.assertTrue(guard.due())
            self.assertTrue(guard.due())                       # latched until consumed
            guard.fired = False
            now[0] += 60
            self.assertFalse(guard.due()); self.assertFalse(guard.due())   # same epoch: never again
            events.epoch = "e2"                                # sidecar restarted
            self.assertFalse(guard.due())
            now[0] += v12.REBIND_UNBOUND_SECONDS + 0.01
            self.assertTrue(guard.due())
            self.assertEqual(guard.count, 2)
            guard.fired = False; events.epoch = "e3"; events.bound = True   # binding clears the timer
            self.assertFalse(guard.due())


class Runtime018SidecarAndScriptTests(unittest.TestCase):
    def test_broker_hides_btvs_window_and_rehides(self):
        src = (ROOT / "runtime/windows/OpenDitoo.RawAvrcpBroker/Program.cs").read_text(encoding="utf-8")
        self.assertIn("hidden: true);", src[src.index("var btvs = Start(options.BtvsExe"):])
        self.assertIn("if (hidden) psi.WindowStyle = ProcessWindowStyle.Hidden;", src)
        self.assertIn("Win32.ShowWindow(window, 0); // SW_HIDE", src)
        self.assertIn('"btvs_window_hidden"', src)

    def test_installer_is_runtime_parameterized_and_admin_only(self):
        src = (ROOT / "runtime/windows/install_openditoo_raw_avrcp_task.ps1").read_text(encoding="utf-8")
        self.assertIn("[ValidatePattern('^\\d{3}$')][string]$Runtime = '018'", src)
        self.assertIn('$root = [string]$launch.install_root', src)
        self.assertIn("Need ($root -match '^C:\\\\Program Files\\\\OpenDitoo\\\\RawAvrcpBroker\\d*$')", src)
        self.assertNotIn("R017_", src)

    def test_cutover_018_is_exact_grant_gated_and_rolls_back_to_017(self):
        shell = (ROOT / "scripts/cutover_runtime_018.sh").read_text(encoding="utf-8")
        for needle in ('"${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-018"', "OPENDITOO-PRODUCT-RUNTIME-017 ]]",
                       "RB=$LOCAL/rollback-runtime-017", "product_check 12 && echo R018_ROLLBACK_PRODUCT_CHECK_PASS",
                       "product_check 13 && echo R018_PRODUCT_CHECK_PASS", 'RAW_TASK="OpenDitoo Raw AVRCP Broker 018"',
                       "verify-task product/OPENDITOO-PRODUCT-RUNTIME-018.json", "tests.test_runtime018_input_robustness",
                       "inactive|failed) systemctl --user reset-failed", "assert raw['runtime_revision'] == 13"):
            self.assertIn(needle, shell)
        for forbidden in ("016", "stage_openditoo_raw_avrcp_broker.ps1", "--force", "reset --hard", " schtasks.exe"):
            self.assertNotIn(forbidden, shell)
        proc = subprocess.run(["bash", "-n", "scripts/cutover_runtime_018.sh"], capture_output=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_runtime_wires_the_guard_into_the_session_stop_and_renews_before_operator_stop(self):
        src = (ROOT / "host/product_runtime_v12.py").read_text(encoding="utf-8")
        run = src[src.index("def run_product("):]
        self.assertIn("stop_requested=lambda: stop_requested() or rebind.due()", run)
        self.assertLess(run.index("if rebind.fired and not stop_requested():"),
                        run.index('if stop_requested() or reason == "operator_stop":'))
        self.assertIn("for _ in range(80):", run)  # 017's bounded capture head start is kept


if __name__ == "__main__":
    unittest.main()
