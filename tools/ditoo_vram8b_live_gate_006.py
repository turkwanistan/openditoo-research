#!/usr/bin/env python3
"""Offline/pre-claim selfcheck for VRAM-8B diagnostic successor 006.

006 changes only the stage-0 execution site inside the already-bounded 1088-byte
overwrite. It keeps the 005 transport/response policy and typed B3 oracle.
No device I/O or authority creation occurs here.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP='OPENDITOO-VRAM8B-CANARY-006'
PREV='OPENDITOO-VRAM8B-CANARY-005'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_fixture_006.json'
PREV_CAPTURE=ROOT/'captures/OPENDITOO-VRAM8B-CANARY-005-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='0cc58e980c0d73c61113adb6a3068bc706fa07bf9cc420259a7d348f554b5540'
EXPECTED_F='886f99add1c3e4128c2923509ff58e3d451e5a89cf4877ee690cc03b438bb9f6'
STAGE0=bytes.fromhex('10b5034c6468e27b01235a40e27310bdf0308000')

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); prev=json.loads(PREV_CAPTURE.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['fixture_report']=={'path':'artifacts/analysis/volatile_ram_api_vram8b_fixture_006.json','sha256':EXPECTED_F}
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-CANARY-006 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    assert prev['classification']=='CONSUMED_TYPED_CANARY_NEGATIVE_STAGE0_EFFECT_NOT_OBSERVED'
    assert prev['execution']['application_sends_completed']==6 and prev['execution']['custom_0x6c_sends']==1
    assert prev['live_observation']['connection_survived_hold'] is True
    assert prev['live_observation']['post_hold_b3_value']==0 and prev['live_observation']['expected_stage0_value']==1
    assert prev['interpretation']['stage0_effect_observed'] is False

    # Seven non-overwrite frames are byte-identical to 005.
    for row in m['sequence']:
        p6=ROOT/row['path']; assert sha(p6)==row['sha256']
        p5=ROOT/row['path'].replace(EXP,PREV)
        if row['key']!='overwrite': assert p6.read_bytes()==p5.read_bytes()

    p6=ROOT/'experiments/fixtures'/f'{EXP}-05-overwrite.bin'
    p5=ROOT/'experiments/fixtures'/f'{PREV}-05-overwrite.bin'
    b6=p6.read_bytes(); b5=p5.read_bytes()
    assert len(b6)==len(b5)==1099 and b6[0]==0x01 and b6[-1]==0x02
    src=8; ckidx=len(b6)-3
    assert (sum(b6[1:ckidx]) & 0xffff)==struct.unpack('<H',b6[ckidx:ckidx+2])[0]
    assert b6[src+0x308:src+0x308+len(STAGE0)]==STAGE0
    assert struct.unpack('<I',b6[src+0x43c:src+0x440])[0]==0x00804A81
    changes=[i for i,(a,b) in enumerate(zip(b5,b6)) if a!=b]
    allowed=set(range(src+0x308,src+0x308+len(STAGE0))) | set(range(src+0x43c,src+0x440)) | {ckidx,ckidx+1}
    assert set(changes) <= allowed and len(changes)==24
    assert m['stage0']['source_address']=='0x804a80' and m['stage0']['entry']=='0x804a81'
    assert m['stage0']['source_offset']=='0x308' and m['stage0']['callback_value']=='0x804a81'
    assert hashlib.sha256(b6[src:src+1088]).hexdigest()==m['stage0']['source_sha256']
    d=m['diagnostic_delta']
    assert d['old_stage0_bytes_left_in_source_as_in_005'] is True
    assert d['new_execution_span']=='0x00804A80..0x00804A93'

    rp=m['response_policy']
    for k in ('baseline_set_b2','restore_set_b2'):
        assert rp[k]['expected_inner_command']=='0xb2' and rp[k]['expected_payload_length']==1
    for k,v in (('baseline_get_b3','00'),('post_get_b3','01'),('restore_get_b3','00')):
        assert rp[k]['expected_inner_command']=='0xb3' and rp[k]['expected_payload_hex']==v
        assert rp[k]['max_unrelated_valid_frames']==8
    assert rp['prime_6e']['mode']=='NO_RESPONSE_REQUIRED_LIVE_EVIDENCE'
    assert rp['voicetip_a5']['mode']=='BOUNDED_VALID_REPORT_DRAIN'
    assert rp['overwrite_6c']['mode']=='BOUNDED_VALID_REPORT_DRAIN'

    local=ROOT/'.openditoo-local/vram8b-canary-006'
    grant=local/'grant.json'; grant_exists=grant.exists(); execution_exists=(local/'execution.json').exists()
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    if grant_exists:
        g=json.loads(grant.read_text())
        assert g['experiment_id']==EXP and g['grant_text']==m['authority']['required_grant_text']
        assert g['manifest_sha256']==EXPECTED_M and g['fixture_report_sha256']==EXPECTED_F
        assert g['manual_stock_btplayer_selected'] is True and g['granted_by']=='owner' and g['state']=='AUTHORIZED_UNCONSUMED'
        assert isinstance(g['one_use_nonce'],str) and len(g['one_use_nonce'])==64
    else:
        assert not execution_exists

    return {
      'schema_version':1,'experiment_id':EXP,'ok':True,
      'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),
      'diagnostic':'relocated_exact_stage0_execution_site','old_entry':'0x00804901','new_entry':'0x00804A81',
      'transmit_frames':len(m['sequence']),'custom_0x6c_frames':sum(1 for x in m['sequence'] if x['command']=='0x6c'),
      'authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'execution_exists':execution_exists},
      'safety':{'offline_only':True,'device_io':False,'runtime018_touched':False}
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args(); r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_006_LIVE_GATE=PASS')
        print('VRAM8B_006_DIAGNOSTIC=RELOCATED_EXACT_STAGE0')
        print('VRAM8B_006_ENTRY=0x00804A81')
        print('VRAM8B_006_TYPED_ORACLE=0->1->0')
        print('VRAM8B_006_TRANSMIT_FRAMES=8')
        print('VRAM8B_006_CUSTOM_0X6C=1')
        print('VRAM8B_006_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
