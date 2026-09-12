from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "host"))

import ditoo_vram67_live_gate as gate  # noqa: E402
from ditoo_candidate_codec import decode_candidate_normal  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Vram67LiveGatePreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "experiments/OPENDITOO-VRAM67-BXLR-001.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_four_authoritative_artifacts_and_fixture_are_current(self) -> None:
        report = gate.verify_committed()
        self.assertTrue(report["ok"])
        expected = {
            "tier2_display": "e7055f2f37c7404fd53d59d8acf48cd502aeb563ea6a53a045f51bd395871013",
            "tier2_placement": "045c4da0bd2fb2c63609ce578d082e063d263ec3dccce9a8f492c48374182999",
            "tier2_trigger": "c6ae80bd9df73f6c0b8286a443d26e8ef03b5bf3e16d0fbd552949c666b15cee",
            "vram3_execution": "ae0bd733b6cac05ab39e65a03d896e34c889c2e7c5c476789a16c8cbe414803d",
        }
        for name, digest in expected.items():
            self.assertEqual(report["authoritative_artifacts"][name]["sha256"], digest)

    def test_exact_source_and_three_packets(self) -> None:
        packets = gate.build_packets()
        source = packets["source"]
        self.assertEqual(len(source), 1088)
        self.assertEqual(source[:2], bytes.fromhex("7047"))
        self.assertEqual(source[1032], 0xFF)
        self.assertEqual(source[1040], 0x22)
        self.assertEqual(source[1084:1088], bytes.fromhex("79478000"))
        self.assertEqual(sha(gate.SOURCE_FILE), "7ec43cab8cd04da6b2d90983dcec868baee3a1615448d05f446aa5a1c2e3ce48")

        prime = decode_candidate_normal(packets["prime"])
        setup = decode_candidate_normal(packets["voicetip"])
        overwrite = decode_candidate_normal(packets["overwrite"])
        self.assertEqual((prime.command, prime.payload), (0x6E, b"\x01"))
        self.assertEqual((setup.command, setup.payload), (0xA5, bytes([1, 2, 1])))
        self.assertEqual(overwrite.command, 0x6C)
        self.assertEqual(overwrite.payload[:4], bytes.fromhex("00004004"))
        self.assertEqual(overwrite.payload[4:], source)
        self.assertEqual(len(packets["overwrite"]), 1099)
        self.assertEqual(sha(gate.OVERWRITE_FILE), "c3fbc813e2646b44ace4a2105163fe7bc2622d5e6cc61477ac6098d0b23b12cd")

    def test_manifest_is_fail_closed_and_one_use(self) -> None:
        m = self.manifest
        self.assertEqual(m["status"], "grant_ready_awaiting_named_grant")
        self.assertEqual(m["authority"]["required_grant_text"], gate.GRANT_TEXT)
        self.assertFalse(m["authority"]["transmission_authorized"])
        self.assertFalse(m["authority"]["authorization_consumed"])
        self.assertFalse(m["authority"]["previous_grants_transfer"])
        self.assertIsNone(m["result"])
        budget = m["transport_budget"]
        self.assertEqual(budget["max_connections"], 1)
        self.assertEqual(budget["exact_application_sends"], 3)
        self.assertEqual(budget["max_custom_0x6c_sends"], 1)
        self.assertEqual(budget["additional_application_packets_allowed"], 0)
        self.assertFalse(budget["retry"])
        self.assertFalse(budget["reconnect"])
        self.assertEqual(budget["observation_hold_ms_after_overwrite"], 75000)
        self.assertEqual(m["stage0"]["bytes_hex"], "7047")
        self.assertEqual(m["stage0"]["instruction"], "BX LR")
        self.assertFalse(m["stage0"]["follow_on_payload"])
        self.assertFalse(m["execution_surface"]["generic_raw_packet_tool"])
        self.assertFalse(m["execution_surface"]["accepts_packet_bytes_from_cli"])
        self.assertFalse(m["execution_surface"]["accepts_target_from_cli"])
        self.assertFalse(m["execution_surface"]["loader"])
        self.assertFalse(m["execution_surface"]["persistence"])

    def test_manifest_binds_fixture_and_execution_surface(self) -> None:
        self.assertEqual(self.manifest["fixture_report"]["sha256"], sha(gate.FIXTURE_REPORT))
        for item in self.manifest["execution_surface"]["files"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha(path), item["sha256"], item["path"])

    def test_runtime018_is_exact_accepted_policy_and_restore_target(self) -> None:
        p = ROOT / self.manifest["preconditions"]["runtime018_policy_path"]
        self.assertEqual(sha(p), self.manifest["preconditions"]["runtime018_policy_sha256"])
        self.assertEqual(self.manifest["preconditions"]["runtime018_revision"], 13)
        self.assertEqual(self.manifest["runtime018_handover"]["service"], "openditoo-product.service")
        self.assertFalse(self.manifest["runtime018_handover"]["experiment_retry_during_restore"])

    def test_orchestrator_checks_grant_before_runtime018_stop(self) -> None:
        script = (ROOT / "scripts/run_vram67_bxlr_001_once.sh").read_text(encoding="utf-8")
        grant_gate = script.index('[[ -f "$GRANT_FILE" ]]')
        stop_runtime = script.index('systemctl --user stop "$SERVICE"')
        self.assertLess(grant_gate, stop_runtime)
        self.assertIn("VRAM67_EXACT_GRANT_NOT_MATERIALIZED", script)
        self.assertIn("STOP_NO_RETRY", (ROOT / "runtime/windows/OpenDitoo.Vram67.Runner/Program.cs").read_text(encoding="utf-8"))
        subprocess.run(["bash", "-n", str(ROOT / "scripts/run_vram67_bxlr_001_once.sh")], check=True)

    def test_dedicated_windows_runner_has_no_packet_or_target_cli(self) -> None:
        program = (ROOT / "runtime/windows/OpenDitoo.Vram67.Runner/Program.cs").read_text(encoding="utf-8")
        self.assertIn('args[0] != "--repo-root"', program)
        self.assertNotIn("--packet", program)
        self.assertNotIn("--target", program)
        protocol = (ROOT / "runtime/windows/OpenDitoo.Vram67.Runner/FrozenVram67Protocol.cs").read_text(encoding="utf-8")
        self.assertIn('TargetMac = "11:75:58:CE:DE:C7"', protocol)
        self.assertIn('RequiredGrantText = "Grant OPENDITOO-VRAM67-BXLR-001 -- stock btplayer selected"', protocol)
        self.assertIn('BuildFrame(0x6C, payload)', protocol)
        self.assertNotIn("Console.ReadLine", program + protocol)


if __name__ == "__main__":
    unittest.main()
