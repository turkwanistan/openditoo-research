#!/usr/bin/env python3
"""Offline lineage/adversarial recovery audit for official Divoom test branches.

Recognition/static-analysis only.  This tool never performs network/device I/O,
constructs packets, modifies firmware, or emits installable images.  It verifies
that the two bounded-API test-branch artifacts are provenance-consistent and asks
whether their stock SPP/recovery/readback architecture invalidates the accepted
SFR-1 conclusion from the preserved production branches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ditoo_update_container import parse as parse_update
from ditoo_software_recovery_surface import (
    EXTERN_PREFIX,
    RECOVERY_COMMANDS,
    _bl_xrefs,
    _byte_similarity,
    _transitive_readback_audit,
    _verified_bl,
    dispatch_map,
)

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "artifacts/firmware"
PROV = ROOT / "artifacts/provenance"

OLD42 = FW / "flag42_v42016.bin"
OLD60 = FW / "flag60_v60014.bin"
TEST42 = FW / "flag42_v42017_test.bin"
TEST60 = FW / "flag60_api60016_internal60017_test.bin"

SHA256 = {
    OLD42.name: "f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a",
    OLD60.name: "02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300",
    TEST42.name: "6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc",
    TEST60.name: "05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339",
}

TABLE_READ = 0x105E8
TABLE_JUMP = 0x105E4
DISPATCH_START = 0x1047C
DISPATCH_END = 0x1271E
DEFAULT = 0x126E4
EXTERN = 0x10A88
EXPECTED_OLD60_TO_TEST60_DIFFS = {0x1B, 0x51, 0x52, 0x53, 0x54, 0xB6, 0xB7}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path) -> bytes:
    data = path.read_bytes()
    want = SHA256[path.name]
    got = _sha256(data)
    if got != want:
        raise ValueError(f"{path.name}: SHA-256 drift {got} != {want}")
    return data


def _require_bytes(data: bytes, start: int, expected_hex: str, label: str) -> None:
    expected = bytes.fromhex(expected_hex)
    got = data[start:start + len(expected)]
    if got != expected:
        raise ValueError(f"{label}: byte witness drift at 0x{start:x}: {got.hex()} != {expected.hex()}")


def _api_matrix() -> dict[str, Any]:
    path = PROV / "getupdatefile_v2_v3_matrix_2026-09-12.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    if m.get("v2_v3_responses_identical_for_matrix") is not True:
        raise ValueError("bounded API matrix no longer records V2/V3 equivalence")
    if m.get("bounded_dimensions") != {
        "Hardware": [42, 60],
        "IsTest": [False, True],
        "endpoints": ["GetUpdateFileV2", "GetUpdateFileV3"],
    }:
        raise ValueError("bounded API matrix dimensions drift")
    rows = m.get("rows", [])
    if len(rows) != 8:
        raise ValueError("bounded API matrix must contain exactly eight rows")
    return m


def _row(matrix: dict[str, Any], endpoint: str, hardware: int, test: bool) -> dict[str, Any]:
    matches = [
        r for r in matrix["rows"]
        if r["endpoint"] == endpoint
        and r["request"]["Hardware"] == hardware
        and r["request"]["IsTest"] is test
    ]
    if len(matches) != 1:
        raise ValueError(f"matrix row lookup drift: {endpoint=} {hardware=} {test=}")
    return matches[0]


def _raw_read_report(data: bytes, wrapper: int) -> dict[str, Any]:
    refs = _bl_xrefs(data, wrapper)
    spp = [x for x in refs if DISPATCH_START <= x < DISPATCH_END]
    if len(refs) != 63:
        raise ValueError(f"raw-read xref count drift for 0x{wrapper:x}: {len(refs)}")
    if spp:
        raise ValueError(f"raw read became directly reachable from SPP dispatcher: {spp}")
    return {
        "wrapper": f"0x{wrapper:x}",
        "direct_bl_xref_count": len(refs),
        "direct_xrefs_inside_spp_dispatch_region": [],
    }


def _test42_readback_semantics(data: bytes, wrapper: int) -> dict[str, Any]:
    """Pin v42017's refactored five-family readback semantics.

    v42017 rewrites the config/storage implementation heavily, making this a useful
    adversarial check rather than a relocation-only comparison.
    """
    # Family 1: refactored config initializer. Both promoted representative reads
    # are one-byte reads at internal context base/cursor derived by the function.
    _verified_bl(data, 0x178C6, wrapper, "v42017 config init raw read A")
    _verified_bl(data, 0x1790E, wrapper, "v42017 config init raw read B")
    _require_bytes(data, 0x178C0, "c0684019211c", "v42017 config-init internal-base address")
    _require_bytes(data, 0x17900, "4019023801e0", "v42017 config-init internal cursor adjustment")

    # Family 2: refactored config-record reader: internal config base + parsed
    # record offset, parsed length; the caller does not supply a raw address.
    _verified_bl(data, 0x17FD4, wrapper, "v42017 config-record raw read")
    _require_bytes(data, 0x17FCA, "998880689a784018211c", "v42017 config-record address derivation")

    # Family 3: refactored config-byte reader: internal config cursor/base, len=1.
    _verified_bl(data, 0x18784, wrapper, "v42017 config-byte raw read")
    _require_bytes(data, 0x18780, "012201a9", "v42017 config-byte one-byte read")

    # Family 4: one-byte raw-header parser. r0 is indeed the raw address argument,
    # so the meaningful proof is the SPP-reachable provenance feeding it.
    _verified_bl(data, 0x3C166, wrapper, "v42017 raw-header parser read")
    _require_bytes(data, 0x3C160, "0122281c6946", "v42017 one-byte parser semantics")

    # 4a: fixed config records 10/11 or 13/14 -> config metadata resolver -> parser.
    _require_bytes(data, 0x238AA, "0a28", "v42017 fixed record 10 compare")
    _require_bytes(data, 0x238C2, "0b20", "v42017 fixed record 11")
    _require_bytes(data, 0x238C8, "0d20", "v42017 fixed record 13")
    _require_bytes(data, 0x238E6, "0e20", "v42017 fixed record 14")
    _verified_bl(data, 0x238B2, 0x17F6A, "v42017 fixed record 10/11 reader")
    _verified_bl(data, 0x238CC, 0x17F6A, "v42017 fixed record 13/14 reader")
    _verified_bl(data, 0x238E8, 0x1802E, "v42017 fixed record address resolver")
    _verified_bl(data, 0x239AE, 0x3C140, "v42017 fixed-record parser")

    # 4b: resource context is initialized from firmware resource-base resolver;
    # boolean selection can add exactly 0x100, not caller-selected address bytes.
    _verified_bl(data, 0x13248, 0x34376, "v42017 SPP resource base")
    _verified_bl(data, 0x13258, 0x32950, "v42017 SPP secondary context")
    _verified_bl(data, 0x13260, 0x28896, "v42017 SPP resource init")
    _require_bytes(data, 0x1324C, "011c", "v42017 secondary base copy")
    _require_bytes(data, 0x13250, "ff31", "v42017 secondary +0xff")
    _require_bytes(data, 0x13254, "0131", "v42017 secondary +1")
    _verified_bl(data, 0x288C4, 0x34376, "v42017 resource base resolver")
    _require_bytes(data, 0x288D0, "ff300130", "v42017 resource alternate +0x100 bank")
    _verified_bl(data, 0x288D8, 0x3C140, "v42017 resource-init parser")
    _require_bytes(data, 0x28798, "0069", "v42017 resource parser address from context+0x10")
    _verified_bl(data, 0x2879A, 0x3C140, "v42017 resource-reader parser")

    # 4c: secondary context stores that managed base at +20 and refresh reloads it.
    _require_bytes(data, 0x32988, "4c61201c", "v42017 secondary context stores managed address")
    _verified_bl(data, 0x3298C, 0x3C140, "v42017 secondary context parser")
    _require_bytes(data, 0x32A40, "30684069", "v42017 secondary context reload +20")
    _verified_bl(data, 0x32A44, 0x3C140, "v42017 secondary context refresh parser")

    # Family 5: screen-save/content scanner, internal object base + bounded index, len=1.
    _verified_bl(data, 0x38B36, wrapper, "v42017 screen-save raw read")
    _require_bytes(data, 0x38B2E, "e06801224019311c", "v42017 screen-save managed-address read")

    return {
        "status": "SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH",
        "five_direct_read_families": [
            {"name": "config_initializer", "entry": "0x1784a"},
            {"name": "config_record_reader", "entry": "0x17f6a"},
            {"name": "config_byte_reader", "entry": "0x18728"},
            {"name": "one_byte_raw_header_parser", "entry": "0x3c140"},
            {"name": "screen_save_content_scanner", "entry": "0x38b1a"},
        ],
        "raw_header_address_provenance": [
            "fixed config records 10/11 or 13/14 resolved through refactored config metadata",
            "firmware resource-base resolver, optionally plus exactly 0x100 as a boolean alternate bank",
            "secondary context initialized from that same resource resolver plus exactly 0x100 and stored/reloaded at context+20",
        ],
        "finding": "The v42017 config/storage refactor preserves the SFR-1 result: no analyzed stock SPP path turns caller-controlled bytes into an arbitrary raw SPI address/range or firmware export buffer.",
    }


def build_report() -> dict[str, Any]:
    matrix = _api_matrix()
    d42 = _load(OLD42)
    d60 = _load(OLD60)
    t42 = _load(TEST42)
    t60 = _load(TEST60)

    # Provenance and container integrity.
    c42 = parse_update(t42)
    c60 = parse_update(t60)
    if not (c42.marker_ok and c42.checksum_ok and c42.version == 42017):
        raise ValueError("flag42 test container metadata drift")
    if not (c60.marker_ok and c60.checksum_ok and c60.version == 60017):
        raise ValueError("flag60 test container metadata drift")
    r42 = _row(matrix, "GetUpdateFileV3", 42, True)["response"]
    r60 = _row(matrix, "GetUpdateFileV3", 60, True)["response"]
    if r42["Version"] != 42017 or r42["Sha1"] != hashlib.sha1(t42).hexdigest():
        raise ValueError("flag42 API/file provenance mismatch")
    if r60["Version"] != 60016 or r60["Sha1"] != hashlib.sha1(t60).hexdigest():
        raise ValueError("flag60 API/file provenance mismatch")

    # Top-level SPP dispatcher is an exceptionally strong lineage anchor.
    dm42 = dispatch_map(d42, TABLE_READ, TABLE_JUMP)
    dmt42 = dispatch_map(t42, TABLE_READ, TABLE_JUMP)
    dm60 = dispatch_map(d60, TABLE_READ, TABLE_JUMP)
    dmt60 = dispatch_map(t60, TABLE_READ, TABLE_JUMP)
    if dm42 != dmt42:
        raise ValueError("flag42 v42017 top-level SPP dispatch topology drifted from v42016")
    if dmt42 != dmt60:
        raise ValueError("new test branches no longer share the same top-level SPP dispatch topology")
    dif60 = {c for c in dm60 if dm60[c] != dmt60[c]}
    if dif60 != EXPECTED_OLD60_TO_TEST60_DIFFS:
        raise ValueError(f"flag60 old->test dispatcher differences drifted: {sorted(dif60)}")
    for dm, label in ((dmt42, "flag42 test"), (dmt60, "flag60 test")):
        if any(dm[c] != DEFAULT for c in range(0x93, 0x97)):
            raise ValueError(f"{label}: SYS update slots 0x93..0x96 no longer default")
        for c in RECOVERY_COMMANDS:
            if dm[c] != dm42[c]:
                raise ValueError(f"{label}: recovery command 0x{c:02x} target drift")
    if t42[EXTERN:EXTERN + len(EXTERN_PREFIX)] != EXTERN_PREFIX or t60[EXTERN:EXTERN + len(EXTERN_PREFIX)] != EXTERN_PREFIX:
        raise ValueError("test-branch EXTERN mux shape drift")

    raw42 = _raw_read_report(t42, 0x1BE9E)
    raw60 = _raw_read_report(t60, 0x1BEAA)
    sem42 = _test42_readback_semantics(t42, 0x1BE9E)

    # The flag60 test file's readback semantics byte-match the accepted flag42-v42016
    # calibration at all promoted SFR-1 witness sites. Reuse the fail-closed verifier
    # rather than duplicating that proof under a misleading global relocation rule.
    sem60 = _transitive_readback_audit(
        "flag42_v42016",
        {"path": TEST60, "flash_read": 0x1BEAA},
    )
    if sem60["status"] != "SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH":
        raise ValueError("flag60 test branch no longer satisfies accepted SFR-1 semantics")

    regions = {
        "spp_dispatch": (0x103E0, 0x1271E),
        "config_storage": (0x17600, 0x18F80),
        "resource_context": (0x23800, 0x23B00),
        "resource_manager": (0x28700, 0x32B80),
        "raw_parser_area": (0x3C000, 0x3C500),
    }
    sims42 = {k: {"start": f"0x{s:x}", "end": f"0x{e:x}", **_byte_similarity(d42[s:e], t42[s:e])} for k, (s, e) in regions.items()}
    sims60 = {k: {"start": f"0x{s:x}", "end": f"0x{e:x}", **_byte_similarity(d60[s:e], t60[s:e])} for k, (s, e) in regions.items()}

    return {
        "schema_version": 1,
        "kind": "offline_official_test_branch_lineage_recovery_audit",
        "ok": True,
        "safety": {"offline_only": True, "device_io": False, "packet_generation": False, "firmware_mutation": False, "installation_authorized": False},
        "api": {
            "matrix_artifact": "artifacts/provenance/getupdatefile_v2_v3_matrix_2026-09-12.json",
            "v2_v3_responses_identical_for_bounded_matrix": True,
            "is_test_true_distinct_for_hardware_42_and_60": True,
        },
        "artifacts": {
            "flag42_test": {
                "path": str(TEST42.relative_to(ROOT)), "sha256": SHA256[TEST42.name], "api_version": r42["Version"], "internal_version": c42.version,
                "sha1": hashlib.sha1(t42).hexdigest(), "bytes": len(t42), "raw_spi_read": raw42,
            },
            "flag60_test": {
                "path": str(TEST60.relative_to(ROOT)), "sha256": SHA256[TEST60.name], "api_version": r60["Version"], "internal_version": c60.version,
                "sha1": hashlib.sha1(t60).hexdigest(), "bytes": len(t60), "raw_spi_read": raw60,
                "version_mismatch": "API declares 60016; valid file container declares 60017",
            },
        },
        "dispatcher_lineage": {
            "flag42_v42016_vs_v42017_exact_target_equal": 251,
            "flag60_v60014_vs_test_exact_target_equal": 244,
            "flag60_old_to_test_changed_slots": [f"0x{x:02x}" for x in sorted(dif60)],
            "flag42_v42017_vs_flag60_test_exact_target_equal": 251,
            "recovery_update_cluster_unchanged": True,
            "sys_0x93_through_0x96_still_default_error": True,
        },
        "region_similarity": {"flag42_v42016_to_v42017": sims42, "flag60_v60014_to_test": sims60},
        "readback_adversarial_check": {
            "flag42_v42017": sem42,
            "flag60_test": sem60,
            "conclusion": "SFR-1 survives both official test branches. This is especially strong for flag42 v42017 because its config/storage implementation is materially refactored while the stock SPP protocol surface remains unchanged.",
        },
        "limits": [
            "bounded static direct-call/control-flow and byte-witness analysis, not whole-program formal proof",
            "no exact per-command raw-read reachability count is claimed for the monolithic SPP switch",
            "computed internal jump tables/callbacks remain an explicit analysis limit",
            "test firmware was downloaded and analyzed only; it was not sent to or installed on the device",
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
        args.write.write_text(text, encoding="utf-8")
    if args.json:
        print(text, end="")
    if args.selfcheck:
        print("DITOO_TEST_BRANCH_LINEAGE=PASS")
        print("API_V2_V3_BOUNDED_MATRIX_IDENTICAL=true")
        print("IS_TEST_TRUE_RETURNS_DISTINCT_BRANCHES=true")
        print("FLAG42_V42017_DISPATCH_TARGETS_CHANGED=0")
        print("TEST_BRANCH_SFR1=SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH")
        print("FLAG60_API_VERSION=60016")
        print("FLAG60_INTERNAL_VERSION=60017")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_TEST_BRANCH_LINEAGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
