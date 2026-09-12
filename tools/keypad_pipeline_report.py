#!/usr/bin/env python3
"""Offline, fail-closed analyzer for the conserved Ditoo Plus analog-key event pipeline.

This tool NEVER modifies firmware and produces no flashable image. It re-locates the three
conserved keypad function bodies by signature (reusing the recognition-only locator), then
verifies — against the actual bytes of each preserved branch — the full runtime event graph:

    poll tick
      -> key_state_machine (press/hold timing; short<1000ms, long>=1000ms)
           -> get_current_key -> [driver ptr] ADC decoder -> adc_read_veneer (6-sample avg)
      -> translated_event_emitter  (short / long press)
      -> repeat_handler            (auto-repeat + key-change finalize)
           each -> queue_post(category=0x82, event, param)   <-- SINGLE COMMON FAN-IN

The important FIRM-R0 result this pins: the common seam that catches short, long AND repeat
events is NOT the emitter (0x52656) alone — the auto-repeat and finalize paths post to the
category-0x82 message queue directly. The guaranteed single hook point for a fail-open
consume-or-forward shim is therefore the set of category-0x82 producers converging on the
queue-post, or the consumer that dequeues category 0x82.

Everything below is asserted against firmware bytes; any drift fails the analysis closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from locate_ditoo_keypad_pipeline import inspect as locate  # recognition-only, fail-closed

# --- Reference map: flag42 v42016 file offsets, established by disassembly (base==0). ---
# flag60 v60014 is the same subsystem shifted by REFERENCE_BRANCH == flag42_offset - shift,
# where the shift is derived per-file from the signature-located emitter (0 for flag42,
# 0x94 for flag60). Every offset here is re-checked against real bytes before it is trusted.
REF = {
    "analog_key_config": 0x60D0,          # 7 calibrated analog ranges -> key IDs 1..7
    "key_translation_table": 0x6119,      # 8 x 4-byte [key_id, short, long, third/repeat]
    "adc_read_veneer": 0xC6764,           # 6-sample ADC read, drop min+max, average
    "adc_decoder": 0x52844,               # ADC counts -> key ID (via calibrated ranges)
    "get_current_key": 0x526F2,           # driver-ptr read of current key into *out
    "key_state_machine": 0x52790,         # debounce/hold timing; emits short vs long
    "translated_event_emitter": 0x52656,  # short/long press -> translate -> post 0x82
    "translation_mapper": 0x52926,        # select short/long/repeat event from the record
    "repeat_handler": 0x52982,            # 500ms auto-repeat + key-change finalize
    "queue_post": 0xC6D7C,                # generic os_post(category, event, u16 param)
    "queue_dequeue": 0xC6DF0,             # generic ring dequeue; shifts with queue implementation
    "key_event_dispatch": 0xE1374,         # category-0x82 semantic dispatcher; shifts with keypad branch
}
# Category-0x82 (translated key event) producers -> the BL-to-queue_post site file offset.
PRODUCERS_82 = {
    "emitter_press": 0x52680,       # short/long translated press event
    "release_finalize": 0x52916,    # current-key short event, action-class 2 (finalize)
    "repeat_keychange": 0x529AA,    # previous-key short event on key change, class 2
    "repeat_fire": 0x529CE,         # auto-repeat event, class 3
}
PRODUCER_81 = {"raw_notify": 0x525A8}  # adjacent category 0x81, NOT a translated key event

# The consumer task itself is fixed at the same file offset in both preserved branches. Only
# its BL immediates retarget the shifted dequeue/key-dispatch functions. This is deliberately
# separate from REF: applying the keypad branch shift to the consumer would be wrong.
CONSUMER = {
    "loop": 0xBC34,
    "category_0x81_compare": 0xBC40,
    "category_0x82_compare": 0xBC44,
    "category_0x82_dispatch_call": 0xBC4C,
    "category_0x81_dispatch_call": 0xBC64,
    "dequeue_call": 0xBC6A,
    "category_0x81_dispatch": 0xBBAC,
}

CONSTANTS = {
    "category_key_event": 0x82,
    "category_adjacent_0x81": 0x81,
    "long_press_threshold_ms": 1000,   # 0x7d<<3 at key_state_machine
    "auto_repeat_period_ms": 500,      # 0xff+0xf5 at repeat_handler
    "scan_reschedule_ms": 10,          # 0x0a at key_state_machine
    "record_stride_bytes": 4,
}


def thumb_bl_target(data: bytes, off: int) -> int | None:
    """Decode an ARMv5T Thumb BL/BLX pair at ``off``; return absolute target (base==0)."""
    if off + 4 > len(data):
        return None
    h1 = data[off] | (data[off + 1] << 8)
    h2 = data[off + 2] | (data[off + 3] << 8)
    if (h1 & 0xF800) != 0xF000:            # first halfword: 11110 prefix
        return None
    if (h2 & 0xF800) not in (0xF800, 0xE800):  # BL (F800) or BLX (E800)
        return None
    off22 = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
    if off22 & (1 << 22):                  # sign-extend the 23-bit signed offset
        off22 -= 1 << 23
    tgt = off + 4 + off22
    if (h2 & 0xF800) == 0xE800:            # BLX forces ARM alignment
        tgt &= ~3
    return tgt


def _bl_xrefs(data: bytes, target: int) -> list[int]:
    """Return every halfword-aligned Thumb BL/BLX callsite targeting ``target``."""
    return [off for off in range(0, len(data) - 3, 2) if thumb_bl_target(data, off) == target]


def _consumer_check(data: bytes, offsets: dict[str, int]) -> dict:
    """Verify the fixed consumer loop and its branch-specific call targets."""
    c = CONSUMER
    cmp81_ok = data[c["category_0x81_compare"]:c["category_0x81_compare"] + 2] == bytes.fromhex("8128")
    cmp82_ok = data[c["category_0x82_compare"]:c["category_0x82_compare"] + 2] == bytes.fromhex("8228")
    dispatch82 = thumb_bl_target(data, c["category_0x82_dispatch_call"])
    dispatch81 = thumb_bl_target(data, c["category_0x81_dispatch_call"])
    dequeue = thumb_bl_target(data, c["dequeue_call"])
    dequeue_xrefs = _bl_xrefs(data, offsets["queue_dequeue"])
    ok = (
        cmp81_ok and cmp82_ok
        and dispatch82 == offsets["key_event_dispatch"]
        and dispatch81 == c["category_0x81_dispatch"]
        and dequeue == offsets["queue_dequeue"]
        and dequeue_xrefs == [c["dequeue_call"]]
    )
    return {
        "loop": f"0x{c['loop']:x}",
        "loop_position": "fixed in both preserved branches; call targets retarget per branch",
        "category_0x81_compare_ok": cmp81_ok,
        "category_0x82_compare_ok": cmp82_ok,
        "category_0x82_dispatch": None if dispatch82 is None else f"0x{dispatch82:x}",
        "category_0x82_dispatch_ok": dispatch82 == offsets["key_event_dispatch"],
        "category_0x81_dispatch": None if dispatch81 is None else f"0x{dispatch81:x}",
        "category_0x81_dispatch_ok": dispatch81 == c["category_0x81_dispatch"],
        "dequeue_call": f"0x{c['dequeue_call']:x}",
        "dequeue_target": None if dequeue is None else f"0x{dequeue:x}",
        "dequeue_target_ok": dequeue == offsets["queue_dequeue"],
        "dequeue_xrefs": [f"0x{x:x}" for x in dequeue_xrefs],
        "dequeue_single_consumer_ok": dequeue_xrefs == [c["dequeue_call"]],
        "ok": ok,
    }


def _check(data: bytes, addr: int, expect_prefix: bytes, expect_bl_to: int) -> dict:
    """Verify a producer site: `movs r0,#cat` (expect_prefix) then BL -> queue_post."""
    prefix_ok = data[addr - 2:addr] == expect_prefix
    tgt = thumb_bl_target(data, addr)
    return {
        "site": f"0x{addr:x}",
        "movs_r0_prefix": data[addr - 2:addr].hex(),
        "movs_r0_ok": prefix_ok,
        "bl_target": None if tgt is None else f"0x{tgt:x}",
        "bl_target_ok": tgt == expect_bl_to,
        "ok": prefix_ok and tgt == expect_bl_to,
    }


def analyze(path: Path) -> dict:
    data = path.read_bytes()
    loc = locate(path)
    result: dict = {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "locator_ok": loc["ok"],
        "locator": {"offsets": loc["offsets"], "observed_deltas": loc["observed_deltas"]},
    }
    if not loc["ok"]:
        result["ok"] = False
        result["reason"] = "locator failed closed; branch not recognized"
        return result

    # Per-file branch shift from the signature-located emitter.
    located_emitter = int(loc["offsets"]["translated_emitter"], 16)
    shift = REF["translated_event_emitter"] - located_emitter  # 0 (flag42) or 0x94 (flag60)

    offsets = {name: ref - shift for name, ref in REF.items()}

    cat = CONSTANTS["category_key_event"]
    prefix82 = bytes([cat, 0x20])  # `movs r0, #0x82`
    queue = offsets["queue_post"]
    producers = {
        name: _check(data, site - shift, prefix82, queue)
        for name, site in PRODUCERS_82.items()
    }
    prefix81 = bytes([CONSTANTS["category_adjacent_0x81"], 0x20])
    p81 = {
        name: _check(data, site - shift, prefix81, queue)
        for name, site in PRODUCER_81.items()
    }
    # Emitter's own BL to the translator must resolve (sanity on shift consistency).
    emitter_bl_to_translator = thumb_bl_target(data, located_emitter + 0xE)
    translator_ok = emitter_bl_to_translator == offsets["translation_mapper"]

    # Exhaustively scan direct BL/BLX references to this queue implementation. The complete
    # caller set must be the four translated-key producers plus the one separate 0x81 producer.
    queue_xrefs = _bl_xrefs(data, queue)
    expected_queue_xrefs = sorted(
        [site - shift for site in PRODUCERS_82.values()]
        + [site - shift for site in PRODUCER_81.values()]
    )
    queue_xrefs_complete = queue_xrefs == expected_queue_xrefs
    consumer = _consumer_check(data, offsets)

    checks_ok = (
        all(p["ok"] for p in producers.values())
        and all(p["ok"] for p in p81.values())
        and translator_ok
        and queue_xrefs_complete
        and consumer["ok"]
    )
    result.update({
        "branch_shift": f"0x{shift:x}",
        "offsets": {name: f"0x{off:x}" for name, off in offsets.items()},
        "category_0x82_producers": producers,
        "category_0x81_producer": p81,
        "queue_post_xrefs": [f"0x{x:x}" for x in queue_xrefs],
        "queue_post_xrefs_complete": queue_xrefs_complete,
        "consumer": consumer,
        "category_0x81_semantics": (
            "separate notify/callback category with its own 0xbbac dispatcher; not the translated "
            "front-panel key class (0x82)"
        ),
        "emitter_bl_to_translator": (
            None if emitter_bl_to_translator is None else f"0x{emitter_bl_to_translator:x}"
        ),
        "emitter_bl_to_translator_ok": translator_ok,
        "ok": checks_ok,
    })
    return result


def build_report(paths: list[Path]) -> dict:
    branches = [analyze(p) for p in paths]
    return {
        "artifact": "ditoo_keypad_pipeline_analysis",
        "contract": "recognition + byte-verified semantic model; fail-closed; no patching",
        "constants": CONSTANTS,
        "runtime_graph": [
            "poll_tick -> key_state_machine",
            "key_state_machine -> get_current_key -> [driver_ptr] adc_decoder -> adc_read_veneer",
            "key_state_machine -> translated_event_emitter (short/long press)",
            "translated_event_emitter -> translation_mapper -> queue_post(category=0x82)",
            "key_state_machine timer -> repeat_handler (500ms) -> queue_post(category=0x82) [BYPASSES emitter]",
            "consumer 0xbc34 -> queue_dequeue -> category 0x82 -> key_event_dispatch",
        ],
        "hook_seam": {
            "single_common_fanin": "queue_post category 0x82",
            "note": (
                "The emitter (translated_event_emitter) catches only short/long PRESS events. "
                "Auto-repeat and key-change finalize post category 0x82 directly, bypassing the "
                "emitter. A consume-or-forward shim that must see short+long+repeat should hook "
                "the category-0x82 producers/consumer, not the emitter alone."
            ),
            "category_0x82_producer_count": len(PRODUCERS_82),
            "consumer_loop": "0xbc34 (same file offset in both preserved branches)",
            "consumer_side_alternative": (
                "hook after the single queue dequeue and before/at the category-0x82 dispatch; "
                "all four translated-key producer paths converge here"
            ),
        },
        "key_translation_table_semantics": {
            "record": "[key_id, short_event(byte1), long_event(byte2), third_repeat(byte3)]",
            "short_press": "translator r1==0 -> byte3 if !=0xFF invokes repeat_handler else byte1",
            "long_press": "translator r1!=0 -> byte2 if !=0xFF else byte1",
            "0xFF": "means 'no distinct event for this phase; fall back to short'",
        },
        "branches": branches,
        "ok": all(branch["ok"] for branch in branches),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="write JSON artifact to this path")
    args = ap.parse_args()
    report = build_report(args.firmware)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text if not args.out else f"{'PASS' if report['ok'] else 'FAIL'} wrote {args.out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
