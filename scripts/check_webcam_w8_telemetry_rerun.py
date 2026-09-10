#!/usr/bin/env python3
"""Read-only strict review of active W8 telemetry-corrected candidate 005."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from host import activity_session, frame_stream
ACTIVE=ROOT/'experiments/DAY1-WEBCAM-N980P-005.json'; PREV=ROOT/'experiments/DAY1-WEBCAM-N980P-004.json'
def main():
  try:
    completed=json.loads(ACTIVE.read_text()).get('status')=='completed_pass_authority_consumed'
    # A consumed manifest's producer hashes record what physically ran; live source moves on
    # afterwards. Verify them while 005 is still armable, read them as history once it is not.
    m,_,s=frame_stream.load_stream_manifest(ACTIVE,require_authority=False,verify_code_hashes=not completed); d=m.raw
    if m.experiment_id!='OPENDITOO-WEBCAM-N980P-005': raise ValueError('W8_005_ID_DRIFT')
    if (m.lifetime_seconds,m.min_frame_interval_ms,m.max_frames,m.max_application_packets,m.max_tx_bytes)!=(10,40,201,603,211854): raise ValueError('W8_005_BUDGET_DRIFT')
    if (s.get('source_kind'),s.get('session_profile'),s.get('playback_interval_ms'))!=('live','streaming_ack_clock',50): raise ValueError('W8_005_PACING_DRIFT')
    if any(d['session'].get(k) for k in ('automatic_retry','automatic_reconnect','stock_screen_reclaim','replay_after_interruption')): raise ValueError('W8_005_RETRY_OR_RECLAIM_ENABLED')
    prev=json.loads(PREV.read_text())
    if prev.get('status')!='consumed_unknown_client_telemetry_validation' or prev.get('authority',{}).get('authorization_consumed') is not True: raise ValueError('W8_004_NOT_FROZEN_CONSUMED')
    if d['w8_failed_baseline'].get('same_identity_retry_forbidden') is not True or d['w8_failed_baseline'].get('host_ledger_frames')!=9: raise ValueError('W8_004_BASELINE_DRIFT')
    hashes=s['live_source']['producer_code_sha256']
    for rel,expected in hashes.items():
      p=ROOT/rel
      if not p.is_file(): raise ValueError('W8_005_PRODUCER_MISSING:'+rel)
      if not completed and activity_session.sha256_file(p)!=expected: raise ValueError('W8_005_PRODUCER_HASH_DRIFT:'+rel)
    if activity_session.sha256_file(activity_session.HOST_BUILD_DLL)!=m.host_build_sha256: raise ValueError('W8_005_HOST_HASH_DRIFT')
    r=d['readiness']; pending={'WINDOWS_W8_005_RUNNER_BUILD_NOT_FROZEN','WINDOWS_W8_005_OFFLINE_SELFTEST_NOT_VERIFIED'}
    if completed:
      if r.get('grant_ready') or r.get('blockers')!=['AUTHORITY_ALREADY_CONSUMED']: raise ValueError('W8_005_COMPLETED_STATE_INVALID')
    elif r.get('grant_ready'):
      if r.get('blockers')!=[]: raise ValueError('W8_005_GRANT_READY_WITH_BLOCKERS')
      prep=d.get('w8_telemetry_rerun_preparation'); ev=ROOT/(prep or {}).get('evidence_file','')
      if not isinstance(prep,dict) or prep.get('status')!='pass' or prep.get('device_io') is not False or prep.get('host_session_io') is not False or prep.get('claim_created') is not False or not ev.is_file() or activity_session.sha256_file(ev)!=prep.get('evidence_sha256'): raise ValueError('W8_005_PREP_EVIDENCE_DRIFT')
    elif set(r.get('blockers',[]))!=pending: raise ValueError('W8_005_PREP_BLOCKERS_DRIFT')
    blockers=list(r.get('blockers',[]))
    for b in frame_stream.authority_blockers(ACTIVE):
      if b not in blockers: blockers.append(b)
    claim=activity_session.SessionClaim(m.experiment_id).read()
    if claim is not None and 'AUTHORITY_ALREADY_CONSUMED' not in blockers: blockers.append('AUTHORITY_ALREADY_CONSUMED')
    if not completed: blockers.append('LIVE_PREFLIGHT_NOT_PERFORMED')
    print(json.dumps({'ok':True,'manifest_valid':True,'experiment_id':m.experiment_id,'grant_ready':bool(r.get('grant_ready')),'execution_ready':False,'claim_created':claim is not None,'device_io':completed,'blockers':blockers,'session_profile':s['session_profile'],'client_interval_ms':50,'host_floor_ms':40,'lifetime_seconds':10,'max_frames':201,'max_application_packets':603,'max_tx_bytes':211854,'future_grant_string':d['authority']['grant_string_after_readiness'],'manifest_sha256':activity_session.sha256_file(ACTIVE)},sort_keys=True)); return 0
  except (OSError,ValueError,KeyError,frame_stream.SessionError) as e:
    print(json.dumps({'ok':False,'device_io':False,'execution_ready':False,'error':str(e)})); return 2
if __name__=='__main__': raise SystemExit(main())
