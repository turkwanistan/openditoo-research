#!/usr/bin/env python3
"""Fail-closed offline atlas of the preserved Ditoo Plus SPP parser surface.

VRAM-0/VRAM-1/early-VRAM-2 evidence only. This tool reads pinned firmware
artifacts and emits JSON. It never opens Bluetooth, constructs live packets,
or mutates a device/firmware image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ditoo_software_recovery_surface import dispatch_map
from keypad_pipeline_report import thumb_bl_target

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "artifacts" / "firmware"
DISPATCH_TABLE = 0x105E8
DISPATCH_JUMP_BASE = 0x105E4
PRIMARY_DEFAULT = 0x126E4
SECONDARY_DEFAULT = 0x126EC
DISPATCH_END = 0x1271E
EXTERN_CMD = 0xBD
EXTERN_HANDLER = 0x10A88
EXTERN_TABLE = 0x10A9C

BRANCHES = {
    "flag42_prod_v42016": {
        "path": FW / "flag42_v42016.bin",
        "sha256": "f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a",
        "size": 1207313,
        "kind": "production",
        "hardware_flag": 42,
    },
    "flag42_test_v42017": {
        "path": FW / "flag42_v42017_test.bin",
        "sha256": "6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc",
        "size": 1207333,
        "kind": "official_test",
        "hardware_flag": 42,
    },
    "flag60_prod_v60014": {
        "path": FW / "flag60_v60014.bin",
        "sha256": "02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300",
        "size": 1207165,
        "kind": "production",
        "hardware_flag": 60,
    },
    "flag60_test_api60016_internal60017": {
        "path": FW / "flag60_api60016_internal60017_test.bin",
        "sha256": "05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339",
        "size": 1207313,
        "kind": "official_test",
        "hardware_flag": 60,
    },
}

# Exact-model command labels already accepted by the software-recovery graph.
KNOWN_LABELS = {
    0x97: "SPP_GET_FILE_VERSION",
    0x98: "SPP_APP_UPDATE_FILE_INFO",
    0x99: "SPP_APP_SEND_FILE_DATA",
    0x9B: "SPP_HOT_UPDATE_FILE_INFO",
    0x9D: "SPP_HOT_PAUSE_FILE_SEND",
    0x9E: "SPP_HOT_SEND_FILE_DATA",
    0x9F: "SPP_PAUSE_SYS_UPDATE_DATA",
    0xBD: "SPP_DIVOOM_EXTERN_CMD",
}

# Protocol-era labels recovered from the provenance-pinned Divoom Android 3.1.58 APK.
# These improve atlas readability only; firmware byte/dataflow remains authoritative.
KNOWN_LABELS.update({
    0x15: "SPP_SEND_SD_TF_STATUS", 0x16: "SPP_LIEGHT_SET_25DOTS_ATTR", 0x18: "SPP_SET_SYSTEM_TIME",
    0x19: "SPP_DEVICE_UPDATE_GIF", 0x1A: "SPP_STOP_SEND_GIF", 0x23: "SPP_SPP_LIGHT_ARROW_SWITCH",
    0x26: "SPP_SEND_APP_NEWEST_TIME", 0x27: "SPP_SET_APP_BR_PASSWORD", 0x34: "SPP_SAND_PAINT_CTRL",
    0x35: "SPP_SCROLL", 0x3A: "SPP_DRAWING_MUL_PAD_CTRL", 0x3B: "SPP_DRAWING_BIG_PAD_CTRL",
    0x3C: "SPP_SET_ANCS_NOTICE_PIC", 0x3E: "SPP_MOVE_RESET_IFRAME", 0x40: "SPP_SET_SLEEP_TIME",
    0x41: "SPP_SET_SLEEP_SCENE", 0x42: "SPP_GET_ALARM_TIME_SCENE", 0x43: "SPP_SET_ALARM_TIME_SCENE",
    0x44: "SPP_SET_BOX_COLOR", 0x45: "SPP_SET_BOX_MODE", 0x46: "SPP_GET_BOX_MODE",
    0x47: "SPP_APP_NEED_GET_MUSIC_LIST", 0x48: "SPP_PAUSE_SYS_UPDATE_DATA", 0x49: "SPP_SET_MUL_BOX_COLOR",
    0x50: "SPP_SET_ANDROID_ANCS", 0x51: "SPP_SET_ALARM_TIME_GIF", 0x52: "SPP_SET_BOOT_GIF",
    0x53: "SPP_GET_DIALY_TIME_EXT2", 0x54: "SPP_SET_DIALY_TIME_EXT2", 0x55: "SPP_SET_DIALY_TIME_GIF",
    0x56: "SPP_SET_TIME_MANAGE_INFO", 0x57: "SPP_GET_TIME_MANAGE_CTRL", 0x58: "SPP_DRAWING_PAD_CTRL",
    0x59: "SPP_GET_DEVICE_TEMP_INFO", 0x5A: "SPP_DRAWING_PAD_EXIT", 0x5B: "SPP_DRAWING_ENCODE_PIC",
    0x5C: "SPP_DRAWING_ENCODE_PLAY", 0x5D: "SPP_SEND_NET_TEMP_INFO", 0x5E: "SPP_SEND_NET_TEMP_DISP_INFO",
    0x5F: "SPP_SEND_CUR_NET_TEMP", 0x6A: "SPP_SET_MIX_MUISE_MODE", 0x6B: "SPP_DRAWING_MUL_ENCODE_GIF_PLAY",
    0x6C: "SPP_DRAWING_ENCODE_MOVIE_PLAY", 0x6D: "SPP_DRAWING_MUL_ENCODE_MOVIE_PLAY", 0x6E: "SPP_DRAWING_CTRL_MOVIE_PLAY",
    0x6F: "SPP_DRAWING_MUL_PAD_ENTER", 0x71: "SPP_GET_TOOL_INFO", 0x72: "SPP_SET_TOOL_INFO",
    0x73: "SPP_GET_NET_TEMP_DISP_INFO", 0x74: "SPP_SET_SYSTEM_BRIGHT", 0x75: "SPP_SET_DEVICE_NAME",
    0x77: "SPP_SET_MUL_DEVICE_CTRL", 0x79: "SPP_SET_SLEEP_CTRL_MODE", 0x7C: "SPP_LED_UPDATE_FONT_INFO",
    0x7E: "SPP_SET_DIVOOM_LEAVE_MSG_GIF", 0x7F: "SPP_DEL_LEAVE_MSG_GIF", 0x82: "SPP_SET_ALARM_VOICE_CTRL",
    0x83: "SPP_SET_SONG_DIS_CTRL", 0x84: "SPP_RESET_NOTIFICATIONS", 0x85: "SPP_SEND_HOTCTRL",
    0x86: "SPP_SEND_LED_WORD_CMD", 0x88: "SPP_SEND_GAME_SHARK", 0x8A: "SPP_SET_POWER_CHANNEL",
    0x8B: "SPP_APP_NEW_GIF_CMD2020", 0x8C: "SPP_APP_NEW_USER_DEFINE2020", 0x8D: "SPP_APP_BIG64_USER_DEFINE",
    0x8E: "SPP_APP_GET_USER_DEFINE_INFO", 0xA0: "SPP_SET_GAME", 0xA1: "SPP_SET_TALK",
    0xA2: "SPP_GET_SCENE", 0xA3: "SPP_SET_SCENE_LISTEN", 0xA4: "SPP_SET_SCENE_LISTEN_VOLUME",
    0xA5: "SPP_SET_ALARM_LISTEN", 0xA6: "SPP_SET_ALARM_LISTEN_VOLUME", 0xA7: "SPP_SET_SOUND_CTRL",
    0xA8: "SPP_GET_SOUND_CTRL", 0xA9: "SPP_SET_PLAY_STOP_VOICE", 0xAA: "SPP_GET_PLAY_VOICE_STATUS",
    0xAB: "SPP_SET_AUTO_POWER_OFF", 0xAC: "SPP_GET_AUTO_POWER_OFF", 0xAD: "SPP_SET_SLEEP_COLOR",
    0xAE: "SPP_SET_SLEEP_LIGHT", 0xAF: "SPP_SET_CONNECTED_FLAG", 0xB0: "SPP_GET_CONNECTED_FLAG",
    0xB1: "SPP_SET_USER_GIF", 0xB2: "SPP_SET_ENERGY_CTRL", 0xB3: "SPP_GET_ENERGY_CTRL",
    0xB6: "SPP_MODIFY_RHYTHM_ITEMS", 0xBB: "SPP_SET_POWERON_VOICE_VOL", 0xBC: "SPP_SET_NEW_MIX_MUSIC_MODE",
})

# Byte-pinned VRAM-2 conclusions. These are intentionally narrower than
# protocol semantics; no conclusion is promoted from a crash/guess.
AUDITED = {
    0x18: {
        "status": "CLOSED_NO_CONTROL",
        "summary": "Allocates 8 bytes and copies exactly 8 bytes from packet+1; destination write is exact-size. Outer length is not locally used to guard the fixed source read, so a short packet can over-read the receive object but does not create a variable write.",
        "caller_control": "first 8 bytes after command",
        "landing": "8-byte heap object",
        "bounds": "destination exactly 8 bytes; copy exactly 8",
        "source_length_caveat": "fixed 8-byte source read is not locally compared with outer length",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x117c0..0x11858", "alloc 0xbfbc(8)", "copy blx 0x7058 len=8"],
    },
    0x35: {
        "status": "CLOSED_BOUNDS_SAFE",
        "summary": "Consumes a fixed selector byte and a fixed u16 at packet+3; no variable-length copy or caller-derived destination was found in the handler.",
        "caller_control": "packet[1], packet[2], u16(packet+3)",
        "landing": "scalar arguments",
        "bounds": "fixed-field parser",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x10d98..0x10dc8"],
    },
    0x44: {
        "status": "CLOSED_NO_CONTROL",
        "summary": "Image decoder accepts internal AA-framed palette/pixel content. Palette capacity is clamped to 64..256 RGB entries and continuation writes require current+count<=capacity. The decoder trusts internal source lengths enough to permit source over-read, but observed destinations remain bounded and no pointer/callback overwrite is reachable from the decoded bytes.",
        "caller_control": "packet+5 image stream, including palette count/content and compressed pixel bytes",
        "landing": "decoder context + bounded RGB palette/output state",
        "bounds": "palette allocation is 3*clamp(2*count,64,256); continuation count checked before writes",
        "source_length_caveat": "internal source consumption is not tied back to outer SPP length before decode",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x11b0a..0x11b2e", "0x14db8", "0x3bc52", "0x3bcb4..0x3be3c", "0x3b77a/0x3b78e"],
    },
    0x45: {
        "status": "CLOSED_BOUNDS_SAFE",
        "summary": "packet[1] is checked <7 before indexing a 7-byte mode table; downstream 0x14104 receives the selected bounded mode and packet+2 fixed content.",
        "caller_control": "bounded selector packet[1] plus fixed mode payload",
        "landing": "mode/state fields",
        "bounds": "selector <7 before table access",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x11b30..0x11b8e", "0x14104"],
    },
    0x49: {
        "status": "CLOSED_NO_CONTROL",
        "summary": "Passes packet+1 through the normal command/report path; no local allocation, variable copy, or caller-derived control sink is present.",
        "caller_control": "packet+1 payload",
        "landing": "normal command/report path",
        "bounds": "no local mutable variable-length destination",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x11bb8..0x11bd0"],
    },
    0x50: {
        "status": "CLOSED_NO_CONTROL",
        "summary": "Contains an unchecked packet[1]*4 table read, but the variable text/data path uses packet[2] as an 8-bit length, allocates len+1 for the first copy and 2*len+4 for the converted buffer, then stores the returned heap pointer. This yields a caller-indexed read but no write overflow/control sink in the audited path.",
        "caller_control": "packet[1] table index, packet[2] <=255 length, packet+3 data",
        "landing": "two heap buffers sized from the same 8-bit length",
        "bounds": "first allocation len+1/copy len; second allocation 2*len+4",
        "source_length_caveat": "packet[1] table index lacks a local range check",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x11c12..0x11c7a", "0x233e4..0x23448", "0x2337e..0x23398"],
    },
    0x58: {
        "status": "CLOSED_BOUNDS_SAFE",
        "summary": "packet[4] is an 8-bit loop count and packet+5 supplies byte indices. Each index is inherently <256 and 0x128ea writes exactly three bytes into a 256*3 palette at index*3 using the fixed three-byte color tuple from packet[1..3].",
        "caller_control": "RGB tuple packet[1..3], count packet[4], index bytes packet+5",
        "landing": "256-entry RGB palette",
        "bounds": "index byte <256; offset=index*3; exactly three bytes per entry; count <=255",
        "indirect_control_sink": False,
        "persistent": False,
        "witnesses": ["0x11e66..0x11ec2", "0x1290a..0x12946", "0x128ea..0x12908"],
    },
    0x6C: {
        "status": "CLOSED_NO_CONTROL",
        "summary": "packet+5 and a caller u16 are synchronously dispatched to the media sink. The in-firmware media object is 0xC50 bytes; its only caller-data staging copy is +0x842 for 263 bytes (ending +0x948), while the callback pointer is at +0xC4C. The staging write cannot reach the callback. No direct branch/call or raw Thumb-pointer reference to the callback setter was found in the preserved blob; the fallback sink is fixed code at 0xA6490.",
        "caller_control": "u16 fields plus packet+5 media bytes",
        "landing": "media object / fixed external sink",
        "bounds": "263-byte staging region is disjoint from callback slot by >0x300 bytes",
        "indirect_control_sink": False,
        "persistent": False,
        "next_tier": "external media/codec sink behind 0x34144/0xA6490 is a separate Tier-2 parser surface, not evidence of a direct SPP control-flow primitive",
        "witnesses": ["0x11fce..0x12012", "event 0x0b -> 0x12cd4 -> 0x34144", "object alloc 0xC50 at 0x340e8", "staging +0x842 at 0x34168", "callback +0xC4C at 0x341a2", "setter 0x34262 has no direct BL/B/literal-pointer xref"],
    },
    0x98: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Firmware/update ingress; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0x99: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Firmware/update file-data ingress; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0x9B: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Hot-update metadata ingress; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0x9D: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Hot/update control path; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0x9E: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Hot-update data ingress; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0x9F: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "System-update control/data path; excluded from volatile-RAM route.",
        "persistent": True,
        "indirect_control_sink": False,
    },
    0xB1: {
        "status": "EXCLUDED_PERSISTENT",
        "summary": "Download/file writer. Caller u16 length reaches 0x508ea, but the writer checks used+len<=capacity before chunk copies and flushes through the persistent erase/write pipeline. Safe front-end for this question and excluded from RAM-only route.",
        "caller_control": "download subcommand, u16 data length, packet+4 data",
        "landing": "bounded streaming writer backed by persistent storage",
        "bounds": "0x508ea rejects used+len>capacity before copies",
        "persistent": True,
        "indirect_control_sink": False,
        "witnesses": ["0x12594..0x1266e", "0x37236", "0x37210", "0x508b8", "0x508ea..0x509d2", "erase call 0x1beea"],
    },
}


def _audit(status: str, summary: str, *, control: str = "fixed fields", landing: str = "scalar/fixed state", bounds: str = "fixed-width", persistent: bool = False, witnesses: list[str] | None = None, caveat: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status, "summary": summary, "caller_control": control, "landing": landing,
        "bounds": bounds, "persistent": persistent, "indirect_control_sink": False,
        "witnesses": witnesses or [],
    }
    if caveat:
        out["source_length_caveat"] = caveat
    return out


# Additional VRAM-2 closures from handler-local CFG + helper dataflow review.
# Exact firmware hashes/targets above fail closed before any of these conclusions are emitted.
AUDITED.update({
    0x16: _audit("CLOSED_BOUNDS_SAFE", "Reads a fixed u16 from packet+1 and forwards only that scalar.", control="u16(packet+1)", witnesses=["0x10d86..0x10d94", "0x28716"]),
    0x1B: _audit("EXCLUDED_PERSISTENT", "Routes packet content into the shared 0xfdb4 content/file pipeline, which contains persistent erase/program branches; excluded from the RAM-only route.", persistent=True, control="packet+2 content", landing="shared content/file pipeline", witnesses=["0x11c88..0x11c92", "0x11db2..0x11db4", "0xfdb4", "0x1beca/0x1be82"]),
    0x27: _audit("CLOSED_BOUNDS_SAFE", "Password path mutates exactly four packet bytes in-place then submits exactly four bytes; no caller-derived destination or count.", control="packet[1] mode + packet[2..5] four bytes", landing="receive buffer in-place + fixed four-byte message", bounds="exactly four bytes", witnesses=["0x10bf2..0x10c4a", "0x1868c len=4"]),
    0x35: _audit("EXCLUDED_PERSISTENT", "The nonzero scroll/content branch reaches the shared 0xfdb4 content pipeline; because that pipeline can erase/program storage, the command is excluded from the volatile route even though its front-end fields are fixed.", persistent=True, control="fixed header plus content branch", landing="shared content/file pipeline", witnesses=["0x10d98..0x10dc8", "0x1158c -> 0x11bb6 -> 0x11db2", "0xfdb4"]),
    0x3A: _audit("CLOSED_BOUNDS_SAFE", "Drawing multi-pad content reaches the same 256-entry RGB palette primitive already audited for 0x58; byte indices are inherently <256 and each update is exactly three bytes.", control="drawing RGB/index fields", landing="256-entry RGB palette", bounds="index byte * 3, fixed three-byte write", witnesses=["0x11ecc..0x11ed8", "0x359fe", "0x1290a", "0x128ea"]),
    0x3C: _audit("CLOSED_NO_CONTROL", "ANCS picture path forwards packet+4 with a caller u16 into a compare-oriented message constructor. The caller length reaches a comparison/read path, not a mutable destination copy; large values are over-read/crash class only, not a controlled RAM write.", control="selector + u16 length + packet+4 bytes", landing="message compare/read path", bounds="no caller-sized destination copy", witnesses=["0x11356..0x1136a", "0x2365a", "0x1868c", "0xa2850"]),
    0x40: _audit("CLOSED_BOUNDS_SAFE", "Sleep-time command reads fixed packet[1..10] fields into stack state; downstream 0x39b46 copies a fixed 12-byte structure into fixed global state.", control="ten fixed bytes", landing="fixed sleep-state structure", bounds="fixed 12-byte structure copy", witnesses=["0x11986..0x11a3c", "0x39b46..0x39b70"]),
    0x41: _audit("CLOSED_BOUNDS_SAFE", "Sleep-scene command reads fixed packet[1..9] fields into stack state; downstream 0x39b46 copies a fixed 12-byte structure into fixed global state.", control="nine fixed bytes", landing="fixed sleep-state structure", bounds="fixed 12-byte structure copy", witnesses=["0x11a3c..0x11ae8", "0x39b46..0x39b70"]),
    0x43: _audit("CLOSED_BOUNDS_SAFE", "Alarm-scene helper consumes a fixed-width record (bytes 0..9) into stack/global state; no variable copy/count is derived from the payload.", control="fixed alarm-scene record", landing="stack/global alarm state", bounds="fixed fields only", witnesses=["0x11af8..0x11b08", "0x2294a..0x22a08"]),
    0x49: _audit("EXCLUDED_PERSISTENT", "Routes packet+1 into the shared 0xfdb4 content/file pipeline, whose command-specific branches include storage erase/program. Excluded from volatile-only work.", persistent=True, control="packet+1 content", landing="shared content/file pipeline", witnesses=["0x11bb8..0x11bce", "0x11db2..0x11db4", "0xfdb4", "0x1beca/0x1be82"]),
    0x4A: _audit("CLOSED_BOUNDS_SAFE", "Consumes a fixed 15-byte boolean/bitmask record; helper iterates exactly 15 entries and emits fixed state.", control="15-byte flag vector", landing="bitmask/state", bounds="exact 15-iteration loop", witnesses=["0x11bd0..0x11bee", "0x2355c..0x235bc"]),
    0x51: _audit("EXCLUDED_PERSISTENT", "Alarm-GIF content routes into the shared 0xfdb4 storage-capable pipeline; excluded from volatile route.", persistent=True, control="GIF/content payload", landing="shared content/file pipeline", witnesses=["0x11c7c..0x11c86", "0xfdb4"]),
    0x52: _audit("EXCLUDED_PERSISTENT", "Boot-GIF content routes into the shared 0xfdb4 storage-capable pipeline; excluded from volatile route.", persistent=True, control="GIF/content payload", landing="shared content/file pipeline", witnesses=["0x11ca6..0x11cb4", "0xfdb4"]),
    0x54: _audit("CLOSED_BOUNDS_SAFE", "Daily-time helper validates record selector <10, copies fixed scalar fields, then copies exactly 0x20 bytes from packet+7 into its stack-owned record.", control="fixed fields + 32-byte record", landing="stack-owned daily-time record", bounds="selector <10; fixed 0x20-byte copy", witnesses=["0x11ce8..0x11cfa", "0x22c62..0x22cfa"], caveat="short outer frames could source-over-read the fixed record, but destination size is fixed"),
    0x55: _audit("EXCLUDED_PERSISTENT", "Daily-time GIF/content reaches the shared 0xfdb4 storage-capable pipeline; excluded from volatile route.", persistent=True, control="GIF/content payload", landing="shared content/file pipeline", witnesses=["0x11da8..0x11db4", "0xfdb4"]),
    0x56: _audit("CLOSED_BOUNDS_SAFE", "Time-manage variable payload is copied only after allocating caller_length+0x1c; helper copies a fixed 0x1c header followed by exactly caller_length bytes.", control="fixed header + caller u16 data length + packet+13 data", landing="allocation sized header+payload", bounds="alloc len+0x1c; fixed header 0x1c; payload copy len", witnesses=["0x11dba..0x11e28", "0x134a8..0x13668"]),
    0x5B: _audit("CLOSED_NO_CONTROL", "Encoded-picture command reuses the audited bounded image decoder; palette/output writes remain bounded and no callback/pointer overwrite was found.", control="encoded picture stream", landing="bounded image decoder", bounds="same palette/output bounds as 0x44", witnesses=["0x11f04..0x11f0a", "0x359c8", "0x14db8"]),
    0x5C: _audit("EXCLUDED_PERSISTENT", "Encoded-play content reaches 0xfdb4, whose command 0x5c branch participates in storage erase/program setup; excluded from volatile route.", persistent=True, control="encoded playback content", landing="shared content/file pipeline", witnesses=["0x11f0c..0x11f14", "0x35a58", "0xfdb4", "0x1beca"]),
    0x5D: _audit("CLOSED_BOUNDS_SAFE", "Network-temperature content clamps count to 0x27, then copies 2*count bytes at offset 7 into an 0x58-byte object: maximum end offset 0x55, inside capacity.", control="fixed six-byte header + count + entries", landing="0x58-byte heap object", bounds="count<=0x27; copy<=0x4e bytes at +7", witnesses=["0x11f16..0x11f1c", "0x15828..0x158c2"]),
    0x5E: _audit("CLOSED_BOUNDS_SAFE", "Network-temperature display info consumes a fixed two-byte selector/bitmask plus fixed scalar time fields; no variable copy.", control="fixed fields", witnesses=["0x11f1e..0x11f24", "0x157dc..0x15826"]),
    0x5F: _audit("CLOSED_BOUNDS_SAFE", "Current network-temperature command consumes exactly two caller bytes into fixed state.", control="two bytes", witnesses=["0x11f26..0x11f2c", "0x158c4..0x15902"]),
    0x6A: _audit("CLOSED_BOUNDS_SAFE", "Music-mode command selects synchronous event 0x1c and passes only its fixed small mode record; no packet pointer survives the event dispatch.", control="small fixed mode record", landing="synchronous event state", witnesses=["0x11f2e..0x11f9c", "0x71b8", "0x12a26"]),
    0x6D: _audit("CLOSED_NO_CONTROL", "Multi-movie play feeds the same bounded media/event object family as 0x6c; caller data stays in the media staging region and does not reach the callback slot.", control="movie fixed header + bounded media data", landing="media object", bounds="same object separation as 0x6c", witnesses=["0x12014..0x1201a", "0x35990", "event 0x0b", "0x34144"]),
    0x6E: _audit("CLOSED_BOUNDS_SAFE", "Movie control sends one fixed control byte and performs start/stop state transitions only; no variable content copy.", control="packet[1] control", landing="movie state machine", witnesses=["0x11278..0x11354"]),
    0x6F: _audit("CLOSED_BOUNDS_SAFE", "Multi-pad-enter path forwards exactly three caller bytes to a helper that copies those three bytes into fixed state.", control="three bytes", bounds="fixed three-byte record", witnesses=["0x11e4a..0x11e60", "0x14e06..0x14e26"]),
    0x72: _audit("CLOSED_BOUNDS_SAFE", "Tool-info setter requires selector <4 and dispatches fixed fields through 0x14104; no caller-sized copy or writable callback path.", control="selector<4 + fixed mode fields", landing="fixed tool state", bounds="selector <4", witnesses=["0x12074..0x12102", "0x14104"]),
    0x75: _audit("CLOSED_BOUNDS_SAFE", "Device-name path bounds the caller name contribution against a 0x1a-character record before copy; backing message object has 0x20-byte name fields.", control="mode/length byte + packet+2 name", landing="fixed name fields in message object", bounds="caller contribution truncated so prefix+name+terminator <=0x1a", witnesses=["0x12142..0x12154", "0x9a8a..0x9c12"]),
    0x77: _audit("CLOSED_NO_CONTROL", "Multi-device control is a selector-driven fixed-field state machine. Deep helper review found no caller-sized memcpy/allocation and no packet-derived indirect control sink.", control="operation selector + fixed scalar fields", landing="device-control state", witnesses=["0x1216c..0x12174", "0x352de..0x35780"]),
    0x78: _audit("CLOSED_BOUNDS_SAFE", "Device-control follow-up consumes fixed scalar fields and writes only fixed internal state; no variable copy.", control="fixed control bytes", landing="device-control state", witnesses=["0x12176..0x1217e", "0x358f4..0x35960"]),
    0x7E: _audit("EXCLUDED_PERSISTENT", "Leave-message GIF/content routes directly into the shared 0xfdb4 storage-capable pipeline; excluded from volatile route.", persistent=True, control="packet+1 content", landing="shared content/file pipeline", witnesses=["0x11bb2..0x11bb6", "0x11db2..0x11db4", "0xfdb4"]),
    0x81: _audit("CLOSED_BOUNDS_SAFE", "Allocates a 0x48-byte message object and copies exactly eight caller bytes into object+0x12 before normal message dispatch.", control="eight bytes", landing="0x48-byte message object +0x12", bounds="fixed eight-byte copy within object", witnesses=["0x121c6..0x1220e"]),
    0x86: _audit("CLOSED_BOUNDS_SAFE", "Caller count is clamped to 0x40 and copy length is 2*count, so the stack copy is at most 128 bytes within the dispatcher frame.", control="mode + count + 2*count bytes", landing="dispatcher stack buffer", bounds="count<=0x40; copy<=0x80", witnesses=["0x10e02..0x10e34"]),
    0x8B: _audit("EXCLUDED_PERSISTENT", "NEW_GIF_CMD2020 uses a bounded streaming context whose setup invokes storage erase/program primitives; excluded from RAM-only route.", persistent=True, control="chunked GIF stream", landing="bounded persistent streaming context", witnesses=["0x108ea..0x10a84", "0x37022..0x3716e", "0x1beca/0x1be82"]),
    0x8C: _audit("EXCLUDED_PERSISTENT", "NEW_USER_DEFINE2020 uses the same bounded storage-backed streaming context as 0x8b; excluded from RAM-only route.", persistent=True, control="chunked user-defined stream", landing="bounded persistent streaming context", witnesses=["0x107de..0x108e8", "0x37022..0x3716e", "0x1beca/0x1be82"]),
    0xA1: _audit("CLOSED_BOUNDS_SAFE", "Talk command uses packet[1] as start/stop and passes packet+2 only to fixed mode 0x0d of 0x14104, which consumes fixed fields/state.", control="start/stop byte + fixed talk config", landing="talk/audio state", witnesses=["0x122c8..0x123e4", "0x14104 mode 0x0d -> 0x1435e"]),
    0xAD: _audit("CLOSED_BOUNDS_SAFE", "Sleep-color helper consumes exactly three caller bytes into fixed global state.", control="three bytes", landing="fixed sleep-color state", bounds="fixed three-byte write", witnesses=["0x12564..0x1256a", "0x39cfa..0x39d32"]),
    0xB5: _audit("CLOSED_BOUNDS_SAFE", "Allocates exactly eight bytes and populates fixed fields from packet offsets 1,3,5,6,7; no variable copy or caller-derived destination.", control="fixed sparse fields", landing="8-byte heap object", bounds="exact 8-byte allocation/fixed stores", witnesses=["0x114c8..0x1152a"]),
    0xB7: _audit("EXCLUDED_PERSISTENT", "Routes packet+2 to the shared 0xfdb4 content pipeline under command 0xb7; because that pipeline has storage mutation branches, exclude it from volatile work.", persistent=True, control="packet+2 content", landing="shared content/file pipeline", witnesses=["0x11c94..0x11ca4", "0xfdb4"]),
    0xBC: _audit("CLOSED_BOUNDS_SAFE", "New mix-music mode dispatches synchronous event 0x1d; its event handler consumes only a fixed two-byte mode record.", control="fixed mode record", landing="synchronous event state", witnesses=["0x11f9c..0x11fcc", "0x71b8", "0x12a26", "0x323b6"]),
    0xBD: _audit("CLOSED_NESTED_MUX", "Top-level EXTERN handler validates subcommand in 0x13..0x1b before its 9-way jump table; every implemented first-level subcommand is separately terminally audited below.", control="subcommand byte + fixed nested fields", landing="bounded nested mux", bounds="subcommand-0x13 <9", witnesses=["0x10a88..0x10aaa"]),
    0xFA: _audit("EXCLUDED_PERSISTENT", "Passes a fixed 0x100-byte block into 0xeb74 -> 0x2323c -> bounded streaming writer 0x508ea; storage-backed path is excluded from volatile work.", persistent=True, control="fixed 256-byte block", landing="persistent streaming writer", bounds="fixed 0x100 front-end; writer capacity-checks", witnesses=["0x10d6c..0x10d76", "0xeb74..0xebcc", "0x2323c..0x2325e", "0x508ea"]),
})

# Commands screened as scalar/fixed-control only on the pinned reference branch.
# The handler-local CFG review found no packet pointer or outer caller length forwarded
# into a content/copy parser and no caller-tainted indirect control sink. They are
# terminal for Tier-1 bulk-parser triage; this is not a claim that every scalar helper
# is mathematically free of all possible logic bugs.
SCALAR_SCREENED = {
    0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x10,0x11,0x12,0x13,0x15,0x17,0x1A,0x1C,0x23,0x26,
    0x2B,0x2D,0x31,0x32,0x42,0x46,0x47,0x48,0x4B,0x53,0x57,0x59,0x5A,0x71,0x73,0x74,0x76,
    0x79,0x7D,0x7F,0x80,0x82,0x83,0x84,0x85,0x88,0x8A,0x97,0x9A,0xA0,0xA2,0xA3,0xA4,0xA5,
    0xA6,0xA7,0xA8,0xA9,0xAA,0xAB,0xAC,0xAE,0xAF,0xB0,0xB2,0xB3,0xB4,0xB6,0xB8,0xB9,0xBA,
    0xBB,0xFB,
}

EXTERN_AUDIT = {
    0x13: ("CLOSED_BOUNDS_SAFE", "No caller payload beyond nested selector reaches a variable destination."),
    0x14: ("CLOSED_BOUNDS_SAFE", "Fixed u16 packet+2 forwarded as scalar."),
    0x15: ("CLOSED_BOUNDS_SAFE", "Read/query path; response construction only."),
    0x16: ("CLOSED_BOUNDS_SAFE", "Fixed byte packet[2] forwarded as scalar."),
    0x17: ("CLOSED_BOUNDS_SAFE", "Fixed byte packet[2], with 0xff query sentinel."),
    0x18: ("CLOSED_BOUNDS_SAFE", "Read/query response path."),
    0x19: ("CLOSED_BOUNDS_SAFE", "Fixed byte packet[2], with 0xff query sentinel."),
    0x1A: ("CLOSED_BOUNDS_SAFE", "Fixed byte packet[2], with 0xff query sentinel."),
    0x1B: ("CLOSED_BOUNDS_SAFE", "Fixed u16 packet+2 scalar/magic-value path."),
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 2], "little")


def _hex(n: int) -> str:
    return f"0x{n:x}"


def _mem_signals(data: bytes, start: int, end: int) -> list[dict[str, Any]]:
    """Decode only simple Thumb-1 immediate load/store forms in a linear slot window."""
    kinds = {
        0x6000: ("str", 4),
        0x6800: ("ldr", 4),
        0x7000: ("strb", 1),
        0x7800: ("ldrb", 1),
        0x8000: ("strh", 2),
        0x8800: ("ldrh", 2),
    }
    out = []
    for off in range(start, max(start, end - 1), 2):
        h = _u16(data, off)
        top = h & 0xF800
        if top not in kinds:
            continue
        kind, scale = kinds[top]
        imm5 = (h >> 6) & 0x1F
        rn = (h >> 3) & 7
        rt = h & 7
        disp = imm5 * scale
        if rn in (4, 7):
            out.append({"offset": _hex(off), "op": kind, "base": f"r{rn}", "disp": disp, "rt": f"r{rt}"})
    return out


def _direct_calls(data: bytes, start: int, end: int) -> list[dict[str, str]]:
    out = []
    for off in range(start, max(start, end - 3), 2):
        tgt = thumb_bl_target(data, off)
        if tgt is not None:
            out.append({"callsite": _hex(off), "target": _hex(tgt)})
    return out


def _extern_map(data: bytes) -> dict[int, int]:
    if data[EXTERN_HANDLER:EXTERN_HANDLER + 18].hex() != "78781338092804d202a31b181b5a5b009f44":
        raise ValueError("EXTERN mux prefix drift")
    return {sub: EXTERN_TABLE + 2 * _u16(data, EXTERN_TABLE + 2 * i) for i, sub in enumerate(range(0x13, 0x1C))}


def _load_branch(name: str, spec: dict[str, Any]) -> tuple[bytes, dict[int, int]]:
    data = Path(spec["path"]).read_bytes()
    if len(data) != spec["size"] or _hash(data) != spec["sha256"]:
        raise ValueError(f"{name} corpus identity drift")
    dm = dispatch_map(data, DISPATCH_TABLE, DISPATCH_JUMP_BASE)
    if len(dm) != 251 or set(dm) != set(range(0x04, 0xFF)):
        raise ValueError(f"{name} dispatcher coverage drift")
    if dm[EXTERN_CMD] != EXTERN_HANDLER:
        raise ValueError(f"{name} EXTERN target drift")
    return data, dm


def _lineage(targets: dict[str, int]) -> str:
    vals = list(targets.values())
    if len(set(vals)) == 1:
        return "STABLE_4_OF_4_EXACT"
    first3 = [targets[k] for k in ("flag42_prod_v42016", "flag42_test_v42017", "flag60_test_api60016_internal60017")]
    if len(set(first3)) == 1:
        return "FLAG60_PROD_DIVERGENCE_ONLY"
    return "BRANCH_DIVERGENT"


def build_report() -> dict[str, Any]:
    loaded: dict[str, tuple[bytes, dict[int, int]]] = {}
    for name, spec in BRANCHES.items():
        loaded[name] = _load_branch(name, spec)

    ref_data, ref_dm = loaded["flag42_prod_v42016"]
    unique_targets = sorted(set(t for t in ref_dm.values() if t != PRIMARY_DEFAULT))
    next_target = {t: min([x for x in unique_targets if x > t] + [DISPATCH_END]) for t in unique_targets}

    slots = []
    status_counts = Counter()
    first_pass_counts = Counter()
    for cmd in range(0x04, 0xFF):
        targets = {name: dm[cmd] for name, (_, dm) in loaded.items()}
        ref_t = ref_dm[cmd]
        if all(t == PRIMARY_DEFAULT for t in targets.values()):
            fp = "DEFAULT_PRIMARY"
            terminal = "CLOSED_NO_CONTROL"
            detail = {"status": terminal, "summary": "Primary default/error dispatch; no command-specific parser."}
            signals: list[dict[str, Any]] = []
            calls: list[dict[str, str]] = []
        elif all(t == SECONDARY_DEFAULT for t in targets.values()):
            fp = "DEFAULT_SECONDARY"
            terminal = "CLOSED_NO_CONTROL"
            detail = {"status": terminal, "summary": "Shared secondary/default handler; no command-specific caller-data parser."}
            signals = _mem_signals(ref_data, ref_t, next_target.get(ref_t, DISPATCH_END))
            calls = _direct_calls(ref_data, ref_t, next_target.get(ref_t, DISPATCH_END))
        else:
            end = next_target.get(ref_t, DISPATCH_END)
            signals = _mem_signals(ref_data, ref_t, end)
            calls = _direct_calls(ref_data, ref_t, end)
            if cmd in AUDITED:
                detail = AUDITED[cmd]
                terminal = detail["status"]
                fp = "VRAM2_AUDITED"
            elif cmd in SCALAR_SCREENED:
                detail = {
                    "status": "CLOSED_SCALAR_CONTROL",
                    "summary": "Handler-local caller-data screen is scalar/fixed-control only: no packet pointer or outer caller length is forwarded to a content/copy parser and no caller-tainted indirect control sink is present at the direct SPP boundary.",
                    "persistent": False,
                    "indirect_control_sink": False,
                }
                terminal = detail["status"]
                fp = "VRAM2_SCALAR_SCREENED"
            else:
                # First-pass classification is evidence-bearing but deliberately non-terminal.
                has_len = any(s["base"] == "r4" and s["op"].startswith("ldr") and s["disp"] in (2, 4) for s in signals)
                has_packet = any(s["base"] in ("r4", "r7") and s["op"].startswith("ldr") for s in signals)
                fp = "DIRECT_LENGTH_SIGNAL_UNRESOLVED" if has_len else ("DIRECT_PACKET_SIGNAL_UNRESOLVED" if has_packet else "NO_DIRECT_PACKET_LENGTH_SIGNAL_UNRESOLVED")
                terminal = "UNRESOLVED"
                detail = {
                    "status": terminal,
                    "summary": "No terminal conclusion promoted. Linear-window signals are atlas/ranking evidence only; transitive parser audit is required before closure.",
                }
        status_counts[terminal] += 1
        first_pass_counts[fp] += 1
        slots.append({
            "command": cmd,
            "command_hex": f"0x{cmd:02x}",
            "label": KNOWN_LABELS.get(cmd),
            "targets": {k: _hex(v) for k, v in targets.items()},
            "lineage": _lineage(targets),
            "reference_target": _hex(ref_t),
            "first_pass": fp,
            "linear_window_signals": signals,
            "linear_window_direct_calls": calls,
            "vram2": detail,
        })

    extern_by_branch = {name: _extern_map(data) for name, (data, _) in loaded.items()}
    nested = []
    for sub in range(0x13, 0x1C):
        targets = {name: m[sub] for name, m in extern_by_branch.items()}
        status, summary = EXTERN_AUDIT[sub]
        nested.append({
            "parent_command": "0xbd",
            "subcommand": sub,
            "subcommand_hex": f"0x{sub:02x}",
            "targets": {k: _hex(v) for k, v in targets.items()},
            "lineage": _lineage(targets),
            "status": status,
            "summary": summary,
        })

    branch_stats = {}
    for name, (_, dm) in loaded.items():
        c = Counter(dm.values())
        branch_stats[name] = {
            "primary_default_slots": c[PRIMARY_DEFAULT],
            "secondary_default_slots": c[SECONDARY_DEFAULT],
            "non_primary_default_slots": 251 - c[PRIMARY_DEFAULT],
            "unique_non_primary_targets": len(set(v for v in dm.values() if v != PRIMARY_DEFAULT)),
        }

    prod60_diff = [cmd for cmd in range(0x04, 0xFF) if loaded["flag60_prod_v60014"][1][cmd] != loaded["flag60_test_api60016_internal60017"][1][cmd]]
    if prod60_diff != [0x1B, 0x51, 0x52, 0x53, 0x54, 0xB6, 0xB7]:
        raise ValueError(f"expected preserved flag60 production divergence drifted: {prod60_diff}")

    explicit_real = {cmd for cmd in range(0x04, 0xFF) if ref_dm[cmd] not in (PRIMARY_DEFAULT, SECONDARY_DEFAULT)}
    classified_real = (set(AUDITED) | set(SCALAR_SCREENED)) & explicit_real
    missing_real = sorted(explicit_real - classified_real)
    if missing_real:
        raise ValueError(f"explicit SPP handlers lack terminal VRAM-2 classification: {[hex(x) for x in missing_real]}")
    audited_status = Counter(AUDITED[c]["status"] for c in AUDITED)
    return {
        "schema_version": 1,
        "kind": "ditoo_plus_spp_volatile_ram_api_surface",
        "ok": True,
        "safety": {
            "offline_analysis_only": True,
            "device_io": False,
            "live_packet_generation": False,
            "runtime_018_touched": False,
            "persistent_mutation": False,
        },
        "corpus": {
            name: {
                "path": str(Path(spec["path"]).relative_to(ROOT)),
                "sha256": spec["sha256"],
                "size_bytes": spec["size"],
                "kind": spec["kind"],
                "hardware_flag": spec["hardware_flag"],
            }
            for name, spec in BRANCHES.items()
        },
        "dispatcher": {
            "command_range": [4, 254],
            "slot_count": 251,
            "table_read_base": _hex(DISPATCH_TABLE),
            "jump_base": _hex(DISPATCH_JUMP_BASE),
            "primary_default": _hex(PRIMARY_DEFAULT),
            "secondary_default": _hex(SECONDARY_DEFAULT),
            "reference_real_slots_including_secondary_default": 251 - branch_stats["flag42_prod_v42016"]["primary_default_slots"],
            "reference_unique_non_primary_targets": branch_stats["flag42_prod_v42016"]["unique_non_primary_targets"],
            "branch_stats": branch_stats,
            "flag60_prod_vs_test_differing_slots": [f"0x{x:02x}" for x in prod60_diff],
        },
        "slots": slots,
        "nested_muxes": {"0xbd": nested},
        "coverage": {
            "top_level_slots_total": 251,
            "top_level_slots_emitted": len(slots),
            "nested_extern_slots_total": 9,
            "nested_extern_slots_emitted": len(nested),
            "terminal_status_counts": dict(sorted(status_counts.items())),
            "first_pass_counts": dict(sorted(first_pass_counts.items())),
            "explicit_vram2_audited_commands": [f"0x{x:02x}" for x in sorted(AUDITED)],
            "scalar_screened_commands": [f"0x{x:02x}" for x in sorted(SCALAR_SCREENED)],
            "explicit_real_handlers_total": len(explicit_real),
            "explicit_real_handlers_terminally_classified": len(classified_real),
            "explicit_vram2_status_counts": dict(sorted(audited_status.items())),
            "unresolved_top_level_commands": [s["command_hex"] for s in slots if s["vram2"]["status"] == "UNRESOLVED"],
        },
        "accepted_early_vram2_conclusions": {
            "candidate_for_live_manifest": None,
            "direct_controlled_ram_write_or_control_flow_primitive_found": False,
            "tier1_direct_spp_surface_closed": True,
            "notable_noncontrol_findings": [
                "0x44 internal image decode trusts source consumption more than outer SPP length, but audited palette/output writes remain bounded",
                "0x50 packet[1] can drive an unchecked table read, but variable heap copies are allocation-matched",
                "0x18 has a fixed 8-byte source over-read possibility for undersized outer payloads, with exact-size destination",
                "0x3c caller u16 can drive a compare/read over-read but not a mutable destination copy",
                "0x5d clamps variable entry count so its maximum copy remains inside an 0x58-byte object",
            ],
            "next_named_surface_if_direct_handlers_close": "Tier-2 external media/codec sink behind 0x6c -> 0x34144 -> fixed fallback 0xA6490 / registered media callback",
        },
        "method_limits": [
            "Linear-window load/call signals are ranking evidence, not decompilation truth; inline data/shared tails can exist.",
            "Deep AUDITED commands have byte/helper-level conclusions; SCALAR_SCREENED commands are terminal only for Tier-1 bulk-parser/control-flow triage and do not claim proof against every possible scalar logic bug.",
            "All 124 explicit non-default handlers are terminally classified on the pinned reference branch; corpus/dispatcher drift fails closed before conclusions emit.",
            "No MiniToo address, command number, bug, or memory map is used as Ditoo evidence.",
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
        cov = report["coverage"]
        print("DITOO_SPP_SURFACE=PASS")
        print(f"SPP_TOP_LEVEL_SLOTS={cov['top_level_slots_emitted']}")
        print(f"SPP_EXTERN_NESTED_SLOTS={cov['nested_extern_slots_emitted']}")
        print(f"SPP_VRAM2_AUDITED={len(cov['explicit_vram2_audited_commands'])}")
        print(f"SPP_UNRESOLVED={len(cov['unresolved_top_level_commands'])}")
        print("SPP_LIVE_MANIFEST_CANDIDATE=NONE")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_SPP_SURFACE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
