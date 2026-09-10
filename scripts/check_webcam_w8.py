#!/usr/bin/env python3
"""Historical read-only review of consumed W8 attempt 003."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host import activity_session, frame_stream
M=ROOT/'experiments/DAY1-WEBCAM-N980P-003.json'
def main():
    try:
        d=json.loads(M.read_text(encoding='utf-8')); a=d['w8_attempt']; auth=d['authority']; r=d['readiness']
        if d.get('status')!='consumed_unknown_pacing_violation': raise ValueError('W8_003_STATUS_DRIFT')
        if auth.get('authorization_consumed') is not True: raise ValueError('W8_003_AUTHORITY_NOT_CONSUMED')
        if r.get('grant_ready') or r.get('blockers')!=['AUTHORITY_ALREADY_CONSUMED']: raise ValueError('W8_003_READINESS_DRIFT')
        if (a.get('outcome'),a.get('terminal_reason'),a.get('frames'),a.get('packets'),a.get('tx_bytes')) != ('unknown','SESSION_PACING_VIOLATION',2,6,2102): raise ValueError('W8_003_RESULT_DRIFT')
        for pk,sk in [('result_file','result_sha256'),('raw_file','raw_sha256'),('failure_file','failure_sha256')]:
            p=ROOT/a[pk]
            if not p.is_file() or activity_session.sha256_file(p)!=a[sk]: raise ValueError('W8_003_EVIDENCE_DRIFT:'+pk)
        claim=activity_session.SessionClaim('OPENDITOO-WEBCAM-N980P-003').read()
        if not claim or claim.get('state')!='finished' or claim.get('outcome')!='unknown': raise ValueError('W8_003_CLAIM_DRIFT')
        print(json.dumps({'ok':True,'historical':True,'experiment_id':'OPENDITOO-WEBCAM-N980P-003','status':d['status'],'claim_created':True,'device_io':True,'outcome':'unknown','terminal_reason':'SESSION_PACING_VIOLATION','frames':2,'packets':6,'tx_bytes':2102,'blockers':frame_stream.authority_blockers(M)},sort_keys=True)); return 0
    except (OSError,ValueError,KeyError) as e:
        print(json.dumps({'ok':False,'historical':True,'device_io':False,'error':str(e)})); return 2
if __name__=='__main__': raise SystemExit(main())
