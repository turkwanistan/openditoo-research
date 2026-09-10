#!/usr/bin/env python3
"""Read-only W8 review. Never opens a camera, Host session, claim, or device link."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import activity_session, frame_stream

ACTIVE = ROOT / "experiments/DAY1-WEBCAM-N980P-003.json"
W7 = ROOT / "experiments/DAY1-WEBCAM-N980P-002.json"


def main() -> int:
    try:
        manifest, _, stream = frame_stream.load_stream_manifest(ACTIVE, require_authority=False)
        doc = manifest.raw
        if manifest.experiment_id != "OPENDITOO-WEBCAM-N980P-003":
            raise ValueError("W8_EXPERIMENT_ID_DRIFT")
        if (manifest.lifetime_seconds, manifest.min_frame_interval_ms, manifest.max_frames,
                manifest.max_application_packets, manifest.max_tx_bytes) != (10, 40, 251, 753, 264554):
            raise ValueError("W8_BUDGET_ENVELOPE_DRIFT")
        if (stream.get("source_kind"), stream.get("session_profile"), stream.get("playback_interval_ms")) != (
                "live", "streaming_ack_clock", 40):
            raise ValueError("W8_PACING_ENVELOPE_DRIFT")
        if any(doc["session"].get(flag) for flag in
               ("automatic_retry", "automatic_reconnect", "stock_screen_reclaim", "replay_after_interruption")):
            raise ValueError("W8_RETRY_OR_RECLAIM_ENABLED")

        w7 = json.loads(W7.read_text(encoding="utf-8"))
        if (w7.get("status") != "completed_pass_authority_consumed"
                or w7.get("w7_attempt", {}).get("owner_visible_acceptance") != "pass"
                or w7.get("authority", {}).get("authorization_consumed") is not True):
            raise ValueError("W7_BASELINE_NOT_ACCEPTED")

        hashes = stream["live_source"]["producer_code_sha256"]
        for relative, expected in hashes.items():
            candidate = ROOT / relative
            if not candidate.is_file() or activity_session.sha256_file(candidate) != expected:
                raise ValueError(f"W8_PRODUCER_HASH_DRIFT:{relative}")
        if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != manifest.host_build_sha256:
            raise ValueError("W8_HOST_BUILD_HASH_DRIFT")

        readiness = doc.get("readiness", {})
        completed = doc.get("status") == "completed_pass_authority_consumed"
        pending = {"WINDOWS_W8_RUNNER_BUILD_NOT_FROZEN", "WINDOWS_W8_OFFLINE_SELFTEST_NOT_VERIFIED"}
        if completed:
            if readiness.get("grant_ready") or readiness.get("blockers") != ["AUTHORITY_ALREADY_CONSUMED"]:
                raise ValueError("W8_COMPLETED_STATE_INVALID")
        elif readiness.get("grant_ready"):
            if readiness.get("blockers") != []:
                raise ValueError("W8_GRANT_READY_WITH_BLOCKERS")
            prep = doc.get("w8_preparation")
            evidence = ROOT / (prep or {}).get("evidence_file", "")
            if (not isinstance(prep, dict) or prep.get("status") != "pass"
                    or prep.get("device_io") is not False or prep.get("host_session_io") is not False
                    or prep.get("claim_created") is not False or not evidence.is_file()
                    or activity_session.sha256_file(evidence) != prep.get("evidence_sha256")):
                raise ValueError("W8_PREPARATION_EVIDENCE_MISSING_OR_DRIFTED")
        elif set(readiness.get("blockers", [])) != pending:
            raise ValueError("W8_PREPARATION_BLOCKERS_DRIFT")

        blockers = list(readiness.get("blockers", []))
        for blocker in frame_stream.authority_blockers(ACTIVE):
            if blocker not in blockers:
                blockers.append(blocker)
        claim = activity_session.SessionClaim(manifest.experiment_id).read()
        if claim is not None and "AUTHORITY_ALREADY_CONSUMED" not in blockers:
            blockers.append("AUTHORITY_ALREADY_CONSUMED")
        if not completed:
            blockers.append("LIVE_PREFLIGHT_NOT_PERFORMED")

        print(json.dumps({
            "ok": True,
            "manifest_valid": True,
            "experiment_id": manifest.experiment_id,
            "grant_ready": bool(readiness.get("grant_ready")),
            "execution_ready": False,
            "claim_created": claim is not None,
            "device_io": completed,
            "blockers": blockers,
            "session_profile": stream["session_profile"],
            "client_interval_ms": stream["playback_interval_ms"],
            "host_floor_ms": manifest.min_frame_interval_ms,
            "lifetime_seconds": manifest.lifetime_seconds,
            "max_frames": manifest.max_frames,
            "max_application_packets": manifest.max_application_packets,
            "max_tx_bytes": manifest.max_tx_bytes,
            "future_grant_string": doc["authority"]["grant_string_after_readiness"],
            "manifest_sha256": activity_session.sha256_file(ACTIVE),
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, frame_stream.SessionError) as exc:
        print(json.dumps({"ok": False, "device_io": False, "execution_ready": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
