#!/usr/bin/env python3
"""Fail-closed offline audit of the Tier-2 VoiceTip indirect-call trigger.

This proves the runtime50 +0x34 function-pointer sink and its in-image invocation sites,
then deliberately separates that from the still-unproven framework registration/stock
trigger needed to invoke it after a hypothetical display overflow.  Analysis only: no
Bluetooth, packet generation, firmware mutation, Runtime 018 touch, or persistent write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from keypad_pipeline_report import thumb_bl_target
from ditoo_tier2_placement import BRANCHES, FW, APP_LINK_BASE

ROOT = Path(__file__).resolve().parents[1]
CALLBACK_REL = 0x96
WORKER_REL = 0x14E
WRAPPER_REL = 0x578
WORKER_CALL_REL = 0x1C8
WRAPPER_CALL_REL = 0x0A
CALLBACK_FIELD = 0x34
CALLBACK_BODY_PATTERN = bytes.fromhex("486b002801d0486b8047")
WORKER_PROLOGUE = bytes.fromhex("feb5")
WRAPPER_PROLOGUE = bytes.fromhex("80b5")
SETTER_REL = 0x376  # runtime50+0x376 == 0x1fd6a on flag42 prod
SETTER_STORE_REL = 0x18A  # str incoming-r1 copy (r5) to object+0x34
SETTER_STORE = bytes.fromhex("4d63")
SPP_0X6C_HANDLER = 0x11FCE
SPP_A9_HANDLER = 0x12438
SPP_A9_END = 0x124D8


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _load(name: str, spec: dict[str, Any]) -> bytes:
    p = FW / spec["file"]
    b = p.read_bytes()
    if len(b) != spec["size"] or _sha(b) != spec["sha"]:
        raise ValueError(f"{name}: corpus identity drift")
    return b


def _direct_bl_xrefs(b: bytes, target: int) -> list[int]:
    return [o for o in range(0, len(b) - 4, 2) if thumb_bl_target(b, o) == target]


def _absolute_app_pointer_xrefs(b: bytes, target: int) -> list[int]:
    out: list[int] = []
    for v in (APP_LINK_BASE + target, APP_LINK_BASE + target + 1):
        needle = struct.pack("<I", v)
        p = 0
        while True:
            i = b.find(needle, p)
            if i < 0:
                break
            out.append(i)
            p = i + 1
    return sorted(set(out))


def _window_direct_targets(b: bytes, start: int, end: int) -> list[int]:
    out: list[int] = []
    for o in range(start, min(end, len(b) - 4), 2):
        t = thumb_bl_target(b, o)
        if t is not None:
            out.append(t)
    return out


def _branch(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    b = _load(name, spec)
    r = spec["runtime50"]
    cb = r + CALLBACK_REL
    worker = r + WORKER_REL
    wrapper = r + WRAPPER_REL
    setter = r + SETTER_REL
    if b[cb:cb + 2] != bytes.fromhex("10b5"):
        raise ValueError(f"{name}: callback function prologue drift")
    if b[cb + 0x32:cb + 0x32 + len(CALLBACK_BODY_PATTERN)] != CALLBACK_BODY_PATTERN:
        raise ValueError(f"{name}: runtime50 +0x34 BLX body drift")
    if b[worker:worker + 2] != WORKER_PROLOGUE or b[wrapper:wrapper + 2] != WRAPPER_PROLOGUE:
        raise ValueError(f"{name}: VoiceTip worker/wrapper prologue drift")
    callers = _direct_bl_xrefs(b, cb)
    expected = [worker + WORKER_CALL_REL, wrapper + WRAPPER_CALL_REL]
    if callers != expected:
        raise ValueError(f"{name}: callback invocation-site drift {callers!r} != {expected!r}")
    if b[setter + SETTER_STORE_REL:setter + SETTER_STORE_REL + 2] != SETTER_STORE:
        raise ValueError(f"{name}: runtime50 callback setter store drift")
    worker_bl = _direct_bl_xrefs(b, worker)
    wrapper_bl = _direct_bl_xrefs(b, wrapper)
    worker_abs = _absolute_app_pointer_xrefs(b, worker)
    wrapper_abs = _absolute_app_pointer_xrefs(b, wrapper)
    if worker_bl or wrapper_bl or worker_abs or wrapper_abs:
        raise ValueError(f"{name}: trigger registration evidence changed")

    # A9 is an explicit stock voice command, but its direct handler body does not call
    # either VoiceTip invocation wrapper or the callback function.  This is deliberately
    # only a direct-edge statement; external framework callbacks remain outside the blob.
    a9_targets = _window_direct_targets(b, SPP_A9_HANDLER, SPP_A9_END)
    trigger_targets = {cb, worker, wrapper}
    if trigger_targets.intersection(a9_targets):
        raise ValueError(f"{name}: SPP A9 gained a direct VoiceTip trigger edge")

    return {
        "runtime50_constructor": hex(r),
        "callback_function": hex(cb),
        "callback_field_offset": hex(CALLBACK_FIELD),
        "callback_blx": hex(cb + 0x3A),
        "callback_setter": hex(setter),
        "callback_setter_store": hex(setter + SETTER_STORE_REL),
        "worker": hex(worker),
        "wrapper": hex(wrapper),
        "direct_callback_invocation_sites": [hex(x) for x in callers],
        "direct_bl_xrefs_to_worker": [],
        "direct_bl_xrefs_to_wrapper": [],
        "raw_absolute_app_pointer_xrefs_to_worker": [],
        "raw_absolute_app_pointer_xrefs_to_wrapper": [],
        "spp_a9_direct_targets_include_voicetip_trigger": False,
    }


def build_report() -> dict[str, Any]:
    branches = {name: _branch(name, spec) for name, spec in BRANCHES.items()}
    return {
        "schema_version": 1,
        "kind": "ditoo_plus_tier2_voicetip_trigger_gate",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "live_packet_generation": False,
            "firmware_mutation": False,
            "persistent_mutation": False,
            "runtime_018_touched": False,
        },
        "branches": branches,
        "control_sink": {
            "proven": True,
            "object_family": "VoiceTip/runtime50 0x50-byte object",
            "field_offset": "0x34",
            "semantics": "0x1fa8a-family loads object+0x34, checks nonzero, then BLXes the loaded value",
            "setter_semantics": "0x1fd6a-family copies its incoming r1 value into object+0x34 on the configured path",
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
        },
        "invocation_gate": {
            "in_image_invocation_sites_proven": True,
            "two_invocation_paths": [
                "worker path: callback function is reached near the terminal path of the 0x1fb42-family VoiceTip worker",
                "wrapper path: 0x1ff6c-family checks runtime50 byte0 != 0xff and then calls the callback function",
            ],
            "worker_or_wrapper_registration_proven": False,
            "deterministic_stock_post_overwrite_invocation_proven": False,
            "reason": "Across all four preserved branches, the VoiceTip worker and wrapper have no direct in-image BL callers and no raw absolute application-code pointer xrefs. Their registration/dispatch is therefore framework-indirect or encoded outside the directly recoverable app call graph.",
            "reference_branch_adr_search": "No Thumb ADR construction of 0x1fb42, 0x1ff6c, or 0x1fa8a was found in flag42 v42016 during the bounded offline audit.",
        },
        "spp_trigger_checks": {
            "command_0x6c": {
                "direct_voicetip_trigger_edge_proven": False,
                "note": "0x6c is proven to reach the separate DIVOOM_LIGHT_WORD resident display handoff. No direct in-image edge from its handler/display path to the VoiceTip worker/wrapper/callback has been promoted.",
            },
            "command_0xa9_play_stop_voice": {
                "direct_voicetip_trigger_edge_proven": False,
                "note": "The explicit SPP play/stop-voice handler drives a higher-level voice state machine, but its direct handler body does not call the VoiceTip worker, wrapper, or +0x34 callback function.",
            },
        },
        "promotion": {
            "controlled_indirect_call_sink_exists": True,
            "deterministic_post_overwrite_callback_invocation": False,
            "remaining_trigger_blocker": "FRAMEWORK_INDIRECT_VOICETIP_TRIGGER_REGISTRATION_OR_EXPLICIT_STOCK_TRIGGER_UNPROVEN",
            "live_manifest_candidate": None,
        },
        "method_limits": [
            "This proves a real stock indirect-call sink, not attacker-controlled placement or invocation.",
            "Absence of direct BL/raw-pointer edges does not prove the framework can never invoke the VoiceTip worker; it proves only that the registration edge is not directly recoverable from these application blobs with the audited encodings.",
            "No crash/timing behavior is used as an invocation oracle.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", type=Path)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    r = build_report()
    text = json.dumps(r, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text)
    if args.json:
        print(text, end="")
    if args.selfcheck:
        print("DITOO_TIER2_TRIGGER=PASS")
        print(f"TRIGGER_BRANCHES={len(r['branches'])}")
        print("TRIGGER_CONTROL_SINK_PROVEN=true")
        print("TRIGGER_DETERMINISTIC_INVOCATION=false")
        print("TRIGGER_BLOCKER=FRAMEWORK_INDIRECT_VOICETIP_TRIGGER_REGISTRATION_OR_EXPLICIT_STOCK_TRIGGER_UNPROVEN")
        print("TRIGGER_LIVE_MANIFEST_CANDIDATE=NONE")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_TIER2_TRIGGER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
