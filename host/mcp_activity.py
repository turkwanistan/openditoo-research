"""Bounded, read-only collector for the three MCP activity sources.

Reads existing audit logs. Never calls the MCP servers themselves, so polling
cannot appear as activity in the sources it observes (see `probe()` /
`test_collector_reads_do_not_appear_as_activity`).

Endpoints live in `.openditoo-local/activity-sources.json` (git-ignored); see
`examples/activity-sources.example.json`.
"""
from __future__ import annotations

import json
import os
import shlex
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = ROOT / ".openditoo-local"
CONFIG_FILE = LOCAL_DIR / "activity-sources.json"
STATE_FILE = LOCAL_DIR / "activity-state.json"

SOURCE_IDS = ("optiplex_mcp", "optiplex_lab", "wsl_mcp")
STATE_VERSION = 1

MAX_BYTES_PER_POLL = 256 * 1024
MAX_RECORDS_PER_POLL = 500
FIRST_TAIL_BYTES = 64 * 1024
DEFAULT_POLL_SECONDS = 2.0
STALE_AFTER_MISSED_POLLS = 3
# A source clock this far ahead of ours is skew, not a brand-new event.
FUTURE_SKEW_TOLERANCE_SECONDS = 120


def _remote(ssh_target: str | None, argv: list[str], timeout: float) -> list[str]:
    """ssh joins its command words with spaces and re-parses them in a remote shell,
    so the command must be quoted once here or `%s` and friends are eaten."""
    if not ssh_target:
        return argv
    return ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={max(1, int(timeout))}",
            ssh_target, shlex.join(argv)]


class SourceError(Exception):
    """Bounded, sanitized collection failure. The message is an error code."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    """Parse the three observed timestamp shapes into aware UTC."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp is missing a timezone")
    return parsed.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

class Event:
    """One qualifying observed record."""

    __slots__ = ("event_id", "at", "outcome", "kind")

    def __init__(self, event_id: str, at: datetime, outcome: str, kind: str) -> None:
        self.event_id = event_id
        self.at = at
        self.outcome = outcome  # success | failure | unknown
        self.kind = kind

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Event({self.event_id!r}, {iso(self.at)}, {self.outcome})"


def _jsonl_events(chunk: str, parse) -> tuple[list[Event], str, int]:
    """Parse whole JSON lines; return events, the incomplete trailing line, and parse failures."""
    events: list[Event] = []
    failures = 0
    lines = chunk.split("\n")
    remainder = lines.pop()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = parse(json.loads(line))
        except Exception:
            failures += 1  # a bad line must not stop the good ones after it
            continue
        if event is not None:
            events.append(event)
    return events, remainder, failures


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------

class FileTailAdapter:
    """Byte-offset tail of an append-only JSONL audit log, local or over ssh.

    Cursor: {"identity": <inode/size fingerprint>, "offset": int, "partial": str}.
    """

    kind = "logged_tool_call"

    def __init__(self, source_id: str, config: dict) -> None:
        self.source_id = source_id
        self.path = config["path"]
        self.ssh_target = config.get("ssh_target")
        self.timeout = float(config.get("timeout_seconds", 1.5))

    # -- transport ---------------------------------------------------------
    def _run(self, argv: list[str]) -> bytes:
        argv = _remote(self.ssh_target, argv, self.timeout)
        try:
            done = subprocess.run(argv, capture_output=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            raise SourceError("SOURCE_READ_TIMEOUT") from exc
        except OSError as exc:
            raise SourceError("SOURCE_TRANSPORT_UNAVAILABLE") from exc
        if done.returncode != 0:
            raise SourceError("SOURCE_READ_FAILED")
        return done.stdout

    def _identity(self) -> tuple[str, int]:
        raw = self._run(["stat", "-c", "%i %s", self.path]).decode("ascii", "replace").split()
        if len(raw) != 2:
            raise SourceError("SOURCE_STAT_UNREADABLE")
        return raw[0], int(raw[1])

    def _read_from(self, offset: int, limit: int) -> bytes:
        # `tail -c +N` is 1-based and available identically locally and over ssh.
        return self._run(["tail", "-c", f"+{offset + 1}", self.path])[:limit]

    def _read_tail(self, size: int) -> bytes:
        return self._run(["tail", "-c", str(size), self.path])

    # -- collection --------------------------------------------------------
    def poll(self, cursor: dict | None) -> tuple[list[Event], dict, bool, int]:
        if cursor is None:
            # First start: establish current activity from a bounded tail without
            # replaying it as new. Stat *after* the read so the stored offset can
            # never sit behind bytes already parsed, which would re-pulse them.
            chunk = self._read_tail(FIRST_TAIL_BYTES)
            identity, size = self._identity()
            text = chunk.decode("utf-8", "replace")
            complete = size <= FIRST_TAIL_BYTES
            if not complete:
                text = text.split("\n", 1)[-1]  # drop the partial first line
            events, _, failures = _jsonl_events(text + "\n", self.parse)
            return events, {"identity": identity, "offset": size, "partial": ""}, complete, failures

        identity, size = self._identity()
        offset = int(cursor.get("offset", 0))
        partial = str(cursor.get("partial", ""))
        complete = True
        if cursor.get("identity") != identity or size < offset:
            # Rotation or truncation: unread bytes are gone. Report the gap.
            offset, partial, complete = 0, "", False
        if size == offset:
            return [], {"identity": identity, "offset": offset, "partial": partial}, complete, 0
        raw = self._read_from(offset, MAX_BYTES_PER_POLL)
        if len(raw) >= MAX_BYTES_PER_POLL:
            complete = False  # catching up; more remains for the next poll
        events, remainder, failures = _jsonl_events(partial + raw.decode("utf-8", "replace"), self.parse)
        if len(events) > MAX_RECORDS_PER_POLL:
            events = events[-MAX_RECORDS_PER_POLL:]
            complete = False
        return events, {"identity": identity, "offset": offset + len(raw), "partial": remainder}, complete, failures

    def parse(self, record: dict) -> Event | None:  # pragma: no cover - overridden
        raise NotImplementedError


class WslMcpAdapter(FileTailAdapter):
    """WSL_MCP audit.jsonl: one record per completed tool call, with a stable request_id."""

    def parse(self, record: dict) -> Event | None:
        at = parse_timestamp(record["ts"])
        result = str(record.get("result", ""))
        if result in {"started", "requested", "scheduled"}:
            outcome = "unknown"  # dispatch, not completion
        elif result in {"ok", "exit_0"}:
            outcome = "success"
        else:
            outcome = "failure"
        return Event(str(record["request_id"]), at, outcome, self.kind)


class OptiplexMcpAdapter(FileTailAdapter):
    """OptiPlex MCP audit.log: completed tool calls with `ok`, but no stable record id.

    Identity is a timestamp+tool fingerprint; two identical calls in the same
    microsecond would collide, so counts are not claimed to be exact.
    """

    def parse(self, record: dict) -> Event | None:
        at = parse_timestamp(record["ts"])
        tool = str(record.get("tool", "?"))
        outcome = "success" if record.get("ok") is True else ("failure" if record.get("ok") is False else "unknown")
        return Event(f"{record['ts']}|{tool}", at, outcome, self.kind)


class LabTunnelAdapter:
    """OptiPlex Lab: the lab's own tool audit lives inside the isolated VM and is
    not reachable from here. What is reachable is its tunnel dispatcher journal,
    which records each MCP command forwarded to the lab server.

    That is transport-level dispatch, not tool completion, and carries no tool
    name — the display must not claim more than that.
    """

    kind = "transport_forwarded_command"
    FORWARDED = "dispatcher forwarded command to MCP server"
    UPSTREAM_ERROR = "dispatcher received MCP upstream error; posted error response to control plane"

    def __init__(self, source_id: str, config: dict) -> None:
        self.source_id = source_id
        self.unit = config["journal_unit"]
        self.ssh_target = config.get("ssh_target")
        self.timeout = float(config.get("timeout_seconds", 2.0))

    def poll(self, cursor: dict | None) -> tuple[list[Event], dict, bool, int]:
        # `-o json` already carries __CURSOR per entry; --show-cursor is incompatible with it.
        argv = ["journalctl", "-u", self.unit, "--no-pager", "-o", "json",
                "-n", str(MAX_RECORDS_PER_POLL)]
        # journald owns rotation; its cursor is the resume point. Until the unit has
        # logged anything there is no cursor, so fall back to a moving --since window
        # -- a fixed window would re-count the same record on every poll.
        since = (cursor or {}).get("since")
        if cursor and cursor.get("journal_cursor"):
            argv += ["--after-cursor", cursor["journal_cursor"]]
        else:
            argv += ["--since", since or utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")]
        argv = _remote(self.ssh_target, argv, self.timeout)
        try:
            done = subprocess.run(argv, capture_output=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            raise SourceError("SOURCE_READ_TIMEOUT") from exc
        except OSError as exc:
            raise SourceError("SOURCE_TRANSPORT_UNAVAILABLE") from exc
        if done.returncode != 0:
            raise SourceError("SOURCE_READ_FAILED")
        return self.parse_journal(done.stdout.decode("utf-8", "replace"), cursor)

    def parse_journal(self, text: str, cursor: dict | None) -> tuple[list[Event], dict, bool, int]:
        events: list[Event] = []
        failures = 0
        journal_cursor = (cursor or {}).get("journal_cursor")
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                journal_cursor = entry.get("__CURSOR", journal_cursor)
                payload = json.loads(entry["MESSAGE"])
                if payload.get("msg") not in {self.FORWARDED, self.UPSTREAM_ERROR}:
                    continue
                at = parse_timestamp(payload["time"])
                outcome = "unknown" if payload["msg"] == self.FORWARDED else "failure"
                events.append(Event(str(payload["request_id"]), at, outcome, self.kind))
            except Exception:
                failures += 1
                continue
        # A first read seeds from a bounded window, so history before it is unknown.
        resume = {"journal_cursor": journal_cursor,
                  "since": utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")}
        anchored = bool(cursor) and (cursor.get("journal_cursor") is not None or cursor.get("since") is not None)
        return events, resume, anchored, failures


ADAPTERS = {
    "optiplex_mcp": OptiplexMcpAdapter,
    "optiplex_lab": LabTunnelAdapter,
    "wsl_mcp": WslMcpAdapter,
}


# --------------------------------------------------------------------------
# Normalized state
# --------------------------------------------------------------------------

def blank_source_state() -> dict:
    return {
        "last_activity_at": None,
        "last_observed_at": None,
        "source_health": "unknown",
        "last_outcome": None,
        "cursor": None,
        "new_activity_sequence": 0,
        "history_complete": False,
        "error_code": None,
    }


def blank_state() -> dict:
    return {"version": STATE_VERSION, "sources": {sid: blank_source_state() for sid in SOURCE_IDS}}


def load_state(path: Path = STATE_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return blank_state()
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
        return blank_state()
    state = blank_state()
    for sid in SOURCE_IDS:
        stored = data.get("sources", {}).get(sid)
        if isinstance(stored, dict):
            state["sources"][sid].update({k: v for k, v in stored.items() if k in state["sources"][sid]})
    return state


def save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1), encoding="utf-8")
    os.replace(tmp, path)  # atomic


def load_config(path: Path = CONFIG_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SourceError("ACTIVITY_SOURCES_NOT_CONFIGURED") from exc
    except json.JSONDecodeError as exc:
        raise SourceError("ACTIVITY_SOURCES_INVALID") from exc
    missing = [sid for sid in SOURCE_IDS if sid not in data.get("sources", {})]
    if missing:
        raise SourceError("ACTIVITY_SOURCES_INCOMPLETE")
    return data


def _apply(source_state: dict, events: list[Event], cursor: dict, complete: bool,
           failures: int, now: datetime) -> None:
    source_state["cursor"] = cursor
    source_state["last_observed_at"] = iso(now)
    source_state["error_code"] = "SOURCE_PARSE_FAILURES" if failures else None
    source_state["history_complete"] = bool(complete)
    skew_limit = now.timestamp() + FUTURE_SKEW_TOLERANCE_SECONDS
    usable = [event for event in events if event.at.timestamp() <= skew_limit]
    if len(usable) != len(events):
        source_state["error_code"] = "SOURCE_CLOCK_SKEW"
    if usable:
        latest = max(usable, key=lambda event: event.at)
        source_state["last_activity_at"] = iso(latest.at)
        source_state["last_outcome"] = latest.outcome
    source_state["source_health"] = "healthy"


def collect_once(config: dict, state: dict, now: datetime | None = None,
                 poll_seconds: float = DEFAULT_POLL_SECONDS) -> dict:
    """One isolated poll of each source. Returns {source_id: new_event_count}."""
    now = now or utc_now()
    seeding = {sid: state["sources"][sid]["cursor"] is None for sid in SOURCE_IDS}

    def run(source_id: str):
        settings = config["sources"][source_id]
        adapter = ADAPTERS[source_id](source_id, settings)
        return adapter.poll(state["sources"][source_id]["cursor"])

    with ThreadPoolExecutor(max_workers=len(SOURCE_IDS)) as pool:
        futures = {sid: pool.submit(run, sid) for sid in SOURCE_IDS}
        results = {}
        for sid, future in futures.items():
            try:
                results[sid] = future.result()
            except SourceError as exc:
                results[sid] = exc
            except Exception as exc:  # never leak an argument or path into state
                results[sid] = SourceError(f"SOURCE_ADAPTER_ERROR:{type(exc).__name__}")

    new_counts: dict[str, int] = {}
    for sid in SOURCE_IDS:
        source_state = state["sources"][sid]
        result = results[sid]
        if isinstance(result, SourceError):
            source_state["source_health"] = "unavailable"
            source_state["error_code"] = str(result)
            new_counts[sid] = 0
            continue
        events, cursor, complete, failures = result
        _apply(source_state, events, cursor, complete, failures, now)
        # Seeding establishes "when did this last happen", never a pulse.
        new_counts[sid] = 0 if seeding[sid] else len(events)
        source_state["new_activity_sequence"] += new_counts[sid]

    age_out_stale(state, now, poll_seconds)
    return new_counts


def age_out_stale(state: dict, now: datetime, poll_seconds: float = DEFAULT_POLL_SECONDS) -> None:
    """A healthy-looking source whose last successful read is old is stale, not idle."""
    limit = poll_seconds * STALE_AFTER_MISSED_POLLS
    for sid in SOURCE_IDS:
        source_state = state["sources"][sid]
        observed = source_state.get("last_observed_at")
        if source_state["source_health"] == "unavailable":
            continue
        if observed is None:
            source_state["source_health"] = "unknown"
        elif (now - parse_timestamp(observed)).total_seconds() > limit:
            source_state["source_health"] = "stale"


def probe(config: dict) -> dict:
    """Diagnostics: does each source read work, and what does it cost?"""
    report = {}
    for sid in SOURCE_IDS:
        adapter = ADAPTERS[sid](sid, config["sources"][sid])
        started = utc_now()
        try:
            events, _, complete, failures = adapter.poll(None)
            report[sid] = {
                "reachable": True,
                "kind": adapter.kind,
                "records_in_seed_window": len(events),
                "history_complete": complete,
                "parse_failures": failures,
                "latency_ms": int((utc_now() - started).total_seconds() * 1000),
                "reads_via_mcp_call": False,
            }
        except SourceError as exc:
            report[sid] = {"reachable": False, "kind": adapter.kind, "error_code": str(exc),
                           "latency_ms": int((utc_now() - started).total_seconds() * 1000),
                           "reads_via_mcp_call": False}
    return report
