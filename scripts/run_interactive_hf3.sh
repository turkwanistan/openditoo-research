#!/usr/bin/env bash
# HF-3 one-use physical acceptance coordinator.
# Requires the exact named grant already recorded in the manifest. It suspends Runtime 006,
# gives the Host an 8 s handover settle, runs exactly one outer HF-3 claim, and restores the
# existing Runtime 006 service on every exit path. The Python runner independently rechecks
# Host identity/idle before consuming the irreversible outer claim.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MAIN="$(git worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/main$/{print p; exit}')"
[[ -n "$MAIN" && -d "$MAIN" ]] || { echo HF3_MAIN_WORKTREE_NOT_FOUND >&2; exit 2; }
SERVICE=openditoo-product.service
PRODUCT_WAS_ACTIVE=false
PRODUCT_RESTORED=false

cleanup(){
  rc=$?
  trap - EXIT INT TERM
  if [[ "$PRODUCT_WAS_ACTIVE" == true && "$PRODUCT_RESTORED" != true ]]; then
    echo "HF3 restoring Runtime 006 dashboard..."
    systemctl --user start "$SERVICE" || true
    for _ in $(seq 1 80); do
      state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
      if [[ "$state" == active ]]; then
        PRODUCT_RESTORED=true
        echo HF3_RUNTIME006_SERVICE_RESTORED
        break
      fi
      sleep 0.25
    done
    if [[ "$PRODUCT_RESTORED" == true ]]; then
      connected=false
      for _ in $(seq 1 60); do
        if (cd "$MAIN" && python3 cli/openditoo.py product-status 2>/dev/null | python3 -c '
import json,sys
try: r=json.load(sys.stdin).get("runtime",{})
except Exception: raise SystemExit(1)
raise SystemExit(0 if r.get("status")=="connected" and r.get("last_error") is None else 1)' >/dev/null); then
          connected=true; break
        fi
        sleep 0.5
      done
      if [[ "$connected" == true ]]; then
        echo HF3_RUNTIME006_CONNECTED_RESTORED
      else
        echo HF3_RUNTIME006_CONNECTED_RESTORE_UNCONFIRMED >&2
        [[ "$rc" -ne 0 ]] || rc=3
      fi
    else
      echo HF3_RUNTIME006_SERVICE_RESTORE_FAILED >&2
      [[ "$rc" -ne 0 ]] || rc=3
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

check="$(python3 scripts/interactive_hf3.py check)" || { echo "$check"; exit 2; }
echo "$check" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("execution_ready") else 1)' || {
  echo "$check"
  echo "HF3_NOT_EXECUTION_READY: exact named grant and full installed-byte verification are required; nothing touched" >&2
  exit 2
}

# Preserve the webcam/product lesson: never tear down a seconds-old dashboard connection.
age="$(cd "$MAIN" && python3 cli/openditoo.py product-status 2>/dev/null | python3 -c '
import datetime,json,sys
try: r=json.load(sys.stdin).get("runtime",{}); opened=r.get("current_session_opened_at")
except Exception: print(0); raise SystemExit
if r.get("status") != "connected" or not opened: print(0); raise SystemExit
t=datetime.datetime.fromisoformat(opened.replace("Z","+00:00"))
print(max(0,int((datetime.datetime.now(datetime.timezone.utc)-t).total_seconds())))' 2>/dev/null || echo 0)"
if [[ "$age" =~ ^[0-9]+$ && "$age" -lt 30 ]]; then
  echo "HF3 dashboard link ${age}s old; honoring 30s young-link guard"
  sleep "$((30-age))"
fi

state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
if [[ "$state" == active ]]; then PRODUCT_WAS_ACTIVE=true; fi
[[ "$PRODUCT_WAS_ACTIVE" == true ]] || { echo "HF3_RUNTIME006_NOT_ACTIVE: refusing to change controller state" >&2; exit 2; }

echo "HF3 suspending Runtime 006..."
systemctl --user stop "$SERVICE"
for _ in $(seq 1 80); do
  state="$(systemctl --user is-active "$SERVICE" 2>/dev/null || true)"
  [[ "$state" == inactive ]] && break
  sleep 0.25
done
[[ "$state" == inactive ]] || { echo "HF3_RUNTIME006_STOP_FAILED state=$state" >&2; exit 2; }

echo "HF3 handover settle: 8 s"
sleep 8
cat <<'EOF'
HF3 LIVE CHOREOGRAPHY
  Right -> Slots
  Short lever x3 -> stop left, middle, right reel
  Short lever x1 -> start a new round
  Left -> Dashboard
  Repeat Dashboard <-> Slots until 10 complete cycles are reached.
  On the final Dashboard, cause one genuine MCP activity event and inspect the lightning strike.
  Press Ctrl+C to finish. Long lever holds are NOT mapped and must not be used.
EOF

set +e
python3 scripts/interactive_hf3.py run
rc=$?
set -e
exit "$rc"
