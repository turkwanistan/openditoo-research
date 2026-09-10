#!/usr/bin/env python3
"""HF-3 operator assist. No Ditoo transport, no Host call, no claim: it only reads the HF-3 probe
NDJSON and the Host ledger, shows topmost Windows popups, and makes one genuine read-only WSL_MCP
call. Start it before scripts/run_interactive_hf3.sh.

- GO popup when the first HF-3 child session opens (HF3-001 failed for lack of a start cue).
- FINAL popup when the operator lands on Dashboard and another full cycle cannot fit (target
  cycles done, child-attempt headroom < 5, or the soft end of the lifetime); then one read-only
  WSL_MCP run_command (-> genuine wsl_mcp audit event -> lightning), then SIGINT to the runner so
  it ends as operator_stop and the coordinator restores Runtime 006.
Popups, not sounds: the Ditoo is itself a Windows audio endpoint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import interactive_acceptance as hf3  # noqa: E402
from scripts.interactive_hf3 import main_worktree  # noqa: E402

PREFIX = hf3.EXPERIMENT_ID + "-S"
EVENTS = ROOT / ".openditoo-local/hf3/button-events.ndjson"
MCP = "http://127.0.0.1:8768/mcp"


def log(**kw):
    kw["at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print(json.dumps(kw), flush=True)


def popup(text: str) -> None:
    # 64 = information icon, 4096 = system-modal (topmost); auto-dismiss after 6 s.
    subprocess.Popen(["powershell.exe", "-NoProfile", "-Command",
                      f"(New-Object -ComObject WScript.Shell).Popup('{text}', 6, 'OpenDitoo HF-3', 4160) | Out-Null"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mcp_event() -> str:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "run_command", "arguments": {"project": "openditoo-research",
                                             "command": "git rev-parse --short HEAD"}}}
    req = urllib.request.Request(MCP, json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read(400).decode(errors="replace")


def runner_pid() -> int | None:
    out = subprocess.run(["pgrep", "-f", "scripts/interactive_hf3.py run"],
                         capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else None


def rows(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def main() -> int:
    m = hf3.load_manifest(ROOT / "experiments/DAY1-INTERACTIVE-HF3-002.json", verify_hashes=False,
                          verify_button_probe=False, require_authority=False)
    ledger = main_worktree() / ".openditoo-local/session-ledger.jsonl"
    soft_end_s = m.lifetime_seconds - 22
    while runner_pid() is None:
        time.sleep(0.1)
    log(event="runner_seen", pid=runner_pid())
    go = None
    while True:
        if runner_pid() is None:
            log(event="runner_exited_before_final")
            return 0
        opens = sum(1 for r in rows(ledger)
                    if r.get("kind") == "open" and str(r.get("experimentId", "")).startswith(PREFIX))
        if go is None and opens:
            go = time.monotonic()
            popup("GO - press RIGHT on the Ditoo now")
            log(event="go_popup", hf3_opens=opens)
        if go is not None:
            nav = [r for r in rows(EVENTS) if r.get("source") == "smtc" and r.get("raw_button") in ("Next", "Previous")]
            lefts = sum(1 for r in nav if r["raw_button"] == "Previous")
            elapsed = time.monotonic() - go
            if nav and len(nav) % 2 == 0 and (lefts >= m.target_profile_cycles
                                              or m.max_child_sessions - opens < 5 or elapsed >= soft_end_s):
                popup("FINAL - hands off, watch the Dashboard for lightning")
                log(event="final_dashboard", lefts=lefts, hf3_opens=opens, elapsed_s=round(elapsed, 1))
                time.sleep(2.5)  # dashboard child opens and draws its base frame
                log(event="mcp_event", response=mcp_event()[:200])
                time.sleep(8.0)  # collector poll (2 s) + 10-stage ACK-gated pulse (~2 s) + margin
                pid = runner_pid()
                if pid:
                    os.kill(pid, signal.SIGINT)
                    log(event="sigint_sent", pid=pid)
                return 0
        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
