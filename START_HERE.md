# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

## Current session route — 2026-09-09

0. **Read `notes/OPENDITOO-HANDOFF-2026-09-09-WEBCAM.md` first** — the current handoff. Then
   `notes/OPENDITOO-WEBCAM-ROUTE-2026-09-09.md`. The external N980P webcam
   plan is adopted as the route, with recorded amendments. Runtime 003 is deployed;
   W5 fault injection is verified (route §13). The interrupted W6 adapter implementation has
   been recovered: source plus a successful Windows build checkpoint exist, while Windows-local
   staging/selftests, the pre-claim camera-ready handshake check and five-minute soak remain
   (route §15). W6 is therefore still an offline-verification boundary, not yet a grant boundary. Then read
   `notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`. It is the current
   route: the general 16x16 frame-streaming primitive is implemented, offline-verified and
   physically exercised once. `OPENDITOO-S1-STREAM-001` is **consumed** and may never be
   re-armed; any further live stream needs a fresh manifest and a fresh named grant.
1. Read `notes/OPENDITOO-STREAMING-HANDOFF-2026-09-09.md` for how streaming was scoped. MCP Dashboard v1 is closed.
2. **Then read `notes/OPENDITOO-HANDOFF-2026-09-09.md` selectively for exact-unit transport/rate evidence and historical traps.** It carries
   current state, the authority position, and an explicit warning about environment
   capability that matters if you are running under WSL_MCP rather than a local session
   with a Windows bridge.
3. Run the three read-only capability checks in the historical handoff section 0 **in your own session**.
   Do not inherit either previous session's answers; two sessions got opposite results on
   the same day.
4. Read `AGENTS.md` for the execution and authority boundary.
5. Run `python3 scripts/verify_day1_offline.py` before changing or executing anything.
6. Read `OPENDITOO-FORWARD-ROADMAP-2026-09-09.md` as historical planning context only; its pre-productization streaming deferral is superseded. N1-N5 and the
   R1-R5 rate ladder are complete; A1 is installed. See handoff section 8d for what is
   genuinely still open.
7. Read milestone evidence only as needed:

### Milestone state

| Milestone | State |
| --- | --- |
| M0-M8 | complete; accepted evidence preserved |
| M9 MCP activity application | complete; layout/activity/status/fault-display acceptance recorded |
| R1-R5 rate ladder | complete; measured through 18.46 fps full-colour one-ACK-per-frame ceiling |
| W4 streaming session profile | deployed under Runtime 003; installed/repository Host hash `0da3a18b...`. Streaming profile has not been exercised live |
| W5 fault injection | PASS: 11 camera-free cases + 5 real-camera/in-memory-Host controls; both parity fixtures pass; route §13 |
| W2 visual ranking | owner-dependent; harness complete, `srgb_area` remains provisional |
| W6 trial freeze | **in progress**: adapter source/build checkpoint recovered; Windows-local selftests/handshake/5-minute soak and final hash freeze remain; route §15 |
| W7 first webcam acceptance | blocked on W6 final freeze + fresh named grant; one 10 s exact-unit trial |
| W8 near-ceiling webcam rate | after W7 acceptance; one bounded ACK-clock characterization, no new ladder |
| W9 optical latency | after W8 if useful; physical scene→display measurement, not inferred from ACKs |
| W10 webcam productization | after experimental acceptance; separate standing-authority decision |
| S2 stream-rate measurement | `OPENDITOO-S2-STREAM-RATE-001` consumed. Measured dispatch→ACK: median 66 ms, p95 93 ms at 1039 bytes. Dispatching at the 150 ms Host floor is FATAL (HTTP 429 on frame 10) — client must add 50 ms margin, so ~5 fps is today's safe cadence. Higher rates need a Host pacing change + Runtime 003. See `notes/OPENDITOO-STREAM-PRODUCER-CONTRACT-2026-09-09.md` |
| S1 general frame streaming | **accepted**; `OPENDITOO-S1-STREAM-001` consumed, transport PASS (42 frames / 126 packets / 2982 bytes, clean close) and operator visual PASS |
| A1 collection worker | installed/preserved; product owns collection while active |
| P1 Runtime 001 | historical accepted evidence; superseded and deliberately no longer hash-valid |
| P2 Runtime 002 | telemetry accepted; superseded by Runtime 003 and deliberately no longer hash-valid |
| Runtime 003 | active local product policy; connected, no errors, runtime_revision remains 2 |
| P3 product evidence | closed for v1; normal MCP use accepted; forced healthy-Lab outage waived |
| P4 MCP Dashboard v1 package | prepared in `PRODUCT.md` + release closure note |

### Authority state

Activations 001–009, R1–R5, S1 and S2 are consumed. No experimental one-shot transmission is live. Runtime 003 authority remains active only in the git-ignored mode-0600 `.openditoo-local/product-runtime-policy.json`; product status reports no authority blockers.

All committed product templates remain unauthorized. Runtime 003 covers the MCP dashboard only;
webcam transmission requires its own reviewed manifest and fresh named grant.
The historical Runtime 002 cutover used `Grant OPENDITOO-PRODUCT-RUNTIME-002`; that revision
is superseded, and its grant must not be reused for the webcam.

### Current objective — complete webcam offline preparation

The MCP dashboard is already the owner's working everyday baseline. Do not reopen durability, firmware, MassBoot, ACK decoding, command enumeration, or speculative UI work as release blockers.

P2/P3/P4 and Runtime 003 deployment are closed. Finish the recovered adapter's Windows-local
verification, pre-claim handshake check, five-minute soak, and final hash freeze before calling
W6 execution-ready. Preferred offline command from a Windows-capable local WSL session:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify_webcam_w6_windows.ps1`.
The coordinator now refuses a non-idle Host **before** one-use claim consumption. Do not claim,
stop the product, or transmit while preparing it.

Use `PRODUCT.md` for normal operation. The reliable startup design boundary remains current-user Windows logon / StartWhenAvailable; a real Windows reboot/login observation is intentionally deferred and is not to be invented as accepted evidence.


## Historical Day-1 objective and milestone evidence

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

### Locked MCP product baseline — 2026-09-09

The accepted MCP/product baseline is frozen in `notes/OPENDITOO-MCP-PRODUCT-BASELINE-FREEZE-2026-09-09.md`. Initial attach, stock-screen reclaim, device power-cycle reconnect, production green/yellow/red/grey aging, real WSL_MCP activity animation, and the simulated Lab fault-bar physical display path are accepted. `OPENDITOO-M9-ACTIVATION-009` is consumed. Standing `OPENDITOO-PRODUCT-RUNTIME-001` authority remains local and active. Do not modify hash-frozen product code in place. Windows reboot/logon autostart remains intentionally **PENDING** operator acceptance; a genuine source outage remains **NOT END-TO-END TESTED**. The live `product-status` `connecting`/stale-error issue is telemetry-only and is deferred to a fresh reviewed product revision.

### S1 general frame-streaming primitive implemented — awaiting first grant

The streaming transport already existed: `/v1/session/frame` takes an arbitrary 768-byte
RGB888 frame, and `run_session` is already a generic ACK-gated loop. The missing half was
the frame source, now `host/frame_stream.py` plus `stream-prepare` / `stream-preview` /
`stream-run`. **No Windows Host change was needed or made** — repository and installed DLL
verified byte-identical in-session at `fb750078...`. `host/activity_session.py` is
hash-frozen by the live Runtime 002 policy and was imported, never modified; MCP Dashboard
v1 is untouched.

This primitive's cadence ceiling is 200 ms / 5 fps, set by `MCP_CLIENT_FRAME_INTERVAL_MS`
inside that hash-frozen runner. Faster is a separate objective with its own boundary.

First live trial `OPENDITOO-S1-STREAM-001` is consumed and its transport result is PASS: one
connection, 42 ACKed frames / 126 packets / 2982 application bytes over a 12 s lifetime,
clean `lifetime_expired`, no refusals, supervisor stopped and restarted cleanly. 42 of 48
playback steps dispatched because measured ACK latency (~110–153 ms) sits close under the
200 ms client cadence; clock-indexed playback drops a step rather than stretching the clip.
A stream needing every frame should state `playback_interval_ms: 250` in its own manifest —
do not change the shared runner. Details:
`notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`.

### MCP Dashboard v1 closed — Runtime 002 accepted

`OPENDITOO-PRODUCT-RUNTIME-002` is now the active local standing product revision. Live cutover is PASS: `runtime_revision=2`, `status=connected`, first frame ACK recorded, session-open/ACK timestamps present, and `last_error=null`. P2/P3/P4 are complete; stop product-hardening work here. Windows reboot/login autostart observation is deferred and non-blocking. **Next objective: streaming and other OpenDitoo capabilities.**
