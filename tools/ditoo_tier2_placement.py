#!/usr/bin/env python3
"""Fail-closed offline audit of Tier-2 heap-victim placement candidates.

This does not generate packets or touch a live heap. It proves stock callback-bearing objects
can be allocated/freed and reconstructs a useful *conditional* cold-start layout, but refuses
to promote that layout unless the framework-owned pre-main heap chronology is proven.
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
    "flag42_prod_v42016": {"file":"flag42_v42016.bin","sha":"f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a","size":1207313,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4,"pre_persistent":0x183E4,"pre_init":0x184E8,"display_startup":0x1BC1C,"display_inner":0x1BB18,"display_root":0x374B4,"backing":0x3B714,"post60":0x3A0E8,"root80":0x20014,"file_cache":0x4553C,"main_init":0x34C3C,"main_temp":0x1BAA2,"heap_init":0x3DF44},
    "flag42_test_v42017": {"file":"flag42_v42017_test.bin","sha":"6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc","size":1207333,"plugin":0x204A6,"destroy":0x20766,"runtime50":0x1F9E8,"pre_persistent":0x17746,"pre_init":0x1784A,"display_startup":0x1BC10,"display_inner":0x1BB0C,"display_root":0x374A8,"backing":0x3B728,"post60":0x3A0FC,"root80":0x20008,"file_cache":0x45550,"main_init":0x34C30,"main_temp":0x1BA96,"heap_init":0x3DF58},
    "flag60_prod_v60014": {"file":"flag60_v60014.bin","sha":"02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300","size":1207165,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4,"pre_persistent":0x183E4,"pre_init":0x184E8,"display_startup":0x1BC1C,"display_inner":0x1BB18,"display_root":0x37420,"backing":0x3B680,"post60":0x3A054,"root80":0x20014,"file_cache":0x454A8,"main_init":0x34BA8,"main_temp":0x1BAA2,"heap_init":0x3DEB0},
    "flag60_test_api60016_internal60017": {"file":"flag60_api60016_internal60017_test.bin","sha":"05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339","size":1207313,"plugin":0x204B2,"destroy":0x20772,"runtime50":0x1F9F4,"pre_persistent":0x183E4,"pre_init":0x184E8,"display_startup":0x1BC1C,"display_inner":0x1BB18,"display_root":0x374B4,"backing":0x3B714,"post60":0x3A0E8,"root80":0x20014,"file_cache":0x4553C,"main_init":0x34C3C,"main_temp":0x1BAA2,"heap_init":0x3DF44},
}
PLUGIN_CALLBACK_PATTERN = bytes.fromhex("e168201c8847")   # ldr r1,[r4,#0x0c]; mov r0,r4; blx r1
RUNTIME50_CALLBACK_PATTERN = bytes.fromhex("486b002801d0486b8047")
PLUGIN_ALLOC_SIZE_SETUP = bytes.fromhex("8020")
PLUGIN_ZERO_SETUP = bytes.fromhex("8021201c")
PLUGIN_DESCRIPTOR_COPY_SETUP = bytes.fromhex("3422311c201c0c30")
RUNTIME50_ALLOC_SIZE_SETUP = bytes.fromhex("5020")

APP_LINK_BASE = 0x08400000
FRAMEWORK_MAIN_ENTRY = 0x8DEA

def _direct_bl_xrefs(b:bytes,target:int)->list[int]:
    return [o for o in range(0,len(b)-4,2) if thumb_bl_target(b,o)==target]

def _absolute_app_pointer_xrefs(b:bytes,target:int)->list[int]:
    import struct
    out=[]
    for value in (APP_LINK_BASE+target, APP_LINK_BASE+target+1):
        needle=struct.pack('<I',value); p=0
        while True:
            i=b.find(needle,p)
            if i<0: break
            out.append(i); p=i+1
    return sorted(set(out))

HEAP_START = 0x00804000
HEAP_SIZE = 0x19000
ALLOC_QUANTUM = 0x10


def _round(n:int)->int:
    return (n + ALLOC_QUANTUM - 1) & ~(ALLOC_QUANTUM - 1)


def _simulate_pristine_heap_hypothesis()->dict[str,int]:
    free=[(HEAP_START,HEAP_SIZE)]
    live={}
    def alloc(name:str,request:int)->int:
        need=_round(request)
        choices=[(size,addr,i) for i,(addr,size) in enumerate(free) if size>=need]
        if not choices: raise ValueError(f"layout: no free extent for {name}")
        size,addr,i=min(choices, key=lambda x:(x[0],x[1]))
        if size==need: free.pop(i)
        else: free[i]=(addr+need,size-need)
        live[name]=(addr,need)
        return addr
    def release(name:str)->None:
        addr,size=live.pop(name); free.append((addr,size)); free.sort()
        merged=[]
        for a,n in free:
            if merged and merged[-1][0]+merged[-1][1]==a:
                merged[-1]=(merged[-1][0],merged[-1][1]+n)
            else: merged.append((a,n))
        free[:]=merged
    out={}
    out["pre_persistent_0x24"]=alloc("pre24",0x24)
    out["pre_temp_0x100"]=alloc("pre100",0x100)
    out["pre_persistent_0x14"]=alloc("pre14",0x14)
    release("pre100")
    out["display_root_0x318"]=alloc("display_root",0x318)
    out["display_backing_0x708"]=alloc("display_backing",0x708)
    out["post_display_0x54"]=alloc("post60",0x54)
    out["root_0x80"]=alloc("root80",0x80)
    out["file_cache_temp_0x400"]=alloc("cache400",0x400)
    out["file_cache_persistent_0x1a0"]=alloc("cache1a0",0x1A0)
    release("cache400")
    # The two main-init config objects and later config probes are temporary and freed
    # before runtime50. They can split this 0x400 gap transiently but cannot change
    # the placement of the >0x400 persistent allocation below.
    out["large_persistent_0x584"]=alloc("large584",0x584)
    out["runtime50_0x50"]=alloc("runtime50",0x50)
    out["runtime50_callback"]=out["runtime50_0x50"]+0x34
    out["display_data_pointer"]=out["display_backing_0x708"]+0x308
    out["callback_source_offset"]=out["runtime50_callback"]-out["display_data_pointer"]
    return out


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
    # Cold-start order is fixed at the common startup callsites. The official v42017
    # test branch relocates its config subsystem, so every target is branch-pinned.
    if thumb_bl_target(b,0x8DFE)!=s["pre_init"] or thumb_bl_target(b,0x8E02)!=s["display_startup"] or thumb_bl_target(b,0x8E10)!=s["post60"]:
        raise ValueError(f"{name}: pre/display startup order drift")
    if thumb_bl_target(b,0x8AB8)!=s["root80"] or thumb_bl_target(b,0x8ABC)!=s["main_init"] or thumb_bl_target(b,0x8AC4)!=0x7A18 or thumb_bl_target(b,0x8AF6)!=r:
        raise ValueError(f"{name}: post-display startup order drift")
    pp=s["pre_persistent"]; pi=s["pre_init"]
    if b[pp+0x0A:pp+0x0C] != bytes.fromhex("2420") or thumb_bl_target(b,pp+0x0C)!=0xBFBC:
        raise ValueError(f"{name}: pre-display 0x24 persistent allocation drift")
    if thumb_bl_target(b,pi+0x0E)!=pp or thumb_bl_target(b,pi+0x18)!=0xBFBC or b[pi+0x2E:pi+0x30]!=bytes.fromhex("1420") or thumb_bl_target(b,pi+0x30)!=0xBFBC or thumb_bl_target(b,pi+0x116)!=0xBFCE:
        raise ValueError(f"{name}: pre-display 0x100/0x14/free topology drift")
    ds=s["display_startup"]; di=s["display_inner"]; dr=s["display_root"]; ba=s["backing"]
    if thumb_bl_target(b,ds+0x18)!=di or thumb_bl_target(b,di+0x28)!=dr:
        raise ValueError(f"{name}: display-root call chain drift")
    if b[dr+0x0A:dr+0x0E] != bytes.fromhex("6325ed00") or thumb_bl_target(b,dr+0x10)!=0xBFBC:
        raise ValueError(f"{name}: display root 0x318 allocation drift")
    if b[ba+2:ba+6] != bytes.fromhex("e125ed00") or thumb_bl_target(b,ba+8)!=0xBFBC:
        raise ValueError(f"{name}: display backing 0x708 allocation drift")
    po=s["post60"]; ro=s["root80"]; fc=s["file_cache"]; mi=s["main_init"]; mt=s["main_temp"]
    if b[po+0x0A:po+0x0C]!=bytes.fromhex("5420") or thumb_bl_target(b,po+0x0C)!=0xBFBC:
        raise ValueError(f"{name}: post-display 0x54 allocation drift")
    if b[ro+2:ro+4]!=bytes.fromhex("8020") or thumb_bl_target(b,ro+4)!=0xBFBC:
        raise ValueError(f"{name}: root 0x80 allocation drift")
    if b[fc+2:fc+6]!=bytes.fromhex("01208002") or thumb_bl_target(b,fc+6)!=0xBFBC or b[fc+0x3E:fc+0x42]!=bytes.fromhex("ff20a130") or thumb_bl_target(b,fc+0x42)!=0xBFBC or thumb_bl_target(b,fc+0x54)!=0xBFCE:
        raise ValueError(f"{name}: 0x400-temp/0x1a0-persistent cache topology drift")
    if thumb_bl_target(b,mi+6)!=fc or thumb_bl_target(b,mi+0x5A)!=0x1479A or thumb_bl_target(b,mi+0x84)!=0xBFCE or thumb_bl_target(b,mi+0x8A)!=0xBFCE:
        raise ValueError(f"{name}: main-init temp/free topology drift")
    if thumb_bl_target(b,mt+0x0A) not in (0x18604,0x17F6A) or thumb_bl_target(b,mt+0x20)!=0xBFCE:
        raise ValueError(f"{name}: final temporary config free drift")
    if thumb_bl_target(b,0x147A4)!=0xBFBC:
        raise ValueError(f"{name}: large persistent allocation call drift")
    import struct
    if struct.unpack_from("<I",b,0x14B04)[0] != 0x584:
        raise ValueError(f"{name}: large persistent allocation size drift")
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
    # Display root/backing lifetime check: one direct constructor edge and no app-heap
    # free in the audited display/backing service windows. This closes the simple
    # "free the vulnerable block and recreate it into a groomed hole" strategy.
    root_callers=_direct_bl_xrefs(b,dr)
    if root_callers != [di+0x28]:
        raise ValueError(f"{name}: display root constructor caller drift {root_callers}")
    display_frees=[o for o in range(max(0,dr-0x134),min(len(b),dr+0x48c),2) if thumb_bl_target(b,o)==0xBFCE]
    backing_frees=[o for o in range(max(0,ba-0xD4),min(len(b),ba+0x13c),2) if thumb_bl_target(b,o)==0xBFCE]
    if display_frees or backing_frees:
        raise ValueError(f"{name}: display/backing app-heap free surface changed")

    # The callback-bearing 0x80 object has only two direct constructor sites in the
    # preserved app. Both belong to singleton subsystem lifecycles reviewed manually;
    # there is no direct unbounded constructor spray surface.
    plugin_callers=_direct_bl_xrefs(b,p)
    if len(plugin_callers)!=2:
        raise ValueError(f"{name}: plugin constructor caller count drift {plugin_callers}")

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
        "plugin_direct_constructor_callers":[hex(x) for x in plugin_callers],
        "display_root_direct_constructor_callers":[hex(x) for x in root_callers],
        "display_service_app_heap_free_calls":[],
        "display_backing_service_app_heap_free_calls":[],
        "runtime50_constructor":hex(r),
        "runtime50_request_bytes":0x50,
        "runtime50_callback_offset":hex(0x34),
        "runtime50_callback_invoke":hex(rcb+8),
        "cold_start_pre_init":hex(pi),
        "cold_start_display_root":hex(dr),
        "cold_start_backing_allocator":hex(ba),
        "cold_start_file_cache":hex(fc),
        "cold_start_main_init":hex(mi),
    }

def build_report()->dict[str,Any]:
    branches={n:_branch(n,spec) for n,spec in BRANCHES.items()}
    layout=_simulate_pristine_heap_hypothesis()
    if layout["display_backing_0x708"] != 0x00804470 or layout["display_data_pointer"] != 0x00804778:
        raise ValueError("conditional layout: display address drift")
    if layout["runtime50_0x50"] != 0x00804B80 or layout["runtime50_callback"] != 0x00804BB4 or layout["callback_source_offset"] != 0x43C:
        raise ValueError("conditional layout: runtime50 adjacency drift")

    framework={}
    for name,spec in BRANCHES.items():
        b=_load(name,spec); hi=spec["heap_init"]
        if b[FRAMEWORK_MAIN_ENTRY:FRAMEWORK_MAIN_ENTRY+2] != bytes.fromhex("80b5"):
            raise ValueError(f"{name}: framework main entry prologue drift")
        main_bl=_direct_bl_xrefs(b,FRAMEWORK_MAIN_ENTRY)
        heap_bl=_direct_bl_xrefs(b,hi)
        main_abs=_absolute_app_pointer_xrefs(b,FRAMEWORK_MAIN_ENTRY)
        heap_abs=_absolute_app_pointer_xrefs(b,hi)
        if main_bl or heap_bl or main_abs or heap_abs:
            raise ValueError(f"{name}: framework ordering evidence changed: main_bl={main_bl} heap_bl={heap_bl} main_abs={main_abs} heap_abs={heap_abs}")
        framework[name]={
            "framework_main_entry":hex(FRAMEWORK_MAIN_ENTRY),
            "heap_init":hex(hi),
            "direct_bl_xrefs_to_main":[],
            "direct_bl_xrefs_to_heap_init":[],
            "raw_absolute_app_pointer_xrefs_to_main":[],
            "raw_absolute_app_pointer_xrefs_to_heap_init":[],
        }

    return {
        "schema_version":3,
        "kind":"ditoo_plus_tier2_victim_placement",
        "ok":True,
        "safety":{"offline_analysis_only":True,"device_io":False,"live_packet_generation":False,"firmware_mutation":False,"persistent_mutation":False,"runtime_018_touched":False},
        "branches":branches,
        "allocator_model":{
            "heap_start":hex(HEAP_START),"heap_end_exclusive":hex(HEAP_START+HEAP_SIZE),"allocation_quantum":ALLOC_QUANTUM,
            "policy":"BEST_FIT_LOW_ADDRESS_SPLIT_SEPARATE_DESCRIPTORS_WITH_ADJACENT_FREE_COALESCING",
            "reviewed_startup_allocations":"The in-image 0x8dea path, once entered, has branch-pinned allocation/free ordering through the display backing and later runtime50 construction.",
        },
        "framework_ordering_gate":{
            "app_link_base":hex(APP_LINK_BASE),
            "branches":framework,
            "heap_reset_before_framework_main_proven":False,
            "no_intervening_app_heap_users_proven":False,
            "reason":"Both Fwl_MallocInit and the 0x8dea application main entry have zero direct in-image BL/BLX callers and zero raw absolute application-pointer xrefs across all four preserved branches. Their ordering is therefore mediated by framework/bootstrap state not represented as a directly recoverable call edge in this corpus.",
            "status":"PRE_MAIN_HEAP_STATE_AFTER_FWL_MALLOCINIT_UNPROVEN",
        },
        "conditional_pristine_heap_hypothesis":{
            "assumption":"Fwl_MallocInit resets the 0x00804000..0x0081cfff application heap immediately before the modeled 0x8dea startup sequence, with no intervening app-heap allocations.",
            "assumption_proven":False,
            "layout_if_true":{k:hex(v) for k,v in layout.items() if k!="callback_source_offset"},
            "runtime50_callback_source_offset_if_true":layout["callback_source_offset"],
            "runtime50_callback_fully_controlled_if_true":True,
            "meaning":"This is a useful candidate geometry only. The addresses 0x00804470/0x00804b80/0x00804bb4 are not promoted as observed or deterministic runtime addresses.",
        },
        "placement_strategy_closures":{
            "display_teardown_recreate":{
                "status":"CLOSED_WITHIN_AUDITED_APP_GRAPH",
                "root_constructor_has_one_direct_caller_4_of_4":True,
                "app_heap_free_in_display_service_window":False,
                "app_heap_free_in_backing_service_window":False,
                "meaning":"No stock app-heap teardown/recreate path for the persistent display root/backing was found in the audited service families, so moving the vulnerable block by ordinary teardown/recreate is not a supported placement strategy."
            },
            "plugin_0x80_spray":{
                "status":"CLOSED_AS_UNBOUNDED_DIRECT_SPRAY",
                "direct_constructor_sites_per_branch":2,
                "reviewed_as_singleton_subsystem_lifecycles":True,
                "unbounded_stock_spray_found":False,
                "meaning":"The 0x80 callback-bearing object is genuinely free/recreate capable, but its only two direct construction sites are singleton subsystem paths rather than an unbounded allocation spray."
            }
        },
        "stock_grooming_surface":{
            "exists":True,
            "plugin_object":{"request_bytes":0x80,"zeroed_on_create":True,"descriptor_copied_to_offset":hex(0x0C),"known_indirect_fields":[hex(0x0C),hex(0x20),hex(0x2C)],"whole_object_free_recreate":True},
            "runtime50_object":{"request_bytes":0x50,"callback_offset":hex(0x34),"conditional_base_if_pristine":hex(layout["runtime50_0x50"]),"conditional_callback_if_pristine":hex(layout["runtime50_callback"]),"conditional_callback_source_offset_if_pristine":layout["callback_source_offset"]},
            "meaning":"Stock lifecycle code provides real app-heap allocate/free/recreate behavior for callback-bearing objects, but grooming capability alone does not prove adjacency.",
        },
        "placement_gate":{
            "deterministic_adjacent_victim_proven":False,
            "controlled_callback_field_proven":False,
            "controlled_indirect_branch_proven":False,
            "conditional_runtime50_candidate":{
                "base":hex(layout["runtime50_0x50"]),
                "callback":hex(layout["runtime50_callback"]),
                "callback_source_offset":layout["callback_source_offset"],
                "minimum_source_length_to_fully_control_callback":layout["callback_source_offset"]+4,
                "candidate_thumb_payload_entry":hex(layout["display_data_pointer"]|1),
            },
            "remaining_offline_question":"PRE_MAIN_HEAP_STATE_AFTER_FWL_MALLOCINIT_UNPROVEN",
            "live_manifest_candidate":None,
        },
        "next_bounded_work":[
            "Do not promote the pristine cold-start addresses unless new exact framework/bootstrap evidence proves Fwl_MallocInit -> no intervening app-heap users -> 0x8dea.",
            "Prefer a placement proof independent of hidden pre-main chronology: audit stock teardown/recreate of the persistent display object and adjacent callback-bearing allocations for a uniquely constrained hole.",
            "If static placement remains non-deterministic, keep live promotion closed rather than using crash behavior as a placement oracle.",
        ],
        "method_limits":[
            "The in-image startup allocation sequence is real and branch-pinned, but the preserved application blobs do not expose a direct call/pointer edge ordering framework-owned Fwl_MallocInit and 0x8dea.",
            "The conditional pristine-heap simulation is not a runtime observation and is not sufficient to prove victim placement.",
            "No live heap address, packet, crash probe or device observation was used.",
        ],
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
        print('PLACEMENT_CONDITIONAL_PRISTINE_RUNTIME50=0x804b80')
        print('PLACEMENT_DETERMINISTIC_VICTIM=false')
        print('PLACEMENT_CONTROLLED_INDIRECT_BRANCH=false')
        print('PLACEMENT_BLOCKER=PRE_MAIN_HEAP_STATE_AFTER_FWL_MALLOCINIT_UNPROVEN')
        print('PLACEMENT_LIVE_MANIFEST_CANDIDATE=NONE')
    if not (a.write or a.json or a.selfcheck): print('DITOO_TIER2_PLACEMENT=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
