#!/usr/bin/env python3
"""Read-only historical W7 closure check; current W8 source drift is expected."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import activity_session, frame_stream

W7 = ROOT / "experiments/DAY1-WEBCAM-N980P-002.json"


def main() -> int:
    try:
        doc = json.loads(W7.read_text(encoding="utf-8"))
        if doc.get("experiment_id") != "OPENDITOO-WEBCAM-N980P-002":
            raise ValueError("W7_EXPERIMENT_ID_DRIFT")
        if doc.get("status") != "completed_pass_authority_consumed":
            raise ValueError("W7_NOT_COMPLETED")
        session, stream, budgets = doc["session"], doc["stream"], doc["budgets"]
        if (session.get("lifetime_seconds"), session.get("min_frame_interval_ms"),
                stream.get("session_profile"), stream.get("playback_interval_ms"),
                budgets.get("max_frames"), budgets.get("max_application_packets"), budgets.get("max_tx_bytes")) != (
                10, 40, "streaming_ack_clock", 90, 112, 336, 118048):
            raise ValueError("W7_HISTORICAL_ENVELOPE_DRIFT")
        authority = doc["authority"]
        if (authority.get("transmission_authorized") is not True
                or authority.get("authorization_consumed") is not True
                or authority.get("grant_text") != "Grant OPENDITOO-WEBCAM-N980P-002"):
            raise ValueError("W7_AUTHORITY_HISTORY_DRIFT")
        attempt = doc.get("w7_attempt", {})
        if (attempt.get("outcome") != "stopped_clean" or attempt.get("terminal_reason") != "lifetime_expired"
                or (attempt.get("frames"), attempt.get("packets"), attempt.get("tx_bytes")) != (108, 324, 110532)
                or attempt.get("owner_visible_acceptance") != "pass"):
            raise ValueError("W7_ACCEPTANCE_HISTORY_DRIFT")
        for path_key, sha_key in (("result_file", "result_sha256"), ("raw_file", "raw_sha256"),
                                  ("acceptance_file", "acceptance_sha256")):
            evidence = ROOT / attempt[path_key]
            if not evidence.is_file() or activity_session.sha256_file(evidence) != attempt[sha_key]:
                raise ValueError("W7_EVIDENCE_DRIFT:" + path_key)
        claim = activity_session.SessionClaim(doc["experiment_id"]).read()
        if not isinstance(claim, dict) or claim.get("state") != "finished" or claim.get("outcome") != "stopped_clean":
            raise ValueError("W7_CLAIM_HISTORY_MISSING")
        blockers = frame_stream.authority_blockers(W7)
        if "AUTHORITY_ALREADY_CONSUMED" not in blockers:
            raise ValueError("W7_REPLAY_NOT_BLOCKED")
        print(json.dumps({
            "ok": True, "manifest_valid": True, "historical": True, "device_io": True,
            "claim_created": True, "execution_ready": False, "grant_ready": False,
            "experiment_id": doc["experiment_id"], "blockers": blockers,
            "frames": attempt["frames"], "packets": attempt["packets"], "tx_bytes": attempt["tx_bytes"],
            "owner_visible_acceptance": attempt["owner_visible_acceptance"],
            "manifest_sha256": activity_session.sha256_file(W7),
        }, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "device_io": False, "execution_ready": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
