#!/usr/bin/env python3
"""Offline VRAM-8C callback-context and allocator-contract proof.

Proves, across the four pinned Ditoo Plus branches, that VoiceTip microtask work is
marked from the hardware timer IRQ but dispatched only after the IRQ return frame is
rewritten to the resident microtask dispatcher.  It also pins the Fwl_Malloc/Fwl_Free
ABI and shared app-heap busy flag used by the already-promoted VoiceTip gate.

This tool performs no device/Bluetooth I/O and creates no live authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from ditoo_tier2_placement import BRANCHES, FW
from ditoo_tier2_trigger import build_report as build_trigger_report
from ditoo_vram3_execution_model import build_report as build_vram3_report
from keypad_pipeline_report import thumb_bl_target

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/analysis/volatile_ram_api_vram8c_context.json"

IRQ_VECTOR = 0x18
IRQ_ENTRY = 0x0AF4
TIMER_IRQ_BRANCH = 0x0B28
TIMER_VENEER = 0x0D3C
TIMER_HANDLER_THUMB = 0x00802171
TIMER_HANDLER = 0x2170
TIMER_CALLBACK_BLX = 0x21C0

IRQ_SPSR_READ = 0x0BD8
IRQ_SPSR_CLEAR_CONTROL = 0x0BE0
IRQ_SPSR_CLEAR_FLAGS = 0x0BE4
IRQ_SPSR_SET_THUMB_SVC = 0x0BE8
IRQ_SPSR_WRITE = 0x0BEC
IRQ_SWITCH_SVC = 0x0BF0
IRQ_SWITCH_SVC_WRITE = 0x0BF4
IRQ_SWITCH_IRQ = 0x0C00
IRQ_SWITCH_IRQ_WRITE = 0x0C04
DEFERRED_CPSR_MODE = 0x33  # T bit + SVC mode
IRQ_DEFER_LDR = 0x0C20
IRQ_DEFER_STR = 0x0C24
IRQ_EXCEPTION_RETURN = 0x0C3C
MICROTASK_DISPATCH_LITERAL = 0x0CAC
MICROTASK_DISPATCH_THUMB = 0x008015ED
MICROTASK_DISPATCH = 0x15EC
MICROTASK_TICK_THUMB = 0x008014F9

FWL_MALLOC = 0xBFBC
FWL_FREE = 0xBFCE
FWL_BUSY_PREDICATE = 0xBFE8
FWL_BUSY_LITERAL = 0xBFF0
APP_HEAP_BUSY = 0x008030C4
APP_LINK_BASE = 0x08400000


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(name: str, spec: dict[str, Any]) -> bytes:
    p = FW / spec["file"]
    data = p.read_bytes()
    if len(data) != spec["size"] or _sha(data) != spec["sha"]:
        raise ValueError(f"{name}: corpus identity drift")
    return data


def _arm_branch_target(off: int, word: int) -> int | None:
    if ((word >> 25) & 0x7) != 0b101:
        return None
    imm = word & 0x00FFFFFF
    if imm & 0x00800000:
        imm -= 0x01000000
    return (off + 8 + (imm << 2)) & 0xFFFFFFFF


def _find_all(data: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    pos = 0
    while True:
        hit = data.find(needle, pos)
        if hit < 0:
            return out
        out.append(hit)
        pos = hit + 1


def _branch(name: str, spec: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
    b = _load(name, spec)

    irq_target = _arm_branch_target(IRQ_VECTOR, struct.unpack_from("<I", b, IRQ_VECTOR)[0])
    if irq_target != IRQ_ENTRY:
        raise ValueError(f"{name}: IRQ vector drift {irq_target!r}")
    timer_target = _arm_branch_target(TIMER_IRQ_BRANCH, struct.unpack_from("<I", b, TIMER_IRQ_BRANCH)[0])
    if timer_target != TIMER_VENEER:
        raise ValueError(f"{name}: timer IRQ branch drift {timer_target!r}")

    veneer = tuple(struct.unpack_from("<I", b, TIMER_VENEER + 4 * i)[0] for i in range(3))
    if veneer != (0xE59FC000, 0xE12FFF1C, TIMER_HANDLER_THUMB):
        raise ValueError(f"{name}: timer veneer drift {veneer!r}")

    # Timer handler iterates its 8-slot table and BLXes slot callback +8.
    if b[TIMER_CALLBACK_BLX:TIMER_CALLBACK_BLX + 2] != bytes.fromhex("9047"):
        raise ValueError(f"{name}: timer callback BLX drift")

    tick_refs = _find_all(b, struct.pack("<I", MICROTASK_TICK_THUMB))
    reg_impl = int(trigger["branches"][name]["microtask_registration_impl"], 16)
    expected_tick_ref = reg_impl + 0xDA
    if tick_refs != [expected_tick_ref]:
        raise ValueError(f"{name}: microtask tick pointer ref drift {tick_refs!r}")
    # The IRQ-level microtask tick only updates countdown/pending state; it does not
    # directly BLX a registered worker.
    tick = b[0x14F8:0x1548]
    if any(int.from_bytes(tick[i:i + 2], "little") in (0x4780, 0x4788, 0x4790, 0x4798)
           for i in range(0, len(tick) - 1, 2)):
        raise ValueError(f"{name}: IRQ microtask tick gained indirect BLX")

    privilege_words = tuple(struct.unpack_from("<I", b, off)[0] for off in (
        0x0BAC, 0x0BB0, 0x0BB4, 0x0BB8, IRQ_SPSR_READ, IRQ_SPSR_CLEAR_CONTROL,
        IRQ_SPSR_CLEAR_FLAGS, IRQ_SPSR_SET_THUMB_SVC, IRQ_SPSR_WRITE, IRQ_SWITCH_SVC,
        IRQ_SWITCH_SVC_WRITE, IRQ_SWITCH_IRQ, IRQ_SWITCH_IRQ_WRITE,
    ))
    expected_privilege_words = (
        0xE14F0000, 0xE200001F, 0xE3500017, 0x0A00001F, 0xE14F0000,
        0xE3C000DF, 0xE3C004F0, 0xE3800033, 0xE16FF000, 0xE3A020D3,
        0xE121F002, 0xE3A020D2, 0xE121F002,
    )
    if privilege_words != expected_privilege_words:
        raise ValueError(f"{name}: deferred SVC privilege sequence drift {privilege_words!r}")

    defer = (
        struct.unpack_from("<I", b, IRQ_DEFER_LDR)[0],
        struct.unpack_from("<I", b, IRQ_DEFER_STR)[0],
        struct.unpack_from("<I", b, IRQ_EXCEPTION_RETURN)[0],
        struct.unpack_from("<I", b, MICROTASK_DISPATCH_LITERAL)[0],
    )
    if defer != (0xE59F0084, 0xE5080004, 0xE8FD9FFF, MICROTASK_DISPATCH_THUMB):
        raise ValueError(f"{name}: deferred IRQ-return hook drift {defer!r}")
    dispatch_refs = _find_all(b, struct.pack("<I", MICROTASK_DISPATCH_THUMB))
    if dispatch_refs != [MICROTASK_DISPATCH_LITERAL]:
        raise ValueError(f"{name}: dispatcher pointer ref drift {dispatch_refs!r}")
    if b[0x161C:0x1620] != bytes.fromhex("40688847"):
        raise ValueError(f"{name}: deferred microtask callback BLX drift")

    # Fwl_Malloc(r0=size)->r0 pointer. The wrapper sets the shared busy byte,
    # calls the branch-local allocator callback, then clears the busy byte.
    if b[FWL_MALLOC:FWL_MALLOC + 8] != bytes.fromhex("10b50c4c01212170"):
        raise ValueError(f"{name}: Fwl_Malloc prefix drift")
    malloc_target = thumb_bl_target(b, FWL_MALLOC + 8)
    expected_malloc = spec["heap_init"] + 0x50
    if malloc_target != expected_malloc:
        raise ValueError(f"{name}: Fwl_Malloc target drift {malloc_target!r} != {expected_malloc:#x}")
    if b[FWL_MALLOC + 12:FWL_MALLOC + 18] != bytes.fromhex("0021217010bd"):
        raise ValueError(f"{name}: Fwl_Malloc epilogue drift")

    if b[FWL_FREE:FWL_FREE + 8] != bytes.fromhex("10b5074c01212170"):
        raise ValueError(f"{name}: Fwl_Free prefix drift")
    free_target = thumb_bl_target(b, FWL_FREE + 8)
    expected_free = spec["heap_init"] + 0x6E
    if free_target != expected_free:
        raise ValueError(f"{name}: Fwl_Free target drift {free_target!r} != {expected_free:#x}")
    if b[FWL_FREE + 12:FWL_FREE + 18] != bytes.fromhex("0021217010bd"):
        raise ValueError(f"{name}: Fwl_Free epilogue drift")

    if b[FWL_BUSY_PREDICATE:FWL_BUSY_PREDICATE + 6] != bytes.fromhex("014800787047"):
        raise ValueError(f"{name}: allocator busy predicate drift")
    busy = struct.unpack_from("<I", b, FWL_BUSY_LITERAL)[0]
    if busy != APP_HEAP_BUSY:
        raise ValueError(f"{name}: allocator busy address drift {busy:#x}")

    return {
        "irq_vector": hex(IRQ_VECTOR),
        "irq_entry": hex(IRQ_ENTRY),
        "timer_irq_branch": hex(TIMER_IRQ_BRANCH),
        "timer_veneer": hex(TIMER_VENEER),
        "timer_handler_thumb": hex(TIMER_HANDLER_THUMB),
        "timer_callback_blx": hex(TIMER_CALLBACK_BLX),
        "microtask_tick_thumb": hex(MICROTASK_TICK_THUMB),
        "microtask_tick_pointer_ref": hex(expected_tick_ref),
        "microtask_tick_direct_worker_blx": False,
        "irq_deferred_dispatch_pointer_literal": hex(MICROTASK_DISPATCH_LITERAL),
        "microtask_dispatch_thumb": hex(MICROTASK_DISPATCH_THUMB),
        "microtask_dispatch_worker_blx": "0x161e",
        "deferred_dispatch_cpsr": hex(DEFERRED_CPSR_MODE),
        "deferred_dispatch_mode": "THUMB_SVC_PRIVILEGED",
        "fwl_malloc": hex(APP_LINK_BASE + FWL_MALLOC + 1),
        "fwl_malloc_file_offset": hex(FWL_MALLOC),
        "fwl_malloc_inner": hex(APP_LINK_BASE + expected_malloc + 1),
        "fwl_free": hex(APP_LINK_BASE + FWL_FREE + 1),
        "fwl_free_file_offset": hex(FWL_FREE),
        "fwl_free_inner": hex(APP_LINK_BASE + expected_free + 1),
        "app_heap_busy_byte": hex(APP_HEAP_BUSY),
    }


def build_report() -> dict[str, Any]:
    trigger = build_trigger_report()
    vram3 = build_vram3_report()
    branches = {name: _branch(name, spec, trigger) for name, spec in BRANCHES.items()}

    if not trigger["invocation_gate"]["allocator_busy_flag_is_transient"]:
        raise ValueError("trigger artifact no longer proves transient allocator busy gate")
    if not trigger["invocation_gate"]["deterministic_stock_post_overwrite_invocation_proven"]:
        raise ValueError("trigger artifact no longer proves deterministic callback invocation")
    if vram3["cache_coherency"]["helpers"].get("invalidate_i_cache") != "0xce0":
        raise ValueError("VRAM-3 I-cache helper drift")

    return {
        "schema_version": 1,
        "kind": "ditoo_plus_vram8c_context_allocator_gate",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "bluetooth_opened": False,
            "live_packet_generation": False,
            "runtime_018_touched": False,
            "firmware_or_flash_mutation": False,
            "persistent_mutation": False,
        },
        "branches": branches,
        "callback_context": {
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
            "hardware_timer_tick_runs_in_irq": True,
            "irq_vector_offset": hex(IRQ_VECTOR),
            "irq_entry": hex(IRQ_ENTRY),
            "timer_irq_dispatch": f"{hex(TIMER_IRQ_BRANCH)} -> {hex(TIMER_VENEER)} -> {hex(TIMER_HANDLER_THUMB)}",
            "irq_level_microtask_tick": hex(MICROTASK_TICK_THUMB),
            "irq_tick_behavior": "decrement/reload microtask countdowns and mark pending slots only; no registered worker BLX occurs in the IRQ tick",
            "deferred_dispatch": f"IRQ return frame injects Thumb {hex(MICROTASK_DISPATCH_THUMB)} and rewrites SPSR control state to 0x33 (Thumb + SVC) before exception return; the dispatcher then BLXes pending workers in privileged SVC context",
            "dispatcher": hex(MICROTASK_DISPATCH_THUMB),
            "deferred_dispatch_cpsr": hex(DEFERRED_CPSR_MODE),
            "deferred_dispatch_mode": "THUMB_SVC_PRIVILEGED",
            "voice_tip_callback_is_direct_irq_callback": False,
            "non_irq_deferred_context_proven": True,
            "privileged_svc_context_proven": True,
            "scope_limit": "This closes the callback execution-mode gate only for the pinned deferred microtask path; it does not generalize arbitrary callback contexts elsewhere in firmware.",
        },
        "allocator_contract": {
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
            "fwl_malloc_thumb": hex(APP_LINK_BASE + FWL_MALLOC + 1),
            "signature": "r0=request_bytes -> r0=allocated_pointer_or_null",
            "callee_saved": "wrapper saves/restores r4/lr",
            "busy_byte": hex(APP_HEAP_BUSY),
            "entry_rule": "VoiceTip worker already defers while the shared app-heap busy byte is nonzero; callback entry therefore occurs after any in-flight Fwl_Malloc/Fwl_Free wrapper clears it.",
            "wrapper_rule": "Fwl_Malloc sets busy=1 before the branch-local allocator call and clears busy=0 before returning; Fwl_Free mirrors the same contract.",
            "retained_allocation_policy": "one fixed-size allocation, never freed during the OpenDitoo boot session; destination is device-selected and never supplied by the host",
            "allocator_context_gate_closed_offline": True,
        },
        "cache_contract": {
            "heap_mapping": vram3["mapping"]["cache_policy"],
            "stock_invalidate_i_cache_helper": vram3["cache_coherency"]["helpers"]["invalidate_i_cache"],
            "helper_bytes_pinned_cross_branch": True,
            "deferred_callback_mode": "THUMB_SVC_PRIVILEGED",
            "direct_cp15_call_authorized": True,
            "interworking_contract": "Thumb stage-0 may BLX the fixed ARM helper address 0x00800ce0 (bit0 clear); helper returns with BX LR",
            "remaining_question": None,
        },
        "promotion": {
            "vram8c_callback_non_irq_deferred_context_closed": True,
            "vram8c_allocator_abi_closed": True,
            "vram8c_allocator_entry_gate_closed": True,
            "vram8c_retained_allocation_design_promoted": True,
            "vram8c_cache_maintenance_privilege_closed": True,
            "vram8c_fixed_resident_image_measured": False,
            "vram8c_installer_closed": False,
            "vram8d_live_authorized": False,
            "vram9_authorized": False,
        },
        "method_limits": [
            "No stock microtask callback was claimed to call Fwl_Malloc; a conservative callback scan did not establish that stronger precedent.",
            "The promotion rests on the resident IRQ/deferred-dispatch structure plus the exact allocator wrapper/busy-gate contract, not on crash/timing behavior.",
            "The IRQ defer path is byte-pinned 4/4 to rewrite SPSR as Thumb SVC (0x33), so the fixed CP15 I-cache helper is permitted from this specific deferred callback context.",
            "A resident installer is still not promoted until one fixed stage-1 image exists, its exact size/hash are frozen, and copy/guard bounds are proven against that measured image.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", type=Path)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if a.write:
        a.write.parent.mkdir(parents=True, exist_ok=True)
        a.write.write_text(text, encoding="utf-8")
    if a.json:
        print(text, end="")
    if a.selfcheck:
        p = report["promotion"]
        print("DITOO_VRAM8C_CONTEXT=PASS")
        print(f"VRAM8C_BRANCHES={len(report['branches'])}")
        print(f"VRAM8C_NON_IRQ_DEFERRED={str(p['vram8c_callback_non_irq_deferred_context_closed']).lower()}")
        print(f"VRAM8C_ALLOCATOR_ABI={str(p['vram8c_allocator_abi_closed']).lower()}")
        print(f"VRAM8C_CACHE_PRIVILEGE={str(p['vram8c_cache_maintenance_privilege_closed']).lower()}")
        print("VRAM8C_INSTALLER_CLOSED=false")
    if not (a.write or a.json or a.selfcheck):
        print("DITOO_VRAM8C_CONTEXT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
