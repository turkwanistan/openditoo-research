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
| M8 repeated frames | complete; accepted ceiling ~1118 ms/frame, measured twice |
| M9 activity application | N1-N4 complete: authority lifecycle, takeover-aware receive, change-only scheduling, sources and offline preview. N5 complete — 002 PASS over its full 300 s; both grants consumed. |

| Rate ladder R1-R5 | complete; **0.90 → 18.46 fps** sustained at full colour, all operator-confirmed |
| A1 collection worker | installed and running; collection only, cannot transmit |

### Authority state

**Nothing is currently authorized.** `OPENDITOO-M9-ACTIVATION-001` was granted and
executed once on 2026-09-09; it is consumed. It ended early on a defect of ours rather
than a device fault, which does not re-authorize it. Every experiment manifest is
consumed; `sequence-run` exits 30 on all of them. **Every live operation — `image-show` included —
needs a NEW reviewed manifest and an explicit operator grant naming that manifest's
experiment id.** A consumed manifest is never re-armed; an ambiguous or partial attempt
needs a fresh manifest, not a reset flag. Build/deploy capability, credentials, a
reachable Host, process startup and prior successful trials confer no transmission
authority. Continuous or unattended display is a larger authority shape than any bounded
run so far.

`sequence_run` enforces this by checking manifest flags before dispatch, but it does not
itself atomically consume or reserve authority, and its Host request carries frames and
budgets rather than an experiment identity. Past consumption was manual bookkeeping —
honest evidence of what happened, not a crash-safe automatic gate. That gap is closed for
the **session** surface by N2: `activity-session` claims its experiment id durably in WSL
and the Host consumes it in an on-disk ledger before the socket exists, neither of which
can be released. The older `sequence-run` route keeps its manual bookkeeping and must
still not be exercised to test it.

### Next objective

**N5 — first bounded M9 activation, awaiting an operator grant.** N1-N4 are complete;
see `notes/OPENDITOO-N2-N4-ACTIVATION-READINESS-2026-09-09.md` and section 8 of the
handoff. The manifest `experiments/DAY1-M9-ACTIVATION-001-PENDING.json` is complete
except for the grant, and two preconditions remain: applying the refreshed Host
(**done** — installed is now `a0f2fa1c…`, byte-identical to the repository build, and the
installed binary itself passes `HOST_SELFTEST_PASS cases=9 failures=0`), and disconnecting
the Android app (**still required**).

Offline work available without any grant:

```sh
python3 cli/openditoo.py activity-probe
python3 cli/openditoo.py activity-status --collect
python3 cli/openditoo.py activity-preview --collect
python3 cli/openditoo.py session-check   --manifest experiments/DAY1-M9-ACTIVATION-001-PENDING.json
python3 cli/openditoo.py session-preview --manifest experiments/DAY1-M9-ACTIVATION-001-PENDING.json \
                                         --scenario tests/session_scenario_bounded.json
```

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
