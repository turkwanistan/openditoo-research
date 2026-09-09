# OpenDitoo agent contract

OpenDitoo is a preservation-first reverse-engineering project for the owner's Divoom Ditoo Plus. Exact-unit evidence outranks family resemblance, static reference firmware, plans, and chat history.

## Current objective

Day-1 application-first portability M0-M5 is complete through the first visible custom 16x16 frame. Current objective is bounded productization of that proven primitive:

`exact 16x16 PNG -> deterministic RGB888 decode -> stock-derived image encoder -> authenticated fixed-target Host -> Ditoo`

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

**Every live operation requires a NEW reviewed manifest and an explicit operator grant naming that manifest's experiment id. `image-show` is included and is not an exception.** The earlier carve-out in this file — which treated an operator's explicit `image-show` invocation as authorizing one fixed-target static-image transaction on its own — is superseded as of 2026-09-09 (N1 reconciliation) and must not be relied on. A consumed manifest is never re-armed: a failed, ambiguous or partially sent attempt needs a fresh manifest and a fresh grant, never a reset flag or a flipped `authorization_consumed`. Build/deploy capability, possession of the Host token, a reachable Host, process startup and prior successful trials confer no transmission authority.

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

## Day-1 prohibitions

Do not perform firmware updates, persistent gallery/uploads, service/test/MassBoot entry, teardown, USB vendor commands, brute-force command enumeration, arbitrary raw sends, or automatic retries after an ambiguous outcome. One controller owns Ditoo at a time.

Ordinary stock operation and official-app capture must be recorded as stock observations, not custom-command authority. Pairing/discovery are active traffic and must be recorded separately from passive advertisement observation.

## Working topology

Target topology is:

`WSL_MCP -> WSL OpenDitoo CLI -> separate authenticated Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

OpenDitoo must keep its Host port, token, state directory, target binding and process ownership separate from OpenTivoo. Never replace the OpenTivoo Host, its scheduled task, or port 8779.

The measured Ditoo transport and M5 image primitive are proven. The OpenDitoo Host exposes exactly the typed image routes documented in the repository: `/v1/image/show` (one static frame) and `/v1/image/sequence` (an ordered, already-hash-frozen frame list inside one connection). `/v1/status` advertises `status`, `image-show` and `image-sequence`. The sequence route is an accepted M8 capability — factually implemented, deployed and physically exercised under grants that are now consumed — and it is **not** ongoing authority. The M9 `/v1/session/open`, `/v1/session/frame`, `/v1/session/heartbeat`, `/v1/session/close` family was also physically exercised under consumed grants. It shares the single-operation gate with the image routes. Its authority is one-use and durable: the Host consumes the experiment id in an on-disk ledger **before** the socket exists, and the WSL CLI claims the same id with `O_EXCL`; neither claim can be released. The Host independently enforces lifetime, pacing and frame/byte budgets through a watchdog the caller cannot cancel. After the completed R1-R5 rate ladder, **future source uses a 150 ms frame-start floor (6.67 fps) and 10 ms activity-session packet spacing**; the historical M9 trials actually ran at 1118 ms and remain immutable evidence. The new rate integration is offline-verified source only until a capable environment builds and verifies the changed Windows Host. Every manifest is consumed and **nothing is currently authorized**. Raw-send, target selection and generic Bluetooth operations remain prohibited, and no further route may be added without its own reviewed experiment boundary.

**Sequence authority lifecycle:** the earlier manual-consumption gap is closed in the current source; `sequence-run` takes the same durable one-use experiment claim before dispatch. This does not revive any sequence authority: every existing sequence manifest is consumed.

## Discipline

- Preserve legitimate concurrent/untracked work.
- Keep raw captures immutable; derive filtered fixtures separately.
- Hash raw inputs, derived fixtures, source and executable artifacts.
- Preserve parser failures and negative results.
- Distinguish transport success, semantic success, visual success and persistence confidence.
- Independently justify drawing entry, paint and exit.
- Freeze first-frame evidence before expanding to stability/streaming.
