#!/usr/bin/env python3
"""Offline VRAM-8C fixed resident image + bounded installer model.

Builds one exact inert stage-1 image and one exact Thumb installer stage-0 inside the
already-proven 1088-byte controlled source.  The design exposes no host-selected address,
length, entry point, chunks, or generic call surface.  It is preparation only: no live
manifest/grant is created and no Bluetooth/device I/O occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from ditoo_tier2_placement import BRANCHES, FW
from ditoo_vram8c_context import build_report as build_context_report
from ditoo_vram3_execution_model import build_report as build_vram3_report

ARTIFACT = ROOT / "artifacts/analysis/volatile_ram_api_vram8c_installer.json"
STAGE0_BIN = ROOT / "artifacts/analysis/volatile_ram_api_vram8c_installer_stage0.bin"
STAGE1_BIN = ROOT / "artifacts/analysis/volatile_ram_api_vram8c_stage1_v0.bin"

CONTROLLED_SOURCE = 0x00804778
SOURCE_LENGTH = 1088
RUNTIME50_BASE = 0x00804B80
RUNTIME50_SOURCE_OFFSET = RUNTIME50_BASE - CONTROLLED_SOURCE
RUNTIME50_MODEL_OFFSET = 0x08
CALLBACK_SOURCE_OFFSET = RUNTIME50_SOURCE_OFFSET + 0x34

# Fresh installer stage-0.  8B uses 0x00804901, so 8D must not rewrite/execute that line.
STAGE0_SOURCE = 0x00804A80
STAGE0_ENTRY = STAGE0_SOURCE | 1
STAGE0_SOURCE_OFFSET = STAGE0_SOURCE - CONTROLLED_SOURCE
STAGE0_MAX_BYTES = RUNTIME50_BASE - STAGE0_SOURCE

# The old 8A/8B code area is data-only for this future gate; it is copied to fresh heap RAM.
STAGE1_SOURCE = 0x00804900
STAGE1_SOURCE_OFFSET = STAGE1_SOURCE - CONTROLLED_SOURCE
STAGE1_IMAGE_LENGTH = 0x50
STAGE1_ENTRY_OFFSET = 0x20
STAGE1_ENTRY_DELTA_THUMB = STAGE1_ENTRY_OFFSET | 1
ALLOCATION_REQUEST = STAGE1_IMAGE_LENGTH

FWL_MALLOC_THUMB = 0x0840BFBD
FWL_FREE_THUMB = 0x0840BFCF
INVALIDATE_I_CACHE_ARM = 0x00800CE0
ENERGY_STATE_GLOBAL = 0x008030F0

PRE_GUARD = 0x31445247   # "GRD1"
MAGIC = 0x3152444F       # "ODR1"
ABI_AND_HEADER = 0x00200001  # abi u16=1, header_len u16=0x20
BUILD_ID = 0x00080001
LENGTH_AND_ENTRY = (STAGE1_ENTRY_OFFSET << 16) | STAGE1_IMAGE_LENGTH
POST_GUARD = 0x32445247  # "GRD2"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(word: int) -> bytes:
    return struct.pack("<H", word & 0xFFFF)


class ThumbBuilder:
    """Tiny fail-closed encoder for the small Thumb-1 subset used by this model."""

    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.branch_fixups: list[tuple[int, str, int | None]] = []
        self.literal_fixups: list[tuple[int, int, str]] = []
        self.literal_values: dict[str, int] = {}
        self.listing: list[dict[str, Any]] = []

    @property
    def off(self) -> int:
        return len(self.code)

    def emit16(self, word: int, text: str) -> None:
        off = self.off
        self.code += _u16(word)
        self.listing.append({"offset": off, "size": 2, "instruction": text})

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label {name}")
        self.labels[name] = self.off

    def bcond(self, cond: int, label: str, text: str) -> None:
        off = self.off
        self.emit16(0, text)
        self.branch_fixups.append((off, label, cond))

    def b(self, label: str, text: str) -> None:
        off = self.off
        self.emit16(0, text)
        self.branch_fixups.append((off, label, None))

    def ldr_lit(self, rd: int, name: str, value: int) -> None:
        if not (0 <= rd <= 7):
            raise ValueError("literal rd out of range")
        if name in self.literal_values and self.literal_values[name] != value:
            raise ValueError(f"literal collision: {name}")
        self.literal_values[name] = value
        off = self.off
        self.emit16(0, f"LDR r{rd}, ={name}")
        self.literal_fixups.append((off, rd, name))

    def finalize(self) -> tuple[bytes, list[dict[str, Any]], dict[str, int]]:
        while len(self.code) % 4:
            self.emit16(0x46C0, "NOP (literal alignment)")

        literal_offsets: dict[str, int] = {}
        for name, value in self.literal_values.items():
            literal_offsets[name] = len(self.code)
            off = len(self.code)
            self.code += struct.pack("<I", value)
            self.listing.append({"offset": off, "size": 4, "instruction": f".word {name}=0x{value:08x}"})

        for off, rd, name in self.literal_fixups:
            target = literal_offsets[name]
            pc = (off + 4) & ~3
            delta = target - pc
            if delta < 0 or delta % 4 or delta // 4 > 0xFF:
                raise ValueError(f"literal out of range: {name} delta={delta}")
            word = 0x4800 | (rd << 8) | (delta // 4)
            self.code[off:off + 2] = _u16(word)

        for off, label, cond in self.branch_fixups:
            if label not in self.labels:
                raise ValueError(f"unknown label {label}")
            target = self.labels[label]
            delta = target - (off + 4)
            if delta % 2:
                raise ValueError("unaligned branch")
            half = delta // 2
            if cond is None:
                if not (-1024 <= half <= 1023):
                    raise ValueError("unconditional branch out of range")
                word = 0xE000 | (half & 0x7FF)
            else:
                if not (0 <= cond <= 0xD) or not (-128 <= half <= 127):
                    raise ValueError("conditional branch out of range")
                word = 0xD000 | (cond << 8) | (half & 0xFF)
            self.code[off:off + 2] = _u16(word)

        listing = []
        for item in self.listing:
            off = item["offset"]
            size = item["size"]
            listing.append({
                "offset": f"0x{off:02x}",
                "bytes": bytes(self.code[off:off + size]).hex(),
                "instruction": item["instruction"],
            })
        return bytes(self.code), listing, literal_offsets


def _mov_reg(b: ThumbBuilder, rd: int, rn: int) -> None:
    b.emit16(0x1C00 | (rn << 3) | rd, f"MOV r{rd}, r{rn} (ADDS #0)")


def _ldr_imm(b: ThumbBuilder, rd: int, rb: int, byte_off: int) -> None:
    if byte_off % 4 or not (0 <= byte_off // 4 <= 31):
        raise ValueError("LDR immediate out of range")
    b.emit16(0x6800 | ((byte_off // 4) << 6) | (rb << 3) | rd,
             f"LDR r{rd}, [r{rb}, #0x{byte_off:x}]")


def _str_imm(b: ThumbBuilder, rd: int, rb: int, byte_off: int) -> None:
    if byte_off % 4 or not (0 <= byte_off // 4 <= 31):
        raise ValueError("STR immediate out of range")
    b.emit16(0x6000 | ((byte_off // 4) << 6) | (rb << 3) | rd,
             f"STR r{rd}, [r{rb}, #0x{byte_off:x}]")


def _strb_imm(b: ThumbBuilder, rd: int, rb: int, byte_off: int) -> None:
    if not (0 <= byte_off <= 31):
        raise ValueError("STRB immediate out of range")
    b.emit16(0x7000 | (byte_off << 6) | (rb << 3) | rd,
             f"STRB r{rd}, [r{rb}, #0x{byte_off:x}]")


def _cmp_reg(b: ThumbBuilder, rn: int, rm: int) -> None:
    b.emit16(0x4280 | (rm << 3) | rn, f"CMP r{rn}, r{rm}")


def _cmp_imm(b: ThumbBuilder, rn: int, imm: int) -> None:
    b.emit16(0x2800 | (rn << 8) | imm, f"CMP r{rn}, #0x{imm:x}")


def _movs(b: ThumbBuilder, rd: int, imm: int) -> None:
    b.emit16(0x2000 | (rd << 8) | imm, f"MOVS r{rd}, #0x{imm:x}")


def _adds_imm(b: ThumbBuilder, rd: int, imm: int) -> None:
    b.emit16(0x3000 | (rd << 8) | imm, f"ADDS r{rd}, #0x{imm:x}")


def _subs_imm(b: ThumbBuilder, rd: int, imm: int) -> None:
    b.emit16(0x3800 | (rd << 8) | imm, f"SUBS r{rd}, #0x{imm:x}")


def _adds_reg(b: ThumbBuilder, rd: int, rn: int, rm: int) -> None:
    b.emit16(0x1800 | (rm << 6) | (rn << 3) | rd, f"ADDS r{rd}, r{rn}, r{rm}")


def _blx_reg(b: ThumbBuilder, rm: int) -> None:
    b.emit16(0x4780 | (rm << 3), f"BLX r{rm}")


def build_stage1() -> tuple[bytes, list[dict[str, Any]]]:
    code = ThumbBuilder()
    # At image+0x20, ADR #0 yields image+0x24. Subtract 0x24 to recover base.
    code.emit16(0xA200, "ADR r2, PC+0")
    _subs_imm(code, 2, 0x24)
    _ldr_imm(code, 3, 2, 0x0C)
    _cmp_imm(code, 3, 0)
    code.bcond(1, "state_done", "BNE state_done")
    _movs(code, 3, 1)
    _str_imm(code, 3, 2, 0x0C)
    code.label("state_done")
    _ldr_imm(code, 3, 2, 0x10)
    _adds_imm(code, 3, 1)
    _str_imm(code, 3, 2, 0x10)
    _movs(code, 1, 1)
    code.ldr_lit(0, "energy_state_global", ENERGY_STATE_GLOBAL)
    _ldr_imm(code, 0, 0, 4)
    _strb_imm(code, 1, 0, 0x0F)
    code.emit16(0x4770, "BX LR")
    code_bytes, code_listing, _ = code.finalize()

    if len(code_bytes) > 0x2C:
        raise ValueError(f"stage1 code grew beyond fixed region: {len(code_bytes)}")

    image = bytearray(b"\xFF" * STAGE1_IMAGE_LENGTH)
    struct.pack_into("<I", image, 0x00, PRE_GUARD)
    struct.pack_into("<I", image, 0x04, MAGIC)
    struct.pack_into("<I", image, 0x08, ABI_AND_HEADER)
    struct.pack_into("<I", image, 0x0C, 0)  # mutable installed state
    struct.pack_into("<I", image, 0x10, 0)  # mutable heartbeat
    struct.pack_into("<I", image, 0x14, BUILD_ID)
    struct.pack_into("<I", image, 0x18, LENGTH_AND_ENTRY)
    struct.pack_into("<I", image, 0x1C, 0)  # additive checksum compensation
    image[STAGE1_ENTRY_OFFSET:STAGE1_ENTRY_OFFSET + len(code_bytes)] = code_bytes
    struct.pack_into("<I", image, 0x4C, POST_GUARD)

    words = list(struct.unpack("<20I", image))
    checksum = (-sum(words)) & 0xFFFFFFFF
    struct.pack_into("<I", image, 0x1C, checksum)
    if sum(struct.unpack("<20I", image)) & 0xFFFFFFFF:
        raise ValueError("stage1 additive checksum construction failed")

    listing = [
        {"offset": "0x00", "bytes": struct.pack("<I", PRE_GUARD).hex(), "instruction": ".word PRE_GUARD"},
        {"offset": "0x04", "bytes": struct.pack("<I", MAGIC).hex(), "instruction": ".word MAGIC ODR1"},
        {"offset": "0x08", "bytes": struct.pack("<I", ABI_AND_HEADER).hex(), "instruction": ".word ABI=1|HEADER_LEN=0x20"},
        {"offset": "0x0c", "bytes": "00000000", "instruction": ".word state=0 (mutable)"},
        {"offset": "0x10", "bytes": "00000000", "instruction": ".word heartbeat=0 (mutable)"},
        {"offset": "0x14", "bytes": struct.pack("<I", BUILD_ID).hex(), "instruction": ".word BUILD_ID"},
        {"offset": "0x18", "bytes": struct.pack("<I", LENGTH_AND_ENTRY).hex(), "instruction": ".word LEN=0x50|ENTRY=0x20"},
        {"offset": "0x1c", "bytes": struct.pack("<I", checksum).hex(), "instruction": ".word additive checksum compensation"},
    ]
    for item in code_listing:
        listing.append({
            "offset": f"0x{STAGE1_ENTRY_OFFSET + int(item['offset'], 16):02x}",
            "bytes": item["bytes"],
            "instruction": item["instruction"],
        })
    listing.append({"offset": "0x4c", "bytes": struct.pack("<I", POST_GUARD).hex(), "instruction": ".word POST_GUARD"})
    return bytes(image), listing


def build_stage0() -> tuple[bytes, list[dict[str, Any]]]:
    b = ThumbBuilder()
    b.emit16(0xB5F8, "PUSH {r3-r7, LR}")  # 24 bytes: preserve SP mod 8
    _mov_reg(b, 4, 1)  # runtime50 base from controlled callback ABI
    b.ldr_lit(5, "stage1_source", STAGE1_SOURCE)

    _ldr_imm(b, 0, 5, 4)
    b.ldr_lit(1, "magic", MAGIC)
    _cmp_reg(b, 0, 1)
    b.bcond(1, "fail", "BNE fail")

    _ldr_imm(b, 0, 5, 8)
    b.ldr_lit(1, "abi_header", ABI_AND_HEADER)
    _cmp_reg(b, 0, 1)
    b.bcond(1, "fail", "BNE fail")

    _ldr_imm(b, 0, 5, 0x18)
    b.ldr_lit(1, "len_entry", LENGTH_AND_ENTRY)
    _cmp_reg(b, 0, 1)
    b.bcond(1, "fail", "BNE fail")

    # Exact fixed-image integrity: unsigned sum of all twenty words must be zero.
    _movs(b, 7, 0)
    _movs(b, 2, STAGE1_IMAGE_LENGTH // 4)
    _mov_reg(b, 3, 5)
    b.label("checksum_loop")
    _ldr_imm(b, 0, 3, 0)
    _adds_imm(b, 3, 4)
    _adds_reg(b, 7, 7, 0)
    _subs_imm(b, 2, 1)
    b.bcond(1, "checksum_loop", "BNE checksum_loop")
    _cmp_imm(b, 7, 0)
    b.bcond(1, "fail", "BNE fail")

    _movs(b, 0, ALLOCATION_REQUEST)
    b.ldr_lit(3, "fwl_malloc", FWL_MALLOC_THUMB)
    _blx_reg(b, 3)
    _cmp_imm(b, 0, 0)
    b.bcond(0, "fail", "BEQ fail")
    _mov_reg(b, 6, 0)

    _mov_reg(b, 3, 5)
    _mov_reg(b, 1, 6)
    _movs(b, 2, STAGE1_IMAGE_LENGTH // 4)
    b.label("copy_loop")
    _ldr_imm(b, 0, 3, 0)
    _adds_imm(b, 3, 4)
    _str_imm(b, 0, 1, 0)
    _adds_imm(b, 1, 4)
    _subs_imm(b, 2, 1)
    b.bcond(1, "copy_loop", "BNE copy_loop")

    _ldr_imm(b, 0, 6, 0)
    b.ldr_lit(1, "pre_guard", PRE_GUARD)
    _cmp_reg(b, 0, 1)
    b.bcond(1, "fail_alloc", "BNE fail_alloc")
    _ldr_imm(b, 0, 6, 0x4C)
    b.ldr_lit(1, "post_guard", POST_GUARD)
    _cmp_reg(b, 0, 1)
    b.bcond(1, "fail_alloc", "BNE fail_alloc")

    # Heap is write-through; invalidate I-cache before executing the freshly copied image.
    b.ldr_lit(3, "invalidate_i_cache_arm", INVALIDATE_I_CACHE_ARM)
    _blx_reg(b, 3)

    _mov_reg(b, 0, 6)
    _adds_imm(b, 0, STAGE1_ENTRY_DELTA_THUMB)
    _str_imm(b, 0, 4, 0x34)  # runtime50 callback becomes fixed resident entry
    _blx_reg(b, 0)            # exact one init/liveness call
    b.emit16(0xBDF8, "POP {r3-r7, PC}")

    b.label("fail_alloc")
    _mov_reg(b, 0, 6)
    b.ldr_lit(3, "fwl_free", FWL_FREE_THUMB)
    _blx_reg(b, 3)

    b.label("fail")
    _movs(b, 0, 0)
    _str_imm(b, 0, 4, 0x34)  # fail closed: no custom callback remains armed
    b.emit16(0xBDF8, "POP {r3-r7, PC}")

    code, listing, _ = b.finalize()
    if len(code) > STAGE0_MAX_BYTES:
        raise ValueError(f"stage0 exceeds fresh pre-runtime50 window: {len(code)} > {STAGE0_MAX_BYTES}")
    return code, listing


def build_source(stage0: bytes, stage1: bytes) -> bytes:
    if STAGE1_SOURCE_OFFSET + len(stage1) > STAGE0_SOURCE_OFFSET:
        raise ValueError("stage1 source overlaps installer stage0")
    if STAGE0_SOURCE_OFFSET + len(stage0) > RUNTIME50_SOURCE_OFFSET:
        raise ValueError("stage0 overlaps runtime50 victim")
    src = bytearray(b"\xFF" * SOURCE_LENGTH)
    src[STAGE1_SOURCE_OFFSET:STAGE1_SOURCE_OFFSET + len(stage1)] = stage1
    src[STAGE0_SOURCE_OFFSET:STAGE0_SOURCE_OFFSET + len(stage0)] = stage0
    src[RUNTIME50_SOURCE_OFFSET] = 0xFF
    src[RUNTIME50_SOURCE_OFFSET + RUNTIME50_MODEL_OFFSET] = 0x22
    src[CALLBACK_SOURCE_OFFSET:CALLBACK_SOURCE_OFFSET + 4] = struct.pack("<I", STAGE0_ENTRY)
    return bytes(src)


def _verify_fresh_installer_span() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, spec in BRANCHES.items():
        p = FW / spec["file"]
        data = p.read_bytes()
        if len(data) != spec["size"] or _sha(data) != spec["sha"]:
            raise ValueError(f"{name}: corpus drift")
        span = data[STAGE0_SOURCE - 0x00800000:RUNTIME50_BASE - 0x00800000]
        refs: dict[str, list[str]] = {}
        for value in (STAGE0_SOURCE, STAGE0_ENTRY, STAGE1_SOURCE):
            needle = struct.pack("<I", value)
            pos = 0
            hits: list[str] = []
            while True:
                hit = data.find(needle, pos)
                if hit < 0:
                    break
                hits.append(hex(hit))
                pos = hit + 1
            refs[hex(value)] = hits
        if span != b"\xFF" * len(span):
            raise ValueError(f"{name}: fresh installer span is not pristine FF")
        if any(refs.values()):
            raise ValueError(f"{name}: fresh installer/source address unexpectedly referenced {refs}")
        rows[name] = {
            "fresh_installer_span_start": hex(STAGE0_SOURCE),
            "fresh_installer_span_end_exclusive": hex(RUNTIME50_BASE),
            "fresh_installer_span_bytes": len(span),
            "pristine_ff": True,
            "raw_pointer_refs": refs,
        }
    return rows


def build_report() -> dict[str, Any]:
    context = build_context_report()
    vram3 = build_vram3_report()
    if not context["promotion"]["vram8c_cache_maintenance_privilege_closed"]:
        raise ValueError("VRAM-8C context/cache privilege gate not closed")
    if not context["promotion"]["vram8c_allocator_abi_closed"]:
        raise ValueError("VRAM-8C allocator ABI gate not closed")
    if vram3["cache_coherency"]["helpers"]["invalidate_i_cache"] != "0xce0":
        raise ValueError("VRAM-3 I-cache helper drift")

    stage1, stage1_listing = build_stage1()
    stage0, stage0_listing = build_stage0()
    source = build_source(stage0, stage1)
    fresh = _verify_fresh_installer_span()

    if len(stage1) != STAGE1_IMAGE_LENGTH:
        raise ValueError("fixed stage1 length drift")
    if sum(struct.unpack("<20I", stage1)) & 0xFFFFFFFF:
        raise ValueError("stage1 integrity sum drift")
    if struct.unpack_from("<I", stage1, 0x00)[0] != PRE_GUARD:
        raise ValueError("pre guard drift")
    if struct.unpack_from("<I", stage1, 0x04)[0] != MAGIC:
        raise ValueError("magic drift")
    if struct.unpack_from("<I", stage1, 0x08)[0] != ABI_AND_HEADER:
        raise ValueError("ABI/header drift")
    if struct.unpack_from("<I", stage1, 0x18)[0] != LENGTH_AND_ENTRY:
        raise ValueError("length/entry drift")
    if struct.unpack_from("<I", stage1, 0x4C)[0] != POST_GUARD:
        raise ValueError("post guard drift")
    if struct.unpack_from("<I", source, CALLBACK_SOURCE_OFFSET)[0] != STAGE0_ENTRY:
        raise ValueError("runtime50 stage0 callback drift")

    return {
        "schema_version": 1,
        "kind": "ditoo_plus_vram8c_fixed_resident_installer",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "bluetooth_opened": False,
            "live_packet_generation": False,
            "runtime_018_touched": False,
            "firmware_or_flash_mutation": False,
            "persistent_mutation": False,
            "live_authority_created": False,
        },
        "fresh_installer_span": fresh,
        "controlled_source": {
            "base": hex(CONTROLLED_SOURCE),
            "length": SOURCE_LENGTH,
            "sha256": _sha(source),
            "stage1_source": hex(STAGE1_SOURCE),
            "stage1_source_offset": hex(STAGE1_SOURCE_OFFSET),
            "stage0_source": hex(STAGE0_SOURCE),
            "stage0_entry": hex(STAGE0_ENTRY),
            "stage0_source_offset": hex(STAGE0_SOURCE_OFFSET),
            "runtime50_source_offset": hex(RUNTIME50_SOURCE_OFFSET),
            "runtime50_model": "0x22",
            "runtime50_callback_source_offset": hex(CALLBACK_SOURCE_OFFSET),
        },
        "stage0_installer": {
            "source": hex(STAGE0_SOURCE),
            "entry": hex(STAGE0_ENTRY),
            "length_bytes": len(stage0),
            "max_pre_runtime50_bytes": STAGE0_MAX_BYTES,
            "bytes_hex": stage0.hex(),
            "sha256": _sha(stage0),
            "stack_frame_bytes": 24,
            "stack_alignment_preserved_mod8": True,
            "fixed_calls": {
                "fwl_malloc_thumb": hex(FWL_MALLOC_THUMB),
                "fwl_free_thumb_failure_only": hex(FWL_FREE_THUMB),
                "invalidate_i_cache_arm": hex(INVALIDATE_I_CACHE_ARM),
                "stage1_entry": "allocation_base + 0x21 only",
            },
            "listing": stage0_listing,
        },
        "stage1_v0": {
            "image_length": len(stage1),
            "allocation_request": ALLOCATION_REQUEST,
            "entry_offset": hex(STAGE1_ENTRY_OFFSET),
            "entry_thumb_delta": hex(STAGE1_ENTRY_DELTA_THUMB),
            "bytes_hex": stage1.hex(),
            "sha256": _sha(stage1),
            "header": {
                "pre_guard": hex(PRE_GUARD),
                "magic": "ODR1",
                "abi_version": 1,
                "header_length": 0x20,
                "state_offset": "0x0c",
                "heartbeat_offset": "0x10",
                "build_id": hex(BUILD_ID),
                "length": STAGE1_IMAGE_LENGTH,
                "entry_offset": hex(STAGE1_ENTRY_OFFSET),
                "checksum": "u32 additive sum of all 20 initial words == 0",
                "post_guard": hex(POST_GUARD),
            },
            "behavior": [
                "self-locate allocation base from PC; ignores caller-provided registers for addressing",
                "set state=1 only if initial state is zero",
                "increment one in-allocation heartbeat on each invocation",
                "set the already-reviewed stock energy-control byte to 1 as the positive 8D liveness marker",
                "return with BX LR; no stock service call and no input interception",
            ],
            "listing": stage1_listing,
        },
        "bounded_installer_proof": {
            "destination": "exact one Fwl_Malloc(0x50) result; host never supplies or influences the address",
            "metadata": "fixed embedded image only; magic/ABI/header/length/entry are exact constants",
            "integrity": "stage0 sums exactly twenty fixed source words; nonzero sum fails before allocation",
            "copy_bounds": "exactly 20 word stores -> allocation_base+0x00..+0x4f; allocation request is exactly 0x50",
            "guard_check": "fixed pre/post guards are re-read from destination before any execution",
            "cache": "write-through heap mapping + fixed privileged ARM I-cache invalidate helper 0x00800ce0 before stage1 execution",
            "entry": "callback field and BLX target are derived only as allocation_base + fixed 0x21",
            "failure_before_allocation": "clear runtime50+0x34 custom callback and return; no copy/execute",
            "failure_after_allocation": "free the exact allocation, clear runtime50+0x34, return; no stage1 execute",
            "success_persistence": "retain allocation for boot session and replace runtime50+0x34 with its fixed stage1 Thumb entry; reboot/power loss removes state",
            "host_selected_address": False,
            "host_selected_length": False,
            "host_selected_entry": False,
            "chunking": False,
            "generic_upload_surface": False,
            "generic_call_surface": False,
        },
        "promotion": {
            "vram8c_callback_context_closed": True,
            "vram8c_allocator_abi_closed": True,
            "vram8c_cache_privilege_closed": True,
            "vram8c_fixed_resident_image_measured": True,
            "vram8c_fixed_resident_image_length": STAGE1_IMAGE_LENGTH,
            "vram8c_bounded_installer_closed_offline": True,
            "vram8c_status": "CLOSED_OFFLINE",
            "vram8d_manifest_may_be_prepared_offline": True,
            "vram8d_live_authorized": False,
            "vram9_authorized": False,
        },
        "method_limits": [
            "The exact purchased unit runs v42012 while preserved exact-model branches are v42016/v42017/v60014/v60017; live 8D remains a separately reviewed exact-unit inference/gate, never automatic authority.",
            "The installer is intentionally single-image and one-allocation. It is not a reusable loader, generic uploader, arbitrary write, or arbitrary call primitive.",
            "The stage1 source uses the previously executed 0x00804900 area only as data. Installer execution moves to pristine unreferenced 0x00804a81 so no rewritten 8B I-cache line is executed.",
            "No VRAM-8D or VRAM-9 packet/manifest authority is created by this offline artifact.",
        ],
    }


def verify_committed() -> tuple[dict[str, Any], bytes, bytes]:
    live = build_report()
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    stage0 = build_stage0()[0]
    stage1 = build_stage1()[0]
    if committed != live:
        raise ValueError("committed VRAM-8C installer artifact drift")
    if STAGE0_BIN.read_bytes() != stage0:
        raise ValueError("committed VRAM-8C stage0 binary drift")
    if STAGE1_BIN.read_bytes() != stage1:
        raise ValueError("committed VRAM-8C stage1 binary drift")
    return live, stage0, stage1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    report = build_report()
    stage0 = build_stage0()[0]
    stage1 = build_stage1()[0]
    if a.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        STAGE0_BIN.write_bytes(stage0)
        STAGE1_BIN.write_bytes(stage1)
    if a.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if a.selfcheck:
        p = report["promotion"]
        print("DITOO_VRAM8C_INSTALLER=PASS")
        print(f"VRAM8C_STAGE0_ENTRY={report['stage0_installer']['entry']}")
        print(f"VRAM8C_STAGE0_BYTES={report['stage0_installer']['length_bytes']}")
        print(f"VRAM8C_STAGE1_BYTES={report['stage1_v0']['image_length']}")
        print(f"VRAM8C_STAGE1_SHA256={report['stage1_v0']['sha256']}")
        print(f"VRAM8C_STATUS={p['vram8c_status']}")
        print("VRAM8D_LIVE_AUTHORIZED=false")
    if not (a.write or a.json or a.selfcheck):
        print("DITOO_VRAM8C_INSTALLER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
