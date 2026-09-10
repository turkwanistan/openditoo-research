# OpenDitoo button/AVRCP + physical pagination implementation plan — 2026-09-10

**Status:** PLANNED / no implementation or device I/O performed by this note.

**Owner-selected immediate objective:** prove that the exact Ditoo Plus left arrow, right arrow, and lever can be received on Windows over Bluetooth while the existing OpenDitoo dashboard is operating; if that succeeds, use the arrows for the smallest possible physical two-page pagination proof: current MCP dashboard <-> one looping animation/GIF-derived page.

**Authority:** the live WSL repository and exact-unit evidence outrank this note. No firmware flashing, MassBoot, teardown, raw Bluetooth send, target override, or proprietary protocol exploration is part of this route.

## 0. Baseline and reconciliation

Repository inspected at:

- WSL project: `/home/wan/Projects/openditoo-research`
- branch: `main`
- HEAD at plan creation: `9e52f3505bad0941a900c03dad2959056c843dc4`
- worktree before this note: clean
- GitHub/origin is substantially behind the WSL tree; plan from WSL, not the stale public clone.

Current accepted product baseline from the live repository:

- MCP Dashboard v1 is the everyday display.
- dashboard product policy: Runtime 005 (`OPENDITOO-PRODUCT-RUNTIME-005` local granted policy; committed template remains unauthorized).
- accepted Host build hash: `f7bd60d4a56de4f4740bd84f7c645e201ddfd7ce29bf6c0f1e7512b1b67cd34e`.
- one Windows Host owns the exact Ditoo RFCOMM display connection at a time.
- current dashboard code/hash envelope includes `host/product_runtime_v2.py`, `host/activity_session.py`, `host/activity_render.py`, `host/activity_ui_data.py`, `host/mcp_activity.py`, and the Host DLL.
- `host/frame_stream.py` already provides a general 16x16 RGB888 frame-set renderer and is suitable for a preprocessed animation page.
- on-demand webcam is a separate policy/product and must remain untouched by the first button proof.

Current WSL_MCP environment at plan creation cannot execute the Windows proof:

- `powershell.exe`: unavailable in this sandbox;
- OpenDitoo Host on `127.0.0.1:8796`: unreachable from this sandbox;
- offline verifier reached 296 tests, with exactly two environment errors because Pillow/PIL is absent from this sandbox. No assertion failure was observed.

Therefore implementation can be prepared/tested offline here, but exact Windows/physical acceptance must run from the local WSL/Windows execution context that can reach the Host and interactive desktop.

## 1. Evidence correction that drives this route

The preserved M7 Android HCI capture already establishes the device-side Bluetooth behavior. The earlier M7 application-layer conclusion was too broad because `host/btsnoop.py` decodes the RFCOMM PSM (`0x0003`) but does not decode the separate AVCTP/AVRCP PSM (`0x0017`).

Recovered exact-unit sequence:

| Physical action | Bluetooth observation | Normalized meaning |
| --- | --- | --- |
| left | AVRCP passthrough `0x4C` press + `0xCC` release | `nav_left` / Previous |
| right | AVRCP `0x4B` press + `0xCB` release | `nav_right` / Next |
| left again | AVRCP `0x4C` press + release | independent repeat confirmation |
| lever | AVRCP `0x44` press + `0xC4` release | `lever` / Play-or-Pause semantic |
| lever, same physical action | proprietary RFCOMM `0xBD` within milliseconds | corroborating/fallback lever signal |
| M | no comparable later Bluetooth key event in the measured sweep | negative only in measured context |

The implementation problem is therefore **Windows event reception and product routing**, not Ditoo firmware unlocking.

## 2. Non-negotiable design constraints

1. **Do not modify the Runtime 005 Host for the initial proof.** A receive-only Windows sidecar is lower risk and keeps the accepted RFCOMM/display path hash-identical.
2. **Do not open a second RFCOMM connection.** AVRCP is handled by the Windows Bluetooth/media stack; the sidecar contains no Ditoo RFCOMM code.
3. **Do not weaken the current canvas-invalidated fence.** Today any unsolicited non-ACK RFCOMM report ends the active Host session. The lever's `0xBD` means lever behavior must be measured before changing that policy.
4. **Keep raw events separate from normalized events.** First prove what Windows emits. Only then add de-duplication or navigation semantics.
5. **Treat SMTC media events as session-scoped rather than inherently device-attributed.** SMTC proves a controlled Ditoo press can reach OpenDitoo, but it does not by itself identify which physical media-key device originated an event. Product capture must therefore only be active while OpenDitoo deliberately owns the Ditoo UI, and contention with keyboard/Spotify/other media sessions must be tested.
6. **Use one successor product revision for pagination.** Do not edit the hash-frozen live renderer/supervisor in place. Build side-by-side, test offline, then cut over under a fresh explicit product policy/grant with rollback to Runtime 005.
7. **First physical pagination uses arrows only.** The lever is mapped/proven in the same receive experiment, but it does not become a navigation action until its simultaneous `0xBD` interaction with the existing Host is characterized.

---

# Milestone sequence

## BTN-0 — Make the recovered AVRCP evidence executable offline

**Goal:** turn the uploaded/manual HCI reconstruction into a reproducible repository result before changing runtime behavior.

### Implementation

Add a small AVCTP/AVRCP decoder beside the existing btsnoop reader rather than replacing the RFCOMM parser. Preferred shape:

- `host/avctp.py` — AVCTP/AVRCP packet classification only;
- extend `host/btsnoop.py` with generic L2CAP-channel tracking so both `0x0003` RFCOMM and `0x0017` AVCTP can be reconstructed from the same capture;
- preserve current RFCOMM outputs byte-for-byte for existing tests/captures;
- add an explicit `capture-avrcp-parse` or an opt-in AVRCP section to `capture-parse`; default privacy behavior remains payload-minimal.

AVRCP decoder scope must be deliberately tiny:

- identify AVCTP PSM `0x0017`;
- classify AVRCP passthrough commands only;
- extract operation id and press/release bit;
- preserve transaction label/timestamp/direction needed to pair press and release;
- assign no meaning beyond the standard IDs actually needed here (`0x44`, `0x4B`, `0x4C`).

Produce a new **derived** exact-unit evidence artifact; do not edit the immutable old M7 capture JSON to make history look cleaner. Suggested artifact:

`captures/OPENDITOO-M7-AVRCP-KEY-SWEEP-2026-09-09.json`

It should include:

- raw bugreport/btsnoop hashes already preserved;
- measured action schedule;
- AVCTP PSM/CID evidence;
- ordered operation events with timestamps;
- press/release pairing;
- normalized *evidence labels* (`previous`, `next`, `play`) separately from future product input names;
- the lever `0x44`/`0xBD` temporal correlation;
- explicit note that M remains only a bounded negative result.

### Offline tests

Pin at least these regressions:

- left -> `0x4C` press then `0xCC` release;
- right -> `0x4B` then `0xCB`;
- third planned action -> `0x4C` again;
- lever -> `0x44`/`0xC4` plus RFCOMM `0xBD` within the measured correlation window;
- arbitrary AVCTP traffic is not mislabeled as a button;
- truncated/fragmented L2CAP PDUs fail closed or remain incomplete, never synthesize an event;
- existing RFCOMM M7 parser results remain unchanged.

### Documentation reconciliation

Create a superseding M7 addendum and update current steering/state only after the parser reproduces the evidence. Historical capture records remain immutable. The durable current statement should become:

> left/right/lever were silent only on the proprietary RFCOMM application stream; the preserved exact-unit HCI capture proves left/right/lever on AVRCP.

### Exit gate

`BTN0_AVRCP_REPRODUCTION=PASS` only when the repository parser independently reproduces the exact left/right/left/lever sequence from preserved bytes.

**Device I/O:** none.

---

## BTN-1 — Build `OpenDitoo.ButtonProbe` as a receive-only Windows diagnostic

**Goal:** create the smallest Windows process capable of proving that Windows surfaces the Ditoo's AVRCP commands to an application.

### Project shape

New side-by-side project:

`runtime/windows/OpenDitoo.ButtonProbe/`

Recommended target:

`net8.0-windows10.0.19041.0`

This matches the repository's working Windows/WinRT pattern used by the webcam projects. Use a hidden WinForms/Win32 top-level window so the process owns a real HWND without adding visible product UI.

### Primary receive path: SMTC

Use `ISystemMediaTransportControlsInterop::GetForWindow` / the C#/WinRT `SystemMediaTransportControlsInterop.GetForWindow(hwnd)` projection to acquire SMTC for the probe's top-level HWND.

Enable only:

- Previous
- Next
- Play
- Pause

Set SMTC enabled and a deliberate non-closed playback status, then subscribe to `ButtonPressed`.

Initial normalization table:

- `Previous` -> `nav_left`
- `Next` -> `nav_right`
- `Play` -> `lever_candidate`
- `Pause` -> `lever_candidate`

Do **not** assume the lever always appears as Play; its result may track playback state.

### Secondary receive path: `WM_APPCOMMAND`

The same probe may log these as a diagnostic channel, but it must not merge them with SMTC during the proof:

- `APPCOMMAND_MEDIA_PREVIOUSTRACK`
- `APPCOMMAND_MEDIA_NEXTTRACK`
- `APPCOMMAND_MEDIA_PLAY_PAUSE`
- `APPCOMMAND_MEDIA_PLAY`
- `APPCOMMAND_MEDIA_PAUSE`

Reason: if both Windows routes report one physical press, merging them too early would manufacture duplicate OpenDitoo events. The physical test should reveal which path is reliable and whether both fire.

### Probe output

NDJSON to stdout and optionally a local file. Every record should have:

- process/session epoch;
- monotonic timestamp;
- UTC timestamp for correlation;
- monotonically increasing sequence;
- `source` = `smtc` or `wm_appcommand`;
- raw Windows button/command;
- candidate normalized event;
- no Ditoo MAC/token/target override/send payload.

Example conceptual record:

`{epoch,seq,at_monotonic_ms,at_utc,source,raw_button,normalized_candidate}`

### Explicit negative capabilities

Tests/source review should prove the executable contains no:

- RFCOMM socket code;
- OpenDitoo Host token access;
- HTTP call to Host;
- image/session route;
- target address;
- device write path;
- firmware/update path.

### Offline tests

- enum/command normalization;
- sequence monotonicity;
- epoch changes on restart;
- unknown media commands remain unknown;
- optional diagnostic channels stay separate;
- no de-duplication yet except exact duplicate callback defense required by the framework itself.

### Exit gate

`BTN1_BUTTON_PROBE_OFFLINE=PASS`

**Ditoo device I/O:** none from OpenDitoo. The probe only registers with Windows media controls.

---

## BTN-2 — Exact Windows Bluetooth receive proof

**Goal:** prove the physical exact-unit sequence reaches Windows/OpenDitoo while the current dashboard owns its normal RFCOMM session.

This is the first physical gate and must run in the local interactive Windows/WSL environment, not the current WSL_MCP sandbox.

### Preflight

Read-only checks first:

1. exact Ditoo paired;
2. Windows audio/AVRCP transport present/connected;
3. current Runtime 005 dashboard healthy before the test;
4. Host idle/active state recorded without reinstalling anything;
5. no unrelated media-key device intentionally exercised during the window;
6. raw Windows HCI capture disabled unless the fallback branch is needed.

Do not require active audio playback unless measurement shows Windows will not keep AVRCP routed without it.

### Controlled short-press trial A

Start ButtonProbe, wait for a quiet baseline, then physically perform:

`Left -> Right -> Left -> Lever`

Use clear spacing between actions. Record operator timestamps or have the probe accept a local marker key so each physical action can be bracketed without touching Ditoo.

Expected SMTC sequence:

`Previous -> Next -> Previous -> Play/Pause`

### Controlled repeat trial B

Repeat the same sequence once more after a fresh quiet baseline. This proves the first mapping was not accidental and tests one-event-per-press behavior.

### Concurrent dashboard observations

For every action record:

- current dashboard visible before press;
- whether any stock screen appears;
- Runtime 005 session id before/after;
- whether `canvas_invalidated` occurred;
- whether automatic reclaim happened;
- event latency from physical marker to Windows callback where measurable.

Expected asymmetry:

- **left/right:** should produce Windows AVRCP/SMTC input without an RFCOMM state report; dashboard should remain owned;
- **lever:** may also produce RFCOMM `0xBD`, and the current Host may consequently yield/reclaim. This is a measured question, not something to suppress in advance.

### BTN-2 acceptance

Pass the input-reception milestone when two controlled trials establish:

- left -> exactly one usable Previous/nav-left event per short press;
- right -> exactly one usable Next/nav-right event per short press;
- repeated left maps identically;
- lever -> one usable Play-or-Pause candidate event per short pull;
- no unexplained extra normalized events;
- all mapping windows are complete and attributable.

Dashboard/session side effects are reported independently; a lever-induced Host yield does not erase the successful Bluetooth mapping, but it blocks lever productization until BTN-7.

### If SMTC sees nothing: diagnostic decision tree

#### Case A — BTVS sees AVRCP and SMTC sees it

Solved; proceed to BTN-3.

#### Case B — BTVS sees `0x4B/0x4C/0x44`, SMTC does not

The Ditoo and Bluetooth path are fine. Fix only Windows routing/session ownership:

- verify a genuine top-level HWND owned by the process;
- SMTC `IsEnabled=true`;
- Previous/Next/Play/Pause enabled;
- deliberate playback status;
- test `WM_APPCOMMAND` independently;
- test with competing media apps closed first, then reintroduce them deliberately.

Do not change firmware or Ditoo protocol.

#### Case C — BTVS does not see AVRCP on Windows

Treat this as a Windows profile-state issue first:

- verify `Ditoo-Plus-audio` / AVRCP connection;
- compare profile connection state before/after starting audio;
- repeat the bounded trial;
- compare Windows HCI with the already-proven Android HCI behavior.

Do not jump to HID, BLE, firmware patching, MassBoot, or teardown.

### Evidence handling

If BTVS/Wireshark is needed, raw HCI may contain sensitive Bluetooth material. Keep raw trace local/private, record its SHA-256, and commit only a filtered derivative for the exact Ditoo/action window.

---

## BTN-3 — Harden the diagnostic into a typed ButtonBroker

**Goal:** turn the proven Windows event path into a bounded, read-only input source the WSL product runtime can consume.

Do this only after BTN-2 proves the actual Windows behavior.

### Windows broker responsibilities

Evolve/copy the probe into `OpenDitoo.ButtonBroker` with:

- the accepted primary Windows receive path (prefer SMTC if BTN-2 passes it);
- one bounded in-memory ring of typed events;
- process epoch + sequence numbers;
- explicit history-gap reporting;
- status/health telemetry;
- no Ditoo transport and no Host transport.

Suggested normalized event schema:

- `nav_left`
- `nav_right`
- `lever`

Each event:

`{epoch, seq, observed_at_monotonic, observed_at_utc, raw_button, event_type}`

### WSL bridge

Preferred product bridge: a **separate authenticated loopback-only typed endpoint owned by ButtonBroker**, not a new generic route in the hash-frozen Ditoo Host.

Minimal routes:

- `GET /v1/status`
- `GET /v1/events?after_seq=N`

Optional later ownership route only if needed:

- an authenticated local lease/enable operation so SMTC capture exists only while OpenDitoo product mode deliberately owns the Ditoo display.

The event API must be read-only from the WSL consumer's perspective and bounded:

- no arbitrary command injection;
- no synthetic button POST route;
- no raw Bluetooth endpoint;
- queue cap fixed in code;
- stale epoch or sequence gap surfaced explicitly, never silently stitched.

### Device-attribution caveat

SMTC is a media-session input surface, not guaranteed Ditoo-device identity. Therefore product enablement is conditional on OpenDitoo ownership:

- broker capture disabled/ignored when dashboard product is not active;
- events never trigger destructive/external actions;
- keyboard/headset media-key contention tested later;
- v1 pagination semantics remain harmless UI-only actions.

### Exit gate

`BTN3_BUTTON_BROKER=PASS` requires offline tests plus a local broker round-trip test with synthetic internal events. Still no display/device action required.

---

## BTN-4 — Build two-page pagination entirely offline

**Goal:** prove page state, animation behavior, event consumption, and rollback without Bluetooth.

### Do not mutate Runtime 005 in place

Runtime 005 is hash-frozen. Build a side-by-side successor source set, e.g.:

- `host/button_input.py` — typed broker client/event cursor;
- `host/page_router.py` — page state machine;
- `host/product_runtime_v3.py` or equivalent successor supervisor;
- a new product service/entrypoint if needed so existing `cli/openditoo.py` behavior is not changed under the currently granted policy during development;
- `product/OPENDITOO-PRODUCT-RUNTIME-006.json` as an unauthorized template only after offline behavior is frozen.

### Two pages only for the proof

**Page 0 — dashboard**

Reuse the existing `LiveActivityRenderer`; do not rewrite the approved MCP page.

**Page 1 — animation/GIF-derived page**

Use the already-existing `host/frame_stream.py` frame-set primitive. A GIF is preprocessing input, not a runtime dependency:

`GIF -> offline conversion -> exact 16x16 RGB888 frame set -> hash -> loop in Page 1`

This avoids adding Pillow/GIF parsing to the live product. The first demo can be a short, obvious animation with enough frame contrast that page entry is unmistakable.

### First navigation semantics

Keep it intentionally boring:

- on Dashboard: `nav_right` -> Animation;
- on Animation: `nav_left` -> Dashboard;
- `nav_left` on Dashboard -> no-op;
- `nav_right` on Animation -> no-op;
- lever -> log/telemetry only until BTN-7;
- no wrap-around for the two-page proof.

### Router behavior

The router owns exactly one current page id. It consumes each `(epoch,seq)` at most once. On broker restart/epoch change it establishes a new baseline and does not replay old events.

Event -> page change must be immediate at the next render tick. The existing activity session already uses a 50 ms render poll and a safe 200 ms nominal MCP dispatch cadence, so a practical first responsiveness target is:

- median button-to-page-frame ACK comfortably below 500 ms;
- no requirement tighter than that until physically measured.

### Animation scheduling

For the first proof, loop the Page-1 frame set at a cadence compatible with the existing activity-profile product envelope. Do not use the high-rate webcam profile just to show a demo GIF. A 200 ms / 5 fps animation is enough to prove physical pagination and stays inside the dashboard's already-accepted cadence shape.

When Page 0 is active, MCP activity collection/animation behaves exactly as today. When Page 1 is active, collection may continue in the background so returning to Page 0 shows current status.

### Offline acceptance suite

Use fake broker + fake Host transport and pin:

1. initial page is Dashboard;
2. right once -> Animation;
3. repeated render ticks do not repeat the navigation event;
4. left once -> Dashboard;
5. left on Dashboard and right on Animation are no-ops;
6. burst right/right coalesces/consumes safely rather than jumping unpredictably;
7. stale event after broker epoch restart is not replayed;
8. sequence gap is observable/fail-safe;
9. animation advances only while Page 1 is selected;
10. dashboard collection continues while Page 1 is selected;
11. a Host `canvas_invalidated` still ends/yields the current session exactly as Runtime 005 does;
12. reconnect/renewal resumes the selected page intentionally, with page state recorded;
13. broker unavailable -> dashboard continues on the current page; missing input must not stop display;
14. no input event can invoke shell/service/device operations.

### Exit gate

`BTN4_PAGINATION_OFFLINE=PASS` with deterministic fake-input transcript:

`dashboard --Right--> animation --Left--> dashboard`

No device I/O.

---

## BTN-5 — One bounded physical pagination acceptance

**Goal:** prove the complete product loop using arrows and the existing dashboard/display transport.

Only start after BTN-2 and BTN-4 pass.

### Authority shape

Cut a fresh reviewed one-shot pagination acceptance manifest or equivalently scoped temporary product policy. It must name:

- exact Ditoo / v42012;
- unchanged accepted Host build if Host remains unchanged;
- exact ButtonBroker build hash;
- exact pagination/router hashes;
- two allowed pages only;
- fixed animation frame-set hash;
- bounded lifetime;
- current activity-profile pacing/budgets;
- no raw send/target override;
- no automatic widening to webcam or other products;
- rollback to Runtime 005 after the experiment.

### Physical script

1. start on MCP dashboard;
2. verify dashboard content/activity still works;
3. press **Right once**;
4. require one `nav_right` broker event;
5. require Page 1 animation becomes visible;
6. allow several animation frames to prove it is actually running;
7. press **Left once**;
8. require one `nav_left` event;
9. require MCP dashboard returns;
10. trigger one harmless MCP activity pulse or wait for normal activity to prove the dashboard is live, not a static screenshot;
11. stop cleanly and restore the standing Runtime 005 product.

### Acceptance criteria

- one physical press -> one page transition;
- no double-page event;
- no stock-screen flash caused by left/right;
- no second RFCOMM controller;
- animation visibly runs;
- return page is the live MCP dashboard;
- current Host ACK/budget/session evidence remains coherent;
- no unwanted Spotify/media action during the controlled trial;
- clean stop/rollback.

This is the exact immediate product proof requested by the owner.

---

## BTN-6 — Productize pagination as Runtime 006

**Goal:** make physical page navigation a standing everyday capability only after the one-shot acceptance succeeds.

Suggested successor:

`OPENDITOO-PRODUCT-RUNTIME-006`

Runtime 006 should preserve Runtime 005's target, Host transport, pacing, reconnect/reclaim behavior, collection ownership, and raw-send prohibition, while adding only:

- ButtonBroker identity/hash;
- input health;
- typed event cursor;
- two-page router;
- selected-page state/telemetry;
- broker ownership gating.

### Cutover discipline

1. build/stage candidate side-by-side; never overwrite the live hash-frozen Host while developing;
2. run all offline tests in an environment with the project's required dependencies;
3. run ButtonBroker selftests from the staged Windows copy;
4. verify current Runtime 005/Host identity before touching services;
5. prepare Runtime 006 but leave unauthorized;
6. request one exact owner grant for the Runtime 006 scope;
7. transactional cutover;
8. physical smoke: right -> animation -> left -> dashboard;
9. test reconnect and Windows logon lifecycle if included in the new standing scope;
10. rollback immediately to preserved Runtime 005 policy/service if any gate fails.

### Status telemetry to add

- `input_broker_connected`
- `input_epoch`
- `last_input_seq`
- `last_input_type`
- `last_input_at`
- `current_page`
- `page_changed_at`
- `input_gap_detected`

No raw AVRCP bytes are necessary in routine product status.

---

## BTN-7 — Lever productization gate

**Goal:** decide whether the lever can safely become `select`/toggle after its simultaneous AVRCP + RFCOMM behavior is physically understood.

Do **not** make lever a page action before this gate.

Questions to answer from BTN-2 / a dedicated short trial:

1. Does one lever pull always produce one SMTC Play/Pause event?
2. Does RFCOMM `0xBD` arrive concurrently while Runtime 005/006 holds the display?
3. Does the Ditoo actually take the stock screen, or is `0xBD` merely input telemetry?
4. Does the current Host terminate/reclaim solely because it sees `0xBD`?
5. If both AVRCP and `0xBD` are observed, what measured time window is safe for de-duplication/correlation?

Only if physical evidence shows `0xBD` can be distinguished from genuine stock takeover should a **successor Host** consider changing the non-ACK fence. Do not special-case `0xBD` merely because we want the lever to work.

If the lever genuinely causes stock takeover, keep the Host fence and let the product redraw/reclaim after handling the AVRCP event, or leave the lever informational only.

Potential safe v1 semantics after acceptance:

- Dashboard: lever = open/toggle detail for selected page;
- animation: lever = pause/resume that animation;

No approvals, shell commands, service restarts, log deletion, firmware actions, or other consequential operations.

---

## BTN-8 — Input robustness, only after basic pagination works

Separate later characterization:

- short press vs long hold;
- auto-repeat rate;
- left+right rapid alternating input;
- broker restart while buttons are pressed;
- Ditoo Bluetooth reconnect;
- dashboard session renewal during a page switch;
- Spotify/media-player contention;
- keyboard/headset media-key interference;
- Windows logon/startup order;
- webcam handoff interaction.

Do not let these delay the first right->animation->left->dashboard proof unless they expose an actual correctness issue.

---

## BTN-X — M button / firmware-internal work (explicitly deferred)

The M button is outside the immediate goal. The current capture contains no comparable later Bluetooth event in its measured slot. If it becomes valuable later, resume static firmware/key-dispatch research or safe RAM-only instrumentation only after the standard AVRCP controls are productized.

No firmware patching is justified for left/right/lever because their radio-level path already exists.

---

# Recommended execution order

The shortest high-confidence path is:

`BTN-0 -> BTN-1 -> BTN-2 -> BTN-4 -> BTN-5`

Run BTN-3 between BTN-2 and BTN-4 as soon as the exact Windows receive path is known; BTN-4 can begin against a fake broker in parallel with BTN-1/BTN-2.

The first meaningful physical victory is **BTN-2**: Windows logs `Previous, Next, Previous, Play/Pause` from the exact Ditoo while the dashboard is up.

The first meaningful product victory is **BTN-5**:

`MCP dashboard --physical Right--> looping 16x16 animation --physical Left--> live MCP dashboard`

Everything beyond that is hardening, not a prerequisite to proving the concept.

# External API facts to verify at implementation time

Current Microsoft documentation supports this route:

- Windows desktop apps obtain `SystemMediaTransportControls` for their own top-level HWND through `ISystemMediaTransportControlsInterop::GetForWindow`.
- SMTC can enable Previous/Next/Play/Pause and raises `ButtonPressed`.
- `WM_APPCOMMAND` provides independent next/previous/play/pause media commands for diagnostic cross-checking.
- Windows Bluetooth guidance describes the audio accessory as generally AVRCP controller and Windows as target.
- Windows currently lists AVCTP 1.4 and AVRCP 1.6.2 support.
- Microsoft's Bluetooth Virtual Sniffer (`btvs.exe`) can feed live HCI into Wireshark and is the correct ground-truth fallback when application event routing is ambiguous.

These APIs are host-side only; none requires a Ditoo firmware change.
