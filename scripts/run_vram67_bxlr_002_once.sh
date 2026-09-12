#!/usr/bin/env bash
# One-use VRAM-6/7 returning-stage-0 coordinator.
# FAIL-CLOSED: performs all authority/artifact checks before touching Runtime 018.
# The Windows runner independently revalidates the manifest, grant, handover, code
# hashes and one-use claim before opening RFCOMM.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EXPERIMENT_ID=OPENDITOO-VRAM67-BXLR-002
GRANT_TEXT='Grant OPENDITOO-VRAM67-BXLR-002 -- stock btplayer selected'
MANIFEST="experiments/${EXPERIMENT_ID}.json"
FIXTURE_REPORT=artifacts/analysis/volatile_ram_api_vram67_fixture_002.json
POLICY=product/OPENDITOO-PRODUCT-RUNTIME-018.json
EXPECTED_POLICY_SHA=895268e91433b0ef18ee717c1378009398ad414d07083aac9eeb4194542b9c8f
SERVICE=openditoo-product.service
LOCAL_DIR=.openditoo-local/vram67-bxlr-002
GRANT_FILE="$LOCAL_DIR/grant.json"
HANDOVER_FILE="$LOCAL_DIR/handover.json"
CLAIM_FILE="$LOCAL_DIR/claim.json"
RESULT_FILE="$LOCAL_DIR/result.json"
HANDOVER_SETTLE_SECONDS=18
WIN_POWERSHELL=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
WIN_RUNNER_PROJECT=runtime/windows/OpenDitoo.Vram67.Runner002/OpenDitoo.Vram67.Runner002.csproj
PRODUCT_WAS_ACTIVE=false
PRODUCT_RESTORED=false
LIVE_PHASE_STARTED=false
RUNNER_RC=99

cleanup(){
  rc=$?
  trap - EXIT INT TERM
  rm -f "$HANDOVER_FILE" 2>/dev/null || true
  if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
    echo 'VRAM67 restoring accepted Runtime 018...'
    systemctl --user start "$SERVICE" || true
    for _ in $(seq 1 80); do
      state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
      if [[ "$state" == active ]]; then
        PRODUCT_RESTORED=true
        break
      fi
      sleep 0.25
    done
    if [[ "$PRODUCT_RESTORED" == true ]]; then
      connected=false
      for _ in $(seq 1 80); do
        if python3 cli/openditoo.py product-status 2>/dev/null | python3 -c '
import json,sys
try: r=json.load(sys.stdin).get("runtime",{})
except Exception: raise SystemExit(1)
raise SystemExit(0 if r.get("status")=="connected" and r.get("last_error") is None else 1)' >/dev/null; then
          connected=true
          break
        fi
        sleep 0.5
      done
      if [[ "$connected" == true ]]; then
        echo 'VRAM67_RUNTIME018_CONNECTED_RESTORED'
      else
        echo 'VRAM67_RUNTIME018_CONNECTED_RESTORE_UNCONFIRMED' >&2
        [[ "$rc" -ne 0 ]] || rc=3
      fi
    else
      echo 'VRAM67_RUNTIME018_SERVICE_RESTORE_FAILED' >&2
      [[ "$rc" -ne 0 ]] || rc=3
    fi
  fi
  if [[ "$LIVE_PHASE_STARTED" == true ]]; then
    echo "VRAM67_ONE_USE_COMPLETE runner_rc=$RUNNER_RC retry=false result=$RESULT_FILE claim=$CLAIM_FILE"
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

# OFFLINE/PRE-TOUCH GATE. Nothing below may stop Runtime 018 unless every check passes.
python3 tools/ditoo_vram67_live_gate_002.py --selfcheck >/dev/null
[[ -f "$MANIFEST" && -f "$FIXTURE_REPORT" ]] || { echo VRAM67_PREP_FILES_MISSING >&2; exit 2; }
[[ "$(sha256sum "$POLICY" | awk '{print $1}')" == "$EXPECTED_POLICY_SHA" ]] || { echo VRAM67_RUNTIME018_POLICY_HASH_DRIFT >&2; exit 2; }
[[ -f "$GRANT_FILE" ]] || { echo "VRAM67_EXACT_GRANT_NOT_MATERIALIZED: required='$GRANT_TEXT'; nothing touched" >&2; exit 2; }
[[ ! -e "$CLAIM_FILE" ]] || { echo VRAM67_ONE_USE_ALREADY_CLAIMED >&2; exit 2; }
[[ ! -e "$RESULT_FILE" ]] || { echo VRAM67_RESULT_ALREADY_EXISTS >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=normal | grep -v '^?? \.openditoo-local/' || true)" ]] || { echo VRAM67_REPO_NOT_CLEAN >&2; exit 2; }

MANIFEST_SHA="$(sha256sum "$MANIFEST" | awk '{print $1}')"
FIXTURE_SHA="$(sha256sum "$FIXTURE_REPORT" | awk '{print $1}')"
NONCE="$(python3 - "$GRANT_FILE" "$MANIFEST_SHA" "$FIXTURE_SHA" "$GRANT_TEXT" <<'PY'
import json,re,sys
p,manifest_sha,fixture_sha,grant_text=sys.argv[1:]
d=json.load(open(p,encoding='utf-8'))
checks=[
 d.get('schema_version')==1,
 d.get('experiment_id')=='OPENDITOO-VRAM67-BXLR-002',
 d.get('grant_text')==grant_text,
 d.get('manual_stock_btplayer_selected') is True,
 d.get('manifest_sha256')==manifest_sha,
 d.get('fixture_report_sha256')==fixture_sha,
 d.get('granted_by')=='owner',
 isinstance(d.get('granted_at_utc'),str) and bool(d.get('granted_at_utc')),
 isinstance(d.get('one_use_nonce'),str) and bool(re.fullmatch(r'[0-9a-fA-F]{64}',d['one_use_nonce'])),
]
if not all(checks): raise SystemExit('VRAM67_LOCAL_GRANT_REJECTED')
print(d['one_use_nonce'])
PY
)" || exit 2

python3 - "$MANIFEST" "$GRANT_TEXT" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8')); g=sys.argv[2]
assert m['experiment_id']=='OPENDITOO-VRAM67-BXLR-002'
assert m['status']=='grant_ready_awaiting_named_grant'
a=m['authority']
assert a['required_grant_text']==g
assert a['transmission_authorized'] is False
assert a['authorization_consumed'] is False
b=m['transport_budget']
assert b['max_connections']==1 and b['exact_application_sends']==3 and b['max_custom_0x6c_sends']==1
assert b['retry'] is False and b['reconnect'] is False
assert m['stage0']['bytes_hex']=='7047' and m['stage0']['instruction']=='BX LR'
PY

# Host-plumbing/build preflight is intentionally before Runtime 018 handover.
# This prevents a missing Windows bridge or compile failure from consuming live downtime.
[[ -x "$WIN_POWERSHELL" ]] || { echo "VRAM67_WINDOWS_POWERSHELL_MISSING path=$WIN_POWERSHELL; nothing touched" >&2; exit 2; }
WIN_PROJECT="$(wslpath -w "$ROOT/$WIN_RUNNER_PROJECT")"
set +e
"$WIN_POWERSHELL" -NoProfile -Command "\$ErrorActionPreference='Stop'; \$d=(Get-Command dotnet.exe -ErrorAction Stop).Source; & \$d build '$WIN_PROJECT' --configuration Release --nologo --verbosity quiet; exit \$LASTEXITCODE" | tr -d '\r'
BUILD_RC=${PIPESTATUS[0]}
set -e
[[ "$BUILD_RC" -eq 0 ]] || { echo "VRAM67_WINDOWS_RUNNER_BUILD_FAILED rc=$BUILD_RC; nothing touched" >&2; exit 2; }

state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
[[ "$state" == active ]] || { echo "VRAM67_RUNTIME018_NOT_ACTIVE state=$state; refusing controller handover" >&2; exit 2; }
PRODUCT_WAS_ACTIVE=true
python3 cli/openditoo.py product-status | python3 -c '
import json,sys
r=json.load(sys.stdin)
assert r.get("runtime_revision")==13
s=r.get("runtime",{})
assert s.get("status")=="connected" and s.get("last_error") is None
' || { echo VRAM67_RUNTIME018_NOT_HEALTHY >&2; exit 2; }

# LIVE CONTROLLER HANDOVER starts only after exact grant + all offline checks above.
LIVE_PHASE_STARTED=true
echo 'VRAM67 suspending accepted Runtime 018; no experiment packet has been sent yet...'
systemctl --user stop "$SERVICE"
for _ in $(seq 1 80); do
  state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
  [[ "$state" == inactive ]] && break
  sleep 0.25
done
[[ "$state" == inactive ]] || { echo "VRAM67_RUNTIME018_STOP_FAILED state=$state" >&2; exit 2; }

echo "VRAM67 handover settle ${HANDOVER_SETTLE_SECONDS}s (covers Runtime 018's 15s sidecar lease expiry)..."
sleep "$HANDOVER_SETTLE_SECONDS"
mkdir -p "$LOCAL_DIR"
python3 - "$HANDOVER_FILE" "$MANIFEST_SHA" "$NONCE" <<'PY'
import json,sys,datetime,os
p,manifest_sha,nonce=sys.argv[1:]
d={
 'schema_version':1,
 'experiment_id':'OPENDITOO-VRAM67-BXLR-002',
 'manifest_sha256':manifest_sha,
 'one_use_nonce':nonce,
 'runtime018_service_inactive':True,
 'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),
}
tmp=p+'.tmp'
with open(tmp,'w',encoding='utf-8') as f: json.dump(d,f,indent=2,sort_keys=True); f.write('\n')
os.replace(tmp,p)
PY

PS1="$(wslpath -w "$ROOT/runtime/windows/run_openditoo_vram67_bxlr_002_once.ps1")"
set +e
"$WIN_POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$PS1"
RUNNER_RC=$?
set -e
if [[ "$RUNNER_RC" -ne 0 ]]; then
  echo "VRAM67_RUNNER_STOPPED_NO_RETRY rc=$RUNNER_RC" >&2
  exit "$RUNNER_RC"
fi

# A runner transport pass is not final success until accepted product liveness is restored.
# cleanup performs that restoration and will change rc to 3 if connection recovery is unconfirmed.
exit 0
