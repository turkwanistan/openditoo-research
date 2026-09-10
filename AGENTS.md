# OpenDitoo agent contract

OpenDitoo is a preservation-first reverse-engineering project for the owner's Divoom Ditoo Plus. Exact-unit evidence outranks family resemblance, static reference firmware, plans, and chat history.

## Current objective

Day-1 application-first portability, MCP Dashboard v1, the R1-R5 rate ladder, general frame streaming, and W10 webcam productization are complete through the accepted Runtime 005 / webcam-product-004 baseline. The owner-selected current objective is **physical button navigation over Bluetooth**, followed by the smallest two-page pagination proof:

`Ditoo left/right/lever -> AVRCP -> Windows receive-only ButtonProbe/ButtonBroker -> typed OpenDitoo input -> page router -> existing typed display session`

The preserved exact-unit M7 HCI capture has been re-analysed as containing left/right/lever AVRCP pass-through events on AVCTP PSM `0x0017`: left=`0x4C` Previous, right=`0x4B` Next, lever=`0x44` Play plus near-simultaneous proprietary RFCOMM `0xBD`. The immediate implementation route is `notes/OPENDITOO-BUTTON-AVRCP-PAGINATION-PLAN-2026-09-10.md`; the current handoff is `notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md`.

For the initial proof, do **not** modify the Runtime 005 Host, open a second RFCOMM controller, weaken the canvas-invalidation fence, or pursue firmware/MassBoot/teardown. Build the Windows input receiver side-by-side and receive-only. First pagination uses the arrows only; the lever becomes a product action only after its simultaneous `0xBD` interaction with the existing Host is measured.

The older MassBoot/update research remains preserved but is not the current execution priority.

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

The measured Ditoo transport and M5 image primitive are proven. The OpenDitoo Host exposes exactly the typed image routes documented in the repository: `/v1/image/show` (one static frame) and `/v1/image/sequence` (an ordered, already-hash-frozen frame list inside one connection). `/v1/status` advertises `status`, `image-show` and `image-sequence`. The sequence route is an accepted M8 capability — factually implemented, deployed and physically exercised under grants that are now consumed — and it is **not** ongoing authority. The M9 `/v1/session/open`, `/v1/session/frame`, `/v1/session/heartbeat`, `/v1/session/close` family was also physically exercised under consumed grants. It shares the single-operation gate with the image routes. Its authority is one-use and durable: the Host consumes the experiment id in an on-disk ledger **before** the socket exists, and the WSL CLI claims the same id with `O_EXCL`; neither claim can be released. The Host independently enforces lifetime, pacing and frame/byte budgets through a watchdog the caller cannot cancel. After the completed R1-R5 rate ladder, **future source uses a 150 ms frame-start floor (6.67 fps) and 10 ms activity-session packet spacing**; the historical M9 trials actually ran at 1118 ms and remain immutable evidence. The new rate integration is offline-verified source only until a capable environment builds and verifies the changed Windows Host. Every experimental manifest is consumed. **The current dashboard product authority is `OPENDITOO-PRODUCT-RUNTIME-005` (earlier revisions superseded), granted only through the local git-ignored mode-0600 policy; it covers only the exact MCP product loop described above and remains in force until explicit uninstall/revocation.** Raw-send, target selection and generic Bluetooth operations remain prohibited, and no further route may be added without its own reviewed boundary.

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
