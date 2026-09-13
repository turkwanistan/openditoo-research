#!/usr/bin/env python3
"""Offline selfcheck for VRAM-8B successor 003.

003 preserves all eight transmit frames from 002. Live 002 evidence changes only
one receive expectation: the exact stock 0x6e prime send completes but does not
produce a wrapped response within the prior 2000 ms budget, so 003 does not wait
for one. No Bluetooth/device I/O and no live authority creation.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXP='OPENDITOO-VRAM8B-CANARY-003'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_fixture_003.json'
PREV=ROOT/'captures/OPENDITOO-VRAM8B-CANARY-002-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='adcf33e0883bbb2885715f8a4a86a23c0fc101ca4b6304c0e5f20e2366ef03a0'
EXPECTED_F='ebdb4be66725c15435d7ed0d24466ba06fb53b2225005d6e2cd13d25cf82161a'

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); prev=json.loads(PREV.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-CANARY-003 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    assert prev['classification']=='CONSUMED_TRANSPORT_HARNESS_INCONCLUSIVE_NOT_VRAM8_NEGATIVE'
    assert prev['execution']['application_sends_completed']==3 and prev['execution']['custom_0x6c_sends']==0
    assert prev['interpretation']['baseline_response_synchronization_proven_live'] is True
    assert prev['interpretation']['prime_0x6e_send_completed'] is True
    assert prev['interpretation']['stage0_reached'] is False and prev['interpretation']['overwrite_sent'] is False
    for row in m['sequence']:
        p3=ROOT/row['path']; p2=ROOT/row['path'].replace('CANARY-003','CANARY-002')
        assert p3.read_bytes()==p2.read_bytes(); assert sha(p3)==row['sha256']
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
    assert rp['baseline_get_b3']['mode']=='REQUIRED_EXACT'
    assert rp['prime_6e']['mode']=='NO_RESPONSE_REQUIRED_LIVE_EVIDENCE'
    assert rp['voicetip_a5']['mode']=='OPTIONAL_MATCHING_DRAIN'
    assert rp['overwrite_6c']['mode']=='OPTIONAL_MATCHING_DRAIN'
    assert rp['post_get_b3']['mode']=='REQUIRED_EXACT'
    assert rp['restore_set_b2']['mode']=='REQUIRED_EXACT'
    assert rp['restore_get_b3']['mode']=='REQUIRED_EXACT'
    assert rp['unexpected_frame']=='STOP_NO_RETRY'
    local=ROOT/'.openditoo-local/vram8b-canary-003'
    grant_path=local/'grant.json'
    grant_exists=grant_path.exists()
    if grant_exists:
        grant=json.loads(grant_path.read_text())
        assert grant['experiment_id']==EXP
        assert grant['grant_text']==m['authority']['required_grant_text']
        assert grant['manifest_sha256']==EXPECTED_M
        assert grant['fixture_report_sha256']==EXPECTED_F
        assert grant['manual_stock_btplayer_selected'] is True
        assert grant['state']=='AUTHORIZED_UNCONSUMED'
        assert isinstance(grant['one_use_nonce'],str) and len(grant['one_use_nonce'])==64
    # A pre-claim coordinator stop may leave execution.json behind; the next run atomically refreshes it before Runtime 018 handover.
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    return {
      'schema_version':1,'experiment_id':EXP,'ok':True,
      'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),
      'transmit_frames':len(m['sequence']),'custom_0x6c_frames':sum(1 for x in m['sequence'] if x['command']=='0x6c'),
      'predecessor_consumed_before_overwrite':True,'baseline_sync_proven_live':True,'prime_response_wait_removed':True,
      'authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'grant_state':'AUTHORIZED_UNCONSUMED' if grant_exists else None},
      'safety':{'offline_only':True,'device_io':False,'runtime018_touched':False}
    }
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args()
    r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_003_LIVE_GATE=PASS')
        print('VRAM8B_003_BASELINE_SYNC_PROVEN_LIVE=true')
        print('VRAM8B_003_PRIME_RESPONSE_WAIT_REMOVED=true')
        print('VRAM8B_003_TRANSMIT_FRAMES=8')
        print('VRAM8B_003_CUSTOM_0X6C=1')
        print('VRAM8B_003_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
