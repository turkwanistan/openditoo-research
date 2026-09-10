#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

MANIFEST="experiments/DAY1-WEBCAM-N980P-001.json"
RESULT_FILE="captures/OPENDITOO-WEBCAM-W7-LIVE-RESULT-2026-09-09.json"
RAW_FILE="captures/OPENDITOO-WEBCAM-W7-LIVE-RAW-2026-09-09.log"
SERVICE="openditoo-product.service"
PRODUCT_WAS_ACTIVE=false
PRODUCT_RESTORED=false
TMP="$(mktemp)"

restore_product() {
    if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
        echo "W7_RESTORE_PRODUCT_BEGIN"
        systemctl --user start "$SERVICE" || true
        for _ in $(seq 1 40); do
            if [[ "$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)" == "active" ]]; then
                PRODUCT_RESTORED=true
                echo "W7_RESTORE_PRODUCT_PASS"
                return 0
            fi
            sleep 0.25
        done
        echo "W7_RESTORE_PRODUCT_FAILED" >&2
        return 1
    fi
}

cleanup() {
    local rc=$?
    rm -f "$TMP"
    restore_product || true
    exit "$rc"
}
trap cleanup EXIT INT TERM

echo "W7_BEGIN experiment_id=OPENDITOO-WEBCAM-N980P-001 lifetime_seconds=10 max_frames=112 max_packets=336 max_tx_bytes=118048"
python3 scripts/verify_day1_offline.py
python3 scripts/check_webcam_trial.py
python3 - <<'PY'
from pathlib import Path
from host import frame_stream
p=Path('experiments/DAY1-WEBCAM-N980P-001.json')
blockers=frame_stream.authority_blockers(p)
if blockers:
    raise SystemExit('W7_AUTHORITY_BLOCKED ' + ','.join(blockers))
m,_,s=frame_stream.load_stream_manifest(p, require_authority=True)
assert m.experiment_id == 'OPENDITOO-WEBCAM-N980P-001'
assert (m.lifetime_seconds,m.min_frame_interval_ms,m.max_frames,m.max_application_packets,m.max_tx_bytes)==(10,40,112,336,118048)
assert s['source_kind']=='live' and s['session_profile']=='streaming_ack_clock' and s['playback_interval_ms']==90
print('W7_AUTHORITY_AND_ENVELOPE_PASS')
PY

state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
if [[ "$state" == "active" ]]; then
    PRODUCT_WAS_ACTIVE=true
fi
echo "W7_PRODUCT_PRE_STATE=$state"

# One-controller rule: suspend the MCP dashboard before the webcam can claim/open a Host session.
systemctl --user stop "$SERVICE"
for _ in $(seq 1 40); do
    state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
    [[ "$state" == "inactive" ]] && break
    sleep 0.25
done
[[ "$state" == "inactive" ]] || { echo "W7_PRODUCT_STOP_FAILED state=$state" >&2; exit 2; }
echo "W7_PRODUCT_STOP_PASS"

# The Host is a separate Windows process. Wait until the stopped product has closed its session.
idle=false
for _ in $(seq 1 40); do
    if python3 - <<'PY'
from host import webcam_trial
try:
    webcam_trial._host_preclaim_status()
except Exception as exc:
    print('W7_HOST_IDLE_WAIT', type(exc).__name__, str(exc))
    raise SystemExit(1)
print('W7_HOST_IDLE_PASS')
PY
    then
        idle=true
        break
    fi
    sleep 0.25
done
[[ "$idle" == true ]] || { echo "W7_HOST_DID_NOT_BECOME_IDLE" >&2; exit 2; }

mkdir -p captures
set +e
python3 cli/webcam.py run --manifest "$MANIFEST" 2>&1 | tee "$TMP"
trial_rc=${PIPESTATUS[0]}
set -e
cp "$TMP" "$RAW_FILE"

json_line="$(grep -E '^\{.*\}$' "$TMP" | tail -n 1 || true)"
[[ -n "$json_line" ]] || { echo "W7_RESULT_JSON_MISSING" >&2; exit 2; }
printf '%s\n' "$json_line" > "$RESULT_FILE"

# Restore the pre-existing everyday controller only after the webcam process has terminated.
restore_product

# Give Runtime 003 a brief chance to reconnect and report status; failure here does not rewrite
# the already-recorded webcam terminal outcome.
for _ in $(seq 1 20); do
    if python3 cli/openditoo.py product-status >/tmp/openditoo-w7-product-status.json 2>/dev/null; then
        cat /tmp/openditoo-w7-product-status.json
        break
    fi
    sleep 0.25
done
rm -f /tmp/openditoo-w7-product-status.json

python3 - "$RESULT_FILE" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
if d.get('experiment_id') != 'OPENDITOO-WEBCAM-N980P-001':
    raise SystemExit('W7_RESULT_ID_MISMATCH')
if d.get('claim_created') is not True:
    raise SystemExit('W7_CLAIM_NOT_CREATED')
if d.get('outcome') != 'stopped_clean':
    raise SystemExit('W7_TERMINAL_NOT_CLEAN ' + str(d.get('outcome')))
print('W7_LIVE_PASS outcome=stopped_clean claim_created=true')
PY

[[ "$trial_rc" -eq 0 ]] || exit "$trial_rc"
echo "W7_COMPLETE result=$RESULT_FILE raw=$RAW_FILE product_restored=$PRODUCT_RESTORED"
