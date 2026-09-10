#!/usr/bin/env bash
# Runtime 004 cutover: deploy the Host build with the separate streaming ceiling, re-bind the
# dashboard policy to it, restore the dashboard. Usage (exact grant text required):
#   bash scripts/cutover_runtime_004.sh "Grant OPENDITOO-PRODUCT-RUNTIME-004"
# Rollback: .openditoo-local/rollback-runtime-003/ holds the previous DLL and local policy; stop the
# product, copy the DLL into %LOCALAPPDATA%\OpenDitoo\Day1Host (task stopped) and the policy back.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
[[ "${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-004" ]] || { echo "R004_EXACT_GRANT_REQUIRED" >&2; exit 2; }
EXPECTED=4a735bab2fafe86001006d8277481b553f41c299e04c31462a72d0f3caf42112
SERVICE=openditoo-product.service; LOCAL=.openditoo-local; ROLLBACK=$LOCAL/rollback-runtime-003
INSTALLED=/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo/Day1Host/OpenDitoo.Day1.Host.dll
REPO_DLL=runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0/OpenDitoo.Day1.Host.dll
python3 scripts/verify_day1_offline.py
[[ "$(python3 -c 'import json;print(json.load(open("'$LOCAL'/product-runtime-policy.json"))["authority"]["policy_id"])')" == OPENDITOO-PRODUCT-RUNTIME-003 ]] \
  || { echo R004_CURRENT_POLICY_IS_NOT_003 >&2; exit 2; }
mkdir -p -m 700 "$ROLLBACK"
cp -p "$LOCAL/product-runtime-policy.json" "$ROLLBACK/"; cp -p "$INSTALLED" "$ROLLBACK/"
echo "R004_ROLLBACK_SAVED $(sha256sum "$ROLLBACK/OpenDitoo.Day1.Host.dll" | cut -c1-16)"
systemctl --user stop "$SERVICE"
for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" || true)" == inactive ]] && break; sleep 0.25; done
python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' && echo R004_HOST_IDLE
# The refresh script stages, backs up, swaps and rolls itself back if the typed identity gate fails.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w runtime/windows/refresh_openditoo_day1_host.ps1)" -Apply | tr -d '\r'
for f in "$INSTALLED" "$REPO_DLL"; do
  [[ "$(sha256sum "$f" | cut -c1-64)" == "$EXPECTED" ]] || { echo "R004_HOST_HASH_MISMATCH $f — dashboard left stopped; see rollback" >&2; exit 2; }
done
echo R004_HOST_DEPLOYED "$EXPECTED"
python3 - <<'PY'
import json, os
from pathlib import Path
doc = json.loads(Path("product/OPENDITOO-PRODUCT-RUNTIME-004.json").read_text(encoding="utf-8"))
a = doc["authority"]
assert a["persistent_runtime_authorized"] is False and a["grant_text"] is None, "committed template must stay unauthorized"
a.update({"persistent_runtime_authorized": True, "revoked": False, "grant_text": "Grant OPENDITOO-PRODUCT-RUNTIME-004",
          "granted_by": "operator, in-session, 2026-09-10", "grant_scope": a["grant_scope_requested"]})
path = Path(".openditoo-local/product-runtime-policy.json")
tmp = path.with_suffix(".tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, indent=2, sort_keys=True)
os.replace(tmp, path)
print("R004_LOCAL_POLICY_WRITTEN")
PY
python3 cli/openditoo.py product-check --policy "$LOCAL/product-runtime-policy.json" >/dev/null && echo R004_PRODUCT_CHECK_PASS
systemctl --user start "$SERVICE"
for _ in $(seq 1 80); do
  status="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["runtime"]["status"])' 2>/dev/null || true)"
  [[ "$status" == connected ]] && { echo R004_DASHBOARD_CONNECTED; exit 0; }; sleep 0.5
done
echo "R004_DASHBOARD_NOT_CONFIRMED status=$status" >&2; exit 2
