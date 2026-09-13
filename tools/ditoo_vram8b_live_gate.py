#!/usr/bin/env python3
"""Prepare the fresh one-use VRAM-8B positive-canary manifest entirely offline.

This tool freezes/hash-binds fixtures and an unauthorized manifest only.  It has no
Bluetooth/Windows/device I/O, creates no grant/claim token, and cannot execute the
experiment.  OPENDITOO-VRAM8B-CANARY-001 is a separate authority boundary from all
consumed VRAM67 grants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from ditoo_candidate_codec import decode_candidate_normal, decode_candidate_wrapped, encode_candidate_normal
from ditoo_vram8_stage0_model import (
    ARTIFACT as STAGE0_ARTIFACT,
    CALLBACK_SOURCE_OFFSET,
    CANARY_BASELINE,
    CANARY_EXPECTED,
    CONTROLLED_SOURCE,
    EXACT_SOURCE_LENGTH,
    RUNTIME50_BASE,
    STAGE0_BYTES,
    STAGE0_ENTRY,
    STAGE0_SOURCE,
    STAGE0_SOURCE_OFFSET,
    build_report as build_stage0_report,
)

EXPERIMENT_ID = "OPENDITOO-VRAM8B-CANARY-001"
REQUIRED_GRANT_TEXT = "Grant OPENDITOO-VRAM8B-CANARY-001 -- stock btplayer selected"
TARGET_MAC = "11:75:58:CE:DE:C7"
TARGET_CHANNEL = 1
TARGET_VERSION = 42012

FIXTURE_DIR = ROOT / "experiments/fixtures"
FIXTURE_REPORT = ROOT / "artifacts/analysis/volatile_ram_api_vram8b_fixture.json"
MANIFEST = ROOT / f"experiments/{EXPERIMENT_ID}.json"
SOURCE_FILE = FIXTURE_DIR / f"{EXPERIMENT_ID}-source.bin"

PACKET_FILES = {
    "baseline_set": FIXTURE_DIR / f"{EXPERIMENT_ID}-01-baseline-set.bin",
    "baseline_get": FIXTURE_DIR / f"{EXPERIMENT_ID}-02-baseline-get.bin",
    "prime": FIXTURE_DIR / f"{EXPERIMENT_ID}-03-prime.bin",
    "voicetip": FIXTURE_DIR / f"{EXPERIMENT_ID}-04-voicetip.bin",
    "overwrite": FIXTURE_DIR / f"{EXPERIMENT_ID}-05-overwrite.bin",
    "post_get": FIXTURE_DIR / f"{EXPERIMENT_ID}-06-post-get.bin",
    "restore_set": FIXTURE_DIR / f"{EXPERIMENT_ID}-07-restore-set.bin",
    "restore_get": FIXTURE_DIR / f"{EXPERIMENT_ID}-08-restore-get.bin",
}
EXPECTED_RESPONSE_FILES = {
    "baseline_get_0": FIXTURE_DIR / f"{EXPERIMENT_ID}-expected-b3-0.bin",
    "post_get_1": FIXTURE_DIR / f"{EXPERIMENT_ID}-expected-b3-1.bin",
}

AUTHORITATIVE = {
    "tier2_display": ROOT / "artifacts/analysis/volatile_ram_api_tier2_display.json",
    "tier2_placement": ROOT / "artifacts/analysis/volatile_ram_api_tier2_placement.json",
    "tier2_trigger": ROOT / "artifacts/analysis/volatile_ram_api_tier2_trigger.json",
    "vram3_execution": ROOT / "artifacts/analysis/volatile_ram_api_vram3_execution.json",
    "vram8a_stage0": STAGE0_ARTIFACT,
    "vram67_002_live_result": ROOT / "captures/OPENDITOO-VRAM67-BXLR-002-LIVE-RESULT-2026-09-12.json",
    "runtime018_policy": ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-018.json",
    "exact_unit_m4": ROOT / "captures/OPENDITOO-DAY1-M4-LIVE-RESULT-2026-09-08.json",
}

RUNTIME50_SOURCE_OFFSET = RUNTIME50_BASE - CONTROLLED_SOURCE
RUNTIME50_BYTE0 = 0xFF
RUNTIME50_MODEL_OFFSET = 0x08
RUNTIME50_MODEL = 0x22
SOURCE_FILL = 0xFF

BASELINE_SET_PAYLOAD = bytes([CANARY_BASELINE])
GET_PAYLOAD = b""
PRIME_PAYLOAD = bytes([0x01])
VOICETIP_PAYLOAD = bytes([0x01, 0x02, 0x01])
FRAME_COUNTER = 0
INTER_PACKET_DELAY_MS = 40
OBSERVATION_HOLD_MS = 75_000
CONNECT_BUDGET_MS = 15_000
TOTAL_BUDGET_MS = 100_000


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _encode_expected_wrapped(command: int, payload: bytes) -> bytes:
    """Exact wrapped response shape already observed on the purchased unit."""
    payload = bytes(payload)
    inner = len(payload) + 5
    prefix = inner.to_bytes(2, "little") + bytes((0x04, command, 0x55)) + payload
    checksum = sum(prefix) & 0xFFFF
    return b"\x01" + prefix + checksum.to_bytes(2, "little") + b"\x02"


def build_source() -> bytes:
    src = bytearray([SOURCE_FILL]) * EXACT_SOURCE_LENGTH
    src[STAGE0_SOURCE_OFFSET:STAGE0_SOURCE_OFFSET + len(STAGE0_BYTES)] = STAGE0_BYTES
    src[RUNTIME50_SOURCE_OFFSET] = RUNTIME50_BYTE0
    src[RUNTIME50_SOURCE_OFFSET + RUNTIME50_MODEL_OFFSET] = RUNTIME50_MODEL
    src[CALLBACK_SOURCE_OFFSET:CALLBACK_SOURCE_OFFSET + 4] = STAGE0_ENTRY.to_bytes(4, "little")
    return bytes(src)


def build_packets() -> dict[str, bytes]:
    source = build_source()
    overwrite_payload = FRAME_COUNTER.to_bytes(2, "little") + EXACT_SOURCE_LENGTH.to_bytes(2, "little") + source
    return {
        "source": source,
        "baseline_set": encode_candidate_normal(0xB2, BASELINE_SET_PAYLOAD),
        "baseline_get": encode_candidate_normal(0xB3, GET_PAYLOAD),
        "prime": encode_candidate_normal(0x6E, PRIME_PAYLOAD),
        "voicetip": encode_candidate_normal(0xA5, VOICETIP_PAYLOAD),
        "overwrite": encode_candidate_normal(0x6C, overwrite_payload),
        "post_get": encode_candidate_normal(0xB3, GET_PAYLOAD),
        "restore_set": encode_candidate_normal(0xB2, BASELINE_SET_PAYLOAD),
        "restore_get": encode_candidate_normal(0xB3, GET_PAYLOAD),
        "expected_b3_0": _encode_expected_wrapped(0xB3, bytes([CANARY_BASELINE])),
        "expected_b3_1": _encode_expected_wrapped(0xB3, bytes([CANARY_EXPECTED])),
    }


def _verify_authority_inputs() -> dict[str, str]:
    stage0_live = build_stage0_report()
    stage0_committed = _json(STAGE0_ARTIFACT)
    _require(stage0_live == stage0_committed, "VRAM-8A committed artifact drift")
    _require(stage0_live["promotion"]["vram8a_callback_abi_closed"], "VRAM-8A ABI not closed")
    _require(stage0_live["promotion"]["vram8a_positive_reversible_canary_closed_offline"], "VRAM-8A canary not closed")
    _require(not stage0_live["promotion"]["vram8b_live_authorized"], "VRAM-8A unexpectedly claims live authority")

    v67 = _json(AUTHORITATIVE["vram67_002_live_result"])
    _require(v67["experiment_id"] == "OPENDITOO-VRAM67-BXLR-002", "VRAM67-002 identity drift")
    _require(v67["classification"] == "PASS_UNDER_PROMOTED_OFFLINE_TRIGGER_MODEL", "VRAM67-002 live classification drift")
    _require(v67["promotion"]["minimal_returning_stage0"] == "LIVE_PASS_UNDER_COMPOSITE_DISCRIMINATOR", "VRAM67-002 return promotion drift")
    _require(v67["stop_boundary"] == "STOP_BEFORE_VRAM8_BOUNDED_LOADER_DESIGN_OR_ANY_NEW_LIVE_GRANT", "VRAM67-002 stop boundary drift")

    m4 = _json(AUTHORITATIVE["exact_unit_m4"])
    _require(m4["status"] == "pass", "exact-unit M4 identity result drift")
    _require(m4["target"]["address"] == TARGET_MAC, "target MAC drift")
    _require(m4["target"]["rfcomm_channel"] == TARGET_CHANNEL, "target RFCOMM channel drift")
    _require(m4["result"]["decoded_version"] == TARGET_VERSION, "target firmware version drift")

    return {name: _sha_path(path) for name, path in AUTHORITATIVE.items()}


def build_report() -> dict[str, Any]:
    hashes = _verify_authority_inputs()
    p = build_packets()
    src = p["source"]

    _require(len(src) == EXACT_SOURCE_LENGTH, "source length drift")
    _require(src[STAGE0_SOURCE_OFFSET:STAGE0_SOURCE_OFFSET + len(STAGE0_BYTES)] == STAGE0_BYTES, "stage0 placement drift")
    _require(int.from_bytes(src[CALLBACK_SOURCE_OFFSET:CALLBACK_SOURCE_OFFSET + 4], "little") == STAGE0_ENTRY, "callback target drift")
    _require(src[RUNTIME50_SOURCE_OFFSET] == RUNTIME50_BYTE0, "runtime50 byte0 drift")
    _require(src[RUNTIME50_SOURCE_OFFSET + RUNTIME50_MODEL_OFFSET] == RUNTIME50_MODEL, "runtime50 model drift")

    expected_commands = {
        "baseline_set": (0xB2, BASELINE_SET_PAYLOAD),
        "baseline_get": (0xB3, GET_PAYLOAD),
        "prime": (0x6E, PRIME_PAYLOAD),
        "voicetip": (0xA5, VOICETIP_PAYLOAD),
        "post_get": (0xB3, GET_PAYLOAD),
        "restore_set": (0xB2, BASELINE_SET_PAYLOAD),
        "restore_get": (0xB3, GET_PAYLOAD),
    }
    for key, expected in expected_commands.items():
        d = decode_candidate_normal(p[key])
        _require((d.command, d.payload) == expected, f"{key}: frozen stock-shaped packet drift")
    ov = decode_candidate_normal(p["overwrite"])
    _require(ov.command == 0x6C, "overwrite command drift")
    _require(int.from_bytes(ov.payload[:2], "little") == FRAME_COUNTER, "overwrite frame counter drift")
    _require(int.from_bytes(ov.payload[2:4], "little") == EXACT_SOURCE_LENGTH, "overwrite declared length drift")
    _require(ov.payload[4:] == src, "overwrite source drift")

    for key, value in (("expected_b3_0", CANARY_BASELINE), ("expected_b3_1", CANARY_EXPECTED)):
        d = decode_candidate_wrapped(p[key])
        _require((d.outer_command, d.command, d.tag, d.payload) == (0x04, 0xB3, 0x55, bytes([value])), f"{key}: response fixture drift")

    packet_order = ["baseline_set", "baseline_get", "prime", "voicetip", "overwrite", "post_get", "restore_set", "restore_get"]
    return {
        "schema_version": 1,
        "kind": "openditoo_vram8b_positive_canary_fixture",
        "experiment_id": EXPERIMENT_ID,
        "ok": True,
        "safety": {
            "offline_preparation_only": True,
            "device_io": False,
            "bluetooth_opened": False,
            "packets_transmitted": 0,
            "runtime_018_touched": False,
            "firmware_or_flash_mutation": False,
            "persistent_mutation": False,
            "generic_loader_or_raw_call_surface": False,
        },
        "authority_boundary": {
            "status": "PREPARED_UNAUTHORIZED_STOP_BEFORE_LIVE",
            "required_grant_text": REQUIRED_GRANT_TEXT,
            "previous_grants_transfer": False,
            "grant_materialized": False,
            "claim_materialized": False,
            "runner_materialized": False,
        },
        "target": {
            "model": "Divoom Ditoo Plus",
            "purchased_unit_only": True,
            "mac": TARGET_MAC,
            "rfcomm_channel": TARGET_CHANNEL,
            "installed_firmware_version_assumption": TARGET_VERSION,
        },
        "authoritative_inputs": {name: {"path": str(path.relative_to(ROOT)), "sha256": hashes[name]} for name, path in AUTHORITATIVE.items()},
        "stage0": {
            "source_address": hex(STAGE0_SOURCE),
            "entry": hex(STAGE0_ENTRY),
            "source_offset": hex(STAGE0_SOURCE_OFFSET),
            "bytes_hex": STAGE0_BYTES.hex(),
            "sha256": _sha_bytes(STAGE0_BYTES),
            "source_length": EXACT_SOURCE_LENGTH,
            "source_sha256": _sha_bytes(src),
            "callback_source_offset": hex(CALLBACK_SOURCE_OFFSET),
            "callback_value": hex(STAGE0_ENTRY),
            "runtime50_base": hex(RUNTIME50_BASE),
            "runtime50_source_offset": hex(RUNTIME50_SOURCE_OFFSET),
            "runtime50_model": hex(RUNTIME50_MODEL),
        },
        "sequence": [
            {"ordinal": 1, "key": "baseline_set", "class": "stock-shaped", "command": "0xb2", "purpose": "force fixed canary baseline 0"},
            {"ordinal": 2, "key": "baseline_get", "class": "stock-shaped", "command": "0xb3", "purpose": "typed baseline proof; require decoded raw value 0"},
            {"ordinal": 3, "key": "prime", "class": "stock-shaped", "command": "0x6e", "purpose": "prime content mode 0x0b"},
            {"ordinal": 4, "key": "voicetip", "class": "stock-shaped", "command": "0xa5", "purpose": "VoiceTip setup selector 2/model 0x22"},
            {"ordinal": 5, "key": "overwrite", "class": "custom-once", "command": "0x6c", "purpose": "exact 1088-byte overwrite with fixed nontrivial stage-0"},
            {"ordinal": 6, "key": "post_get", "class": "stock-shaped", "command": "0xb3", "purpose": "positive stage-0 marker after hold; require decoded raw value 1"},
            {"ordinal": 7, "key": "restore_set", "class": "stock-shaped", "command": "0xb2", "purpose": "restore fixed baseline 0"},
            {"ordinal": 8, "key": "restore_get", "class": "stock-shaped", "command": "0xb3", "purpose": "typed restoration proof; require decoded raw value 0"},
        ],
        "fixtures": {
            "source": {"path": str(SOURCE_FILE.relative_to(ROOT)), "length": len(src), "sha256": _sha_bytes(src)},
            **{
                key: {
                    "path": str(PACKET_FILES[key].relative_to(ROOT)),
                    "wire_length": len(p[key]),
                    "sha256": _sha_bytes(p[key]),
                    "wire_hex": p[key].hex() if key != "overwrite" else None,
                    "wire_prefix_hex": p[key][:16].hex() if key == "overwrite" else None,
                    "wire_suffix_hex": p[key][-16:].hex() if key == "overwrite" else None,
                }
                for key in packet_order
            },
            "expected_b3_0": {"path": str(EXPECTED_RESPONSE_FILES["baseline_get_0"].relative_to(ROOT)), "sha256": _sha_bytes(p["expected_b3_0"]), "wire_hex": p["expected_b3_0"].hex()},
            "expected_b3_1": {"path": str(EXPECTED_RESPONSE_FILES["post_get_1"].relative_to(ROOT)), "sha256": _sha_bytes(p["expected_b3_1"]), "wire_hex": p["expected_b3_1"].hex()},
        },
        "transport_budget": {
            "max_connections": 1,
            "exact_application_sends": 8,
            "max_custom_0x6c_sends": 1,
            "retry": False,
            "reconnect": False,
            "inter_packet_delay_ms": INTER_PACKET_DELAY_MS,
            "observation_hold_ms_after_overwrite": OBSERVATION_HOLD_MS,
            "connect_budget_ms": CONNECT_BUDGET_MS,
            "total_budget_ms": TOTAL_BUDGET_MS,
        },
        "response_contract": {
            "wrapped_outer_command": "0x04",
            "echo_command": "0xb3",
            "tag": "0x55",
            "payload_length": 1,
            "baseline_expected": 0,
            "post_stage0_expected": 1,
            "restored_expected": 0,
            "unexpected_or_missing_response": "NOT_PASS_STOP_NO_RETRY",
        },
        "success_discriminator": {
            "required": [
                "baseline GET decodes to raw energy-control value 0",
                "all eight frozen application sends complete on the same RFCOMM connection with no retry",
                "the single custom 0x6c overwrite is sent exactly once",
                "after the full post-overwrite hold, GET decodes to raw value 1",
                "the connection remains alive and no crash/reboot/watchdog/disconnect symptom occurs",
                "restore SET 0 then GET decodes to 0",
                "accepted Runtime 018 is restored afterward and returns connected with last_error=null",
            ],
            "interpretation": "The 0 -> 1 -> 0 typed stock readback is the positive RAM-only execution marker. Liveness alone is insufficient, and crash/reboot/disconnect/timing behavior can never be success.",
        },
        "stop_policy": {
            "baseline_not_zero": "STOP_NO_CUSTOM_OVERWRITE_RESTORE_RUNTIME018",
            "ambiguous_or_partial_send": "STOP_NO_RETRY_RESTORE_RUNTIME018",
            "unexpected_or_missing_b3_response": "STOP_NO_RETRY_RESTORE_RUNTIME018",
            "disconnect_or_crash": "STOP_NO_RETRY_RESTORE_RUNTIME018_IF_POSSIBLE",
            "post_get_not_one": "NOT_PASS_RESTORE_BASELINE_AND_RUNTIME018_STOP",
            "restore_get_not_zero": "NOT_PASS_STOP_AND_RECORD_RESTORE_FAILURE",
            "candidate_pass": "RESTORE_RUNTIME018_RECORD_RESULT_STOP_BEFORE_ANY_VRAM8D_OR_VRAM9_WORK",
        },
    }


def build_manifest(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "openditoo_vram8b_positive_canary_one_use_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": "prepared_unauthorized",
        "purpose": "One exact nontrivial RAM-only canary: fixed stock baseline 0 -> exact 20-byte returning Thumb stage-0 toggles one typed volatile byte -> stock GET proves value 1 -> stock restore/query returns to 0. No resident install, loader, generic call target, persistence, flash, MassBoot, or VRAM-9 surface.",
        "fixture_report": {"path": str(FIXTURE_REPORT.relative_to(ROOT)), "sha256": _sha_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())},
        "target": report["target"],
        "authoritative_inputs": report["authoritative_inputs"],
        "stage0": report["stage0"],
        "sequence": [dict(item, **report["fixtures"][item["key"]]) for item in report["sequence"]],
        "expected_responses": {
            "baseline_or_restore_zero": report["fixtures"]["expected_b3_0"],
            "post_stage0_one": report["fixtures"]["expected_b3_1"],
            **report["response_contract"],
        },
        "transport_budget": report["transport_budget"],
        "success_discriminator": report["success_discriminator"],
        "stop_policy": report["stop_policy"],
        "live_boundary": {
            "runtime018_must_remain_untouched_until_fresh_owner_grant": True,
            "no_bluetooth_open_before_grant": True,
            "no_grant_or_claim_file_exists_from_this_preparation": True,
            "runner_not_materialized": True,
            "vram8d_resident_install_is_separate_future_grant": True,
            "vram9_not_authorized": True,
        },
        "authority": {
            "required_grant_text": REQUIRED_GRANT_TEXT,
            "transmission_authorized": False,
            "authorization_consumed": False,
            "one_use": True,
            "retry": False,
            "previous_grants_transfer": False,
            "grant_materialization_rule": "Only after the owner sends the exact fresh VRAM-8B grant text. Any future grant must bind the committed manifest SHA-256 and fixture-report SHA-256 and create a fresh one-use nonce/claim before socket creation.",
        },
        "result": None,
    }


def write_all() -> tuple[dict[str, Any], dict[str, Any]]:
    report = build_report()
    packets = build_packets()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_FILE.write_bytes(packets["source"])
    for key, path in PACKET_FILES.items():
        path.write_bytes(packets[key])
    EXPECTED_RESPONSE_FILES["baseline_get_0"].write_bytes(packets["expected_b3_0"])
    EXPECTED_RESPONSE_FILES["post_get_1"].write_bytes(packets["expected_b3_1"])
    FIXTURE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    FIXTURE_REPORT.write_text(report_text, encoding="utf-8")
    manifest = build_manifest(report)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, manifest


def verify_committed() -> tuple[dict[str, Any], dict[str, Any]]:
    report = build_report()
    committed_report = _json(FIXTURE_REPORT)
    _require(report == committed_report, "committed VRAM-8B fixture report drift")
    packets = build_packets()
    _require(SOURCE_FILE.read_bytes() == packets["source"], "source fixture drift")
    for key, path in PACKET_FILES.items():
        _require(path.read_bytes() == packets[key], f"packet fixture drift: {key}")
    _require(EXPECTED_RESPONSE_FILES["baseline_get_0"].read_bytes() == packets["expected_b3_0"], "expected zero response drift")
    _require(EXPECTED_RESPONSE_FILES["post_get_1"].read_bytes() == packets["expected_b3_1"], "expected one response drift")
    manifest = build_manifest(report)
    _require(_json(MANIFEST) == manifest, "committed VRAM-8B manifest drift")
    return report, manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    report, manifest = write_all() if args.write else (verify_committed() if FIXTURE_REPORT.exists() and MANIFEST.exists() else (build_report(), None))
    if manifest is None:
        manifest = build_manifest(report)
    if args.selfcheck:
        print("DITOO_VRAM8B_LIVE_GATE=PASS")
        print(f"VRAM8B_EXPERIMENT_ID={EXPERIMENT_ID}")
        print(f"VRAM8B_STAGE0_ENTRY={report['stage0']['entry']}")
        print(f"VRAM8B_SOURCE_SHA256={report['stage0']['source_sha256']}")
        print("VRAM8B_APPLICATION_SENDS=8")
        print("VRAM8B_CUSTOM_0X6C_SENDS=1")
        print("VRAM8B_TYPED_CANARY=0_TO_1_TO_0")
        print("VRAM8B_AUTHORITY=PREPARED_UNAUTHORIZED_STOP_BEFORE_LIVE")
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    if not (args.write or args.selfcheck or args.json):
        print("DITOO_VRAM8B_LIVE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
