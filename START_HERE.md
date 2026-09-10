# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

**Successor implementation location:** high-FPS interactive-page work is intentionally isolated on branch `feat/high-fps-interactive-pages` (current checkpoint `b2fd0e9`; core code `65723e6`). Do not merge its hash-bound runtime changes into live `main` before HF-3 physical acceptance; use the existing worktree under `.openditoo-local/worktrees/high-fps-interactive-pages` for successor work.

## Current session route — 2026-09-10

**Host re-bind (Runtime 007 + webcam 006):** the first-frame-spacing Host fix (streaming first-frame `IMAGE_RX_RECV_TIMEOUT` 5/19 vs activity 0/199). Status, grants and the cutover/rollback are in `notes/OPENDITOO-HOST-FIRST-FRAME-REBIND-2026-09-10.md`; `product-status` / the local policy id says which runtime is live.

**Current handoff (2026-09-10): physical button pagination is LIVE as Runtime 006.** Read `notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md` first, then `notes/OPENDITOO-HIGH-FPS-INTERACTIVE-PAGES-PLAN-2026-09-10.md`. Ditoo Left/Right page a wrap-around list and a short lever pull runs the page's own action; Runtime 006 is the accepted rollback baseline for the next work. The owner has explicitly reframed BTN-9: do **not** optimize the spiral as an end in itself. The active objective is a **general high-FPS interactive page runtime** on the existing `streaming_ack_clock` profile, with a small three-reel slots game as the first meaningful acceptance app. In parallel, prototype a richer MCP activity animation in which a lightning bolt descends into the active icon before the existing blue/cyan flare. Research/plan notes (`…BUTTON-AVRCP-RESEARCH…`, `…PAGINATION-PLAN…`) are history for BTN-0..6.

0. **Prior accepted product baseline:** after the current button handoff/plan, use `notes/OPENDITOO-HANDOFF-2026-09-10-W10.md` selectively — W10 is CLOSED: on-demand webcam (desktop shortcut,
   policy `OPENDITOO-WEBCAM-PRODUCT-005`, proven 6,307-frame run) and dashboard Runtime 005 (headless Host) are live. The W9 handoff below is history.
   Previous: `notes/OPENDITOO-HANDOFF-2026-09-10-W9.md`. W8 is closed PASS and
   W9A is done offline. **W9B is DEFERRED by owner decision (2026-09-10)** — do not re-propose, re-prepare
   or execute it; 007 stays prepared, grant-ready and unauthorized so revival costs one grant. Panel refresh
   and visible unique-frame cadence are therefore **UNMEASURED and stay that way** — never describe
   16.285 fps as what the panel does. Post-v1 >18.46 fps research stays closed by default, since its gate
   was W9B. **W10 productization is closed** — use `notes/OPENDITOO-W10-PLAN-2026-09-10.md` only as prior accepted implementation evidence:
   W10A (Studio app) and W10B (live W10-001 + W10-002) are **closed PASS**; W10-001/002 are consumed. W10C
   on-demand webcam (desktop shortcut → Studio → dashboard restored on close) moved to **one connection per launch**: 001 (granted, then revoked) hit IMAGE_RX_RECV_TIMEOUT on its 4th
   session reopen. Runtime 004 was superseded by **Runtime 005**, whose Host is `f7bd60d4…` and whose dashboard numbers remain unchanged; rollback history is preserved under `.openditoo-local/rollback-runtime-004/` and `.openditoo-local/rollback-runtime-003/`.
   `OPENDITOO-WEBCAM-PRODUCT-005` (Runtime 005 Host; live Look/Colours, Host-confirmed stock yield, Host-anchored pacing floor) is **GRANTED** (owner,
   2026-09-10) through the local mode-0600 policy only; 001–004 revoked. Desktop shortcut `OpenDitoo Webcam` is live. Revoke: `python3 host/webcam_studio.py policy-revoke`. See the W10 note. The W9 handoff lists the remaining lower-priority items.
   Then `notes/OPENDITOO-HANDOFF-2026-09-09-WEBCAM.md` for the earlier webcam handoff. Then
   `notes/OPENDITOO-WEBCAM-ROUTE-2026-09-09.md`. The external N980P webcam
   plan is adopted as the route, with recorded amendments. Runtime 003 is deployed;
   W5 fault injection is verified (route §13). The interrupted W6 adapter implementation has
   been recovered: source plus a successful Windows build checkpoint exist, while Windows-local
   staging/selftests, the pre-claim camera-ready handshake check and five-minute soak remain
   (route §15). W6 is therefore still an offline-verification boundary, not yet a grant boundary. Then read
   `notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`. It is the current
   route: the general 16x16 frame-streaming primitive is implemented, offline-verified and
   physically exercised once. `OPENDITOO-S1-STREAM-001` is **consumed** and may never be
   re-armed; any further live stream needs a fresh manifest and a fresh named grant.
1. Read `notes/OPENDITOO-STREAMING-HANDOFF-2026-09-09.md` for how streaming was scoped. MCP Dashboard v1 is closed.
2. **Then read `notes/OPENDITOO-HANDOFF-2026-09-09.md` selectively for exact-unit transport/rate evidence and historical traps.** It carries
   current state, the authority position, and an explicit warning about environment
   capability that matters if you are running under WSL_MCP rather than a local session
   with a Windows bridge.
3. Run the three read-only capability checks in the historical handoff section 0 **in your own session**.
   Do not inherit either previous session's answers; two sessions got opposite results on
   the same day.
4. Read `AGENTS.md` for the execution and authority boundary.
5. Run `python3 scripts/verify_day1_offline.py` before changing or executing anything.
6. Read `OPENDITOO-FORWARD-ROADMAP-2026-09-09.md` as historical planning context only; its pre-productization streaming deferral is superseded. N1-N5 and the
   R1-R5 rate ladder are complete; A1 is installed. See handoff section 8d for what is
   genuinely still open.
7. Read milestone evidence only as needed:

### Milestone state

| Milestone | State |
| --- | --- |
| M0-M8 | complete; accepted evidence preserved |
| M9 MCP activity application | complete; layout/activity/status/fault-display acceptance recorded |
| R1-R5 rate ladder | complete; measured through 18.46 fps full-colour one-ACK-per-frame ceiling |
| W4 streaming session profile | deployed under Runtime 003; installed/repository Host hash `0da3a18b...`; now physically exercised by successful W7 webcam trial |
| W5 fault injection | PASS: 11 camera-free cases + 5 real-camera/in-memory-Host controls; both parity fixtures pass; route §13 |
| W2 visual ranking | owner-dependent; harness complete, `srgb_area` remains provisional |
| W6 trial freeze | **PASS**: Windows-local selftests, camera-ready handshake negative control, 300.12 s soak, and final hash freeze complete |
| W7 first webcam acceptance | **PASS / consumed**: attempt 002 streamed 108 frames in 10.0145 s (~10.78 fps), clean lifetime expiry, owner visual PASS |
| W8 near-ceiling webcam rate | **PASS / consumed**: 005 completed its full 10 s lifetime — 163 frames / 489 packets / 170,737 bytes, **16.285 fps** (quarters 15.6/16.4/16.4/16.8), source age at send p95 51.86 ms, ACK p50 42.31 / p95 69.58 ms, 0 duplicate source frames, `lifetime_expired` / `stopped_clean`, Host ledger in exact agreement, no retry/reconnect/reclaim, Runtime 003 restored `connected`. owner visual PASS. **W8 closed PASS.** 003 and 004 remain consumed failures; all three are replay-forbidden |
| W9A source identity + motion truth | **implemented offline**: `SourceId` assigned once at acquisition, propagated unchanged through raw slot → transform → ready slot → sender selection; bounded `sourceIdentity` telemetry; offline control `ADAPTER_W9A_SOURCE_IDENTITY_PASS`; `host/motion_truth.py` + `tools/w9a_motion_truth_stimulus.html` decode all 4096 counters through the real production transform. Transport untouched. See route §27 |
| W9B optical unique-frame/latency trial | **DEFERRED by owner decision 2026-09-10** — do not start unprompted. Offline tooling and operator framing verified; attempt 006 consumed/unknown with no optical evidence; 007 prepared, grant-ready and unauthorized (no claim, no ledger entry). Revival costs one grant. See route §29-§30 |
| W10 webcam productization | **W10A done offline** (`OpenDitoo.Webcam.Studio`: preview with camera/mode, ROI/zoom, source + exact 16x16 matrix; absolute-deadline scheduler; duplicate/unchanged suppression with heartbeat; clean stop on Stop/close/unplug/stall; 17 C# checks + real-camera dry run). **W10B CLOSED PASS**: W10-001 (500 frames, 16.458 fps ACKed transport, budget end, owner visual "looked great") and W10-002 (live zoom/pan followed on the Ditoo, operator Stop → `operator_stop`/`stopped_clean`, 290 frames) — both consumed, Host ledgers identical, Runtime 003 restored. Panel refresh still UNMEASURED. Standing (multi-session) webcam authority is W10C, a separate owner decision, not built. See `notes/OPENDITOO-W10-PLAN-2026-09-10.md` |
| Post-v1 >ACK-ceiling research | **closed by default** — its gate was W9B, which is deferred, so the answer is no unless the owner reopens W9B first. Do not infer Tivoo's 30/54 fps results apply to Ditoo or reopen R1-R5 |
| S2 stream-rate measurement | `OPENDITOO-S2-STREAM-RATE-001` consumed. Measured dispatch→ACK: median 66 ms, p95 93 ms at 1039 bytes. Dispatching at the 150 ms Host floor is FATAL (HTTP 429 on frame 10) — client must add 50 ms margin, so ~5 fps is today's safe cadence. Higher rates need a Host pacing change + Runtime 003. See `notes/OPENDITOO-STREAM-PRODUCER-CONTRACT-2026-09-09.md` |
| S1 general frame streaming | **accepted**; `OPENDITOO-S1-STREAM-001` consumed, transport PASS (42 frames / 126 packets / 2982 bytes, clean close) and operator visual PASS |
| A1 collection worker | installed/preserved; product owns collection while active |
| P1 Runtime 001 | historical accepted evidence; superseded and deliberately no longer hash-valid |
| P2 Runtime 002 | telemetry accepted; superseded by Runtime 003 and deliberately no longer hash-valid |
| Runtime 003 | superseded 2026-09-10 by Runtime 004 (Host re-bind only); no longer hash-valid |
| Runtime 004 | superseded 2026-09-10 by Runtime 005 (pacing clock); no longer hash-valid |
| Runtime 005 | superseded 2026-09-10 17:44Z by Runtime 006; saved as rollback in `.openditoo-local/rollback-runtime-005/` (`scripts/cutover_runtime_006.sh --rollback`) |
| Runtime 007 | **active** (granted 2026-09-10, live 20:42Z): Runtime 006 re-bound to the first-frame-spacing Host `3faf520f…` (+ webcam 006); cutover `scripts/cutover_runtime_007.sh`, rollback `--rollback`. See the re-bind note |
| Runtime 006 | superseded 2026-09-10 20:42Z by Runtime 007; exact-byte rollback in `.openditoo-local/rollback-runtime-006/` (granted 2026-09-10 17:44Z): Runtime 005 envelope + button pagination, runtime_revision 3, same Host `f7bd60d4…` |
| P3 product evidence | closed for v1; normal MCP use accepted; forced healthy-Lab outage waived |
| P4 MCP Dashboard v1 package | prepared in `PRODUCT.md` + release closure note |
| BTN-0 AVRCP evidence reproduction | **PASS** (`BTN0_AVRCP_REPRODUCTION=PASS`): `host/avctp.py` + direction-scoped L2CAP channels in `host/btsnoop.py` + `capture-avrcp-parse` reproduce 0x4C/0x4B/0x4C/0x44 (all press+release, all ACCEPTED) from the raw M7 bytes; derived `captures/OPENDITOO-M7-AVRCP-KEY-SWEEP-2026-09-09.json`. New: the first Left coincided with an unsolicited RFCOMM 0x09 report (-2.7 ms), so arrows are not assumed session-neutral |
| BTN-1 Windows ButtonProbe | **PASS** (`BTN1_BUTTON_PROBE_OFFLINE=PASS`): `runtime/windows/OpenDitoo.ButtonProbe/` (hidden top-level HWND + SMTC primary; WM_APPCOMMAND, raw-input media-VK-only keyboard and HID consumer logged as separate sources, never merged). Built isolated to `%LOCALAPPDATA%\OpenDitoo\ButtonProbe` (dll `f758b922…`); selftest PASS; SMTC acquired; positive control (one injected media-Next) reached raw input + SMTC `Next`. Static test pins no transport/Host/credential/send code |
| BTN-2 exact Windows physical receive proof | **arrows PASS / lever PARTIAL** (`captures/OPENDITOO-BTN2-WINDOWS-RECEIVE-2026-09-10.json`): 6/6 arrow presses -> exactly one SMTC Previous/Next each, both trials; SMTC is the only Windows path (no WM_APPCOMMAND/raw input). 1 of 6 arrows (first Left, as in M7) came with RFCOMM 0x09 -> Runtime 005 canvas_invalidated -> ~1 s reconnect, invisible to the owner. Lever: trial A SMTC Pause only; trial B 0xBD only (Host yield + reclaim) |
| BTN-3 button broker | **PASS** (`BTN3_BUTTON_BROKER=PASS`): the ButtonProbe's NDJSON file (`.openditoo-local/button-events.ndjson`, epoch+seq) is the broker; `host/pagination.ButtonEvents` is a read-only at-most-once cursor (starts at EOF, drops repeats, counts gaps, new epoch = new baseline, SMTC source only). Real round trip: injected media-Next -> probe -> UNC file -> exactly one `nav_right` |
| BTN-4 two-page router | **PASS** (`BTN4_PAGINATION_OFFLINE=PASS`): `host/pagination.py` renders through Runtime 005's unchanged `run_product` (`renderer_factory` seam); page 0 = live dashboard renderer, page 1 = frozen `assets/pagination/spiral-10.rgb888` at 250 ms; page state survives a canvas_invalidated session end (proven offline). 320 tests PASS |
| BTN-5 physical pagination acceptance | **PASS (navigation) / consumed**: `OPENDITOO-PAGINATION-ACCEPTANCE-001` granted and run once (16:56Z): dashboard -> physical Right -> spiral -> physical Left -> dashboard, owner-confirmed; exactly 2 SMTC events / 2 transitions / 0 gaps, one Host session end to end (no invalidation, reclaim or reconnect), SMTC->first ACK 109 ms (Right) / 284 ms (Left), clean `operator_stop`, Runtime 005 restored. Live MCP pulse on the returned page NOT exercised in-window. Evidence `captures/OPENDITOO-BTN5-PAGINATION-ACCEPTANCE-2026-09-10.json`. Replay forbidden |
| BTN-7 lever | **short pull PASS with reclaim / long hold unreliable** (`captures/OPENDITOO-BTN7-LEVER-CHARACTERIZATION-2026-09-10.json`): with the probe in `--status mirror`, 8/8 short pulls -> exactly one SMTC event, alternating Pause/Play; every Play-direction pull also sends RFCOMM 0xBD -> Runtime 005 session end -> reclaim in 46-69 ms, invisible to the owner. Explains BTN-2 trial B (fixed 'Playing' status drops Play). Long holds gave 0xBD without SMTC and left the Ditoo in a 'recording' mode: never map holds |
| BTN-6 always-on pagination (Runtime 006) | **LIVE** — owner granted `Grant OPENDITOO-PRODUCT-RUNTIME-006` and cut over 17:44Z; smoke PASS (Right -> spiral, lever pause/resume, Right wraps to dashboard, twice; 0 input gaps, one lever `0xBD` reclaim). Untested: Spotify contention, webcam-shortcut suspend/restore under 006 |
| UI-1 MCP lightning successor | **offline PASS, not live**: 10-stage bolt-descend -> icon-impact -> blue/cyan aftershock; accepted no-pulse pixels unchanged; hidden-page pulses dropped rather than replayed |
| HF-1 high-FPS page primitive | **offline PASS** on `feat/high-fps-interactive-pages` (`65723e6`): generic `activity` / `streaming_ack_clock` page contract, buffered physical inputs, ACK-driven state, change-only output, 50 ms idle poll |
| GAME-1 slots | **offline PASS**: procedural 3-reel 16x16 game; successive short lever pulls stop L/M/R, fourth starts a new round; 1000 deterministic rounds |
| HF-2 profile orchestrator | **offline PASS**: one-controller activity <-> streaming transitions, 100 transition stress + 1000 mixed inputs; known canvas yield reclaims same page, ambiguity never retries |
| HF-3 one-use interactive acceptance | **prepared/dry-run PASS, NOT LIVE**: `OPENDITOO-INTERACTIVE-HF3-001`; 37/37 focused tests; 10-cycle dry-run = 21 opens / 81 ACKed frames / 60 inputs. WSL_MCP cannot see `/mnt/c` to re-verify installed ButtonProbe, so grant-ready/live remains blocked until normal local WSL re-runs preparation/check. Exact named grant still required |

### Authority state

Activations 001–009, R1–R5, S1 and S2 are consumed. No experimental one-shot transmission is live. The active MCP dashboard authority is the local git-ignored Runtime 006 policy (`OPENDITOO-PRODUCT-RUNTIME-006`); committed product templates remain unauthorized. The separately granted local webcam policy is `OPENDITOO-WEBCAM-PRODUCT-005`; it does not widen the dashboard policy. Neither existing product grant authorizes a new pagination/display behavior or new Bluetooth control surface. The one-use `OPENDITOO-PAGINATION-ACCEPTANCE-001` is consumed (PASS). The active dashboard authority is now `OPENDITOO-PRODUCT-RUNTIME-006` (local mode-0600 policy; committed template unauthorized); webcam policy is `OPENDITOO-WEBCAM-PRODUCT-005`.

BTN-0/BTN-1 are offline/receive-only preparation. Any later live pagination/display successor must follow `AGENTS.md` with a fresh reviewed policy/manifest and explicit named owner grant.

Historical authority bookkeeping remains preserved for verification: the superseded Runtime 002 cutover used the exact grant string `Grant OPENDITOO-PRODUCT-RUNTIME-002`. That historical grant does not authorize Runtime 005, webcam 004, or any button/pagination successor.

### Prior objective — W10 productization (CLOSED; W9B parked)

The MCP dashboard is already the owner's working everyday baseline. Do not reopen durability, firmware, MassBoot, ACK decoding, command enumeration, or speculative UI work as release blockers.

P2/P3/P4 and Runtime 003 deployment are closed. **W6 is now PASS and grant-ready**: the Windows
runner rebuilt/staged successfully, adapter/transform/encoder tests passed, the camera-ready nonce
negative control passed with no claim/Host session, and the real-camera allocation soak passed for
300.1216 s with only 9,416 bytes growth after warmup. Exact evidence is
`captures/OPENDITOO-WEBCAM-W6-WINDOWS-OFFLINE-RESULT-2026-09-09.json`. The coordinator refuses a
non-idle Host before one-use claim consumption. **W7 is now PASS.** Attempt 001 is preserved as a consumed zero-I/O pre-open failure caused by the status-contract client bug. Fresh attempt `OPENDITOO-WEBCAM-N980P-002` then completed the real 10-second webcam trial cleanly: 108 frames / 324 packets / 110,532 bytes in 10.0145 s (~10.78 fps), ACK p50 27.17 ms / p95 57.37 ms, no retry/reconnect/reclaim, terminal `lifetime_expired` / `stopped_clean`. The Host ledger independently records the same 108/324/110532 totals. The operator visually confirmed the live webcam feed genuinely worked on the Ditoo. Runtime 003 was restored and separately verified connected with a fresh active dashboard session. Attempt 002 is consumed and must never be replayed. **Next milestone is W8**, one separately reviewed near-ceiling ACK-clock characterization if useful; W7 authority does not carry forward.

**W8 attempt 003 is consumed and remains `unknown`.** It opened the reviewed Host session and ACKed two frames, then the third POST was rejected with `SESSION_PACING_VIOLATION`; client evidence is 2 frames / 6 packets / 2,102 bytes in 297.45 ms with no retry/reconnect/reclaim. The Host ledger closed its own session `stopped_clean` after the refusal, but the client/claim correctly preserves `unknown` because a live POST failed after open. Runtime 003 was restored and verified `connected`. The decisive correction is that a **40 ms client dispatch gap is not a 40 ms Host frame-start gap**: variable localhost serialization/request latency can make the next request reach the Host earlier relative to the prior one. Equal 40/40 floors therefore have zero arrival-jitter margin.

Fresh replacement `OPENDITOO-WEBCAM-N980P-004` proved the 50 ms pacing correction itself was viable: no `SESSION_PACING_VIOLATION` occurred. It reached **9 Host-ACKed frames / 27 packets / 9,420 bytes** before the client aborted for a separate telemetry bug. Client counters stopped at 8 because the ninth successful Host response was rejected by `HOST_FRAME_ELAPSED_INVALID`. The Host uses `Environment.TickCount64` for `hostFrameElapsedMs`; the client uses high-resolution `Stopwatch` in a separate process. Treating `hostFrameElapsedMs <= client HTTP round-trip + 10 ms` as a fatal invariant incorrectly compared independent clock domains/resolutions. Attempt 004 is consumed/unknown and replay-forbidden; Runtime 003 restored cleanly.

Fresh `OPENDITOO-WEBCAM-N980P-005` keeps the proven **50 ms client / 40 ms Host** pacing, same **201 / 603 / 211,854** hard limits, same camera/transform/Host protocol, and changes only telemetry validation: `hostFrameElapsedMs` must exist and remain within the reviewed **0..5000 ms ACK budget**, while the signed client-minus-Host elapsed residual is recorded observationally and never used as a cross-process ordering invariant. Offline regression includes a coarse-clock control that would have killed 004. Current suite is **274 tests PASS**. **W8 is closed on transport evidence: `OPENDITOO-WEBCAM-N980P-005` is consumed and PASS.** Preparation passed with zero device I/O, the exact grant was given, and one bounded run followed: 163 frames / 489 packets / 170,737 bytes in 10,009.43 ms (**16.285 fps**, per-quarter 15.6/16.4/16.4/16.8, no decay), ACK p50 42.31 / p95 69.58 ms, dispatch p50 60.47 ms, source age at send p50 36.99 / p95 51.86 ms flat by quarter, transform p95 3.66 ms, 0 duplicate source frames, both capacity-one queues at depth 1, 50.45 % latest-frame-wins replacement, terminal `lifetime_expired` / `stopped_clean` with no retry/reconnect/reclaim and no pacing violation. The Host ledger independently records the identical 163 / 489 / 170737, so the 004 client/Host divergence is resolved. Runtime 003 was stopped, the Host verified idle, and the dashboard restored and verified `connected` (`last_error=null`, run_nonce `8d6f0892`). Signed `clientMinusHostElapsedMs` (p50 1.14, p95 11.57, max 16.91 ms) is recorded as observational residual only — never a cross-process ordering invariant, and not HTTP overhead. **Transport FPS is not physical panel FPS**; visible unique-frame cadence and true scene-to-visible latency are exactly what W9A/W9B must establish. Owner visual observation is **PASS** ("looked great", no tearing versus the W7 baseline), so **W8 is closed PASS**. Attempts 002-005 are all consumed and replay-forbidden. See route §26. **Next milestone is W9A** — monotonic source identity plus a deterministic motion-truth stimulus, transport unchanged, and never retrofitted into the frozen 005 producer.

**Cross-project high-FPS planning update:** OpenTivoo's 30 fps work does not change W8-005 or Ditoo's measured R5 ceiling. Portable lessons are recorded in `notes/OPENDITOO-HIGH-FPS-CROSS-PROJECT-LESSONS-2026-09-09.md`. After W8 closes, W9A should add monotonic source-frame identity and a deterministic motion-truth stimulus; W9B should combine unique-frame observation with true scene-to-visible optical latency. W10 fixed-rate modes should use monotonic absolute-deadline scheduling, advance missed logical deadlines without catch-up bursts, and never treat duplicate/no-new-frame selection as a transmitted interval. Any attempt to exceed the existing one-ACK-per-frame shape is post-v1 and requires a separate concrete justification.

Use `PRODUCT.md` for normal operation. The reliable startup design boundary remains current-user Windows logon / StartWhenAvailable; a real Windows reboot/login observation is intentionally deferred and is not to be invented as accepted evidence.


## Historical Day-1 objective and milestone evidence

M0-M5 are complete through a visibly successful custom 16x16 frame. Current objective is the hardened plug-and-play MCP product runtime:

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

`OPENDITOO-M9-ACTIVATION-004` is consumed after one ACKed cyan frame (3 packets / 153 bytes). Frame 2 was refused HTTP 429 because the runner backdated its send start to the tick timestamp captured before slow live source collection. Dashboard visibility passed; four-stage animation and stock-yield remain NOT TESTED. The runner now re-samples monotonic time after rendering and at dispatch; a 350 ms slow-collection regression is pinned. `OPENDITOO-M9-ACTIVATION-005` is consumed; at that historical point no transmission authority was live.

### Activation 005 result / 006 pending — 2026-09-09

`OPENDITOO-M9-ACTIVATION-005` is consumed. The actual-dispatch timestamp fix worked: five frames / 15 packets / 765 bytes were ACKed before the operator pressed brightness. The animation was visibly active, but one sweep was too fast to confidently identify every color. The brightness press produced `canvas_invalidated / stopped_yielded_to_stock`, so **stock-yield is now PASS** and no reclaim occurred. Product source now runs **three visible sweeps** per activity event, collapsing duplicate cyan boundaries: 10 distinct ACK-gated frames at the 200 ms client cadence (~2.0 s total). Fresh visual-acceptance manifest: `OPENDITOO-M9-ACTIVATION-006`. **At that historical point, no transmission authority was live.**

### Activation 006 result / 007 pending — 2026-09-09

**At that historical point no transmission authority was live.** `OPENDITOO-M9-ACTIVATION-007` is consumed and may never be re-armed.

`OPENDITOO-M9-ACTIVATION-006` is consumed after a clean 30 s idle-hold run: one base frame, 552 unchanged holds, no activity event, so animation was not exercised. `OPENDITOO-M9-ACTIVATION-007` is the fresh deterministic visual trial: after the operator starts it and messages `RUNNING`, the assistant will perform one harmless read-only WSL_MCP call, creating a genuine audit event for the existing collector to animate. At that historical point no transmission authority was live.


### Activation 007 deterministic trigger result — 2026-09-09

`OPENDITOO-M9-ACTIVATION-007` is consumed after a clean deterministic live-trigger run: 31 ACKed frames / 93 packets / 4743 bytes over the full 30 s lifetime, zero dropped pulses and no pacing refusal. A genuine `wsl_mcp` audit event at 18:00:41Z occurred inside the session after the assistant's harmless read-only WSL_MCP call; the operator reported "yes the skull flashed". Deterministic trigger and visible animation are PASS. Individual cyan/blue/light-blue order remains PARTIAL because the operator did not explicitly confirm every color. Stock-yield remains PASS from 005; fault-bar remains NOT TESTED because no genuine source failure occurred. **At that historical point no transmission authority was live.**

### Activation 008 pending — accelerated green/yellow/red/grey acceptance

Production status semantics remain green <5 min, yellow 5-20 min, red >=20 min, and grey for no usable activity data. A test-only virtual-clock profile lets the exact device show those states as green 0-3 s -> yellow 3-6 s -> red 6-9 s -> grey from 9 s onward without changing production thresholds or persisted source state. Offline suite: **157 tests PASS**. `experiments/DAY1-M9-ACTIVATION-008.json` was historically authorized for exactly one bounded 15 s execution under `Grant OPENDITOO-M9-ACTIVATION-008`; that run is now consumed and PASS (four changed frames, hard ceiling 8). See `notes/OPENDITOO-MCP-STATUS-TRANSITION-ACCEPTANCE-2026-09-09.md`.


### Product decision after 007 — dashboard owns the display while connected

The operator does not intend to use the stock Ditoo UI. Future hardened product mode should therefore treat a physical-input stock takeover as transient: detect canvas invalidation, then deliberately reacquire the exact Ditoo and restore the MCP dashboard. This is a NEW unattended/reclaim authority shape and is not authorized by 008 or any earlier grant. It must preserve exact-target binding, single-controller ownership, bounded reconnect/backoff, no raw-send surface, and OpenTivoo isolation.


### Activation 008 result — status transitions physically accepted

`OPENDITOO-M9-ACTIVATION-008` is consumed and PASS. The test-only virtual-clock profile produced exactly four ACKed changed frames over 15 s (12 packets / 714 bytes), clean `lifetime_expired`, with 287 unchanged holds and no pacing/refusal. Operator observation: **all green → yellow → red → grey transitions were visible and looked good**. Production thresholds remain unchanged: green <5 min, yellow 5–20 min, red >=20 min; grey remains no usable activity data. At completion of 008, no standing product authority had yet been granted; that historical state is superseded by the current `OPENDITOO-PRODUCT-RUNTIME-001` grant.

Product decision recorded immediately after acceptance: stock UI is not desired while OpenDitoo owns the device. Future plug-and-play product mode should automatically restore the last/current MCP dashboard after a physical input causes stock takeover, rather than yielding until reconnect. This is a new product-runtime authority shape and is not authorized by 008.

### Persistent product runtime live acceptance — initial attach + stock reclaim — 2026-09-09

`OPENDITOO-PRODUCT-RUNTIME-001` is now installed under its local mode-0600 persistent policy. Windows installer reported `PRODUCT_SERVICE=ACTIVE`, `WINDOWS_STARTUP=AT_LOGON_START_WHEN_AVAILABLE`, and `INSTALL_STATUS=PASS_PRODUCT_RUNTIME`; the committed policy template remains disabled. The dashboard became physically visible without a manual activity-session invocation, so automatic initial attach is **PASS**.

Physical reclaim is also **PASS**. The operator pressed brightness once; the Ditoo briefly showed the stock clock and then automatically returned to the MCP dashboard. Runtime telemetry recorded `canvas_invalidated / stopped_yielded_to_stock`, `reclaims=1`, `reconnects=0`, `connected_sessions=1`, and advanced from product session `...000001` to `...000002`, proving this was immediate stock-screen reclaim rather than disconnect backoff.

Known observability defect: while a bounded product session is actively running, `product-status` remains at `status=connecting` because the supervisor persists that state before entering `run_session()` and receives no mid-session callback after Host open/first ACK. This is telemetry-only: physical display plus Host/session evidence prove attach/reclaim. Do not modify the hash-frozen live runtime in place; fix under a fresh reviewed product revision after live acceptance of reconnect/startup.

### Persistent product reconnect acceptance — 2026-09-09

Physical device power-cycle reconnect is **PASS** under `OPENDITOO-PRODUCT-RUNTIME-001`. With the Windows product service left running (same `run_nonce` `2066c485`, same `started_at`), the Ditoo was powered off long enough to force reconnect backoff and then powered on again. The MCP dashboard returned automatically with no Windows intervention. Runtime evidence after recovery: `connected_sessions=2`, `reconnects=4`, `session_sequence=6`; one failed epoch recorded `open_failed` / HTTP 502 before later recovery. Because the runtime state file is only persisted at session boundaries, live `status=connecting` and `last_error` may remain stale while a later session is visibly healthy; this is an observability defect, not a reconnect failure, and must be corrected only in a new hash-frozen product revision after startup acceptance.



### Activation 009 result — Lab fault bar physically accepted

`OPENDITOO-M9-ACTIVATION-009` is consumed and PASS. The frozen production-renderer sequence sent exactly three frames in one connection (9 packets / 494 application bytes, ACKs 0x61/0x99/0xF4, 6413 ms total): healthy Lab grey/no bar -> render-only simulated `source_health=unavailable` Lab grey + dim-red crown fault bar -> healthy Lab grey/no bar. Operator observation: **"saw it, looks good"**. This physically accepts the fault-bar appearance/path on the exact Ditoo. It remains correctly labeled simulated source-health acceptance; it does not prove that a genuine Lab outage is detected end-to-end. Persistent product authority remains separate and active.

### Locked MCP product baseline — 2026-09-09

The accepted MCP/product baseline is frozen in `notes/OPENDITOO-MCP-PRODUCT-BASELINE-FREEZE-2026-09-09.md`. Initial attach, stock-screen reclaim, device power-cycle reconnect, production green/yellow/red/grey aging, real WSL_MCP activity animation, and the simulated Lab fault-bar physical display path are accepted. `OPENDITOO-M9-ACTIVATION-009` is consumed. Standing `OPENDITOO-PRODUCT-RUNTIME-001` authority remains local and active. Do not modify hash-frozen product code in place. Windows reboot/logon autostart remains intentionally **PENDING** operator acceptance; a genuine source outage remains **NOT END-TO-END TESTED**. The live `product-status` `connecting`/stale-error issue is telemetry-only and is deferred to a fresh reviewed product revision.

### S1 general frame-streaming primitive implemented — awaiting first grant

The streaming transport already existed: `/v1/session/frame` takes an arbitrary 768-byte
RGB888 frame, and `run_session` is already a generic ACK-gated loop. The missing half was
the frame source, now `host/frame_stream.py` plus `stream-prepare` / `stream-preview` /
`stream-run`. **No Windows Host change was needed or made** — repository and installed DLL
verified byte-identical in-session at `fb750078...`. `host/activity_session.py` is
hash-frozen by the live Runtime 002 policy and was imported, never modified; MCP Dashboard
v1 is untouched.

This primitive's cadence ceiling is 200 ms / 5 fps, set by `MCP_CLIENT_FRAME_INTERVAL_MS`
inside that hash-frozen runner. Faster is a separate objective with its own boundary.

First live trial `OPENDITOO-S1-STREAM-001` is consumed and its transport result is PASS: one
connection, 42 ACKed frames / 126 packets / 2982 application bytes over a 12 s lifetime,
clean `lifetime_expired`, no refusals, supervisor stopped and restarted cleanly. 42 of 48
playback steps dispatched because measured ACK latency (~110–153 ms) sits close under the
200 ms client cadence; clock-indexed playback drops a step rather than stretching the clip.
A stream needing every frame should state `playback_interval_ms: 250` in its own manifest —
do not change the shared runner. Details:
`notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`.

### MCP Dashboard v1 closed — Runtime 002 accepted

`OPENDITOO-PRODUCT-RUNTIME-002` is now the active local standing product revision. Live cutover is PASS: `runtime_revision=2`, `status=connected`, first frame ACK recorded, session-open/ACK timestamps present, and `last_error=null`. P2/P3/P4 are complete; stop product-hardening work here. Windows reboot/login autostart observation is deferred and non-blocking. **Next objective: streaming and other OpenDitoo capabilities.**
