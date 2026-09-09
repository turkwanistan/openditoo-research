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

The live render was reviewed at 16× nearest-neighbour and reads clearly.

**The renderer was replaced after N5's first trial** — see section 7.

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

## 7. The approved MCP page (operator-supplied design, 2026-09-09)

The operator supplied `opentivoo_mcp_activity_ui_handoff_package`, making the artwork
migration the roadmap had parked ("needs an explicit later product decision and actual
assets") an explicit decision with actual assets. The three-band renderer is replaced.

**Layout** — rows 0-2 activity crown, 3-4 spacer, 5-9 identity letters, 10 divider,
11-15 icons; 5 px per source, x=15 spare.

| Column | Source | Identity | Status accent |
| --- | --- | --- | --- |
| x0-4 | `optiplex_lab` | `L` + mushroom | whole cap recolours |
| x5-9 | `optiplex_mcp` | `O` + bunny | eyes only |
| x10-14 | `wsl_mcp` | `W` + skull | eyes only |

**Status** — green under 5 min, yellow to 20, red beyond, grey for no usable data.
**Activity** — the active column's crown, letter and icon accent take the blue override
together, then fall back to status colour. Crowns are per column, so simultaneous
activity merges rather than queueing — which is also what the no-replay rule requires.

### Nothing was transcribed

The design arrived as PNG mockups. Hand-transcribing them is the mistake this project
already made once with a capture payload, so `host/activity_ui_data.py` is **derived**
from `assets/ui/reference/` by `scripts/generate_activity_ui_data.py`, and two guards
keep it honest:

- the generator re-runs in `--check` mode from the offline verifier and the test suite,
  failing on any drift between the committed data and the mockups;
- the renderer re-renders **all eight approved mockups pixel-for-pixel** — four status
  frames, the mixed state, and the three single-column activity frames.

The mockups are therefore executable acceptance criteria: if a pixel moves, a test fails.

### Three things to know

1. **The four-stage blue pulse is not animated.** At the accepted ~1118 ms per frame it
   would be decimated to noise. The crown is static while activity is fresh; the visible
   activity signal is the blue override appearing and disappearing. Upgrading this needs
   a faster rate, which needs separate evidence and its own grant.
2. **Idle and unreachable are separated by a fault bar**, on the operator's decision.
   The approved spec merged them into grey and listed splitting them as an open question.
   A source the collector could not read (`unavailable`) or has stopped reading (`stale`)
   shows a dim red bar across the middle of its crown row; a source that has simply been
   quiet stays plain grey, and a source never yet polled shows neither — otherwise a cold
   start would light three fault bars.

   The crown row is free by construction: the collector zeroes the new-event count for
   any source it failed to read, so a faulted source can never pulse. The renderer still
   gives fault explicit precedence rather than resting on that invariant, and a test pins
   the invariant itself. The bar reuses a red already in the design, so it costs no extra
   palette entry and the worst-case frame is unchanged.
3. **RGB222 is gone as a constraint.** It came in with the Tivoo artwork; the exact unit's
   stock `0x44` path is plain RGB888, proven by all 8/8 captured snapshots re-encoding
   byte-for-byte from an RGB888 palette. The approved artwork keeps its colours because
   they are the approved design, not because they are required. A behavioural test now
   round-trips off-palette colours through the whole encode path to prove nothing
   quantises them. Worst-case frame is 188 bytes, 203 with preambles, up from 191.

## 8. Parked: the frame-rate ladder

The operator wants ~10 fps eventually. Recording the evidence now so nobody re-derives it,
and so nobody mistakes the target for an earned rate.

**Where the current 1118 ms actually goes** — *corrected by R1 on 2026-09-09:* a
deliberately conservative 1000 ms inter-frame delay, plus ~80 ms of packet spacing
(`SendSpacingMs` 40 ms x 2 gaps), plus roughly **25-40 ms** of actual device turnaround.

The `ackLatencyMs` this project has recorded since M6 is measured as
`ackAt - frameStartedAt`, so it **includes** our own 80 ms of send spacing. The
"~105 ms ACK latency" was never the device's turnaround, and treating it as such is what
produced the wrong conclusion below.

| Step | Change | Result | Risk |
| --- | --- | --- | --- |
| **R1** | delay 1000 -> 250 ms | **DONE: 371.6 ms, 2.71 fps** | none realised |
| **R2a** | delay 250 -> 50 ms | **DONE: 175.4 ms, 5.70 fps** | none realised |
| **R2b** | spacing 40 -> 10 ms | **DONE: 109.3 ms, 9.15 fps** | none realised; the stock spacing was not load-bearing |
| **R3** | frame size 71 -> 1054 B | **DONE: 118.2 ms, 8.46 fps** | none realised; full colour costs 8.9 ms |
| **R4** | 512 frames over 67 s | **DONE: 131.0 ms, 7.63 fps, no drift** | none realised on the device; the CLI misread its own result |
| R5? | pipeline past the ACK | **not needed** for anything asked for so far | would abandon per-frame confirmation |

**Correction.** This note previously said 10 fps was unreachable without R3, because
100 ms per frame sat "below the observed median ACK latency alone". That compared against
the wrong number: ~105 ms was mostly our own send spacing. With the spacing reduced and
the delay floor lowered, **10 fps is reachable while keeping one ACK per frame**, so R3
is very likely not needed at all.

Two things that remain *not* evidence for any rate here: OpenTivoo's 10 fps is class-5
prior art on a different device, and the stock app's 148 ms floor is an observation about
that app. R1 earned 250 ms by measuring it; R2 must earn the next step the same way.

## 9. A1 — installed collection worker (2026-09-09)

Installed and running. **Collection only: it holds no transmission authority and cannot
acquire one.** Login, boot and restart all produce zero Bluetooth operations.

Native supervision, near-zero new code: a systemd **user** timer firing a `oneshot`
service that runs exactly `activity-status --collect`. systemd owns single-instance
execution, restart-on-boot and log rotation, so none of that is reimplemented.

- `runtime/wsl/openditoo-collect.service` / `.timer`, installed by
  `runtime/wsl/install_openditoo_collector.sh` (`--status`, `--uninstall`).
- 30 s period. The adapters are cursor-based, so a longer period costs freshness and
  never correctness; a display session does its own per-second collection while it runs.
- `stdout` goes to `/dev/null` deliberately — the state file is the source of truth, and
  logging it every tick would copy source cursors into the journal for no benefit. Only
  failures are logged.
- The installer refuses to install a unit mentioning any transmitting command, and the
  offline verifier fails if one ever appears.
- Uninstall removes the two units and explicitly preserves `.openditoo-local` (claims,
  ledger, cursors, token), `captures/`, and everything OpenTivoo owns.

Verified after install: all three sources healthy, `bluetoothTouched=false`, zero device
operations, and OpenTivoo's three user services (`opentivoo-codex-usage`,
`opentivoo-tv-web`, `opentivoo-usage-dashboard`) still enabled and running.

### Trap found while doing it: `PrivateTmp=true` breaks the remote sources

Added as routine hardening; it silently took out two of the three sources. `PrivateTmp`
gives the unit its own mount namespace, and inside it `ssh` rejects
`/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` — a symlink into `/usr/lib` — with
`Bad owner or permissions`, exiting 255 in about 45 ms.

Isolated by a clean comparison rather than guessed: direct `ssh`, plain `systemd-run`,
and `systemd-run -p NoNewPrivileges=true` all succeed in 130-250 ms; adding `PrivateTmp`
alone fails. Two earlier theories — a missing ssh agent, and a cold-connection timeout —
were both wrong and both discarded against evidence.

The unit reads audit logs and writes `.openditoo-local`; it needs nothing from `/tmp`, so
the setting bought no isolation and cost two sources. It is removed, the reason is
recorded in the unit file, and a test and the verifier both fail if it returns.

Note this also made the display *correct* while it was broken: the two dead sources
rendered as unavailable, which is exactly what the fault bar is for.
