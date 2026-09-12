#!/usr/bin/env python3
"""Fail-closed offline audit of Tier-2 heap-victim placement candidates.

This does not generate packets or model a live heap address. It proves that stock callback-bearing
objects can be allocated/freed, but deliberately refuses to equate grooming capability with
predictable adjacency to the persistent display backing allocation.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from keypad_pipeline_report import thumb_bl_target

FW = ROOT / "artifacts" / "firmware"
BRANCHES = {
    "flag42_prod_v42016": {"file":"flag42_v42016.bin","sha":"f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a","size":1207313,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4},
    "flag42_test_v42017": {"file":"flag42_v42017_test.bin","sha":"6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc","size":1207333,"plugin":0x204A6,"destroy":0x20766,"runtime50":0x1F9E8},
    "flag60_prod_v60014": {"file":"flag60_v60014.bin","sha":"02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300","size":1207165,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4},
    "flag60_test_api60016_internal60017": {"file":"flag60_api60016_internal60017_test.bin","sha":"05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339","size":1207313,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4},
}
PLUGIN_CALLBACK_PATTERN = bytes.fromhex("e168201c8847")   # ldr r1,[r4,#0x0c]; mov r0,r4; blx r1
RUNTIME50_CALLBACK_PATTERN = bytes.fromhex("486b002801d0486b8047")
PLUGIN_ALLOC_SIZE_SETUP = bytes.fromhex("8020")
PLUGIN_ZERO_SETUP = bytes.fromhex("8021201c")
PLUGIN_DESCRIPTOR_COPY_SETUP = bytes.fromhex("3422311c201c0c30")
RUNTIME50_ALLOC_SIZE_SETUP = bytes.fromhex("5020")


def _load(name:str,s:dict[str,Any])->bytes:
    b=(FW/s["file"]).read_bytes()
    if len(b)!=s["size"] or hashlib.sha256(b).hexdigest()!=s["sha"]:
        raise ValueError(f"{name}: corpus identity drift")
    return b

def _unique(b:bytes,needle:bytes,label:str,name:str)->int:
    hits=[]; p=0
    while True:
        i=b.find(needle,p)
        if i<0: break
        hits.append(i); p=i+1
    if len(hits)!=1:
        raise ValueError(f"{name}: {label} not unique: {hits}")
    return hits[0]

def _branch(name:str,s:dict[str,Any])->dict[str,Any]:
    b=_load(name,s); p=s["plugin"]; d=s["destroy"]; r=s["runtime50"]
    # Constructor shape: movs r0,#0x80; BL app malloc; memset(...,0x80); copy 0x34 bytes to +0x0c.
    if b[p+0x20:p+0x22] != PLUGIN_ALLOC_SIZE_SETUP or thumb_bl_target(b,p+0x22)!=0xBFBC:
        raise ValueError(f"{name}: plugin 0x80 allocation drift")
    if b[p+0x32:p+0x36] != PLUGIN_ZERO_SETUP:
        raise ValueError(f"{name}: plugin zero-on-create drift")
    if b[p+0x3A:p+0x42] != PLUGIN_DESCRIPTOR_COPY_SETUP:
        raise ValueError(f"{name}: plugin descriptor copy drift")
    cb=_unique(b,PLUGIN_CALLBACK_PATTERN,"plugin +0x0c callback",name)
    if cb not in range(p,p+0x80):
        raise ValueError(f"{name}: plugin callback moved outside constructor family")
    # Destructor frees nested allocations and finally the object itself through app free.
    frees=[o for o in range(d,d+0x70,2) if thumb_bl_target(b,o)==0xBFCE]
    if not frees:
        raise ValueError(f"{name}: plugin destructor no longer frees via app heap")
    # Separate 0x50-byte runtime object with callback at +0x34.
    if b[r+2:r+4] != RUNTIME50_ALLOC_SIZE_SETUP or thumb_bl_target(b,r+4)!=0xBFBC:
        raise ValueError(f"{name}: runtime50 allocation drift")
    rcb=_unique(b,RUNTIME50_CALLBACK_PATTERN,"runtime50 +0x34 callback",name)
    return {
        "plugin_constructor":hex(p),
        "plugin_object_request_bytes":0x80,
        "plugin_zeroed_on_create":True,
        "plugin_descriptor_copy_bytes":0x34,
        "plugin_descriptor_destination_offset":hex(0x0C),
        "plugin_callback_0x0c_invoke":hex(cb),
        "plugin_destructor":hex(d),
        "plugin_app_heap_free_calls":[hex(x) for x in frees],
        "runtime50_constructor":hex(r),
        "runtime50_request_bytes":0x50,
        "runtime50_callback_offset":hex(0x34),
        "runtime50_callback_invoke":hex(rcb+8),
    }

def build_report()->dict[str,Any]:
    branches={n:_branch(n,s) for n,s in BRANCHES.items()}
    return {
        "schema_version":1,
        "kind":"ditoo_plus_tier2_victim_placement",
        "ok":True,
        "safety":{"offline_analysis_only":True,"device_io":False,"live_packet_generation":False,"firmware_mutation":False,"persistent_mutation":False,"runtime_018_touched":False},
        "branches":branches,
        "stock_grooming_surface":{
            "exists":True,
            "plugin_object":{"request_bytes":0x80,"zeroed_on_create":True,"descriptor_copied_to_offset":hex(0x0C),"known_indirect_fields":[hex(0x0C),hex(0x20),hex(0x2C)],"whole_object_free_recreate":True},
            "runtime50_object":{"request_bytes":0x50,"callback_offset":hex(0x34)},
            "meaning":"Stock lifecycle code provides real app-heap allocate/free/recreate behavior for callback-bearing objects.",
        },
        "placement_gate":{
            "deterministic_adjacent_victim_proven":False,
            "controlled_indirect_branch_proven":False,
            "prefill_free_space_strategy_closed":True,
            "recreate_same_size_is_not_adjacency_proof":True,
            "why_not": [
                "The application allocator is best-fit/separate-descriptor and the heap is already fragmented before the persistent display backing allocation.",
                "Plugin creation clears all 0x80 bytes and then repopulates descriptor fields, so pre-seeding a free block cannot preserve a forged callback through creation.",
                "Free/recreate demonstrates grooming capability but does not prove which equally suitable hole will be selected without an exact allocator-state or uniquely constrained-hole model.",
                "No runtime address for the Tier-2 display backing block or exact adjacent free-hole topology is statically established yet.",
            ],
            "remaining_offline_question":"EXACT_DISPLAY_BLOCK_ADDRESS_OR_UNIQUE_ADJACENT_HOLE_MODEL",
            "live_manifest_candidate":None,
        },
        "next_bounded_work":[
            "Reconstruct allocator state only up to the persistent 0x708 display backing allocation and determine whether any pre-existing free hole can satisfy 0x710 physical units.",
            "If the display allocation is forced into the main extent, account only subsequent allocations/frees within the 1009-byte overwrite reach and test for a uniquely placeable callback object.",
            "If multiple viable layouts remain, keep live promotion closed rather than using crash behavior as a placement oracle.",
        ],
        "method_limits":["This proves stock grooming surfaces, not heap adjacency.","No live heap address, packet, crash probe or device observation was used."],
    }

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--write',type=Path); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args()
    r=build_report(); t=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.write: a.write.parent.mkdir(parents=True,exist_ok=True); a.write.write_text(t)
    if a.json: print(t,end='')
    if a.selfcheck:
        print('DITOO_TIER2_PLACEMENT=PASS')
        print(f"PLACEMENT_BRANCHES={len(r['branches'])}")
        print('PLACEMENT_STOCK_GROOMING=true')
        print('PLACEMENT_DETERMINISTIC_VICTIM=false')
        print('PLACEMENT_LIVE_MANIFEST_CANDIDATE=NONE')
    if not (a.write or a.json or a.selfcheck): print('DITOO_TIER2_PLACEMENT=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
