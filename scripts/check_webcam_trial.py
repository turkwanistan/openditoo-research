#!/usr/bin/env python3
"""Read-only review of the active webcam candidate; no Host/camera/device I/O or claims."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import activity_session, frame_stream

ACTIVE = ROOT / "experiments/DAY1-WEBCAM-N980P-002.json"


def main() -> int:
    path = ACTIVE
    try:
        manifest, _, stream = frame_stream.load_stream_manifest(path, require_authority=False)
        doc = manifest.raw
        if manifest.experiment_id != "OPENDITOO-WEBCAM-N980P-002":
            raise ValueError("active webcam experiment id drift")
        if (manifest.lifetime_seconds, manifest.min_frame_interval_ms, manifest.max_frames,
                manifest.max_application_packets, manifest.max_tx_bytes) != (10, 40, 112, 336, 118048):
            raise ValueError("webcam budget envelope drift")
        if (stream.get("source_kind"), stream.get("session_profile"), stream.get("playback_interval_ms")) != (
                "live", "streaming_ack_clock", 90):
            raise ValueError("webcam pacing/source envelope drift")
        adapter = doc.get("adapter", {})
        expected_routes = ["/v1/status", "/v1/session/open", "/v1/session/frame", "/v1/session/close"]
        if adapter.get("typed_origin") != "http://127.0.0.1:8796" or adapter.get("routes") != expected_routes:
            raise ValueError("webcam typed adapter envelope drift")

        readiness = doc.get("readiness", {})
        if readiness.get("execution_ready"):
            raise ValueError("review manifest never claims live preflight execution-ready")
        pending = {
            "WINDOWS_STATUS_CONTRACT_FIX_NOT_VERIFIED",
            "WINDOWS_RUNNER_REBUILD_NOT_FROZEN",
        }
        completed = doc.get("status") == "completed_pass_authority_consumed"
        if completed:
            if readiness.get("grant_ready") or readiness.get("blockers") != ["AUTHORITY_ALREADY_CONSUMED"]:
                raise ValueError("completed webcam trial must be consumed and non-grant-ready")
        elif readiness.get("grant_ready"):
            if readiness.get("blockers") != []:
                raise ValueError("grant-ready webcam candidate must have no engineering blockers")
        elif set(readiness.get("blockers", [])) != pending:
            raise ValueError("webcam rerun preparation blockers drift")

        verification = doc.get("w6_verification", {})
        evidence = ROOT / verification.get("evidence_file", "")
        if (verification.get("status") != "pass" or verification.get("windows_offline_pass") is not True
                or verification.get("device_io") is not False or verification.get("claim_created") is not False
                or not evidence.is_file()
                or activity_session.sha256_file(evidence) != verification.get("evidence_sha256")):
            raise ValueError("W6 Windows verification evidence missing or drifted")

        rerun = doc.get("w7_rerun_preparation")
        if readiness.get("grant_ready"):
            if not isinstance(rerun, dict) or rerun.get("status") != "pass":
                raise ValueError("W7 rerun preparation evidence missing")
            rerun_evidence = ROOT / rerun.get("evidence_file", "")
            if (not rerun_evidence.is_file()
                    or activity_session.sha256_file(rerun_evidence) != rerun.get("evidence_sha256")
                    or rerun.get("device_io") is not False
                    or rerun.get("host_session_io") is not False):
                raise ValueError("W7 rerun preparation evidence drift")

        hashes = stream["live_source"]["producer_code_sha256"]
        for relative, expected in hashes.items():
            candidate = ROOT / relative
            if not candidate.is_file() or activity_session.sha256_file(candidate) != expected:
                raise ValueError(f"producer artifact missing or changed: {relative}")
        if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != manifest.host_build_sha256:
            raise ValueError("repository Host build changed")

        blockers = list(readiness.get("blockers", []))
        for blocker in frame_stream.authority_blockers(path):
            if blocker not in blockers:
                blockers.append(blocker)
        if activity_session.SessionClaim(manifest.experiment_id).read() is not None and "AUTHORITY_ALREADY_CONSUMED" not in blockers:
            blockers.append("AUTHORITY_ALREADY_CONSUMED")
        if not completed:
            blockers.append("LIVE_PREFLIGHT_NOT_PERFORMED")
        claim_present = activity_session.SessionClaim(manifest.experiment_id).read() is not None
        print(json.dumps({
            "ok": True, "manifest_valid": True, "device_io": completed, "claim_created": claim_present,
            "execution_ready": False, "grant_ready": bool(readiness.get("grant_ready")),
            "experiment_id": manifest.experiment_id, "blockers": blockers,
            "manifest_sha256": activity_session.sha256_file(path),
            "source_kind": stream["source_kind"], "session_profile": stream["session_profile"],
            "lifetime_seconds": manifest.lifetime_seconds,
            "min_frame_interval_ms": manifest.min_frame_interval_ms,
            "max_frames": manifest.max_frames, "max_application_packets": manifest.max_application_packets,
            "max_tx_bytes": manifest.max_tx_bytes,
            "future_grant_string": manifest.raw["authority"]["grant_string_after_readiness"],
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, frame_stream.SessionError) as exc:
        print(json.dumps({"ok": False, "device_io": False, "execution_ready": False,
                          "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
