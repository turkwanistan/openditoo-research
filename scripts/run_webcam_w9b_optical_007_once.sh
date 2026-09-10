#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
MANIFEST="experiments/DAY1-WEBCAM-N980P-007.json"
RESULT_FILE="captures/OPENDITOO-WEBCAM-W9B-007-LIVE-RESULT-2026-09-10.json"
RAW_FILE="captures/OPENDITOO-WEBCAM-W9B-007-LIVE-RAW-2026-09-10.log"
SERVICE="openditoo-product.service"; PRODUCT_WAS_ACTIVE=false; PRODUCT_RESTORED=false; TMP="$(mktemp)"
restore_product(){
 if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
  echo W9B_RESTORE_PRODUCT_BEGIN; systemctl --user start "$SERVICE" || true
  for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)" == active ]] && { PRODUCT_RESTORED=true; echo W9B_RESTORE_PRODUCT_SERVICE_ACTIVE; return 0; }; sleep 0.25; done
  echo W9B_RESTORE_PRODUCT_FAILED >&2; return 1
 fi
}
cleanup(){ local rc=$?; rm -f "$TMP"; restore_product || true; exit "$rc"; }; trap cleanup EXIT INT TERM
echo 'W9B_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-007 lifetime_seconds=10 client_floor_ms=50 host_floor_ms=40 margin_ms=10 max_frames=201 max_packets=603 max_tx_bytes=211854'
python3 scripts/verify_day1_offline.py
python3 scripts/check_webcam_w9b_optical_007.py
python3 - <<'PY'
from pathlib import Path
from host import frame_stream
p=Path('experiments/DAY1-WEBCAM-N980P-007.json'); blockers=frame_stream.authority_blockers(p)
if blockers: raise SystemExit('W9B_AUTHORITY_BLOCKED '+','.join(blockers))
m,_,s=frame_stream.load_stream_manifest(p,require_authority=True)
assert m.experiment_id=='OPENDITOO-WEBCAM-N980P-007'
assert (m.lifetime_seconds,m.min_frame_interval_ms,m.max_frames,m.max_application_packets,m.max_tx_bytes)==(10,40,201,603,211854)
assert s['source_kind']=='live' and s['session_profile']=='streaming_ack_clock' and s['playback_interval_ms']==50
print('W9B_AUTHORITY_AND_ENVELOPE_PASS')
PY
state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == active ]] && PRODUCT_WAS_ACTIVE=true; echo "W9B_PRODUCT_PRE_STATE=$state"
systemctl --user stop "$SERVICE"
for _ in $(seq 1 40); do state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == inactive ]] && break; sleep 0.25; done
[[ "$state" == inactive ]] || { echo "W9B_PRODUCT_STOP_FAILED state=$state" >&2; exit 2; }; echo W9B_PRODUCT_STOP_PASS
idle=false
for _ in $(seq 1 40); do
 if python3 - <<'PY'
from host import webcam_trial
try: webcam_trial._host_preclaim_status()
except Exception as exc: print('W9B_HOST_IDLE_WAIT',type(exc).__name__,str(exc)); raise SystemExit(1)
print('W9B_HOST_IDLE_PASS')
PY
 then idle=true; break; fi; sleep 0.25
done
[[ "$idle" == true ]] || { echo W9B_HOST_DID_NOT_BECOME_IDLE >&2; exit 2; }
# Attempt 006 opened 3.99 s after stopping a product session that was itself only seconds old,
# and the Ditoo then ignored the new link for the full 5 s ACK budget. The Host reporting idle
# says nothing about the DEVICE having finished tearing its side down, so wait a fixed settle
# window before opening. Root cause is LOW confidence, so this is insurance, not a proven fix:
# a second consecutive IMAGE_RX_RECV_TIMEOUT falsifies the handover theory.
echo "W9B_HANDOVER_SETTLE_BEGIN seconds=8"
sleep 8
echo W9B_HANDOVER_SETTLE_DONE
mkdir -p captures; set +e; python3 cli/webcam.py run --manifest "$MANIFEST" 2>&1 | tee "$TMP"; trial_rc=${PIPESTATUS[0]}; set -e
cp "$TMP" "$RAW_FILE"; json_line="$(grep -E '^\{.*\}$' "$TMP" | tail -n 1 || true)"; [[ -n "$json_line" ]] || { echo W9B_RESULT_JSON_MISSING >&2; exit 2; }; printf '%s\n' "$json_line" > "$RESULT_FILE"
restore_product
connected=false
for _ in $(seq 1 40); do
 status_json="$(python3 cli/openditoo.py product-status 2>/dev/null || true)"
 if [[ -n "$status_json" ]] && STATUS_JSON="$status_json" python3 - <<'PY'
import json,os
try:d=json.loads(os.environ['STATUS_JSON'])
except Exception:raise SystemExit(1)
raise SystemExit(0 if d.get('runtime',{}).get('status')=='connected' else 1)
PY
 then printf '%s\n' "$status_json"; echo W9B_RESTORE_PRODUCT_CONNECTED_PASS; connected=true; break; fi; sleep 0.25
done
[[ "$connected" == true ]] || echo W9B_RESTORE_PRODUCT_CONNECTED_NOT_CONFIRMED >&2
python3 - "$RESULT_FILE" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
if d.get('experiment_id')!='OPENDITOO-WEBCAM-N980P-007': raise SystemExit('W9B_RESULT_ID_MISMATCH')
if d.get('claim_created') is not True: raise SystemExit('W9B_CLAIM_NOT_CREATED')
if d.get('outcome')!='stopped_clean': raise SystemExit('W9B_TERMINAL_NOT_CLEAN '+str(d.get('outcome')))
if any(d.get(k) for k in ('retry','reconnect','reclaim')): raise SystemExit('W9B_RETRY_OR_RECLAIM_OBSERVED')
if d.get('duplicateSourceFrames')!=0: raise SystemExit('W9B_DUPLICATE_SOURCE_FRAME')
if d.get('rawQueueDepthMax',2)>1 or d.get('readyQueueDepthMax',2)>1: raise SystemExit('W9B_QUEUE_DEPTH_BROKEN')
ident=d.get('sourceIdentity') or {}
if not ident: raise SystemExit('W9B_SOURCE_IDENTITY_MISSING')
if ident.get('duplicateSelections'): raise SystemExit('W9B_DUPLICATE_SELECTION')
if ident.get('outOfOrderSelections'): raise SystemExit('W9B_OUT_OF_ORDER_SELECTION')
if ident.get('selectedCount') != d.get('frames'): raise SystemExit('W9B_IDENTITY_COUNT_MISMATCH')
fps=float(d.get('effectiveFps',0)); p95=float(d.get('sourceAgeAtSendMs',{}).get('p95',999999))
# No rate assertion: 005 characterized rate and 006 must not reintroduce a target.
print(f"W9B_LIVE_TRIAL_PASS outcome=stopped_clean frames={d.get('frames')} fps={fps:.3f} "
      f"source_age_send_p95_ms={p95:.3f} first_source_id={ident.get('firstSelectedSourceId')} "
      f"last_source_id={ident.get('lastSelectedSourceId')} acquired={ident.get('lastAcquiredSourceId')} "
      f"skipped={ident.get('skippedBetweenSelections')} duplicates=0")
PY
[[ "$trial_rc" -eq 0 ]] || exit "$trial_rc"
echo "W9B_COMPLETE result=$RESULT_FILE raw=$RAW_FILE product_restored=$PRODUCT_RESTORED"
