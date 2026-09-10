#!/usr/bin/env bash
# BTN-5: the one-use physical pagination acceptance (OPENDITOO-PAGINATION-ACCEPTANCE-001).
# Suspends the Runtime 005 dashboard, starts the receive-only ButtonProbe, runs the two-page
# router for at most 300 s, then stops the probe and restores Runtime 005. Refuses before
# touching anything unless the local policy is granted, hash-valid and unconsumed.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
SERVICE="openditoo-product.service"; PRODUCT_WAS_ACTIVE=false; PRODUCT_RESTORED=false; PROBE_PID=""
LOG_DIR=".openditoo-local/pagination-log"; STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVENTS=".openditoo-local/button-events.ndjson"
PROBE='/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo/ButtonProbe/OpenDitoo.ButtonProbe.exe'
EVENTS_WIN="$(wslpath -w "$REPO/$EVENTS")"
cleanup(){
 if [[ -n "$PROBE_PID" ]]; then
  powershell.exe -NoProfile -Command "Stop-Process -Id $PROBE_PID -ErrorAction SilentlyContinue" || true
  echo "ButtonProbe $PROBE_PID stopped"
 fi
 if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
  echo "Restoring the Runtime 005 dashboard..."; systemctl --user start "$SERVICE" || true
  for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)" == active ]] && { PRODUCT_RESTORED=true; echo PAGINATION_DASHBOARD_RESTORED; return 0; }; sleep 0.25; done
  echo PAGINATION_DASHBOARD_RESTORE_FAILED >&2; return 1
 fi
}
trap 'rc=$?; cleanup || true; exit "$rc"' EXIT INT TERM
python3 host/pagination.py policy-check >/dev/null || { python3 host/pagination.py policy-check; echo "PAGINATION_POLICY_NOT_USABLE: nothing was touched" >&2; exit 2; }
# Same young-link guard as the webcam launcher: never tear down a seconds-old dashboard connection.
age="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c '
import json, sys, datetime
r = json.load(sys.stdin)["runtime"]; opened = r.get("current_session_opened_at")
if r.get("status") != "connected" or not opened: print(0); raise SystemExit
t = datetime.datetime.fromisoformat(opened.replace("Z", "+00:00"))
print(int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()))' 2>/dev/null || echo 0)"
if [[ "$age" =~ ^[0-9]+$ && "$age" -lt 30 ]]; then echo "Dashboard link ${age}s old; waiting $((30 - age))s"; sleep $((30 - age)); fi
echo "Suspending the Runtime 005 dashboard..."
state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == active ]] && PRODUCT_WAS_ACTIVE=true
systemctl --user stop "$SERVICE"
for _ in $(seq 1 40); do state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"; [[ "$state" == inactive ]] && break; sleep 0.25; done
[[ "$state" == inactive ]] || { echo "PAGINATION_DASHBOARD_STOP_FAILED state=$state" >&2; exit 2; }
idle=false
for _ in $(seq 1 40); do python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' 2>/dev/null && { idle=true; break; }; sleep 0.25; done
[[ "$idle" == true ]] || { echo PAGINATION_HOST_DID_NOT_BECOME_IDLE >&2; exit 2; }
sleep 8 # handover settle, as in W10
mkdir -p -m 700 "$LOG_DIR"; touch "$EVENTS"; chmod 600 "$EVENTS"
lines_before="$(wc -l < "$EVENTS")"
"$PROBE" --seconds 420 --log "$EVENTS_WIN" > "$LOG_DIR/$STAMP-probe.ndjson" 2>&1 &
for _ in $(seq 1 40); do
 PROBE_PID="$(tail -n +"$((lines_before + 1))" "$EVENTS" | python3 -c '
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    if r.get("type") == "probe_started" and r["smtc"].get("acquired"): print(r["pid"]); break' 2>/dev/null || true)"
 [[ -n "$PROBE_PID" ]] && break; sleep 0.25
done
[[ -n "$PROBE_PID" ]] || { echo PAGINATION_BUTTON_PROBE_NOT_READY >&2; exit 2; }
echo "ButtonProbe $PROBE_PID ready. Pagination live for up to 300 s: Right -> animation, Left -> dashboard."
set +e; python3 cli/openditoo.py pagination-run > "$LOG_DIR/$STAMP-result.json"; rc=$?; set -e
python3 - "$LOG_DIR/$STAMP-result.json" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read() or "{}")
for t in d.get("transitions", []):
    print(f"  {t['raw_button']} seq {t['seq']}: {t['from']} -> {t['to']}, first ACK {t['first_ack_ms']} ms")
r = d.get("runtime", {})
print("PAGINATION_RUN", d.get("ok"), d.get("error_code", ""), "final_page", d.get("final_page"),
      "reclaims", r.get("reclaims"), "reconnects", r.get("reconnects"), "gaps", d.get("input_gaps"))
PY
exit "$rc"
