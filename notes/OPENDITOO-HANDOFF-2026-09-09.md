# OpenDitoo handoff — 2026-09-09

Written for a fresh session that will decide the next milestones from the repository.
**The repository is authoritative; this note is a map, not a transcript.** Where this
note and the code disagree, the code wins.

Snapshot: `main` @ `b86dfcb`, clean, pushed.
`DAY1_OFFLINE_PASS artifacts=19 tests=78 host=typed_image port=8796 device_io=false`

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

**Capability is a property of your environment, not of the project. Verify, do not
inherit either claim below.**

- **From a local Claude Code session in WSL** (which produced this handoff):
  `powershell.exe`, `cmd.exe` and `dotnet.exe` are reachable, the project builds over
  `\\wsl.localhost\...`, and loopback plus LAN both work. The post-M5 note's claim that
  build and deploy are operator-only was a property of the WSL_MCP sandbox, not of this
  environment.
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
  the repository's `bin/Release/net8.0` build.
- `OpenTivoo Product Runtime` and port 8779 were preserved throughout and never touched.
  OpenTivoo has **active concurrent work**; treat it as read-only reference.

## 5. Authority state — nothing is currently authorized

Every experiment manifest is consumed. `manifest-check` on any of them reports
`execution_ready: false` with `transmission_authority_missing`, and `sequence-run`
exits 30.

**Any new live operation needs a new manifest and an explicit operator grant naming its
experiment id.** In particular, continuous or unattended display is a *larger* authority
shape than any bounded run so far, and no bounded pass implies it.

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

## 8. Next objective

**M9 display activation.** The offline half is done and tested: collector, normalized
state, renderer, previews and CLI (`activity-probe`, `activity-status`,
`activity-preview`). What remains is continuous operation, which is exactly the part
that needs a new authority shape.

A next session should expect to write an activation manifest covering at minimum:

- a bounded session lifetime and a defined activation source;
- **send a frame only when the rendered image actually changes** — the accepted ceiling
  is a ceiling, not a heartbeat;
- the `0x46` canvas-invalidation fence above;
- a fault policy where a Bluetooth fault stops the display while collection keeps running;
- no replay of queued animation after any interruption — show current state only;
- the WSL worker install and a sign-out/restart acceptance.

Before widening scope, note what is deliberately **not** built and why:

- No installed worker yet — it would have had no display to drive.
- No M7.4 custom receive window — proven useful on Tivoo, plausible here, but it buys
  nothing until there is something to navigate.
- No rate above the accepted ceiling.

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
