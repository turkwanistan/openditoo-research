#!/usr/bin/env python3
"""HF-3 review/dry-run/grant/live entrypoint. Live mode assumes the shell coordinator has
already suspended the dashboard runtime (Runtime 007) and verified the Host idle; it independently rechecks Host identity
and consumes the outer claim before the first child session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.openditoo import _HostSessionTransport
from host import activity_session, mcp_activity
from host.activity_lightning_renderer import LightningActivityRenderer
from host.dashboard_page import DashboardPage
from host import interactive_acceptance as hf3
from host.interactive_pages import BufferedButtonEvents, PageCarousel, RATE_ACTIVITY
from host.pagination import Broker, ButtonEvents
from host.slots_page import SlotsPage

MANIFEST = ROOT / "experiments/DAY1-INTERACTIVE-HF3-007.json"
LOCAL = ROOT / ".openditoo-local/hf3"


def main_worktree() -> Path:
    raw = subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=ROOT, text=True)
    current = None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            current = Path(line.split(" ", 1)[1])
        elif line == "branch refs/heads/main" and current is not None:
            return current
    raise RuntimeError("MAIN_WORKTREE_NOT_FOUND")


def read_main_token(main_root: Path) -> str:
    path = main_root / ".openditoo-local/host.token"
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise RuntimeError("HOST_TOKEN_MODE_INVALID")
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise RuntimeError("HOST_TOKEN_INVALID")
    return token


def host_idle_status(token: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:8796/v1/status",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=3.0) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("HOST_STATUS_TOO_LARGE")
    body = json.loads(raw)
    required = {"apiVersion": 1, "service": "OpenDitoo Day1 Host", "hostRuntime": ".NET",
                "bind": "127.0.0.1", "port": 8796, "masterTransmitEnabled": True,
                "target": activity_session.EXACT_UNIT_ID, "targetBound": True, "rawSendEnabled": False}
    if any(body.get(k) != v for k, v in required.items()):
        raise RuntimeError("HOST_IDENTITY_MISMATCH")
    if body.get("activitySession", {}).get("active") is True:
        raise RuntimeError("HOST_CONTROLLER_NOT_IDLE")
    if body.get("diagnostics", {}).get("operationInProgress") is True:
        raise RuntimeError("HOST_OPERATION_IN_PROGRESS")
    return body


class FakeClock:
    def __init__(self): self.ms = 0
    def __call__(self): return self.ms
    def sleep(self, ms): self.ms += max(1, int(ms))


class SequenceEvents:
    def __init__(self, batches): self.batches, self.index = list(batches), 0
    def poll(self):
        if self.index >= len(self.batches): return []
        value = self.batches[self.index]; self.index += 1; return list(value)
    @property
    def done(self): return self.index >= len(self.batches)


class DryDashboard:
    name = "dashboard"; rate_mode = RATE_ACTIVITY
    def __init__(self): self.frames = 0; self.last_from_pulse = False
    def on_enter(self): pass
    def on_exit(self): pass
    def render(self, _now): return bytes([0, 85, 0]) * 256
    def handle_input(self, _event): return None
    def frame_sent(self): self.frames += 1
    def telemetry(self): return {"frames": self.frames}


class FakeHost:
    """Enforces the Host's profile floor at the Host's own frame start (HTTP 429 is terminal), with
    request-arrival jitter alternating 12/0 ms (HF3-005: 50 ms client gaps still broke the 40 ms Host
    floor), ACKs simple streaming frames in 20 ms (HF3-004 saw 21 ms), reports hostFrameElapsedMs, and
    delivers every 0xBD as a mid-send 409 SESSION_CANVAS_INVALIDATED that the Host's record confirms."""
    def __init__(self, clock, invalidations=None):
        self.clock = clock; self.profile = RATE_ACTIVITY
        self.invalidations = [] if invalidations is None else invalidations
        self.last_start = None; self.yielded = False; self.sends = 0
    def open(self, child):
        self.profile = (child.raw.get("stream") or {}).get("session_profile", RATE_ACTIVITY)
        return {"sessionId": child.experiment_id, "sessionProfile": self.profile}
    def send_frame(self, _rgb, expected):
        import io, urllib.error
        floor = 40 if self.profile != RATE_ACTIVITY else 150
        self.sends += 1
        self.clock.sleep(12 if self.sends % 2 else 0)  # request transit jitter before the Host stamps
        if self.last_start is not None and self.clock() - self.last_start < floor:
            raise urllib.error.HTTPError("fake", 429, "pacing", {}, io.BytesIO(b'{"errorCode":"SESSION_PACING_VIOLATION"}'))
        self.last_start = self.clock()
        if self.invalidations:  # BTN-7: Play-direction lever pull -> RFCOMM 0xBD, here mid-send
            self.invalidations.pop(); self.yielded = True; self.yields = getattr(self, "yields", 0) + 1
            # alternate the two live races: seen inside the send, or by the Host watchdog just before it
            body = b'{"errorCode":"SESSION_NOT_ACTIVE"}' if self.yields % 2 == 0 else b'{"errorCode":"SESSION_CANVAS_INVALIDATED"}'
            raise urllib.error.HTTPError("fake", 409, "yield", {}, io.BytesIO(body))
        ack_ms = 20 if self.profile != RATE_ACTIVITY else 40
        self.clock.sleep(ack_ms)
        return {"ok": True, "imagePacketSha256": expected, "ackPayloadHex": "0x00",
                "hostFrameElapsedMs": ack_ms}
    def poll_reports(self):
        if self.yielded:
            return [{"kind": "session_ended", "reason": "canvas_invalidated",
                     "outcome": "stopped_yielded_to_stock"}]
        return []
    def close(self, _reason): return {"closed": True}


class PacedEvents:
    """Release scheduled inputs by clock time (human pace), flagging a 0xBD per Play pull."""
    def __init__(self, schedule, clock, invalidations):
        self.schedule, self.clock, self.invalidations, self.index = schedule, clock, invalidations, 0
    def poll(self):
        out = []
        while self.index < len(self.schedule) and self.schedule[self.index][0] <= self.clock():
            event = self.schedule[self.index][1]; self.index += 1; out.append(event)
            if event["raw_button"] == "Play": self.invalidations.append(1)
        return out


def paced_schedule(cycles=10, start_ms=1000, pull_ms=1200, dwell_ms=1700):
    """Right, 4 short pulls ~1.2 s apart, Left, ~1.7 s on Dashboard: ~8 s/cycle (HF3-001 lesson)."""
    schedule, seq, t = [], 0, start_ms
    for _ in range(cycles):
        seq += 1; schedule.append((t, _event(seq, "nav_right", "Next")))
        for i, raw in enumerate(("Pause", "Play", "Pause", "Play"), 1):
            seq += 1; schedule.append((t + 300 + i * pull_ms, _event(seq, "lever_candidate", raw)))
        t += 300 + 5 * pull_ms
        seq += 1; schedule.append((t, _event(seq, "nav_left", "Previous")))
        t += dwell_ms
    return schedule, t


def _event(seq, kind, raw):
    return {"epoch": "hf3-dry", "seq": seq, "type": kind, "raw_button": raw, "at_utc": None}


def dry_batches(cycles=10):
    batches, seq = [], 0
    for _ in range(cycles):
        seq += 1; batches.append([_event(seq, "nav_right", "Next")])
        batches.append([])
        for raw in ("Pause", "Play", "Pause", "Play"):
            seq += 1; batches.append([_event(seq, "lever_candidate", raw)])
            batches.append([])
        seq += 1; batches.append([_event(seq, "nav_left", "Previous")])
    batches.extend([[], []])
    return batches


def check(full_probe: bool) -> dict:
    m = hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=full_probe,
                          require_authority=False)
    authority = hf3.authority_blockers(MANIFEST)
    environment = [] if full_probe else ["BUTTON_PROBE_NOT_REVERIFIED_IN_THIS_ENVIRONMENT"]
    try:
        claim = activity_session.SessionClaim(
            hf3.EXPERIMENT_ID, main_worktree() / ".openditoo-local/session-claims").read()
    except Exception:
        claim = None
    if claim is not None:
        environment.append("HF3_OUTER_CLAIM_ALREADY_CONSUMED")
    return {"ok": True, "experiment_id": m.experiment_id, "manifest_sha256": hf3.sha256_file(MANIFEST),
            "grant_ready": not environment, "execution_ready": not authority and not environment,
            "authority_blockers": authority, "environment_blockers": environment,
            "existing_outer_claim": claim, "device_io": False}


def dry_run(paced: bool = False) -> dict:
    m = hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=False,
                          require_authority=False)
    clock = FakeClock(); invalidations: list = []
    if paced:
        schedule, last_left_ms = paced_schedule(m.target_profile_cycles)
        source = PacedEvents(schedule, clock, invalidations)
        stop = lambda: clock() >= last_left_ms + 12000  # final Dashboard + lightning window
    else:
        source = SequenceEvents(dry_batches(m.target_profile_cycles))
        stop = lambda: source.done and mailbox.pending_count == 0
    mailbox = BufferedButtonEvents(source)
    result = hf3.run_acceptance(
        m, [PageCarousel([DryDashboard(), SlotsPage(seed=20260910)])], mailbox,
        lambda: FakeHost(clock, invalidations), clock, clock.sleep, stop_requested=stop)
    if result["outcome"] != "stopped_clean" or not result["cycle_target_met"]:
        raise RuntimeError("HF3_DRY_RUN_FAILED")
    if paced and (result["orchestrator"]["session_reclaims"] != 2 * m.target_profile_cycles
                  or result["terminal_reason"] != "operator_stop"):
        raise RuntimeError("HF3_PACED_DRY_RUN_ENVELOPE_TOO_SMALL")
    return {"ok": True, "device_io": False, "claim_created": False,
            ("HF3_PACED_DRY_RUN" if paced else "HF3_DRY_RUN"): "PASS", **result}


def grant(grant_text: str) -> dict:
    # Granting is deliberately impossible in WSL_MCP if installed ButtonProbe bytes are not visible.
    hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=True, require_authority=False)
    main_root = main_worktree()
    claim = activity_session.SessionClaim(hf3.EXPERIMENT_ID, main_root / ".openditoo-local/session-claims")
    if claim.path.exists():
        raise RuntimeError("HF3_OUTER_CLAIM_ALREADY_EXISTS")
    if grant_text != hf3.REQUIRED_GRANT_TEXT:
        raise RuntimeError("HF3_GRANT_TEXT_MISMATCH")
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if doc["authority"].get("transmission_authorized") or doc["authority"].get("authorization_consumed"):
        raise RuntimeError("HF3_MANIFEST_ALREADY_GRANTED_OR_CONSUMED")
    now = datetime.now(timezone.utc)
    doc["authority"].update({
        "transmission_authorized": True, "authorization_consumed": False,
        "granted_by": "operator, in-session", "grant_text": grant_text,
        "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
    })
    doc["status"] = "granted_unconsumed"
    doc["readiness"].update({"grant_ready": True, "blockers": []})
    MANIFEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=True, require_authority=True)
    return {"ok": True, "granted": hf3.EXPERIMENT_ID, "expires_at": doc["authority"]["expires_at"],
            "device_io": False, "claim_created": False}


def live_run() -> dict:
    m = hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=True, require_authority=True)
    main_root = main_worktree()
    token = read_main_token(main_root)
    host_idle_status(token)  # final no-controller check before the outer claim

    local_main = main_root / ".openditoo-local"
    config = mcp_activity.load_config(local_main / "activity-sources.json")
    state_path = local_main / "activity-state.json"
    state = mcp_activity.load_state(state_path)

    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    events_file = LOCAL / "button-events.ndjson"
    events_win = subprocess.check_output(["wslpath", "-w", str(events_file.resolve())], text=True).strip()
    broker = Broker(hf3.BUTTON_PROBE_EXE, events_win, events_file)
    broker.ensure()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and broker.alive:
        try:
            rows = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            rows = []
        started = next((row for row in rows if row.get("type") == "probe_started"), None)
        if started and (started.get("smtc") or {}).get("acquired") is True:
            break
        time.sleep(0.05)
    else:
        broker.stop()
        raise RuntimeError("HF3_BUTTON_PROBE_NOT_READY")

    source = ButtonEvents(events_file)
    mailbox = BufferedButtonEvents(source)
    dashboard = DashboardPage(config, state,
                              renderer=LightningActivityRenderer(config, state, state_path=state_path))
    slots = SlotsPage()
    carousel = PageCarousel([dashboard, slots], background_thread=True)
    stop = {"value": False}
    def requested(): return stop["value"]
    def stop_signal(_signum, _frame): stop["value"] = True
    old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in old_handlers: signal.signal(sig, stop_signal)
    started_ms = time.monotonic()
    claim = None
    try:
        # No transport has opened yet. This is the irreversible outer authority boundary.
        claim = hf3.claim_outer(m, main_root / ".openditoo-local/session-claims")
        result = hf3.run_acceptance(
            m, [carousel], mailbox, lambda: _HostSessionTransport(token),
            lambda: int((time.monotonic() - started_ms) * 1000),
            lambda ms: time.sleep(ms / 1000.0), stop_requested=requested)
        hf3.finish_outer_claim(claim, result)
        # The O_EXCL claim is the replay authority. Mirror consumption into the tracked
        # manifest when this process reaches a terminal result so future humans see it too.
        doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
        doc["authority"].update({
            "transmission_authorized": False, "authorization_consumed": True,
            "consumed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        doc["status"] = ("completed_transport_clean" if result["outcome"] != "unknown"
                         else "completed_unknown_authority_consumed")
        MANIFEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        out = LOCAL / f"{hf3.EXPERIMENT_ID}-result.json"
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return {"ok": result["outcome"] != "unknown", "device_io": True,
                "claim_file": str(claim.path), "result_file": str(out), **result}
    finally:
        carousel._join_worker()  # never exit mid-collection (it persists activity state)
        broker.stop()
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check"); p.add_argument("--sandbox-skip-probe", action="store_true")
    p = sub.add_parser("dry-run"); p.add_argument("--paced", action="store_true")
    p = sub.add_parser("grant"); p.add_argument("grant_text")
    sub.add_parser("run")
    args = parser.parse_args()
    try:
        if args.command == "check": result = check(not args.sandbox_skip_probe)
        elif args.command == "dry-run": result = dry_run(args.paced)
        elif args.command == "grant": result = grant(args.grant_text)
        else: result = live_run()
    except (hf3.AcceptanceError, activity_session.SessionError, RuntimeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        print(json.dumps({"ok": False, "error_code": code, "detail": str(exc),
                          "device_io": args.command == "run"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
