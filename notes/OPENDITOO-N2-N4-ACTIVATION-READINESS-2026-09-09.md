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

**Scheduling (historical N3 acceptance, superseded for future source):** N3 originally
used the then-accepted ~1118 ms interval. R1-R5 later measured the exact unit through
18.46 fps, and the product source now uses a conservative **150 ms / 6.67 fps** floor.
The change-only properties below are unchanged.

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

## 5. What remains deliberately out of scope

This section was originally written before N5/A1 and is superseded by the handoff for
installation state. A1 collection is now installed, but it still restores **collection
only** and never revives transmission authority.

- No M7.4 custom receive window. Still buys nothing: there is nothing to navigate.
- No automatic reconnect, replay, stock-screen reclaim or unattended transmission policy.
- No pipelining past the per-frame ACK. R5 closed the current protocol-shape rate ladder
  at 18.46 fps; future activity source intentionally operates at 6.67 fps.
- No claim that a short/one-minute run proves longer-duration durability.

## 6. Current next boundary

The old `DAY1-M9-ACTIVATION-001-PENDING` instruction is obsolete: N5 ran twice and both
resulting manifests are consumed. After the rate integration, the changed Windows Host
source must first be built in a capable environment and its repository/installed identity
verified. The activity sources must also be reachable there. Only after those offline/build
preconditions are frozen should a **new** experiment id and manifest be prepared for any
new physical acceptance. This historical statement is superseded by section 10: activation
003 now has its own one-execution operator grant.

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

1. **The four-stage pulse is now implemented in source.** The completed R1-R5 ladder
   removed the old 1118 ms product constraint. Future activity sessions use 150 ms frame
   starts (6.67 fps), and each ACK advances cyan -> blue -> light blue -> cyan across the
   crown, identity letter and icon accent before returning to status colour. This source
   integration passed offline verification; it has not yet been rebuilt/installed or
   physically accepted after the change.
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

## 8. Frame-rate ladder — complete; product policy wired offline

R1-R5 are complete and physically accepted on the exact unit. The progression was
0.90 -> 2.71 -> 5.70 -> 9.15 -> 8.46 full-colour -> 7.63 sustained full-colour ->
**18.46 fps** with every deliberate wait removed. R4's sustained 131.0 ms/frame over 67 s
is the conservative full-colour baseline; R5's 54.2 ms/frame over 56 s is the ceiling for
the current one-ACK-per-frame protocol shape. Going faster would require pipelining and is
not prepared.

The activity product now operates in source at **150 ms/frame start (6.67 fps)** with the
accepted **10 ms intra-frame spacing**, intentionally below R4 for jitter headroom. That
rate yields a ~0.60 s four-stage activity pulse and preserves per-frame acknowledgement.
See `notes/OPENDITOO-ACTIVITY-RATE-INTEGRATION-2026-09-09.md`.

Historical reminder: `ackLatencyMs` includes this project's own intra-frame sleeps; the
earlier ~105 ms interpretation as pure device turnaround was wrong. The official app's
148 ms floor is still only an observation about that app.

The 150 ms source integration is offline-verified only. The implementing WSL_MCP session
had no `powershell.exe`, no reachable Host, and no readable live activity sources, so no
Windows build, install or physical acceptance is claimed for the new source.

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


## 10. Rate-integrated MCP dashboard activation 003 — granted, pending execution

The post-rate-integration Windows boundary is now closed: changed Host build/deploy PASS, installed DLL == repository DLL (`fb750078e9...af70f`), `/v1/status` healthy with `activity-session`, and all three activity sources reachable from normal WSL. `DAY1-M9-ACTIVATION-003.json` freezes the current renderer/collector/session hashes and a 60 s, 150 ms, one-ACK-per-frame envelope. The operator explicitly granted `OPENDITOO-M9-ACTIVATION-003` in-session on 2026-09-09 for exactly this one execution; it is armed and not yet consumed. No Bluetooth/device I/O was performed while preparing or recording the grant. Streaming and pipelining are deliberately deferred to later milestones.


## 11. Activation 003 pacing-edge result; 004 pending

003 is consumed after one ACKed frame. The next client request hit the Host's 150 ms arrival guard with HTTP 429 because exact 150 ms client dispatch does not guarantee exact 150 ms server arrival across HTTP. Physical dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The client now uses 200 ms nominal frame dispatch with a phase-stable 50 ms render tick while the unchanged Host keeps its 150 ms hard floor. Offline suite: 152 tests PASS. `DAY1-M9-ACTIVATION-004.json` is the fresh acceptance manifest. `OPENDITOO-M9-ACTIVATION-004` is consumed.


### Activation 004 result / 005 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-004` is consumed after one ACKed cyan frame (3 packets / 153 bytes). Frame 2 was refused HTTP 429 because the runner backdated its send start to the tick timestamp captured before slow live source collection. Dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The runner now re-samples monotonic time after rendering and at dispatch; a 350 ms slow-collection regression is pinned. `OPENDITOO-M9-ACTIVATION-005` is consumed; no transmission is currently authorized.

### Activation 005 result / 006 pending — 2026-09-09

005 validates the corrected dispatch timestamp and stock-yield path: 5 ACKed frames / 15 packets / 765 bytes, followed by the operator brightness press and `canvas_invalidated / stopped_yielded_to_stock`. Animation was visible but too brief to identify every color confidently. Product source now repeats the color sweep three times while collapsing identical cyan boundaries: 10 distinct ACK-gated frames at 200 ms nominal client cadence (~2.0 s). 006 is pending visual acceptance only; stock-yield is already PASS from 005. **At that historical point, no transmission authority was live.**

### Activation 006 result / 007 pending — 2026-09-09

006 cleanly held the idle dashboard for 30 s (1 frame, 552 unchanged holds) but saw no source event, so animation remained unexercised. 007 is a deterministic visual trial using one genuine WSL_MCP audit event created by a harmless read-only WSL_MCP call while the bounded session is live. No synthetic collector state or fake failure is used. No current transmission is authorized.
