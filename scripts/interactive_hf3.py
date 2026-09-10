#!/usr/bin/env python3
"""HF-3 review/dry-run/grant/live entrypoint. Live mode assumes the shell coordinator has
already suspended Runtime 006 and verified the Host idle; it independently rechecks Host identity
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
from host.interactive_pages import BufferedButtonEvents, RATE_ACTIVITY
from host.pagination import Broker, ButtonEvents
from host.slots_page import SlotsPage

MANIFEST = ROOT / "experiments/DAY1-INTERACTIVE-HF3-001.json"
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
    def __init__(self, clock): self.clock = clock; self.profile = RATE_ACTIVITY
    def open(self, child):
        self.profile = (child.raw.get("stream") or {}).get("session_profile", RATE_ACTIVITY)
        return {"sessionId": child.experiment_id, "sessionProfile": self.profile}
    def send_frame(self, _rgb, expected):
        self.clock.sleep(55 if self.profile != RATE_ACTIVITY else 40)
        return {"ok": True, "imagePacketSha256": expected, "ackPayloadHex": "0x00"}
    def poll_reports(self): return []
    def close(self, _reason): return {"closed": True}


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


def dry_run() -> dict:
    m = hf3.load_manifest(MANIFEST, verify_hashes=True, verify_button_probe=False,
                          require_authority=False)
    clock = FakeClock(); source = SequenceEvents(dry_batches(m.target_profile_cycles))
    mailbox = BufferedButtonEvents(source)
    result = hf3.run_acceptance(
        m, [DryDashboard(), SlotsPage(seed=20260910)], mailbox,
        lambda: FakeHost(clock), clock, clock.sleep,
        stop_requested=lambda: source.done and mailbox.pending_count == 0)
    if result["outcome"] != "stopped_clean" or not result["cycle_target_met"]:
        raise RuntimeError("HF3_DRY_RUN_FAILED")
    return {"ok": True, "device_io": False, "claim_created": False,
            "HF3_DRY_RUN": "PASS", **result}


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
            m, [dashboard, slots], mailbox, lambda: _HostSessionTransport(token),
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
        broker.stop()
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check"); p.add_argument("--sandbox-skip-probe", action="store_true")
    sub.add_parser("dry-run")
    p = sub.add_parser("grant"); p.add_argument("grant_text")
    sub.add_parser("run")
    args = parser.parse_args()
    try:
        if args.command == "check": result = check(not args.sandbox_skip_probe)
        elif args.command == "dry-run": result = dry_run()
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
