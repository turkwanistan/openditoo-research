# OpenDitoo agent contract

OpenDitoo is a preservation-first reverse-engineering project for the owner's Divoom Ditoo Plus. Exact-unit evidence outranks family resemblance, static reference firmware, plans, and chat history.

## Current objective

Application-first Day-1 portability:

`stock characterization -> measured application-control transport -> codec verdict -> one bounded custom query -> one independently justified volatile 16x16 frame`

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

Repository work, parsing, fixtures, preview generation, static analysis and local status-only Host work are offline and do not grant device authority.

Before any custom Ditoo application transmission, require a concrete reviewed experiment manifest binding:

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

Until an exact Ditoo transport is measured, the OpenDitoo Host is status-only and must expose no Bluetooth operation.

## Discipline

- Preserve legitimate concurrent/untracked work.
- Keep raw captures immutable; derive filtered fixtures separately.
- Hash raw inputs, derived fixtures, source and executable artifacts.
- Preserve parser failures and negative results.
- Distinguish transport success, semantic success, visual success and persistence confidence.
- Independently justify drawing entry, paint and exit.
- Freeze first-frame evidence before expanding to stability/streaming.
