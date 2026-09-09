# OpenDitoo persistent MCP product runtime — hardening / activation handoff

## Accepted prerequisite

Activation 008 physically accepted the production status state machine on the exact Ditoo Plus: four ACKed frames, green → yellow → red → grey, operator-confirmed. Production thresholds were not shortened; the acceptance renderer only accelerated the test clock. Activations 001–008 are consumed.

## Product objective

After Windows user logon, no terminal or manual WSL command should be required. The MCP dashboard should appear whenever the exact paired Ditoo is available. If the device is off/disconnected, the runtime should wait and reconnect when it returns. If a physical input temporarily takes the display to stock UI, OpenDitoo should restore the current MCP dashboard automatically.

The operator explicitly does not want stock UI to retain display ownership while OpenDitoo is active.

## Architecture chosen

Do **not** add a new Bluetooth implementation or generic Host route. Reuse the already-accepted `/v1/session/open|frame|heartbeat|close` engine and its exact-target guard, Host ledger, one-ACK-per-frame semantics, 150 ms Host floor, 10 ms packet spacing and single-operation gate.

`Windows logon -> OpenDitoo Product Runtime scheduled task -> wsl.exe -> openditoo-product.service -> product-runtime supervisor -> existing typed Host activity sessions -> exact Ditoo`

The supervisor creates a globally unique experiment/session epoch ID for every bounded connection. Host ledger evidence therefore remains attributable even though the product is unattended.

## Runtime behavior

- Session lifetime: 600 s; automatic clean renewal.
- Per-session ceiling: 500 changed frames / 101,500 application bytes.
- Render tick: 50 ms; nominal changed-frame dispatch remains 200 ms; Host floor remains 150 ms.
- Bluetooth/Host/device failure: fresh session ID after bounded 1, 2, 5, 10, then 30 s capped backoff.
- `canvas_invalidated`: no failure backoff; immediately open a fresh bounded session and paint current MCP state.
- Reclaim storm guard: after more than 8 takeovers in 10 s, add a 1 s cooldown rather than spin tightly on a stuck/noisy input.
- Shutdown/SIGTERM: runner notices supervisor stop and closes the active Host session cleanly.
- Source collection continues during reconnect backoff, so the first frame after device return is current.

## Startup / ownership

Existing task `OpenDitoo Day1 Host` remains untouched. Existing `OpenTivoo Product Runtime` is observed/preserved only.

New task: `OpenDitoo Product Runtime`, current-user **AtLogOn + StartWhenAvailable**, runs only the WSL product start helper. WSL is user-scoped, so user logon is the reliable Windows startup boundary; pre-login machine boot is deliberately not claimed.

WSL service: `openditoo-product.service`, `Restart=on-failure`, `SIGTERM`, `NoNewPrivileges`, `UMask=0077`, no `PrivateTmp` (known to break the SSH-backed sources).

The old `openditoo-collect.timer` is a separate cursor writer. Product PREPARE records its prior enabled/active state and stops it before product service ownership begins. Rollback/uninstall restores that exact prior state.

## Persistent authority model

Committed template: `product/OPENDITOO-PRODUCT-RUNTIME-001.json`.

**The committed template must remain disabled forever.** Standing authorization is local only: `.openditoo-local/product-runtime-policy.json`, mode `0600`, materialized after an explicit operator grant naming `OPENDITOO-PRODUCT-RUNTIME-001`.

The local policy freezes exact MAC/firmware, code hashes, installed Host DLL hash, reconnect/reclaim behavior, startup task/service, and prohibitions. `product-runtime` recalculates these hashes at startup and fails closed if source changed after approval.

Uninstall stops/disables the service, removes only the owned Windows product task, restores collector state, marks authority revoked, and moves the local policy record under `.openditoo-local/revoked/`.

Persistent authority grants only this exact product loop. It does **not** authorize `image-show`, arbitrary sequences, raw send, target override, generic Bluetooth, firmware/persistent device writes, command enumeration or pipelining.

## Transactional install path

1. Materialize the explicitly granted local 0600 policy from the frozen committed template.
2. `product-check`: must report `execution_ready:true` with matching code/Host hashes. No device I/O.
3. WSL `--prepare`: record/stop standalone collector, install+enable product service, **do not start it**. No device I/O.
4. Register the owned Windows logon task.
5. Start the task/service. This is the first point that persistent product authority may cause device I/O.
6. If registration/startup fails, remove only the owned product task/unit and restore the collector state.

Windows orchestration: `runtime/windows/install_openditoo_product_runtime.ps1`.
WSL lifecycle: `runtime/wsl/install_openditoo_product.sh`.

## Live acceptance after persistent grant

Do not claim plug-and-play complete until all are observed:

1. **Initial attach** — with Ditoo available, product service reaches MCP dashboard without a manual activity-session command.
2. **Input reclaim** — press brightness/M/etc.; stock may flash briefly, then MCP dashboard returns automatically without operator command.
3. **Disconnect/reconnect** — power off/disconnect Ditoo, verify bounded waiting; power it back on and verify dashboard returns automatically.
4. **Source activity** — generate a real MCP event and confirm normal three-sweep animation still works in product mode.
5. **Status aging** — no regression from 008 production threshold semantics.
6. **Windows startup** — log out/reboot and log back in; Host and product bootstrap start, WSL service becomes active, Ditoo dashboard returns without a terminal.
7. **Uninstall/rollback** — structural/offline checks remain mandatory; do not exercise uninstall against the live product merely to prove it unless the operator asks.

## Current state

Implementation is frozen at the reviewed product boundary. The committed product policy remains disabled. **Persistent authority `OPENDITOO-PRODUCT-RUNTIME-001` is now granted only through the local mode-0600 `.openditoo-local/product-runtime-policy.json`, and `product-check` reports `execution_ready:true`.** `scripts/verify_day1_offline.py` must remain PASS before install/start.

### Persistent product runtime live acceptance — initial attach + stock reclaim — 2026-09-09

`OPENDITOO-PRODUCT-RUNTIME-001` is now installed under its local mode-0600 persistent policy. Windows installer reported `PRODUCT_SERVICE=ACTIVE`, `WINDOWS_STARTUP=AT_LOGON_START_WHEN_AVAILABLE`, and `INSTALL_STATUS=PASS_PRODUCT_RUNTIME`; the committed policy template remains disabled. The dashboard became physically visible without a manual activity-session invocation, so automatic initial attach is **PASS**.

Physical reclaim is also **PASS**. The operator pressed brightness once; the Ditoo briefly showed the stock clock and then automatically returned to the MCP dashboard. Runtime telemetry recorded `canvas_invalidated / stopped_yielded_to_stock`, `reclaims=1`, `reconnects=0`, `connected_sessions=1`, and advanced from product session `...000001` to `...000002`, proving this was immediate stock-screen reclaim rather than disconnect backoff.

Known observability defect: while a bounded product session is actively running, `product-status` remains at `status=connecting` because the supervisor persists that state before entering `run_session()` and receives no mid-session callback after Host open/first ACK. This is telemetry-only: physical display plus Host/session evidence prove attach/reclaim. Do not modify the hash-frozen live runtime in place; fix under a fresh reviewed product revision after live acceptance of reconnect/startup.

### Persistent product reconnect acceptance — 2026-09-09

Physical device power-cycle reconnect is **PASS** under `OPENDITOO-PRODUCT-RUNTIME-001`. With the Windows product service left running (same `run_nonce` `2066c485`, same `started_at`), the Ditoo was powered off long enough to force reconnect backoff and then powered on again. The MCP dashboard returned automatically with no Windows intervention. Runtime evidence after recovery: `connected_sessions=2`, `reconnects=4`, `session_sequence=6`; one failed epoch recorded `open_failed` / HTTP 502 before later recovery. Because the runtime state file is only persisted at session boundaries, live `status=connecting` and `last_error` may remain stale while a later session is visibly healthy; this is an observability defect, not a reconnect failure, and must be corrected only in a new hash-frozen product revision after startup acceptance.

