#!/usr/bin/env python3
"""Recognition-only audit of stock Divoom SPP recovery/readback surfaces.

This tool performs *offline static analysis only*.  It never opens a transport,
constructs device packets, modifies firmware, or emits an installable image.

The goal is deliberately narrow: make the negative/positive recovery-surface
claims machine-checkable across the preserved Ditoo Plus branches and the
original-Ditoo comparative firmware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from keypad_pipeline_report import _bl_xrefs, thumb_bl_target

ROOT = Path(__file__).resolve().parents[1]

BRANCHES = {
    "flag42_v42016": {
        "path": ROOT / "artifacts/firmware/flag42_v42016.bin",
        "sha256": "f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a",
        "dispatcher_start": 0x1047C,
        "dispatcher_end": 0x1271E,
        "table_read_base": 0x105E8,
        "table_jump_base": 0x105E4,
        "default_handler": 0x126E4,
        "secondary_default_handler": 0x126EC,
        "flash_read": 0x1BEAA,
        "extern_handler": 0x10A88,
    },
    "flag60_v60014": {
        "path": ROOT / "artifacts/firmware/flag60_v60014.bin",
        "sha256": "02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300",
        "dispatcher_start": 0x1047C,
        "dispatcher_end": 0x1271E,
        "table_read_base": 0x105E8,
        "table_jump_base": 0x105E4,
        "default_handler": 0x126E4,
        "secondary_default_handler": 0x126EC,
        "flash_read": 0x1BEAA,
        "extern_handler": 0x10A88,
    },
    "original_ditoo_flag46_v46032": {
        "path": ROOT / "artifacts/reference/ditoo_flag46_v46032.bin",
        "sha256": "a7ee309ef2d0c07f8a72abb9dd9bb444f33bd8f952ca9009c7b7f8e385d7e3d2",
        "dispatcher_start": 0x1045C,
        "dispatcher_end": 0x126CA,
        "table_read_base": 0x105C8,
        "table_jump_base": 0x105C4,
        "default_handler": 0x12690,
        "secondary_default_handler": 0x12698,
        "flash_read": 0x1BFB8,
        "extern_handler": 0x10A68,
    },
}

# Recovery-interest command labels.  Names come from Divoom app-family enum
# archaeology; handler addresses/verdicts below are established from the local
# firmware bytes and must not be inferred from the names alone.
RECOVERY_COMMANDS = {
    0x48: "SPP_PAUSE_SYS_UPDATE_DATA",
    0x49: "update_state_query_family_label",
    0x93: "SPP_SYS_DEVICE_UPDATE",
    0x94: "SPP_SYS_UPDATE_DATA",
    0x95: "SPP_SYS_CONTINUE_UPDATE_DATA",
    0x96: "SPP_SYS_GET_UPDATE_ADDR",
    0x97: "SPP_GET_FILE_VERSION",
    0x98: "SPP_APP_UPDATE_FILE_INFO",
    0x99: "SPP_APP_SEND_FILE_DATA",
    0x9B: "SPP_SEND_HOT_FILE_LIST",
    0x9D: "SPP_HOT_UPDATE_FILE_INFO",
    0x9E: "SPP_HOT_SEND_FILE_DATA",
    0x9F: "SPP_HOT_PAUSE_FILE_SEND",
    0xBD: "SPP_DIVOOM_EXTERN_CMD",
}

EXPECTED_PLUS_TARGETS = {
    0x48: 0x11144,
    0x49: 0x11BB8,
    0x93: 0x126E4,
    0x94: 0x126E4,
    0x95: 0x126E4,
    0x96: 0x126E4,
    0x97: 0x110CC,
    0x98: 0x1115A,
    0x99: 0x1124C,
    0x9B: 0x10E78,
    0x9D: 0x10EA2,
    0x9E: 0x10F52,
    0x9F: 0x10F3C,
    0xBD: 0x10A88,
}

# Exact instruction prefix of the 0xbd sub-dispatch on the preserved Plus
# branches: ldrb payload[1]; sub #0x13; cmp #9; bcs default; jump table.
EXTERN_PREFIX = bytes.fromhex("78781338092804d202a31b181b5a5b009f44")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dispatch_map(data: bytes, read_base: int, jump_base: int) -> dict[int, int]:
    if read_base + 2 * 251 > len(data):
        raise ValueError("dispatcher table outside firmware")
    out: dict[int, int] = {}
    for cmd in range(0x04, 0xFF):
        idx = cmd - 4
        off = int.from_bytes(data[read_base + 2 * idx : read_base + 2 * idx + 2], "little")
        out[cmd] = jump_base + 2 * off
    return out


def _branch_report(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    path: Path = cfg["path"]
    data = path.read_bytes()
    actual_sha = _sha256(data)
    if actual_sha != cfg["sha256"]:
        raise ValueError(f"{name}: SHA-256 mismatch; refusing to interpret unknown bytes")

    dm = dispatch_map(data, cfg["table_read_base"], cfg["table_jump_base"])
    counts = Counter(dm.values())
    flash_xrefs = _bl_xrefs(data, cfg["flash_read"])
    spp_flash_xrefs = [
        x for x in flash_xrefs if cfg["dispatcher_start"] <= x < cfg["dispatcher_end"]
    ]

    commands = {}
    for cmd, label in RECOVERY_COMMANDS.items():
        target = dm[cmd]
        commands[f"0x{cmd:02x}"] = {
            "family_label": label,
            "handler": f"0x{target:x}",
            "is_primary_default": target == cfg["default_handler"],
            "is_secondary_default": target == cfg["secondary_default_handler"],
        }

    extern_prefix_ok = data[cfg["extern_handler"] : cfg["extern_handler"] + len(EXTERN_PREFIX)] == EXTERN_PREFIX

    return {
        "name": name,
        "path": str(path.relative_to(ROOT)),
        "sha256": actual_sha,
        "dispatcher": {
            "start": f"0x{cfg['dispatcher_start']:x}",
            "end": f"0x{cfg['dispatcher_end']:x}",
            "table_read_base": f"0x{cfg['table_read_base']:x}",
            "table_jump_base": f"0x{cfg['table_jump_base']:x}",
            "entry_count": len(dm),
            "primary_default": f"0x{cfg['default_handler']:x}",
            "primary_default_count": counts[cfg["default_handler"]],
            "secondary_default": f"0x{cfg['secondary_default_handler']:x}",
            "secondary_default_count": counts[cfg["secondary_default_handler"]],
            "real_handler_count_by_primary_default": sum(t != cfg["default_handler"] for t in dm.values()),
        },
        "recovery_commands": commands,
        "extern_mux": {
            "handler": f"0x{cfg['extern_handler']:x}",
            "plus_style_0x13_through_0x1b_prefix_verified": extern_prefix_ok,
            "implemented_range_if_verified": ["0x13", "0x1b"] if extern_prefix_ok else None,
        },
        "raw_spi_read": {
            "wrapper": f"0x{cfg['flash_read']:x}",
            "direct_bl_xref_count": len(flash_xrefs),
            "direct_bl_xrefs": [f"0x{x:x}" for x in flash_xrefs],
            "direct_xrefs_inside_spp_dispatch_region": [f"0x{x:x}" for x in spp_flash_xrefs],
        },
        "known_indirect_flash_paths": _plus_indirect_flash_paths(name, cfg, dm),
        "_dispatch_map": dm,
    }


def _verified_bl(data: bytes, callsite: int, expected: int, label: str) -> None:
    actual = thumb_bl_target(data, callsite)
    if actual != expected:
        got = "none" if actual is None else f"0x{actual:x}"
        raise ValueError(f"{label}: BL target drift at 0x{callsite:x}: {got} != 0x{expected:x}")


def _plus_indirect_flash_paths(name: str, cfg: dict[str, Any], dm: dict[int, int]) -> dict[str, Any]:
    """Pin shortest known SPP -> fixed storage helper -> SPI-read chains.

    These are *not* arbitrary readback primitives.  The purpose of recording them is
    precisely to prevent the weaker "zero direct SPP->SPI edge" result from being
    misread as "SPP never causes an internal flash read".  We verify the command
    handler, call sites, BL targets, and fixed immediate selector arguments from the
    preserved Plus bytes.  Broader transitive/data-flow reachability remains a
    separate question.
    """
    if name not in ("flag42_v42016", "flag60_v60014"):
        return {"applicable": False, "reason": "calibrated only on preserved Ditoo Plus branches"}
    data = cfg["path"].read_bytes()
    flash = cfg["flash_read"]

    # Stable low-level helpers in both Plus branches.
    config_blob_read = 0x18604
    config_byte_read = 0x18B64
    _verified_bl(data, 0x1866E, flash, f"{name} config_blob_read->SPI")
    _verified_bl(data, 0x18BC0, flash, f"{name} config_byte_read->SPI")

    # 0x80 and 0x81 both enter the same storage helper with fixed immediates
    # r2=72, r1=0, r0=0.  No caller-supplied flash address/length appears here.
    fixed_blob_args = bytes.fromhex("482200210020")
    paths: list[dict[str, Any]] = []
    for cmd, handler, callsite in ((0x80, 0x12180, 0x12186), (0x81, 0x121C6, 0x121CC)):
        if dm[cmd] != handler:
            raise ValueError(f"{name}: command 0x{cmd:02x} handler drift")
        if data[callsite - len(fixed_blob_args):callsite] != fixed_blob_args:
            raise ValueError(f"{name}: command 0x{cmd:02x} fixed storage arguments drift")
        _verified_bl(data, callsite, config_blob_read, f"{name} command 0x{cmd:02x}")
        paths.append({
            "command": f"0x{cmd:02x}",
            "handler": f"0x{handler:x}",
            "spp_callsite": f"0x{callsite:x}",
            "chain": [f"0x{config_blob_read:x}", f"0x{flash:x}"],
            "fixed_immediates_before_helper": {"r0": 0, "r1": 0, "r2": 72},
            "classification": "fixed internal storage/config read path; not an arbitrary-address flash export",
        })

    # Command 0x27, subcase payload[1]==0, zeroes a local buffer then invokes
    # the byte/config helper with immediate r0=28 while r1 remains zero.  The
    # helper itself performs a one-byte raw SPI read at 0x18bc0.
    if dm[0x27] != 0x10BF2:
        raise ValueError(f"{name}: command 0x27 handler drift")
    if data[0x10BF2:0x10C02] != bytes.fromhex("7878002807d11fa8002102c002c01c20"):
        raise ValueError(f"{name}: command 0x27 read-subcase prefix drift")
    _verified_bl(data, 0x10C02, config_byte_read, f"{name} command 0x27")
    paths.append({
        "command": "0x27",
        "handler": "0x10bf2",
        "spp_callsite": "0x10c02",
        "subcase": "payload[1] == 0",
        "chain": [f"0x{config_byte_read:x}", f"0x{flash:x}"],
        "fixed_immediates_before_helper": {"r0": 28, "r1": 0},
        "raw_spi_read_length_inside_helper_bytes": 1,
        "classification": "fixed internal config-byte read path; not an arbitrary-address flash export",
    })

    # 0xba and 0x6e call a branch-shifted state helper.  That helper's relevant
    # branch calls the same config/blob reader with r0=22,r1=0,r2=0.  Locate the
    # exact inner call from its fixed argument prefix rather than assuming the
    # flag42 high-address relocation applies to flag60.
    state_helper = thumb_bl_target(data, 0x1111E)
    if state_helper is None or thumb_bl_target(data, 0x112AE) != state_helper:
        raise ValueError(f"{name}: 0xba/0x6e state-helper identity drift")
    fixed_state_args = bytes.fromhex("002200211620")  # r2=0,r1=0,r0=22
    inner_candidates = []
    for off in range(state_helper, min(len(data) - 4, state_helper + 0xA0), 2):
        if data[off - len(fixed_state_args):off] == fixed_state_args and thumb_bl_target(data, off) == config_blob_read:
            inner_candidates.append(off)
    if len(inner_candidates) != 1:
        raise ValueError(f"{name}: expected one fixed record-22 call in state helper, got {inner_candidates}")
    inner = inner_candidates[0]
    for cmd, handler, callsite in ((0xBA, 0x110E6, 0x1111E), (0x6E, 0x11278, 0x112AE)):
        if dm[cmd] != handler:
            raise ValueError(f"{name}: command 0x{cmd:02x} handler drift")
        _verified_bl(data, callsite, state_helper, f"{name} command 0x{cmd:02x}")
        paths.append({
            "command": f"0x{cmd:02x}",
            "handler": f"0x{handler:x}",
            "spp_callsite": f"0x{callsite:x}",
            "chain": [f"0x{state_helper:x}", f"0x{config_blob_read:x}", f"0x{flash:x}"],
            "inner_fixed_storage_callsite": f"0x{inner:x}",
            "inner_fixed_immediates": {"r0": 22, "r1": 0, "r2": 0},
            "classification": "state-management path reaches a fixed internal storage record; not an arbitrary-address flash export",
        })

    return {
        "applicable": True,
        "finding": "SPP can indirectly trigger internal SPI reads, but the shortest verified chains use fixed internal selectors rather than caller-selected flash addresses",
        "paths": paths,
        "scope_limit": "These pinned shortest chains do not close every deeper SPP helper/data-flow path; transitive semantic reachability remains SFR-1.",
    }


def _byte_similarity(a: bytes, b: bytes) -> dict[str, Any]:
    if len(a) != len(b):
        raise ValueError("similarity regions must be equal-sized")
    same = sum(x == y for x, y in zip(a, b))
    return {"bytes": len(a), "same": same, "percent": round(100.0 * same / len(a), 3)}


def build_report() -> dict[str, Any]:
    branches = {name: _branch_report(name, cfg) for name, cfg in BRANCHES.items()}
    p42 = branches["flag42_v42016"]
    p60 = branches["flag60_v60014"]
    orig = branches["original_ditoo_flag46_v46032"]

    # Fail closed on the core exact-Plus calibration before publishing conclusions.
    for plus_name in ("flag42_v42016", "flag60_v60014"):
        br = branches[plus_name]
        dm = br["_dispatch_map"]
        for cmd, expected in EXPECTED_PLUS_TARGETS.items():
            if dm[cmd] != expected:
                raise ValueError(f"{plus_name}: command 0x{cmd:02x} target drift")
        if any(dm[c] != BRANCHES[plus_name]["default_handler"] for c in range(0x93, 0x97)):
            raise ValueError(f"{plus_name}: SYS update family no longer maps to default")
        if br["raw_spi_read"]["direct_bl_xref_count"] != 63:
            raise ValueError(f"{plus_name}: raw SPI-read xref count drift")
        if br["raw_spi_read"]["direct_xrefs_inside_spp_dispatch_region"]:
            raise ValueError(f"{plus_name}: raw SPI-read became directly reachable from SPP region")
        if not br["extern_mux"]["plus_style_0x13_through_0x1b_prefix_verified"]:
            raise ValueError(f"{plus_name}: EXTERN mux shape drift")

    dm42: dict[int, int] = p42["_dispatch_map"]
    dm60: dict[int, int] = p60["_dispatch_map"]
    dmo: dict[int, int] = orig["_dispatch_map"]
    noop42 = BRANCHES["flag42_v42016"]["default_handler"]
    noopo = BRANCHES["original_ditoo_flag46_v46032"]["default_handler"]

    exact_plus_target_diffs = {
        f"0x{cmd:02x}": {"flag42": f"0x{dm42[cmd]:x}", "flag60": f"0x{dm60[cmd]:x}"}
        for cmd in dm42 if dm42[cmd] != dm60[cmd]
    }
    real42_only_vs_original = [
        f"0x{cmd:02x}" for cmd in dm42 if dm42[cmd] != noop42 and dmo[cmd] == noopo
    ]
    real_original_only = [
        f"0x{cmd:02x}" for cmd in dm42 if dm42[cmd] == noop42 and dmo[cmd] != noopo
    ]

    A = BRANCHES["flag42_v42016"]["path"].read_bytes()
    B = BRANCHES["flag60_v60014"]["path"].read_bytes()
    regions = {
        "spp_dispatch_monolith": (0x103E0, 0x1271E),
        "spp_jump_table": (0x105E8, 0x107DE),
        "extern_mux": (0x10A88, 0x10D6C),
        "hot_update": (0x10E78, 0x11020),
        "app_update": (0x110CC, 0x11278),
        "flash_wrappers": (0x1BE82, 0x1BF00),
    }
    similarities = {
        name: {"start": f"0x{s:x}", "end": f"0x{e:x}", **_byte_similarity(A[s:e], B[s:e])}
        for name, (s, e) in regions.items()
    }

    for br in branches.values():
        br.pop("_dispatch_map", None)

    return {
        "schema_version": 2,
        "kind": "offline_stock_software_recovery_surface",
        "ok": True,
        "safety": {
            "offline_only": True,
            "device_io": False,
            "packet_generation": False,
            "firmware_mutation": False,
        },
        "branches": branches,
        "comparative": {
            "flag42_vs_flag60_exact_dispatch_target_equal": sum(dm42[c] == dm60[c] for c in dm42),
            "dispatch_entry_count": len(dm42),
            "flag42_vs_flag60_target_differences": exact_plus_target_diffs,
            "flag42_vs_flag60_region_similarity": similarities,
            "flag42_plus_vs_original_ditoo": {
                "commands_default_in_both": sum(dm42[c] == noop42 and dmo[c] == noopo for c in dm42),
                "commands_real_in_both": sum(dm42[c] != noop42 and dmo[c] != noopo for c in dm42),
                "real_flag42_only": real42_only_vs_original,
                "real_original_only": real_original_only,
            },
        },
        "conclusions": {
            "sys_update_0x93_through_0x96": "default/error handler on both preserved Ditoo Plus branches",
            "app_update_0x98_0x99": "real inbound update-info/chunk handlers; not a stock flash-readback surface",
            "hot_update_0x9b_0x9d_0x9e_0x9f": "real update-content handlers; no direct raw-SPI-read edge from SPP dispatcher region",
            "extern_0xbd": "exact Plus mux shape implements only subcommands 0x13..0x1b; wider app enum does not imply firmware handlers",
            "raw_spi_read": "63 direct callers in each preserved Plus branch; zero direct callers inside the SPP dispatcher/handler region",
            "indirect_flash_reads": "verified stock SPP paths do trigger internal SPI reads via fixed config/state selectors (0x27,0x80,0x81,0x6e,0xba); none of the pinned shortest chains exposes a caller-selected flash address",
            "scope_limit": "pinned shortest-chain evidence does not prove absence of every deeper helper/data-flow path; SFR-1 remains open",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit full JSON report")
    ap.add_argument("--write", type=Path, help="write JSON report to this path")
    ap.add_argument("--selfcheck", action="store_true", help="build report and print a compact PASS marker")
    args = ap.parse_args()
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
    if args.json:
        print(text, end="")
    if args.selfcheck:
        print("DITOO_SOFTWARE_RECOVERY_SURFACE=PASS")
        print("PLUS_RAW_SPI_READ_DIRECT_XREFS=63,63")
        print("PLUS_SPP_DIRECT_FLASH_READ_XREFS=0,0")
        print("SYS_0X93_0X96=DEFAULT_BOTH_PLUS_BRANCHES")
    if not (args.json or args.selfcheck or args.write):
        print("DITOO_SOFTWARE_RECOVERY_SURFACE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
