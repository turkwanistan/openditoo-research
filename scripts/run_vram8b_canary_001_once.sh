#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EXPERIMENT_ID=OPENDITOO-VRAM8B-CANARY-001
GRANT_TEXT='Grant OPENDITOO-VRAM8B-CANARY-001 -- stock btplayer selected'
MANIFEST="experiments/${EXPERIMENT_ID}.json"
FIXTURE_REPORT=artifacts/analysis/volatile_ram_api_vram8b_fixture.json
EXPECTED_MANIFEST_SHA=8a63e8f776c0f4409e077d066d987ade03c6b0b8bf38d2004643fc93a43ee11d
EXPECTED_FIXTURE_SHA=a9d36cf8f5f29405a0478a35939188a58bb2a26968ae3227c5b6ec4aa4831af2
POLICY=product/OPENDITOO-PRODUCT-RUNTIME-018.json
EXPECTED_POLICY_SHA=895268e91433b0ef18ee717c1378009398ad414d07083aac9eeb4194542b9c8f
SERVICE=openditoo-product.service
LOCAL_DIR=.openditoo-local/vram8b-canary-001
GRANT_FILE="$LOCAL_DIR/grant.json"
HANDOVER_FILE="$LOCAL_DIR/handover.json"
EXECUTION_FILE="$LOCAL_DIR/execution.json"
CLAIM_FILE="$LOCAL_DIR/claim.json"
RESULT_FILE="$LOCAL_DIR/result.json"
HANDOVER_SETTLE_SECONDS=18
WIN_POWERSHELL=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
RUNNER_PROJECT=runtime/windows/OpenDitoo.Vram8B.Runner001/OpenDitoo.Vram8B.Runner001.csproj
RUNNER_DLL=runtime/windows/OpenDitoo.Vram8B.Runner001/bin/Release/net8.0/OpenDitoo.Vram8B.Runner001.dll
PS1=runtime/windows/run_openditoo_vram8b_canary_001_once.ps1
PRODUCT_WAS_ACTIVE=false
PRODUCT_RESTORED=false
LIVE_PHASE_STARTED=false
RUNNER_RC=99

cleanup(){
  rc=$?
  trap - EXIT INT TERM
  rm -f "$HANDOVER_FILE" 2>/dev/null || true
  if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
    echo 'VRAM8B restoring accepted Runtime 018...'
    systemctl --user start "$SERVICE" || true
    for _ in $(seq 1 80); do
      state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
      if [[ "$state" == active ]]; then PRODUCT_RESTORED=true; break; fi
      sleep 0.25
    done
    if [[ "$PRODUCT_RESTORED" == true ]]; then
      connected=false
      for _ in $(seq 1 80); do
        if python3 cli/openditoo.py product-status 2>/dev/null | python3 -c '
import json,sys
try: r=json.load(sys.stdin).get("runtime",{})
except Exception: raise SystemExit(1)
raise SystemExit(0 if r.get("status")=="connected" and r.get("last_error") is None else 1)' >/dev/null; then connected=true; break; fi
        sleep 0.5
      done
      if [[ "$connected" == true ]]; then
        echo 'VRAM8B_RUNTIME018_CONNECTED_RESTORED'
      else
        echo 'VRAM8B_RUNTIME018_CONNECTED_RESTORE_UNCONFIRMED' >&2
        [[ "$rc" -ne 0 ]] || rc=3
      fi
    else
      echo 'VRAM8B_RUNTIME018_SERVICE_RESTORE_FAILED' >&2
      [[ "$rc" -ne 0 ]] || rc=3
    fi
  fi
  if [[ "$LIVE_PHASE_STARTED" == true ]]; then
    echo "VRAM8B_ONE_USE_COMPLETE runner_rc=$RUNNER_RC retry=false result=$RESULT_FILE claim=$CLAIM_FILE"
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

python3 tools/ditoo_vram8b_live_gate.py --selfcheck >/dev/null
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA" ]] || { echo VRAM8B_MANIFEST_HASH_DRIFT >&2; exit 2; }
[[ "$(sha256sum "$FIXTURE_REPORT" | awk '{print $1}')" == "$EXPECTED_FIXTURE_SHA" ]] || { echo VRAM8B_FIXTURE_REPORT_HASH_DRIFT >&2; exit 2; }
[[ "$(sha256sum "$POLICY" | awk '{print $1}')" == "$EXPECTED_POLICY_SHA" ]] || { echo VRAM8B_RUNTIME018_POLICY_HASH_DRIFT >&2; exit 2; }
[[ -f "$GRANT_FILE" ]] || { echo "VRAM8B_EXACT_GRANT_NOT_MATERIALIZED required='$GRANT_TEXT'" >&2; exit 2; }
[[ ! -e "$CLAIM_FILE" ]] || { echo VRAM8B_ONE_USE_ALREADY_CLAIMED >&2; exit 2; }
[[ ! -e "$RESULT_FILE" ]] || { echo VRAM8B_RESULT_ALREADY_EXISTS >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=normal | grep -v '^?? \.openditoo-local/' || true)" ]] || { echo VRAM8B_REPO_NOT_CLEAN >&2; exit 2; }
NONCE="$(python3 - "$GRANT_FILE" "$EXPECTED_MANIFEST_SHA" "$EXPECTED_FIXTURE_SHA" "$GRANT_TEXT" <<'PY'
import json,re,sys
p,mh,fh,text=sys.argv[1:]
d=json.load(open(p,encoding='utf-8'))
checks=[d.get('schema_version')==1,d.get('experiment_id')=='OPENDITOO-VRAM8B-CANARY-001',d.get('grant_text')==text,d.get('manual_stock_btplayer_selected') is True,d.get('manifest_sha256')==mh,d.get('fixture_report_sha256')==fh,d.get('granted_by')=='owner',d.get('state')=='AUTHORIZED_UNCONSUMED',isinstance(d.get('one_use_nonce'),str) and bool(re.fullmatch(r'[0-9a-fA-F]{64}',d['one_use_nonce']))]
if not all(checks): raise SystemExit('VRAM8B_LOCAL_GRANT_REJECTED')
print(d['one_use_nonce'])
PY
)" || exit 2
[[ -x "$WIN_POWERSHELL" ]] || { echo "VRAM8B_WINDOWS_POWERSHELL_MISSING path=$WIN_POWERSHELL; authority unconsumed" >&2; exit 2; }
WIN_PROJECT="$(wslpath -w "$ROOT/$RUNNER_PROJECT")"
set +e
"$WIN_POWERSHELL" -NoProfile -Command "\$ErrorActionPreference='Stop'; \$d=(Get-Command dotnet.exe -ErrorAction Stop).Source; & \$d build '$WIN_PROJECT' --configuration Release --nologo --verbosity quiet; exit \$LASTEXITCODE" | tr -d '\r'
BUILD_RC=${PIPESTATUS[0]}
set -e
[[ "$BUILD_RC" -eq 0 ]] || { echo "VRAM8B_WINDOWS_RUNNER_BUILD_FAILED rc=$BUILD_RC; authority unconsumed" >&2; exit 2; }
[[ -f "$RUNNER_DLL" ]] || { echo VRAM8B_RUNNER_DLL_MISSING >&2; exit 2; }
mkdir -p "$LOCAL_DIR"
python3 - "$EXECUTION_FILE" "$NONCE" "$RUNNER_DLL" <<'PY'
import hashlib,json,os,sys,datetime
p,nonce,dll=sys.argv[1:]
files=['runtime/windows/OpenDitoo.Vram8B.Runner001/OpenDitoo.Vram8B.Runner001.csproj','runtime/windows/OpenDitoo.Vram8B.Runner001/FrozenVram8BProtocol.cs','runtime/windows/OpenDitoo.Vram8B.Runner001/WindowsRfcommVram8BTransport.cs','runtime/windows/OpenDitoo.Vram8B.Runner001/Program.cs','runtime/windows/run_openditoo_vram8b_canary_001_once.ps1','scripts/run_vram8b_canary_001_once.sh']
sha=lambda x: hashlib.sha256(open(x,'rb').read()).hexdigest()
d={'schema_version':1,'experiment_id':'OPENDITOO-VRAM8B-CANARY-001','manifest_sha256':'8a63e8f776c0f4409e077d066d987ade03c6b0b8bf38d2004643fc93a43ee11d','fixture_report_sha256':'a9d36cf8f5f29405a0478a35939188a58bb2a26968ae3227c5b6ec4aa4831af2','one_use_nonce':nonce,'assembly_sha256':sha(dll),'source_files':[{'path':x,'sha256':sha(x)} for x in files],'sealed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')}
tmp=p+'.tmp'; open(tmp,'w',encoding='utf-8').write(json.dumps(d,indent=2,sort_keys=True)+'\n'); os.replace(tmp,p)
print('VRAM8B_EXECUTION_ASSEMBLY_SHA256='+d['assembly_sha256'])
PY
state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
[[ "$state" == active ]] || { echo "VRAM8B_RUNTIME018_NOT_ACTIVE state=$state; authority unconsumed" >&2; exit 2; }
PRODUCT_WAS_ACTIVE=true
python3 cli/openditoo.py product-status | python3 -c '
import json,sys
r=json.load(sys.stdin); assert r.get("runtime_revision")==13
s=r.get("runtime",{}); assert s.get("status")=="connected" and s.get("last_error") is None
' || { echo VRAM8B_RUNTIME018_NOT_HEALTHY >&2; exit 2; }
LIVE_PHASE_STARTED=true
echo 'VRAM8B suspending accepted Runtime 018; no experiment packet has been sent yet...'
systemctl --user stop "$SERVICE"
for _ in $(seq 1 80); do state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == inactive ]] && break; sleep 0.25; done
[[ "$state" == inactive ]] || { echo "VRAM8B_RUNTIME018_STOP_FAILED state=$state" >&2; exit 2; }
echo "VRAM8B handover settle ${HANDOVER_SETTLE_SECONDS}s..."
sleep "$HANDOVER_SETTLE_SECONDS"
python3 - "$HANDOVER_FILE" "$EXPECTED_MANIFEST_SHA" "$NONCE" <<'PY'
import json,sys,datetime,os
p,mh,nonce=sys.argv[1:]
d={'schema_version':1,'experiment_id':'OPENDITOO-VRAM8B-CANARY-001','manifest_sha256':mh,'one_use_nonce':nonce,'runtime018_service_inactive':True,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')}
tmp=p+'.tmp'; open(tmp,'w',encoding='utf-8').write(json.dumps(d,indent=2,sort_keys=True)+'\n'); os.replace(tmp,p)
PY
WIN_PS1="$(wslpath -w "$ROOT/$PS1")"
set +e
"$WIN_POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$WIN_PS1"
RUNNER_RC=$?
set -e
if [[ "$RUNNER_RC" -ne 0 ]]; then echo "VRAM8B_RUNNER_STOPPED_NO_RETRY rc=$RUNNER_RC" >&2; exit "$RUNNER_RC"; fi
exit 0
