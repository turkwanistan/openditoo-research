"""Receive-only raw AVRCP input broker for media-resilient OpenDitoo controls.

The Windows sidecar runs as an elevated on-demand scheduled task (BTVS requires elevation) and owns three
receive-only helper processes:
- OpenDitoo.ButtonProbe in fixed ``playing`` mode, solely to keep Windows media-session ownership;
- Microsoft BTVS on a dedicated local TCP port;
- tshark, reading raw L2CAP bytes; the Ditoo ACL handle is learned at runtime from OpenDitoo's own outbound
  image preambles (never persisted), and only inbound AVRCP pass-through PRESS commands on it become input.

Only normalized input NDJSON crosses back into WSL. No Bluetooth write, Host call, RFCOMM controller,
media injection, or device target selection exists here. The hash-bound policy target is passed only as the
audit label for the learned handle.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from typing import Callable

INPUT_TYPES = {"nav_left", "nav_right", "lever_candidate"}
MAX_LINE_BYTES = 4096
BROKER_RESTART_SECONDS = 5.0
LEASE_WRITE_SECONDS = 1.0  # sidecar expires after 15 s without a change


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RawAvrcpEvents:
    """At-most-once cursor over the raw broker's normalized event stream.

    Starts at EOF so stale input can never replay after a product restart. A broker restart truncates the
    file and creates a new epoch. Only ``source=avrcp_raw`` records with one of the three normalized input
    types are exposed to the page driver.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self.offset = self.path.stat().st_size
        except FileNotFoundError:
            self.offset = 0
        self.pending = b""
        self.epoch: str | None = None
        self.last_seq = 0
        self.gaps = 0
        self.epochs = 0
        self.rejected_lines = 0

    def poll(self) -> list[dict]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []
        if size < self.offset:
            self.offset, self.pending = 0, b""
        if size == self.offset:
            return []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read(size - self.offset)
        self.offset += len(chunk)
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        if len(self.pending) > MAX_LINE_BYTES:
            self.pending, self.rejected_lines = b"", self.rejected_lines + 1
        events = []
        for line in lines:
            if len(line) > MAX_LINE_BYTES:
                self.rejected_lines += 1
                continue
            try:
                record = json.loads(line)
                epoch, seq = str(record["epoch"]), int(record["seq"])
            except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                self.rejected_lines += 1
                continue
            if epoch != self.epoch:
                self.epoch, self.epochs = epoch, self.epochs + 1
            elif seq <= self.last_seq:
                continue
            elif seq != self.last_seq + 1:
                self.gaps += 1
            self.last_seq = seq
            if record.get("type") == "event" and record.get("source") == "avrcp_raw" \
                    and record.get("normalized_candidate") in INPUT_TYPES:
                events.append({
                    "epoch": epoch,
                    "seq": seq,
                    "type": record["normalized_candidate"],
                    "raw_button": record.get("raw_button"),
                    "operation": record.get("operation"),
                    "at_utc": record.get("at_utc"),
                })
        return events


class RawAvrcpBroker:
    """Keep the elevated raw-AVRCP sidecar alive without ever elevating this process.

    BTVS requires elevation, so the sidecar runs as an on-demand, highest-privilege scheduled task registered once
    from Administrator PowerShell (``runtime/windows/install_openditoo_raw_avrcp_task.ps1``). Its executables live
    in an admin-only directory and its arguments are fixed at registration from the hash-bound policy, so this side
    can only ask Task Scheduler to run it (a no-op while it already runs) and keep a lease changing. The sidecar
    exits by itself once the lease stops changing, so it never outlives the product.
    """

    def __init__(self, task_name: str, lease_file: Path, *, popen=subprocess.Popen,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.task_name, self.lease_file = task_name, Path(lease_file)
        self.popen, self.monotonic = popen, monotonic
        self.request = None  # last schtasks.exe child; never waited on inside the input poll loop
        self.starts = 0
        self.beats = 0
        self.last_start = float("-inf")
        self.last_lease = float("-inf")
        self.last_exit_code: int | None = None

    def _schtasks(self, verb: str):
        return self.popen(["schtasks.exe", verb, "/tn", self.task_name], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def ensure(self) -> None:
        now = self.monotonic()
        if now - self.last_lease >= LEASE_WRITE_SECONDS:
            self.last_lease, self.beats = now, self.beats + 1
            self.lease_file.parent.mkdir(parents=True, exist_ok=True)
            self.lease_file.write_text(f"{self.beats}\n", encoding="ascii")
        if self.request is not None:
            code = self.request.poll()
            if code is None:
                return
            self.last_exit_code, self.request = code, None
        if now - self.last_start < BROKER_RESTART_SECONDS:
            return
        self.last_start = now
        self.request = self._schtasks("/run")  # MultipleInstances=IgnoreNew: harmless while running
        self.starts += 1

    @property
    def alive(self) -> bool:
        """Task Scheduler accepted the last run request (the task exists and is runnable)."""
        return self.last_exit_code == 0

    def stop(self) -> None:
        try:
            self.lease_file.unlink()  # even if /end fails, the sidecar expires on its own
        except FileNotFoundError:
            pass
        end = self._schtasks("/end")
        try:
            end.wait(timeout=10)
        except subprocess.TimeoutExpired:
            end.kill()

    def telemetry(self) -> dict:
        return {
            "alive": self.alive,
            "starts": self.starts,
            "last_exit_code": self.last_exit_code,
            "mode": "raw_avrcp_plus_playing_smtc_sink_via_elevated_task",
            "updated_at": _utc(),
        }


def task_arguments(broker: dict, target: str) -> str:
    """The exact argument line the elevated task must carry; the installer builds the same line from the policy."""
    values = ["--seconds", "0", "--target", target, "--events", broker["events_windows_path"],
              "--sink-log", broker["sink_log_windows_path"], "--sink-exe", broker["sink_exe"],
              "--btvs", broker["btvs_exe"], "--tshark", broker["tshark_exe"], "--port", str(broker["port"]),
              "--lease", broker["launch"]["lease_windows_path"]]
    for value in values:
        if '"' in value or value.endswith("\\"):
            raise ValueError(f"unquotable task argument: {value}")
    return " ".join(f'"{value}"' for value in values)


def task_problems(xml_text: str, broker: dict, target: str) -> list[str]:
    """Compare a registered task (``schtasks /query /xml``) with the policy. Empty list means it matches."""
    import xml.etree.ElementTree as ET
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    root = ET.fromstring(xml_text)
    text = lambda path: (root.findtext(path, default="", namespaces=ns) or "").strip()
    execs = root.findall("t:Actions/t:Exec", ns)
    problems = []
    if len(execs) != 1 or len(list(root.find("t:Actions", ns))) != 1:
        problems.append("task must have exactly one Exec action")
    if text("t:Actions/t:Exec/t:Command").strip('"') != broker["exe"]:
        problems.append("task command is not the admin-only broker")
    if text("t:Actions/t:Exec/t:Arguments") != task_arguments(broker, target):
        problems.append("task arguments differ from policy")
    if text("t:Principals/t:Principal/t:RunLevel") != "HighestAvailable":
        problems.append("task is not highest-privilege")
    if text("t:Principals/t:Principal/t:LogonType") != "InteractiveToken":
        problems.append("task does not run in the interactive session")
    if text("t:Settings/t:MultipleInstancesPolicy") != "IgnoreNew":
        problems.append("task may start a second instance")
    triggers = root.find("t:Triggers", ns)
    if triggers is not None and len(list(triggers)):
        problems.append("task must be on-demand only (no triggers)")
    return problems


def main(argv: list[str]) -> int:
    """``python3 -m host.raw_avrcp_input verify-task <policy.json>``: read-only check of the registered task."""
    if len(argv) != 2 or argv[0] != "verify-task":
        print("usage: python3 -m host.raw_avrcp_input verify-task <policy.json>")
        return 2
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    broker = raw["pagination"]["broker"]
    query = subprocess.run(["schtasks.exe", "/query", "/tn", broker["launch"]["task_name"], "/xml"],
                           stdin=subprocess.DEVNULL, capture_output=True)
    if query.returncode != 0:
        print("R017_TASK_NOT_INSTALLED")
        return 1
    raw_xml = query.stdout
    xml_text = raw_xml.decode("utf-16") if raw_xml[:2] in (b"\xff\xfe", b"\xfe\xff") else raw_xml.decode("utf-8", "replace")
    problems = task_problems(xml_text.split("?>", 1)[-1], broker, raw["target"]["exact_unit_id"])
    for problem in problems:
        print(f"R017_TASK_MISMATCH={problem}")
    if not problems:
        print("R017_TASK_MATCHES_POLICY")
    return 1 if problems else 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
