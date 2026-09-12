# OpenDitoo handoff — 2026-09-12 — Runtime 018 live (media-resilient raw AVRCP input)

## State

- **Live: Runtime 018.** Policy `OPENDITOO-PRODUCT-RUNTIME-018`, `runtime_revision=13`, `host/product_runtime_v12.py`. Granted by the owner in-session; main cutover at `f604c32`. Post-cutover `product-check` reports `execution_ready`.
- **Unchanged from Runtime 016:** Dashboard/Slots/Moss pages, Host `3faf520f…`, the `streaming_ack_clock` envelope, pacing, reconnect/reclaim and webcam policy 006. Only the input path differs.
- **Rollback:** Runtime 017 is the exact rollback in `.openditoo-local/rollback-runtime-017`:
  ```bash
  cd .openditoo-local/worktrees/media-avrcp && bash scripts/cutover_runtime_018.sh --rollback
  ```
  Runtime 017 keeps its own elevated task and install root, untouched. The older rollbacks (016 and earlier) are kept.
- **Development branch:** `feat/media-avrcp-input` in the `--relative-paths` worktree `.openditoo-local/worktrees/media-avrcp`. Main and the branch are identical at handoff.
- **Untracked note:** main's `notes/OPENDITOO-FULL-INPUT-TAKEOVER-RESEARCH-2026-09-11.md` is unrelated and deliberately left uncommitted.

## How input works now

1. **Media-key ownership.** `OpenDitoo.ButtonProbe --status playing` is only the SMTC ownership sink, so browser/Windows media never receives Ditoo controls. Its callbacks are lossy, so they are never used as input.
2. **Authoritative input.** A receive-only elevated sidecar runs `OpenDitoo.RawAvrcpBroker` → Microsoft BTVS → tshark (`--disable-protocol btrfcomm/btavctp`, raw `btl2cap.payload`, `-E separator=/t`). It maps inbound AVRCP pass-through **presses** to input: `0x4C` = Left, `0x4B` = Right, `0x44|0x46` = lever. Releases are ignored.
3. **Exact-Ditoo attribution.** The broker learns the Ditoo ACL handle at runtime from OpenDitoo's own outbound image preamble `0103009fa20002` followed by `010400bd31f20002` on one handle. It unbinds on HCI Disconnection Complete. Nothing about the handle or CID is persisted. Presses on any other handle (for example the Tivoo) are logged `ignored_foreign_handle`.
4. **Freshness.** ETW rows captured before the broker started may update binding but never produce input. The broker force-flushes `BTETWRTSession` every 50 ms, which cut latency from ~1.8 s to ~0.1–0.2 s.
5. **Elevation.** BTVS requires elevation, and only the sidecar gets it.
   - It runs through the on-demand, highest-privilege, interactive, `IgnoreNew` scheduled task `OpenDitoo Raw AVRCP Broker 018`.
   - The task launches admin-only copies in `C:\Program Files\OpenDitoo\RawAvrcpBroker018`, with arguments fixed from the policy.
   - The WSL runtime stays unelevated. It runs `/mnt/c/Windows/System32/schtasks.exe /run` (non-blocking, at most once per 5 s) and rewrites a lease counter every second.
   - The broker exits 15 s after the lease stops changing. A Job Object kills BTVS, tshark and the sink with it.
6. **Runtime 018 additions.**
   - BTVS starts hidden and is re-hidden if its window ever appears. Closing that window used to kill the capture.
   - When the broker is capture-ready but unbound for 3 s in a connected session, the runtime does **one** clean session renewal per broker epoch. The new session's first frame rebinds input.
   - `run_product` also gives the capture a bounded head start of up to 8 s before the first session.

## Verified live

- **Runtime 017 receive-only acceptance:** 30/30, then 14/14 through the unelevated task path. Tivoo excluded, latency p50 104–140 ms, media reaction NO, 0 orphans, and the broker exited on its own when the lease stopped. Evidence: `captures/OPENDITOO-R017-RAW-AVRCP-ACCEPTANCE-2026-09-11.json`.
- **Runtime 017 in the product:** owner check with media playing: "everything looks to be working" (16 inputs, 0 gaps, a full Slots round, press to first ACK 17–202 ms).
- **Runtime 018:**
  - BTVS window hidden, both after cutover and after a restart.
  - Simulated sidecar crash (`schtasks /end`): restart at 00:57:15Z, capture ready at 00:57:16Z, one renewal, bound at 00:57:19Z. Status stayed `connected`, with 0 reconnects and 0 reclaims.
- **Offline gates:**
  - Focused suites pass: `tests.test_raw_avrcp_input`, `tests.test_runtime017_raw_avrcp`, `tests.test_runtime018_input_robustness`.
  - `scripts/verify_interactive_pages_offline.py` passes 136/136.
  - The cutover's full Day-1 gate from main passes. In the worktree only the known 13 git-ignored-Host-build failures remain.

## Operating notes

- **After any broker rebuild:** `powershell.exe -File runtime/windows/stage_openditoo_raw_avrcp_broker.ps1 -WslRepositoryPath <worktree>` builds, runs the selftest and prints hashes. Freeze those into a **new successor** policy, then from Administrator PowerShell run `install_openditoo_raw_avrcp_task.ps1 -Runtime NNN`. Each successor gets its own root and task.
- **Read-only checks:**
  - `python3 -m host.raw_avrcp_input verify-task product/OPENDITOO-PRODUCT-RUNTIME-018.json`
  - `python3 cli/openditoo.py product-status`
  - `.openditoo-local/pagination-state.json` has `input_bound`, `input_rebind_renewals` and `inputs_applied`. It is republished on input and session events, so it can lag.
  - The broker event log is private, at `%LOCALAPPDATA%\OpenDitoo\RawAvrcp018\events.ndjson`.
- **Rehearse Windows-helper changes inside `systemd-run --user --wait --pipe`**, not an interactive shell. The service has no Windows `PATH`; the first Runtime 017 cutover crash-looped on a bare `schtasks.exe` and was rolled back.
- **The 017 and 018 sidecars share BTVS port 24353**, so only one can run at a time. The cutover stops the service first.

## Open items (none blocking)

1. **Ditoo power-cycle under Runtime 018:** not yet exercised live. A reconnect opens a new session, whose first frame should rebind.
2. **Lingering trace session:** `BTETWRTSession` outlives a killed BTVS and keeps buffering HCI (privacy/perf). Consider stopping it when the broker exits, in a future successor.
3. **Retire Runtime 017's task and root** once rollback to 017 is no longer wanted. The 018 installer's `-Uninstall` cannot do it, because the 017 policy has no `launch.install_root` and fails the installer's admin-only root check. From Administrator PowerShell:
   ```powershell
   Stop-ScheduledTask -TaskName 'OpenDitoo Raw AVRCP Broker' -EA SilentlyContinue; Unregister-ScheduledTask -TaskName 'OpenDitoo Raw AVRCP Broker' -Confirm:$false; Remove-Item 'C:\Program Files\OpenDitoo\RawAvrcpBroker' -Recurse -Force
   ```
   After this, `scripts/cutover_runtime_018.sh --rollback` would fail its 017 hash check, so only retire it deliberately.
4. **Misleading telemetry:** `broker_starts` counts task run requests (one every 5 s), not broker processes. Cosmetic.
5. **Owner-side trial:** a long session with media playing, Dashboard ↔ Slots ↔ Moss, to confirm there are no stray rebind renewals (`input_rebind_renewals` should stay 0 unless the sidecar restarts).

## Guardrails (unchanged)

- No hard-coded HCI handle or CID.
- The raw-input path is receive-only. No proprietary RFCOMM reports and no SMTC re-arm as input.
- Never commit raw captures or Bluetooth addresses beyond the already-public policy target.
- Never point an elevated task at user-writable paths (`C:\BTP` is Authenticated Users:Modify).
- Every hash-bound change ships as a fresh runtime successor with its own exact grant. Preserve Host/session behavior and the Dashboard/Slots/Moss semantics.
