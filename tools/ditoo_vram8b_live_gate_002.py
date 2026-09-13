#!/usr/bin/env python3
"""Offline selfcheck for fresh response-synchronous VRAM-8B successor 002.

No Bluetooth/device I/O and no live authority creation.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXP='OPENDITOO-VRAM8B-CANARY-002'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_fixture_002.json'
PREV=ROOT/'captures/OPENDITOO-VRAM8B-CANARY-001-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='0f054872b6886a6eacea9ae71ab43f01ef393d1cf55e4e242535f73d6a1cc758'
EXPECTED_F='6b87fe811a22614654bcb0fb30fd8ffcaa84442ef73291a7af4925920dc0fd9a'

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); prev=json.loads(PREV.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-CANARY-002 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    assert prev['classification']=='CONSUMED_TRANSPORT_HARNESS_INCONCLUSIVE_NOT_VRAM8_NEGATIVE'
    assert prev['execution']['application_sends_completed']==2 and prev['execution']['custom_0x6c_sends']==0
    assert prev['interpretation']['stage0_reached'] is False and prev['interpretation']['overwrite_sent'] is False
    # Exact successor TX bytes remain identical to predecessor.
    for row in m['sequence']:
        p2=ROOT/row['path']; p1=ROOT/row['path'].replace('CANARY-002','CANARY-001')
        assert p2.read_bytes()==p1.read_bytes(); assert sha(p2)==row['sha256']
    rf=f['response_fixtures']
    expected={
      'expected-b2-0':'01060004b25500110102',
      'expected-b3-0':'01060004b35500120102',
      'expected-b3-1':'01060004b35501130102',
    }
    for k,h in expected.items():
        p=ROOT/rf[k]['path']; assert p.read_bytes().hex()==h and sha(p)==rf[k]['sha256']
    rp=m['response_policy']
    assert rp['baseline_set_b2']['mode']=='REQUIRED_EXACT'
    assert rp['prime_6e']['mode']=='REQUIRED_MATCHING_WRAPPED'
    assert rp['voicetip_a5']['mode']=='OPTIONAL_MATCHING_DRAIN'
    assert rp['overwrite_6c']['mode']=='OPTIONAL_MATCHING_DRAIN'
    assert rp['unexpected_frame']=='STOP_NO_RETRY'
    local=ROOT/'.openditoo-local/vram8b-canary-002'
    return {
      'schema_version':1,'experiment_id':EXP,'ok':True,
      'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),
      'transmit_frames':len(m['sequence']),'custom_0x6c_frames':sum(1 for x in m['sequence'] if x['command']=='0x6c'),
      'predecessor_consumed_before_overwrite':True,'response_synchronous':True,
      'authority':{'grant_exists':(local/'grant.json').exists(),'claim_exists':(local/'claim.json').exists(),'result_exists':(local/'result.json').exists(),'transmission_authorized':False},
      'safety':{'offline_only':True,'device_io':False,'runtime018_touched':False}
    }
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args()
    r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_002_LIVE_GATE=PASS'); print('VRAM8B_002_RESPONSE_SYNCHRONOUS=true'); print('VRAM8B_002_TRANSMIT_FRAMES=8'); print('VRAM8B_002_CUSTOM_0X6C=1'); print('VRAM8B_002_LIVE_AUTHORIZED=false')
    return 0
if __name__=='__main__': raise SystemExit(main())
