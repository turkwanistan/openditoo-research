#!/usr/bin/env python3
"""Offline/pre-claim gate for VRAM8B MODEL-SENTINEL-009 one-byte differential."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from ditoo_candidate_codec import decode_candidate_normal
EXP='OPENDITOO-VRAM8B-MODEL-SENTINEL-009'
M=ROOT/'experiments'/f'{EXP}.json'
F=ROOT/'artifacts/analysis/volatile_ram_api_vram8b_model_sentinel_009.json'
PREV=ROOT/'captures/OPENDITOO-VRAM8B-PREMODEL-008-LIVE-RESULT-2026-09-13.json'
EXPECTED_M='c0687e106867da409de0747be7900e4df3d863cfc7daa2324f0f2579d645bb01'
EXPECTED_F='7292b0bdef25c9b5468dae905d13eb9b2fbc4e9b175a9220e7b9c35796f6c097'
EXPECTED_PREV='1f41c44ef20a7cdceca2e89166cc29cb6b8bf79c642752fc7be319900e57ad7f'
SOURCE_LEN=0x411
RUNTIME50_OFF=0x408
MODEL_OFF=0x08
CALLBACK_OFF=0x34
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def build_report():
    m=json.loads(M.read_text()); f=json.loads(F.read_text()); p=json.loads(PREV.read_text())
    assert sha(M)==EXPECTED_M and sha(F)==EXPECTED_F and sha(PREV)==EXPECTED_PREV
    assert p['classification']=='PASS_PREMODEL_CONTROL_MATCHES_CONTROL_007'
    assert m['experiment_id']==EXP and m['status']=='prepared_unauthorized'
    assert m['authority']['required_grant_text']=='Grant OPENDITOO-VRAM8B-MODEL-SENTINEL-009 -- stock btplayer selected'
    assert m['authority']['transmission_authorized'] is False and m['authority']['authorization_consumed'] is False
    b=m['transport_budget']; assert b['max_connections']==1 and b['exact_application_sends']==3 and b['max_custom_0x6c_sends']==1
    assert b['custom_0x6c_declared_source_length']==SOURCE_LEN and b['retry'] is False and b['reconnect'] is False
    g=f['geometry_hypothesis']; assert g['predicted_runtime50_source_offset']=='0x408' and g['source_length']==SOURCE_LEN
    assert g['predicted_last_victim_offset']=='runtime50+0x08' and g['predicted_model_reached'] is True and g['predicted_model_value']=='0xff' and g['callback_reached'] is False
    d=f['device_side_delta_from_008']; assert d['exactly_one_additional_source_byte'] is True and d['old_source_length']==0x410 and d['new_source_length']==0x411
    src=ROOT/f['source']['path']; raw=src.read_bytes(); assert len(raw)==SOURCE_LEN and raw==bytes([0xff])*SOURCE_LEN and sha(src)==f['source']['sha256']
    old=(ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-PREMODEL-008-source.bin').read_bytes(); assert raw[:-1]==old and raw[-1]==0xff
    seq=m['sequence']; assert [x['command'] for x in seq]==['0x6e','0xa5','0x6c']
    assert (ROOT/seq[0]['path']).read_bytes()==(ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-PREMODEL-008-01-prime.bin').read_bytes()
    assert (ROOT/seq[1]['path']).read_bytes()==(ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-PREMODEL-008-02-voicetip.bin').read_bytes()
    for row in seq:
        q=ROOT/row['path']; assert sha(q)==row['sha256']
    ov=decode_candidate_normal((ROOT/seq[2]['path']).read_bytes())
    assert ov.command==0x6c and int.from_bytes(ov.payload[:2],'little')==0 and int.from_bytes(ov.payload[2:4],'little')==SOURCE_LEN and ov.payload[4:]==raw
    assert SOURCE_LEN==RUNTIME50_OFF+MODEL_OFF+1 and SOURCE_LEN < RUNTIME50_OFF+CALLBACK_OFF+4
    transport=(ROOT/'runtime/windows/OpenDitoo.Vram8B.ModelSentinel009/WindowsRfcommModelSentinel009Transport.cs').read_text()
    assert transport.count('connect(socketHandle, ref remote, layoutSize)')==1
    assert transport.count('send(socketHandle, bytes, bytes.Length, 0)')==1
    assert 'CaptureWithScheduledOverwrite' in transport and 'fixtures[2]' in transport and 'CustomSourceLength' in transport
    assert 'pending.RemoveRange(0, expectedTotal)' in transport and 'pre_overwrite' in transport and 'post_overwrite' in transport
    local=ROOT/'.openditoo-local/vram8b-model-sentinel-009'; grant=local/'grant.json'; grant_exists=grant.exists(); execution_exists=(local/'execution.json').exists()
    assert not (local/'claim.json').exists() and not (local/'handover.json').exists() and not (local/'result.json').exists()
    if grant_exists:
        x=json.loads(grant.read_text()); assert x['experiment_id']==EXP and x['grant_text']==m['authority']['required_grant_text']
        assert x['manifest_sha256']==EXPECTED_M and x['fixture_report_sha256']==EXPECTED_F and x['manual_stock_btplayer_selected'] is True
        assert x['granted_by']=='owner' and x['state']=='AUTHORIZED_UNCONSUMED' and isinstance(x['one_use_nonce'],str) and len(x['one_use_nonce'])==64
    else: assert not execution_exists
    return {'schema_version':1,'experiment_id':EXP,'ok':True,'manifest_sha256':sha(M),'fixture_report_sha256':sha(F),'source_length':SOURCE_LEN,'predicted_last_victim_offset':'runtime50+0x08','predicted_model_reached':True,'predicted_model_value':'0xff','predicted_callback_reached':False,'application_sends':3,'custom_0x6c_sends':1,'capture_ms':75000,'authority':{'grant_exists':grant_exists,'claim_exists':False,'result_exists':False,'execution_exists':execution_exists}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args(); r=build_report()
    if a.json: print(json.dumps(r,indent=2,sort_keys=True))
    if a.selfcheck or not a.json:
        print('DITOO_VRAM8B_MODEL_SENTINEL_009_GATE=PASS')
        print('MODEL009_APPLICATION_SENDS=3')
        print('MODEL009_CUSTOM_0X6C=1')
        print('MODEL009_SOURCE_LENGTH=0x411')
        print('MODEL009_PREDICTED_LAST_VICTIM=runtime50+0x08')
        print('MODEL009_MODEL_REACHED=true')
        print('MODEL009_MODEL_VALUE=0xff')
        print('MODEL009_CALLBACK_REACHED=false')
        print('MODEL009_GRANT_MATERIALIZED='+('true' if r['authority']['grant_exists'] else 'false'))
    return 0
if __name__=='__main__': raise SystemExit(main())
