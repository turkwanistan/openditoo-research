#!/usr/bin/env python3
"""Fail-closed offline VRAM-3 execution/RAM model for Ditoo Plus.

Reads only the pinned preserved firmware corpus. It proves the stock SRAM/heap mapping,
ARMv5T MMU/cache setup and Thumb execution contract needed by a future RAM-resident stage-0.
No Bluetooth/device IO, packet generation, firmware mutation or Runtime 018 access occurs.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "artifacts" / "firmware"

BRANCHES = {
    "flag42_prod_v42016": ("flag42_v42016.bin", "f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a", 1207313),
    "flag42_test_v42017": ("flag42_v42017_test.bin", "6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc", 1207333),
    "flag60_prod_v60014": ("flag60_v60014.bin", "02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300", 1207165),
    "flag60_test_api60016_internal60017": ("flag60_api60016_internal60017_test.bin", "05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339", 1207313),
}

MMU_SETUP = 0x4354
MMU_SETUP_SIG = bytes.fromhex("00b585b0154a4123012189035b040092134ac800fff7fefefff766fe1148fff7affffff775ff0122a0210f48")
MAP_FN = 0x4168
MAP_SIG = bytes.fromhex("f8b51c1c151c071c28059b049b0c000d069a184393059b0d0343002b304802d00122522109e00123db059d4203d39c4201d39a4205d201225921fef7b9fb0020")
ENABLE_SEQ = 0x4264
ENABLE_SIG = bytes.fromhex("80b500f024e8fcf744ed00f004e800f00ae880bd")
HEAP_INIT_PREFIX = bytes.fromhex("22482349b0b54018041c22488c43001b05092d01291c201c")

HEAP_MANAGER = 0x00803B78
HEAP_RAW_START = 0x00803F80
HEAP_START = 0x00804000
HEAP_END = 0x0081D000
HEAP_SIZE = HEAP_END - HEAP_START
IDENTITY_MAP_START = 0x00803000
IDENTITY_MAP_END = 0x00820000
PAGE_ATTR = 0xFFA
RESIDENT_BASE = 0x00800000
RESIDENT_RUNTIME_SERVICE = 0x008012A9

# Application-copy CP15 helpers (file/runtime application offset uses normal app mapping).
CP15 = {
    "disable_i_cache": (0xCB8, bytes.fromhex("100f11ee400dc0e3100f01ee1eff2fe1")),
    "disable_d_cache": (0xCC8, bytes.fromhex("100f11ee0400c0e3100f01ee1eff2fe1")),
    "invalidate_both_caches": (0xCD8, bytes.fromhex("170f07ee1eff2fe1")),
    "invalidate_i_cache": (0xCE0, bytes.fromhex("150f07ee1eff2fe1")),
    "test_clean_invalidate_d_cache": (0xCE8, bytes.fromhex("7eff17eefdffff1a1eff2fe1")),
    "invalidate_tlb": (0xCF4, bytes.fromhex("170f08ee1eff2fe1")),
    "disable_mmu": (0xCFC, bytes.fromhex("100f11ee0100c0e3100f01ee1eff2fe1")),
}


def _sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def _load(spec: tuple[str, str, int]) -> bytes:
    fn, sha, size = spec
    b = (FW / fn).read_bytes()
    if len(b) != size or _sha(b) != sha:
        raise ValueError(f"corpus identity drift: {fn}")
    return b

def _find_all(b: bytes, needle: bytes) -> list[int]:
    out=[]; s=0
    while True:
        i=b.find(needle,s)
        if i < 0: return out
        out.append(i); s=i+1

def _branch(name: str, spec: tuple[str,str,int]) -> dict[str, Any]:
    b = _load(spec)
    if b[MMU_SETUP:MMU_SETUP+len(MMU_SETUP_SIG)] != MMU_SETUP_SIG:
        raise ValueError(f"{name}: stage1 MMU setup drift")
    if b[MAP_FN:MAP_FN+len(MAP_SIG)] != MAP_SIG:
        raise ValueError(f"{name}: stage1 mapping function drift")
    if b[ENABLE_SEQ:ENABLE_SEQ+len(ENABLE_SIG)] != ENABLE_SIG:
        raise ValueError(f"{name}: MMU/cache enable sequence drift")
    for label,(off,sig) in CP15.items():
        if b[off:off+len(sig)] != sig:
            raise ValueError(f"{name}: CP15 helper drift: {label}")

    starts = [x for x in _find_all(b, HEAP_RAW_START.to_bytes(4,'little')) if x > 0x10000]
    if len(starts) != 1:
        raise ValueError(f"{name}: heap-start literal ambiguity: {starts}")
    lit = starts[0]
    init = lit - 0x8C
    if b[init:init+len(HEAP_INIT_PREFIX)] != HEAP_INIT_PREFIX:
        raise ValueError(f"{name}: heap init prefix drift")
    vals = [int.from_bytes(b[lit+d:lit+d+4],'little') for d in (-4,0,4,8)]
    if vals != [HEAP_MANAGER, HEAP_RAW_START, 0xFFF, HEAP_END]:
        raise ValueError(f"{name}: heap init literals drift: {vals}")

    # The common setup's literal block and arithmetic pin the identity-mapped SRAM window.
    literals = [int.from_bytes(b[o:o+4], 'little') for o in (0x43B0,0x43B4,0x43B8)]
    if literals != [0x0081FC00, 0x0081F000, 0x00800048]:
        raise ValueError(f"{name}: MMU setup literals drift")
    # 0x41e0..0x41fc uses page attrs 0xff2 then 0xffa for the 0x803000..0x820000 mapping.
    if int.from_bytes(b[0x4258:0x425C],'little') != 0xFF2 or int.from_bytes(b[0x425C:0x4260],'little') != 0x00803000:
        raise ValueError(f"{name}: page mapping constants drift")

    return {
        "heap_init": hex(init),
        "heap_start": hex(HEAP_START),
        "heap_end_exclusive": hex(HEAP_END),
        "heap_size_bytes": HEAP_SIZE,
        "identity_map_start": hex(IDENTITY_MAP_START),
        "identity_map_end_exclusive": hex(IDENTITY_MAP_END),
        "mmu_setup": hex(MMU_SETUP),
        "mmu_cache_enable_sequence": hex(ENABLE_SEQ),
        "resident_service_example": hex(RESIDENT_RUNTIME_SERVICE),
    }


def build_report() -> dict[str, Any]:
    branches={name:_branch(name,spec) for name,spec in BRANCHES.items()}
    if not (IDENTITY_MAP_START <= HEAP_START < HEAP_END <= IDENTITY_MAP_END):
        raise ValueError("heap no longer inside identity mapping")
    return {
        "schema_version": 1,
        "kind": "ditoo_plus_vram3_execution_model",
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
        "execution_model": {
            "isa": "ARMv5T_ARM_THUMB_INTERWORKING",
            "resident_load_base": hex(RESIDENT_BASE),
            "heap_start": hex(HEAP_START),
            "heap_end_exclusive": hex(HEAP_END),
            "heap_size_bytes": HEAP_SIZE,
            "identity_mapped_sram": f"{hex(IDENTITY_MAP_START)}..{hex(IDENTITY_MAP_END-1)}",
            "mmu_enabled_by_stock_stage1": True,
            "i_cache_enabled_by_stock_stage1": True,
            "d_cache_enabled_by_stock_stage1": True,
            "armv5_short_descriptor_execute_never_bit": False,
            "heap_executable_by_mapping_model": True,
            "thumb_entry_requires_address_bit0": 1,
            "conclusion": "The application heap is inside the stock identity-mapped SRAM window. ARMv5T short descriptors provide access/cache attributes but no XN permission, so mapped heap RAM is executable; no NX bypass is required.",
        },
        "mapping": {
            "small_page_descriptor_low_bits": hex(PAGE_ATTR),
            "cacheable_C": 1,
            "bufferable_B": 0,
            "cache_policy": "WRITE_THROUGH_CACHEABLE_NONBUFFERABLE",
            "access": "full-access AP fields in the pinned descriptor constant",
            "stage1_tail_reclaimed": "Heap begins at 0x00804000 while boot/cache helper code exists around resident 0x00804278; stock initialization deliberately reuses the stage1 tail as heap after boot.",
        },
        "cache_coherency": {
            "first_execution": "Write-through heap mapping means CPU stores reach backing SRAM; a never-before-executed heap address avoids a stale I-cache line. Static analysis cannot prove an arbitrary chosen heap address has never been fetched, so a first live stage-0 should remain tiny and use a freshly controlled span.",
            "post_stage0": "Once stage-0 executes, stock CP15 helpers provide explicit I-cache invalidation and D-cache clean/invalidate primitives before transferring to a larger rewritten code buffer.",
            "helpers": {k: hex(v[0]) for k,v in CP15.items()},
        },
        "calling_contract": {
            "thumb_target": "set bit0 of the function pointer before BLX/BX",
            "argument_registers": "r0-r3",
            "return_register": "r0",
            "return_mechanism": "bx lr / pop {...,pc}",
            "stage0_rule": "preserve callee-saved state used by the victim callsite and return cleanly before attempting any loader behavior",
        },
        "scratch_model": {
            "fixed_reserved_heap_scratch_proven": False,
            "preferred_stage0_storage": "caller-controlled bytes already inside the proven adjacent-overwrite span, once a deterministic victim offset is established",
            "larger_loader_storage": "a separately controlled/allocated heap span after stage-0 can perform cache maintenance and bounds checks",
            "reason": "The heap is allocator-owned; no fixed address inside 0x00804000..0x0081cfff is statically reserved for OpenDitoo.",
        },
        "promotion": {
            "vram3_execution_environment_established": True,
            "ram_executable": True,
            "nx_blocker": False,
            "remaining_blocker_before_live_stage0": "DETERMINISTIC_CONTROL_FLOW_VICTIM_PLACEMENT",
            "live_manifest_candidate": None,
        },
        "method_limits": [
            "This proves the execution/mapping contract, not control-flow hijack.",
            "No absolute heap allocation address for the Tier-2 backing object is inferred from boot chronology.",
            "No live malformed/custom packet or device experiment was performed.",
        ],
    }


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--write',type=Path); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args()
    r=build_report(); text=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.write: a.write.parent.mkdir(parents=True,exist_ok=True); a.write.write_text(text)
    if a.json: print(text,end='')
    if a.selfcheck:
        e=r['execution_model']; p=r['promotion']
        print('DITOO_VRAM3_EXECUTION=PASS')
        print(f"VRAM3_BRANCHES={len(r['branches'])}")
        print(f"VRAM3_HEAP={e['heap_start']}..{e['heap_end_exclusive']}")
        print(f"VRAM3_RAM_EXECUTABLE={str(p['ram_executable']).lower()}")
        print('VRAM3_NX_BLOCKER=NONE')
        print('VRAM3_LIVE_MANIFEST_CANDIDATE=NONE')
    if not (a.write or a.json or a.selfcheck): print('DITOO_VRAM3_EXECUTION=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
