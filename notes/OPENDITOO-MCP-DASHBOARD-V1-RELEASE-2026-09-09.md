# OpenDitoo MCP Dashboard v1 — release closure — 2026-09-09

## Release intent

This is the product wrap-up boundary requested by the owner. P2 telemetry cleanup, P3 evidence closure and P4 operating/release packaging are the final MCP-dashboard productization work. After Runtime 002 is explicitly granted/activated and its telemetry is checked once, stop expanding this product milestone and move to streaming/other OpenDitoo objectives.

## Accepted product behavior inherited from Runtime 001

- exact Ditoo Plus `11:75:58:CE:DE:C7`, firmware v42012;
- 16x16 Lab / OptiPlex MCP / WSL MCP dashboard physically accepted;
- real WSL_MCP activity animation physically accepted;
- green/yellow/red/grey production aging physically accepted;
- dim-red fault marker physical display path accepted via Activation 009;
- automatic initial product attach accepted;
- physical stock-screen takeover -> automatic fresh-session dashboard reclaim accepted;
- physical Ditoo power loss -> bounded reconnect -> automatic dashboard return accepted;
- one ACK per changed frame, no pipelining;
- no raw-send/target-selection/generic-Bluetooth/firmware-write surface.

P3 closure is recorded separately in `notes/OPENDITOO-P3-PRODUCT-EVIDENCE-CLOSURE-2026-09-09.md`. A forced outage of a healthy Lab is not required for release.

## P2 — Runtime 002

`product/OPENDITOO-PRODUCT-RUNTIME-002.json` is a committed disabled template. Runtime 002 is side-by-side with Runtime 001 so the currently authorized Runtime 001 remains hash-valid and restart-safe until cutover.

Runtime 002 changes telemetry only:

- persist `status=connected` after a successful Host session open;
- persist per-session ACK count / last ACK time after successful frames;
- clear stale `last_error` and retry delay after a successful reconnect/open;
- retain the same Host DLL and all accepted session/reconnect/reclaim budgets and semantics.

The CLI selects the frozen runtime revision from the policy (`runtime_revision=2` for Runtime 002; absent/1 remains Runtime 001). The installed systemd unit and Windows startup task do not need a new route or task.

## P4 — operating/release package

- `PRODUCT.md` is the concise operator guide.
- `notes/OPENDITOO-MCP-PRODUCT-BASELINE-FREEZE-2026-09-09.md` preserves Runtime 001 acceptance evidence.
- this note is the v1 closure/release boundary;
- `START_HERE.md` routes future sessions to the product guide/release closure before reviving historical milestones.

## Final cutover gate

Runtime 002 is not authorized merely by being implemented. Before cutover:

1. full offline verifier PASS;
2. committed Runtime 002 template `product-check` passes code hashes but remains `execution_ready:false` because committed authority is absent;
3. existing local Runtime 001 policy remains `execution_ready:true` until cutover;
4. obtain explicit operator grant: `Grant OPENDITOO-PRODUCT-RUNTIME-002`;
5. materialize the local mode-0600 policy from the exact reviewed Runtime 002 template, with the exact grant/scope;
6. restart `openditoo-product.service` once;
7. confirm `product-status` reports `runtime_revision=2`, `status=connected`, no stale error, and at least one ACKed frame while the dashboard is visibly healthy.

No additional physical animation/reclaim/reconnect replay is required for a telemetry-only successor unless the cutover produces contradictory behavior.

## Deferred but non-blocking

- Windows reboot/login physical autostart acceptance remains deferred by owner choice.
- A naturally occurring genuine source outage may add evidence later; a forced Lab outage is waived.

Neither blocks the owner's v1 wrap-up.
