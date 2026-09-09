# OpenDitoo M9 — MCP activity source discovery, adapters and preview — 2026-09-09

Offline/read-only work from `OPENDITOO-IMPLEMENTATION-PLAN-2026-09-09.md` §7.
No Ditoo transmission was performed. Concrete hosts, users and log paths live only
in `.openditoo-local/activity-sources.json` (git-ignored); the committed
`examples/activity-sources.example.json` carries placeholders, and a test asserts no
private address appears in committed files.

## M9.1 Source inventory (verified live, 2026-09-09)

| | **OptiPlex MCP** | **OptiPlex Lab** | **WSL MCP** |
| --- | --- | --- | --- |
| What is running | the evolution front door on the OptiPlex, whose active slot proxies to the generation-0 guardrail backend | a separate MCP server inside an isolated QEMU VM on the same OptiPlex, reached through its own tunnel client | the WSL project-scoped MCP executor (`wsl-mcp.service`) plus its tunnel |
| Authoritative record | the guardrail's `audit.log` — the frontend slots write no audit of their own, so this one file is the whole OptiPlex MCP surface | **the lab's own tool audit is inside the VM and is not reachable from here.** Reachable instead: its tunnel-client journal, which logs each MCP command forwarded to the lab server | `audit.jsonl` under the executor's XDG state directory |
| Format | JSON Lines | journald, `-o json`, message body is JSON | JSON Lines |
| Timestamp | `ts`, ISO-8601 with `+00:00` and microseconds | `time`, ISO-8601 with a **local** UTC offset and nanoseconds | `ts`, ISO-8601 `Z`, whole seconds |
| Record means | a **completed** tool call (`ok` bool, `duration_ms`) | a **forwarded/dispatched** command, plus a separate upstream-error record — not a completion, and no tool name | a **completed** tool call (`result`, `duration_ms`); `started`/`requested`/`scheduled` are dispatch only |
| Stable ID | none — fingerprinted as `ts|tool`, so exact counts are not claimed | `request_id` (`cmd_…`) | `request_id` (UUID) |
| Failures visible | yes, `ok:false` plus a sanitized `error` | only upstream transport errors | yes, `exit_N` / `timeout` / `error:…` |
| Access from WSL | `ssh` + `tail`/`stat`; the file is world-readable, **no sudo needed** | `ssh` + `journalctl`; the account is in `adm`, **no sudo needed** | direct local file read |
| Independent health | service state + tunnel journal | the tunnel journal's own `poller recovered` / `poll failed; backing off` records | service state |
| Rotation | none observed (single growing file); handled anyway | journald owns it; the journal cursor is the resume point | none observed (single growing file); handled anyway |
| Read cost measured | ~330-380 ms per poll (ssh round trip) | ~200 ms per poll | ~5 ms per poll |

Fields sampled per source were the minimum needed to write the adapters; no audit
history was bulk-loaded, and no raw log content is committed.

### Feedback loop — resolved by construction

All three reads are **file/journal reads, not MCP calls**. None of them causes the
observed servers to write an audit record, so the collector cannot make an icon
active by polling. Verified two ways: four consecutive polls with no user activity
produced `{optiplex_mcp: 0, optiplex_lab: 0, wsl_mcp: 0}`, and
`test_collector_never_issues_an_mcp_call` pins the module to `ssh`, `stat`, `tail`
and `journalctl` with no HTTP/JSON-RPC client and no `shell=True`.

Because no attribution filter is needed, none was added — filtering by collector
identity would have been speculative machinery for a loop that does not exist.

### Honest limits recorded rather than papered over

- **OptiPlex Lab activity is transport-level.** Its pulse means "an MCP command was
  forwarded to the lab", never "tool X completed". Its outcome is `unknown` unless a
  matching upstream-error record appears. Getting real per-tool lab activity needs
  read access inside the lab VM, which this session did not have and did not attempt
  to obtain — that is an open access question, not a bug.
- **OptiPlex MCP has no stable record id.** Two identical calls inside the same
  microsecond would collide, so the collector tracks recency and outcome, not exact
  counts.
- **A readable log is not service health.** `source_health` is derived only from
  whether the *read* succeeded and how fresh it is. Nothing in the model claims the
  MCP service is connected or disconnected.

## M9.2-M9.4 Collector — `host/mcp_activity.py`

One normalized record per source (`optiplex_mcp`, `optiplex_lab`, `wsl_mcp`) with
exactly the planned fields: `last_activity_at`, `last_observed_at`, `source_health`,
`last_outcome`, `cursor`, `new_activity_sequence`, `history_complete`, `error_code`.

- **Cursors.** File sources: `(inode identity, byte offset, buffered partial line)`.
  A changed inode or a size below the stored offset is rotation/truncation — the
  collector restarts from zero and reports `history_complete: false` rather than
  silently skipping. The lab source uses journald's own cursor, falling back to a
  *moving* `--since` window until the unit has logged anything (a fixed window would
  re-count the same record on every poll).
- **Seeding.** The first read establishes `last_activity_at` from a bounded 64 KiB
  tail and returns **zero** new events, so a restart never replays history as pulses.
  The stat that fixes the resume offset is taken *after* the read, so the offset can
  never sit behind bytes already parsed.
- **Bounds.** 256 KiB and 500 records per poll; exceeding either sets
  `history_complete: false` (honest catch-up) instead of unbounded work.
- **Partial lines** are buffered and completed on the next poll; a malformed line
  costs one `SOURCE_PARSE_FAILURES` and does not stop the valid records after it.
- **Clock skew.** Every timestamp is normalized to UTC. A record more than 120 s in
  the future is refused as `SOURCE_CLOCK_SKEW` rather than becoming zero-age activity.
- **Isolation.** The three sources are polled concurrently with per-source timeouts,
  so the ~350 ms ssh source cannot delay the ~5 ms local one. A failure is confined to
  its own source: health becomes `unavailable` with a bounded error code, its last
  known age is preserved, and the other two continue.
- **Persistence.** Only cursors, compact state and a version go to
  `.openditoo-local/activity-state.json`, written atomically via `os.replace`. No
  tokens, arguments, command bodies, usernames or raw log lines are stored or
  displayed.

## M9.5 Interface — `host/activity_render.py`

Three fixed indicators in horizontal bands; rows 0, 5, 10 and 15 are black, so no two
icons touch (asserted by test).

```
row 0        black separator
rows 1-4     OptiPlex MCP   [glyph cols 0-3][gap][age field cols 5-13][gap][health col 15]
row 5        black separator
rows 6-9     OptiPlex Lab
row 10       black separator
rows 11-14   WSL MCP
row 15       black separator
```

- **Identity** is a fixed 4x4 glyph in a fixed per-source colour: blue server box,
  violet flask, amber W. It never changes with state.
- **Age** fills the field: white pulse (new), green (<5 min), yellow (5-20 min), dim
  blue-grey (>=20 min), grey checkerboard (no reliable history — an explicit unknown
  pattern, not a dim "idle" lie).
- **Health** is a separate one-pixel column so a stale or unavailable collector is
  visible *through* a recent historical age: black healthy, red-orange stale, red
  unavailable, grey unknown. Red is used only for the error dimension.

Hand-authored logical pixels only — **no image generation**. Previews are written as
an exact 16x16 PNG plus a nearest-neighbour enlargement. The rendered frame encodes to
7 palette colours, well inside the demonstrated 255-colour limit, and decodes back to
the identical RGB888 through the existing `png16` decoder.

Animated GIF QA was skipped: with automatic device updates still gated on M8 there is
no animation to review yet.

## M9.6 Commands

- `openditoo activity-probe` — per-source reachability, record kind, seed-window size,
  parse failures and measured latency. Collection health only; says nothing about the
  device.
- `openditoo activity-status [--collect]` — normalized state plus the display view.
- `openditoo activity-preview [--collect] [--scale N]` — offline render to PNGs, with
  the legend, the packet hash the frame *would* produce, and which sources are pulsing.

All three report `device_io: false` and none can transmit.

## What is deliberately not built yet

- **No installed WSL worker** (M9.7). Automatic physical updates are gated on M8's
  repeated-frame primitive, which has no authority yet; a login-installed poller that
  cannot legally drive the display would be machinery with no consumer. The collector
  is already loop-safe and restart-safe, so adding the worker later is a small step.
- **No key navigation** (M9.6 optional): waiting on M7.
- **No device sends from the activity path at all.**

## Verification

`DAY1_OFFLINE_PASS artifacts=19 tests=51 host=typed_image port=8796 device_io=false
m4_completed=true m4_authorized=false m5_authorized=false`

22 new offline tests cover the M9 acceptance matrix rows that do not need the device:
seed-without-replay, incremental reads, torn final line, malformed line, truncation
gap, failed-call-is-activity, dispatch-is-not-completion, offset/nanosecond timestamp
parsing, lab message filtering and cursor advance, clock skew, one-source-unreachable
isolation, atomic state round-trip with version rejection, stale-not-idle, no-MCP-call
proof, age boundaries at exactly 5 and 20 minutes, future-stamp handling, icon
separation, health surviving a recent age, every age/health/pulse combination
encoding, pulse isolation, PNG round-trip, and no private endpoints in committed files.

Live sanity run against the three real sources: all reachable, and a genuine WSL MCP
call was observed and pulsed within one poll.
