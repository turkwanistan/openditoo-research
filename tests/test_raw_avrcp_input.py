import json
from pathlib import Path
import tempfile
import unittest

from host import raw_avrcp_input


class _Proc:
    def __init__(self): self.rc = None
    def poll(self): return self.rc
    def terminate(self): self.rc = -15
    def wait(self, timeout=None): return self.rc
    def kill(self): self.rc = -9


class RawAvrcpInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.events = self.root / "events.ndjson"
        self.sink = self.root / "sink.ndjson"
        self.clock = 0.0

    def tearDown(self): self.tmp.cleanup()

    def append(self, row):
        with self.events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    @staticmethod
    def row(seq, candidate, *, epoch="e1", source="avrcp_raw", op="0x46"):
        return {"epoch": epoch, "seq": seq, "type": "event", "source": source,
                "normalized_candidate": candidate, "raw_button": "x", "operation": op,
                "at_utc": "2026-09-11T00:00:00Z"}

    def test_cursor_accepts_raw_only_maps_both_lever_opcodes_and_is_at_most_once(self):
        cursor = raw_avrcp_input.RawAvrcpEvents(self.events)
        self.append(self.row(1, "nav_left", op="0x4C"))
        self.append(self.row(2, "lever_candidate", op="0x44"))
        self.append(self.row(3, "lever_candidate", op="0x46"))
        self.append(self.row(4, "nav_right", source="smtc", op="0x4B"))
        got = cursor.poll()
        self.assertEqual([x["type"] for x in got], ["nav_left", "lever_candidate", "lever_candidate"])
        self.assertEqual([x["operation"] for x in got], ["0x4C", "0x44", "0x46"])
        self.assertEqual(cursor.poll(), [])

    def test_cursor_rebases_on_new_epoch_counts_gap_and_rejects_bad_lines(self):
        cursor = raw_avrcp_input.RawAvrcpEvents(self.events)
        self.append(self.row(4, "nav_left", epoch="a"))
        self.append(self.row(6, "nav_right", epoch="a"))
        self.append({"broken": True})
        self.append(self.row(1, "lever_candidate", epoch="b"))
        self.assertEqual(len(cursor.poll()), 3)
        self.assertEqual(cursor.gaps, 1)
        self.assertEqual(cursor.epochs, 2)
        self.assertEqual(cursor.rejected_lines, 1)

    def test_broker_starts_one_sidecar_truncates_private_files_and_rate_limits_restart(self):
        launched = []
        def popen(args, **kwargs):
            launched.append((args, kwargs))
            return _Proc()
        self.events.write_text("stale\n")
        self.sink.write_text("stale\n")
        broker = raw_avrcp_input.RawAvrcpBroker(
            Path("C:/broker.exe"), target="AA:BB:CC:DD:EE:FF",
            events_windows_path=r"\\wsl\events.ndjson", events_file=self.events,
            sink_exe=Path("C:/sink.exe"), sink_log_windows_path=r"\\wsl\sink.ndjson", sink_log_file=self.sink,
            btvs_exe=Path("C:/btvs.exe"), tshark_exe=Path("C:/tshark.exe"),
            popen=popen, monotonic=lambda: self.clock)
        broker.ensure()
        self.assertEqual(self.events.read_bytes(), b"")
        self.assertEqual(self.sink.read_bytes(), b"")
        args = launched[0][0]
        self.assertIn("--target", args)
        self.assertIn("--sink-exe", args)
        self.assertIn("--btvs", args)
        self.assertIn("--tshark", args)
        broker.process.rc = 2
        broker.ensure()
        self.assertEqual(len(launched), 1)
        self.clock += 5.0
        broker.ensure()
        self.assertEqual(len(launched), 2)
        broker.stop()

    def test_module_has_no_device_transport_or_network_client(self):
        src = Path(raw_avrcp_input.__file__).read_text(encoding="utf-8")
        lowered = src.lower()
        for forbidden in ("import socket", "from socket", "import urllib", "import requests",
                          "image/show", "session/open"):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
