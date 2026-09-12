#!/usr/bin/env python3
"""Small offline Thumb-1/ARMv5T disassembly aid for OpenDitoo firmware research.

This is intentionally a recognition/inspection helper, not a patcher. It decodes the
instruction forms used by the preserved Anyka firmware and annotates PC-relative literals.
Unknown encodings remain explicit ``.hword`` values rather than being guessed.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

DEFAULT_LINK_BASE = 0x08400000


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def decode_thumb_bl(data: bytes, offset: int) -> int | None:
    if offset + 4 > len(data):
        return None
    hi, lo = struct.unpack_from("<HH", data, offset)
    if hi >> 11 != 0b11110 or lo >> 11 != 0b11111:
        return None
    delta = (sign_extend(hi & 0x7FF, 11) << 12) + ((lo & 0x7FF) << 1)
    return offset + 4 + delta


def _reglist(mask: int) -> list[str]:
    return [f"r{i}" for i in range(8) if mask & (1 << i)]


def decode_one(data: bytes, offset: int, *, link_base: int = DEFAULT_LINK_BASE) -> tuple[int, str]:
    if offset + 2 > len(data):
        raise ValueError("truncated halfword")
    h = struct.unpack_from("<H", data, offset)[0]
    target = decode_thumb_bl(data, offset)
    if target is not None:
        return 4, f"bl 0x{target:x}"

    if h >> 13 == 0b000:
        op = (h >> 11) & 3
        if op < 3:
            imm, rs, rd = (h >> 6) & 0x1F, (h >> 3) & 7, h & 7
            return 2, f'{["lsls", "lsrs", "asrs"][op]} r{rd},r{rs},#{imm}'
        immediate, subtract = (h >> 10) & 1, (h >> 9) & 1
        rhs, rs, rd = (h >> 6) & 7, (h >> 3) & 7, h & 7
        return 2, f'{"subs" if subtract else "adds"} r{rd},r{rs},{"#" if immediate else "r"}{rhs}'

    if h >> 13 == 0b001:
        op, rd, imm = (h >> 11) & 3, (h >> 8) & 7, h & 0xFF
        return 2, f'{["movs", "cmp", "adds", "subs"][op]} r{rd},#{imm}'

    if h >> 10 == 0b010000:
        op, rs, rd = (h >> 6) & 0xF, (h >> 3) & 7, h & 7
        names = ["ands", "eors", "lsls", "lsrs", "asrs", "adcs", "sbcs", "rors",
                 "tst", "negs", "cmp", "cmn", "orrs", "muls", "bics", "mvns"]
        return 2, f"{names[op]} r{rd},r{rs}"

    if h >> 10 == 0b010001:
        op = (h >> 8) & 3
        h1, h2 = (h >> 7) & 1, (h >> 6) & 1
        rs, rd = ((h >> 3) & 7) | (h2 << 3), (h & 7) | (h1 << 3)
        if op == 3:
            return 2, f'{"blx" if h1 else "bx"} r{rs}'
        return 2, f'{["add", "cmp", "mov"][op]} r{rd},r{rs}'

    if h >> 11 == 0b01001:
        rd, imm = (h >> 8) & 7, (h & 0xFF) * 4
        pc, literal = (offset + 4) & ~3, ((offset + 4) & ~3) + imm
        suffix = ""
        if literal + 4 <= len(data):
            value = struct.unpack_from("<I", data, literal)[0]
            suffix = f" ; [0x{literal:x}]=0x{value:08x}"
            if link_base <= value < link_base + len(data):
                suffix += f" -> file 0x{value - link_base:x}"
        return 2, f"ldr r{rd},[pc,#{imm}]{suffix}"

    if h >> 12 == 0b0101:
        op, rm, rn, rd = (h >> 9) & 7, (h >> 6) & 7, (h >> 3) & 7, h & 7
        names = ["str", "strh", "strb", "ldrsb", "ldr", "ldrh", "ldrb", "ldrsh"]
        return 2, f"{names[op]} r{rd},[r{rn},r{rm}]"

    if h >> 13 == 0b011:
        byte, load = (h >> 12) & 1, (h >> 11) & 1
        imm, rn, rd = (h >> 6) & 0x1F, (h >> 3) & 7, h & 7
        scale = 1 if byte else 4
        name = ("ldr" if load else "str") + ("b" if byte else "")
        return 2, f"{name} r{rd},[r{rn},#{imm * scale}]"

    if h >> 12 == 0b1000:
        load, imm, rn, rd = (h >> 11) & 1, ((h >> 6) & 0x1F) * 2, (h >> 3) & 7, h & 7
        return 2, f'{"ldrh" if load else "strh"} r{rd},[r{rn},#{imm}]'

    if h >> 12 == 0b1001:
        load, rd, imm = (h >> 11) & 1, (h >> 8) & 7, (h & 0xFF) * 4
        return 2, f'{"ldr" if load else "str"} r{rd},[sp,#{imm}]'

    if h >> 12 == 0b1010:
        sp_base, rd, imm = (h >> 11) & 1, (h >> 8) & 7, (h & 0xFF) * 4
        if sp_base:
            return 2, f"add r{rd},sp,#{imm}"
        pc = (offset + 4) & ~3
        return 2, f"adr r{rd},0x{pc + imm:x}"

    if h & 0xFF00 == 0xB000:
        subtract, imm = (h >> 7) & 1, (h & 0x7F) * 4
        return 2, f'{"sub" if subtract else "add"} sp,#{imm}'

    if (h & 0xFE00) in (0xB400, 0xBC00):
        pop, extra = (h >> 11) & 1, (h >> 8) & 1
        regs = _reglist(h & 0xFF)
        if extra:
            regs.append("pc" if pop else "lr")
        return 2, f'{"pop" if pop else "push"} ' + "{" + ",".join(regs) + "}"

    if h >> 12 == 0b1100:
        load, rb, mask = (h >> 11) & 1, (h >> 8) & 7, h & 0xFF
        return 2, f'{"ldmia" if load else "stmia"} r{rb}!,{{' + ",".join(_reglist(mask)) + "}"

    if h >> 12 == 0b1101:
        cond, imm = (h >> 8) & 0xF, sign_extend(h & 0xFF, 8) << 1
        names = ["beq", "bne", "bcs", "bcc", "bmi", "bpl", "bvs", "bvc",
                 "bhi", "bls", "bge", "blt", "bgt", "ble", "undef", "swi"]
        return 2, f"{names[cond]} 0x{offset + 4 + imm:x}"

    if h >> 11 == 0b11100:
        imm = sign_extend(h & 0x7FF, 11) << 1
        return 2, f"b 0x{offset + 4 + imm:x}"

    return 2, f".hword 0x{h:04x}"


def disassemble(data: bytes, start: int, end: int, *, link_base: int = DEFAULT_LINK_BASE) -> list[str]:
    if not (0 <= start <= end <= len(data)):
        raise ValueError("invalid range")
    out: list[str] = []
    pc = start
    while pc < end:
        size, text = decode_one(data, pc, link_base=link_base)
        raw = data[pc:pc + size].hex()
        out.append(f"{pc:08x}: {raw:<9} {text}")
        pc += size
    return out


def selfcheck() -> None:
    # Known flag42 emitter sequence: movs r0,#0x82 ; bl 0xc6d7c ; pop {r3,r4,r5,pc}
    sample = bytes.fromhex("822074f07cfb38bd")
    assert decode_one(sample, 0, link_base=0)[1] == "movs r0,#130"
    # The BL's absolute target depends on its file offset, so exercise the production decoder separately.
    assert decode_thumb_bl(bytes.fromhex("74f07cfb"), 0) == 0x746FC
    assert decode_one(sample, 6, link_base=0)[1] == "pop {r3,r4,r5,pc}"
    # Negative: a non-BL halfword is not misclassified.
    assert decode_thumb_bl(bytes.fromhex("822038bd"), 0) is None
    print("THUMBV5T_MINIDIS_SELFCHECK=PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", nargs="?")
    ap.add_argument("start", nargs="?")
    ap.add_argument("end", nargs="?")
    ap.add_argument("--link-base", default=hex(DEFAULT_LINK_BASE))
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return 0
    if not (args.firmware and args.start and args.end):
        ap.error("firmware, start and end are required unless --selfcheck is used")
    data = Path(args.firmware).read_bytes()
    for line in disassemble(data, int(args.start, 0), int(args.end, 0), link_base=int(args.link_base, 0)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
