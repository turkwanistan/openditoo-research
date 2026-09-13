#!/usr/bin/env python3
"""Offline/pre-claim selfcheck for VRAM-8B successor 005."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXP='OPENDITOO-VRAM8B-CANARY-005'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_fixture_005.json'
PREV=ROOT/'captures/OPENDITOO-VRAM8B-CANARY-004-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='0248438e5b448858a31ed64d266a84314291332022f149e9bd25a4c99e37cc57'
EXPECTED_F='43b55d41162dc12c4f98f8923fa5269affca28d3cdb1e3d96d0015630159e395'
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); prev=json.loads(PREV.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['fixture_report']['path']=='artifacts/analysis/volatile_ram_api_vram8b_fixture_005.json'
    assert m['fixture_report']['sha256']==EXPECTED_F
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-CANARY-005 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    assert prev['classification']=='CONSUMED_MULTIPLEXED_VALID_REPORT_HARNESS_INCONCLUSIVE_NOT_VRAM8_NEGATIVE'
    assert prev['execution']['application_sends_completed']==4 and prev['execution']['custom_0x6c_sends']==0
    assert prev['interpretation']['observed_valid_unrelated_inner_command']=='0xBD'
    assert prev['interpretation']['stage0_reached'] is False and prev['interpretation']['overwrite_sent'] is False
    for row in m['sequence']:
        p5=ROOT/row['path']; p4=ROOT/row['path'].replace('CANARY-005','CANARY-004')
        assert p5.read_bytes()==p4.read_bytes(); assert sha(p5)==row['sha256']
    rp=m['response_policy']
    for k in ('baseline_set_b2','restore_set_b2'):
        assert rp[k]['mode']=='REQUIRED_MATCHING_WRAPPED_ONE_BYTE_ANY_VALUE'
        assert rp[k]['expected_inner_command']=='0xb2' and rp[k]['expected_payload_length']==1
        assert rp[k]['correlation']=='REQUIRED_MATCH_WITH_BOUNDED_VALID_UNRELATED_SKIP'
        assert rp[k]['max_unrelated_valid_frames']==8
    for k,v in (('baseline_get_b3','00'),('post_get_b3','01'),('restore_get_b3','00')):
        assert rp[k]['mode']=='REQUIRED_EXACT' and rp[k]['expected_payload_hex']==v
        assert rp[k]['correlation']=='REQUIRED_MATCH_WITH_BOUNDED_VALID_UNRELATED_SKIP'
        assert rp[k]['max_unrelated_valid_frames']==8
    assert rp['prime_6e']['mode']=='NO_RESPONSE_REQUIRED_LIVE_EVIDENCE'
    for k in ('voicetip_a5','overwrite_6c'):
        assert rp[k]['mode']=='BOUNDED_VALID_REPORT_DRAIN'
        assert rp[k]['max_frames']==4 and rp[k]['quiet_window_ms']==150
    local=ROOT/'.openditoo-local/vram8b-canary-005'
    grant_path=local/'grant.json'; grant_exists=grant_path.exists(); execution_exists=(local/'execution.json').exists()
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    if grant_exists:
        g=json.loads(grant_path.read_text())
        assert g['experiment_id']==EXP and g['grant_text']==m['authority']['required_grant_text']
        assert g['manifest_sha256']==EXPECTED_M and g['fixture_report_sha256']==EXPECTED_F
        assert g['manual_stock_btplayer_selected'] is True and g['state']=='AUTHORIZED_UNCONSUMED'
        assert isinstance(g['one_use_nonce'],str) and len(g['one_use_nonce'])==64
    else:
        assert not execution_exists
    return {'schema_version':1,'experiment_id':EXP,'ok':True,'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),
      'transmit_frames':len(m['sequence']),'custom_0x6c_frames':sum(1 for x in m['sequence'] if x['command']=='0x6c'),
      'valid_unrelated_skip_budget':8,'optional_valid_drain_max_frames':4,'b3_typed_oracle':'0->1->0',
      'authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'execution_exists':execution_exists},
      'safety':{'offline_only':True,'device_io':False,'runtime018_touched':False}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args(); r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_005_LIVE_GATE=PASS')
        print('VRAM8B_005_MULTIPLEXED_VALID_REPORTS=BOUNDED_SKIP')
        print('VRAM8B_005_B3_TYPED_ORACLE=0->1->0')
        print('VRAM8B_005_TRANSMIT_FRAMES=8')
        print('VRAM8B_005_CUSTOM_0X6C=1')
        print('VRAM8B_005_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
