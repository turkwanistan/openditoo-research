# OpenDitoo MCP dashboard — locked product baseline — 2026-09-09

## Status

This note freezes the accepted OpenDitoo MCP dashboard/product baseline after Activations 001–009 and the first persistent product-runtime acceptance cycle. The live repository remains authoritative; this file is the concise routing record for what is accepted, what remains intentionally pending, and what must not be silently changed.

## Frozen product identity

- Product: `OPENDITOO-MCP-DASHBOARD-V1`
- Standing authority: `OPENDITOO-PRODUCT-RUNTIME-001`
- Exact unit: `11:75:58:CE:DE:C7`
- Installed firmware: `v42012`
- RFCOMM channel: 1
- Host: `127.0.0.1:8796`
- Host DLL SHA-256: `fb750078e9f5d8e763e57e2f58d8a79b1faff1d886d2d04946274a29dd9af70f`
- Local standing policy: `.openditoo-local/product-runtime-policy.json`, mode 0600, git-ignored
- Committed product template: `product/OPENDITOO-PRODUCT-RUNTIME-001.json`, intentionally and permanently disabled in Git

`product-check` reports `execution_ready:true`; no product authority blocker is present. Standing authority persists until explicit uninstall/revocation and remains limited to the exact frozen product loop.

## Accepted visual/product behavior

### Dashboard layout and activity

- 16x16 MCP dashboard layout is physically accepted.
- Columns: Lab mushroom + L; OptiPlex MCP bunny + O; WSL MCP skull + W.
- A qualifying source event animates that source's crown + letter + icon accent together.
- Three visible cyan/blue/light-blue/cyan sweeps are the accepted activity program; duplicate cyan boundaries collapse to 10 distinct ACK-gated frames at the nominal 200 ms client cadence (~2 s total).
- A genuine WSL_MCP audit event physically triggered the skull animation in Activation 007.

### Status aging

Activation 008 physically accepted the complete production state machine:

- green: usable activity <5 minutes old
- yellow: 5–20 minutes old
- red: >=20 minutes old while source data remains usable
- grey: no usable activity timestamp/data

Production thresholds were not changed by the accelerated acceptance profile.

### Source-health fault marker

Activation 009 physically accepted the production renderer's fault marker on the exact Ditoo:

- healthy Lab with no usable activity history: grey, no fault bar
- simulated `source_health=unavailable`: grey + three-pixel dim-red bar in the top/crown row
- restored healthy state: grey, no fault bar

This proves the renderer + wire + physical-display path. It is deliberately labeled **simulated source-health acceptance**; a genuine Lab outage has not been used as end-to-end detection evidence.

### Product ownership / reclaim

Persistent runtime initial attach is physically accepted: after installation, the MCP dashboard became visible without a manual `activity-session` command.

Physical stock takeover/reclaim is accepted: brightness briefly opened the stock clock, Host/session telemetry reported `canvas_invalidated / stopped_yielded_to_stock`, and the persistent supervisor immediately opened a new bounded epoch and restored the MCP dashboard. Evidence: `reclaims=1`, `reconnects=0`, product session sequence advanced from `...000001` to `...000002`.

### Device loss / reconnect

Physical Ditoo power-cycle recovery is accepted. With the same persistent supervisor process still running, device loss caused bounded reconnect attempts; after power-on the dashboard returned automatically with no Windows intervention. Evidence included `reconnects=4`, `connected_sessions=2`, `session_sequence=6`, and an intermediate `open_failed` / HTTP 502 before successful recovery.

## Product runtime invariants

- 600 s bounded Host sessions with clean renewal
- max 500 changed frames / 101,500 application bytes per bounded session
- Host frame-start floor 150 ms; nominal MCP changed-frame cadence 200 ms; 50 ms render tick
- reconnect backoff: 1, 2, 5, 10, then 30 s capped
- `canvas_invalidated` uses immediate fresh-session reclaim, not failure backoff
- reclaim-storm guard: >8 takeovers in 10 s adds a 1 s cooldown
- exact-target only
- one controller at a time
- one ACK per changed frame
- no raw send
- no target override
- no generic Bluetooth surface
- no firmware/persistent device writes
- no command enumeration
- no pipelining
- OpenTivoo remains isolated/preserved

## Known accepted limitation — telemetry only

`product-status` can show `status=connecting` while a bounded product session is visibly healthy, and `last_error` can remain stale from an earlier failed epoch. The supervisor persists state before entering `run_session()` and currently has no mid-session callback after Host open/first frame ACK. Physical attach/reclaim/reconnect evidence proves this is an observability defect, not a transport failure.

**Do not patch the hash-frozen live runtime in place.** Any observability improvement must be a separately reviewed/frozen product revision with corresponding local-policy hash refresh/authority handling.

## Intentionally pending acceptance

The only major plug-and-play acceptance intentionally deferred by the operator is **Windows reboot/logon autostart**. The scheduled task is installed as `OpenDitoo Product Runtime` with current-user `AtLogOn + StartWhenAvailable`, but a real Windows reboot/login has not yet been physically accepted because the operator is doing other work.

Do not claim full Windows-startup acceptance until the operator reboots/logs in and observes the dashboard returning without manually opening WSL or starting the runtime.

A genuine source outage is also not end-to-end accepted; only the fault-bar visual path is physically accepted via Activation 009.

## Consumed one-shot authority

Activations 001–009 are historical one-shot experiments and must remain consumed. In particular `OPENDITOO-M9-ACTIVATION-009` is consumed after one clean 3-frame / 9-packet / 494-byte sequence and may never be re-armed. A future one-shot test requires a new experiment ID and grant.

## Current operational baseline

Leave the persistent product runtime installed and running under `OPENDITOO-PRODUCT-RUNTIME-001`. Normal physical-input stock screens are transient by design; the dashboard reclaims ownership. Device loss is recoverable via bounded reconnect. No further experimentation is required merely to preserve this baseline.

Before changing implementation code, hydrate from `START_HERE.md`, this note, `notes/OPENDITOO-HANDOFF-2026-09-09.md`, and `notes/OPENDITOO-PRODUCT-RUNTIME-HARDENING-2026-09-09.md`; run `python3 scripts/verify_day1_offline.py`; verify `product-check`; preserve the local standing policy and all legitimate concurrent work.
## Follow-on closure package

The Runtime 001 baseline in this file remains immutable acceptance evidence. P2/P3/P4 follow-on work is routed through `notes/OPENDITOO-MCP-DASHBOARD-V1-RELEASE-2026-09-09.md`. Runtime 002 is side-by-side and telemetry-only; it does not supersede this physical evidence until separately granted and cut over.
