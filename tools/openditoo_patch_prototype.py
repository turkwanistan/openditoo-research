#!/usr/bin/env python3
"""OFFLINE, NON-DEPLOYABLE PATCH-R0 prototype for the OpenDitoo fail-open input hook.

This tool recognizes the conserved Ditoo Plus keypad pipeline across known firmware branches
and MODELS a fail-open consume-or-forward hook at the category-0x82 event seam (see FIRM-R0).
It is a research transformer/validator, NOT a firmware builder:

  * FAIL CLOSED  — refuses any firmware the signature locator does not recognize.
  * VERIFY ORIGINAL BYTES — every producer site must contain exactly the expected
                            `movs r0,#0x82` + `bl queue_post` before it will model an edit.
  * REPORT CHANGED REGIONS — emits a byte-level diff and hashes of every untouched region.
  * NON-INSTALLABLE BY CONSTRUCTION — any emitted research image has a deliberately INVALID
                            stored updater checksum, PROVEN by re-running the UPDATE-R0
                            validator; the tool refuses to emit an image the updater would
                            accept.

What it deliberately does NOT do (these are LIVE-gated future steps, out of scope here):
  * author the actual shim machine code;
  * prove an all-0xFF region is a resident/executable code cave;
  * recompute a valid container checksum;
  * write any device.

The modeled edit re-targets each category-0x82 producer's `bl queue_post` to a caller-supplied
`shim_entry`. The shim body (claim/heartbeat check -> forward-or-consume) is NOT authored; a
real build must also validate executable placement of the shim. Without `--shim-entry` the tool
only recognizes, verifies and plans — it emits no image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))
from locate_ditoo_keypad_pipeline import inspect as locate  # fail-closed recognition
import ditoo_update_container as udc  # UPDATE-R0 validator (non-installability proof)
from keypad_pipeline_report import REF, PRODUCERS_82, thumb_bl_target  # verified seam model


def encode_bl(src: int, target: int) -> bytes:
    """ARMv5T Thumb BL encoder (inverse of thumb_bl_target); base==0 file offsets."""
    off = target - (src + 4)
    imm_hi = (off >> 12) & 0x7FF
    imm_lo = (off >> 1) & 0x7FF
    h1 = 0xF000 | imm_hi
    h2 = 0xF800 | imm_lo
    return bytes([h1 & 0xFF, h1 >> 8, h2 & 0xFF, h2 >> 8])


class UnrecognizedFirmware(Exception):
    pass


class OriginalBytesMismatch(Exception):
    pass


def _seam(data: bytes) -> tuple[int, dict]:
    """Locate + verify the category-0x82 producer seam. Returns (branch_shift, sites)."""
    loc = locate_path_bytes(data)
    if not loc["ok"]:
        raise UnrecognizedFirmware("keypad pipeline not recognized; refusing (fail closed)")
    located_emitter = int(loc["offsets"]["translated_emitter"], 16)
    shift = REF["translated_event_emitter"] - located_emitter
    queue = REF["queue_post"] - shift
    sites = {}
    for name, ref_site in PRODUCERS_82.items():
        site = ref_site - shift
        orig = data[site:site + 4]
        prefix = data[site - 2:site]
        if prefix != bytes([0x82, 0x20]):
            raise OriginalBytesMismatch(f"{name}@0x{site:x}: expected movs r0,#0x82, got {prefix.hex()}")
        if thumb_bl_target(data, site) != queue:
            raise OriginalBytesMismatch(f"{name}@0x{site:x}: BL does not target queue_post 0x{queue:x}")
        sites[name] = {"site": site, "original_bl": orig, "targets": queue}
    return shift, sites


def locate_path_bytes(data: bytes) -> dict:
    """locator.inspect works on a path; run it against a temp file of these bytes."""
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".bin")
    try:
        os.write(fd, data)
        os.close(fd)
        return locate(Path(p))
    finally:
        os.unlink(p)


def model_hook(data: bytes, shim_entry: int | None) -> dict:
    """Recognize + verify + (optionally) apply the modeled redirect. Never installable."""
    shift, sites = _seam(data)
    plan = {
        "branch_shift": f"0x{shift:x}",
        "queue_post": f"0x{REF['queue_post'] - shift:x}",
        "fail_open_semantics": (
            "shim checks a short-TTL claim: claim inactive/expired -> tail-call queue_post "
            "(stock forward, byte-equivalent behavior); claim active -> report typed key "
            "event, optionally consume. Disconnect/crash/TTL -> stock resumes automatically."
        ),
        "producer_sites": {
            name: {"site": f"0x{s['site']:x}", "original_bl": s["original_bl"].hex(),
                   "redirect_to": None if shim_entry is None else f"0x{shim_entry:x}"}
            for name, s in sites.items()
        },
        "shim_body": "NOT AUTHORED (LIVE-gated): claim/heartbeat check + forward/consume; "
                     "executable placement must be validated before any real build.",
    }
    result = {"recognized": True, "plan": plan, "image_emitted": False}

    if shim_entry is None:
        return result

    patched = bytearray(data)
    changes = []
    for name, s in sites.items():
        new_bl = encode_bl(s["site"], shim_entry)
        patched[s["site"]:s["site"] + 4] = new_bl
        changes.append({"region": name, "offset": f"0x{s['site']:x}",
                        "before": s["original_bl"].hex(), "after": new_bl.hex()})

    # Non-installability proof: the edits changed bytes inside file[:-4], so the stored
    # additive checksum no longer matches. Prove the UPDATE-R0 validator rejects it.
    verdict = udc.validate(bytes(patched), installed_version=None)
    if verdict.get("gates") and verdict["gates"][2]["ok"]:
        raise RuntimeError("refusing to emit: research image unexpectedly passes the checksum gate")

    result.update({
        "image_emitted": True,
        "changed_regions": changes,
        "changed_byte_count": len(changes) * 4,
        "untouched_sha256_excluding_edits": _untouched_hash(data, patched),
        "non_installable_proof": {
            "updater_checksum_gate_ok": verdict["gates"][2]["ok"],
            "note": "stored additive checksum no longer matches sum(file[:-4]); updater rejects",
        },
        "_patched": bytes(patched),
    })
    return result


def _untouched_hash(orig: bytes, patched: bytes) -> str:
    """Hash of all bytes that are identical between orig and patched (a tamper witness)."""
    h = hashlib.sha256()
    for a, b in zip(orig, patched):
        if a == b:
            h.update(bytes([a]))
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("firmware", type=Path)
    ap.add_argument("--shim-entry", type=lambda s: int(s, 0), default=None,
                    help="file offset the modeled redirect points BLs at (emits a research image)")
    ap.add_argument("--out", type=Path, help="write the NON-INSTALLABLE research image here")
    args = ap.parse_args()
    try:
        res = model_hook(args.firmware.read_bytes(), args.shim_entry)
    except (UnrecognizedFirmware, OriginalBytesMismatch) as exc:
        print(json.dumps({"recognized": False, "refused": str(exc)}, indent=2))
        return 1
    img = res.pop("_patched", None)
    if args.out and img is not None:
        args.out.write_bytes(img)
        res["written"] = str(args.out)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
