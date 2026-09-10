#!/usr/bin/env python3
"""Read-only historical review of consumed W8 attempt 004."""
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/'experiments/DAY1-WEBCAM-N980P-004.json'
E=ROOT/'captures/OPENDITOO-WEBCAM-W8-RERUN-004-FAILURE-2026-09-09.json'
R=ROOT/'captures/OPENDITOO-WEBCAM-W8-RERUN-004-LIVE-RESULT-2026-09-09.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
  try:
    d=json.loads(M.read_text()); e=json.loads(E.read_text()); r=json.loads(R.read_text())
    if d.get('status')!='consumed_unknown_client_telemetry_validation': raise ValueError('W8_004_HISTORICAL_STATUS_DRIFT')
    if d.get('authority',{}).get('authorization_consumed') is not True: raise ValueError('W8_004_AUTHORITY_NOT_CONSUMED')
    if d.get('readiness',{}).get('blockers')!=['AUTHORITY_ALREADY_CONSUMED']: raise ValueError('W8_004_REPLAY_BLOCKER_DRIFT')
    a=d.get('w8_attempt',{})
    if (a.get('client_counted_frames'),a.get('host_ledger_frames'),a.get('host_ledger_packets'),a.get('host_ledger_tx_bytes'))!=(8,9,27,9420): raise ValueError('W8_004_EVIDENCE_TOTAL_DRIFT')
    if a.get('terminal_reason')!='HOST_FRAME_ELAPSED_INVALID' or a.get('pacing_violation_observed') is not False: raise ValueError('W8_004_DIAGNOSIS_DRIFT')
    if sha(E)!=a.get('failure_evidence_sha256'): raise ValueError('W8_004_FAILURE_EVIDENCE_HASH_DRIFT')
    print(json.dumps({'ok':True,'historical':True,'device_io':True,'claim_created':True,'experiment_id':'OPENDITOO-WEBCAM-N980P-004','status':d['status'],'outcome':r.get('outcome'),'terminal_reason':r.get('terminalReason'),'client_counted_frames':8,'host_ledger_frames':9,'host_ledger_packets':27,'host_ledger_tx_bytes':9420,'blockers':['AUTHORITY_ALREADY_CONSUMED']},sort_keys=True)); return 0
  except Exception as ex:
    print(json.dumps({'ok':False,'historical':True,'error':str(ex)})); return 2
if __name__=='__main__': raise SystemExit(main())
