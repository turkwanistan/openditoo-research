# OpenDitoo MCP Dashboard v1

OpenDitoo MCP Dashboard v1 is the everyday product built from the exact-unit Ditoo research. It displays activity/health for OptiPlex Lab, OptiPlex MCP and WSL MCP on the owner's exact Ditoo Plus.

## Supported unit

- Ditoo Plus: `11:75:58:CE:DE:C7`
- firmware: `v42012`
- RFCOMM channel: 1
- Windows Host: `127.0.0.1:8796`
- Host DLL SHA-256: `fb750078e9f5d8e763e57e2f58d8a79b1faff1d886d2d04946274a29dd9af70f`

This is intentionally exact-unit scoped; it is not a generic Ditoo package.

## Normal behavior

- Windows task `OpenDitoo Product Runtime` starts the WSL product service at user logon / StartWhenAvailable.
- The MCP dashboard owns the display while the product runtime is active.
- A stock screen triggered by a Ditoo button is transient; `canvas_invalidated` causes a fresh bounded session and automatic dashboard restore.
- Device/Host loss uses bounded reconnect backoff: 1, 2, 5, 10, then 30 seconds capped.
- Each Host session remains bounded to 600 seconds, 500 changed frames and 101,500 application bytes, then renews with a fresh session id.
- No raw send, target override, generic Bluetooth, firmware write, command enumeration or pipelining exists in product mode.

## Dashboard legend

- green: usable activity under 5 minutes old
- yellow: 5–20 minutes old
- red: 20+ minutes old while the source remains healthy
- grey: no usable activity timestamp/data
- grey + dim-red crown bar: source unavailable/stale
- activity: three visible cyan/blue/light-blue/cyan sweeps; crown + identity letter + icon accent animate together

## Useful commands

Offline/read-only product policy check:

```sh
python3 cli/openditoo.py product-check --policy .openditoo-local/product-runtime-policy.json
```

Read current supervisor state:

```sh
python3 cli/openditoo.py product-status --policy .openditoo-local/product-runtime-policy.json
```

WSL service status:

```sh
runtime/wsl/install_openditoo_product.sh --status
```

Full offline verification:

```sh
python3 scripts/verify_day1_offline.py
```

## Install / recovery / uninstall

Installer:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\runtime\windows\install_openditoo_product_runtime.ps1 `
  -Apply `
  -WslDistro Ubuntu `
  -WslRepositoryPath /home/wan/Projects/openditoo-research
```

The installer preserves `OpenDitoo Day1 Host` and OpenTivoo, transactionally pauses the standalone activity collector, and rolls back if bootstrap registration/start fails.

Uninstall/revocation is intentionally explicit:

```sh
runtime/wsl/install_openditoo_product.sh --uninstall
```

Uninstall stops/disables the product service, restores the collector's prior state, and revokes/moves the local standing policy. Do not run uninstall just as a test on a working deployment.

## Authority

Committed product templates are always unauthorized. Standing product authority exists only in the git-ignored mode-0600 `.openditoo-local/product-runtime-policy.json` after an explicit grant naming the reviewed runtime revision.

Runtime 001 is the physically accepted baseline. Runtime 002 is the telemetry-only successor: it preserves Runtime 001 transport/device behavior and adds truthful live `connected` / ACK state plus stale-error clearing. Runtime 002 must receive its own explicit grant before replacing the local Runtime 001 policy.

## Known deferred acceptance

A real Windows reboot/login autostart observation is intentionally deferred until convenient. The task is installed and ordinary product start/restart has been accepted, but the project does not claim a physical reboot/login acceptance that has not happened.

See `notes/OPENDITOO-MCP-DASHBOARD-V1-RELEASE-2026-09-09.md` for the release evidence boundary.

## Final product status

- Runtime 002 live acceptance: PASS (`status=connected`, first frame ACKed, stale error cleared).
- MCP Dashboard v1 productization: CLOSED.
- Windows reboot/login autostart observation: deferred, non-blocking.
- Next route: streaming and other OpenDitoo objectives.
