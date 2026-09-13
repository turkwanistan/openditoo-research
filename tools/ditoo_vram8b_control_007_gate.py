#!/usr/bin/env python3
"""Offline/pre-claim gate for exact-unit stock-only VRAM8B CONTROL-007."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXP='OPENDITOO-VRAM8B-CONTROL-007'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_control_007.json'
PREV=ROOT/'captures/OPENDITOO-VRAM8B-CANARY-006-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='7660aee525515499c094c2bf5d124349efb9fdf36d46559ba8c88895b7366bae'
EXPECTED_F='95ad61a7de060ed6b53a31e74180cca803e48f98b1385f646c2dabbd8805cb34'
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); prev=json.loads(PREV.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F
    assert sha(PREV)=='e234abc26db2b1c122585c19593bb5cc38316690c4ea53e5fb01b183ef961de5'
    assert prev['classification']=='CONSUMED_TYPED_CANARY_NEGATIVE_RELOCATED_STAGE0_EFFECT_NOT_OBSERVED'
    assert prev['execution']['application_sends_completed']==6 and prev['execution']['custom_0x6c_sends']==1
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-CONTROL-007 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    assert m['transport_budget']['exact_application_sends']==2 and m['transport_budget']['max_custom_0x6c_sends']==0
    assert m['transport_budget']['receive_only_ms_after_a5']==75000 and m['transport_budget']['max_connections']==1
    assert m['transport_budget']['retry'] is False and m['transport_budget']['reconnect'] is False
    seq=m['sequence']; assert [x['command'] for x in seq]==['0x6e','0xa5']
    expected=[ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-CANARY-006-03-prime.bin',ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-CANARY-006-04-voicetip.bin']
    for row,old in zip(seq,expected):
        p=ROOT/row['path']; assert p.read_bytes()==old.read_bytes(); assert sha(p)==row['sha256']
    assert f['safety']['custom_0x6c_sends']==0 and f['safety']['ram_overflow'] is False and f['safety']['custom_code'] is False
    assert f['receive_capture']['fragmentation_supported'] is True and f['receive_capture']['concatenated_frames_supported'] is True
    src=(ROOT/'runtime/windows/OpenDitoo.Vram8B.Control007/WindowsRfcommControl007Transport.cs').read_text()
    assert src.count('connect(socketHandle, ref remote, layoutSize)')==1
    assert src.count('send(socketHandle, bytes, bytes.Length, 0)')==1
    assert '0x6C' not in src and '0x6c' not in src
    assert 'ParseAvailableFrames' in src and 'pending.RemoveRange(0, expectedTotal)' in src
    local=ROOT/'.openditoo-local/vram8b-control-007'
    grant=local/'grant.json'; grant_exists=grant.exists(); execution_exists=(local/'execution.json').exists()
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    if grant_exists:
        g=json.loads(grant.read_text()); assert g['experiment_id']==EXP and g['grant_text']==m['authority']['required_grant_text']
        assert g['manifest_sha256']==EXPECTED_M and g['fixture_report_sha256']==EXPECTED_F
        assert g['manual_stock_btplayer_selected'] is True and g['granted_by']=='owner' and g['state']=='AUTHORIZED_UNCONSUMED'
        assert isinstance(g['one_use_nonce'],str) and len(g['one_use_nonce'])==64
    else:
        assert not execution_exists
    return {'schema_version':1,'experiment_id':EXP,'ok':True,'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),
      'stock_transmit_frames':2,'custom_0x6c_frames':0,'receive_only_ms':75000,'max_reports':64,
      'parser':'FRAGMENTATION_AND_CONCATENATION_SAFE','authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'execution_exists':execution_exists}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args(); r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_CONTROL_007_GATE=PASS')
        print('CONTROL007_STOCK_SENDS=2')
        print('CONTROL007_CUSTOM_0X6C=0')
        print('CONTROL007_CAPTURE_MS=75000')
        print('CONTROL007_STREAM_PARSER=FRAGMENTATION_AND_CONCATENATION_SAFE')
        print('CONTROL007_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
