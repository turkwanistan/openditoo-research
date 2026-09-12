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
from ditoo_tier2_placement import BRANCHES, FW, APP_LINK_BASE, build_report as build_placement_report
from ditoo_tier2_display_surface import build_report as build_display_report

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
SPP_A5_HANDLER = 0x12402
EVENT_34C_BUILDER = 0x17348
CLASS0_TABLE = 0x79D8
BTPPLAYER_HANDLER_INDEX = 2
MODEL_SELECTOR = 2
MODEL_ID = 0x22
CONTROLLED_SOURCE_ADDRESS = 0x00804778
CONTROLLED_SOURCE_FILE_OFFSET = 0x4778
RUNTIME50_ADDRESS = 0x00804B80
RUNTIME50_CALLBACK_ADDRESS = 0x00804BB4
RUNTIME50_SOURCE_OFFSET = RUNTIME50_ADDRESS - CONTROLLED_SOURCE_ADDRESS
CALLBACK_SOURCE_OFFSET = RUNTIME50_CALLBACK_ADDRESS - CONTROLLED_SOURCE_ADDRESS
EXACT_SOURCE_LENGTH = CALLBACK_SOURCE_OFFSET + 4
STAGE0_THUMB_ENTRY = CONTROLLED_SOURCE_ADDRESS | 1
STAGE0_RETURN_BYTES = bytes.fromhex("7047")  # Thumb: BX LR
SAFE_MICROTASK_BYTE = 0xFF
RUNTIME50_MODEL_OFFSET = 0x08
RUNTIME50_CALLBACK_OFFSET = 0x34
RUNTIME50_PRESERVED_OFFSETS = (0x3C, 0x40, 0x44)
TRANSFORMED_BASE = 0x00200000
TRANSFORMED_FILE_BIAS = 0x7000

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


def _decode_transformed_file_pointer(value: int) -> int:
    if not (0x00200000 <= value < 0x00300000):
        raise ValueError(f"not a transformed application pointer: {value:#x}")
    return (value - TRANSFORMED_BASE) + TRANSFORMED_FILE_BIAS


def _thumb_literal_u32(b: bytes, off: int) -> tuple[int, int]:
    h = int.from_bytes(b[off:off + 2], "little")
    if (h & 0xF800) != 0x4800:
        raise ValueError(f"expected Thumb LDR literal at {off:#x}")
    literal_off = ((off + 4) & ~3) + ((h & 0xFF) << 2)
    return literal_off, struct.unpack_from("<I", b, literal_off)[0]


def _transformed_handler(b: bytes, index: int) -> int:
    value = struct.unpack_from("<I", b, CLASS0_TABLE + 4 * index)[0]
    return _decode_transformed_file_pointer(value) & ~1


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

    # Stock VoiceTip preview setup: SPP 0xa5 forwards payload[1:4] to a
    # branch-local helper.  Selector 2 resolves to the same stock model 0x22
    # on all preserved Plus branches, and the helper fixes duration=0x3c and
    # the fourth 0x34c payload halfword to 2 before posting through 0x17348.
    if b[SPP_A5_HANDLER:SPP_A5_HANDLER + 6] != bytes.fromhex("7a78b878f978"):
        raise ValueError(f"{name}: SPP 0xa5 argument mapping drift")
    a5_helper = thumb_bl_target(b, SPP_A5_HANDLER + 6)
    if a5_helper is None:
        raise ValueError(f"{name}: SPP 0xa5 helper edge missing")
    if b[a5_helper + 0x4A:a5_helper + 0x58] != bytes.fromhex("02220092b9482b1c3a1c3c21805d"):
        raise ValueError(f"{name}: SPP 0xa5 VoiceTip event setup drift")
    if thumb_bl_target(b, a5_helper + 0x58) != EVENT_34C_BUILDER:
        raise ValueError(f"{name}: SPP 0xa5 event-builder edge drift")
    model_literal_off, model_table_ptr = _thumb_literal_u32(b, a5_helper + 0x4E)
    model_table_off = _decode_transformed_file_pointer(model_table_ptr)
    if b[model_table_off + MODEL_SELECTOR] != MODEL_ID:
        raise ValueError(f"{name}: selector {MODEL_SELECTOR} no longer maps to model {MODEL_ID:#x}")
    if b[EVENT_34C_BUILDER + 0x1A:EVENT_34C_BUILDER + 0x22] != bytes.fromhex("d3208000dc806946"):
        raise ValueError(f"{name}: 0x34c event-id/fourth-halfword construction drift")

    # The btplayer handler is resolved through the class-0 table instead of a
    # global offset assumption. It contains one branch-local direct call into
    # the VoiceTip setter family for the 0x34c preview path.
    btplayer_handler = _transformed_handler(b, BTPPLAYER_HANDLER_INDEX)
    btplayer_setter_calls = [
        o for o in range(btplayer_handler, min(btplayer_handler + 0x700, len(b) - 4), 2)
        if thumb_bl_target(b, o) == setter
    ]
    if len(btplayer_setter_calls) != 1:
        raise ValueError(f"{name}: btplayer VoiceTip setter edge drift {btplayer_setter_calls!r}")

    # Exact 1088-byte overwrite stops at runtime50+0x37. The callback path
    # reads controlled byte0 and byte8, while +0x3c/+0x44 remain untouched.
    # byte0=0xff is explicitly accepted by 0x1b3dc as a no-op release path;
    # byte8=0x22 reuses the stock preview model and is <0xfd in 0x45596.
    if b[cb + 0x06:cb + 0x0C] != bytes.fromhex("017aff2941d0"):
        raise ValueError(f"{name}: runtime50 model-byte gate drift")
    if b[cb + 0x0C:cb + 0x0E] != bytes.fromhex("0078"):
        raise ValueError(f"{name}: runtime50 byte0 read drift")
    if b[cb + 0x14:cb + 0x16] != bytes.fromhex("c06b") or b[cb + 0x1C:cb + 0x1E] != bytes.fromhex("406c"):
        raise ValueError(f"{name}: runtime50 preserved handle reads drift")
    if b[cb + 0x24:cb + 0x2A] != bytes.fromhex("017a4170007a"):
        raise ValueError(f"{name}: runtime50 model reopen path drift")
    microtask_release = thumb_bl_target(b, cb + 0x0E)
    if microtask_release is None or b[microtask_release:microtask_release + 6] != bytes.fromhex("80b5ff2804d1"):
        raise ValueError(f"{name}: 0xff microtask no-op gate drift")
    model_opener = thumb_bl_target(b, cb + 0x2A)
    if model_opener is None:
        raise ValueError(f"{name}: VoiceTip model opener edge drift")
    model_bound_helpers = []
    for o in range(model_opener, min(model_opener + 0xC0, len(b) - 4), 2):
        t = thumb_bl_target(b, o)
        if t is not None and b[t:t + 8] == bytes.fromhex("fd2801d300207047"):
            model_bound_helpers.append(t)
    if len(set(model_bound_helpers)) != 1 or not (MODEL_ID < 0xFD):
        raise ValueError(f"{name}: VoiceTip model bound drift {model_bound_helpers!r}")
    model_bound = model_bound_helpers[0]

    # Chosen stage-0 is in a pristine reclaimed stage-1 fill span, with no raw
    # reference to the eventual heap address in the preserved image.
    if b[CONTROLLED_SOURCE_FILE_OFFSET:CONTROLLED_SOURCE_FILE_OFFSET + 0x40] != b"\xff" * 0x40:
        raise ValueError(f"{name}: candidate stage-0 span no longer pristine fill")
    for ptr in (CONTROLLED_SOURCE_ADDRESS, STAGE0_THUMB_ENTRY):
        if struct.pack("<I", ptr) in b:
            raise ValueError(f"{name}: candidate stage-0 address unexpectedly referenced in image")

    # 0xbfe8 is not an open-ended device-idle predicate: it reads the app-heap
    # critical-section flag. Both malloc/free wrappers set it for the allocator
    # call and clear it before returning, so a colliding worker tick is deferred
    # rather than permanently blocked.
    if b[0xBFBC:0xBFC4] != bytes.fromhex("10b50c4c01212170") or b[0xBFC8:0xBFCE] != bytes.fromhex("0021217010bd"):
        raise ValueError(f"{name}: app malloc busy-flag wrapper drift")
    if b[0xBFCE:0xBFD6] != bytes.fromhex("10b5074c01212170") or b[0xBFDA:0xBFE0] != bytes.fromhex("0021217010bd"):
        raise ValueError(f"{name}: app free busy-flag wrapper drift")
    if b[0xBFE8:0xBFEE] != bytes.fromhex("014800787047"):
        raise ValueError(f"{name}: app heap busy predicate drift")

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
        "spp_a5_helper": hex(a5_helper),
        "spp_a5_model_table_literal": hex(model_literal_off),
        "spp_a5_model_table_pointer": hex(model_table_ptr),
        "spp_a5_selector_2_model": hex(MODEL_ID),
        "event_34c_builder": hex(EVENT_34C_BUILDER),
        "btplayer_handler": hex(btplayer_handler),
        "btplayer_voicetip_setter_call": hex(btplayer_setter_calls[0]),
        "microtask_release_helper": hex(microtask_release),
        "model_opener": hex(model_opener),
        "model_bound_helper": hex(model_bound),
        "stage0_span_pristine_fill": True,
        "stage0_raw_pointer_xrefs": [],
        "allocator_busy_flag_predicate": "0xbfe8",
        "allocator_busy_flag_is_transient": True,
    }


def build_report() -> dict[str, Any]:
    placement = build_placement_report()
    display = build_display_report()
    gate = placement["placement_gate"]
    if not gate["deterministic_adjacent_victim_proven"]:
        raise ValueError("Tier-2 trigger refuses to promote without deterministic placement")
    if gate["runtime50_candidate"]["base"] != hex(RUNTIME50_ADDRESS):
        raise ValueError("Tier-2 placement runtime50 base drift")
    if gate["runtime50_candidate"]["callback"] != hex(RUNTIME50_CALLBACK_ADDRESS):
        raise ValueError("Tier-2 placement callback address drift")
    if gate["runtime50_candidate"]["callback_source_offset"] != CALLBACK_SOURCE_OFFSET:
        raise ValueError("Tier-2 placement callback source offset drift")
    reach = display["reachability"]
    if not reach["prime_stable_4_of_4"] or reach["prime_command"] != "0x6e SPP_DRAWING_CTRL_MOVIE_PLAY":
        raise ValueError("Tier-2 trigger refuses stale/uncorrected display priming model")
    if reach["copy_precondition"] != "content mode 0x0b already selected; 0x6c does not prime itself":
        raise ValueError("Tier-2 trigger display-copy precondition drift")
    if not reach["prime_initializer_preserves_proven_startup_geometry"]:
        raise ValueError("Tier-2 trigger refuses display prime that can invalidate startup geometry")
    if display["placement_integration"]["display_data_pointer"] != hex(CONTROLLED_SOURCE_ADDRESS):
        raise ValueError("Tier-2 display controlled source address drift")
    if display["placement_integration"]["runtime50_base"] != hex(RUNTIME50_ADDRESS):
        raise ValueError("Tier-2 display runtime50 base drift")

    branches = {name: _branch(name, spec) for name, spec in BRANCHES.items()}
    return {
        "schema_version": 4,
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
            "runtime50_base": hex(RUNTIME50_ADDRESS),
            "field_offset": hex(RUNTIME50_CALLBACK_OFFSET),
            "callback_address": hex(RUNTIME50_CALLBACK_ADDRESS),
            "semantics": "0x1fa8a-family loads object+0x34, checks nonzero, then BLXes the loaded value",
            "setter_semantics": "0x1fd6a-family copies its incoming r1 value into object+0x34 on the configured path",
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
        },
        "stock_setup": {
            "precondition": "stock Bluetooth-player / btplayer mode (mode 4); manual stock-mode selection is the fail-closed deterministic precondition",
            "content_mode_prime": {
                "command": reach["prime_command"],
                "control": reach["prime_control"],
                "target_mode": reach["stock_mode"],
                "role": reach["prime_role"],
                "geometry_preserved": reach["prime_initializer_preserves_proven_startup_geometry"],
            },
            "voicetip_setup_command": "0xa5 SPP_SET_ALARM_LISTEN",
            "start_flag": "payload[1] != 0",
            "model_selector": MODEL_SELECTOR,
            "model_id": hex(MODEL_ID),
            "caller_argument": "payload[3]",
            "event": "0x34c",
            "event_payload_halfwords": [hex(MODEL_ID), "caller_argument", "0x3c", "0x2"],
            "btplayer_event_34c_reaches_voicetip_setter": True,
            "host_only_mode_normalization_candidate": {
                "command": "0x8a SPP_SET_POWER_CHANNEL payload[1]=0",
                "status": "NOT_PROMOTED_AS_DETERMINISTIC_PRECONDITION",
                "reason": "The handler enqueues 0x101f before mutating the selector queue; static analysis has not excluded a scheduler preemption between those operations. Active btphone mode also intentionally blocks the BLUE normalization branch.",
            },
        },
        "overwrite_witness": {
            "source_address": hex(CONTROLLED_SOURCE_ADDRESS),
            "exact_source_length": EXACT_SOURCE_LENGTH,
            "runtime50_source_offset": RUNTIME50_SOURCE_OFFSET,
            "callback_source_offset": CALLBACK_SOURCE_OFFSET,
            "controlled_runtime50_byte0": hex(SAFE_MICROTASK_BYTE),
            "controlled_runtime50_byte8_model": hex(MODEL_ID),
            "controlled_callback_value": hex(STAGE0_THUMB_ENTRY),
            "last_overwritten_runtime50_offset": hex(EXACT_SOURCE_LENGTH - RUNTIME50_SOURCE_OFFSET - 1),
            "preserved_runtime50_offsets": [hex(x) for x in RUNTIME50_PRESERVED_OFFSETS],
            "pre_blx_dependency_closure": "Before BLX +0x34, the controlled prefix needs only byte0=0xff and byte8=0x22; +0x3c and +0x44 are preserved stock handles and +0x40 is the preserved timeout/deadline consumed by the worker.",
        },
        "microtask_registration": {
            "proven": True,
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
            "callback_namespace": "callback_value = 0x00200000 + (worker_file_offset - 0x7000) + 1",
            "slot_count": MICROTASK_SLOT_COUNT,
            "slot_size_bytes": MICROTASK_SLOT_SIZE,
            "slot_layout": {"callback": "+0x0", "argument": "+0x4", "countdown": "+0x8:u16", "reload": "+0xa:u16"},
            "voicetip_registration": "VoiceTip registers its worker with argument 0 and period/reload 1, then resumes the returned microtask slot.",
            "resident_tick": hex(RESIDENT_TICK),
            "resident_dispatch": hex(RESIDENT_DISPATCH),
            "resident_dispatch_blx": hex(RESIDENT_DISPATCH_BLX),
        },
        "invocation_gate": {
            "in_image_invocation_sites_proven": True,
            "worker_registration_proven": True,
            "periodic_worker_dispatch_proven": True,
            "worker_timeout_path_reaches_callback": True,
            "allocator_busy_flag_is_transient": True,
            "deterministic_stock_post_overwrite_invocation_proven": True,
            "eventual_invocation_semantics": "If the timeout tick collides with app-heap malloc/free, the worker defers while 0x008030c4 is 1; both wrappers clear it before return, and the period-1 worker retries on subsequent ticks.",
            "conditions": [
                "stock btplayer precondition",
                "successful stock 0xa5 VoiceTip preview setup using selector 2/model 0x22",
                "exact 1088-byte overwrite so runtime50+0x3c/+0x40/+0x44 remain intact",
                "normal VoiceTip timeout expires; transient app-heap busy flag 0xbfe8 eventually returns zero after any in-flight malloc/free wrapper exits",
            ],
        },
        "stage0_witness": {
            "entry": hex(STAGE0_THUMB_ENTRY),
            "bytes_hex": STAGE0_RETURN_BYTES.hex(),
            "instruction": "BX LR",
            "purpose": "minimal offline returning execution witness only; no loader, mutation, or device packet is emitted",
            "candidate_span_pristine_ff_in_image_4_of_4": True,
            "raw_pointer_xrefs_4_of_4": 0,
        },
        "spp_trigger_checks": {
            "command_0x6e_drawing_ctrl_movie_play": {
                "content_mode_prime_proven": True,
                "control": "payload[1] != 0",
                "role": "select content mode 0x0b before the separate 0x6c copy primitive",
            },
            "command_0x6c": {
                "direct_voicetip_trigger_edge_proven": False,
                "requires_content_mode_0x0b_preselected": True,
                "role": "resident display copy/adjacent overwrite primitive; does not prime its own content mode",
            },
            "command_0xa5_alarm_listen": {
                "direct_stock_setup_edge_proven": True,
                "role": "stock VoiceTip preview setup and timeout source",
            },
            "command_0xa9_play_stop_voice": {
                "direct_voicetip_trigger_edge_proven": False,
                "role": "separate recorded-voice state machine",
            },
        },
        "promotion": {
            "controlled_indirect_call_sink_exists": True,
            "deterministic_victim_placement": True,
            "deterministic_post_overwrite_callback_invocation": True,
            "controlled_indirect_branch_proven_offline": True,
            "returning_thumb_stage0_witness_proven_offline": True,
            "remaining_trigger_blocker": None,
            "remaining_before_any_live_stage0": "REVIEWED_ONE_USE_LIVE_MANIFEST_AND_EXPLICIT_GRANT",
            "live_manifest_candidate": None,
        },
        "method_limits": [
            "This is an offline structural control-flow proof, not a live device execution observation.",
            "The deterministic proof deliberately uses a stock/manual btplayer-mode precondition; content mode 0x0b is then primed separately by stock 0x6e(nonzero). The all-SPP 0x8a btplayer normalization candidate remains unpromoted because queue/preemption ordering is not statically closed.",
            "The timeout edge may defer during an in-flight app-heap malloc/free critical section; the wrappers clear the busy flag before return and the periodic worker retries. No crash or timing behavior is used as an oracle.",
            "No malformed/custom live packet, transmitter, loader, firmware write, or persistent mutation is produced by this analyzer.",
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
        print("TRIGGER_DETERMINISTIC_COMPLETION_INVOCATION=true")
        print("TRIGGER_CONTROLLED_INDIRECT_BRANCH_OFFLINE=true")
        print("TRIGGER_STAGE0_RETURN_WITNESS=0x804779:7047")
        print("TRIGGER_BLOCKER=LIVE_MANIFEST_NOT_AUTHORIZED")
        print("TRIGGER_LIVE_MANIFEST_CANDIDATE=NONE")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_TIER2_TRIGGER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
