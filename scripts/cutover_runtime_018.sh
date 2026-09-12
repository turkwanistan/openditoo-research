#!/usr/bin/env bash
# Runtime 018 cutover: Runtime 017 exactly + hidden BTVS window + one rebind renewal per sidecar epoch.
#   bash scripts/cutover_runtime_018.sh "Grant OPENDITOO-PRODUCT-RUNTIME-018"
#   bash scripts/cutover_runtime_018.sh --rollback   (restores Runtime 017; its own task/install root stay intact)
# Run from feat/media-avrcp-input. The script acts on main only after exact grant + frozen dependency checks.
set -euo pipefail
BRANCH=feat/media-avrcp-input
SERVICE=openditoo-product.service
WIN=/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo
RAW_TASK="OpenDitoo Raw AVRCP Broker 018"  # elevated sidecar; installed once by the owner (see below)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$HERE" worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/main$/{print p; exit}')"
[[ -n "$MAIN" && -d "$MAIN" ]] || { echo R018_MAIN_NOT_FOUND >&2; exit 2; }
cd "$MAIN"
LOCAL=.openditoo-local; POLICY=$LOCAL/product-runtime-policy.json; RB=$LOCAL/rollback-runtime-017
TEMPLATE="$HERE/product/OPENDITOO-PRODUCT-RUNTIME-018.json"

policy_id(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["authority"]["policy_id"])' "$1"; }
expected_host(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["build"]["host_dll_sha256"])' "$TEMPLATE"; }
host_ok(){ [[ "$(sha256sum "$WIN/Day1Host/OpenDitoo.Day1.Host.dll" | cut -c1-64)" == "$(expected_host)" ]]; }

template_ready(){
  (cd "$HERE" && PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY')
import json
from host import product_runtime_v12 as v12
raw=json.loads(v12.TEMPLATE.read_text(encoding='utf-8'))
assert '__PENDING_' not in json.dumps(raw), 'Runtime 018 binary/dependency identities are not frozen'
v12.load_policy(v12.TEMPLATE, require_authority=False, verify_hashes=False)
assert raw['runtime_revision'] == 13
assert raw['build']['code_sha256'] == v12.code_hashes()
assert v12.authority_blockers(v12.TEMPLATE) == [
  'PRODUCT_AUTHORITY_MISSING','PRODUCT_AUTHORITY_UNATTRIBUTED','PRODUCT_AUTHORITY_SCOPE_MISMATCH']
print('R018_TEMPLATE_READY')
PY
}

verify_windows_group(){ # build key
  local key="$1"
  PYTHONDONTWRITEBYTECODE=1 python3 - "$TEMPLATE" "$key" <<'PY'
import hashlib,json,sys
from pathlib import Path
from host.pagination import windows_path
raw=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for name, expected in raw['build'][sys.argv[2]].items():
    path=windows_path(name)
    if not path.is_file(): raise SystemExit(f'missing {sys.argv[2]} file: {name}')
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected: raise SystemExit(f'{sys.argv[2]} hash mismatch: {name} expected={expected} actual={actual}')
PY
}

stop_service(){
  systemctl --user stop "$SERVICE" || true
  # A crash-looped unit ends "failed", not "inactive"; that is stopped too (else rollback aborts half-way).
  for _ in $(seq 1 40); do
    case "$(systemctl --user is-active "$SERVICE" || true)" in
      inactive|failed) systemctl --user reset-failed "$SERVICE" 2>/dev/null || true; return 0 ;;
    esac
    sleep 0.25
  done
  echo R018_SERVICE_STOP_FAILED >&2; return 1
}
start_and_confirm(){
  systemctl --user start "$SERVICE"
  for _ in $(seq 1 100); do
    r="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c 'import json,sys;r=json.load(sys.stdin)["runtime"];print(r.get("status"), r.get("last_error") is None)' 2>/dev/null || true)"
    [[ "$r" == "connected True" ]] && return 0; sleep 0.5
  done
  echo "R018_DASHBOARD_NOT_CONFIRMED $r" >&2; return 1
}
product_check(){
  python3 cli/openditoo.py product-check --policy "$POLICY" \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["execution_ready"] and d["runtime_revision"]==int(sys.argv[1]),d' "$1"
}
end_raw_task(){ /mnt/c/Windows/System32/schtasks.exe /end /tn "$RAW_TASK" >/dev/null 2>&1 || true; }

if [[ "${1:-}" == "--rollback" ]]; then
  [[ -f "$RB/pre_commit" && -f "$RB/product-runtime-policy.json" ]] || { echo R018_NO_ROLLBACK_SAVED >&2; exit 2; }
  stop_service
  pre="$(cat "$RB/pre_commit")"
  if [[ "$(git rev-parse 'HEAD^{tree}')" != "$(git rev-parse "$pre^{tree}")" ]]; then
    git read-tree -u --reset "$pre"
    git commit -q -m "Rollback: restore the Runtime 017 source tree ($(git rev-parse --short "$pre"))"
  fi
  [[ "$(git rev-parse 'HEAD^{tree}')" == "$(git rev-parse "$pre^{tree}")" ]] || { echo R018_ROLLBACK_TREE_MISMATCH >&2; exit 2; }
  install -m 600 "$RB/product-runtime-policy.json" "$POLICY"
  end_raw_task  # Runtime 018 task stays registered but idle; Runtime 017 runs its own task
  host_ok || { echo R018_ROLLBACK_HOST_HASH >&2; exit 2; }
  product_check 12 && echo R018_ROLLBACK_PRODUCT_CHECK_PASS
  start_and_confirm && echo R018_ROLLED_BACK_TO_RUNTIME_017
  exit 0
fi

[[ "${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-018" ]] || { echo R018_EXACT_GRANT_REQUIRED >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo R018_MAIN_HAS_TRACKED_CHANGES >&2; exit 2; }
git merge-base --is-ancestor HEAD "$BRANCH" || { echo R018_BRANCH_NOT_FAST_FORWARD >&2; exit 2; }
[[ "$(policy_id "$POLICY")" == OPENDITOO-PRODUCT-RUNTIME-017 ]] || { echo R018_CURRENT_POLICY_IS_NOT_017 >&2; exit 2; }
template_ready || { echo R018_TEMPLATE_NOT_READY >&2; exit 2; }
host_ok || { echo R018_INSTALLED_HOST_NOT_RUNTIME_017 >&2; exit 2; }
verify_windows_group button_probe_sha256 || { echo R018_BUTTON_PROBE_IDENTITY_FAIL >&2; exit 2; }
verify_windows_group raw_avrcp_dependencies_sha256 || { echo R018_CAPTURE_DEPENDENCY_IDENTITY_FAIL >&2; exit 2; }
# BTVS needs elevation: the sidecar must already be installed (admin-only bytes + highest-privilege on-demand task)
# by the owner from Administrator PowerShell with runtime/windows/install_openditoo_raw_avrcp_task.ps1 -Runtime 018.
verify_windows_group raw_avrcp_broker_sha256 || { echo R018_ELEVATED_SIDECAR_NOT_INSTALLED >&2; exit 2; }
(cd "$HERE" && python3 -m host.raw_avrcp_input verify-task "$TEMPLATE") || { echo R018_ELEVATED_TASK_MISMATCH >&2; exit 2; }
echo R018_TEMPLATE_AND_DEPENDENCIES_PASS

rm -rf "$RB"; mkdir -p -m 700 "$RB"
git rev-parse HEAD > "$RB/pre_commit"
cp -p "$POLICY" "$RB/"
echo "R018_ROLLBACK_SAVED pre=$(cut -c1-12 "$RB/pre_commit")"

stop_service
python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' \
  || { echo R018_HOST_NOT_IDLE >&2; systemctl --user start "$SERVICE"; exit 2; }
echo R018_HOST_IDLE
rollback_now(){ echo "R018_FAILED: $1 -- rolling back" >&2; bash "$HERE/scripts/cutover_runtime_018.sh" --rollback; exit 2; }

git merge --ff-only "$BRANCH" >/dev/null && echo "R018_MAIN_FAST_FORWARDED $(git rev-parse --short HEAD)"

# Re-check the installed elevated sidecar against main's (now identical) policy after the fast-forward.
verify_windows_group raw_avrcp_broker_sha256 || rollback_now RAW_BROKER_HASH
python3 -m host.raw_avrcp_input verify-task product/OPENDITOO-PRODUCT-RUNTIME-018.json || rollback_now RAW_TASK_MISMATCH
echo R018_ELEVATED_SIDECAR_PASS

{ python3 scripts/verify_day1_offline.py && python3 scripts/verify_interactive_pages_offline.py \
  && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_raw_avrcp_input tests.test_runtime017_raw_avrcp tests.test_runtime018_input_robustness; } \
  > "$RB/offline-gate.log" 2>&1 || { tail -30 "$RB/offline-gate.log" >&2; rollback_now OFFLINE_GATE; }
echo R018_MAIN_OFFLINE_PASS

python3 - "$1" <<'PY' || rollback_now LOCAL_POLICY
import json,os,sys
from pathlib import Path
doc=json.loads(Path('product/OPENDITOO-PRODUCT-RUNTIME-018.json').read_text(encoding='utf-8'))
a=doc['authority']
assert a['persistent_runtime_authorized'] is False and a['grant_text'] is None
assert '__PENDING_' not in json.dumps(doc)
a.update({'persistent_runtime_authorized':True,'revoked':False,'grant_text':sys.argv[1],
          'granted_by':'owner, in-session','grant_scope':a['grant_scope_requested']})
path=Path('.openditoo-local/product-runtime-policy.json'); tmp=path.with_suffix('.tmp')
fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as h: json.dump(doc,h,indent=1,sort_keys=True)
os.replace(tmp,path)
print('R018_LOCAL_POLICY_WRITTEN')
PY
product_check 13 && echo R018_PRODUCT_CHECK_PASS || rollback_now PRODUCT_CHECK
start_and_confirm || rollback_now DASHBOARD_NOT_CONNECTED
python3 host/webcam_studio.py policy-check >/dev/null && echo R018_WEBCAM_POLICY_CHECK_PASS || rollback_now WEBCAM_POLICY_CHECK
echo "R018_CUTOVER_PASS main=$(git rev-parse --short HEAD) rollback=$RB"
