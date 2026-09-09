#!/usr/bin/env python3
"""Read-only W6 review: never opens a camera, contacts a Host, or claims an experiment."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import activity_session, frame_stream


def main() -> int:
    path = ROOT / "experiments/DAY1-WEBCAM-N980P-001.json"
    try:
        manifest, _, stream = frame_stream.load_stream_manifest(path, require_authority=False)
        hashes = stream["live_source"]["producer_code_sha256"]
        for relative, expected in hashes.items():
            candidate = ROOT / relative
            if not candidate.is_file() or activity_session.sha256_file(candidate) != expected:
                raise ValueError(f"producer artifact missing or changed: {relative}")
        if activity_session.sha256_file(activity_session.HOST_BUILD_DLL) != manifest.host_build_sha256:
            raise ValueError("repository Host build changed")
        blockers = list(manifest.raw["readiness"]["blockers"])
        blockers.extend(frame_stream.authority_blockers(path))
        if activity_session.SessionClaim(manifest.experiment_id).read() is not None:
            blockers.append("AUTHORITY_ALREADY_CONSUMED")
        # This checker cannot prove an installed binary or physical controller ownership.
        blockers.append("LIVE_PREFLIGHT_NOT_PERFORMED")
        print(json.dumps({
            "ok": True, "manifest_valid": True, "device_io": False, "claim_created": False,
            "execution_ready": False, "grant_ready": False,
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
