#!/usr/bin/env bash
# W10C on-demand webcam: suspend the MCP dashboard, run the Studio under the standing webcam policy
# until the owner closes it, then restore the dashboard. Refuses before touching anything unless the
# local policy (.openditoo-local/webcam-product-policy.json) exists, is granted and hash-valid.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
SERVICE="openditoo-product.service"; PRODUCT_WAS_ACTIVE=false; PRODUCT_RESTORED=false
LOG_DIR=".openditoo-local/webcam-product-log"; LOG="$LOG_DIR/$(date -u +%Y%m%dT%H%M%SZ).json"
restore_product(){
 if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
  echo "Restoring the MCP dashboard..."; systemctl --user start "$SERVICE" || true
  for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)" == active ]] && { PRODUCT_RESTORED=true; echo WEBCAM_DASHBOARD_RESTORED; return 0; }; sleep 0.25; done
  echo WEBCAM_DASHBOARD_RESTORE_FAILED >&2; return 1
 fi
}
trap 'rc=$?; restore_product || true; exit "$rc"' EXIT INT TERM
python3 host/webcam_studio.py policy-check >/dev/null || { python3 host/webcam_studio.py policy-check; echo "WEBCAM_POLICY_NOT_USABLE: nothing was touched" >&2; exit 2; }
echo "OpenDitoo webcam: suspending the MCP dashboard..."
state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == active ]] && PRODUCT_WAS_ACTIVE=true
systemctl --user stop "$SERVICE"
for _ in $(seq 1 40); do state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == inactive ]] && break; sleep 0.25; done
[[ "$state" == inactive ]] || { echo "WEBCAM_DASHBOARD_STOP_FAILED state=$state" >&2; exit 2; }
idle=false
for _ in $(seq 1 40); do
 python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' 2>/dev/null && { idle=true; break; }; sleep 0.25
done
[[ "$idle" == true ]] || { echo WEBCAM_HOST_DID_NOT_BECOME_IDLE >&2; exit 2; }
sleep 8 # handover settle, as in W10-001/002 (see the W9B-006 note)
echo "Opening the Studio window. Close it (or press Stop) to return to the dashboard."
mkdir -p -m 700 "$LOG_DIR"
set +e; python3 host/webcam_studio.py policy-run > "$LOG"; rc=$?; set -e
python3 - "$LOG" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read() or "{}")
for s in d.get("sessions", []):
    print(f"  {s['experimentId']}: {s['outcome']} / {s['terminalReason']}, {s['frames']} frames, {s['ackedTransportFps']:.1f} fps ACKed transport")
print("WEBCAM_RUN", d.get("outcome", "unknown"), d.get("error", ""))
PY
exit "$rc"
