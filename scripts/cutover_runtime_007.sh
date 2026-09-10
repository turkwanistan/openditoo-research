#!/usr/bin/env bash
# Runtime 007 + webcam 006 cutover: install the first-frame-spacing Host, re-bind the dashboard
# (Runtime 006 -> 007, Host binding only) and the on-demand webcam (005 -> 006), restore the dashboard.
#   bash scripts/cutover_runtime_007.sh "Grant OPENDITOO-PRODUCT-RUNTIME-007" "Grant OPENDITOO-WEBCAM-PRODUCT-006"
#   bash scripts/cutover_runtime_007.sh --rollback     # exact bytes back: Runtime 006 + webcam 005
# Run it from the feat/host-first-frame-spacing worktree. It acts on the MAIN checkout (where the
# service runs): after the grants and a Host-idle check it fast-forwards main to this branch.
set -euo pipefail
BRANCH=feat/host-first-frame-spacing
HOST_EXPECTED=3faf520f46ce824970f583c3d932e0168484b0f6ffa5975e6b38e77330c4900f
HOST_OLD=f7bd60d4a56de4f4740bd84f7c645e201ddfd7ce29bf6c0f1e7512b1b67cd34e
SERVICE=openditoo-product.service
WIN=/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$(git -C "$HERE" worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/main$/{print p; exit}')"
[[ -n "$MAIN" && -d "$MAIN" ]] || { echo R007_MAIN_NOT_FOUND >&2; exit 2; }
cd "$MAIN"
LOCAL=.openditoo-local; POLICY=$LOCAL/product-runtime-policy.json; WEBCAM=$LOCAL/webcam-product-policy.json
RB=$LOCAL/rollback-runtime-006
HOST_BIN=runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0
STUDIO_BIN=runtime/windows/OpenDitoo.Webcam.Studio/bin/Release/net8.0-windows10.0.19041.0

policy_id(){ python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["authority"]["policy_id"])' "$1"; }
stop_service(){
  systemctl --user stop "$SERVICE"
  for _ in $(seq 1 40); do [[ "$(systemctl --user is-active "$SERVICE" || true)" == inactive ]] && return 0; sleep 0.25; done
  echo R007_SERVICE_STOP_FAILED >&2; return 1
}
start_and_confirm(){
  systemctl --user start "$SERVICE"
  for _ in $(seq 1 80); do
    r="$(python3 cli/openditoo.py product-status 2>/dev/null | python3 -c 'import json,sys;r=json.load(sys.stdin)["runtime"];print(r["status"], r["last_error"] is None)' 2>/dev/null || true)"
    [[ "$r" == "connected True" ]] && return 0; sleep 0.5
  done
  echo "R007_DASHBOARD_NOT_CONFIRMED $r" >&2; return 1
}
# Copy a saved Host directory into the installed runtime with the Host task stopped (a running exe
# cannot be overwritten), then require the typed identity again.
install_host_dir(){
  powershell.exe -NoProfile -Command "\$ErrorActionPreference='Stop'; \$exe=Join-Path \$env:LOCALAPPDATA 'OpenDitoo\\Day1Host\\OpenDitoo.Day1.Host.exe'; Stop-ScheduledTask -TaskName 'OpenDitoo Day1 Host'; Get-Process OpenDitoo.Day1.Host -ErrorAction SilentlyContinue | Where-Object { \$_.Path -ieq \$exe } | ForEach-Object { Stop-Process -Id \$_.Id; if (-not \$_.WaitForExit(8000)) { throw 'OWNED_HOST_DID_NOT_EXIT' } }; Copy-Item -Path '$(wslpath -w "$1")\\*' -Destination (Join-Path \$env:LOCALAPPDATA 'OpenDitoo\\Day1Host') -Recurse -Force; Start-ScheduledTask -TaskName 'OpenDitoo Day1 Host'" | tr -d '\r'
  for _ in $(seq 1 40); do python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' 2>/dev/null && return 0; sleep 0.25; done
  echo R007_HOST_IDENTITY_NOT_CONFIRMED >&2; return 1
}

if [[ "${1:-}" == "--rollback" ]]; then
  [[ -f "$RB/pre_commit" && -f "$RB/product-runtime-policy.json" ]] || { echo R007_NO_ROLLBACK_SAVED >&2; exit 2; }
  stop_service
  pre="$(cat "$RB/pre_commit")"
  [[ "$(git rev-parse HEAD)" == "$pre" ]] || git revert --no-edit "$pre..HEAD"
  rm -rf "$HOST_BIN" "$STUDIO_BIN"; mkdir -p "$(dirname "$HOST_BIN")" "$(dirname "$STUDIO_BIN")"
  cp -a "$RB/host-bin" "$HOST_BIN"; cp -a "$RB/studio-bin" "$STUDIO_BIN"
  install_host_dir "$RB/installed-host"
  cp -a "$RB/installed-studio/." "$WIN/WebcamStudio/"
  [[ "$(sha256sum "$WIN/Day1Host/OpenDitoo.Day1.Host.dll" | cut -c1-64)" == "$HOST_OLD" ]] || { echo R007_ROLLBACK_HOST_HASH >&2; exit 2; }
  install -m 600 "$RB/product-runtime-policy.json" "$POLICY"
  [[ -f "$RB/webcam-product-policy.json" ]] && install -m 600 "$RB/webcam-product-policy.json" "$WEBCAM"
  start_and_confirm && echo R007_ROLLED_BACK_TO_RUNTIME_006
  [[ -f "$WEBCAM" ]] && python3 host/webcam_studio.py policy-check >/dev/null && echo R007_ROLLBACK_WEBCAM_005_POLICY_CHECK_PASS
  exit 0
fi

[[ "${1:-}" == "Grant OPENDITOO-PRODUCT-RUNTIME-007" ]] || { echo R007_EXACT_GRANT_REQUIRED >&2; exit 2; }
[[ "${2:-}" == "Grant OPENDITOO-WEBCAM-PRODUCT-006" ]] || { echo R007_EXACT_WEBCAM_GRANT_REQUIRED >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo R007_MAIN_HAS_TRACKED_CHANGES >&2; exit 2; }
git merge-base --is-ancestor HEAD "$BRANCH" || { echo R007_BRANCH_NOT_FAST_FORWARD >&2; exit 2; }
[[ "$(policy_id "$POLICY")" == OPENDITOO-PRODUCT-RUNTIME-006 ]] || { echo R007_CURRENT_POLICY_IS_NOT_006 >&2; exit 2; }
[[ ! -f "$WEBCAM" || "$(policy_id "$WEBCAM")" == OPENDITOO-WEBCAM-PRODUCT-005 ]] || { echo R007_CURRENT_WEBCAM_IS_NOT_005 >&2; exit 2; }
[[ "$(sha256sum "$WIN/Day1Host/OpenDitoo.Day1.Host.dll" | cut -c1-64)" == "$HOST_OLD" ]] || { echo R007_INSTALLED_HOST_NOT_006 >&2; exit 2; }

# Young-link guard (webcam launcher lesson): do not tear down a seconds-old dashboard connection.
age="$(python3 cli/openditoo.py product-status | python3 -c '
import json, sys, datetime
r = json.load(sys.stdin)["runtime"]; o = r.get("current_session_opened_at")
print(0 if r.get("status") != "connected" or not o else int((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(o.replace("Z", "+00:00"))).total_seconds()))')"
[[ "$age" -lt 30 ]] && { echo "dashboard link ${age}s old; waiting $((30 - age))s"; sleep $((30 - age)); }

rm -rf "$RB"; mkdir -p -m 700 "$RB"
git rev-parse HEAD > "$RB/pre_commit"
cp -p "$POLICY" "$RB/"; [[ -f "$WEBCAM" ]] && cp -p "$WEBCAM" "$RB/"
cp -a "$HOST_BIN" "$RB/host-bin"; cp -a "$STUDIO_BIN" "$RB/studio-bin"
cp -a "$WIN/Day1Host" "$RB/installed-host"; cp -a "$WIN/WebcamStudio" "$RB/installed-studio"
echo "R007_ROLLBACK_SAVED pre=$(cut -c1-12 "$RB/pre_commit")"

stop_service
python3 -c 'from host import webcam_trial; webcam_trial._host_preclaim_status()' \
  || { echo R007_HOST_NOT_IDLE >&2; systemctl --user start "$SERVICE"; exit 2; }
echo R007_HOST_IDLE
rollback_now(){ echo "R007_FAILED: $1 -- rolling back" >&2; bash "$HERE/scripts/cutover_runtime_007.sh" --rollback; exit 2; }

git merge --ff-only "$BRANCH" >/dev/null && echo "R007_MAIN_FAST_FORWARDED $(git rev-parse --short HEAD)"
# Fresh builds so nothing stale survives the csproj/PathMap change.
rm -rf runtime/windows/OpenDitoo.Day1.Host/obj runtime/windows/OpenDitoo.Day1.Host/bin \
       runtime/windows/OpenDitoo.Webcam.Studio/obj runtime/windows/OpenDitoo.Webcam.Studio/bin
# The refresh script publishes from main, swaps, gates on typed identity and rolls itself back.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w runtime/windows/refresh_openditoo_day1_host.ps1)" -Apply | tr -d '\r' \
  || rollback_now HOST_REFRESH
for f in "$WIN/Day1Host/OpenDitoo.Day1.Host.dll" "$HOST_BIN/OpenDitoo.Day1.Host.dll"; do
  [[ "$(sha256sum "$f" | cut -c1-64)" == "$HOST_EXPECTED" ]] || rollback_now "HOST_HASH $f"
done
echo "R007_HOST_DEPLOYED $HOST_EXPECTED"
# Rebuild the Studio from main now (deterministic; must equal the frozen webcam 006 hashes) so the
# offline gate below sees real binaries; it is installed only after the dashboard is back.
powershell.exe -NoProfile -Command "dotnet build '$(wslpath -w runtime/windows/OpenDitoo.Webcam.Studio/OpenDitoo.Webcam.Studio.csproj)' -c Release --nologo -v q; if (\$LASTEXITCODE) { throw 'BUILD' }" | tr -d '\r' \
  || rollback_now STUDIO_BUILD
python3 -c 'from host import webcam_studio as w; w.load_policy(w.POLICY_TEMPLATE, authority=False, verify=False); import json; h=json.load(open(w.POLICY_TEMPLATE))["build"]["producer_code_sha256"]
from host import activity_session as a; bad=[p for p in w.producer_binaries() if a.sha256_file(p)!=h[str(p.relative_to(w.ROOT))]]
raise SystemExit("STUDIO_BUILD_HASH_DRIFT %s" % bad if bad else 0)' || rollback_now STUDIO_HASH
echo R007_STUDIO_BUILT
# The full offline gate runs HERE, in main (it needs main's local claim/evidence state), against the
# merged source and the deployed Host, before the dashboard restarts. Any failure rolls back.
python3 scripts/verify_day1_offline.py > "$RB/offline-gate.log" 2>&1 || { tail -20 "$RB/offline-gate.log" >&2; rollback_now OFFLINE_GATE; }
echo R007_MAIN_OFFLINE_PASS

python3 - "$1" <<'PY' || rollback_now LOCAL_POLICY
import json, os, sys
from pathlib import Path
doc = json.loads(Path("product/OPENDITOO-PRODUCT-RUNTIME-007.json").read_text(encoding="utf-8"))
a = doc["authority"]
assert a["persistent_runtime_authorized"] is False and a["grant_text"] is None, "committed template must stay unauthorized"
a.update({"persistent_runtime_authorized": True, "revoked": False, "grant_text": sys.argv[1],
          "granted_by": "owner, in-session", "grant_scope": a["grant_scope_requested"]})
path = Path(".openditoo-local/product-runtime-policy.json"); tmp = path.with_suffix(".tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, indent=1, sort_keys=True)
os.replace(tmp, path)
print("R007_LOCAL_POLICY_WRITTEN")
PY
python3 cli/openditoo.py product-check --policy "$POLICY" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["execution_ready"] and d["runtime_revision"]==3, d' \
  && echo R007_PRODUCT_CHECK_PASS || rollback_now PRODUCT_CHECK
start_and_confirm || rollback_now DASHBOARD_NOT_CONNECTED
echo R007_DASHBOARD_CONNECTED

# Webcam: install the Studio built above, then swap the local policy 005 -> 006.
cp -a "$STUDIO_BIN/." "$WIN/WebcamStudio/"
[[ -f "$WEBCAM" ]] && python3 host/webcam_studio.py policy-revoke
python3 host/webcam_studio.py policy-grant --grant-text "$2" --granted-by "owner, in-session" || rollback_now WEBCAM_GRANT
python3 host/webcam_studio.py policy-check >/dev/null && echo R007_WEBCAM_006_POLICY_CHECK_PASS || rollback_now WEBCAM_POLICY_CHECK
echo "R007_CUTOVER_PASS main=$(git rev-parse --short HEAD) host=${HOST_EXPECTED:0:12} rollback=$RB"
