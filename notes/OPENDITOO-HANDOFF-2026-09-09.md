# OpenDitoo handoff — 2026-09-09

**The repository is authoritative; this note is a map, not a transcript.** Where this note
and the code disagree, the code wins.

Snapshot: `main` @ `4f93141`, clean.
`DAY1_OFFLINE_PASS artifacts=19 tests=148 host=typed_image port=8796 device_io=false
m4_completed=true m4_authorized=false m5_authorized=false ui=approved_mcp_page
m9_activation_authorized=false`

## 0. Read this first if you are the next session

**`OPENDITOO-M9-ACTIVATION-003` is currently authorized for ONE execution.** The prior
live experiments remain consumed. This grant names only the fresh 003 manifest: a 60 s
supervised MCP-dashboard acceptance at a 150 ms frame-start floor, fixed 10 ms packet
spacing, one connection, ACK-per-frame, no retry/reconnect/reclaim/pipelining. Never
re-arm a consumed manifest: un-consuming destroys the record of
what happened, and the durable claim would refuse anyway.

### If you are running under WSL_MCP, expect to do offline work only

The session that produced this handoff was a local Claude Code session in WSL with a
Windows bridge. **WSL_MCP is a different environment and historically has less.** Under it,
assume these may fail until you prove otherwise in your own session:

- `powershell.exe` / `dotnet.exe` — so **no builds, no installs, no Host refresh**
- reaching the Host on `127.0.0.1:8796` — so **no `status`, no transmission of any kind**
- `ssh` to the OptiPlex — so **two of the three activity sources go unavailable**, and the
  display will honestly render fault bars for them

Three cheap read-only checks settle it in seconds, and none touches the device:

```sh
command -v powershell.exe
python3 cli/openditoo.py status
python3 cli/openditoo.py activity-probe
```

**Verify; do not inherit.** Two sessions ran exactly these three checks on 2026-09-09 and
got opposite results — one found everything reachable, the other found none of it. That is
the whole reason they are re-run rather than assumed. A 504 is not proof the Host is down,
and a reachable Host is not proof of anything about the device.

**Self-observation:** the M9 collector reads WSL_MCP's own audit log as the `wsl_mcp`
source. Your own tool calls will appear there as genuine activity. It is not a feedback
loop — the collector reads a file and never calls an MCP server — but do not mistake your
own footprint for a user signal.

### What is fully available offline, whatever your environment

Repository work needs none of the above: parsing, fixtures, rendering, previews, the
generated UI data, the offline suite and `scripts/verify_day1_offline.py`. So are
`session-check`, `session-preview`, `manifest-check`, `image-prepare`, `frame-preview`,
`capture-parse` and `activity-status`/`activity-preview` without `--collect`.

**Bluetooth transmission is gated for authority reasons in every environment, never
tooling.** A session that *can* build and deploy still may not transmit.

## 1. What is accepted and proven

M0-M8 are complete on the exact purchased Ditoo Plus (`11:75:58:CE:DE:C7`, v42012).

| Milestone | State |
| --- | --- |
| M0-M5 | complete; first visible custom frame; authorities consumed |
| M6 static runtime + diagnostics | complete; physically accepted; pixel geometry proven |
| M7 keyboard/button mapping | complete **as a bounded negative**; no usable navigation input |
| M8 repeated frames | complete; rate ceiling measured and reproduced |
| M9 activity application | N1-N5 complete. 002 PASS: full 300 s, change-only, operator-confirmed. Stock yield and fault bar still untested |

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

**Sustained: ~131 ms per frame (7.63 fps) at full RGB888 colour**, measured by
`OPENDITOO-R4-MOTION-SUSTAINED-001`: 512 frames, 1536 packets, 536,576 bytes over 67
seconds on one connection, 512/512 ACKs, zero errors, clean close, operator-confirmed
smooth motion throughout.

| Run | Frames | Bytes/frame | Interval | Rate |
| --- | --- | --- | --- | --- |
| M8 baseline | 10 | 71 | 1114.1 ms | 0.90 fps |
| R1 (250 ms delay) | 10 x3 | 71 | 371.6 ms | 2.71 fps |
| R2a (50 ms delay) | 10 | 71 | 175.4 ms | 5.70 fps |
| R2b (10 ms spacing) | 10 | 71 | 109.3 ms | 9.15 fps |
| R3 (full colour) | 10 | 1054 | 118.2 ms | 8.46 fps |
| R4 (sustained) | 512 | 1048 | 131.0 ms | 7.63 fps |
| **R5 (no sleep)** | **1024** | **1048** | **54.2 ms** | **18.46 fps** |

Four things these settled, in order of importance to a streaming product:

- **Full-colour frames are nearly free.** 14.8x the bytes cost 8.9 ms per frame. Marginal
  throughput is about 107 KB/s, so at 16x16 even a maximum-palette frame is not the
  constraint. Bytes were never the bottleneck; our own pacing was.
- **Sustained streaming holds.** 67 seconds continuous with quarter means of 130.5, 128.5,
  132.4 and 132.7 ms and flat ACK medians. No throttling, no degradation. Nothing is
  claimed beyond one minute.
- **Short bursts overstate the sustainable rate by about 11 %** (131.0 vs 118.2 ms at
  identical timing). Budget streaming at **7.6 fps**, not 8.5.
- **The stock 40 ms send spacing is not load-bearing** down to 10 ms. It was the only
  timing value taken from observed stock behaviour rather than chosen by us.

**Ceiling: 18.46 fps at full colour**, measured by `OPENDITOO-R5-NOSLEEP-CEILING-001` over
1024 frames and 1.07 MB in 56 s, with quarter means of 54.1/54.1/54.1/54.4 ms and no
tearing. That is the ceiling *for this protocol shape*: with no waits of ours left, the
interval IS the ACK round trip, so nothing remains to remove without abandoning one ACK
per frame. 20.5x the original accepted rate.

Two caveats on using it. The device is about 20 % slower per turnaround when denied idle
time (44 -> 53 ms), which is real but far cheaper than the 70 ms of waiting removed. And
jitter is now ~28 % of the interval, with a 111 ms worst frame against a 53 ms median, so
content assuming constant cadence should run **below** the ceiling.

**Recommended operating rate: 6-7 fps** for the activity display, which is change-only and
sent six frames in 300 seconds. Streaming can use the full 7.6 fps, but at ~131 ms the
jitter is now dominated by Windows `Thread.Sleep` granularity (~15.6 ms), so further gains
mean not sleeping at all -- letting the ACK be the clock -- rather than sleeping less.

**Wired offline after the ladder:** the activity-product source now chooses **150 ms per
frame start (6.67 fps)** and the Host source fixes intra-frame packet spacing at the
physically accepted 10 ms. Four ACK-gated cyan/blue/light-blue/cyan stages take ~0.60 s.
The runner measures cadence start-to-start, so transport/ACK time consumes the interval
instead of being added to it. Source collection remains at its configured multi-second
cadence rather than running at 6.67 Hz. See
`notes/OPENDITOO-ACTIVITY-RATE-INTEGRATION-2026-09-09.md`. This is **source/offline
verification only** in the implementing WSL_MCP session: no Windows build/install or new
physical acceptance was possible there.

**Correction carried by R1:** the `ackLatencyMs` recorded since M6 is
`ackAt - frameStartedAt` and therefore **includes** the send spacing our own transport
inserts between a frame's three packets. Anything reasoning about achievable rate must
subtract it.

This is still the rate *measured and accepted*, not the fastest possible; it is the only
rate later display work may use without a new grant. The official app's observed 148 ms
floor remains an observation about that app, not an earned rate.

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

## 5. Authority state — activation 003 authorized for one execution

`OPENDITOO-M9-ACTIVATION-001` and `-002` were each granted and executed once on
2026-09-09. Both are consumed. 002 passed to its full lifetime; a spent grant is spent
either way. Any further trial needs a new manifest with a new experiment id under a new
grant. See section 8a for what they proved and what they did not.

Every experiment manifest is now consumed. `manifest-check` on any of them reports
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
  into the same read as the ACK. Change-only scheduling with burst coalescing and pulse
  freshness was physically accepted at the then-current 1118 ms floor. That historical
  floor is now superseded for future product source by the offline 150 ms integration
  described below; the old trials remain evidence of what actually ran. Nine shared
  receive cases agree between the WSL Python assembler and the compiled Host (`--selftest`).
- **N4** — three sources verified reachable from this environment; two scenario replays
  through render, scheduler and a fake transport, differing only in whether the unit was
  touched.

Verified on 2026-09-09, and kept distinct:
`DAY1_OFFLINE_PASS artifacts=19 tests=124 … m9_activation_authorized=false`;
`dotnet publish` Release PASS with `OPENTIVOO_TASK=preserved` and the installed runtime
unchanged; `HOST_SELFTEST_PASS cases=9 failures=0`. **No transport acceptance and no
visual acceptance** — neither was attempted.

## 8a. N5 activation — two trials, complete

Full records in `experiments/DAY1-M9-ACTIVATION-001.json` and `-002.json`.

**001 (2026-09-09, partial).** Visual acceptance PASS, but the session ended at 30.4 s on
our own defect: `WorkerSilenceGraceMs` inferred worker liveness from *frames*, and a
change-only display legitimately sends none. Thirty seconds of correct silence read as a
dead worker. The worker, which could only learn the session state by sending, then polled
127 s longer believing the display was live. A second defect: the worker counted 132
application bytes per frame to the Host's 147, omitting the two stock preambles.

**002 (2026-09-09, PASS).** Ran its full 300 s granted lifetime and closed cleanly.

| Criterion | Result |
| --- | --- |
| Transport | **PASS** — 1 connection, 6 frames, 18 packets, 1032 bytes, six wrapped `0x44` ACKs, clean close, zero retries/reconnects |
| Visual | **PASS** — operator: *"I could see the skull animate blue when signal came through. looks great."* Photograph shows the approved page rendering |
| Change-only | **PASS** — 6 frames against 248 unchanged holds over 300 s; 1032 bytes against a 54 607 ceiling, under 2% |
| Pacing | **PASS by enforcement** — the Host 429s anything under 1118 ms and none occurred. Not measured: the session route records no per-frame timings |
| Liveness regression | **PASS** — ended `lifetime_expired`, not `worker_silent`, through 248 silent polls. The 001 defect is fixed on hardware |
| Stock yield | **NOT TESTED** — no control touched |
| Fault bar | **NOT TESTED** — no source failed during the session |
| Collection survives | **PASS** |
| Authority consumed | **PASS** — a second run was attempted while the manifest was *still armed*; the durable claim refused with `AUTHORITY_ALREADY_CONSUMED`, exit 30, before any transport contact |

Worker and Host independently recorded identical figures this time. In 001 they disagreed
on both the byte count and the terminal reason; both are confirmed fixed on the device.

### Colour rendition — mostly closed

A photograph of 002 made the idle column look blue, though the frame contained pure
neutral values. **Resolved by operator observation: the panel renders greys correctly and
the cast was the phone camera.** The design's grey-versus-blue distinction is intact and
needs no change.

Red, green, yellow and neutral greys/whites are now all confirmed rendering as themselves
on this panel. **Magenta and cyan remain unverified**, so M6's "complete colour rendition
NOT confirmed" caveat is narrowed, not closed.

Worth keeping as a method note: a phone auto-white-balancing a dark scene against
saturated LEDs will shift neutrals. Photographs are evidence of layout and change, not of
colour.

### Both trials' grants are consumed

At that historical point both grants were consumed. The fresh 003 trial below now has its
own separate one-execution grant; 001 and 002 remain consumed.

## 8b. A1 collection worker — installed 2026-09-09

A systemd **user** timer runs `activity-status --collect` every 30 s. Collection only:
the unit cannot transmit, the installer refuses to install one that could, and the
offline verifier fails if a transmitting command or `PrivateTmp` ever appears in it.
Login, boot and restart produce zero Bluetooth operations. Uninstall preserves
`.openditoo-local`, `captures/` and OpenTivoo. Details in section 9 of the N2-N4 note.

## 8c. The rate ladder — complete, and where it stopped

R1 through R5 all ran and were accepted on 2026-09-09. Full records in `experiments/`.
The ladder is **finished for this protocol shape**: at 54 ms the interval *is* the ACK
round trip, so nothing remains to remove without abandoning one ACK per frame.

Going faster would mean pipelining — sending frame N+1 before frame N is acknowledged.
That is a different protocol shape, it discards the per-frame confirmation every safety
property here depends on, and **nothing has asked for it**. It is not prepared and should
not be prepared speculatively.

`sequence-run` now takes the same durable one-use claim as the activity session, closing
the enforcement-depth gap this note used to record as open.

## 8d. Genuinely open, in rough value order

**Rate integration is complete offline.** Future activity-session source uses a 150 ms
frame-start floor (6.67 fps), 10 ms accepted intra-frame spacing, and the approved four
ACK-gated pulse stages. `DAY1_OFFLINE_PASS ... tests=151`; no device I/O occurred. The
changed Windows Host has **not** been built or installed from this WSL_MCP environment, so
the next physical boundary begins with build/installed-identity verification, not a send.

1. **Stock yield and the fault bar — both still `NOT TESTED` on hardware.** Neither can be
   forced: they need the operator to touch a physical control during a live session, or a
   source to genuinely fail. Do not manufacture a fake failure to close them; that would
   test the mock, not the device. Ride them along on a future authorized session.
2. **Streaming beyond one minute.** The longest run is 56 s. Ten minutes is a different
   question — thermal behaviour, drift, resource growth — and has not been asked.
3. **`operator_visual_order` on the two M8 loop manifests** is still `pending`. One glance
   closes it; if the operator cannot recall, leave it pending rather than recording a
   recollection as evidence.

Parked and explicitly not to be revived without a trigger: L1-L3 in the forward roadmap,
MassBoot and service-mode research, and any delta or partial-frame command (finding one
means command enumeration, which is prohibited).

## 9. Traps — do not redo these

- **Do not compare an ACK latency against a rate budget without subtracting your own
  sleeps.** `ackLatencyMs` is `ackAt - frameStartedAt` and includes the inter-packet send
  spacing. Believing it was device turnaround produced a confidently wrong conclusion that
  10 fps required abandoning per-frame acknowledgement. It did not.
- **Do not size a response read by a fixed constant.** A 512-frame result is ~90 KB; a
  64 KB cap truncated it, `json.loads` raised, and a fully successful run was reported as
  `HOST_UNAVAILABLE`, consuming real authority against an outcome that was false. Reads
  are now bounded at 8 MB and detect truncation explicitly.
- **Do not trust a ten-frame sample as a sustainable rate.** Bursts overstate it by ~11 %.
- **A photograph is evidence of layout and change, not of colour.** A phone
  auto-white-balancing a dark scene against saturated LEDs shifted neutral greys to blue
  and nearly produced a phantom finding; the operator's eye settled it in one glance.
- `PrivateTmp=true` on a systemd unit that uses `ssh` breaks it: inside the mount
  namespace `ssh` rejects `/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` with
  `Bad owner or permissions` and exits 255. It cost two of three activity sources and
  looked like routine hardening.

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


## 8e. MCP dashboard rate-integrated activation — prepared 2026-09-09

Windows deployment and preconditions are now verified for source commit `d1d72d8`: `WINDOWS_BUILD=PASS`, `REFRESH_STATUS=PASS_TYPED_IMAGE`, OpenTivoo preserved; repository and installed Host DLL are byte-identical at `fb750078e9f5d8e763e57e2f58d8a79b1faff1d886d2d04946274a29dd9af70f`; normal WSL `/v1/status` is healthy with `activity-session`; all three MCP sources are reachable.

Fresh manifest: `experiments/DAY1-M9-ACTIVATION-003.json`, experiment id **`OPENDITOO-M9-ACTIVATION-003`**. It is a 60 s supervised MCP-dashboard acceptance at the current 150 ms frame-start floor and fixed 10 ms packet spacing, max 401 frames / 1203 packets / 81403 bytes, one connection, ACK-per-frame, no retry/reconnect/reclaim. **Operator grant received in-session on 2026-09-09; exactly one execution is authorized and not yet consumed.** The operator should observe one complete four-stage pulse and then press one physical Ditoo control to test stock-yield. Streaming/pipelining is tabled until the dashboard milestone is complete.


## 8f. Activation 003 result and 004 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-003` is consumed. It sent exactly one dashboard frame (3 packets, 153 application bytes) and then the worker received HTTP 429 from the Host pacing guard. The Host recorded `transport_fault / stopped_clean`; the worker recorded an unknown transport outcome. Root cause is cross-process timing: dispatching exactly 150 ms client start-to-start does not guarantee 150 ms Host arrival-to-arrival because HTTP latency varies. The dashboard itself was physically visible. The four-stage pulse was not observed. The operator pressed brightness only after the session had already stopped, so the resulting stock clock is **not** stock-yield acceptance.

The client fix keeps the Host's hard 150 ms floor but uses a nominal **200 ms MCP send cadence** with a phase-stable **50 ms render tick**. This leaves 50 ms timing headroom and produces a ~0.8 s four-stage pulse. Offline verification passes 152 tests. Fresh manifest: `experiments/DAY1-M9-ACTIVATION-004.json`. `OPENDITOO-M9-ACTIVATION-004` is consumed. Streaming remains tabled until MCP dashboard acceptance is complete.


### Activation 004 result / 005 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-004` is consumed after one ACKed cyan frame (3 packets / 153 bytes). Frame 2 was refused HTTP 429 because the runner backdated its send start to the tick timestamp captured before slow live source collection. Dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The runner now re-samples monotonic time after rendering and at dispatch; a 350 ms slow-collection regression is pinned. `OPENDITOO-M9-ACTIVATION-005` is consumed; no transmission is currently authorized.

### Activation 005 result / 006 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-005` is consumed. The actual-dispatch timestamp fix closed the 003/004 pacing defect: five frames / 15 packets / 765 bytes were ACKed. The operator visibly observed animation but reported that the single cyan→blue→light-blue→cyan sweep went too quickly to confirm every color. After the operator pressed brightness, the worker recorded `canvas_invalidated / stopped_yielded_to_stock`, `display_state=unknown_not_ours`; the unit returned to the stock clock and no reclaim frame was sent. **Stock-yield is now physically accepted.**

Operator product decision: each activity event should cycle a few times. Source now runs three visible sweeps; identical cyan boundaries are collapsed so an ACK-gated animation cannot stall on an unchanged frame. That is 10 distinct frames at the 200 ms MCP send cadence, about 2.0 s total. Offline verification remains green. `OPENDITOO-M9-ACTIVATION-006` is currently authorized for exactly one bounded visual-acceptance execution under the operator grant `Grant OPENDITOO-M9-ACTIVATION-006`; no other transmission is authorized. **At that historical point, no transmission authority was live.** Streaming remains tabled until the dashboard is accepted.
