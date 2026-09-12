#!/usr/bin/env python3
"""Fail-closed offline model of the Ditoo Plus Tier-2 0x6c resident display path.

This is analysis only. It reads pinned preserved firmware and emits evidence about the
stock SPP -> divoom_light_word -> resident stage-1 buffer handoff. It never opens
Bluetooth, creates a live packet, mutates firmware, or touches Runtime 018.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from keypad_pipeline_report import thumb_bl_target

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "artifacts" / "firmware"

BRANCHES = {
    "flag42_prod_v42016": {
        "path": FW / "flag42_v42016.bin",
        "sha256": "f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a",
        "size": 1207313,
        "display_entry": 0x34144,
        "display_resident_call": 0x341D6,
        "resident_veneer": 0xA6490,
        "mode_init": 0x340D2,
        "backing_alloc": 0x3B714,
        "backing_plus_0x308": 0x3B76A,
        "heap_alloc": 0x51108,
    },
    "flag42_test_v42017": {
        "path": FW / "flag42_v42017_test.bin",
        "sha256": "6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc",
        "size": 1207333,
        "display_entry": 0x34138,
        "display_resident_call": 0x341CA,
        "resident_veneer": 0xA64A4,
        "mode_init": 0x340C6,
        "backing_alloc": 0x3B728,
        "backing_plus_0x308": 0x3B77E,
        "heap_alloc": 0x5111C,
    },
    "flag60_prod_v60014": {
        "path": FW / "flag60_v60014.bin",
        "sha256": "02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300",
        "size": 1207165,
        "display_entry": 0x34100,
        "display_resident_call": 0x34190,
        "resident_veneer": 0xA63FC,
        "mode_init": 0x34038,
        "backing_alloc": 0x3B680,
        "backing_plus_0x308": 0x3B6D6,
        "heap_alloc": 0x51074,
    },
    "flag60_test_api60016_internal60017": {
        "path": FW / "flag60_api60016_internal60017_test.bin",
        "sha256": "05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339",
        "size": 1207313,
        "display_entry": 0x34144,
        "display_resident_call": 0x341D6,
        "resident_veneer": 0xA6490,
        "mode_init": 0x340D2,
        "backing_alloc": 0x3B714,
        "backing_plus_0x308": 0x3B76A,
        "heap_alloc": 0x51108,
    },
}

SPP_COMMAND = 0x6C
SPP_HANDLER = 0x11FCE
SPP_ASSEMBLER = 0xF614
SPP_MAX_INNER = 0x800
SPP_INNER_FIXED_BYTES = 3  # command + checksum u16
CMD6C_PAYLOAD_PREFIX_BEFORE_SOURCE = 4
MODE = 0x0B
SAME_MODE_TABLE = 0x12AAC
SAME_MODE_PC_BASE = 0x12AA8
MODE_ENTRY_TABLE = 0x12F00
MODE_ENTRY_PC_BASE = 0x12F00
SAME_MODE_HANDLER = 0x12CD4
MODE_ENTRY_HANDLER = 0x12F94
SHARED_DISPLAY_CALL = 0x12FA6
RESIDENT_LOAD_BASE = 0x00800000
RESIDENT_COPY_FILE_OFFSET = 0x12A8
RESIDENT_COPY_THUMB = 0x008012A9
BACKING_REQUEST = 0x708
BACKING_DATA_OFFSET = 0x308
ALLOC_QUANTUM = 0x10

# Bytes decoded once during discovery and now used as fail-closed invariants. They are
# intentionally small semantic anchors rather than a full disassembly dependency.
CMD6C_PREFIX = bytes.fromhex("00f05afc0b281dd1a088a16802380204")
SAME_MODE_PREFIX = bytes.fromhex("002cd3d021886068002262e1")
SPP_LIMIT_BYTES = bytes.fromhex("0121c9028842288202d9")  # 1<<11; cmp; store; <= accepted
PLUS_0X308_BYTES = bytes.fromhex("002803d06121c9004018704700207047")
RESIDENT_COPY_PREFIX = bytes.fromhex("f8b50d1c041c002803d11948fff71eef")
HEAP_ROUNDING_BYTES = bytes.fromhex("0f369202920a0909891a3609")  # size+=15; unit math; size>>=4


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 2], "little")


def _hex(v: int) -> str:
    return f"0x{v:x}"


def _round_up(v: int, q: int) -> int:
    return (v + q - 1) // q * q


def _load(name: str, spec: dict[str, Any]) -> bytes:
    data = Path(spec["path"]).read_bytes()
    if len(data) != spec["size"] or _sha(data) != spec["sha256"]:
        raise ValueError(f"{name}: preserved corpus identity drift")
    return data


def _check_branch(name: str, spec: dict[str, Any], data: bytes) -> dict[str, Any]:
    # 0x6c is the same dispatcher entry across all four preserved Plus branches.
    if data[SPP_HANDLER:SPP_HANDLER + len(CMD6C_PREFIX)] != CMD6C_PREFIX:
        raise ValueError(f"{name}: 0x6c handler prefix drift")

    # The receive assembler builds a 16-bit inner length and rejects only values > 0x800.
    if data[0xF638:0xF638 + len(SPP_LIMIT_BYTES)] != SPP_LIMIT_BYTES:
        raise ValueError(f"{name}: SPP 0x800 inner-length gate drift")

    # Mode 0x0b: first packet enters/initializes; later same-mode packet reaches 0x12cd4.
    same_rel = _u16(data, SAME_MODE_TABLE + 2 * MODE)
    same_target = SAME_MODE_PC_BASE + 2 * same_rel
    entry_rel = _u16(data, MODE_ENTRY_TABLE + 2 * MODE)
    entry_target = MODE_ENTRY_PC_BASE + 2 * entry_rel
    if same_target != SAME_MODE_HANDLER or entry_target != MODE_ENTRY_HANDLER:
        raise ValueError(f"{name}: mode-0x0b jump-table drift")
    if data[SAME_MODE_HANDLER:SAME_MODE_HANDLER + len(SAME_MODE_PREFIX)] != SAME_MODE_PREFIX:
        raise ValueError(f"{name}: same-mode 0x0b argument bridge drift")
    if thumb_bl_target(data, 0x12F98) != spec["mode_init"]:
        raise ValueError(f"{name}: mode-0x0b initializer target drift")
    if thumb_bl_target(data, SHARED_DISPLAY_CALL) != spec["display_entry"]:
        raise ValueError(f"{name}: same-mode display target drift")

    # Display function carries the original source pointer/length to an ARM veneer.
    if thumb_bl_target(data, spec["display_resident_call"]) != spec["resident_veneer"]:
        raise ValueError(f"{name}: resident display veneer call drift")
    veneer = spec["resident_veneer"]
    words = struct.unpack_from("<III", data, veneer)
    if words[:2] != (0xE59FC000, 0xE12FFF1C) or words[2] != RESIDENT_COPY_THUMB:
        raise ValueError(f"{name}: resident veneer no longer targets 0x008012a9")
    if data[RESIDENT_COPY_FILE_OFFSET:RESIDENT_COPY_FILE_OFFSET + len(RESIDENT_COPY_PREFIX)] != RESIDENT_COPY_PREFIX:
        raise ValueError(f"{name}: resident stage-1 copy routine drift")

    # Backing object requests 0xe1<<3 == 0x708 and returns object+(0x61<<3)==+0x308.
    ba = spec["backing_alloc"]
    if data[ba:ba + 8] != bytes.fromhex("b0b5e125ed00281c"):
        raise ValueError(f"{name}: 0x708 backing allocation setup drift")
    if thumb_bl_target(data, ba + 8) != 0xBFBC:
        raise ValueError(f"{name}: backing allocation no longer uses application heap")
    po = spec["backing_plus_0x308"]
    if data[po:po + len(PLUS_0X308_BYTES)] != PLUS_0X308_BYTES:
        raise ValueError(f"{name}: +0x308 display-data pointer helper drift")

    # Application heap stores sizes in 16-byte units: add 0xf then shift right 4.
    ha = spec["heap_alloc"]
    if data[ha + 0x60:ha + 0x60 + len(HEAP_ROUNDING_BYTES)] != HEAP_ROUNDING_BYTES:
        raise ValueError(f"{name}: application heap 16-byte rounding drift")

    return {
        "display_entry": _hex(spec["display_entry"]),
        "display_resident_call": _hex(spec["display_resident_call"]),
        "resident_veneer": _hex(veneer),
        "resident_target_thumb": _hex(RESIDENT_COPY_THUMB),
        "mode_0x0b_first_entry": _hex(entry_target),
        "mode_0x0b_same_mode_handler": _hex(same_target),
        "mode_0x0b_initializer": _hex(spec["mode_init"]),
        "backing_allocation_helper": _hex(ba),
        "backing_data_pointer_helper": _hex(po),
        "heap_allocator": _hex(ha),
        "spp_max_inner_verified": SPP_MAX_INNER,
    }


def build_report() -> dict[str, Any]:
    branches: dict[str, Any] = {}
    for name, spec in BRANCHES.items():
        data = _load(name, spec)
        branches[name] = _check_branch(name, spec, data)

    max_payload = SPP_MAX_INNER - SPP_INNER_FIXED_BYTES
    max_source = max_payload - CMD6C_PAYLOAD_PREFIX_BEFORE_SOURCE
    physical_backing = _round_up(BACKING_REQUEST, ALLOC_QUANTUM)
    physical_capacity = physical_backing - BACKING_DATA_OFFSET
    max_overwrite = max_source - physical_capacity
    if (max_payload, max_source, physical_backing, physical_capacity, max_overwrite) != (
        2045, 2041, 0x710, 0x408, 1009
    ):
        raise ValueError("Tier-2 size model drift")

    return {
        "schema_version": 1,
        "kind": "ditoo_plus_tier2_resident_display_surface",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "live_packet_generation": False,
            "firmware_mutation": False,
            "runtime_018_touched": False,
            "persistent_mutation": False,
        },
        "surface_identity": {
            "corrected_name": "DIVOOM_LIGHT_WORD_RESIDENT_DISPLAY_HANDOFF",
            "generic_audio_codec_path_proven": False,
            "note": "The former 'external media/codec' label was too broad. Source provenance and the resident veneer identify a display/light-word buffer handoff; generic codec strings are not evidence of reachability from 0x6c.",
        },
        "corpus": {
            name: {
                "path": str(Path(spec["path"]).relative_to(ROOT)),
                "sha256": spec["sha256"],
                "size_bytes": spec["size"],
            }
            for name, spec in BRANCHES.items()
        },
        "branches": branches,
        "reachability": {
            "command": "0x6c",
            "handler": _hex(SPP_HANDLER),
            "stock_mode": "0x0b",
            "first_packet_role": "normal volatile mode entry initializes the light-word/display object",
            "subsequent_same_mode_role": "same-mode event reaches 0x12cd4 and forwards caller source/length through the display function to resident stage-1",
            "requires_persistent_write": False,
            "resident_target_stable_4_of_4": True,
        },
        "size_model": {
            "spp_max_inner_bytes": SPP_MAX_INNER,
            "spp_inner_fixed_bytes_command_plus_checksum": SPP_INNER_FIXED_BYTES,
            "max_payload_bytes": max_payload,
            "command_0x6c_payload_prefix_before_source": CMD6C_PAYLOAD_PREFIX_BEFORE_SOURCE,
            "max_caller_controlled_source_bytes": max_source,
            "backing_request_bytes": BACKING_REQUEST,
            "allocator_quantum_bytes": ALLOC_QUANTUM,
            "backing_physical_bytes_after_rounding": physical_backing,
            "display_data_offset": BACKING_DATA_OFFSET,
            "physical_capacity_from_display_pointer": physical_capacity,
            "max_controlled_bytes_beyond_physical_allocation": max_overwrite,
        },
        "promoted_primitive": {
            "status": "PROMOTED_OFFLINE",
            "class": "CALLER_CONTROLLED_ADJACENT_HEAP_OVERWRITE",
            "source": "packet+5",
            "copy_length": "caller u16(packet+3)",
            "sink": "resident 0x008012a8 later memcpy(ctx[0], source, caller_length)",
            "maximum_controlled_overwrite_bytes": max_overwrite,
            "persistent": False,
            "cross_branch": "4_OF_4_PRESERVED_PLUS_BRANCHES",
        },
        "control_flow_gate": {
            "deterministic_victim_placement_proven": False,
            "controlled_indirect_branch_proven": False,
            "live_manifest_candidate": None,
            "why_not_yet": [
                "The application heap uses separate descriptors and 16-byte units rather than an inline next-chunk header, so the first overflow bytes are not automatically control metadata.",
                "The heap is already allocation/free-active before the display backing object is created; static call chronology alone does not prove physical adjacency.",
                "Callback-bearing objects exist in firmware, but no exact victim has yet been proven to occupy a deterministic offset inside the overwrite window.",
            ],
            "interesting_unpromoted_flag42_sinks": [
                {"object_family": "plugin/child object", "callback_offsets": ["0x0c", "0x20", "0x2c"], "indirect_calls": ["0x20508", "0x20356", "0x20332", "0x204a8"]},
                {"object_family": "0x50-byte runtime object", "callback_offset": "0x34", "indirect_call": "0x1fac4"},
            ],
            "next_offline_gate": "DETERMINISTIC_VICTIM_OR_CONTROL_SINK_PLACEMENT",
        },
        "method_limits": [
            "This artifact proves a copy primitive and its maximum structural overwrite, not code execution.",
            "It does not infer heap adjacency from allocation order because the allocator is not modeled as a monotonic bump allocator.",
            "No live malformed/custom 0x6c packet has been transmitted; physical behavior remains untested by design.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", type=Path)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text)
    if args.json:
        print(text, end="")
    if args.selfcheck:
        s = report["size_model"]
        p = report["promoted_primitive"]
        print("DITOO_TIER2_DISPLAY=PASS")
        print(f"TIER2_BRANCHES={len(report['branches'])}")
        print(f"TIER2_PRIMITIVE={p['class']}")
        print(f"TIER2_MAX_SOURCE_BYTES={s['max_caller_controlled_source_bytes']}")
        print(f"TIER2_PHYSICAL_CAPACITY={s['physical_capacity_from_display_pointer']}")
        print(f"TIER2_MAX_OVERWRITE_BYTES={s['max_controlled_bytes_beyond_physical_allocation']}")
        print("TIER2_CONTROL_FLOW_SINK=UNRESOLVED_PLACEMENT")
        print("TIER2_LIVE_MANIFEST_CANDIDATE=NONE")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_TIER2_DISPLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
