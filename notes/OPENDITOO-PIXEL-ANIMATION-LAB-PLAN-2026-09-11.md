# OpenDitoo — reusable 16×16 Pixel Animation Lab plan — 2026-09-11

**Status:** design/implementation plan; offline only until separately integrated into a live product revision.

## 1. Purpose

Build a high-quality **offline 16×16 animation lab** that becomes the default art/animation feedback loop for OpenDitoo projects.

The lab is not only for Pocket Moss. It should support:

- characters and pets;
- games and procedural scenes;
- UI/status animations;
- MCP effects;
- icons and selectors;
- webcam/video overlays;
- future OpenDitoo homebrew pages.

The primary goal is to let an agent in a normal ChatGPT session create, inspect, critique, revise, compare, and verify pixel animation **before the physical Ditoo is involved**.

The intended loop is:

`author machine-readable sprite/animation -> validate -> render exact 16×16 frames -> simulate real transport cadence -> inspect visually -> compare alternatives -> revise -> freeze reviewed assets -> only then try physical device`

The lab should reduce the current pattern of “make something, manually test it, tweak it many times” and make it practical for ChatGPT to do several quality iterations independently before asking the owner to look at anything.

## 2. Design principles

1. **Literal 16×16 first.** The authored artifact is the device matrix, not a large image that is downscaled later.
2. **Machine-readable source of truth.** PNG/GIF are generated review artifacts, not the only editable representation.
3. **Deterministic rendering.** Same source + same settings = byte-identical frames and hashes.
4. **Production-path parity.** Validation should reuse the same RGB888/palette/packet assumptions as OpenDitoo, not a fake web-only renderer.
5. **ACK-realistic animation.** Animation quality is judged under the timing behavior the device transport actually provides.
6. **Visual iteration without device I/O.** No Bluetooth is needed to create or approve most art/animation changes.
7. **ChatGPT-readable review bundles.** A chat session with WSL_MCP must be able to retrieve the authored frame data and reconstruct the exact animation independently for visual inspection.
8. **Human review remains final for physical-panel appearance.** The lab should eliminate bad candidates before hardware UAT, not pretend a browser is the physical panel.
9. **General infrastructure, project-specific content.** Moss assets live under Pocket Moss; the lab itself stays generic.

## 3. Source formats

Use small text formats so WSL_MCP can expose exact frame content directly to ChatGPT.

### 3.1 Sprite format — `openditoo.pixel-sprite.v1`

Recommended JSON shape:

```json
{
  "schema": "openditoo.pixel-sprite.v1",
  "id": "moss.idle.a",
  "width": 16,
  "height": 16,
  "palette": {
    ".": [0, 0, 0],
    "o": [51, 30, 20],
    "b": [139, 82, 49],
    "h": [205, 137, 78],
    "c": [245, 217, 171],
    "e": [10, 8, 8]
  },
  "rows": [
    "................",
    "................"
  ],
  "meta": {
    "anchor": [8, 13],
    "mirroring": "horizontal",
    "tags": ["moss", "idle"]
  }
}
```

The exact syntax may use rows, sparse runs, or both after implementation benchmarking. Requirements are:

- exactly 16×16 logical pixels;
- explicit RGB888 palette;
- deterministic row-major expansion;
- no implicit antialiasing;
- no hidden renderer-only pixels;
- easy textual diff;
- easy WSL_MCP retrieval;
- easy reconstruction by ChatGPT/Python without project-specific libraries.

A compact sparse/RLE representation can be added if it remains human-readable.

### 3.2 Animation format — `openditoo.pixel-animation.v1`

Recommended JSON shape:

```json
{
  "schema": "openditoo.pixel-animation.v1",
  "id": "moss.pet",
  "canvas": [16, 16],
  "loop": false,
  "sequence": [
    {"sprite": "moss.idle", "hold_acks": 3, "phase": "notice"},
    {"sprite": "moss.pet.lean", "hold_acks": 2, "phase": "anticipate"},
    {"sprite": "moss.pet.contact", "hold_acks": 4, "phase": "contact"},
    {"sprite": "moss.happy", "hold_acks": 6, "phase": "hold"},
    {"sprite": "moss.idle", "hold_acks": 3, "phase": "settle"}
  ]
}
```

The authored timing primitive should be **ACK opportunities / sent-frame progression**, because current interactive OpenDitoo advances meaningful motion from acknowledged frames. The lab may also display approximate milliseconds for selected cadence profiles, but wall-clock duration is derived presentation, not authoritative authored motion.

Optional future fields:

- composited overlays;
- per-frame anchor/translation;
- palette-role substitutions;
- event markers;
- procedural frame generator reference for games/effects.

Do not make the schema a generic scene graph in v1.

## 4. Exact render/compile path

Provide one canonical loader/compiler shared by tests and previews.

Suggested modules:

- `host/pixel_art.py` — schemas, validation, palette expansion, mirroring, compositing;
- `host/pixel_animation.py` — deterministic animation state machine;
- `tools/pixel_lab.py` — CLI and review-bundle generator.

Each sprite must compile to exactly:

`16 × 16 × 3 = 768 RGB888 bytes`

The compiler should also run frames through the same constraints used by `host/ditoo_pixel_coloring.py`:

- exact dimensions;
- RGB channels 0..255;
- distinct color count compatible with the Ditoo palette encoder;
- deterministic palette/index generation where that encoder is used;
- packet-size/color-count telemetry for review.

For animations used by the standing `streaming_ack_clock` path, RGB888 frame parity is the main requirement. Do not create a second unrelated color pipeline.

## 5. Browser preview workbench

Create a simple local browser workbench generated/served entirely offline.

Suggested route/tool:

`python3 tools/pixel_lab.py serve --asset <...>`

Core UI:

- literal 16×16 preview;
- 8× and 16× nearest-neighbor enlargement;
- optional pixel grid;
- black / neutral / custom backdrop;
- play/pause;
- single-frame step forward/back;
- scrub timeline;
- current sprite id / phase / frame index;
- current hold count;
- loop count;
- elapsed simulated ACKs;
- palette swatches;
- occupancy/bounding box;
- anchor marker toggle;
- horizontal mirror toggle;
- transport cadence profile selector;
- deterministic restart.

Do not smooth pixels. CSS/image rendering must use nearest-neighbor/pixelated behavior.

## 6. Realistic cadence simulator

The preview must make timing mistakes visible before hardware testing.

Profiles should include at minimum:

- **ideal 18 fps-class ACK flow**;
- **measured 16.3–16.5 fps-class webcam-like flow**;
- **10 fps** slower animation check;
- **low-rate ~5 fps** readability check;
- **jittered ACK profile** using a deterministic recorded/synthetic interval sequence;
- manual step mode.

Do not label any of these as physical panel FPS. They are render/transport opportunity simulations.

Important behavior:

- no catch-up burst after a long ACK;
- authored `hold_acks` progress only as simulated acknowledgements occur;
- change-only frames may remain held indefinitely without manufacturing motion;
- deterministic jitter seeds so two variants can be compared under identical cadence.

Later, allow loading actual captured ACK interval sequences from OpenDitoo telemetry for replay.

## 7. Side-by-side variant comparison

The workbench should make A/B/C art iteration cheap.

Support:

- two or three assets/animations playing on the same deterministic cadence clock;
- synchronized restart;
- synchronized phase/frame stepping;
- same background and scale;
- optional XOR/difference overlay;
- occupancy comparison;
- palette/color-count comparison;
- silhouette-only mode;
- mirrored comparison;
- contact sheet export.

This is particularly important for the initial Pocket Moss identity selection and for future sprite refinements.

## 8. Automated quality checks

The lab should reject obvious defects without human review.

### Structural checks

- exact 16×16 dimensions;
- valid palette references;
- no duplicate asset ids;
- no impossible animation references;
- deterministic expansion/hash;
- RGB888 length exactly 768 bytes;
- encoder color-count compatibility;
- animation sequence non-empty;
- all holds positive and bounded;
- mirror operation remains on-canvas.

### Visual geometry checks

Report rather than blindly reject unless a project supplies bounds:

- non-background bounding box;
- occupied-pixel count;
- percentage of canvas occupied;
- edge touches;
- center of mass;
- left/right silhouette width;
- per-frame changed-pixel count;
- adjacent-frame pixel delta;
- palette usage;
- disconnected one-pixel islands;
- potential accidental 1-frame flicker pixels.

### Animation checks

- repeated identical authored frames that could be holds instead;
- one-frame flashes shorter than configured readability minimum;
- excessive full-frame churn;
- phase order correctness;
- loop seam delta;
- anchor jumps;
- unintended mirrored asymmetry loss;
- selector/icon collision with protected sprite region when a page supplies one.

The lab must report metrics but avoid turning subjective animation quality into a fake numeric score.

## 9. Review bundle — optimized for ChatGPT

This is a core requirement, not an export convenience.

Command concept:

`python3 tools/pixel_lab.py review-bundle <animation-or-scene>`

Generate a self-contained directory under a predictable ignored path, e.g.:

`.openditoo-local/pixel-lab/reviews/<id>/`

with:

- `manifest.json` — schema, hashes, source files, cadence profile, generation command;
- `frames.json` — exact compact machine-readable 16×16 frame content and timing/phase metadata;
- `quality.json` — structural/geometry/animation checks;
- `contact-sheet.png` — every unique frame at nearest-neighbor scale with labels;
- `preview.gif` or equivalent animated review asset;
- `preview.html` — standalone deterministic workbench snapshot;
- `frame-000.png`, etc. only when requested/needed;
- `README.txt` — one short instruction block for a future agent.

### Why `frames.json` matters

A ChatGPT session using WSL_MCP can read `frames.json` directly, then reconstruct the exact frames in its own Python/container environment for **independent visual inspection**. This avoids depending on WSL_MCP to display binary PNGs and avoids requiring the owner to manually upload screenshots for every iteration.

The review manifest should make the reconstruction trivial:

- palette;
- 16 strings or 256 indices per unique frame;
- frame sequence;
- hold counts;
- phase labels;
- deterministic cadence seed/profile.

## 10. ChatGPT autonomous iteration contract

A future ChatGPT session should be able to follow this loop:

1. Read the project plan and selected animation spec.
2. Read sprite/animation JSON through WSL_MCP.
3. Run the lab's offline validation/review-bundle command.
4. Read `quality.json` and `frames.json`.
5. Reconstruct contact sheets / animation frames independently in the ChatGPT sandbox.
6. Visually inspect silhouette, pose readability, animation flow, collisions, flicker, pacing, and transitions.
7. Make one coherent authored-source revision.
8. Re-run deterministic validation.
9. Compare old/new variants side-by-side under identical cadence.
10. Repeat until the agent believes the candidate is genuinely good.
11. Only then ask the owner for subjective review or physical-device UAT.

This should be written into the lab README/agent steering so future chats do not immediately punt every visual choice to the owner.

The agent should still surface genuine subjective forks (e.g. two equally strong Moss silhouettes), but it should eliminate broken/weak variants itself first.

## 11. Animation critique checklist for agents

Every autonomous review should explicitly inspect:

- **identity/readability:** what does the 16×16 silhouette read as with no label?
- **pose hierarchy:** can key poses be distinguished at 1× and enlarged view?
- **timing:** are anticipation/contact/hold/recovery readable under slow and fast profiles?
- **continuity:** do anchors/body mass jump accidentally?
- **economy:** are frames doing useful work, or is animation busy for its own sake?
- **stillness:** does the sequence know when to stop moving?
- **palette:** are important features separated by value/hue at tiny scale?
- **mirroring:** does direction change preserve identity?
- **loop seam:** does a loop pop?
- **device constraints:** is the animation still legible when the transport cadence jitters?
- **UI collision:** do icons/overlays obscure important character pixels?

Agent notes should be stored in the review manifest or a short `critique.md` when a revision is promoted.

## 12. Fast authoring/editing ergonomics

The lab should optimize for agents editing text, not mouse-driven pixel art.

Useful commands:

- `pixel_lab.py validate <asset-or-animation>`
- `pixel_lab.py render <asset>`
- `pixel_lab.py animate <animation>`
- `pixel_lab.py compare <a> <b> [c]`
- `pixel_lab.py review-bundle <animation>`
- `pixel_lab.py serve ...`
- `pixel_lab.py list`

Useful generated diagnostics:

- row/column coordinates;
- diff coordinates between frames;
- palette-role replacement;
- mirror output;
- translate by ±N pixels with clipping report;
- overlay an icon/protected region;
- contact-sheet labels.

Avoid building a full graphical sprite editor unless the text-first workflow proves inadequate.

## 13. Procedural animation support

Static sprite sequences are the v1 priority, but the lab should have a bounded seam for procedural renderers because Slots/MCP effects already use procedural content.

A procedural preview adapter may provide:

`render(state, ack_index, now_ms) -> 768-byte RGB888`

The lab can then:

- run it against deterministic fake ACK sequences;
- capture unique frames;
- build the same review bundle;
- compare procedural versions;
- detect unchanged frames/churn.

Do not require procedural pages to convert themselves into sprite JSON.

## 14. Physical-device promotion boundary

The lab is an offline quality gate. Passing it does not grant Bluetooth authority.

A candidate is eligible for physical UAT when:

- all structural checks pass;
- the agent has completed at least one documented visual critique iteration;
- owner review is complete when the change is identity-defining or subjective;
- assets/animation specs are hash-frozen;
- exact production RGB888 output is reproducible;
- relevant existing OpenDitoo offline tests still pass.

Only then should a separately reviewed Runtime/experiment revision send frames to the Ditoo.

## 15. Implementation milestones

### LAB-0 — schemas + deterministic compiler

- define sprite/animation schemas;
- implement loader/validator;
- render 768-byte RGB888;
- mirror/anchor/composite primitives;
- deterministic hashes;
- tests.

### LAB-1 — static review artifacts

- nearest-neighbor PNG;
- contact sheet;
- frame/palette/geometry telemetry;
- compare A/B/C;
- exact machine-readable `frames.json`.

### LAB-2 — cadence-aware animation engine

- ACK-driven holds;
- deterministic profile replay;
- single-step/scrub;
- loop handling;
- jitter/no-catch-up behavior;
- tests against known timing fixtures.

### LAB-3 — browser workbench

- playback controls;
- side-by-side variants;
- scale/grid/background/mirror controls;
- telemetry;
- deterministic standalone HTML output.

### LAB-4 — ChatGPT review bundle workflow

- one-command review bundle;
- concise agent instructions;
- quality report;
- source/hash provenance;
- prove a fresh ChatGPT session can reconstruct exact frames from WSL_MCP text output and independently inspect them.

### LAB-5 — procedural adapter

- optional deterministic renderer seam;
- capture/review arbitrary InteractivePage-style frame generators offline.

### LAB-6 — first real consumer: Pocket Moss

- use the lab for all Moss art candidates and animations;
- require side-by-side comparison and at least one autonomous critique/revision before owner selection;
- record lessons that improve the generic lab rather than adding Moss-only hacks.

## 16. Acceptance

The Pixel Animation Lab is successful when a fresh ChatGPT session can, without Bluetooth and without asking the owner to manually inspect every edit:

1. create or modify a 16×16 sprite/animation in text form;
2. validate it deterministically;
3. generate realistic playback/review artifacts;
4. retrieve exact frame content through WSL_MCP;
5. independently reconstruct and visually inspect those frames;
6. identify obvious art/animation weaknesses itself;
7. iterate at least once autonomously;
8. compare alternatives under the same cadence;
9. freeze a candidate with reproducible hashes;
10. hand the owner a small number of genuinely strong candidates rather than a long trail of rough drafts.

That feedback loop is a reusable OpenDitoo capability, not merely a Pocket Moss development convenience.

## 17. Implementation checkpoint — 2026-09-11

The first implementation pass is now real infrastructure, not only a plan:

- LAB-0 schemas/compiler: **PASS**.
- LAB-1 review PNG/contact-sheet/exact frame export: **PASS**.
- LAB-2 deterministic ACK/cadence engine: **PASS**.
- LAB-3 standalone browser workbench: **PASS** for v1 controls (play/pause, step, cadence, grid, mirror, restart, telemetry).
- LAB-4 ChatGPT review bundle: **PASS** and exercised on Pocket Moss; a first-consumer issue with WSL_MCP absolute sandbox provenance was found and fixed so manifests now use portable project-relative paths.
- LAB-5 procedural adapter: **DEFERRED / optional**, not needed for Pocket Moss v1.
- LAB-6 Pocket Moss consumer: **PASS offline**. A/B/C variants were rendered and independently inspected; weak candidates were eliminated; selected art was revised multiple times from observed visual defects before promotion.

The canonical tool entry point is `tools/pixel_lab.py`; fresh-session usage is in `tools/PIXEL_LAB.md`. Generated bundles remain ignored under `.openditoo-local/pixel-lab/reviews/`.
