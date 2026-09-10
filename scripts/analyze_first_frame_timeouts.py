#!/usr/bin/env python3
"""Read-only: tally first-frame IMAGE_RX_RECV_TIMEOUT by session profile from the Host ledger.

No Host/device I/O. Default ledger is the main checkout's .openditoo-local/session-ledger.jsonl.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.interactive_hf3 import main_worktree  # noqa: E402


def analyze(rows: list[dict]) -> dict:
    opens, previous, sessions = {}, None, []
    for row in rows:
        kind, sid = row.get("kind"), row.get("sessionId")
        if kind == "open":
            opens[sid] = (row, previous)
        elif kind == "terminal":
            if sid in opens:
                opened, prev = opens.pop(sid)
                detail = row["detail"]
                gap = None if prev is None else round((
                    datetime.fromisoformat(opened["atUtc"]) - datetime.fromisoformat(prev["atUtc"])
                ).total_seconds(), 3)
                sessions.append({
                    "experiment_id": opened["experimentId"], "opened_utc": opened["atUtc"],
                    "profile": opened["detail"].get("sessionProfile", "activity"),
                    "frames_sent": detail.get("framesSent"),
                    "first_frame_timeout": detail.get("framesSent") == 0
                    and "IMAGE_RX_RECV_TIMEOUT" in (detail.get("detail") or ""),
                    "gap_after_previous_terminal_s": gap,
                    "previous_frames": None if prev is None else prev["detail"].get("framesSent"),
                })
            previous = row
    tally = Counter((s["profile"], s["first_frame_timeout"]) for s in sessions)
    return {"by_profile": {f"{p}:{'first_frame_timeout' if t else 'no_timeout'}": n
                           for (p, t), n in sorted(tally.items())},
            "streaming_sessions": [s for s in sessions if s["profile"] == "streaming_ack_clock"]}


if __name__ == "__main__":
    ledger = Path(sys.argv[1]) if len(sys.argv) > 1 else main_worktree() / ".openditoo-local/session-ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    print(json.dumps(analyze(rows), indent=2))
