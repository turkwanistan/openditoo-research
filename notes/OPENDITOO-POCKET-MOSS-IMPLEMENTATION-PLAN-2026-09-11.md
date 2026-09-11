# OpenDitoo — Pocket Moss implementation plan — 2026-09-11

**Status:** implementation plan only; no live-device authority is granted by this note.

**Current direction:** port **Moss the character and interaction idea**, not the Terrarium simulation engine. Pocket Moss v1 is a lightweight OpenDitoo application owned by WSL and rendered through the existing OpenDitoo Windows Bluetooth/input stack.

**Companion lab plan:** `notes/OPENDITOO-PIXEL-ANIMATION-LAB-PLAN-2026-09-11.md`

## 1. Product goal

Build **Pocket Moss** as a first-class OpenDitoo page.

The experience should feel like:

> Page over to Moss and he is simply there, doing his thing. Pull the lever and one tiny action glyph appears. Left/Right choose an action. Pull the lever and Moss reacts. Select Back to return Left/Right to global OpenDitoo navigation.

Pocket Moss v1 is deliberately small:

- recognizable Moss character;
- a few pleasant autonomous idle behaviors;
- purpose-built 16×16 animation;
- Pet / Dance / Kisses / Back interaction mode;
- no Terrarium world simulation dependency;
- no hunger/health/maintenance loop;
- no text menus;
- no LLM behavior engine.

The implementation should prove that OpenDitoo can host a polished animated character application using the same page/input/runtime primitives already accepted for Dashboard and Slots.

## 2. Runtime architecture

Pocket Moss should fit the same architecture as the existing OpenDitoo tools.

### WSL owns application logic

WSL should own:

- `MossPage`;
- Pocket Moss local state machine;
- sprite and animation selection;
- Pet/Dance/Kisses/Back selector state;
- autonomous idle scheduling;
- frame generation;
- animation timing/state;
- tests, previews, tooling and development iteration.

### Windows remains the device bridge

Reuse the existing Windows components rather than introducing a Moss-specific Bluetooth implementation:

- existing OpenDitoo ButtonProbe / SMTC path for Ditoo Left/Right/lever input;
- existing event broker into WSL;
- existing OpenDitoo Host/DLL/session protocol;
- existing RFCOMM graphics output to the Ditoo.

Preferred topology:

```text
Ditoo Left / Right / lever
        |
        v
existing Windows ButtonProbe / SMTC
        |
        v
existing OpenDitoo event broker
        |
        v
WSL Runtime successor
        |
        +--> Dashboard
        +--> Slots
        +--> MossPage
                 |
                 v
          Pocket Moss state + animation
                 |
                 v
          16x16 RGB888 frames
        |
        v
existing Windows OpenDitoo Host/DLL
        |
        v
Bluetooth RFCOMM
        |
        v
Ditoo
```

There should be **no second Bluetooth owner and ideally no new Moss-specific Windows DLL**. If a Windows change is eventually required, it must be justified by a generic runtime need rather than moving character logic out of WSL.

This architecture is appropriate because the Ditoo already depends on the Windows Bluetooth environment for the product path; when that environment is active, WSL is readily available and is the much better development/application layer.

## 3. Current OpenDitoo foundation — already achieved

Runtime 009 already provides the hard platform pieces:

- one persistent `streaming_ack_clock` Host session;
- accepted Dashboard + Slots single-session PageCarousel;
- physical Left/Right input;
- reliable short-lever input;
- page-local lever actions;
- known 0x09/0xBD yield/reclaim handling;
- page/application state above individual Host sessions;
- ACK-paced dynamic rendering in the accepted interactive envelope;
- webcam suspend/restore coexistence;
- standing reconnect/power-cycle/rollover behavior.

Pocket Moss therefore starts as **another OpenDitoo interactive page**, not a new transport research project.

Initial page order:

`Dashboard <-> Slots <-> Moss`

Long lever holds remain out of scope.

## 4. Character-port principle

Port **Moss's identity and acting philosophy**, not Terrarium's simulation complexity.

Useful Terrarium inspiration:

- brown-and-cream identity;
- floppy asymmetric ears;
- compact horizontal quadruped silhouette;
- short muzzle / short legs / low center of gravity;
- readable head/ear/body acting;
- low-frame-count authored animation;
- anticipation/contact/hold/recovery;
- stillness is valid;
- avoid random jitter and meaningless movement.

Do **not** mechanically downscale the larger Terrarium sprites. Pocket Moss should be explicitly authored for 16×16.

Do **not** import in v1:

- Terrarium world engine;
- canonical event ledger;
- habits/consequence memory;
- weather/seasons;
- objects/inventory;
- autonomous navigation/world geometry;
- needs, energy or maintenance systems;
- Terrarium persistence database.

Terrarium integration can remain an optional future direction if Pocket Moss becomes compelling enough to justify it.

## 5. PM-LAB-0 — build the offline Pixel Animation Lab first

This is a major deliverable, not a disposable Moss preview script.

Implement the reusable plan in:

`notes/OPENDITOO-PIXEL-ANIMATION-LAB-PLAN-2026-09-11.md`

Pocket Moss should be the lab's first serious consumer and stress test.

The lab must make it practical for a ChatGPT session to:

1. author machine-readable literal 16×16 frames;
2. render deterministic previews;
3. simulate realistic ACK cadence/jitter;
4. inspect animations without Bluetooth;
5. reconstruct exact frames independently from WSL_MCP-readable JSON;
6. compare A/B/C variants under the same cadence;
7. critique and revise weak frames autonomously;
8. generate contact sheets / animated previews / review bundles;
9. freeze strong candidates with hashes;
10. involve the owner only after poor variants have been eliminated.

The goal is a substantially better feedback loop for **all future OpenDitoo visual work**, not merely Moss.

## 6. PM-ART-1 — choose Pocket Moss identity

Use the animation lab to create **at least three deliberately different Moss idle candidates**.

Suggested directions:

- **A — side profile:** strongest compact canine silhouette;
- **B — slight three-quarter:** more expressive head while retaining quadruped body;
- **C — compact/chibi:** slightly larger head and compressed body, without becoming frontal/humanoid.

Target character envelope: roughly **11–13 pixels on the dominant dimension**, varying by pose.

Use a restrained palette such as:

- dark brown outline/shadow;
- medium body brown;
- warm highlight brown;
- cream muzzle/chest/paw accent;
- dark eye/nose;
- optional restrained accent/floor color.

For each candidate, the lab should produce:

- exact 16×16 frame;
- enlarged nearest-neighbor preview;
- mirror;
- silhouette-only comparison;
- occupancy/bounding box;
- palette telemetry;
- side-by-side A/B/C sheet;
- deterministic source/hash.

### ChatGPT quality loop

Before owner selection, the implementing agent should independently inspect and iterate the candidates at least once using the lab review workflow.

Do not present obviously weak candidates simply because three were requested.

Owner chooses among a small set of candidates that already pass basic character/readability review.

## 7. PM-ART-2 — minimum pose vocabulary

Once the base identity is selected, author a compact pose set.

### Passive / autonomous poses

- `idle`
- `look_left/right` or mirrorable look
- `happy`
- `loaf/rest`
- `sleep`
- `wake`
- optional `stretch`
- optional `groom`

### Interaction poses

Pet:

- notice
- lean/anticipate
- contact
- happy hold
- settle

Dance:

- bounce A
- step A
- step B
- happy/final pose
- settle

Kisses:

- notice/look toward user
- affectionate/happy response
- optional heart particle frame(s)
- settle

Avoid large sprite inventories until physical UAT demonstrates value.

## 8. PM-ANIM-1 — animation quality pass

Use the Pixel Animation Lab to develop complete sequences offline before touching the Ditoo.

Every major sequence should be inspected at:

- fast ~18 fps-class simulated ACK flow;
- measured ~16 fps-class flow;
- 10 fps;
- slower ~5 fps readability check;
- deterministic jittered ACK sequence;
- manual frame stepping.

Animation advances from ACK/frame progression rather than assuming perfect wall-clock playback.

### Motion rules

- important poses should be held long enough to read;
- no one-frame eye/ear noise merely to create movement;
- avoid whole-body breathing bob;
- avoid random fidget spam;
- no catch-up bursts after simulated stalls;
- contact actions require readable anticipation and recovery;
- idle may be totally still for meaningful stretches;
- animation should preserve a stable body anchor unless movement is intentional.

### Required agent review

Before promotion, the implementing ChatGPT session should document at least one self-directed critique/revision cycle for:

- base idle/look loop;
- Pet;
- Dance;
- Kisses.

This is specifically intended to reduce owner-driven micro-edit loops.

## 9. PM-BEHAVIOR-1 — lightweight local Moss state machine

Do not build a life simulation.

Use a tiny WSL-local presentation state machine that makes Moss feel alive while the page is visible.

Suggested passive states:

- `IDLE`
- `LOOK`
- `LOAF`
- `SLEEP`
- `WAKE`
- optional `STRETCH`

Example behavior:

```text
IDLE
  -> occasional LOOK
  -> back to IDLE
  -> occasional LOAF
  -> back to IDLE
  -> rare SLEEP
  -> WAKE
  -> IDLE
```

Rules:

- deterministic PRNG per runtime/start is preferable for tests;
- bounded weighted timers/cooldowns;
- no needs/energy/hunger stats;
- no punishment for absence;
- no constant animation;
- no autonomous state transitions while an interaction animation is executing;
- page re-entry should feel coherent rather than always resetting to frame zero.

A simple scheduler is enough. The purpose is ambient charm, not simulation depth.

## 10. PM-PAGE-1 — offline `MossPage`

Implement `host/moss_page.py` as an OpenDitoo `InteractivePage`-compatible page.

Initial page modes:

- `NORMAL`
- later `SELECTOR`
- later `ACTION_ANIMATION`

In `NORMAL`, the page:

- runs the lightweight local state machine;
- renders through the locked Pocket Moss assets;
- produces exactly 768 RGB888 bytes;
- advances animation on accepted frame progression;
- suppresses unchanged output naturally;
- preserves local state through Host session reclaim/rollover within one runtime process;
- exposes bounded telemetry.

Suggested telemetry:

- page mode;
- behavior state;
- active animation;
- phase/frame;
- ACK/frame progression;
- selector action if any;
- interaction count;
- enter/exit count.

## 11. PM-NAV-1 — generic modal navigation capture

Runtime 009 currently treats Left/Right as global PageCarousel navigation. Moss interaction mode needs them temporarily.

Add a **generic page capability**, not a Moss-specific branch.

Conceptual contract:

`page.handle_navigation(direction, event) -> consumed: bool`

Carousel behavior:

1. offer the navigation event to the current page;
2. if consumed, stay on that page;
3. otherwise perform ordinary global wrap-around navigation.

Moss behavior:

- `NORMAL`: do not consume -> Left/Right navigate OpenDitoo pages;
- `SELECTOR`: consume -> Left/Right rotate Moss actions;
- `ACTION_ANIMATION`: consume/ignore while the bounded reaction completes.

This becomes another reusable homebrew-app primitive.

Test carefully for:

- at-most-once input consumption;
- buffered event ordering;
- no event leakage to the next page;
- no accidental page move while selector is active;
- Back restores global navigation immediately.

## 12. PM-LIVE-1 — read-only physical Moss page

Do **not** add the submenu before Moss itself looks good on the physical display.

First live scope:

`Dashboard <-> Slots <-> Moss`

Moss has passive local behavior only.

Acceptance:

1. Page into Moss physically.
2. Observe several passive behavior/animation sequences.
3. Moss is immediately recognizable at literal 16×16 scale.
4. Idle/still frames look intentional, not dead.
5. Look/loaf/sleep/wake transitions read clearly.
6. Navigate away/back at least 10 times.
7. Page state remains coherent.
8. Exercise a known canvas yield/reclaim while Moss is selected.
9. Dashboard and Slots remain unchanged.
10. No separate Bluetooth session/controller appears.

If art/animation is weak physically, return to the offline lab and improve it there rather than adding UI complexity.

## 13. PM-SELECTOR-1 — tiny icon-only interaction mode

After the Moss page itself is accepted, add the original interaction concept.

### Normal Moss

- Left -> previous OpenDitoo page
- Right -> next OpenDitoo page
- short lever -> enter selector

### Selector mode

- Left -> previous Moss action
- Right -> next Moss action
- short lever -> execute selected action

Initial action loop:

`PET <-> DANCE <-> KISSES <-> BACK`

Back:

- lever exits selector;
- action icon disappears;
- Left/Right return immediately to global PageCarousel navigation.

### Visual law

- no text;
- one icon at a time;
- target ~3×3 pixels, allow 3×4 only if physical readability requires it;
- reserve a consistent corner/edge after collision testing;
- Moss remains visible while browsing actions;
- icon disappears when executing an action;
- the action animation receives the full 16×16 canvas.

Create Pet/Dance/Kisses/Back glyphs in the Pixel Animation Lab and collision-test them against every relevant Moss pose.

## 14. PM-ACTION-1 — local interactions

For Pocket Moss v1, **all interactions are local OpenDitoo presentation state**.

### Pet

`notice -> lean/contact -> happy hold -> small tail/body response -> settle`

### Dance

`bounce -> side step -> opposite step -> happy pose -> settle`

### Kisses

`look toward user -> happy/affection response -> optional tiny heart -> settle`

After an action:

- return to selector;
- keep the same selected action unless physical UAT suggests otherwise;
- do not invent persistent mood/affection stats;
- increment only lightweight local telemetry if useful.

There is no Terrarium write/API requirement in v1.

## 15. PM-LIVE-2 — physical interaction acceptance

Acceptance choreography:

1. Navigate to Moss.
2. Pull lever once -> Pet icon appears.
3. Left/Right through all four actions.
4. Verify global page does not move.
5. Execute Pet once.
6. Verify one clean Pet animation and return to selector.
7. Execute Dance.
8. Execute Kisses.
9. Verify each animation is visually distinct and responsive.
10. Select Back.
11. Pull lever -> selector disappears.
12. Left/Right immediately navigate globally again.
13. Repeat through one known 0xBD/0x09 canvas yield/reclaim.
14. Repeat around Host rollover/reconnect if appropriate to the bounded acceptance.
15. Confirm no duplicate physical input application.
16. Confirm Dashboard/Slots/webcam coexistence remains intact.

## 16. Persistence policy

Keep v1 simple.

Recommended:

- passive Moss state exists in-memory in WSL while the product runtime is alive;
- reclaim/renewal/reconnect does not reset it;
- process/service restart may reset Moss to `IDLE`;
- selector starts on Pet after a process restart;
- no durable mood/needs database;
- no hunger/energy/health;
- no absence penalties;
- no inventory.

Possible later persistence:

- last selected action;
- total interaction counts;
- rare cosmetic preference/history.

Only add it if it makes Moss feel better rather than making the system more complex.

## 17. Terrarium integration — explicitly deferred / optional

Pocket Moss v1 has **no runtime dependency on Terrarium**.

The existing old concept of a canonical Terrarium bridge remains valid as a possible future expansion, but it should not block or shape v1 unnecessarily.

Possible future directions:

- read-only mapping from Terrarium Moss state to Pocket Moss poses;
- narrow idempotent affection/attention interactions;
- shared identity/history;
- Ditoo as a physical Terrarium window.

If revisited later, preserve the original principle that there should be only one canonical Terrarium world rather than two competing simulations.

For now, port the character and interaction experience only.

## 18. Repository strategy

Create a fresh branch/worktree for implementation, suggested:

`feat/pocket-moss`

Do not modify Runtime 009 hash-bound files on live `main` during development.

Likely generic lab files:

- `host/pixel_art.py`
- `host/pixel_animation.py`
- `tools/pixel_lab.py`
- focused lab tests

Likely Moss files:

- `host/moss_page.py`
- `assets/pocket_moss/sprites/...`
- `assets/pocket_moss/animations/...`
- Pocket Moss tests
- physical acceptance runner/manifest later

Likely existing files changed:

- `host/interactive_pages.py` — generic modal navigation capture;
- standing runtime successor — add Moss to PageCarousel;
- product policy/hash set;
- product status/telemetry serialization.

Windows ButtonProbe/Host should remain unchanged unless implementation proves a generic blocker.

## 19. Verification ladder

### Lab gate

- sprite/animation schemas deterministic;
- exact 768-byte output;
- side-by-side review works;
- cadence simulation works;
- ChatGPT can reconstruct exact frames from WSL_MCP-readable review JSON;
- at least one autonomous critique/revision loop proven.

### Art gate

- owner-approved 16×16 Moss identity;
- mirror works;
- palette/readability acceptable;
- animations visually distinct;
- selector icons readable and non-obstructive.

### Behavior/page gate

- deterministic local scheduler tests;
- no needs/simulation creep;
- state survives expected Host session boundaries;
- animations advance correctly from acknowledged frames;
- unchanged frames suppressed where appropriate.

### Input gate

- normal Left/Right = global pages;
- selector Left/Right = local choices;
- lever enter/execute;
- Back releases navigation;
- at-most-once semantics remain intact;
- no page/action leakage.

### Full regression

Before standing cutover:

- current OpenDitoo legacy tests;
- interactive-page tests;
- product policy/hash validation;
- rollback verification;
- webcam suspend/restore regression;
- physical Moss acceptance.

Existing Runtime 009 transport and recovery rules are not weakened for Moss.

## 20. Milestone order

1. **PM-0 — branch + plan boundary**
2. **PM-LAB-0 — implement reusable Pixel Animation Lab foundation**
3. **PM-ART-1 — create/iterate Moss identity candidates in lab**
4. **PM-ART-2 — owner locks character identity**
5. **PM-ANIM-1 — passive + interaction animations; autonomous ChatGPT critique/revision**
6. **PM-BEHAVIOR-1 — lightweight local Moss state machine**
7. **PM-PAGE-1 — offline MossPage**
8. **PM-NAV-1 — generic modal navigation capture**
9. **PM-LIVE-1 — physical passive Moss page acceptance**
10. **PM-SELECTOR-1 — Pet/Dance/Kisses/Back icon selector**
11. **PM-ACTION-1 — local interaction behavior**
12. **PM-LIVE-2 — exact-device interaction acceptance**
13. **PM-PRODUCT-1 — standing Runtime successor**
14. **Future only — decide whether Terrarium integration adds enough value to justify complexity**

## 21. Definition of success

Pocket Moss v1 is successful when:

- Moss is a recognizable, charming 16×16 character rather than a crude downscale;
- animations have been developed and substantially refined offline before hardware testing;
- ChatGPT can independently inspect and iterate the exact frame data through the reusable animation lab;
- the owner is not required to drive every tiny sprite/animation revision;
- Moss pages in alongside Dashboard and Slots through the existing one-session runtime;
- a lightweight WSL-local state machine makes him feel alive without becoming a simulation project;
- lever enters the tiny icon-only selector;
- Left/Right cycle Pet/Dance/Kisses/Back locally;
- each action produces a polished, distinct animation;
- Back restores global page navigation;
- no separate Bluetooth stack or unnecessary Windows application logic is introduced;
- existing OpenDitoo transport/recovery/webcam behavior remains intact.

The strongest v1 is therefore deliberately simple: **Moss the character becomes a polished native OpenDitoo app, while the reusable Pixel Animation Lab makes high-quality 16×16 visual development dramatically faster for everything that comes after it.**
