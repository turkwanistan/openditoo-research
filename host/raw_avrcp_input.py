"""Receive-only raw AVRCP input broker for media-resilient OpenDitoo controls.

The Windows sidecar owns three receive-only helper processes:
- OpenDitoo.ButtonProbe in fixed ``playing`` mode, solely to keep Windows media-session ownership;
- Microsoft BTVS on a dedicated local TCP port;
- tshark, display-filtered to AVRCP pass-through PRESS commands whose ACL source is the exact Ditoo.

Only normalized input NDJSON crosses back into WSL. No Bluetooth write, Host call, RFCOMM controller,
media injection, or device target selection exists here. The target is supplied by the hash-bound product
policy and is used only as a capture attribution filter.
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
    """Supervise one Windows raw-AVRCP sidecar, rate-limited and fail-closed."""

    def __init__(self, exe: Path, *, target: str, events_windows_path: str, events_file: Path,
                 sink_exe: Path, sink_log_windows_path: str, sink_log_file: Path,
                 btvs_exe: Path, tshark_exe: Path, port: int = 24353,
                 popen=subprocess.Popen, monotonic: Callable[[], float] = time.monotonic) -> None:
        self.args = [
            str(exe), "--seconds", "0", "--target", target,
            "--events", events_windows_path,
            "--sink-log", sink_log_windows_path,
            "--sink-exe", str(sink_exe),
            "--btvs", str(btvs_exe), "--tshark", str(tshark_exe),
            "--port", str(port),
        ]
        self.events_file, self.sink_log_file = Path(events_file), Path(sink_log_file)
        self.popen, self.monotonic = popen, monotonic
        self.process = None
        self.starts = 0
        self.last_start = float("-inf")
        self.last_exit_code: int | None = None

    def ensure(self) -> None:
        if self.alive:
            return
        if self.process is not None:
            self.last_exit_code = self.process.poll()
        if self.monotonic() - self.last_start < BROKER_RESTART_SECONDS:
            return
        self.last_start = self.monotonic()
        for path in (self.events_file, self.sink_log_file):
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(b"")
            path.chmod(0o600)
        self.process = self.popen(self.args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        self.starts += 1

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if not self.alive:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.last_exit_code = self.process.poll()

    def telemetry(self) -> dict:
        return {
            "alive": self.alive,
            "starts": self.starts,
            "last_exit_code": self.last_exit_code,
            "mode": "raw_avrcp_plus_playing_smtc_sink",
            "updated_at": _utc(),
        }
