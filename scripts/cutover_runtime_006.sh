#!/usr/bin/env bash
# Runtime 006 cutover: same service, same Host, same dashboard envelope, plus button pagination.
#   bash scripts/cutover_runtime_006.sh "Grant OPENDITOO-PRODUCT-RUNTIME-006"
#   bash scripts/cutover_runtime_006.sh --rollback      # back to the saved Runtime 005 policy
# No Host or webcam change: the webcam shortcut keeps stopping/starting the same service, and the
# ButtonProbe (a child of the service) releases the Windows media keys whenever it is stopped.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
SERVICE=openditoo-product.service; LOCAL=.openditoo-local; POLICY=$LOCAL/product-runtime-policy.json
ROLLBACK=$LOCAL/rollback-runtime-005
restart_and_confirm(){
  systemctl --user restart "$SERVICE"
  for _ in $(seq 1 80); do
    status="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["runtime"]["status"])' 2>/dev/null || true)"
    [[ "$status" == connected ]] && return 0; sleep 0.5
  done
  echo "R006_DASHBOARD_NOT_CONFIRMED status=$status" >&2; return 1
}
if [[ "${1:-}" == "--rollback" ]]; then
  [[ -f "$ROLLBACK/product-runtime-policy.json" ]] || { echo R006_NO_ROLLBACK_SAVED >&2; exit 2; }
  install -m 600 "$ROLLBACK/product-runtime-policy.json" "$POLICY"
  restart_and_confirm && echo R006_ROLLED_BACK_TO_005; exit
fi
[[ "${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-006" ]] || { echo R006_EXACT_GRANT_REQUIRED >&2; exit 2; }
python3 scripts/verify_day1_offline.py
python3 cli/openditoo.py product-check --policy product/OPENDITOO-PRODUCT-RUNTIME-006.json >/dev/null \
  || { echo R006_TEMPLATE_NOT_HASH_VALID >&2; exit 2; }
[[ "$(python3 -c 'import json;print(json.load(open("'$POLICY'"))["authority"]["policy_id"])')" == OPENDITOO-PRODUCT-RUNTIME-005 ]] \
  || { echo R006_CURRENT_POLICY_IS_NOT_005 >&2; exit 2; }
mkdir -p -m 700 "$ROLLBACK"; cp -p "$POLICY" "$ROLLBACK/"; echo R006_ROLLBACK_SAVED
# Young-link guard (webcam launcher trap): do not tear down a seconds-old dashboard connection.
age="$(python3 cli/openditoo.py product-status | python3 -c '
import json, sys, datetime
r = json.load(sys.stdin)["runtime"]; o = r.get("current_session_opened_at")
print(0 if r.get("status") != "connected" or not o else int((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(o.replace("Z", "+00:00"))).total_seconds()))')"
[[ "$age" -lt 30 ]] && { echo "dashboard link ${age}s old; waiting $((30 - age))s"; sleep $((30 - age)); }
python3 - "$1" <<'PY'
import json, os, sys
from pathlib import Path
doc = json.loads(Path("product/OPENDITOO-PRODUCT-RUNTIME-006.json").read_text(encoding="utf-8"))
a = doc["authority"]
assert a["persistent_runtime_authorized"] is False and a["grant_text"] is None, "committed template must stay unauthorized"
a.update({"persistent_runtime_authorized": True, "revoked": False, "grant_text": sys.argv[1],
          "granted_by": "owner, in-session, 2026-09-10", "grant_scope": a["grant_scope_requested"]})
path = Path(".openditoo-local/product-runtime-policy.json"); tmp = path.with_suffix(".tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, indent=1, sort_keys=True)
os.replace(tmp, path)
print("R006_LOCAL_POLICY_WRITTEN")
PY
python3 cli/openditoo.py product-check --policy "$POLICY" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["execution_ready"] and d["runtime_revision"]==3, d' \
  && echo R006_PRODUCT_CHECK_PASS
restart_and_confirm || { echo "rolling back"; install -m 600 "$ROLLBACK/product-runtime-policy.json" "$POLICY"; restart_and_confirm; exit 2; }
python3 cli/openditoo.py product-status | python3 -c '
import json, sys
d = json.load(sys.stdin); p = d.get("pages") or {}
print("R006_DASHBOARD_CONNECTED revision", d["runtime_revision"], "page", p.get("current_page"), "pages", p.get("pages"), "broker_alive", p.get("input_broker_alive"))'
