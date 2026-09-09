# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

## Current session route — 2026-09-09

1. **Read `notes/OPENDITOO-HANDOFF-2026-09-09.md` first, especially section 0.** It carries
   current state, the authority position, and an explicit warning about environment
   capability that matters if you are running under WSL_MCP rather than a local session
   with a Windows bridge.
2. Run the three read-only capability checks in handoff section 0 **in your own session**.
   Do not inherit either previous session's answers; two sessions got opposite results on
   the same day.
3. Read `AGENTS.md` for the execution and authority boundary.
4. Run `python3 scripts/verify_day1_offline.py` before changing or executing anything.
5. Read `OPENDITOO-FORWARD-ROADMAP-2026-09-09.md` for the N/A/L sequence. N1-N5 and the
   R1-R5 rate ladder are complete; A1 is installed. See handoff section 8d for what is
   genuinely still open.
6. Read milestone evidence only as needed:

### Milestone state

| Milestone | State |
| --- | --- |
| M0-M5 | complete; authorities consumed |
| M6 static runtime + diagnostics | complete; physically accepted; pixel geometry proven |
| M7 keyboard/button mapping | complete as a **bounded negative**; no usable physical navigation |
| M8 repeated frames | complete; historical loops ran ~1118 ms/frame; later R1-R5 measured the same one-ACK-per-frame shape through 18.46 fps |
| M9 activity application | complete through 008: deterministic trigger, repeated activity animation, stock takeover detection, and physical green → yellow → red → grey status acceptance all PASS; fault-bar remains opportunistic only |

| Rate ladder R1-R5 | complete; **0.90 → 18.46 fps** sustained at full colour, all operator-confirmed |
| A1 collection worker | installed collection-only baseline; product installer will transactionally pause it while product runtime owns source cursors and restore its prior state on uninstall |
| P1 persistent MCP product runtime | implemented/offline-hardened; **persistent local authority granted**; install/start pending |

### Authority state

**Persistent product authority `OPENDITOO-PRODUCT-RUNTIME-001` remains active locally, and `OPENDITOO-M9-ACTIVATION-009` is additionally authorized for ONE fault-bar visual acceptance execution.** 009 requires temporarily stopping the product service, running the exact frozen healthy → simulated Lab unavailable → healthy sequence once, then restarting the product service. No other experimental transmission is authorized.

**Every activation 001–008 is consumed. Persistent product authority `OPENDITOO-PRODUCT-RUNTIME-001` is now granted.** The committed template remains deliberately disabled; standing authority exists only in the local git-ignored mode-0600 `.openditoo-local/product-runtime-policy.json`, which currently passes `product-check` with `execution_ready:true`. Install/start is the next boundary. Never commit the authorized local policy.

### Next objective — plug-and-play product activation

008 physically accepted production status rendering: green <5 min, yellow 5–20 min, red >=20 min, grey for no usable activity data. The dashboard/product surface is therefore ready for the granted persistent authority shape. See `notes/OPENDITOO-PRODUCT-RUNTIME-HARDENING-2026-09-09.md`.

Prepared product behavior:

- Windows user logon starts the existing `OpenDitoo Day1 Host` and a separate owned `OpenDitoo Product Runtime` bootstrap;
- the bootstrap starts the WSL `openditoo-product.service`;
- product service collects MCP state itself, using the same approved renderer and bounded Host sessions;
- if Ditoo/Host is unavailable, reconnect uses bounded 1/2/5/10/30 s backoff and keeps collecting while waiting;
- if a physical input causes `canvas_invalidated`, the supervisor immediately starts a fresh bounded session and restores the current MCP dashboard; a storm guard adds a 1 s cooldown only after >8 takeovers in 10 s;
- routine bounded-session renewal is automatic and uses a fresh globally unique Host-ledger ID each epoch;
- SIGTERM/Windows shutdown requests a clean session close;
- the standalone collection timer is transactionally paused during product install and its exact prior enabled/active state is restored on rollback/uninstall;
- uninstall revokes the local persistent policy.

The reliable Windows startup boundary is **current-user logon / StartWhenAvailable**, not pre-login kernel boot, because the WSL distro and its systemd user service are user-scoped. The bootstrap itself starts WSL, so no terminal or manual WSL launch is required.

Offline commands remain safe without authority: verifier, `product-check`, `product-status`, `session-check`, `session-preview`, `activity-status` without a transmitting action, and `activity-preview`. `product-runtime` refuses without a valid local persistent policy.

## Current objective

M0-M5 are complete through a visibly successful custom 16x16 frame. Current objective is the hardened plug-and-play MCP product runtime:

`exact local 16x16 PNG -> deterministic RGB888 decode -> stock-derived image packet -> authenticated fixed-target Windows Host -> Ditoo`

The older MassBoot key/GPIO/update-dispatch research is preserved but deferred. Do not restart USB/service-mode work merely because those static paths exist.

## Working topology

`WSL_MCP -> WSL project/CLI -> separate authenticated Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

The WSL project is `openditoo-research` under `/home/wan/Projects`. The OpenDitoo Host must keep its endpoint, token, state and process ownership separate from OpenTivoo. Never replace OpenTivoo's Host, task or port 8779.

The post-M5 OpenDitoo Host remains isolated on `127.0.0.1:8796` and is a typed image
runtime: fixed exact Ditoo target, fixed RFCOMM channel 1, `/v1/image/show` plus the M8
`/v1/image/sequence` route, no target override and no raw-send route.

The older statement that the installed Windows Host "may still be the older status-only
build" is **stale and superseded** by M6/M8 evidence. At M6 time the installed
`OpenDitoo.Day1.Host.dll` SHA-256 was
`092ed38d4dd7aaeb3eedbdab15c2c0a0f8dac07ea6134545e18ad15398fa636c`, byte-identical to the
repository's `bin/Release/net8.0` build, deployed at `%LOCALAPPDATA%\OpenDitoo\Day1Host`
under the at-logon scheduled task `OpenDitoo Day1 Host`. **That identity was verified at
M6 time.** Any claim about the bytes installed *right now* is a separate check that was
not re-run during this documentation pass; re-verify the hash before a build-sensitive
step rather than inheriting it, and do not reinstall on the strength of this paragraph.

## Prohibitions for current Day 1

No firmware updates, persistent uploads, teardown, service/test/MassBoot entry, USB vendor commands, arbitrary proprietary writes, command brute-forcing, inherited Tivoo permissions, or automatic resend after an ambiguous custom outcome.


### Activation 004 result / 005 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-004` is consumed after one ACKed cyan frame (3 packets / 153 bytes). Frame 2 was refused HTTP 429 because the runner backdated its send start to the tick timestamp captured before slow live source collection. Dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The runner now re-samples monotonic time after rendering and at dispatch; a 350 ms slow-collection regression is pinned. `OPENDITOO-M9-ACTIVATION-005` is consumed; at that historical point no transmission authority was live.

### Activation 005 result / 006 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-005` is consumed. The actual-dispatch timestamp fix worked: five frames / 15 packets / 765 bytes were ACKed before the operator pressed brightness. The animation was visibly active, but one sweep was too fast to confidently identify every color. The brightness press produced `canvas_invalidated / stopped_yielded_to_stock`, so **stock-yield is now PASS** and no reclaim occurred. Product source now runs **three visible sweeps** per activity event, collapsing duplicate cyan boundaries: 10 distinct ACK-gated frames at the 200 ms client cadence (~2.0 s total). Fresh visual-acceptance manifest: `OPENDITOO-M9-ACTIVATION-006`. **At that historical point, no transmission authority was live.**

### Activation 006 result / 007 pending — 2026-09-09

**At that historical point no transmission authority was live.** `OPENDITOO-M9-ACTIVATION-007` is consumed and may never be re-armed.

`OPENDITOO-M9-ACTIVATION-006` is consumed after a clean 30 s idle-hold run: one base frame, 552 unchanged holds, no activity event, so animation was not exercised. `OPENDITOO-M9-ACTIVATION-007` is the fresh deterministic visual trial: after the operator starts it and messages `RUNNING`, the assistant will perform one harmless read-only WSL_MCP call, creating a genuine audit event for the existing collector to animate. At that historical point no transmission authority was live.


### Activation 007 deterministic trigger result — 2026-09-09

`OPENDITOO-M9-ACTIVATION-007` is consumed after a clean deterministic live-trigger run: 31 ACKed frames / 93 packets / 4743 bytes over the full 30 s lifetime, zero dropped pulses and no pacing refusal. A genuine `wsl_mcp` audit event at 18:00:41Z occurred inside the session after the assistant's harmless read-only WSL_MCP call; the operator reported "yes the skull flashed". Deterministic trigger and visible animation are PASS. Individual cyan/blue/light-blue order remains PARTIAL because the operator did not explicitly confirm every color. Stock-yield remains PASS from 005; fault-bar remains NOT TESTED because no genuine source failure occurred. **At that historical point no transmission authority was live.**

### Activation 008 pending — accelerated green/yellow/red/grey acceptance

Production status semantics remain green <5 min, yellow 5-20 min, red >=20 min, and grey for no usable activity data. A test-only virtual-clock profile lets the exact device show those states as green 0-3 s -> yellow 3-6 s -> red 6-9 s -> grey from 9 s onward without changing production thresholds or persisted source state. Offline suite: **157 tests PASS**. `experiments/DAY1-M9-ACTIVATION-008.json` was historically authorized for exactly one bounded 15 s execution under `Grant OPENDITOO-M9-ACTIVATION-008`; that run is now consumed and PASS (four changed frames, hard ceiling 8). See `notes/OPENDITOO-MCP-STATUS-TRANSITION-ACCEPTANCE-2026-09-09.md`.


### Product decision after 007 — dashboard owns the display while connected

The operator does not intend to use the stock Ditoo UI. Future hardened product mode should therefore treat a physical-input stock takeover as transient: detect canvas invalidation, then deliberately reacquire the exact Ditoo and restore the MCP dashboard. This is a NEW unattended/reclaim authority shape and is not authorized by 008 or any earlier grant. It must preserve exact-target binding, single-controller ownership, bounded reconnect/backoff, no raw-send surface, and OpenTivoo isolation.


### Activation 008 result — status transitions physically accepted

`OPENDITOO-M9-ACTIVATION-008` is consumed and PASS. The test-only virtual-clock profile produced exactly four ACKed changed frames over 15 s (12 packets / 714 bytes), clean `lifetime_expired`, with 287 unchanged holds and no pacing/refusal. Operator observation: **all green → yellow → red → grey transitions were visible and looked good**. Production thresholds remain unchanged: green <5 min, yellow 5–20 min, red >=20 min; grey remains no usable activity data. At completion of 008, no standing product authority had yet been granted; that historical state is superseded by the current `OPENDITOO-PRODUCT-RUNTIME-001` grant.

Product decision recorded immediately after acceptance: stock UI is not desired while OpenDitoo owns the device. Future plug-and-play product mode should automatically restore the last/current MCP dashboard after a physical input causes stock takeover, rather than yielding until reconnect. This is a new product-runtime authority shape and is not authorized by 008.

### Persistent product runtime live acceptance — initial attach + stock reclaim — 2026-09-09

`OPENDITOO-PRODUCT-RUNTIME-001` is now installed under its local mode-0600 persistent policy. Windows installer reported `PRODUCT_SERVICE=ACTIVE`, `WINDOWS_STARTUP=AT_LOGON_START_WHEN_AVAILABLE`, and `INSTALL_STATUS=PASS_PRODUCT_RUNTIME`; the committed policy template remains disabled. The dashboard became physically visible without a manual activity-session invocation, so automatic initial attach is **PASS**.

Physical reclaim is also **PASS**. The operator pressed brightness once; the Ditoo briefly showed the stock clock and then automatically returned to the MCP dashboard. Runtime telemetry recorded `canvas_invalidated / stopped_yielded_to_stock`, `reclaims=1`, `reconnects=0`, `connected_sessions=1`, and advanced from product session `...000001` to `...000002`, proving this was immediate stock-screen reclaim rather than disconnect backoff.

Known observability defect: while a bounded product session is actively running, `product-status` remains at `status=connecting` because the supervisor persists that state before entering `run_session()` and receives no mid-session callback after Host open/first ACK. This is telemetry-only: physical display plus Host/session evidence prove attach/reclaim. Do not modify the hash-frozen live runtime in place; fix under a fresh reviewed product revision after live acceptance of reconnect/startup.

### Persistent product reconnect acceptance — 2026-09-09

Physical device power-cycle reconnect is **PASS** under `OPENDITOO-PRODUCT-RUNTIME-001`. With the Windows product service left running (same `run_nonce` `2066c485`, same `started_at`), the Ditoo was powered off long enough to force reconnect backoff and then powered on again. The MCP dashboard returned automatically with no Windows intervention. Runtime evidence after recovery: `connected_sessions=2`, `reconnects=4`, `session_sequence=6`; one failed epoch recorded `open_failed` / HTTP 502 before later recovery. Because the runtime state file is only persisted at session boundaries, live `status=connecting` and `last_error` may remain stale while a later session is visibly healthy; this is an observability defect, not a reconnect failure, and must be corrected only in a new hash-frozen product revision after startup acceptance.



### Activation 009 result — Lab fault bar physically accepted

`OPENDITOO-M9-ACTIVATION-009` is consumed and PASS. The frozen production-renderer sequence sent exactly three frames in one connection (9 packets / 494 application bytes, ACKs 0x61/0x99/0xF4, 6413 ms total): healthy Lab grey/no bar -> render-only simulated `source_health=unavailable` Lab grey + dim-red crown fault bar -> healthy Lab grey/no bar. Operator observation: **"saw it, looks good"**. This physically accepts the fault-bar appearance/path on the exact Ditoo. It remains correctly labeled simulated source-health acceptance; it does not prove that a genuine Lab outage is detected end-to-end. Persistent product authority remains separate and active.
