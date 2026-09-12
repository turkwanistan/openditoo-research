#!/usr/bin/env python3
"""Fail-closed offline audit of the Tier-2 VoiceTip indirect-call trigger.

This proves the runtime50 +0x34 function-pointer sink, the VoiceTip microtask
registration that periodically reaches its worker, and the resident timer-dispatch
mechanism.  It deliberately keeps the final stock state transition into the +0x34
callback fail-closed until a deterministic post-overwrite completion/idle path is
proven.  Analysis only: no Bluetooth, packet generation, firmware mutation,
Runtime 018 touch, or persistent write.
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
SETTER_REL = 0x376
SETTER_STORE_REL = 0x18A
SETTER_STORE = bytes.fromhex("4d63")
SPP_0X6C_HANDLER = 0x11FCE
SPP_A9_HANDLER = 0x12438
SPP_A9_END = 0x124D8

# VoiceTip registers its worker through Fwl_MicroTask using a relocated callback
# namespace.  callback_value = 0x00200000 + (file_offset - 0x7000) + ThumbBit.
MICROTASK_CALLBACK_BASE = 0x00200000
MICROTASK_FILE_BIAS = 0x7000
MICROTASK_SLOT_COUNT = 8
MICROTASK_SLOT_SIZE = 12
MICROTASK_PERIOD = 1
RESIDENT_TICK = 0x14F8
RESIDENT_DISPATCH = 0x15EC
RESIDENT_DISPATCH_BLX = 0x161E
RESIDENT_DISPATCH_PATTERN = bytes.fromhex(
    "f1b500240126104f0f4d08370f484078002814d0301c6978a04001400ad06978814369700c2060433958002902d0c019406888470134"
)
REGISTER_IMPL_PATTERN = bytes.fromhex(
    "b0b50024344d08350c236343eb58002b23d10c236343e8505819416002812d4d4281e87801210130"
)

MICROTASK_REGISTRATION = {
    "flag42_prod_v42016": {"call": 0x1FF24, "literal": 0x1FFF8},
    "flag42_test_v42017": {"call": 0x1FF18, "literal": 0x1FFEC},
    "flag60_prod_v60014": {"call": 0x1FF24, "literal": 0x1FFF8},
    "flag60_test_api60016_internal60017": {"call": 0x1FF24, "literal": 0x1FFF8},
}


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


def _microtask_callback_for_file_offset(worker: int) -> int:
    return MICROTASK_CALLBACK_BASE + (worker - MICROTASK_FILE_BIAS) + 1


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

    reg = MICROTASK_REGISTRATION[name]
    reg_call = reg["call"]
    reg_literal = reg["literal"]
    callback_value = struct.unpack_from("<I", b, reg_literal)[0]
    expected_callback = _microtask_callback_for_file_offset(worker)
    if callback_value != expected_callback:
        raise ValueError(f"{name}: VoiceTip microtask callback mapping drift {callback_value:#x} != {expected_callback:#x}")
    if b[reg_call - 6:reg_call - 2] != bytes.fromhex("01220021"):
        raise ValueError(f"{name}: VoiceTip microtask period/arg setup drift")
    reg_veneer = thumb_bl_target(b, reg_call)
    if reg_veneer is None or b[reg_veneer:reg_veneer + 2] != bytes.fromhex("80b5"):
        raise ValueError(f"{name}: Fwl_MicroTask veneer drift")
    reg_impl = thumb_bl_target(b, reg_veneer + 2)
    if reg_impl is None or b[reg_impl:reg_impl + len(REGISTER_IMPL_PATTERN)] != REGISTER_IMPL_PATTERN:
        raise ValueError(f"{name}: Fwl_MicroTask implementation drift")
    if b[RESIDENT_DISPATCH:RESIDENT_DISPATCH + len(RESIDENT_DISPATCH_PATTERN)] != RESIDENT_DISPATCH_PATTERN:
        raise ValueError(f"{name}: resident microtask dispatcher drift")

    # The worker is registered through the transformed 0x002xxxxx callback namespace,
    # so direct BL/raw 0x084xxxxx pointer searches are expected to remain empty.
    worker_bl = _direct_bl_xrefs(b, worker)
    worker_abs = _absolute_app_pointer_xrefs(b, worker)
    wrapper_bl = _direct_bl_xrefs(b, wrapper)
    wrapper_abs = _absolute_app_pointer_xrefs(b, wrapper)
    if worker_bl or worker_abs or wrapper_bl or wrapper_abs:
        raise ValueError(f"{name}: direct trigger-reference evidence changed")

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
        "microtask_registration_call": hex(reg_call),
        "microtask_registration_veneer": hex(reg_veneer),
        "microtask_registration_impl": hex(reg_impl),
        "microtask_callback_literal_offset": hex(reg_literal),
        "microtask_callback_value": hex(callback_value),
        "microtask_callback_decodes_to_worker": True,
        "microtask_period_ticks": MICROTASK_PERIOD,
        "microtask_argument": 0,
        "direct_bl_xrefs_to_worker": [],
        "raw_absolute_app_pointer_xrefs_to_worker": [],
        "direct_bl_xrefs_to_wrapper": [],
        "raw_absolute_app_pointer_xrefs_to_wrapper": [],
        "spp_a9_direct_targets_include_voicetip_trigger": False,
    }


def build_report() -> dict[str, Any]:
    branches = {name: _branch(name, spec) for name, spec in BRANCHES.items()}
    return {
        "schema_version": 2,
        "kind": "ditoo_plus_tier2_voicetip_trigger_gate",
        "ok": True,
        "branches": branches,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "live_packet_generation": False,
            "firmware_mutation": False,
            "persistent_mutation": False,
            "runtime_018_touched": False,
        },
        "control_sink": {
            "proven": True,
            "object_family": "VoiceTip/runtime50 0x50-byte object",
            "field_offset": "0x34",
            "semantics": "0x1fa8a-family loads object+0x34, checks nonzero, then BLXes the loaded value",
            "setter_semantics": "0x1fd6a-family copies its incoming r1 value into object+0x34 on the configured path",
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
        },
        "microtask_registration": {
            "proven": True,
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
            "callback_namespace": "callback_value = 0x00200000 + (worker_file_offset - 0x7000) + 1",
            "slot_count": MICROTASK_SLOT_COUNT,
            "slot_size_bytes": MICROTASK_SLOT_SIZE,
            "slot_layout": {"callback": "+0x0", "argument": "+0x4", "countdown": "+0x8:u16", "reload": "+0xa:u16"},
            "voicetip_registration": "VoiceTip registers its own 0x1fb42-family worker with argument 0 and period/reload 1, then resumes the returned microtask slot.",
            "resident_tick": hex(RESIDENT_TICK),
            "resident_dispatch": hex(RESIDENT_DISPATCH),
            "resident_dispatch_blx": hex(RESIDENT_DISPATCH_BLX),
            "resident_dispatch_semantics": "When a due slot is pending, resident code loads slot.callback and slot.argument and BLXes the callback with the argument in r0.",
        },
        "invocation_gate": {
            "in_image_invocation_sites_proven": True,
            "worker_registration_proven": True,
            "wrapper_registration_proven": False,
            "periodic_worker_dispatch_proven": True,
            "worker_reaches_callback_on_completion_or_idle_path": True,
            "deterministic_stock_post_overwrite_invocation_proven": False,
            "reason": "The periodic VoiceTip worker is now proven registered and dispatched. Its path to 0x1fa8a is conditional on normal VoiceTip completion/idle state; a stock command/state transition that guarantees that condition after the display overwrite has not yet been proven.",
        },
        "spp_trigger_checks": {
            "command_0x6c": {
                "direct_voicetip_trigger_edge_proven": False,
                "note": "0x6c is proven to reach the separate DIVOOM_LIGHT_WORD resident display handoff. It does not directly invoke VoiceTip; a second ordinary stock state transition may still provide the post-overwrite trigger.",
            },
            "command_0xa9_play_stop_voice": {
                "direct_voicetip_trigger_edge_proven": False,
                "note": "The explicit SPP play/stop-voice handler drives a separate recorded-voice state machine. Shared voice arbitration reaches VoiceTip teardown, but teardown does not itself BLX object+0x34.",
            },
        },
        "promotion": {
            "controlled_indirect_call_sink_exists": True,
            "voicetip_periodic_worker_registration": True,
            "deterministic_post_overwrite_callback_invocation": False,
            "remaining_trigger_blocker": "STOCK_VOICETIP_COMPLETION_STATE_TO_RUNTIME50_CALLBACK_UNPROVEN",
            "live_manifest_candidate": None,
        },
        "method_limits": [
            "This proves a real stock indirect-call sink plus deterministic periodic worker registration, not attacker-controlled placement or the final completion-state transition.",
            "The transformed 0x002xxxxx microtask callback namespace is supported by broad independent registration examples; it must not be confused with a second direct application code mapping.",
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
        print("TRIGGER_VOICETIP_MICROTASK_REGISTRATION=true")
        print("TRIGGER_PERIODIC_WORKER_DISPATCH=true")
        print("TRIGGER_DETERMINISTIC_COMPLETION_INVOCATION=false")
        print("TRIGGER_BLOCKER=STOCK_VOICETIP_COMPLETION_STATE_TO_RUNTIME50_CALLBACK_UNPROVEN")
        print("TRIGGER_LIVE_MANIFEST_CANDIDATE=NONE")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_TIER2_TRIGGER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
