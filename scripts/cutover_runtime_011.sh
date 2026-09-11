#!/usr/bin/env bash
# Runtime 011 cutover: Runtime 010 plus Pocket Moss and generic modal navigation.
# Same exact Host, target, webcam policy, session envelope, pacing, reconnect/reclaim and ButtonProbe.
#   bash scripts/cutover_runtime_011.sh "Grant OPENDITOO-PRODUCT-RUNTIME-011"
#   bash scripts/cutover_runtime_011.sh --rollback     # exact source tree + local policy back: Runtime 010
# Run it from the feat/pocket-moss-v2-art worktree. It acts on the MAIN checkout (where the
# service runs): after the grant and a Host-idle check it fast-forwards main to this branch.
# The Host (3faf520f) and webcam 006 are unchanged, so nothing on Windows is stopped, copied or
# restarted in either direction; the installed Host hash is asserted instead.
set -euo pipefail
BRANCH=feat/pocket-moss-v2-art
HOST_EXPECTED=3faf520f46ce824970f583c3d932e0168484b0f6ffa5975e6b38e77330c4900f
SERVICE=openditoo-product.service
WIN=/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$HERE" worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/main$/{print p; exit}')"
[[ -n "$MAIN" && -d "$MAIN" ]] || { echo R011_MAIN_NOT_FOUND >&2; exit 2; }
cd "$MAIN"
LOCAL=.openditoo-local; POLICY=$LOCAL/product-runtime-policy.json; RB=$LOCAL/rollback-runtime-010

policy_id(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["authority"]["policy_id"])' "$1"; }
host_ok(){ [[ "$(sha256sum "$WIN/Day1Host/OpenDitoo.Day1.Host.dll" | cut -c1-64)" == "$HOST_EXPECTED" ]]; }
probe_ok(){
  python3 - "$HERE/product/OPENDITOO-PRODUCT-RUNTIME-011.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
from host.pagination import windows_path
raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for name, expected in raw["build"]["button_probe_sha256"].items():
    path = windows_path(name)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"button-probe hash mismatch: {name}")
PY
}
template_ok(){
  # A linked worktree intentionally does not contain git-ignored Release build outputs.
  # Validate the exact Runtime 011 source/assets and policy structure here; installed Host/Probe
  # bytes are checked independently before main is touched. Full product-check runs again in main.
  (cd "$HERE" && python3 - <<'PY')
import json
from host import product_runtime_v5 as v5
raw = json.loads(v5.TEMPLATE.read_text(encoding="utf-8"))
v5.load_policy(v5.TEMPLATE, require_authority=False, verify_hashes=False)
assert raw["runtime_revision"] == 6
assert raw["build"]["code_sha256"] == v5.code_hashes()
assert v5.authority_blockers(v5.TEMPLATE) == [
    "PRODUCT_AUTHORITY_MISSING",
    "PRODUCT_AUTHORITY_UNATTRIBUTED",
    "PRODUCT_AUTHORITY_SCOPE_MISMATCH",
]
PY
}
stop_service(){
  systemctl --user stop "$SERVICE"
  for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" || true)" == inactive ]] && return 0; sleep 0.25; done
  echo R011_SERVICE_STOP_FAILED >&2; return 1
}
start_and_confirm(){
  systemctl --user start "$SERVICE"
  for _ in $(seq 1 80); do
    r="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c 'import json,sys;r=json.load(sys.stdin)["runtime"];print(r["status"], r["last_error"] is None)' 2>/dev/null || true)"
    [[ "$r" == "connected True" ]] && return 0; sleep 0.5
  done
  echo "R011_DASHBOARD_NOT_CONFIRMED $r" >&2; return 1
}
product_check(){  # $1 = expected runtime_revision
  python3 cli/openditoo.py product-check --policy "$POLICY" \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["execution_ready"] and d["runtime_revision"]==int(sys.argv[1]), d' "$1"
}

if [[ "${1:-}" == "--rollback" ]]; then
  [[ -f "$RB/pre_commit" && -f "$RB/product-runtime-policy.json" ]] || { echo R011_NO_ROLLBACK_SAVED >&2; exit 2; }
  stop_service
  pre="$(cat "$RB/pre_commit")"
  # The merged range may contain merge commits, which `git revert A..B` cannot revert. Restore the
  # exact Runtime 010 tree as one forward commit instead (no history rewrite), then prove it.
  if [[ "$(git rev-parse 'HEAD^{tree}')" != "$(git rev-parse "$pre^{tree}")" ]]; then
    git read-tree -u --reset "$pre"
    git commit -q -m "Rollback: restore the Runtime 010 source tree ($(git rev-parse --short "$pre"))"
  fi
  [[ "$(git rev-parse 'HEAD^{tree}')" == "$(git rev-parse "$pre^{tree}")" ]] || { echo R011_ROLLBACK_TREE_MISMATCH >&2; exit 2; }
  install -m 600 "$RB/product-runtime-policy.json" "$POLICY"
  host_ok || { echo R011_ROLLBACK_HOST_HASH >&2; exit 2; }
  product_check 5 && echo R011_ROLLBACK_PRODUCT_CHECK_PASS
  start_and_confirm && echo R011_ROLLED_BACK_TO_RUNTIME_010
  exit 0
fi

[[ "${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-011" ]] || { echo R011_EXACT_GRANT_REQUIRED >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo R011_MAIN_HAS_TRACKED_CHANGES >&2; exit 2; }
git merge-base --is-ancestor HEAD "$BRANCH" || { echo R011_BRANCH_NOT_FAST_FORWARD >&2; exit 2; }
[[ "$(policy_id "$POLICY")" == OPENDITOO-PRODUCT-RUNTIME-010 ]] || { echo R011_CURRENT_POLICY_IS_NOT_010 >&2; exit 2; }
host_ok || { echo R011_INSTALLED_HOST_NOT_RUNTIME_010 >&2; exit 2; }
probe_ok || { echo R011_INSTALLED_BUTTON_PROBE_NOT_RUNTIME_010 >&2; exit 2; }
# The linked feature worktree has no git-ignored Release DLL by design. Prove its exact frozen
# source/assets/policy without requiring that absent build output; Host/Probe bytes were just
# proven against their installed Windows copies.
template_ok || { echo R011_TEMPLATE_NOT_HASH_VALID >&2; exit 2; }
echo R011_TEMPLATE_AND_INSTALLED_BINARIES_PASS

# Young-link guard (webcam launcher lesson): do not tear down a seconds-old dashboard connection.
age="$(python3 cli/openditoo.py product-status | python3 -c '
import json, sys, datetime
r = json.load(sys.stdin)["runtime"]; o = r.get("current_session_opened_at")
print(0 if r.get("status") != "connected" or not o else int((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(o.replace("Z", "+00:00"))).total_seconds()))')"
[[ "$age" -lt 30 ]] && { echo "dashboard link ${age}s old; waiting $((30 - age))s"; sleep $((30 - age)); }

rm -rf "$RB"; mkdir -p -m 700 "$RB"
git rev-parse HEAD > "$RB/pre_commit"
cp -p "$POLICY" "$RB/"
echo "R011_ROLLBACK_SAVED pre=$(cut -c1-12 "$RB/pre_commit")"

stop_service
python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' \
  || { echo R011_HOST_NOT_IDLE >&2; systemctl --user start "$SERVICE"; exit 2; }
echo R011_HOST_IDLE
rollback_now(){ echo "R011_FAILED: $1 -- rolling back" >&2; bash "$HERE/scripts/cutover_runtime_011.sh" --rollback; exit 2; }

git merge --ff-only "$BRANCH" >/dev/null && echo "R011_MAIN_FAST_FORWARDED $(git rev-parse --short HEAD)"
# The full offline gates run HERE, in main (they need main's local claim/evidence state), against the
# merged source and the installed Host, before the dashboard restarts. Any failure rolls back.
{ python3 scripts/verify_day1_offline.py && python3 scripts/verify_interactive_pages_offline.py; } > "$RB/offline-gate.log" 2>&1 \
  || { tail -20 "$RB/offline-gate.log" >&2; rollback_now OFFLINE_GATE; }
echo R011_MAIN_OFFLINE_PASS

python3 - "$1" <<'PY' || rollback_now LOCAL_POLICY
import json, os, sys
from pathlib import Path
doc = json.loads(Path("product/OPENDITOO-PRODUCT-RUNTIME-011.json").read_text(encoding="utf-8"))
a = doc["authority"]
assert a["persistent_runtime_authorized"] is False and a["grant_text"] is None, "committed template must stay unauthorized"
a.update({"persistent_runtime_authorized": True, "revoked": False, "grant_text": sys.argv[1],
          "granted_by": "owner, in-session", "grant_scope": a["grant_scope_requested"]})
path = Path(".openditoo-local/product-runtime-policy.json"); tmp = path.with_suffix(".tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, indent=1, sort_keys=True)
os.replace(tmp, path)
print("R011_LOCAL_POLICY_WRITTEN")
PY
product_check 6 && echo R011_PRODUCT_CHECK_PASS || rollback_now PRODUCT_CHECK
start_and_confirm || rollback_now DASHBOARD_NOT_CONNECTED
echo R011_DASHBOARD_CONNECTED
# Webcam 006 binds the same Host and Studio; Runtime 011 must leave it valid.
python3 host/webcam_studio.py policy-check >/dev/null && echo R011_WEBCAM_006_POLICY_CHECK_PASS || rollback_now WEBCAM_POLICY_CHECK
echo "R011_CUTOVER_PASS main=$(git rev-parse --short HEAD) host=${HOST_EXPECTED:0:12} rollback=$RB"
