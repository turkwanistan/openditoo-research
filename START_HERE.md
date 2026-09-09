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
| M9 activity application | N1-N4 complete: authority lifecycle, takeover-aware receive, change-only scheduling, sources and offline preview. N5 complete — 002 PASS over its full 300 s; both grants consumed. |

| Rate ladder R1-R5 | complete; **0.90 → 18.46 fps** sustained at full colour, all operator-confirmed |
| A1 collection worker | installed and running; collection only, cannot transmit |

### Authority state

**`OPENDITOO-M9-ACTIVATION-004` is currently authorized for ONE bounded execution only.** `OPENDITOO-M9-ACTIVATION-003` is consumed after its one-frame HTTP 429 pacing-edge partial and must never be re-armed. The live 004 grant is limited to the exact frozen 60 s MCP-dashboard envelope; no retry, reconnect, reclaim, streaming, pipelining, unattended operation, or second attempt.

### Next objective

**Rate integration is complete offline.** Future activity-session source uses a **150 ms
frame-start floor (6.67 fps)**, the accepted 10 ms intra-frame spacing, and the approved
four ACK-gated cyan/blue/light-blue/cyan stages. See
`notes/OPENDITOO-ACTIVITY-RATE-INTEGRATION-2026-09-09.md`.

That capable-environment boundary is now closed for activation 003: the changed Windows
Host built and deployed successfully, repository and installed DLL hashes match exactly,
`/v1/status` is healthy with `activity-session`, and all three MCP activity sources are
reachable from normal WSL. `OPENDITOO-M9-ACTIVATION-003` is now the sole live grant and is
ready for one supervised execution. No consumed manifest may be re-armed.

Offline commands that remain safe without a grant include the verifier, `session-check`,
`session-preview`, `activity-status` without a transmitting action, and `activity-preview`.
The old `DAY1-M9-ACTIVATION-001/002` manifests are consumed historical evidence, not
activation templates.

## Current objective

M0-M5 are complete through a visibly successful custom 16x16 frame. Current objective is the bounded product runtime:

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

`OPENDITOO-M9-ACTIVATION-004` is consumed after one ACKed cyan frame (3 packets / 153 bytes). Frame 2 was refused HTTP 429 because the runner backdated its send start to the tick timestamp captured before slow live source collection. Dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The runner now re-samples monotonic time after rendering and at dispatch; a 350 ms slow-collection regression is pinned. `OPENDITOO-M9-ACTIVATION-005` is consumed; no transmission is currently authorized.

### Activation 005 result / 006 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-005` is consumed. The actual-dispatch timestamp fix worked: five frames / 15 packets / 765 bytes were ACKed before the operator pressed brightness. The animation was visibly active, but one sweep was too fast to confidently identify every color. The brightness press produced `canvas_invalidated / stopped_yielded_to_stock`, so **stock-yield is now PASS** and no reclaim occurred. Product source now runs **three visible sweeps** per activity event, collapsing duplicate cyan boundaries: 10 distinct ACK-gated frames at the 200 ms client cadence (~2.0 s total). Fresh visual-acceptance manifest: `OPENDITOO-M9-ACTIVATION-006`. **At that historical point, no transmission authority was live.**

### Activation 006 result / 007 pending — 2026-09-09

**Nothing is currently authorized.** 007 still requires a fresh explicit operator grant naming `OPENDITOO-M9-ACTIVATION-007`.

`OPENDITOO-M9-ACTIVATION-006` is consumed after a clean 30 s idle-hold run: one base frame, 552 unchanged holds, no activity event, so animation was not exercised. `OPENDITOO-M9-ACTIVATION-007` is the fresh deterministic visual trial: after the operator starts it and messages `RUNNING`, the assistant will perform one harmless read-only WSL_MCP call, creating a genuine audit event for the existing collector to animate. No current transmission is authorized.
