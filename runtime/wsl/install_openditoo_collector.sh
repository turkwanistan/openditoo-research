#!/usr/bin/env bash
# Install, remove or inspect the OpenDitoo collection worker as a systemd user timer.
#
# Collection only. This installs a unit that can run exactly one command --
# `activity-status --collect` -- which reads local audit logs and a remote journal and
# reaches no device. It confers no transmission authority and cannot start a display:
# login, boot and restart all produce zero Bluetooth operations.
#
#   ./install_openditoo_collector.sh            install and start
#   ./install_openditoo_collector.sh --status   show what is installed and running
#   ./install_openditoo_collector.sh --uninstall remove the worker, touch nothing else
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE=openditoo-collect.service
TIMER=openditoo-collect.timer

die() { echo "ERROR: $*" >&2; exit 1; }

command -v systemctl >/dev/null || die "systemctl not found; this needs systemd in WSL (/etc/wsl.conf [boot] systemd=true)"
systemctl --user show-environment >/dev/null 2>&1 || die "no systemd user session"

case "${1:-install}" in
  --status)
    echo "REPO=$REPO"
    echo "UNIT_DIR=$UNIT_DIR"
    for u in "$TIMER" "$SERVICE"; do
      if [ -f "$UNIT_DIR/$u" ]; then echo "INSTALLED=$u"; else echo "ABSENT=$u"; fi
    done
    systemctl --user is-enabled "$TIMER" 2>/dev/null | sed 's/^/ENABLED=/' || true
    systemctl --user is-active  "$TIMER" 2>/dev/null | sed 's/^/ACTIVE=/'  || true
    systemctl --user list-timers --all "$TIMER" --no-pager 2>/dev/null || true
    echo "--- last collected state (no polling) ---"
    python3 "$REPO/cli/openditoo.py" activity-status \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d["display"], indent=1))'
    exit 0
    ;;
  --uninstall)
    systemctl --user disable --now "$TIMER" 2>/dev/null || true
    systemctl --user stop "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT_DIR/$TIMER" "$UNIT_DIR/$SERVICE"
    systemctl --user daemon-reload
    # Deliberately left alone: .openditoo-local (token, source config, cursors,
    # session claims and the Host ledger), captures/, and anything OpenTivoo owns.
    # Uninstalling a poller must never destroy evidence or un-consume authority.
    echo "UNINSTALLED=$TIMER,$SERVICE"
    echo "PRESERVED=.openditoo-local (claims, ledger, cursors, token), captures/, OpenTivoo"
    exit 0
    ;;
  install) ;;
  *) die "unknown argument: $1" ;;
esac

[ -f "$REPO/cli/openditoo.py" ] || die "cannot find the CLI under $REPO"
[ -f "$REPO/.openditoo-local/activity-sources.json" ] \
  || echo "WARNING: activity sources are not configured; the timer will run and report the sources unavailable, which is honest but useless until you configure them." >&2

mkdir -p "$UNIT_DIR"
for u in "$SERVICE" "$TIMER"; do
  sed "s#__REPO__#$REPO#g" "$REPO/runtime/wsl/$u" > "$UNIT_DIR/$u"
done

# Refuse to install a unit that could transmit. The guard is here as well as in the
# test suite because this is the file that actually writes to the user's systemd.
for forbidden in activity-session image-show sequence-run image/show image/sequence session/open; do
  if grep -q -- "$forbidden" "$UNIT_DIR/$SERVICE"; then
    rm -f "$UNIT_DIR/$SERVICE" "$UNIT_DIR/$TIMER"
    die "refusing to install: the unit references '$forbidden'; collection must never transmit"
  fi
done

systemctl --user daemon-reload
systemctl --user enable --now "$TIMER"
echo "INSTALLED=$TIMER"
echo "COLLECTION_ONLY=true TRANSMITS=false"
echo "Run './install_openditoo_collector.sh --status' to inspect, '--uninstall' to remove."
echo
echo "NOTE: a systemd *user* session in WSL starts with your first login shell and ends"
echo "when the distro shuts down. For collection to run without a login shell open, enable"
echo "lingering once:  loginctl enable-linger $USER"
