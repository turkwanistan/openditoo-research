#!/usr/bin/env python3
"""Fail-closed offline locator for the conserved Ditoo Plus analog-key pipeline.

This tool never modifies firmware.  It searches for three exact function bodies that are
byte-identical in the preserved flag42 v42016 and flag60 v60014 Ditoo Plus branches, then
requires their relative layout to match the known keypad module before reporting success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SIGS = {
    "translated_emitter": bytes.fromhex(
        "38b5051c08021043041c281c6a4600f05ff90006000e03d100ab1978221c03e0"
        "012804d1221c291c822074f07cfb38bd"
    ),
    "adc_decoder": bytes.fromhex(
        "f1b5002500272748284e4168002938d0002424484068007873f082ff0004000c"
        "a84200d9051cb04200d2061c381807043f0c0134062cecd3781b801b801000041"
        "849000c08804a685188814219d89188814216d30021547811e006234b439b18dd"
        "8885420ad81b89834207d3062048438018807a009908700120f8bd01318c42ebd8"
        "0020f9e7"
    ),
    "translation_mapper": bytes.fromhex(
        "70b52b4d6c68002c01d1012070bd00232d7806e09e00a65d864204d001331b06"
        "1b0eab42f6d3ab4201d3022070bd002906d0980001198878ff280cd148780ae098"
        "000019c178ff2904d0181c00f006f8032070bd40781070002070bd"
    ),
}

EXPECTED_DELTAS = {
    ("translated_emitter", "adc_decoder"): 0x1EE,
    ("adc_decoder", "translation_mapper"): 0xE2,
}


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    matches = {name: all_offsets(data, sig) for name, sig in SIGS.items()}
    unique = all(len(v) == 1 for v in matches.values())
    offsets = {name: vals[0] for name, vals in matches.items() if len(vals) == 1}

    deltas_ok = False
    delta_results = {}
    if unique:
        delta_results = {
            f"{a}->{b}": offsets[b] - offsets[a]
            for a, b in EXPECTED_DELTAS
        }
        deltas_ok = all(
            offsets[b] - offsets[a] == expected
            for (a, b), expected in EXPECTED_DELTAS.items()
        )

    ok = unique and deltas_ok
    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "ok": ok,
        "locator_contract": "three exact conserved function bodies + relative-layout validation; fail closed",
        "matches": {k: [f"0x{x:x}" for x in v] for k, v in matches.items()},
        "offsets": {k: f"0x{v:x}" for k, v in offsets.items()},
        "observed_deltas": {k: f"0x{v:x}" for k, v in delta_results.items()},
        "expected_deltas": {
            f"{a}->{b}": f"0x{expected:x}"
            for (a, b), expected in EXPECTED_DELTAS.items()
        },
        "notes": (
            "Recognition only; this script does not patch, recompute checksums, or produce a flashable image."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    results = [inspect(p) for p in args.firmware]
    if args.json:
        print(json.dumps(results[0] if len(results) == 1 else results, indent=2))
    else:
        for r in results:
            status = "PASS" if r["ok"] else "FAIL"
            print(f"{status} {r['path']} sha256={r['sha256']}")
            for name, vals in r["matches"].items():
                print(f"  {name}: {', '.join(vals) if vals else 'NO MATCH'}")
            if r["observed_deltas"]:
                for name, val in r["observed_deltas"].items():
                    print(f"  delta {name}: {val}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
