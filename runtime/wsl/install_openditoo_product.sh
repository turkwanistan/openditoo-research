#!/usr/bin/env bash
# Transactional WSL-side lifecycle for the persistent OpenDitoo product service.
# PREPARE performs no Bluetooth I/O: it validates persistent authority, records/stops the
# old collection timer, installs+enables the product unit, but does NOT start it.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
PRODUCT_SERVICE=openditoo-product.service
COLLECT_SERVICE=openditoo-collect.service
COLLECT_TIMER=openditoo-collect.timer
LOCAL="$REPO/.openditoo-local"
POLICY="$LOCAL/product-runtime-policy.json"
INSTALL_STATE="$LOCAL/product-runtime-install-state.json"

die() { echo "ERROR: $*" >&2; exit 1; }
need_systemd() {
  command -v systemctl >/dev/null || die "systemctl not found; WSL needs systemd enabled"
  systemctl --user show-environment >/dev/null 2>&1 || die "no systemd user session"
}
product_check() {
  python3 "$REPO/cli/openditoo.py" product-check --policy "$POLICY"
}
restore_collector() {
  [ -f "$INSTALL_STATE" ] || return 0
  python3 - "$INSTALL_STATE" <<'PY' | while IFS='=' read -r key value; do
import json,sys
s=json.load(open(sys.argv[1]))
print("ENABLED=" + str(s.get("collector_enabled", "unknown")))
print("ACTIVE=" + str(s.get("collector_active", "unknown")))
PY
    case "$key" in
      ENABLED)
        if [ "$value" = "enabled" ]; then systemctl --user enable "$COLLECT_TIMER" >/dev/null 2>&1 || true
        else systemctl --user disable "$COLLECT_TIMER" >/dev/null 2>&1 || true; fi ;;
      ACTIVE)
        if [ "$value" = "active" ]; then systemctl --user start "$COLLECT_TIMER" >/dev/null 2>&1 || true
        else systemctl --user stop "$COLLECT_TIMER" >/dev/null 2>&1 || true; fi ;;
    esac
  done
}

need_systemd
case "${1:---status}" in
  --status)
    echo "REPO=$REPO"
    echo "POLICY=$POLICY"
    if [ -f "$POLICY" ]; then product_check || true; else echo "POLICY_ABSENT=true"; fi
    systemctl --user is-enabled "$PRODUCT_SERVICE" 2>/dev/null | sed 's/^/PRODUCT_ENABLED=/' || true
    systemctl --user is-active "$PRODUCT_SERVICE" 2>/dev/null | sed 's/^/PRODUCT_ACTIVE=/' || true
    python3 "$REPO/cli/openditoo.py" product-status --policy "$POLICY" || true
    exit 0
    ;;
  --prepare)
    [ -f "$POLICY" ] || die "local persistent product policy is missing: $POLICY"
    mode=$(stat -c '%a' "$POLICY")
    [ "$mode" = "600" ] || die "product policy must be mode 0600; got $mode"
    check="$(product_check)"
    echo "$check"
    python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("execution_ready") is True else 1)' <<<"$check" \
      || die "product policy is not execution-ready"
    mkdir -p "$LOCAL" "$UNIT_DIR"
    if [ ! -f "$INSTALL_STATE" ]; then
      enabled=$(systemctl --user is-enabled "$COLLECT_TIMER" 2>/dev/null || true)
      active=$(systemctl --user is-active "$COLLECT_TIMER" 2>/dev/null || true)
      python3 - "$INSTALL_STATE" "$enabled" "$active" <<'PY'
import json,sys,os
p,e,a=sys.argv[1:]
os.makedirs(os.path.dirname(p), exist_ok=True)
with open(p,'w') as f: json.dump({'collector_enabled':e,'collector_active':a}, f, indent=1)
os.chmod(p,0o600)
PY
    fi
    # One writer owns activity-state cursors. Product runtime collects while connected and
    # while backing off, so the standalone timer must not race it.
    systemctl --user disable --now "$COLLECT_TIMER" >/dev/null 2>&1 || true
    systemctl --user stop "$COLLECT_SERVICE" >/dev/null 2>&1 || true
    sed "s#__REPO__#$REPO#g" "$REPO/runtime/wsl/$PRODUCT_SERVICE" > "$UNIT_DIR/$PRODUCT_SERVICE"
    chmod 600 "$UNIT_DIR/$PRODUCT_SERVICE"
    systemctl --user daemon-reload
    systemctl --user enable "$PRODUCT_SERVICE" >/dev/null
    echo "PRODUCT_PREPARED=true STARTED=false DEVICE_IO=false"
    ;;
  --start)
    check="$(product_check)"; echo "$check"
    python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("execution_ready") is True else 1)' <<<"$check" \
      || die "product policy is not execution-ready"
    [ -f "$UNIT_DIR/$PRODUCT_SERVICE" ] || die "product service is not prepared"
    systemctl --user start "$PRODUCT_SERVICE"
    echo "PRODUCT_START_REQUESTED=true"
    ;;
  --rollback)
    systemctl --user disable --now "$PRODUCT_SERVICE" >/dev/null 2>&1 || true
    rm -f "$UNIT_DIR/$PRODUCT_SERVICE"
    systemctl --user daemon-reload
    restore_collector
    rm -f "$INSTALL_STATE"
    echo "PRODUCT_ROLLBACK=true POLICY_PRESERVED=true"
    ;;
  --uninstall)
    systemctl --user disable --now "$PRODUCT_SERVICE" >/dev/null 2>&1 || true
    rm -f "$UNIT_DIR/$PRODUCT_SERVICE"
    systemctl --user daemon-reload
    restore_collector
    rm -f "$INSTALL_STATE"
    if [ -f "$POLICY" ]; then
      mkdir -p "$LOCAL/revoked"
      stamp=$(date -u +%Y%m%dT%H%M%SZ)
      revoked="$LOCAL/revoked/product-runtime-policy-$stamp.json"
      python3 - "$POLICY" "$revoked" <<'PY'
import json,sys,os
src,dst=sys.argv[1:]
d=json.load(open(src)); a=d.setdefault('authority',{})
a['persistent_runtime_authorized']=False; a['revoked']=True; a['revoked_at']='__NOW__'
from datetime import datetime,timezone
a['revoked_at']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
os.makedirs(os.path.dirname(dst),exist_ok=True)
with open(dst,'w') as f: json.dump(d,f,indent=2); f.write('\n')
os.chmod(dst,0o600); os.unlink(src)
PY
      echo "POLICY_REVOKED_TO=$revoked"
    fi
    echo "PRODUCT_UNINSTALLED=true COLLECTOR_STATE_RESTORED=true"
    ;;
  *) die "usage: $0 --status|--prepare|--start|--rollback|--uninstall" ;;
esac
