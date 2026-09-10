#!/usr/bin/env python3
"""Freeze OPENDITOO-INTERACTIVE-HF3-001 to an unauthorized, reviewable manifest.

Zero device I/O, zero Host-session I/O and no claim. In environments where /mnt/c is not
visible (notably WSL_MCP's sandbox), the accepted Runtime 006 ButtonProbe hashes are inherited
but the manifest remains not grant-ready until this preparation is re-run from normal local WSL
and those installed bytes are re-verified directly.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host import activity_session, frame_stream, interactive_acceptance as hf3

MANIFEST = ROOT / "experiments/DAY1-INTERACTIVE-HF3-001.json"
EVIDENCE = ROOT / "captures/OPENDITOO-INTERACTIVE-HF3-001-PREPARATION-2026-09-10.json"
R006 = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-006.json"


def _runtime006_probe_hashes() -> dict[str, str]:
    raw = json.loads(R006.read_text(encoding="utf-8"))
    hashes = raw["build"]["button_probe_sha256"]
    exe = next(value for key, value in hashes.items() if key.lower().endswith("openditoo.buttonprobe.exe"))
    dll = next(value for key, value in hashes.items() if key.lower().endswith("openditoo.buttonprobe.dll"))
    return {str(hf3.BUTTON_PROBE_EXE): exe, str(hf3.BUTTON_PROBE_DLL): dll}


def _probe_verified(hashes: dict[str, str]) -> bool:
    return all(Path(name).is_file() and hf3.sha256_file(Path(name)) == digest
               for name, digest in hashes.items())


def _main_worktree() -> Path:
    raw = subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=ROOT, text=True)
    current = None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            current = Path(line.split(" ", 1)[1])
        elif line == "branch refs/heads/main" and current is not None:
            return current
    raise SystemExit("HF3_PREP_MAIN_WORKTREE_NOT_FOUND")


def main() -> int:
    main_root = _main_worktree()
    if activity_session.SessionClaim(hf3.EXPERIMENT_ID, main_root / ".openditoo-local/session-claims").path.exists():
        raise SystemExit("HF3_PREP_REFUSES_EXISTING_OUTER_CLAIM")
    if MANIFEST.exists():
        previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        authority = previous.get("authority") or {}
        if authority.get("transmission_authorized") or authority.get("authorization_consumed"):
            raise SystemExit("HF3_PREP_REFUSES_AUTHORIZED_OR_CONSUMED_MANIFEST")

    probe_hashes = _runtime006_probe_hashes()
    probe_verified_now = _probe_verified(probe_hashes)
    host_hash = hf3.sha256_file(hf3.HOST_BUILD)
    code_hashes = hf3.module_hashes()
    max_frames = 500
    max_tx = max_frames * frame_stream.worst_case_frame_tx_bytes()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    doc = {
        "schema_version": hf3.SCHEMA_VERSION,
        "kind": hf3.KIND,
        "experiment_id": hf3.EXPERIMENT_ID,
        "milestone": "HF-3 one-use high-FPS interactive page / repeated profile-open acceptance",
        "status": "prepared_unauthorized" if probe_verified_now else "offline_prepared_probe_reverification_required",
        "objective": "Prove the generic Dashboard <-> streaming_ack_clock page boundary with the three-reel slots app, including one-reel-per-lever behavior and ten complete high-rate profile cycles without retry after ambiguity.",
        "readiness": {
            "offline_ready": True,
            "grant_ready": probe_verified_now,
            "blockers": [] if probe_verified_now else ["BUTTON_PROBE_INSTALLED_BYTES_NOT_VISIBLE_IN_THIS_ENVIRONMENT"],
            "required_followup": None if probe_verified_now else "Re-run this preparation from normal local WSL where /mnt/c is visible; installed ButtonProbe hashes must match accepted Runtime 006 before grant."
        },
        "target": {
            "exact_unit_id": activity_session.EXACT_UNIT_ID,
            "installed_firmware": activity_session.INSTALLED_FIRMWARE,
            "model": "Ditoo Plus",
            "rfcomm_channel": 1,
            "target_override_enabled": False,
        },
        "transport": {
            "measured_endpoint": "Windows Classic RFCOMM channel 1",
            "host_origin": "http://127.0.0.1:8796",
            "one_controller": True,
            "allowed_session_profiles": [hf3.RATE_ACTIVITY, hf3.RATE_STREAMING],
            "one_frame_in_flight": True,
            "pipelining": False,
            "raw_send_enabled": False,
            "retry_after_ambiguous": False,
            "known_canvas_reclaim": "Only exact canvas_invalidated with stopped_clean or stopped_yielded_to_stock may open a fresh child while the page remains selected; any other non-clean child outcome terminates the outer experiment.",
        },
        "build": {
            "source_checkpoint": head,
            "code_sha256": code_hashes,
            "host_dll_sha256": host_hash,
            "button_probe_sha256": probe_hashes,
            "button_probe_hash_source": "accepted Runtime 006 policy/template",
            "button_probe_verified_now": probe_verified_now,
        },
        "acceptance": {
            "lifetime_seconds": 90,
            "max_child_sessions": 28,
            "max_total_frames": max_frames,
            "max_total_tx_bytes": max_tx,
            "activity_child_max_frames": 20,
            "streaming_child_max_frames": 120,
            "target_profile_cycles": 10,
            "pages": [
                {"name": "dashboard", "session_profile": hf3.RATE_ACTIVITY,
                 "renderer": "accepted MCP dashboard + successor lightning pulse"},
                {"name": "slots", "session_profile": hf3.RATE_STREAMING,
                 "renderer": "procedural three-reel slots; ACK-advanced motion"},
            ],
            "long_lever_holds_mapped": False,
            "manual_choreography": [
                "Start from a healthy Runtime 006 dashboard; coordinator suspends it and verifies Host idle.",
                "HF-3 opens its own dashboard child; Right selects slots.",
                "Confirm three reels spin; three short lever pulls stop reel 1, then 2, then 3.",
                "One more short lever starts a new round.",
                "Use Left/Right to complete ten Dashboard <-> Slots high-rate profile cycles total.",
                "Return to Dashboard, cause one genuine MCP activity event and visually inspect the lightning strike.",
                "Ctrl+C after the tenth cycle/pulse; coordinator restores Runtime 006.",
            ],
            "specific_regression_target": "No IMAGE_RX_RECV_TIMEOUT or other ambiguous failure on/after the fourth streaming-profile reopen.",
        },
        "stop_policy": {
            "stop_immediately_on": [
                "any Host open/send/refusal/ACK timeout not reported as the exact known canvas-invalidated outcome",
                "outer 90 second lifetime",
                "outer 500 ACKed-frame / derived byte budget",
                "28 attempted Host child sessions",
                "operator Ctrl+C",
            ],
            "on_ambiguous_outcome_resend": False,
            "automatic_retry": False,
            "automatic_reconnect_after_ambiguous": False,
            "restore_runtime006_after_terminal": True,
        },
        "persistence_analysis": {
            "expected_effect": "volatile display/game state only",
            "forbidden": "firmware/update/gallery persistence, raw send, target selection, command enumeration, pipelining",
        },
        "authority": {
            "experiment_id": hf3.EXPERIMENT_ID,
            "required_grant_text": hf3.REQUIRED_GRANT_TEXT,
            "transmission_authorized": False,
            "authorization_consumed": False,
            "granted_by": None,
            "grant_text": None,
            "expires_at": None,
            "grant_scope_requested": "ONE bounded HF-3 interactive acceptance on exact Ditoo 11:75:58:CE:DE:C7 v42012: at most 90 s, 28 child session attempts, 500 ACKed frames and derived byte ceiling; only activity + streaming_ack_clock profiles; Dashboard + slots pages; physical Left/Right + short lever; known canvas-invalidated reclaim only; no retry after ambiguity, no raw send/pipelining/target override/persistence; Runtime 006 suspended then restored separately.",
        },
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    reviewed = hf3.load_manifest(MANIFEST, verify_hashes=True,
                                 verify_button_probe=probe_verified_now,
                                 require_authority=False)
    blockers = hf3.authority_blockers(MANIFEST)
    evidence = {
        "schema_version": 1,
        "experiment_id": reviewed.experiment_id,
        "status": "pass_offline" if not probe_verified_now else "pass_grant_ready",
        "prepared_from_git_head": head,
        "manifest_sha256": hf3.sha256_file(MANIFEST),
        "checks": {
            "code_hashes_verified": True,
            "host_build_verified": True,
            "host_dll_sha256": host_hash,
            "button_probe_hashes_inherited_from_runtime006": True,
            "button_probe_installed_bytes_verified_now": probe_verified_now,
            "outer_budget_derived": True,
        },
        "operation": {"claim_created": False, "host_session_io": False, "device_io": False},
        "authority_blockers": blockers,
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "HF3_PREP_PASS": reviewed.experiment_id,
        "manifest": str(MANIFEST),
        "manifest_sha256": evidence["manifest_sha256"],
        "offline_ready": True,
        "grant_ready": probe_verified_now,
        "button_probe_verified_now": probe_verified_now,
        "authority_blockers": blockers,
        "device_io": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
