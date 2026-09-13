#!/usr/bin/env python3
"""Offline/pre-claim gate for VRAM8B PREMODEL-008 differential control."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from ditoo_candidate_codec import decode_candidate_normal
EXP='OPENDITOO-VRAM8B-PREMODEL-008'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_premodel_008.json'
CONTROL=ROOT/'captures/OPENDITOO-VRAM8B-CONTROL-007-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='201b55743131fa143abcbc360a76d9c22a85f5177217d897b3726802e6b5bbf8'
EXPECTED_F='84edcd2ae29b90a7c9ccb7359a9aba4b8ba28cf23841360f9cfc3e5a90c963c3'
EXPECTED_CONTROL='42f53970da762c86c585cd50013beea9620bd6c94ac6b7e7737beb184aa449a0'
SOURCE_LEN=0x410
RUNTIME50_OFF=0x408
MODEL_OFF=0x08
CALLBACK_OFF=0x34
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); c=json.loads(CONTROL.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F and sha(CONTROL)==EXPECTED_CONTROL
    assert c['classification']=='PASS_EXACT_UNIT_STOCK_VOICETIP_TRANSCRIPT'
    reps=c['exact_unit_transcript']; assert len(reps)==2
    assert reps[0]['PayloadHex']=='13014b00' and reps[1]['PayloadHex']=='13011e00'
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-PREMODEL-008 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    b=m['transport_budget']; assert b['max_connections']==1 and b['exact_application_sends']==3 and b['max_custom_0x6c_sends']==1
    assert b['custom_0x6c_declared_source_length']==SOURCE_LEN and b['retry'] is False and b['reconnect'] is False
    g=f['geometry_hypothesis']; assert g['predicted_runtime50_source_offset']=='0x408' and g['source_length']==SOURCE_LEN
    assert g['predicted_last_victim_offset']=='runtime50+0x07' and g['model_reached'] is False and g['callback_reached'] is False
    src=ROOT/f['source']['path']; raw=src.read_bytes(); assert len(raw)==SOURCE_LEN and raw==bytes([0xff])*SOURCE_LEN and sha(src)==f['source']['sha256']
    seq=m['sequence']; assert [x['command'] for x in seq]==['0x6e','0xa5','0x6c']
    for row in seq:
        p=ROOT/row['path']; assert sha(p)==row['sha256']
    ov=decode_candidate_normal((ROOT/seq[2]['path']).read_bytes())
    assert ov.command==0x6c and int.from_bytes(ov.payload[:2],'little')==0 and int.from_bytes(ov.payload[2:4],'little')==SOURCE_LEN and ov.payload[4:]==raw
    assert SOURCE_LEN==RUNTIME50_OFF+MODEL_OFF and SOURCE_LEN < RUNTIME50_OFF+CALLBACK_OFF+4
    transport=(ROOT/'runtime/windows/OpenDitoo.Vram8B.Premodel008/WindowsRfcommPremodel008Transport.cs').read_text()
    assert transport.count('connect(socketHandle, ref remote, layoutSize)')==1
    assert transport.count('send(socketHandle, bytes, bytes.Length, 0)')==1
    assert 'CaptureWithScheduledOverwrite' in transport and 'fixtures[2]' in transport and 'CustomSourceLength' in transport
    assert 'pending.RemoveRange(0, expectedTotal)' in transport and 'pre_overwrite' in transport and 'post_overwrite' in transport
    local=ROOT/'.openditoo-local/vram8b-premodel-008'; grant=local/'grant.json'; grant_exists=grant.exists(); execution_exists=(local/'execution.json').exists()
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    if grant_exists:
        x=json.loads(grant.read_text()); assert x['experiment_id']==EXP and x['grant_text']==m['authority']['required_grant_text']
        assert x['manifest_sha256']==EXPECTED_M and x['fixture_report_sha256']==EXPECTED_F and x['manual_stock_btplayer_selected'] is True
        assert x['granted_by']=='owner' and x['state']=='AUTHORIZED_UNCONSUMED' and isinstance(x['one_use_nonce'],str) and len(x['one_use_nonce'])==64
    else: assert not execution_exists
    return {'schema_version':1,'experiment_id':EXP,'ok':True,'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),'source_length':SOURCE_LEN,'predicted_last_victim_offset':'runtime50+0x07','predicted_model_reached':False,'predicted_callback_reached':False,'application_sends':3,'custom_0x6c_sends':1,'capture_ms':75000,'authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'execution_exists':execution_exists}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args(); r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_PREMODEL_008_GATE=PASS')
        print('PREMODEL008_APPLICATION_SENDS=3')
        print('PREMODEL008_CUSTOM_0X6C=1')
        print('PREMODEL008_SOURCE_LENGTH=0x410')
        print('PREMODEL008_PREDICTED_LAST_VICTIM=runtime50+0x07')
        print('PREMODEL008_MODEL_REACHED=false')
        print('PREMODEL008_CALLBACK_REACHED=false')
        print('PREMODEL008_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
