#!/usr/bin/env python3
"""Fail-closed offline audit of Tier-2 heap-victim placement candidates.

This does not generate packets or touch a live heap. It proves the stage-1 bootstrap ordering,
proves no app-heap user intervenes between Fwl_MallocInit and the application main entry,
and reconstructs the deterministic cold-start adjacency between the vulnerable display backing
and the persistent VoiceTip/runtime50 callback-bearing object.
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
TRANSFORMED_CALLBACK_BASE = 0x00200000
TRANSFORMED_FILE_BIAS = 0x7000
STAGE1_BSS_START = 0x00802FC4
STAGE1_BSS_END_EXCLUSIVE = 0x00803F80
STAGE1_CALLBACK_TABLE = 0x00803ADC
STAGE1_RESIDENT_CALLBACK = 0x0080010D
STAGE1_BSS_ZERO_PATTERN = bytes.fromhex(
    "30009fe50010a0e3001080e528009fe50020a0e318309fe5030050e104208034fcffff3a"
)
STAGE1_ARM_VENEER = bytes.fromhex("00c09fe51cff2fe1")
STAGE1_BOOTSTRAP_CALL_PATTERN = bytes.fromhex(
    "fff73ceefff740ee0c4800ab98800c4802900c4803900c48049001a8fff73aee0a48fff73eeefff742ee"
)
POST_HEAP_HELPER_PATTERN = bytes.fromhex(
    "10b50fc80b4c0fc4fff748ff5bf7a6fcc4f724effff7e6ffc4f7d0ef011c06480122c4f7eaee0448012200212838c4f7e4ee10bddc3a8000"
)
EMPTY_CONSTRUCTOR_LOOP_PATTERN = bytes.fromhex(
    "b0b5054d2c6802e020688047043468688442f9d3b0bd0000a02c8000"
)
CALLBACK_STORE_HELPER_PATTERN = bytes.fromhex("0349086070470000")
RESIDENT_CALLBACK_INVOKE_PATTERN = bytes.fromhex("80b5034b5b68002b00d0984780bd0000")
RESIDENT_CALLBACK_TABLE_READ_PATTERN = bytes.fromhex("0148008870470000dc3a8000")
RESIDENT_CALLBACK_BODY_PATTERN = bytes.fromhex("b0b50c1c151cfff7f4ff002c02d0201c00f006f8")

def _transformed_app_pointer(file_offset:int)->int:
    return TRANSFORMED_CALLBACK_BASE + (file_offset - TRANSFORMED_FILE_BIAS) + 1

def _decode_transformed_app_pointer(value:int)->int:
    return TRANSFORMED_FILE_BIAS + ((value & ~1) - TRANSFORMED_CALLBACK_BASE)

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

def _stage1_bootstrap_proof(name:str,spec:dict[str,Any],b:bytes)->dict[str,Any]:
    import struct
    hi=spec["heap_init"]
    expected_heap=_transformed_app_pointer(hi)
    expected_main=_transformed_app_pointer(FRAMEWORK_MAIN_ENTRY)
    if b[0xA0:0xA0+len(STAGE1_BSS_ZERO_PATTERN)] != STAGE1_BSS_ZERO_PATTERN:
        raise ValueError(f"{name}: stage1 BSS zero loop drift")
    if struct.unpack_from("<I",b,0xD4)[0] != STAGE1_BSS_END_EXCLUSIVE or struct.unpack_from("<I",b,0xDC)[0] != STAGE1_BSS_START:
        raise ValueError(f"{name}: stage1 BSS bounds drift")
    if b[0x400C:0x4014] != STAGE1_ARM_VENEER or b[0x4030:0x4038] != STAGE1_ARM_VENEER:
        raise ValueError(f"{name}: stage1 heap/main ARM veneer drift")
    if struct.unpack_from("<I",b,0x4014)[0] != expected_heap:
        raise ValueError(f"{name}: transformed Fwl_MallocInit pointer drift")
    if struct.unpack_from("<I",b,0x4038)[0] != expected_main:
        raise ValueError(f"{name}: transformed framework-main pointer drift")
    if b[0x4384:0x4384+len(STAGE1_BOOTSTRAP_CALL_PATTERN)] != STAGE1_BOOTSTRAP_CALL_PATTERN:
        raise ValueError(f"{name}: stage1 bootstrap call order drift")

    post_reset=_decode_transformed_app_pointer(struct.unpack_from("<I",b,0x4020)[0])
    callback_store=_decode_transformed_app_pointer(struct.unpack_from("<I",b,0x402C)[0])
    if b[post_reset:post_reset+len(POST_HEAP_HELPER_PATTERN)] != POST_HEAP_HELPER_PATTERN:
        raise ValueError(f"{name}: post-heap framework helper drift")
    if b[callback_store:callback_store+len(CALLBACK_STORE_HELPER_PATTERN)] != CALLBACK_STORE_HELPER_PATTERN:
        raise ValueError(f"{name}: pre-main callback-store helper drift")
    constructor_loop=post_reset-0x1C
    if b[constructor_loop:constructor_loop+len(EMPTY_CONSTRUCTOR_LOOP_PATTERN)] != EMPTY_CONSTRUCTOR_LOOP_PATTERN:
        raise ValueError(f"{name}: empty constructor-loop helper drift")
    ctor_start=struct.unpack_from("<I",b,0x2CA0)[0]
    ctor_end=struct.unpack_from("<I",b,0x2CA4)[0]
    if ctor_start != 0x00802C08 or ctor_end != ctor_start:
        raise ValueError(f"{name}: pre-main constructor range is no longer empty")

    allocator_cb=hi+0x50
    free_cb=hi+0x6E
    if struct.unpack_from("<I",b,0x43C4)[0] != STAGE1_RESIDENT_CALLBACK:
        raise ValueError(f"{name}: resident callback-table +4 drift")
    if struct.unpack_from("<I",b,0x43C8)[0] != _transformed_app_pointer(allocator_cb):
        raise ValueError(f"{name}: registered app allocator callback drift")
    if struct.unpack_from("<I",b,0x43CC)[0] != _transformed_app_pointer(free_cb):
        raise ValueError(f"{name}: registered app free callback drift")

    table_needle=struct.pack("<I",STAGE1_CALLBACK_TABLE)
    resident_refs=[]; pos=0
    while True:
        i=b.find(table_needle,pos,0x5000)
        if i<0: break
        resident_refs.append(i); pos=i+1
    if resident_refs != [0x2928,0x293C]:
        raise ValueError(f"{name}: resident callback-table reference set drift {resident_refs}")
    if b[0x2918:0x2918+len(RESIDENT_CALLBACK_INVOKE_PATTERN)] != RESIDENT_CALLBACK_INVOKE_PATTERN:
        raise ValueError(f"{name}: resident table+4 invocation drift")
    if b[0x2934:0x2934+len(RESIDENT_CALLBACK_TABLE_READ_PATTERN)] != RESIDENT_CALLBACK_TABLE_READ_PATTERN:
        raise ValueError(f"{name}: resident table+0 read drift")
    if b[0x10C:0x10C+len(RESIDENT_CALLBACK_BODY_PATTERN)] != RESIDENT_CALLBACK_BODY_PATTERN:
        raise ValueError(f"{name}: resident callback body drift")

    helper_mallocs=[o for o in range(post_reset,post_reset+len(POST_HEAP_HELPER_PATTERN),2) if thumb_bl_target(b,o)==0xBFBC]
    store_mallocs=[o for o in range(callback_store,callback_store+len(CALLBACK_STORE_HELPER_PATTERN),2) if thumb_bl_target(b,o)==0xBFBC]
    if helper_mallocs or store_mallocs:
        raise ValueError(f"{name}: app heap user appeared between heap reset and main")

    return {
        "bss_zero_start":hex(STAGE1_BSS_START),
        "bss_zero_end_exclusive":hex(STAGE1_BSS_END_EXCLUSIVE),
        "dispatcher_initial_mode_address":"0x8036ec",
        "dispatcher_initial_mode_zero_proven":STAGE1_BSS_START <= 0x008036EC < STAGE1_BSS_END_EXCLUSIVE,
        "heap_init":hex(hi),
        "transformed_heap_init_pointer":hex(expected_heap),
        "heap_init_veneer_literal_offset":"0x4014",
        "heap_init_bootstrap_call_va":"0x804388",
        "framework_main_entry":hex(FRAMEWORK_MAIN_ENTRY),
        "transformed_framework_main_pointer":hex(expected_main),
        "framework_main_veneer_literal_offset":"0x4038",
        "framework_main_bootstrap_call_va":"0x8043aa",
        "post_heap_helper":hex(post_reset),
        "callback_store_helper":hex(callback_store),
        "constructor_table_start":hex(ctor_start),
        "constructor_table_end":hex(ctor_end),
        "constructor_table_empty":True,
        "registered_allocator_callback":hex(allocator_cb),
        "registered_free_callback":hex(free_cb),
        "resident_callback_table":hex(STAGE1_CALLBACK_TABLE),
        "resident_callback_table_refs":[hex(x) for x in resident_refs],
        "resident_callback_invoked_pre_main":hex(STAGE1_RESIDENT_CALLBACK),
        "app_allocator_callback_invoked_pre_main":False,
        "app_free_callback_invoked_pre_main":False,
        "intervening_app_heap_users":[],
    }

def build_report()->dict[str,Any]:
    branches={n:_branch(n,spec) for n,spec in BRANCHES.items()}
    layout=_simulate_pristine_heap_hypothesis()
    if layout["display_backing_0x708"] != 0x00804470 or layout["display_data_pointer"] != 0x00804778:
        raise ValueError("deterministic layout: display address drift")
    if layout["runtime50_0x50"] != 0x00804B80 or layout["runtime50_callback"] != 0x00804BB4 or layout["callback_source_offset"] != 0x43C:
        raise ValueError("deterministic layout: runtime50 adjacency drift")

    framework={}
    for name,spec in BRANCHES.items():
        b=_load(name,spec)
        if b[FRAMEWORK_MAIN_ENTRY:FRAMEWORK_MAIN_ENTRY+2] != bytes.fromhex("80b5"):
            raise ValueError(f"{name}: framework main entry prologue drift")
        proof=_stage1_bootstrap_proof(name,spec,b)
        proof["direct_bl_xrefs_to_main"]=_direct_bl_xrefs(b,FRAMEWORK_MAIN_ENTRY)
        proof["direct_bl_xrefs_to_heap_init"]=_direct_bl_xrefs(b,spec["heap_init"])
        proof["raw_absolute_app_pointer_xrefs_to_main"]=_absolute_app_pointer_xrefs(b,FRAMEWORK_MAIN_ENTRY)
        proof["raw_absolute_app_pointer_xrefs_to_heap_init"]=_absolute_app_pointer_xrefs(b,spec["heap_init"])
        if any(proof[k] for k in ("direct_bl_xrefs_to_main","direct_bl_xrefs_to_heap_init","raw_absolute_app_pointer_xrefs_to_main","raw_absolute_app_pointer_xrefs_to_heap_init")):
            raise ValueError(f"{name}: ordinary framework xref evidence changed")
        framework[name]=proof

    deterministic_layout={k:hex(v) for k,v in layout.items() if k!="callback_source_offset"}
    return {
        "schema_version":4,
        "kind":"ditoo_plus_tier2_victim_placement",
        "ok":True,
        "safety":{"offline_analysis_only":True,"device_io":False,"live_packet_generation":False,"firmware_mutation":False,"persistent_mutation":False,"runtime_018_touched":False},
        "branches":branches,
        "allocator_model":{
            "heap_start":hex(HEAP_START),"heap_end_exclusive":hex(HEAP_START+HEAP_SIZE),"allocation_quantum":ALLOC_QUANTUM,
            "policy":"BEST_FIT_LOW_ADDRESS_SPLIT_SEPARATE_DESCRIPTORS_WITH_ADJACENT_FREE_COALESCING",
            "reviewed_startup_allocations":"The 0x8dea startup allocation/free sequence is branch-pinned through the display backing and persistent runtime50 construction. Stage-1 now proves the application heap is reset immediately before this sequence with no intervening app-heap user.",
        },
        "framework_ordering_gate":{
            "app_link_base":hex(APP_LINK_BASE),
            "transformed_callback_base":hex(TRANSFORMED_CALLBACK_BASE),
            "branches":framework,
            "heap_reset_before_framework_main_proven":True,
            "no_intervening_app_heap_users_proven":True,
            "reason":"Stage-1 ARM veneers and the common Thumb bootstrap explicitly order Fwl_MallocInit before 0x8dea. The only two post-reset/pre-main helpers are byte-pinned; their constructor range is empty, and resident callback-table use invokes +4 (0x0080010D), not the app malloc/free callbacks registered at +8/+0c.",
            "status":"PROVEN_STAGE1_BOOTSTRAP_ORDER_AND_EMPTY_APP_HEAP",
        },
        "deterministic_startup_layout":{
            "proven":True,
            "layout":deterministic_layout,
            "runtime50_callback_source_offset":layout["callback_source_offset"],
            "minimum_source_length_to_fully_control_callback":layout["callback_source_offset"]+4,
            "display_to_runtime50_base_offset":layout["runtime50_0x50"]-layout["display_data_pointer"],
            "runtime50_callback_fully_controlled":True,
            "cross_branch":"4_OF_4_PRESERVED_PLUS_BRANCHES",
            "meaning":"The vulnerable display data pointer is 0x00804778 and the persistent 0x50-byte VoiceTip/runtime50 object starts at 0x00804b80. The runtime50 base is exactly 0x408 bytes after the display pointer, i.e. immediately after the display backing allocation's physical capacity. Callback +0x34 is source offset 0x43c.",
        },
        "placement_strategy_closures":{
            "display_teardown_recreate":{
                "status":"CLOSED_WITHIN_AUDITED_APP_GRAPH",
                "root_constructor_has_one_direct_caller_4_of_4":True,
                "app_heap_free_in_display_service_window":False,
                "app_heap_free_in_backing_service_window":False,
                "meaning":"No stock app-heap teardown/recreate path for the persistent display root/backing was found in the audited service families."
            },
            "plugin_0x80_spray":{
                "status":"CLOSED_AS_UNBOUNDED_DIRECT_SPRAY",
                "direct_constructor_sites_per_branch":2,
                "reviewed_as_singleton_subsystem_lifecycles":True,
                "unbounded_stock_spray_found":False,
                "meaning":"The 0x80 callback-bearing plugin object is free/recreate capable, but its two direct construction sites are singleton subsystem lifecycles, not an unbounded spray."
            }
        },
        "stock_grooming_surface":{
            "exists":True,
            "plugin_object":{"request_bytes":0x80,"zeroed_on_create":True,"descriptor_copied_to_offset":hex(0x0C),"known_indirect_fields":[hex(0x0C),hex(0x20),hex(0x2C)],"whole_object_free_recreate":True},
            "runtime50_object":{"request_bytes":0x50,"callback_offset":hex(0x34),"deterministic_base":hex(layout["runtime50_0x50"]),"deterministic_callback":hex(layout["runtime50_callback"]),"callback_source_offset":layout["callback_source_offset"],"persistent_startup_allocation":True,"stock_free_recreate_proven":False},
            "meaning":"Stock grooming remains available for the separate plugin object. VoiceTip/runtime50 is a persistent startup allocation; its value here is deterministic adjacency, not preview-time free/recreate grooming.",
        },
        "placement_gate":{
            "deterministic_adjacent_victim_proven":True,
            "controlled_callback_field_proven":True,
            "controlled_indirect_branch_proven":False,
            "runtime50_candidate":{
                "base":hex(layout["runtime50_0x50"]),
                "callback":hex(layout["runtime50_callback"]),
                "callback_source_offset":layout["callback_source_offset"],
                "minimum_source_length_to_fully_control_callback":layout["callback_source_offset"]+4,
                "candidate_thumb_payload_entry":hex(layout["display_data_pointer"]|1),
            },
            "remaining_offline_question":"RUNTIME50_POST_OVERWRITE_STATE_AND_TRIGGER",
            "live_manifest_candidate":None,
        },
        "next_bounded_work":[
            "Audit the exact 1088-byte source prefix needed to reach runtime50+0x34 while preserving or deliberately setting the VoiceTip fields consumed before the callback BLX.",
            "Close a deterministic stock VoiceTip setup/completion route in a known dispatcher mode; 0xA5 SPP_SET_ALARM_LISTEN -> event 0x34c is already a strong candidate.",
            "Keep live promotion closed until controlled callback invocation is proven without using crash behavior as an oracle.",
        ],
        "method_limits":[
            "The promoted addresses are a static cold-start proof for the pinned firmware corpus; they are not a live heap observation.",
            "Placement alone does not prove that overwriting runtime50+0x34 yields a safe/deterministic indirect call: the preceding runtime50 bytes and the VoiceTip trigger path still require proof.",
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
        print('PLACEMENT_DETERMINISTIC_RUNTIME50=0x804b80')
        print('PLACEMENT_DETERMINISTIC_VICTIM=true')
        print('PLACEMENT_CONTROLLED_INDIRECT_BRANCH=false')
        print('PLACEMENT_BLOCKER=RUNTIME50_POST_OVERWRITE_STATE_AND_TRIGGER')
        print('PLACEMENT_LIVE_MANIFEST_CANDIDATE=NONE')
    if not (a.write or a.json or a.selfcheck): print('DITOO_TIER2_PLACEMENT=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
