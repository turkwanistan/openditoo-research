#!/usr/bin/env python3
"""Offline parser/validator for the Divoom Ditoo Plus SD update container (UPDATE-R0).

READ-ONLY. This tool inspects a `divoomupdate.bin` candidate and reports, in the firmware's
actual evaluation order, whether each acceptance gate would pass. It NEVER writes a device,
NEVER recomputes a checksum to "fix" a file, and produces no installable package. It is a
review aid so a candidate can be judged byte-for-byte before any (separately authorized) live
use.

Container format (verified against preserved flag42 v42016 and flag60 v60014 — the trailer is
the last 20 bytes of the file):

    [ version : u32 LE ][ "DIVOOMUPDATE" : 12 bytes ][ checksum : u32 LE ]
      file[-20:-16]        file[-16:-4]                 file[-4:]

Acceptance logic, disassembled from `divoom_check_update` (flag42 file 0x8394; link base
0x08400000). Evaluation order and reject points:

  1. MARKER   memcmp(marker, b"DIVOOMUPDATE", 12)                 (0x8744, str@0x8410)
  2. VERSION  reject if installed_version >= candidate_version,   (0x878c-0x879a)
             UNLESS a header flag byte == 0x33 ('3') forces it   (0x8790 beq skip)
  3. CHECKSUM sum(file[:-4]) mod 2**32 == stored u32             (0x87be subs #4; 0x8820 cmp)
  4. WRITE    only then: updater init 0x3a824(mode, data_len, checksum, version)

UPDATE-R1 write topology (flag42 v42016, byte-verified offline): 0x3a824 resolves three named
flash objects with the stock Fwl lookup — BIOS1, BOAR1 and PROG1. The lookup returns each
object's byte capacity and a u16 start-page; flash page size is 256 bytes. For mode=0 the erase
helper 0x3a746 erases BIOS1 in 4 KiB sectors (16 pages, wrapper 0x1beca) and the combined
PROG1+BOAR1 allocation in 64 KiB blocks (256 pages, wrapper 0x1beea). The streaming writer
0x3a4ec maps logical update pages BIOS1 -> BOAR1 -> PROG1 and writes one 256-byte page at a
time through 0x1be82. Completion check 0x3a356 re-reads those mapped pages, recomputes the
additive byte sum from flash, and compares it with the stored checksum before entering 0x3a246;
that completion path logs `divoom_update_device_update_firmware; reset!` and calls the
non-returning reset primitive 0x1b60c. Named-object lookup/capacity failures occur before erase;
a post-write checksum mismatch takes the failure/exit path instead of reset.

The additive checksum covers everything except the final 4 bytes (so it includes the version
field and the marker). No cryptographic signature/HMAC is present in this path.
"""
from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path

MARKER = b"DIVOOMUPDATE"
TRAILER_LEN = 20  # u32 version + 12 marker + u32 checksum
FORCE_FLAG = 0x33  # header flag byte '3' bypasses the version-monotonicity gate

# Byte-verified UPDATE-R1 topology. This is descriptive metadata only: no method in this module
# erases, writes, fixes a checksum, or emits a candidate package. Addresses are flag42 v42016
# file offsets; runtime object locations are discovered by stock name lookup, not hardcoded.
WRITE_TOPOLOGY = {
    "initializer": "0x3a824",
    "page_size_bytes": 256,
    "logical_stream_order": ["BIOS1", "BOAR1", "PROG1"],
    "named_region_lookup": {
        "api": "Fwl lookup wrapper 0x1bf5c -> 0x52c2a",
        "returns": "byte capacity; writes u16 start_page to caller output",
    },
    "erase": {
        "BIOS1": {
            "helper": "0x3a746 -> 0x1beca",
            "granularity_bytes": 4096,
            "formula": "start_sector = BIOS1.start_page >> 4; count = BIOS1.size_bytes >> 12",
        },
        "PROG1_plus_BOAR1": {
            "helper": "0x3a746 -> 0x1beea",
            "granularity_bytes": 65536,
            "formula": (
                "start_block = PROG1.start_page >> 8; "
                "count = (PROG1.size_bytes + BOAR1.size_bytes) >> 16"
            ),
        },
    },
    "write": {
        "helper": "0x3a4ec -> 0x1be82",
        "unit_bytes": 256,
        "mapping": (
            "logical page i maps to BIOS1.start_page+i, then BOAR1.start_page+(i-BIOS1_pages), "
            "then PROG1.start_page+(i-BIOS1_pages-BOAR1_pages)"
        ),
    },
    "verify": {
        "helper": "0x3a356 -> 0x1beaa",
        "behavior": "re-read mapped pages from flash, additive-sum bytes, compare expected checksum",
    },
    "completion": {
        "path": "0x3a246",
        "reset_log": "divoom_update_device_update_firmware; reset!",
        "reset_primitive": "0x1b60c (non-returning)",
    },
    "failure_order_after_outer_accept": [
        "internal version/update-info guard",
        "state allocation",
        "BIOS1 lookup",
        "BOAR1 lookup",
        "PROG1 lookup",
        "combined capacity check",
        "erase/setup",
        "streamed page writes",
        "post-write flash re-read checksum",
        "completion/reset only on checksum match",
    ],
}


class ContainerError(ValueError):
    """Raised when the file is too small to contain a valid trailer."""


@dataclass
class Container:
    size: int
    version: int
    marker: bytes
    stored_checksum: int
    computed_checksum: int

    @property
    def marker_ok(self) -> bool:
        return self.marker == MARKER

    @property
    def checksum_ok(self) -> bool:
        return self.stored_checksum == self.computed_checksum


def parse(data: bytes) -> Container:
    if len(data) < TRAILER_LEN + 1:
        raise ContainerError(f"file too small ({len(data)} bytes) for a {TRAILER_LEN}-byte trailer")
    version = struct.unpack_from("<I", data, len(data) - 20)[0]
    marker = data[-16:-4]
    stored = struct.unpack_from("<I", data, len(data) - 4)[0]
    computed = sum(data[:-4]) & 0xFFFFFFFF
    return Container(len(data), version, marker, stored, computed)


def version_gate(candidate: int, installed: int | None, force: bool = False) -> dict:
    """Model 0x878c-0x879a. installed=None means 'unknown' -> not decidable, reported as such."""
    if force:
        return {"decision": "accept", "reason": "force flag 0x33 present; version gate bypassed"}
    if installed is None:
        return {"decision": "unknown", "reason": "installed version not supplied; gate not evaluated"}
    if installed >= candidate:
        return {"decision": "reject", "reason": f"installed {installed} >= candidate {candidate} (no downgrade/reinstall)"}
    return {"decision": "accept", "reason": f"candidate {candidate} > installed {installed}"}


def validate(data: bytes, installed_version: int | None = None, force: bool = False) -> dict:
    """Report each gate in firmware evaluation order. `accepted` is True only if a real
    device with `installed_version` would reach the flash writer."""
    try:
        c = parse(data)
    except ContainerError as exc:
        return {"parse_ok": False, "error": str(exc), "accepted": False}

    ver = version_gate(c.version, installed_version, force)
    gates = [
        {"gate": "marker", "ok": c.marker_ok,
         "detail": f"{c.marker!r} == {MARKER!r}" if c.marker_ok else f"got {c.marker!r}"},
        {"gate": "version", "ok": ver["decision"] == "accept",
         "decision": ver["decision"], "detail": ver["reason"],
         "candidate_version": c.version, "installed_version": installed_version},
        {"gate": "checksum", "ok": c.checksum_ok,
         "detail": f"stored=0x{c.stored_checksum:08x} computed=0x{c.computed_checksum:08x} over file[:-4]"},
    ]
    # Firmware rejects at the FIRST failing gate; report which one.
    first_fail = next((g["gate"] for g in gates if not g["ok"]), None)
    accepted = first_fail is None and ver["decision"] == "accept"
    return {
        "parse_ok": True,
        "container": {**asdict(c), "marker": c.marker.decode("latin1")},
        "gates": gates,
        "first_failing_gate": first_fail,
        "accepted": accepted,
        "write_topology": WRITE_TOPOLOGY,
        "note": "read-only analysis; no package was produced or modified",
    }


def _selfcheck() -> None:
    """Runnable check: a synthetic minimal-but-valid container and the four negative cases."""
    body = bytes(range(256)) * 4  # arbitrary body
    def build(version: int) -> bytes:
        pre = body + struct.pack("<I", version) + MARKER
        return pre + struct.pack("<I", sum(pre) & 0xFFFFFFFF)

    good = build(42016)
    assert validate(good, installed_version=42012)["accepted"], "valid upgrade must accept"
    assert not validate(good, installed_version=42016)["accepted"], "same version must reject"
    assert not validate(good, installed_version=42099)["accepted"], "downgrade must reject"
    assert validate(good, installed_version=42099, force=True)["accepted"], "force must bypass"

    bad_marker = good[:-16] + b"XIVOOMUPDATE" + good[-4:]
    r = validate(bad_marker, installed_version=42012)
    assert r["first_failing_gate"] == "marker", r

    bad_cksum = good[:-1] + bytes([good[-1] ^ 0xFF])
    r = validate(bad_cksum, installed_version=42012)
    assert r["first_failing_gate"] == "checksum", r

    r = validate(good[:8], installed_version=42012)
    assert not r["parse_ok"] and not r["accepted"], "truncated must fail parse"

    # marker is checked before checksum: a file with bad marker AND bad checksum reports marker
    both_bad = bad_marker[:-1] + bytes([bad_marker[-1] ^ 0xFF])
    assert validate(both_bad, installed_version=42012)["first_failing_gate"] == "marker"

    # UPDATE-R1 documentation invariants: topology is named-region based and remains read-only.
    assert WRITE_TOPOLOGY["page_size_bytes"] == 256
    assert WRITE_TOPOLOGY["logical_stream_order"] == ["BIOS1", "BOAR1", "PROG1"]
    assert WRITE_TOPOLOGY["erase"]["BIOS1"]["granularity_bytes"] == 4096
    assert WRITE_TOPOLOGY["erase"]["PROG1_plus_BOAR1"]["granularity_bytes"] == 65536
    assert WRITE_TOPOLOGY["write"]["unit_bytes"] == 256
    print("selfcheck OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?", type=Path, help="candidate divoomupdate.bin")
    ap.add_argument("--installed", type=int, default=None, help="installed firmware version for the version gate")
    ap.add_argument("--force", action="store_true", help="model the 0x33 header force flag")
    ap.add_argument("--selfcheck", action="store_true", help="run built-in fixtures and exit")
    args = ap.parse_args()
    if args.selfcheck or not args.file:
        _selfcheck()
        return 0
    report = validate(args.file.read_bytes(), installed_version=args.installed, force=args.force)
    print(json.dumps(report, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
