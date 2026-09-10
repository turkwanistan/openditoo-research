# OpenDitoo — high-FPS interactive pages + MCP lightning plan — 2026-09-10

**Status:** adopted owner priority; implementation may proceed offline/autonomously. Live Runtime 006 remains the accepted rollback baseline until a successor is separately reviewed and granted.

**Location:** implementation and the HF-3 manifest currently live on `feat/high-fps-interactive-pages`; `main` carries this steering note only so fresh sessions can route into the isolated worktree without invalidating Runtime 006.

## Implementation checkpoint — 2026-09-10

Implementation is isolated on branch/worktree `feat/high-fps-interactive-pages`; core implementation checkpoint `65723e6`; live `main` remains the Runtime 006 rollback baseline and its hash-bound runtime files have not been changed. **No successor device transmission has occurred.**

Current offline gates after the HF-3 freeze pass:

- `UI1_LIGHTNING_OFFLINE=PASS` — 10 distinct ACK-gated spatial stages: bolt descent -> icon impact -> cyan/blue/light-blue aftershock. Fault precedence and simultaneous-source composition are covered; no-pulse output remains byte-identical to the accepted renderer. Hidden-page activity is collected into current MCP status but its visual pulse is deliberately dropped so no stale lightning replays on return.
- `HF1_INTERACTIVE_PAGE_PRIMITIVE=PASS` — buffered at-most-once inputs survive page/profile boundaries; high-rate pages use the existing one-frame-in-flight `streaming_ack_clock` transport; navigation stops a child session cleanly; state survives exact known canvas-yield/reopen; stationary output is change-suppressed. Interactive stationary pages use a 50 ms idle control poll rather than the generic 10 ms stream heartbeat, reducing no-pixel-change control traffic about fivefold without changing moving-frame ACK cadence.
- `GAME1_SLOTS_OFFLINE=PASS` — procedural 16x16 three-reel page, 1000 deterministic rounds, successive short pulls stop left/middle/right exactly once, stopped reels remain stable, the fourth pull starts a new round, state survives session/page re-entry, and result frames hold without resend.
- `HF2_PROFILE_ORCHESTRATOR=PASS` — 100 wrap-around profile transitions and 1000 mixed inputs consume exactly once; exactly one child session/controller is active; the exact-unit `canvas_invalidated/stopped_yielded_to_stock` outcome from BTN-2/BTN-7 is a same-page reclaim, while ambiguous/non-reviewed failures terminate immediately with no retry. MCP collection continues in the background while a high-rate page owns the panel.
- `HF3_ACCEPTANCE_ENVELOPE_OFFLINE=PASS` — executable one-use boundary `OPENDITOO-INTERACTIVE-HF3-001` is implemented and hash-frozen. Outer limits: 90 s, 28 child-session attempts, 500 ACKed frames, derived byte ceiling, 20 frames per activity child, 120 per streaming child, activity + streaming profiles only, no raw-send/pipelining/target override, no retry after ambiguity. Live coordinator restores Runtime 006 and verifies it returns to `connected`.
- Canonical successor gate: `python3 scripts/verify_interactive_pages_offline.py` -> **37/37 PASS**.
- Deterministic HF-3 dry-run: **PASS** — 10 complete Dashboard <-> Slots cycles, 21 child opens (including the final Dashboard return), 81 ACKed frames, 60 unique physical-input events, and 60/60 inputs correlated to a strictly later transport ACK; simulated high-rate ACK cadence is ~18.18 fps. This is transport/runtime simulation, not panel-FPS evidence.
- Offline preview generation: `python3 scripts/render_interactive_page_previews.py` -> PASS, using project/stdlib PNG output only; no image generation.
- Existing `python3 scripts/verify_day1_offline.py` still runs all 322 legacy tests and stops only on the same two deferred W9B Pillow imports (`ModuleNotFoundError: PIL`) in WSL_MCP, with six environment skips. No successor regression is exposed by that run.

HF-3 preparation artifact: `experiments/DAY1-INTERACTIVE-HF3-001.json`; latest offline-prepared manifest SHA-256 after the freeze pass is `7ad8ef4d3eba00e8c4170757868be55e29b046e72b2dd448661bad0ca4184a23`. Preparation evidence is `captures/OPENDITOO-INTERACTIVE-HF3-001-PREPARATION-2026-09-10.json`. The tracked manifest remains **unauthorized and unconsumed**.

**Current blocker / next boundary:** WSL_MCP's bubblewrap environment cannot see the installed Windows ButtonProbe under `/mnt/c`, so it cannot honestly re-verify the staged `.exe/.dll` against Runtime 006 and therefore cannot declare HF-3 grant-ready. From a normal local WSL session with Windows interop, re-run `python3 scripts/prepare_interactive_hf3.py` and `python3 scripts/interactive_hf3.py check`; they must directly verify the installed ButtonProbe bytes. Only then may the exact named grant `Grant OPENDITOO-INTERACTIVE-HF3-001` be recorded and `scripts/run_interactive_hf3.sh` invoked. General/wildcard development approval is not that named one-use grant.

## Grant/execution checkpoint — 2026-09-10

The owner issued the exact named grant `Grant OPENDITOO-INTERACTIVE-HF3-001` after the frozen HF-3 manifest (`7ad8ef4d…`) was presented. WSL_MCP then attempted the real grant command. It failed closed **before any authority mutation or outer claim** because this bubblewrap session has no `/mnt/c` and therefore cannot directly re-hash or launch the installed ButtonProbe. Network-enabled WSL_MCP can reach the exact authenticated Host at `127.0.0.1:8796`; Runtime 006 is live and its policy names the same ButtonProbe digest values as HF-3, but the HF-3 verifier intentionally still requires direct installed-byte verification before materializing authority. No device/session I/O occurred and HF-3 remains unconsumed. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-001-GRANT-BLOCKED-2026-09-10.json`.

**Next capable local WSL session:** in this feature worktree run `python3 scripts/interactive_hf3.py check`, then materialize the already-issued exact grant with `python3 scripts/interactive_hf3.py grant 'Grant OPENDITOO-INTERACTIVE-HF3-001'`, then `bash scripts/run_interactive_hf3.sh`. Do not use `--sandbox-skip-probe` for grant/run. If direct installed-byte verification fails there, stop; do not weaken or bypass the verifier.

## 1. Goal

Turn the physical-button pagination proof into a reusable interactive application platform rather than optimizing one spiral asset.

The target product model is:

`Ditoo Left/Right/short-lever -> AVRCP -> Windows SMTC -> ButtonProbe -> page controller -> page-specific renderer/input state -> selected Host session profile -> exact Ditoo`

A page may be either:

- **informational / low-rate** — existing `activity` session behavior, change-only, nominal 200 ms dispatch; or
- **interactive / high-rate** — existing `streaming_ack_clock` profile, one frame in flight, one ACK per frame, no pipelining, latest state rendered immediately after each ACK.

High-FPS is therefore a page capability, not a special animation/GIF mode.

## 2. Preserve these accepted boundaries

- Exact target remains Ditoo Plus `11:75:58:CE:DE:C7`, firmware `v42012`.
- Runtime 006 is the live accepted dashboard/button baseline and rollback target.
- `OPENDITOO-WEBCAM-PRODUCT-005` remains a separate granted authority and its hash-frozen Studio/Host bytes must not drift accidentally.
- One RFCOMM controller owns the Ditoo at a time.
- Reuse the existing typed Host and the already-proven `streaming_ack_clock` profile; do not add raw-send, target override, firmware, MassBoot, USB, pipelining, or a second Bluetooth stack.
- Arrow `0x09` and lever `0xBD` reports remain canvas/session invalidation evidence handled by reclaim/transition logic; do not special-case them as harmless without evidence.
- Never map long lever holds; BTN-7 showed they can enter stock recording behavior.
- Do not describe measured transport FPS as panel-visible unique-frame FPS. W9B remains deferred unless the owner explicitly reopens it.
- New live display behavior still requires a fresh reviewed manifest/policy and the exact named grant required by `AGENTS.md`. General permission to develop does not re-arm consumed identities.

## 3. Performance target

Use existing exact-unit evidence as the starting envelope, not a new rate hunt:

- R5 transport ceiling evidence: ~18.46 fps with `streaming_ack_clock` and one ACK per frame.
- W8 webcam achieved 16.285 fps over a bounded run with stable source age and clean shutdown.
- Initial interactive product target: **sustain useful dynamic content in the ~16–18 fps transport range where the Host/device permit it**, while preserving clean button response and transitions.

Optimization priority:

1. correctness and state continuity;
2. no duplicate/replayed inputs;
3. no reconnect/reopen instability;
4. low input-to-render latency;
5. sustained ACK-clock throughput;
6. only then reduce CPU/allocations if measurements justify it.

At 16x16, procedural frame generation is cheap. Avoid premature caching that complicates state. Continue change-only suppression so stationary output costs no frames.

## 4. Page contract v2

Create a page-generic contract that can support both dashboard-style and game/video-style pages. The implementation may use concrete Python classes rather than a formal ABC initially, but behavior must be testable.

Each page should expose equivalent semantics to:

- `name` — durable page identity.
- `rate_mode` — `activity` or `streaming_ack_clock`.
- `on_enter(context)` — initialize/resume page-specific transient state.
- `on_exit(context)` — clean transition; persistent game state remains owned outside any Host session.
- `render(now_ms) -> 768-byte RGB888` — current 16x16 frame.
- `handle_input(event) -> action/result` — short lever and any future page-local controls.
- `frame_sent()` — ACK callback so animation/game state can advance on what actually reached the Host when appropriate.
- optional telemetry snapshot — compact page state, rates, transitions and input outcomes.

Global Left/Right remain navigation in v1 of this contract. The page gets the short lever as its primary local action. Future pages may request richer input semantics only under a new explicit design/review.

Page state must live above individual Host sessions. A canvas invalidation, bounded session rollover, profile transition, or reclaim may close a session; it must not reset the game unless that page itself chooses to reset.

## 5. HF-1 — offline general high-FPS page primitive

### Implementation

Build a side-by-side module rather than changing Runtime 006 hash-bound files in place.

Preferred initial shape:

- new `host/interactive_pages.py` for page contract, input/state controller and profile transition intent;
- new `host/interactive_stream.py` for ACK-clocked interactive dispatch using the existing transport/session primitives;
- reuse `host/frame_stream.py` constants/encoder/session-profile names rather than duplicating protocol knowledge;
- reuse Runtime 006 `ButtonEvents` semantics or factor only through a side-by-side import; do not inject or synthesize Ditoo input in product code;
- no Host change for HF-1 unless tests prove an existing Host limitation.

The interactive stream loop must preserve the same safety semantics as `frame_stream.stream_session`:

- one frame in flight;
- Host-selected `streaming_ack_clock` floor;
- no retry after ambiguous send;
- no automatic reconnect inside one experimental session;
- unsolicited non-ACK report terminates/yields the session;
- exact lifetime/frame/byte budgets;
- changed-frame suppression;
- bounded idle sleep when the page is stationary.

Add only what interaction needs:

- poll the read-only button cursor between ACKs;
- apply every accepted input at most once;
- let global navigation request a clean page/profile transition;
- let the lever mutate page state without opening another transport;
- record input-observed -> state-applied -> first-ACK timing where possible.

### Exit gate

Offline fake-transport tests prove:

- 100+ ACKed dynamic frames without duplicate input;
- navigation can request clean exit from a high-rate page;
- short lever actions affect the next available frame;
- page state survives simulated `canvas_invalidated` and a new session;
- no transport retry/reconnect/raw-send behavior appears;
- duplicate rendered frames are held rather than transmitted;
- a slow ACK naturally lowers FPS without catch-up bursts.

Suggested durable gate: `HF1_INTERACTIVE_PAGE_PRIMITIVE=PASS`.

## 6. HF-2 — profile-switch/product orchestration, offline first

Runtime 006 currently chooses the `activity` profile for the product session and changes only pixels inside that session. High-rate pages require a session-profile transition because profile is chosen at Host session open.

Build a successor supervisor that owns:

1. one persistent page router/input cursor;
2. the ButtonProbe lifetime;
3. low-rate activity sessions when an informational page is selected;
4. high-rate streaming sessions when an interactive page is selected;
5. a single-controller transition fence: close old session before opening the new profile;
6. page state independent of either session.

Transition rules:

- Dashboard -> high-rate page: finish/yield current activity session cleanly, retain broker/page state, open one streaming-profile session, render immediately.
- High-rate page -> Dashboard: stop streaming session cleanly, return to activity profile, restore current MCP dashboard state without replaying stale pulses.
- High-rate page -> high-rate page: prefer one clean streaming session transition unless keeping the same session is demonstrably safe and materially simpler; correctness outranks avoiding one reopen.
- Session invalidation while a page remains selected: preserve page state and apply the reviewed successor policy's reclaim behavior only after that behavior has its own acceptance evidence.

### Reliability gate

Offline transition stress test:

- >=100 synthetic page transitions;
- >=1000 mixed input events with monotonic epoch/seq rules;
- simulated Host open/send/ACK failures at every transition phase;
- no state reset or duplicate input after a failure;
- exactly one active controller/session in all states.

Suggested gate: `HF2_PROFILE_ORCHESTRATOR=PASS`.

## 7. GAME-1 — slots as the first meaningful high-FPS acceptance application

The first real high-rate page should be a tiny slots game, because it simultaneously exercises animation, deterministic state, physical input and stopping motion on user action.

### Visual model

Use the 16x16 matrix directly. Initial layout:

- three 5-pixel-wide vertical reels at x=0..4, x=5..9 and x=10..14;
- x=15 may remain border/status/spare;
- 5x5 or smaller deterministic symbol sprites arranged in cyclic reel strips;
- continuous vertical sub-symbol motion represented with integer-pixel offsets/frame phases;
- high-contrast flat RGB888 palette chosen for legibility at 16x16;
- no image-generation dependency; assets/sprites are procedural or explicitly authored pixel matrices in source.

### State machine

- `READY`: lever starts all reels.
- `SPINNING_3`: all three reels advance.
- first short lever -> freeze reel 1 at its current ACKed/current visible-compatible stop state.
- second short lever -> freeze reel 2.
- third short lever -> freeze reel 3 and evaluate result.
- `RESULT`: hold result without continuously transmitting unchanged pixels.
- next short lever -> new round and all reels spin again.

Use deterministic PRNG seeding in tests. Production may seed from a normal non-security random source, but outcomes must be decided in page state rather than inferred from dropped frames or transport timing.

### Input/animation semantics

A lever event changes state immediately when consumed. The next send opportunity renders from that new state. Do not queue historical frames to make the animation look smooth; newest state wins.

The stopped reel must not visually move again merely because the other reels keep rendering.

Global Left/Right always page away, even mid-spin. Returning to the page should use an explicit policy chosen and tested before live use; preferred first behavior is **resume current round state**, not silently reset.

### Offline acceptance

- 1000 deterministic game rounds;
- every round follows exactly 3 sequential stop actions;
- stopped reels remain pixel-stable while later reels move;
- leaving/re-entering mid-spin preserves the selected game state;
- no duplicate lever event stops two reels;
- changed-frame suppression after final result;
- renderer always outputs exactly 768 RGB888 bytes and <=255 palette colors.

Suggested gate: `GAME1_SLOTS_OFFLINE=PASS`.

## 8. HF-3 — one-use exact-device acceptance

Only after HF-1/HF-2/GAME-1 pass offline, freeze a new one-use experiment. Do not widen Runtime 006 yet.

The first live acceptance should validate the generic capability, not chase a rate record.

### Trial script

1. Runtime 006 dashboard visibly healthy.
2. Suspend Runtime 006 using the established single-controller pattern.
3. Start the one-use interactive runner under `streaming_ack_clock`.
4. Page/select the slots test page as defined by the runner.
5. Observe all reels spinning.
6. Pull lever three times with clear spacing; verify one additional reel stops each time.
7. Start another round.
8. Exercise page/profile exit and re-entry repeatedly — target **10 complete high-rate open/close cycles** in the bounded trial if budgets allow.
9. Return to dashboard and verify a fresh MCP activity pulse still works.
10. Restore Runtime 006 regardless of clean success/failure where recovery policy permits.

Specific regression target: repeated streaming reopen must not reproduce the earlier webcam-product-001 `IMAGE_RX_RECV_TIMEOUT` on the fourth reopen.

### Capture

- exact experiment id/grant;
- frames/packets/application bytes;
- realized transport FPS and ACK latency distribution;
- every input epoch/seq/type;
- input observed -> state applied -> first ACK latency;
- session/profile open/close sequence;
- canvas invalidations/reclaims/reconnects;
- owner visual observations for motion and one-reel-at-a-time stop behavior.

Suggested gate: `HF3_INTERACTIVE_LIVE=PASS`.

## 9. HF-4 — standing successor product runtime

After HF-3 passes, create a new reviewed standing product revision (number assigned from live repo state at implementation time; do not reserve blindly).

It may authorize only the page/profile behaviors explicitly listed in its policy. Preserve Runtime 006 rollback material.

Standing acceptance should include:

- Dashboard <-> slots repeated transitions;
- button broker continuity;
- lever behavior including the known every-other Play-direction `0xBD` reclaim case;
- device power-cycle while dashboard selected and while an interactive page is selected;
- webcam shortcut suspend -> restore under the successor runtime;
- Spotify/media contention;
- Windows reboot/logon startup of ButtonProbe/product if still pending.

No high-rate page may silently widen webcam or experimental stream authority.

## 10. UI-1 — richer MCP activity lightning animation

This is deliberately independent of HF-1. The accepted dashboard already sends a 10-frame ACK-gated activity sequence at nominal 200 ms. Use those existing frame opportunities more expressively before spending high-rate product complexity on the status UI.

### Visual intent

Keep the accepted layout, source columns, letters, icons, status colors and fault semantics. Replace the current whole-column color shimmer with a spatial sequence:

1. lightning seed appears at the top of the active 5-pixel source column;
2. bolt extends/zig-zags downward through the crown/spacer area;
3. bolt reaches the top of the source icon;
4. impact/spark frame at the icon;
5. icon + identity letter flare cyan;
6. icon + letter flash blue;
7. icon + letter flash light-blue;
8. second compact flare/aftershock;
9. final cyan/blue settle flash;
10. return toward the source's normal status color after the ACK-gated sequence completes.

Exact pixel choreography may be tuned in offline previews, but it must remain confined to the active source column except for any explicitly reviewed 1-pixel impact accent. Simultaneous source activity must compose independently without collisions.

### Implementation boundary

Prototype the choreography in a new side-by-side helper/module first so Runtime 006's hash-bound `activity_render.py` and `activity_session.py` remain untouched during design.

Then integrate only in the successor revision after:

- exact 16x16 offline frame previews exist;
- every stage is distinct under change-only scheduling;
- fault marker wins over activity animation for unavailable/stale sources;
- simultaneous two/three-source pulses remain deterministic;
- existing green/yellow/red/grey status behavior is unchanged outside the pulse;
- static accepted reference layout is unchanged when no pulse is active.

Do **not** increase polling of MCP sources just to animate. Animation runs locally from already-detected activity.

Suggested gate: `UI1_LIGHTNING_OFFLINE=PASS`, followed by one bounded visual acceptance when included in a successor runtime/experiment.

## 11. Telemetry cleanup to bundle with the successor

Fix the known Runtime 006 defect where `pages.recent_transitions[].first_ack_ms` may remain `null` until another input causes `publish()`.

The successor should publish immediately when `frame_sent()` fills the first ACK latency for a transition.

For high-rate pages add compact bounded telemetry:

- selected page + rate mode;
- current Host profile/session id;
- frames ACKed and realized FPS window;
- most recent input seq/type/action;
- last input-to-first-ACK latency;
- profile transitions/open failures;
- page-specific state summary (for slots: round state and number of stopped reels, not every frame).

Do not create unbounded frame logs in standing product mode.

## 12. Implementation order

Recommended execution sequence:

1. **PLAN-0** — land this plan and update active steering/handoff so future sessions route here.
2. **UI-1A** — side-by-side lightning frame choreography + offline tests/previews; no live hash-bound edits.
3. **HF-1** — generic high-rate page + interactive ACK-clock loop offline.
4. **GAME-1** — slots renderer/state machine and stress tests.
5. **HF-2** — profile-switch orchestrator and transition/failure stress tests.
6. **RECONCILE** — run full offline suite in an environment with Pillow; distinguish W9B dependency failures from new regressions.
7. **HF-3 PREP** — freeze one-use live manifest/runner and exact grant string; stop before transmission until the named grant condition is satisfied.
8. **HF-3 LIVE** — bounded slots + repeated reopen acceptance.
9. **HF-4/UI-1B** — combine accepted interactive runtime, lightning animation, ACK telemetry fix and chosen pages into the next standing product revision; review/grant/cutover with Runtime 006 rollback preserved.

UI-1A and HF-1/GAME-1 may proceed in parallel because they touch different side-by-side modules.

## 13. Definition of success

This priority set is complete when OpenDitoo has demonstrated, on the exact Ditoo Plus, a standing page system in which:

- Left/Right reliably navigate pages;
- a page can opt into the existing high-rate ACK-clock profile without a second Bluetooth controller;
- dynamic procedural content sustains useful ~16–18 fps transport where the device permits it;
- a physical lever action changes high-rate application state promptly and exactly once;
- the slots page visibly spins three reels and stops them one at a time across three lever pulls;
- repeated profile/page switching is stable;
- the MCP dashboard returns intact and uses the richer lightning-strike activity animation;
- Runtime 006 remains a tested rollback until the successor is accepted.
