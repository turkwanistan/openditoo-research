# OpenDitoo N2–N4 — bounded activation readiness

Date: 2026-09-09. Written after implementing N2, N3 and N4 from
`OPENDITOO-FORWARD-ROADMAP-2026-09-09.md`. N1 is recorded in the reconciled
`AGENTS.md`, `START_HERE.md` and handoff.

**Nothing here was transmitted.** No socket was opened, no frame was sent, and no
authority was granted or consumed. Every result below is offline verification, a
Windows build, or a fixture replay.

## 1. What each verification level actually proves

These are kept separate on purpose, and one is never substituted for another.

| Level | Status on 2026-09-09 | What it does NOT prove |
| --- | --- | --- |
| Offline verification | `DAY1_OFFLINE_PASS artifacts=19 tests=124 host=typed_image port=8796 device_io=false m4_completed=true m4_authorized=false m5_authorized=false m9_activation_authorized=false` | nothing about Windows, the installed Host, the link, or the screen |
| Windows build | `dotnet publish` Release PASS; `refresh_openditoo_day1_host.ps1` dry-run `WINDOWS_BUILD=PASS`, `OPENTIVOO_TASK=preserved`, installed runtime unchanged | that the built bytes are the running bytes |
| Host receive self-check | `HOST_SELFTEST_PASS cases=9 failures=0 device_io=false` — the real compiled assembler, run against the shared fixture | anything about a real device's timing or byte stream |
| Installed identity | **NOT current.** Installed DLL is still `092ed38d…a636c` (M6-era); the built DLL is `d3ece014…a042a` | — the installed Host has no session routes at all |
| Transport acceptance | not attempted | — |
| Visual acceptance | not attempted | — |

## 2. N2 — bounded activation authority lifecycle

`host/activity_session.py` plus `runtime/windows/.../ActivitySessionHost.cs`.

A dynamic display cannot freeze all future pixels in a frame list, so the manifest
freezes the **envelope** instead: exact unit and firmware, the SHA-256 of the renderer,
collector and session modules, the Host build hash, lifetime, pacing floor, derived
budgets and stop conditions. Change the renderer and the reviewed manifest is no longer
describing what will be drawn — `BUILD_CODE_HASH_DRIFT` refuses it.

Authority is durable and one-use on **both** sides:

- WSL: `.openditoo-local/session-claims/<experiment_id>.json`, created with `O_EXCL`.
  The filesystem decides who got there first, not a flag inside the manifest.
- Host: an append-only ledger line written **before the socket exists** — the ordering is
  asserted by a test and by the verifier.

A worker or Host that dies mid-session leaves a claim in `claimed`/`unknown` and refuses
re-entry. There is deliberately no release, reset or un-consume path, and the verifier
fails if one appears.

The Host owns the bounds, not the caller. A watchdog the client cannot cancel enforces
lifetime, terminates a session whose worker has fallen silent, and observes the link
while idle. A dropped HTTP client cannot leave a live link running to its own schedule,
and cannot authorize a second request.

## 3. N3 — takeover-aware receive and change-only scheduling

**Receive.** `ReadOneAck` previously accepted exactly one 10-byte ACK and rejected
anything else. During a session the device also sends *unsolicited* reports of its own
accord (M7), so the link now reads a stream: `DitooReportAssembler` reassembles fragments,
splits coalesced reads, and classifies each frame as our wrapped `0x44` ACK or as
something else. Anything else ends the session. An ACK coalesced into the same read as a
state report still ends it — a late ACK cannot restore ownership — and **no reclaim frame
is ever sent**.

The same nine cases are replayed by the WSL Python assembler and by the compiled Host
(`--selftest`), from one shared fixture, `tests/receive_assembler_cases.json`: exact ACK,
three-way fragmentation, ACK+report coalesced, two reports in one read, trailing
fragment, garbage before start, corrupt checksum, oversize, and an unwrapped frame. Both
agree on all nine. No new command semantics are assigned; the ACK payload byte is
reported and never validated as a constant.

**Scheduling.** The accepted ~1118 ms interval is a ceiling, not a heartbeat.

- Unchanged scene → nothing sent, for as long as it stays unchanged.
- A burst coalesces to the newest frame; nothing is queued and nothing is replayed.
- A pulse deferred by pacing survives to the next permitted slot **inside** its freshness
  window, and is **dropped** if the window closes — not shown late.
- A scene that simply persists cannot renew a pulse window indefinitely.
- Age and health transitions are legitimate changes even with no new activity.
- After a takeover the display state is `unknown_not_ours` and stays that way.

**Faults.** A Bluetooth fault stops the display, records completed and unknown bytes, and
leaves collection running. A source failure is not a Bluetooth fault: it renders as an
unavailable indicator and never stops sending.

## 4. N4 — sources and a previewed session, offline

Three sources verified from this environment, read-only, no device I/O:

| Source | Reachable | Seed records | Latency | Meaning, and its limit |
| --- | --- | --- | --- | --- |
| `optiplex_mcp` | yes | 310 | 305 ms | completed tool calls; identity is a timestamp+tool fingerprint, so counts are not exact |
| `wsl_mcp` | yes | 106 | 5 ms | completed tool calls with a stable request id |
| `optiplex_lab` | yes | 0 | 215 ms | **transport dispatch, not tool completion**, and no records in the window — it renders as `no_data` (grey checkerboard), never as idle |

Two caveats that must not be lost:

- **`optiplex_lab` is reachable but has no history**, and it never carries tool-completion
  semantics. The complete three-source product cannot be called accepted on this
  evidence; degraded-mode operation can.
- **`wsl_mcp` activity includes this agent's own footprint.** The collector reads a file
  and never calls an MCP server, so there is no feedback loop — but a pulse there during
  a session may be the operator's own tooling, not independent user activity.

Two scenario replays through render → scheduler → fake transport, differing **only** in
whether someone touched the unit, so the difference in outcome is attributable to the
takeover alone:

| Scenario | Frames sent | Holds | Terminal | Display state |
| --- | --- | --- | --- | --- |
| `session_scenario_bounded` | 5 | pacing 2, unchanged 9 | `lifetime_expired` / `stopped_clean` | `ours_last_acked` |
| `session_scenario_takeover` | 3 | pacing 1, unchanged 3 | `canvas_invalidated` / `stopped_yielded_to_stock` | `unknown_not_ours` |

660 bytes and 399 bytes respectively — against a 51 379-byte ceiling. Change-only
sending is doing real work, not being asserted.

The live render was reviewed at 16× nearest-neighbour: three bands read clearly, and the
lab source's absent history shows as an explicit checkerboard rather than being hidden
behind an idle colour.

## 5. What is deliberately still not built

- No installed worker (A1). Startup would restore collection only; it would restore no
  authority, and there is nothing to supervise until an activation is accepted.
- No M7.4 custom receive window. Still buys nothing: there is nothing to navigate.
- No rate above the accepted ceiling, no reconnect policy, no session receipts beyond
  the claim and ledger (A2).

## 6. Next action

`experiments/DAY1-M9-ACTIVATION-001-PENDING.json` is complete except for the grant.
Its preconditions include applying the refreshed Host and re-verifying the installed
hash — that has **not** been done, and the installed Host does not contain the session
routes. See the handoff's authority section.
