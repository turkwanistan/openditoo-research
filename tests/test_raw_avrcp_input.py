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

    def test_cursor_tracks_capture_ready_and_binding_per_epoch(self):
        cursor = raw_avrcp_input.RawAvrcpEvents(self.events)
        self.append({"epoch": "a", "seq": 1, "type": "broker_started"})
        self.append({"epoch": "a", "seq": 2, "type": "capture_ready"})
        self.append({"epoch": "a", "seq": 3, "type": "handle_bound", "acl_handle": "0x0100"})
        self.assertEqual(cursor.poll(), [])
        self.assertTrue(cursor.capture_ready and cursor.bound)
        self.append({"epoch": "a", "seq": 4, "type": "handle_unbound"})
        cursor.poll()
        self.assertFalse(cursor.bound)
        self.append({"epoch": "b", "seq": 1, "type": "broker_started"})  # restarted broker: fresh baseline
        cursor.poll()
        self.assertFalse(cursor.capture_ready or cursor.bound)

    def test_broker_runs_elevated_task_keeps_lease_changing_and_never_blocks(self):
        calls = []
        def popen(args, **kwargs):
            calls.append(args)
            return _Proc()
        lease = self.root / "raw" / "lease"
        broker = raw_avrcp_input.RawAvrcpBroker("OpenDitoo Raw AVRCP Broker", lease, popen=popen,
                                                monotonic=lambda: self.clock)
        broker.ensure()
        self.assertEqual(calls, [[raw_avrcp_input.SCHTASKS, "/run", "/tn", "OpenDitoo Raw AVRCP Broker"]])
        first = lease.read_text()
        broker.request.rc = 0
        self.clock += 1.0
        broker.ensure()
        self.assertNotEqual(lease.read_text(), first)       # lease content changes every second
        self.assertTrue(broker.alive)
        self.assertEqual(len(calls), 1)                     # run request rate-limited to once/5 s
        self.clock += 4.0
        broker.ensure()
        self.assertEqual(len(calls), 2)
        self.clock += 5.0
        broker.ensure()                                     # previous request still pending: no pile-up
        self.assertEqual(len(calls), 2)
        broker.request.rc = 1
        self.clock += 5.0
        broker.ensure()
        self.assertFalse(broker.alive)                      # missing/unrunnable task is visible
        broker.stop()
        self.assertFalse(lease.exists())
        self.assertEqual(calls[-1], [raw_avrcp_input.SCHTASKS, "/end", "/tn", "OpenDitoo Raw AVRCP Broker"])

    def test_windows_tools_are_absolute_because_systemd_has_no_windows_path(self):
        self.assertEqual(raw_avrcp_input.SCHTASKS, "/mnt/c/Windows/System32/schtasks.exe")
        src = Path(raw_avrcp_input.__file__).read_text(encoding="utf-8")
        self.assertNotIn('["schtasks.exe"', src)
        self.assertNotIn('[\'schtasks.exe\'', src)

    def _policy_broker(self):
        raw = json.loads((Path(__file__).resolve().parents[1] / "product/OPENDITOO-PRODUCT-RUNTIME-017.json")
                         .read_text(encoding="utf-8"))
        return raw["pagination"]["broker"], raw["target"]["exact_unit_id"]

    def _task_xml(self, broker, target, **over):
        f = dict(command=broker["exe"], arguments=raw_avrcp_input.task_arguments(broker, target),
                 run_level="HighestAvailable", logon="InteractiveToken", instances="IgnoreNew", triggers="")
        f.update(over)
        esc = lambda v: v.replace("&", "&amp;").replace('"', "&quot;")
        return ('<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                f'<Triggers>{f["triggers"]}</Triggers><Principals><Principal id="Author">'
                f'<LogonType>{f["logon"]}</LogonType><RunLevel>{f["run_level"]}</RunLevel></Principal></Principals>'
                f'<Settings><MultipleInstancesPolicy>{f["instances"]}</MultipleInstancesPolicy></Settings>'
                f'<Actions Context="Author"><Exec><Command>{esc(f["command"])}</Command>'
                f'<Arguments>{esc(f["arguments"])}</Arguments></Exec></Actions></Task>')

    def test_task_xml_must_match_policy_exactly(self):
        broker, target = self._policy_broker()
        self.assertEqual(raw_avrcp_input.task_problems(self._task_xml(broker, target), broker, target), [])
        bad = {
            "command": dict(command=r"C:\Users\x\AppData\Local\evil.exe"),
            "arguments": dict(arguments=raw_avrcp_input.task_arguments(broker, target).replace("24353", "24354")),
            "privilege": dict(run_level="LeastPrivilege"),
            "session": dict(logon="Password"),
            "instances": dict(instances="Parallel"),
            "trigger": dict(triggers="<LogonTrigger/>"),
        }
        for name, over in bad.items():
            self.assertTrue(raw_avrcp_input.task_problems(self._task_xml(broker, target, **over), broker, target), name)

    def test_task_arguments_are_fixed_quoted_and_reject_injection(self):
        broker, target = self._policy_broker()
        line = raw_avrcp_input.task_arguments(broker, target)
        self.assertTrue(line.startswith('"--seconds" "0" "--target"'))
        self.assertIn('"--lease" "' + broker["launch"]["lease_windows_path"] + '"', line)
        for evil in ('C:\\x" --btvs "C:\\evil.exe', 'C:\\dir\\'):
            with self.assertRaises(ValueError):
                raw_avrcp_input.task_arguments(dict(broker, sink_exe=evil), target)

    def test_module_has_no_device_transport_or_network_client(self):
        src = Path(raw_avrcp_input.__file__).read_text(encoding="utf-8")
        lowered = src.lower()
        for forbidden in ("import socket", "from socket", "import urllib", "import requests",
                          "image/show", "session/open"):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
