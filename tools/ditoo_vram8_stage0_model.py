#!/usr/bin/env python3
"""Fail-closed offline VRAM-8A callback-ABI and positive-canary model.

This tool reads only the pinned Ditoo Plus firmware corpus and previously promoted
VRAM artifacts.  It does not open Bluetooth, generate a live transport sequence,
touch Runtime 018, mutate firmware, or create execution authority.

VRAM-8A answers one bounded question: can a nontrivial Thumb leaf entered through
the already-proven runtime50 +0x34 BLX mutate one reversible volatile RAM byte,
return cleanly, and expose that byte through an already-typed stock query?
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from ditoo_tier2_placement import BRANCHES, FW
from keypad_pipeline_report import thumb_bl_target

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/analysis/volatile_ram_api_vram8_stage0.json"
FIXTURE = ROOT / "artifacts/analysis/volatile_ram_api_vram8_stage0.bin"

APP_LINK_BASE = 0x08400000
RESIDENT_BASE = 0x00800000
CONTROLLED_SOURCE = 0x00804778
RUNTIME50_BASE = 0x00804B80
RUNTIME50_CALLBACK = RUNTIME50_BASE + 0x34
CALLBACK_SOURCE_OFFSET = RUNTIME50_CALLBACK - CONTROLLED_SOURCE
EXACT_SOURCE_LENGTH = CALLBACK_SOURCE_OFFSET + 4

# VRAM67-002 already executed at 0x00804779.  VRAM-8A deliberately uses a
# different, 0x100-aligned, previously unreferenced first-execution span inside
# the same proven controlled display-copy allocation rather than rewriting the
# old I-cache line.  This is NOT a general cache-maintenance substitute.
STAGE0_SOURCE = 0x00804900
STAGE0_ENTRY = STAGE0_SOURCE | 1
STAGE0_SOURCE_OFFSET = STAGE0_SOURCE - CONTROLLED_SOURCE
FRESH_SPAN_BYTES = 0x40

# Shared stock state object root used by SET/GET_ENERGY_CTRL in all four branches.
# The literal is a struct/global at 0x008030f0; +4 holds the live object pointer.
STATE_GLOBAL = 0x008030F0
STATE_OBJECT_POINTER_CELL = STATE_GLOBAL + 4
ENERGY_FIELD_OFFSET = 0x0F
ENERGY_SET_HELPER = 0x14D92
ENERGY_GET_HELPER = 0x14DA2
ENERGY_SET_HANDLER = 0x126BC
ENERGY_GET_HANDLER = 0x126CC

# Exact 20-byte Thumb-1 stage-0.  Data literal at +0x10 is not executed.
#   push {r4,lr}
#   ldr  r4,[pc,#0x0c]     ; -> 0x008030f0 literal
#   ldr  r4,[r4,#4]        ; live stock state-object pointer
#   ldrb r2,[r4,#0x0f]
#   movs r3,#1
#   eors r2,r3             ; baseline 0 -> positive canary 1
#   strb r2,[r4,#0x0f]
#   pop  {r4,pc}
#   .word 0x008030f0
STAGE0_BYTES = bytes.fromhex("10b5034c6468e27b01235a40e27310bdf0308000")
STAGE0_CODE_BYTES = 16
STAGE0_LITERAL_OFFSET = 16
STAGE0_DISASSEMBLY = [
    {"offset": "0x00", "bytes": "10b5", "instruction": "PUSH {r4, LR}"},
    {"offset": "0x02", "bytes": "034c", "instruction": "LDR r4, [PC, #0x0c]"},
    {"offset": "0x04", "bytes": "6468", "instruction": "LDR r4, [r4, #4]"},
    {"offset": "0x06", "bytes": "e27b", "instruction": "LDRB r2, [r4, #0x0f]"},
    {"offset": "0x08", "bytes": "0123", "instruction": "MOVS r3, #1"},
    {"offset": "0x0a", "bytes": "5a40", "instruction": "EORS r2, r3"},
    {"offset": "0x0c", "bytes": "e273", "instruction": "STRB r2, [r4, #0x0f]"},
    {"offset": "0x0e", "bytes": "10bd", "instruction": "POP {r4, PC}"},
    {"offset": "0x10", "bytes": "f0308000", "instruction": ".word 0x008030f0"},
]

# Byte-level ABI pins from the already-promoted callback family.
CALLBACK_PROLOGUE = bytes.fromhex("10b5")                    # push {r4,lr}
CALLBACK_BLX_REGION = bytes.fromhex("486b002801d0486b8047")   # +0x32..+0x3b
CALLBACK_POST_BLX = bytes.fromhex("2068c169")                # reload r0, then r1
WORKER_PROLOGUE = bytes.fromhex("feb5")                      # push 8 regs = 32 bytes
WRAPPER_PROLOGUE = bytes.fromhex("80b5")                     # push {r7,lr} = 8 bytes
DISPATCH_PROLOGUE = bytes.fromhex("f1b5")                    # push 6 regs = 24 bytes

# Stock typed canary path.  BL logging targets vary in one official-test branch,
# so pin the dataflow before/after that call rather than its encoding.
ENERGY_SET_PREFIX = bytes.fromhex("10b5041c00f0b5ff61484068c473")
ENERGY_GET_PREFIX = bytes.fromhex("10b55e4c6068c17b75a00a1c")
ENERGY_GET_SUFFIX = bytes.fromhex("6068c07b10bd")
ENERGY_QUERY_HANDLER_PREFIX = bytes.fromhex("02f069fb20ab187068690127b32120aa3b1c")
STATE_GLOBAL_LITERAL_OFFSET = 0x14F20

# The fixed pre/post live canary values are chosen only for a future separately
# granted VRAM-8B manifest: stock SET_ENERGY_CTRL 0 establishes the baseline;
# stage-0 changes exactly that byte to 1; stock GET_ENERGY_CTRL returns exactly
# one raw byte; stock SET_ENERGY_CTRL 0 can restore it.
CANARY_BASELINE = 0
CANARY_EXPECTED = 1
CANARY_XOR_MASK = 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_branch(name: str, spec: dict[str, Any]) -> bytes:
    data = (FW / spec["file"]).read_bytes()
    if len(data) != spec["size"] or _sha(data) != spec["sha"]:
        raise ValueError(f"{name}: firmware corpus identity drift")
    return data


def _find_all(data: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            return out
        out.append(pos)
        pos += 1


def _direct_bl_xrefs(data: bytes, target: int) -> list[int]:
    return [off for off in range(0, len(data) - 3, 2) if thumb_bl_target(data, off) == target]


def _literal_value(data: bytes, instruction_off: int) -> int | None:
    """Decode a Thumb-1 LDR literal and return its 32-bit literal value."""
    h = int.from_bytes(data[instruction_off:instruction_off + 2], "little")
    if h & 0xF800 != 0x4800:
        return None
    imm = (h & 0xFF) * 4
    va = APP_LINK_BASE + instruction_off
    literal_va = ((va + 4) & ~3) + imm
    literal_off = literal_va - APP_LINK_BASE
    if not (0 <= literal_off <= len(data) - 4):
        return None
    return int.from_bytes(data[literal_off:literal_off + 4], "little")


def _canonical_energy_field_writers(data: bytes) -> list[int]:
    """Find direct STATE_GLOBAL -> [global+4] -> STRB +0x0f writers.

    This intentionally recognizes only the exact simple Thumb-1 dataflow used by
    the stock energy-control setter.  If another path aliases/modifies the object
    register before the store, it is not falsely promoted as the same field.
    """
    writers: list[int] = []
    for off in range(0, len(data) - 24, 2):
        h = int.from_bytes(data[off:off + 2], "little")
        if h & 0xF800 != 0x4800 or _literal_value(data, off) != STATE_GLOBAL:
            continue
        global_reg = (h >> 8) & 7
        object_reg: int | None = None
        object_reg_invalidated = False
        for p in range(off + 2, off + 18, 2):
            q = int.from_bytes(data[p:p + 2], "little")
            top = q & 0xF800
            # LDR Rt,[Rn,#imm*4]
            if top == 0x6800:
                imm5 = (q >> 6) & 0x1F
                rn = (q >> 3) & 7
                rt = q & 7
                if rn == global_reg and imm5 == 1:
                    object_reg = rt
                    object_reg_invalidated = False
                    continue
                if object_reg is not None and rt == object_reg:
                    object_reg_invalidated = True
            # ADD/SUB immediate on a low register invalidates the direct object alias.
            if q & 0xF800 in (0x3000, 0x3800):
                rd = (q >> 8) & 7
                if object_reg is not None and rd == object_reg:
                    object_reg_invalidated = True
            # STRB Rt,[Rn,#imm5]
            if top == 0x7000 and object_reg is not None and not object_reg_invalidated:
                imm5 = (q >> 6) & 0x1F
                rn = (q >> 3) & 7
                if rn == object_reg and imm5 == ENERGY_FIELD_OFFSET:
                    writers.append(p)
                    break
    return sorted(set(writers))


def _branch_report(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    data = _load_branch(name, spec)
    runtime50_constructor = spec["runtime50"]
    callback = runtime50_constructor + 0x96
    worker = runtime50_constructor + 0x14E
    wrapper = runtime50_constructor + 0x578

    if data[callback:callback + 2] != CALLBACK_PROLOGUE:
        raise ValueError(f"{name}: callback prologue drift")
    if data[callback + 0x32:callback + 0x3C] != CALLBACK_BLX_REGION:
        raise ValueError(f"{name}: callback BLX ABI region drift")
    if data[callback + 0x3C:callback + 0x40] != CALLBACK_POST_BLX:
        raise ValueError(f"{name}: callback post-BLX return-value consumer drift")
    if data[worker:worker + 2] != WORKER_PROLOGUE:
        raise ValueError(f"{name}: worker stack frame drift")
    if data[wrapper:wrapper + 2] != WRAPPER_PROLOGUE:
        raise ValueError(f"{name}: wrapper stack frame drift")
    if data[0x15EC:0x15EE] != DISPATCH_PROLOGUE:
        raise ValueError(f"{name}: periodic dispatcher stack frame drift")

    fresh_off = STAGE0_SOURCE - RESIDENT_BASE
    if data[fresh_off:fresh_off + FRESH_SPAN_BYTES] != b"\xff" * FRESH_SPAN_BYTES:
        raise ValueError(f"{name}: VRAM-8A fresh stage-0 span no longer pristine")
    raw_source_refs = _find_all(data, struct.pack("<I", STAGE0_SOURCE))
    raw_entry_refs = _find_all(data, struct.pack("<I", STAGE0_ENTRY))
    if raw_source_refs or raw_entry_refs:
        raise ValueError(f"{name}: VRAM-8A fresh stage-0 span unexpectedly referenced")

    if data[ENERGY_SET_HELPER:ENERGY_SET_HELPER + len(ENERGY_SET_PREFIX)] != ENERGY_SET_PREFIX:
        raise ValueError(f"{name}: energy setter dataflow drift")
    if data[ENERGY_GET_HELPER:ENERGY_GET_HELPER + len(ENERGY_GET_PREFIX)] != ENERGY_GET_PREFIX:
        raise ValueError(f"{name}: energy getter prefix drift")
    if data[ENERGY_GET_HELPER + 0x10:ENERGY_GET_HELPER + 0x10 + len(ENERGY_GET_SUFFIX)] != ENERGY_GET_SUFFIX:
        raise ValueError(f"{name}: energy getter return dataflow drift")
    if data[ENERGY_GET_HANDLER:ENERGY_GET_HANDLER + len(ENERGY_QUERY_HANDLER_PREFIX)] != ENERGY_QUERY_HANDLER_PREFIX:
        raise ValueError(f"{name}: SPP_GET_ENERGY_CTRL response path drift")
    if int.from_bytes(data[STATE_GLOBAL_LITERAL_OFFSET:STATE_GLOBAL_LITERAL_OFFSET + 4], "little") != STATE_GLOBAL:
        raise ValueError(f"{name}: energy state-global literal drift")
    if data[ENERGY_SET_HANDLER:ENERGY_SET_HANDLER + 2] != bytes.fromhex("7878"):
        raise ValueError(f"{name}: SPP_SET_ENERGY_CTRL input byte load drift")
    if thumb_bl_target(data, ENERGY_SET_HANDLER + 2) != ENERGY_SET_HELPER:
        raise ValueError(f"{name}: SPP_SET_ENERGY_CTRL helper target drift")
    if thumb_bl_target(data, ENERGY_GET_HANDLER) != ENERGY_GET_HELPER:
        raise ValueError(f"{name}: SPP_GET_ENERGY_CTRL helper target drift")

    setter_xrefs = _direct_bl_xrefs(data, ENERGY_SET_HELPER)
    getter_xrefs = _direct_bl_xrefs(data, ENERGY_GET_HELPER)
    field_writers = _canonical_energy_field_writers(data)
    if setter_xrefs != [ENERGY_SET_HANDLER + 2]:
        raise ValueError(f"{name}: energy setter direct-call xrefs drift: {setter_xrefs}")
    if getter_xrefs != [ENERGY_GET_HANDLER]:
        raise ValueError(f"{name}: energy getter direct-call xrefs drift: {getter_xrefs}")
    if field_writers != [ENERGY_SET_HELPER + 0x0C]:
        raise ValueError(f"{name}: canonical energy-field writer set drift: {field_writers}")

    return {
        "callback_function": hex(callback),
        "callback_blx": hex(callback + 0x3A),
        "worker": hex(worker),
        "wrapper": hex(wrapper),
        "stack_frame_deltas_bytes": {
            "periodic_dispatcher": -24,
            "worker": -32,
            "callback_function": -8,
            "wrapper": -8,
        },
        "fresh_stage0_file_offset": hex(fresh_off),
        "fresh_stage0_span_pristine_ff": True,
        "fresh_stage0_raw_source_pointer_xrefs": [],
        "fresh_stage0_raw_thumb_entry_xrefs": [],
        "energy_state_global": hex(STATE_GLOBAL),
        "energy_state_object_pointer_cell": hex(STATE_OBJECT_POINTER_CELL),
        "energy_field_offset": hex(ENERGY_FIELD_OFFSET),
        "energy_set_helper": hex(ENERGY_SET_HELPER),
        "energy_get_helper": hex(ENERGY_GET_HELPER),
        "energy_set_direct_bl_xrefs": [hex(x) for x in setter_xrefs],
        "energy_get_direct_bl_xrefs": [hex(x) for x in getter_xrefs],
        "canonical_energy_field_writers": [hex(x) for x in field_writers],
        "typed_query_returns_raw_one_byte": True,
    }


def build_report() -> dict[str, Any]:
    branches = {name: _branch_report(name, spec) for name, spec in BRANCHES.items()}
    if len(STAGE0_BYTES) != 20 or STAGE0_BYTES[STAGE0_LITERAL_OFFSET:] != STATE_GLOBAL.to_bytes(4, "little"):
        raise ValueError("stage-0 fixture literal/length drift")
    if STAGE0_SOURCE_OFFSET < 0 or STAGE0_SOURCE_OFFSET + len(STAGE0_BYTES) > (RUNTIME50_BASE - CONTROLLED_SOURCE):
        raise ValueError("stage-0 no longer fits wholly inside controlled display backing")
    if STAGE0_SOURCE % 0x100 != 0:
        raise ValueError("stage-0 first-execution span lost conservative alignment")

    return {
        "schema_version": 1,
        "kind": "ditoo_plus_vram8a_nontrivial_returning_stage0",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "bluetooth_opened": False,
            "live_packet_generation": False,
            "runtime_018_touched": False,
            "firmware_mutation": False,
            "persistent_mutation": False,
            "flash_or_peripheral_access": False,
            "generic_loader_or_raw_call_surface": False,
        },
        "branches": branches,
        "callback_abi": {
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
            "entry_registers": {
                "r0": "runtime50+0x34 callback value itself; for VRAM-8A 0x00804901",
                "r1": "runtime50 base 0x00804b80",
                "r2": "unspecified/caller-saved; stage-0 must not depend on entry value",
                "r3": "unspecified/caller-saved; stage-0 must not depend on entry value",
                "r4_r11": "callee-saved under stock Thumb ABI; preserve any register touched",
                "lr": "Thumb return address written by BLX; bit0 set for return to callback+0x3c",
            },
            "return_value_semantics": "ignored: stock immediately reloads r0 from [r4] after BLX",
            "condition_flags": "caller-clobbered; stock post-BLX path does not consume callback flags",
            "thumb_state": "callback pointer bit0=1; BLX enters Thumb and saved LR returns to Thumb",
            "stack": {
                "relative_alignment": "periodic dispatcher (-24), worker (-32), callback (-8), wrapper (-8) all preserve SP mod 8",
                "stage0_delta": "PUSH {r4,lr} is -8; POP {r4,pc} restores exact SP",
                "nested_call_requirement": "none; VRAM-8A stage-0 is a leaf and makes no stock/helper call",
            },
            "interrupt_preemption_constraint": {
                "non_interrupt_task_context_proven": False,
                "rule": "Until task/IRQ context is independently closed, stage-0 must be a bounded leaf: no allocator, locks, waits, stock helper calls, MMIO, cache helper calls, or interrupt-state changes.",
                "vram8a_fixture_complies": True,
            },
        },
        "stage0": {
            "source": hex(STAGE0_SOURCE),
            "entry": hex(STAGE0_ENTRY),
            "controlled_source_base": hex(CONTROLLED_SOURCE),
            "source_offset": hex(STAGE0_SOURCE_OFFSET),
            "length_bytes": len(STAGE0_BYTES),
            "code_bytes": STAGE0_CODE_BYTES,
            "bytes_hex": STAGE0_BYTES.hex(),
            "sha256": _sha(STAGE0_BYTES),
            "disassembly": STAGE0_DISASSEMBLY,
            "instructions_executed": 8,
            "branches_or_loops": 0,
            "stock_calls": 0,
            "stack_net_delta": 0,
            "callee_saved_registers_touched": ["r4"],
            "callee_saved_registers_restored": ["r4"],
            "caller_saved_registers_touched": ["r2", "r3"],
            "fresh_first_execution_span": {
                "alignment_bytes": 0x100,
                "checked_bytes": FRESH_SPAN_BYTES,
                "pristine_ff_4_of_4": True,
                "raw_source_pointer_xrefs_4_of_4": 0,
                "raw_thumb_entry_xrefs_4_of_4": 0,
                "reason": "VRAM67-002 used 0x00804779; VRAM-8A intentionally relocates 0x188 bytes away to an unreferenced pristine span instead of rewriting the previously executed location.",
                "scope_limit": "This preserves the first-execution cache premise only for this fixture. Resident/reused code still requires explicit I-cache maintenance before execution.",
            },
            "touched_addresses": {
                "reads": [
                    {"address": hex(STATE_OBJECT_POINTER_CELL), "width": 4, "meaning": "stock live state-object pointer"},
                    {"address": "*(u32*)0x008030f4 + 0x0f", "width": 1, "meaning": "stock energy-control byte"},
                    {"address": "SP-8..SP-1", "width": 8, "meaning": "temporary saved r4/LR stack frame"},
                ],
                "writes": [
                    {"address": "*(u32*)0x008030f4 + 0x0f", "width": 1, "meaning": "energy-control canary byte only"},
                    {"address": "SP-8..SP-1", "width": 8, "meaning": "temporary saved r4/LR, restored by epilogue"},
                ],
                "no_other_data_writes": True,
            },
        },
        "positive_canary": {
            "status": "PROMOTED_OFFLINE",
            "mechanism": "typed stock volatile control byte readback",
            "stock_commands": {
                "set": "0xb2 SPP_SET_ENERGY_CTRL",
                "get": "0xb3 SPP_GET_ENERGY_CTRL",
            },
            "backing": {
                "state_global": hex(STATE_GLOBAL),
                "object_pointer_cell": hex(STATE_OBJECT_POINTER_CELL),
                "field": "*(u32*)0x008030f4 + 0x0f",
                "width_bytes": 1,
            },
            "precommitted_transform": {
                "baseline": CANARY_BASELINE,
                "operation": "XOR bit0",
                "mask": CANARY_XOR_MASK,
                "expected_after_stage0": CANARY_EXPECTED,
            },
            "typed_observation": "SPP_GET_ENERGY_CTRL calls 0x14da2, returns the raw +0x0f byte in r0, copies that byte into a one-byte command-0xb3 response, and has no alternate direct getter callsite.",
            "writer_uniqueness": "Across the pinned corpus, the canonical direct STATE_GLOBAL -> [global+4] -> STRB +0x0f writer is only 0x14d9e inside 0x14d92, and that setter has exactly one direct BL xref: the stock 0xb2 handler.",
            "future_live_discriminator": [
                "stock SET_ENERGY_CTRL 0 establishes a fixed benign baseline",
                "stock GET_ENERGY_CTRL must confirm raw value 0 before trigger",
                "the exact VRAM-8A stage-0 executes after the already-promoted VoiceTip timeout and changes only that byte 0 -> 1",
                "stock GET_ENERGY_CTRL returning raw value 1 is the positive execution marker",
                "normal callback return/liveness must also remain intact",
                "stock SET_ENERGY_CTRL 0 followed by GET=0 is the bounded restoration check",
            ],
            "invalid_oracles": ["crash", "reboot", "disconnect", "watchdog", "timeout", "timing-only change", "peripheral register effect"],
        },
        "resident_window_vram8c": {
            "status": "DESIGN_ADVANCED_NOT_CLOSED",
            "ranked_candidates": [
                {
                    "rank": 1,
                    "candidate": "one deliberate retained app-heap allocation owned by OpenDitoo for the boot session",
                    "verdict": "PREFERRED_PENDING_CONTEXT_AND_ALLOCATOR_ABI",
                    "reason": "avoids hardcoding allocator-owned free RAM and permits guards/state/code to live in one bounded object",
                },
                {
                    "rank": 2,
                    "candidate": "hardcoded free-looking address inside 0x00804000..0x0081cfff",
                    "verdict": "REJECT",
                    "reason": "application heap is allocator-owned; free-looking is not reserved/stable",
                },
                {
                    "rank": 3,
                    "candidate": "0x00804778 display backing / VRAM-8A controlled span",
                    "verdict": "REJECT_RESIDENT",
                    "reason": "live display backing and overwrite carrier; not a stable resident store",
                },
                {
                    "rank": 4,
                    "candidate": "0x00804b80 runtime50 or adjacent live startup objects",
                    "verdict": "REJECT",
                    "reason": "live stock object/metadata with proven callback/deadline/handle semantics",
                },
                {
                    "rank": 5,
                    "candidate": "upper identity-mapped SRAM outside the app heap",
                    "verdict": "REJECT_UNPROVEN",
                    "reason": "no reservation proof; may be stack/other resident runtime storage",
                },
            ],
            "current_blockers": [
                "callback task-vs-interrupt context is not yet proven; allocator calls are forbidden from the VRAM-8A leaf",
                "exact allocator-call ABI/reentrancy contract for a retained allocation is not yet promoted for this callback context",
                "compiled stage-1 size does not exist yet, so a maximum image length must not be guessed",
            ],
            "bounded_installer_contract": {
                "destination": "device-side retained-allocation result only; host never supplies an address",
                "image": "single fixed resident image preferred; no chunking unless measured image size later requires it",
                "max_image_length": "UNSET_UNTIL_STAGE1_SIZE_IS_MEASURED_AND_FROZEN",
                "header": ["fixed magic", "fixed version", "fixed image length bound", "integrity digest/check"],
                "entry": "one fixed stage-1 entry offset inside the retained allocation",
                "failure": "validation failure performs no execution and leaves stock path fail-open",
                "guards": "fixed pre/post guards plus allocation/image bounds before copy/execute",
                "cache": "explicit I-cache maintenance is mandatory before first stage-1 execution",
                "rollback": "reboot/power loss fully removes resident state",
                "forbidden": ["host-selected address", "host-selected call target", "poke(addr,bytes)", "goto(addr)", "generic ARM uploader", "interpreter/shell", "generic raw-packet product surface"],
            },
        },
        "promotion": {
            "vram8a_callback_abi_closed": True,
            "vram8a_nontrivial_returning_stage0_closed_offline": True,
            "vram8a_positive_reversible_canary_closed_offline": True,
            "vram8b_manifest_may_be_prepared_offline": True,
            "vram8b_live_authorized": False,
            "vram8c_resident_window_closed": False,
            "vram8c_design_advanced": True,
            "next_owner_boundary": "PREPARE_HASH_BOUND_VRAM8B_MANIFEST_OFFLINE_THEN_STOP_FOR_EXPLICIT_OWNER_GRANT",
        },
        "method_limits": [
            "No VRAM-8+ packet was generated or transmitted and Runtime 018 was not stopped or touched.",
            "Task/IRQ context is intentionally not overclaimed; this is why the promoted stage-0 is a leaf RAM-only mutation with no calls.",
            "The fresh 0x00804900 execution span avoids the already-used VRAM67-002 location; it does not promote cache-coherent arbitrary code rewriting.",
            "VRAM-8C remains design-only until a safe resident allocation context and allocator ABI are independently proven.",
        ],
    }


def write_artifacts() -> dict[str, Any]:
    report = build_report()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FIXTURE.write_bytes(STAGE0_BYTES)
    return report


def verify_committed() -> dict[str, Any]:
    live = build_report()
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if committed != live:
        raise ValueError("committed VRAM-8A artifact drift")
    if FIXTURE.read_bytes() != STAGE0_BYTES:
        raise ValueError("committed VRAM-8A stage-0 fixture drift")
    return live


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    report = write_artifacts() if args.write else (verify_committed() if ARTIFACT.exists() and FIXTURE.exists() else build_report())
    if args.selfcheck:
        print("DITOO_VRAM8_STAGE0=PASS")
        print(f"VRAM8_BRANCHES={len(report['branches'])}")
        print(f"VRAM8_STAGE0_ENTRY={report['stage0']['entry']}")
        print(f"VRAM8_STAGE0_SHA256={report['stage0']['sha256']}")
        print("VRAM8_CANARY=ENERGY_CTRL_TYPED_READBACK_0_TO_1_TO_0")
        print("VRAM8_LIVE_AUTHORITY=false")
        print(f"VRAM8_VRAM8C={report['resident_window_vram8c']['status']}")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if not (args.write or args.selfcheck or args.json):
        print("DITOO_VRAM8_STAGE0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
