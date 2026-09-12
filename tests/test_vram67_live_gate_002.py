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

import ditoo_vram67_live_gate_002 as gate  # noqa: E402
from ditoo_candidate_codec import decode_candidate_normal  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Vram67Successor002Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "experiments/OPENDITOO-VRAM67-BXLR-002.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_predecessor_is_consumed_inconclusive_and_custom_packet_never_sent(self) -> None:
        report = gate.verify_committed()
        p = report["predecessor"]
        self.assertEqual(p["experiment_id"], "OPENDITOO-VRAM67-BXLR-001")
        self.assertEqual(p["classification"], "TRANSPORT_HARNESS_INCONCLUSIVE_NOT_VRAM_NEGATIVE")
        self.assertFalse(p["custom_0x6c_transmitted"])
        self.assertFalse(p["same_grant_replay_allowed"])
        self.assertEqual(self.manifest["predecessor"]["result_sha256"], sha(ROOT / self.manifest["predecessor"]["result_path"]))

    def test_payload_is_byte_identical_to_001(self) -> None:
        packets = gate.build_packets()
        self.assertEqual(sha(gate.SOURCE_FILE), "7ec43cab8cd04da6b2d90983dcec868baee3a1615448d05f446aa5a1c2e3ce48")
        self.assertEqual(sha(gate.PRIME_FILE), "9f643ace4ce755ddcd04446c0cb21bbaa23b53f123788a225d1c9eda81e213ec")
        self.assertEqual(sha(gate.SETUP_FILE), "4cf9f3d0458664a2c99681e6a672b8eaefea3a043d83a2f15a751aabcd9d0316")
        self.assertEqual(sha(gate.OVERWRITE_FILE), "c3fbc813e2646b44ace4a2105163fe7bc2622d5e6cc61477ac6098d0b23b12cd")
        self.assertEqual(packets["source"][:2], bytes.fromhex("7047"))
        self.assertEqual((decode_candidate_normal(packets["prime"]).command, decode_candidate_normal(packets["prime"]).payload), (0x6E, b"\x01"))
        self.assertEqual((decode_candidate_normal(packets["voicetip"]).command, decode_candidate_normal(packets["voicetip"]).payload), (0xA5, bytes([1, 2, 1])))
        self.assertEqual(decode_candidate_normal(packets["overwrite"]).command, 0x6C)

    def test_manifest_is_fresh_fail_closed_authority(self) -> None:
        m = self.manifest
        self.assertEqual(m["experiment_id"], "OPENDITOO-VRAM67-BXLR-002")
        self.assertEqual(m["status"], "grant_ready_awaiting_named_grant")
        self.assertEqual(m["authority"]["required_grant_text"], "Grant OPENDITOO-VRAM67-BXLR-002 -- stock btplayer selected")
        self.assertFalse(m["authority"]["transmission_authorized"])
        self.assertFalse(m["authority"]["authorization_consumed"])
        self.assertFalse(m["authority"]["previous_grants_transfer"])
        self.assertIsNone(m["result"])
        self.assertFalse(m["transport_semantics"]["payload_changed_from_001"])
        self.assertTrue(m["transport_semantics"]["wire_hashes_identical_to_001"])

    def test_manifest_binds_fixture_and_execution_surface(self) -> None:
        self.assertEqual(self.manifest["fixture_report"]["sha256"], sha(gate.FIXTURE_REPORT))
        for item in self.manifest["execution_surface"]["files"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha(path), item["sha256"], item["path"])

    def test_transport_waits_fdwrite_once_then_one_send_call_per_frame(self) -> None:
        transport = (ROOT / "runtime/windows/OpenDitoo.Vram67.Runner002/WindowsRfcommVram67Transport.cs").read_text(encoding="utf-8")
        self.assertIn("WaitForInitialWritable", transport)
        self.assertEqual(transport.count("SendSingleCall(socketHandle, eventHandle"), 3)
        self.assertIn("exactly one send() call for this application frame", transport)
        self.assertIn('error == WsaWouldBlock ? "WOULD_BLOCK"', transport)
        self.assertNotIn("SendExactlyOnce", transport)
        self.assertNotIn('SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, stage)', transport)

    def test_coordinator_preflights_absolute_windows_bridge_before_handover(self) -> None:
        script = (ROOT / "scripts/run_vram67_bxlr_002_once.sh").read_text(encoding="utf-8")
        self.assertIn("WIN_POWERSHELL=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", script)
        build = script.index("VRAM67_WINDOWS_RUNNER_BUILD_FAILED")
        stop = script.index('systemctl --user stop "$SERVICE"')
        self.assertLess(build, stop)
        self.assertNotIn("\npowershell.exe -NoProfile", script)
        subprocess.run(["bash", "-n", str(ROOT / "scripts/run_vram67_bxlr_002_once.sh")], check=True)

    def test_old_001_execution_surface_is_unchanged(self) -> None:
        old = json.loads((ROOT / "experiments/OPENDITOO-VRAM67-BXLR-001.json").read_text(encoding="utf-8"))
        for item in old["execution_surface"]["files"]:
            self.assertEqual(sha(ROOT / item["path"]), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
