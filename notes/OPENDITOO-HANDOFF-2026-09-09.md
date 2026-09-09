# OpenDitoo handoff — 2026-09-09

Written for a fresh session that will decide the next milestones from the repository.
**The repository is authoritative; this note is a map, not a transcript.** Where this
note and the code disagree, the code wins.

Snapshot, re-verified 2026-09-09 during the N1 documentation pass: `main` @ `d957bda`,
worktree clean apart from the untracked `OPENDITOO-FORWARD-ROADMAP-2026-09-09.md`.
`DAY1_OFFLINE_PASS artifacts=19 tests=79 host=typed_image port=8796 device_io=false`

The earlier snapshot line said `b86dfcb` / 78 tests. That was stale. The two commits after
`b86dfcb` (`cfedb2f`, `d957bda`) concern handoff preparation, routing and capability
wording only — **no M9 activation was completed**, and no new device evidence was added.
Offline verification is all that line asserts: not a Windows build, not installed-identity
re-verification, not transport acceptance, not visual acceptance.

Forward routing: the current sequence is **N1-N5** in
`OPENDITOO-FORWARD-ROADMAP-2026-09-09.md`. N1 (this reconciliation) is done; N2 (bounded
activity-session authority lifecycle) is in progress by another worker. M0-M8 are complete
and are not to be repeated.

## 1. What is accepted and proven

M0-M8 are complete on the exact purchased Ditoo Plus (`11:75:58:CE:DE:C7`, v42012).

| Milestone | State |
| --- | --- |
| M0-M5 | complete; first visible custom frame; authorities consumed |
| M6 static runtime + diagnostics | complete; physically accepted; pixel geometry proven |
| M7 keyboard/button mapping | complete **as a bounded negative**; no usable navigation input |
| M8 repeated frames | complete; rate ceiling measured and reproduced |
| M9 activity application | offline half complete; display integration **not started** |

### The product primitive

`exact 16x16 PNG → deterministic RGB888 → stock-derived 0x44 packet → Python/C# hash
agreement → authenticated fixed-target Windows Host → Ditoo`

Two live commands exist, both operator-invoked, neither able to retry or reconnect:

- `image-show` — one connection, three packets, one frame.
- `sequence-run --manifest <file>` — one connection, N frames from a reviewed manifest.
  It takes **no** frame, delay, target or packet arguments; everything comes from the
  manifest, every frozen hash is re-verified locally first, and it refuses a manifest
  with no authority or with authority already consumed.

### Accepted operating ceiling

**~1118 ms per frame (0.894 frames/s), measured twice.** ACK latency 99-124 ms, median
105 ms, no drift across 20 frames in two sessions, zero missing ACKs, zero errors.

This is the rate *measured and accepted*, not the fastest possible. It is the only rate
later automatic display work may use without a new grant. The official app's observed
148 ms floor is an observation about that app, not an earned rate.

## 2. Findings, with their confidence

**MATCHED (exact-unit):**

- Row-major, top-left-origin 16x16 geometry is physically correct. A 3 px asymmetry mark
  at rows 1-2 / cols 1-2 rendered in the top-left; combined with the frame reading
  upright this excludes all eight dihedral orientations.
- A displayed frame is **volatile across a power cycle** — the unit returns to stock and
  the default clock. It is display state, not a persisted boot selection.
- A frame otherwise persists **until stock takes the screen**, not on a timer. The
  brightness key cleared one.
- The unit accepts and renders repeated frames inside **one connection** with no
  reconnect, each answered by its own ACK.
- Physical controls that change device state cause **unsolicited** wrapped `0x04` reports
  on RFCOMM channel 1, with no request from the controller.
- Those reports are **state, not keystrokes** — they name a changed facility with no key
  identity, no press/release, no repeat.
- The wrapped `0x44` ACK payload is **not a success constant** (observed 0x12, 0x75,
  0xF0, 0xE5, 0x33, plus 20 distinct values across two loop runs).

**MATCHED_NEGATIVE:**

- Left arrow, right arrow and joystick produce **no traffic and no visible effect** under
  the tested context. They were the only symmetric navigation candidates.
- The ACK payload is **not a simple time-derived value**: over 18 intervals the inter-ACK
  interval varied ~3% while the increment varied ~35%; r=0.066.

**LEAD (do not build on):**

- The `0x09` one-byte report is either an absolute volume level or a key identifier.
  OpenTivoo independently concluded "absolute level" on Tivoo, which raises confidence
  but is class-5 comparative evidence and does not settle it here.

**Never inherited:** OpenTivoo command semantics. Its own `0x46` has no proven CW/CCW
identity, so there is nothing to import even if importing were allowed.

## 3. Consequence for the product: M9 keeps local navigation

M7's honest answer is that no usable physical navigation exists. The arrows are silent;
the keys that do report (volume, brightness, M) all carry a stock side effect and report
state rather than presses. A physical page cycle is **not deliverable** from this
evidence. This is a completed negative result, not an open task.

One genuinely useful pattern did fall out, and needs no new protocol semantics:

```
our frame is on screen → unsolicited 0x46 observed → the canvas is no longer ours
→ mark display state unknown; do not claim the last frame is still shown
```

## 4. Environment facts that correct earlier handoffs

**Capability is a property of your environment, not of the project. Verify every claim
below in your own session; inherit none of them.**

**Two sessions ran the same three checks on 2026-09-09 and got opposite results. That is
exactly why they are re-run, never inherited.**

- **From the local WSL Claude Code session that performed the N1 reconciliation
  (2026-09-09):** `powershell.exe`
  (`/mnt/c/Windows/System32/WindowsPowerShell/v1.0//powershell.exe`), `cmd.exe` and
  `dotnet.exe` (`/mnt/c/Program Files/dotnet//dotnet.exe`) are all reachable.
  `python3 cli/openditoo.py status` returned a healthy Host on `127.0.0.1:8796` — uptime
  ~1995 s, 3 operations since host start, `bluetoothTouched: false`.
  `python3 cli/openditoo.py activity-probe` reported all three sources `reachable: true`:
  `optiplex_mcp` 310 seed records / 305 ms, `wsl_mcp` 108 / 4 ms, `optiplex_lab` 0 / 161 ms.
  None of these three touches the device.
- **From the sandbox in which the forward roadmap was written (2026-09-09), the same three
  checks failed:** `command -v powershell.exe` exited 1; `status` returned HTTP 504 with no
  CLI result; `activity-probe` executed but reported all three sources `reachable: false`
  with `SOURCE_READ_FAILED`, including the local WSL source. Its execution context was
  bubblewrap with `write_scope=none` and network off.
- Neither result is a property of the project. A 504 is not proof the Host is down, and a
  reachable Host is not proof of anything about the device. Do not widen sandbox
  permissions or change source access controls to make a session pass.
- **From a local Claude Code session in WSL** (which produced the original handoff):
  the project builds over `\\wsl.localhost\...`, and loopback plus LAN both work. The
  post-M5 note's claim that build and deploy are operator-only was a property of the
  WSL_MCP sandbox, not of this environment.
- **From WSL_MCP**, expect less. Its `~/.config/wsl-mcp/config.toml` runs commands under
  bubblewrap with `default_network = "off"` and `fail_closed = true`, and it has
  historically had no Windows shell or SDK bridge. Under it, assume these may fail until
  proven otherwise: `powershell.exe` / `dotnet.exe`, reaching the Host on
  `127.0.0.1:8796`, and `ssh` to the OptiPlex for the two remote activity sources.
- **Cheap checks before planning around either:** `command -v powershell.exe`,
  `python3 cli/openditoo.py status`, `python3 cli/openditoo.py activity-probe`. All three
  are read-only and none touches the device.
- Repository work — parsing, fixtures, rendering, previews, tests, `verify_day1_offline.py`
  — needs none of the above and is unaffected.
- Bluetooth transmission is gated for **authority** reasons in every environment, never
  tooling. A session that *can* build and deploy still may not transmit.

- **Self-observation, if you run under WSL_MCP:** the M9 collector reads WSL_MCP's own
  audit log as the `wsl_mcp` source. Your own tool calls will therefore appear as genuine
  activity there. That is not a feedback loop — the collector reads a file and never calls
  an MCP server — but do not mistake your own footprint for a live user signal when
  interpreting `activity-status`.
- Deployed Host: `%LOCALAPPDATA%\OpenDitoo\Day1Host`, scheduled task `OpenDitoo Day1 Host`,
  at-logon, no terminal required. Installed DLL SHA-256
  `092ed38d4dd7aaeb3eedbdab15c2c0a0f8dac07ea6134545e18ad15398fa636c`, byte-identical to
  the repository's `bin/Release/net8.0` build. **That identity was verified at M6/M8 time.**
  It supersedes the older "the installed Host may still be the status-only build" text in
  `START_HERE.md` and `PROJECT_STATE.md`, but it is not a statement about the bytes
  installed right now: no installed-hash re-verification was performed during the N1
  documentation pass. Re-verify before any build-sensitive step; do not reinstall on the
  strength of this bullet either.
- The installed Host implements and advertises **two** typed image routes, `/v1/image/show`
  and `/v1/image/sequence` (capabilities `status`, `image-show`, `image-sequence`). The
  sequence route is an accepted, already-exercised M8 capability, not standing authority.
- `OpenTivoo Product Runtime` and port 8779 were preserved throughout and never touched.
  OpenTivoo has **active concurrent work**; treat it as read-only reference.

## 5. Authority state — nothing is currently authorized

Every experiment manifest is consumed. `manifest-check` on any of them reports
`execution_ready: false` with `transmission_authority_missing`, and `sequence-run`
exits 30.

**Every live operation — `image-show` included — needs a NEW reviewed manifest and an
explicit operator grant naming that manifest's experiment id.** `AGENTS.md` previously
carved out `image-show` as self-authorizing on explicit operator invocation; that
exception is superseded as of 2026-09-09 (N1) and `AGENTS.md` now states the stricter
rule. A consumed manifest is never re-armed: a failed, ambiguous or partially sent attempt
needs a fresh manifest and a fresh grant, never a reset flag. Build/deploy capability,
possession of the Host token, a reachable Host, process startup and prior successful
trials confer no transmission authority. In particular, continuous or unattended display
is a *larger* authority shape than any bounded run so far, and no bounded pass implies it.

### Known gap: enforcement depth (productization, not permission)

`sequence_run` checks the manifest's `transmission_authorized` / `authorization_consumed`
flags before dispatch, but it does **not** itself atomically consume or reserve that
authority, and the request it sends the Host carries frames and budgets rather than an
experiment identity. Consumption to date has been manual bookkeeping after the fact:
adequate evidence of what happened, not a crash-safe automatic gate, and not proof that a
crash mid-run leaves the authority unusable. Recorded honestly here as a gap.

Closing it is **N2**, currently in progress by another worker — it is not done. Until it
lands, do not describe the flag check as an end-to-end durable one-use gate, and do not
exercise the route in order to test it.

## 6. Local state that is NOT in git

- `.openditoo-local/` — Host token, activity source config with real endpoints, activity
  cursor state, generated previews.
- `captures/private/` — extracted btsnoop logs and parsed trial output.
- `bugreport-*.zip` in the repo root — three raw Android bugreports. **These were once
  untracked and un-ignored in a repo with a public remote**; they are now covered by
  `.gitignore` and were verified never to have been committed. Keep it that way.
- `examples/activity-sources.example.json` is the committed placeholder; a test forbids
  private addresses in committed files.

## 7. Open questions, with honest cost and value

| Question | Cost | Value | Recommendation |
| --- | --- | --- | --- |
| Did the operator see 10 alternating frames in either loop run? | one glance | closes `operator_visual_order: pending` on both loop manifests | ask once; ACKs already prove acceptance, only rendering is unconfirmed |
| Is `0x09` a volume level or a key identifier? | one 30 s stock trial: press minus 4x from mid volume | closes a LEAD | optional; gates nothing |
| What is the ACK payload? | unknown, likely several experiments | none | **do not pursue** — nothing depends on it and the CLI refuses to validate it |

## 8. Next objective — N5 first bounded activation, awaiting a grant

**N1-N4 are complete.** See `notes/OPENDITOO-N2-N4-ACTIVATION-READINESS-2026-09-09.md`
for the evidence; the short version:

- **N1** — routing and authority wording reconciled; the old `image-show` carve-out is
  superseded, and eight documentation contradictions are closed.
- **N2** — bounded session contract, durable one-use claim (`O_EXCL` in WSL, an
  append-only ledger written before the socket exists on the Host), and Host-side
  lifetime/pacing/budget enforcement by a watchdog the caller cannot cancel.
- **N3** — the link now reassembles a byte stream and classifies each report; an
  unsolicited state report ends the session with no reclaim frame, even when coalesced
  into the same read as the ACK. Change-only scheduling with burst coalescing, pulse
  freshness and a 1118 ms pacing floor. Nine shared receive cases agree between the WSL
  Python assembler and the compiled Host (`--selftest`).
- **N4** — three sources verified reachable from this environment; two scenario replays
  through render, scheduler and a fake transport, differing only in whether the unit was
  touched.

Verified on 2026-09-09, and kept distinct:
`DAY1_OFFLINE_PASS artifacts=19 tests=124 … m9_activation_authorized=false`;
`dotnet publish` Release PASS with `OPENTIVOO_TASK=preserved` and the installed runtime
unchanged; `HOST_SELFTEST_PASS cases=9 failures=0`. **No transport acceptance and no
visual acceptance** — neither was attempted.

### What blocks N5

`experiments/DAY1-M9-ACTIVATION-001-PENDING.json` is complete except for the grant.
It requests ONE bounded session: 300 s, change-only frames at no faster than one frame
start per 1118 ms, at most 269 frames / 807 packets / 51 379 application bytes, one
connection, no retry, no reconnect, no reclaim. `session-check` reports
`TRANSMISSION_AUTHORITY_MISSING` and `activity-session` exits 30 until an operator fills
`granted_by`, `grant_text` and `expires_at`.

Two preconditions beyond the grant:

1. **The installed Host is not the built Host.** Installed is `092ed38d…a636c` (M6-era,
   no session routes); the built and self-checked binary is `d3ece014…a042a`.
   `runtime/windows/refresh_openditoo_day1_host.ps1 -Apply` must be run and the installed
   hash re-verified. Only the dry-run has been performed.
2. The Android Divoom app must be disconnected — one controller owns the unit at a time.

### After N5

A1 installs collection (never display authority) under native supervision; A2 qualifies
faults and incrementally longer sessions under their own grants; A3 packages the
exact-unit release. L1-L3 stay parked.

Deliberately still not built, and why:

- No installed worker yet — startup would restore collection only, and there is nothing
  to supervise until an activation is accepted.
- No M7.4 custom receive window — it buys nothing until there is something to navigate.
- No rate above the accepted ceiling, and no reconnect policy.

## 9. Traps — do not redo these

- Do not re-run a consumed manifest by flipping `authorization_consumed`. Cut a new
  manifest with its own id; un-consuming destroys the record of what happened.
- Do not treat family resemblance as exact-unit truth, even when OpenTivoo agrees.
- Do not hand-transcribe capture bytes. One `0x46` payload was transcribed and silently
  lost a byte; report fields are now derived from `wire_hex` and a test re-derives them.
- Do not weaken a boundary test to accommodate new code. When `capture-parse` tripped the
  "no Bluetooth transport vocabulary in the CLI" guard, the command was reworded and the
  guard kept.
- One controller at a time is real: the first loop attempt failed at connect
  (`WSA=10060`) because the Android app still held the link. Zero bytes were sent, which
  is why it was safe to retry after the operator disconnected.
- `journalctl -o json` is incompatible with `--show-cursor`; use each entry's `__CURSOR`.
- L2CAP signalling identifiers are reused and CIDs are recycled after disconnect. Both
  bugs produced plausible-looking phantom frames in the btsnoop parser.
