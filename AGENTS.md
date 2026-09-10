# OpenDitoo agent contract

OpenDitoo is a preservation-first reverse-engineering project for the owner's Divoom Ditoo Plus. Exact-unit evidence outranks family resemblance, static reference firmware, plans, and chat history.

## Current objective

Day-1 application-first portability, MCP Dashboard v1, the R1-R5 rate ladder, general frame streaming, W10 webcam productization and **physical button pagination (BTN-0..6)** are complete. The live everyday product is **Runtime 006**:

`Ditoo left/right/lever -> AVRCP -> Windows SMTC -> receive-only OpenDitoo.ButtonProbe (child of the product service) -> read-only NDJSON cursor -> page router (host/pagination.py) -> existing typed activity session`

Runtime 006 reuses Runtime 005's `run_product`, Host, target, session/pacing/budgets and reclaim/reconnect unchanged; the probe contains no Ditoo transport, Host call or send path. Do not open a second RFCOMM controller, weaken the canvas-invalidation fence (arrow `0x09` and lever `0xBD` reports are tolerated by reclaim, never special-cased), map long lever holds, or pursue firmware/MassBoot/teardown for input. Adding or changing a page changes hashed code/assets and needs a fresh reviewed product revision and grant — develop such changes on a branch/worktree, because editing `host/pagination.py`, `cli/openditoo.py`, `host/frame_stream.py`, page assets or the staged probe on `main` makes the live policy refuse its next restart. The current handoff is `notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md`.

The older MassBoot/update research remains preserved but is not the current execution priority.

### Active successor objective — high-FPS interactive pages + richer MCP pulse

The owner-selected successor work is specified in `notes/OPENDITOO-HIGH-FPS-INTERACTIVE-PAGES-PLAN-2026-09-10.md`. Treat BTN-9 as a platform capability, not a spiral optimization: pages must be able to select either the existing low-rate `activity` profile or the existing one-frame-in-flight `streaming_ack_clock` profile, while physical Left/Right remain global navigation and the short lever becomes a page-local action. The first meaningful high-rate acceptance app is a three-reel slots page whose reels stop one at a time on successive short lever pulls. In parallel, prototype the MCP activity pulse as a spatial lightning-strike animation that descends into the active icon before the accepted blue/cyan flare.

Develop this successor side-by-side. Runtime 006 remains the live rollback baseline; do not edit its hash-bound files on `main`. Offline implementation/research may proceed autonomously, but a new live display/session still requires the exact named manifest/policy grant required by this contract.

**Current successor checkpoint (2026-09-10):** HF-1, HF-2, GAME-1 and UI-1 are offline PASS on `feat/high-fps-interactive-pages` (core implementation commit `65723e6`). HF-3 is implemented as one outer one-use experiment, `OPENDITOO-INTERACTIVE-HF3-001`, with deterministic unique Host child ids and hard aggregate lifetime/session/frame/byte ceilings. The canonical successor verifier is 37/37 PASS and its 10-cycle dry-run is PASS. No successor device I/O has occurred. **HF-3 is PASS** (`OPENDITOO-INTERACTIVE-HF3-008`; 001–007 consumed, never re-arm). Next is HF-4, a standing successor on the accepted single-session `PageCarousel` architecture; its cutover needs a fresh reviewed product revision and the exact named grant. Never close/reopen the Host session to change pages. 

## Evidence hierarchy

1. Exact-unit raw captures, photos, exported app traffic, immutable artifacts and experiment results.
2. Exact purchased-unit model/firmware/transport observations.
3. Exact Ditoo Plus reference firmware and preserved provenance under `artifacts/`.
4. Current project synthesis in `PROJECT_STATE.md`.
5. OpenTivoo and other Divoom-family evidence as comparative prior art only.
6. Plans, notes and chat history.

Never convert matching framing, command numbers, device-family firmware, or a temporary visual result into stronger semantics than the evidence supports.

## Physical boundary

Repository work, parsing, fixtures, preview generation and static analysis are offline and do not grant device authority.

M4/M5 experimental transmissions required frozen manifests and explicit session authority. Those milestones are complete and their authority is consumed.

**Every experimental/manual live operation requires a NEW reviewed manifest and an explicit operator grant naming that manifest's experiment id. `image-show` is included and is not an exception.** The earlier carve-out in this file — which treated an operator's explicit `image-show` invocation as authorizing one fixed-target static-image transaction on its own — is superseded as of 2026-09-09 (N1 reconciliation) and must not be relied on. A consumed experiment manifest is never re-armed: a failed, ambiguous or partially sent attempt needs a fresh manifest and a fresh grant, never a reset flag or a flipped `authorization_consumed`. Build/deploy capability, possession of the Host token, a reachable Host, process startup and prior successful trials confer no transmission authority.

**Persistent product mode is a separate authority shape, not an exception that revives experimental grants.** It may run only from a local mode-0600 `.openditoo-local/product-runtime-policy.json` materialized after an explicit operator grant naming `OPENDITOO-PRODUCT-RUNTIME-001` (or a later reviewed product policy). The committed `product/OPENDITOO-PRODUCT-RUNTIME-001.json` template MUST remain unauthorized. A product policy binds the exact Ditoo/MAC+firmware, frozen code hashes, existing typed activity-session Host, startup behavior, bounded reconnect backoff and stock-screen reclaim semantics; it grants no raw-send, target-selection, firmware, generic Bluetooth, pipelining, or unrelated CLI authority. Within that policy only, the supervisor may create fresh unique bounded session IDs automatically, renew a bounded session, reconnect after genuine unavailability, and reclaim the MCP dashboard after canvas invalidation. Product authority persists only until explicit uninstall/revocation; uninstall must stop/disable the product service and revoke/move the local policy record.

The operational boundary on `image-show` is unchanged and still binding under the new manifest rule: one connection, exactly three stock-derived packets, no automatic retry, no automatic reconnect, no target override and no raw-packet override. Automation must not invoke `image-show` merely because a PNG exists.

Any new command family, protocol semantic, persistence behavior, streaming mode, retry behavior or target still requires a concrete reviewed experiment boundary binding:

- exact unit and installed firmware evidence;
- measured endpoint/transport;
- deterministic application bytes and hashes;
- attributable semantic evidence;
- expected response/result;
- packet, byte and timing budgets;
- persistence/state-effect analysis;
- explicit retry policy (default: none after ambiguity);
- stop/recovery policy;
- explicit session transmission authority covering that exact operation.

The current Day-1 plan is not transmission authority. Tivoo authority, target identity, pairing, channel, credentials, commands, response geometry and persistence conclusions never transfer automatically.

**On-demand webcam authority is a second, separate product policy.** `OPENDITOO-WEBCAM-PRODUCT-005` (committed template unauthorized; granted only through the local mode-0600 `.openditoo-local/webcam-product-policy.json`) lets the owner-launched desktop shortcut (`scripts/webcam_on_demand.sh`) suspend the dashboard, run ONE bounded `streaming_ack_clock` session (≤30 min / 36001 frames, fresh one-use id, no retry/reconnect/reclaim) through the W10 Studio, and restore the dashboard. It never starts by itself, never widens the dashboard policy, and any Host or Studio change invalidates it by hash and needs a fresh reviewed revision and grant. Revoke with `python3 host/webcam_studio.py policy-revoke`.

## Day-1 prohibitions

Do not perform firmware updates, persistent gallery/uploads, service/test/MassBoot entry, teardown, USB vendor commands, brute-force command enumeration, arbitrary raw sends, or automatic retries after an ambiguous outcome. One controller owns Ditoo at a time.

Ordinary stock operation and official-app capture must be recorded as stock observations, not custom-command authority. Pairing/discovery are active traffic and must be recorded separately from passive advertisement observation.

## Working topology

Target topology is:

`WSL_MCP -> WSL OpenDitoo CLI -> separate authenticated Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

OpenDitoo must keep its Host port, token, state directory, target binding and process ownership separate from OpenTivoo. Never replace the OpenTivoo Host, its scheduled task, or port 8779.

The measured Ditoo transport and M5 image primitive are proven. The OpenDitoo Host exposes exactly the typed image routes documented in the repository: `/v1/image/show` (one static frame) and `/v1/image/sequence` (an ordered, already-hash-frozen frame list inside one connection). `/v1/status` advertises `status`, `image-show` and `image-sequence`. The sequence route is an accepted M8 capability — factually implemented, deployed and physically exercised under grants that are now consumed — and it is **not** ongoing authority. The M9 `/v1/session/open`, `/v1/session/frame`, `/v1/session/heartbeat`, `/v1/session/close` family was also physically exercised under consumed grants. It shares the single-operation gate with the image routes. Its authority is one-use and durable: the Host consumes the experiment id in an on-disk ledger **before** the socket exists, and the WSL CLI claims the same id with `O_EXCL`; neither claim can be released. The Host independently enforces lifetime, pacing and frame/byte budgets through a watchdog the caller cannot cancel. After the completed R1-R5 rate ladder, **future source uses a 150 ms frame-start floor (6.67 fps) and 10 ms activity-session packet spacing**; the historical M9 trials actually ran at 1118 ms and remain immutable evidence. The new rate integration is offline-verified source only until a capable environment builds and verifies the changed Windows Host. Every experimental manifest is consumed. **The current dashboard product authority is `OPENDITOO-PRODUCT-RUNTIME-007` (exactly Runtime 006 — Runtime 005 envelope plus button pagination — re-bound to the first-frame-spacing Host `3faf520f…`; 006 kept as exact-byte rollback), granted only through the local git-ignored mode-0600 policy; it covers only the exact MCP product loop and the pages it names, and remains in force until explicit uninstall/revocation. The webcam policy is `OPENDITOO-WEBCAM-PRODUCT-006`. The Host task is headless (conhost), so stopping the task orphans the Host; the refresh script stops only the port owner whose exe path is the owned runtime.** Raw-send, target selection and generic Bluetooth operations remain prohibited, and no further route may be added without its own reviewed boundary.

**Frame streaming (S1) adds no route and no second stack.** The general 16x16 RGB888
streaming path (`host/frame_stream.py`, `stream-prepare` / `stream-preview` / `stream-run`)
is a frame *source* only: it freezes and quantizes frames offline, then hands them to the
existing typed `/v1/session/*` transaction through the same client, the same durable
one-use experiment claim, the same Host-side watchdog, budgets and 150 ms floor. Its
dispatch cadence is bounded by the hash-frozen runner at 200 ms. It confers no authority:
every live stream needs its own reviewed `kind=frame_stream` manifest and an explicit
operator grant naming that experiment id, and the persistent product supervisor must be
stopped for the duration because one controller owns Ditoo at a time.

**Session pacing profiles.** The session family now resolves timing from a named profile:
`activity` (150 ms floor, 10 ms packet spacing — the MCP dashboard, and what an absent profile
means) and `streaming_ack_clock` (40 ms floor, 0 ms spacing, ACK-clocked — R5's accepted
shape). A caller selects a profile by NAME and never supplies timing; the Host owns the
constants, confirms which profile it applied, and refuses an unknown name rather than
defaulting. One frame in flight and one ACK per frame in both: this is not pipelining, which
remains prohibited. The streaming floor is deliberately non-zero so the Host, not the client,
remains what bounds the rate. **The streaming profile is currently built only at
`bin/Streaming/net8.0`; deploying it over `bin/Release/net8.0` invalidates the standing
Runtime 002 policy hash and requires a reviewed Runtime 003 policy.**

**Sequence authority lifecycle:** the earlier manual-consumption gap is closed in the current source; `sequence-run` takes the same durable one-use experiment claim before dispatch. This does not revive any sequence authority: every existing sequence manifest is consumed.

## Discipline

- Preserve legitimate concurrent/untracked work.
- Keep raw captures immutable; derive filtered fixtures separately.
- Hash raw inputs, derived fixtures, source and executable artifacts.
- Preserve parser failures and negative results.
- Distinguish transport success, semantic success, visual success and persistence confidence.
- Independently justify drawing entry, paint and exit.
- Freeze first-frame evidence before expanding to stability/streaming.
