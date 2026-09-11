# OpenDitoo handoff — Pocket Moss + Pixel Animation Lab — 2026-09-11

## Executive state

**Runtime 009 remains the accepted live product. No Runtime 010 grant has been given and no device I/O occurred during this development phase.**

The Pocket Moss / Pixel Animation Lab successor is implemented offline on `feat/pocket-moss-pixel-lab` as **Runtime 010** (`runtime_revision=5`). It is intentionally unauthorized and stops at the exact owner-grant / normal-local-WSL cutover boundary.

Runtime 010 preserves Runtime 009's exact Host, target, ButtonProbe, one-session topology, pacing, reconnect/reclaim rules and webcam policy. It adds:

- reusable text-first 16×16 Pixel Animation Lab infrastructure;
- selected A2-based Pocket Moss v1 art and authored animations;
- a lightweight WSL-owned `MossPage` behavior state machine;
- generic page-first modal Left/Right capture;
- `Dashboard <-> Slots <-> Moss` in the existing one `streaming_ack_clock` Host session;
- icon-only `Pet <-> Dance <-> Kisses <-> Back` controls;
- Runtime 010 policy/cutover/rollback machinery with every Moss JSON asset hash-bound.

## Read next

1. `notes/OPENDITOO-POCKET-MOSS-IMPLEMENTATION-PLAN-2026-09-11.md`
2. `notes/OPENDITOO-PIXEL-ANIMATION-LAB-PLAN-2026-09-11.md`
3. `notes/OPENDITOO-POCKET-MOSS-ART-REVIEW-2026-09-11.md`
4. `AGENTS.md`

## Pixel Animation Lab

Implemented reusable infrastructure:

- `host/pixel_art.py` — `openditoo.pixel-sprite.v1`, literal 16×16 rows/palette, exact 768-byte RGB888, deterministic hashes, mirror/translate, geometry/diffs, stdlib PNG/contact sheets.
- `host/pixel_animation.py` — `openditoo.pixel-animation.v1`, ACK-authored holds, deterministic cadence profiles, no-catch-up progression, quality checks.
- `tools/pixel_lab.py` — `validate`, `render`, `compare`, `review-bundle`, `list`, `serve`.
- `tools/PIXEL_LAB.md` — fresh-session workflow.
- `tests/test_pixel_lab.py` — compiler, animation, deterministic preview, bundle/provenance checks.

Review bundles are generated under ignored `.openditoo-local/pixel-lab/reviews/<id>/` and contain exact `frames.json`, `quality.json`, portable `manifest.json`, `contact-sheet.png`, `preview.html`, and `README.txt`. Bundle source paths are project-relative, not WSL_MCP sandbox paths, so another ChatGPT session can reconstruct exact frames from text.

LAB-0 through LAB-4 are substantially complete. LAB-5 procedural adapter remains optional/future; it is not a blocker for Pocket Moss. LAB-6 is proven by Pocket Moss as the first serious consumer.

## Pocket Moss visual freeze

Product assets live only under `assets/pocket_moss/v1/`; exploratory A/B/C candidate files were deliberately discarded after review rather than becoming product baggage.

Selected identity: revised **A2 side profile** — compact horizontal brown/cream quadruped, short legs/muzzle, low center of gravity, asymmetric canine acting.

Final idle geometry:

- bbox `[1,3,14,12]`;
- 74 occupied pixels;
- no edge touches;
- no disconnected one-pixel islands;
- canonical sprite hash `4eb552b2098e23793994a6aae8630a2f40ed25b834bae4c11b0b1936d82e4bba`.

Autonomous visual critique/revision is documented in `notes/OPENDITOO-POCKET-MOSS-ART-REVIEW-2026-09-11.md`. Key fixes found by the lab loop itself:

- Look: whole-body/edge drift -> head-led motion, final deltas `17,17`.
- Dance: ~70-pixel sliding -> anchored paw/tail acting, final deltas `9,9,9,27,26`.
- Kisses: detached rear heart -> heart beside/above the head.
- Pet selector glyph: A-like symbol -> paw-like 3×3 symbol.

Final promoted animation hashes:

- Look `9b8276d7088bdccbd25e8794c1528210b2d573291c33be6003961908335ad88c`
- Loaf `ec5e6d8faae3f0e36860dc400a9124d4e05759f25f3d81311fbf2d39e9914c95`
- Sleep/Wake `e77cbe23dc3319df0be81f6db5c1c2457ecc6fb0b5041c3ca401561cd6baf0f6`
- Pet `6ab19a27e7032926f5364b6b89dc8147902f8123fe9646834a88736fb0c5ccb3`
- Dance `3c6d979e53addd1947121c216a67039a7d04bc26af965930ff942c787ca1144e`
- Kisses `47ffdf13f4ec1cd4f9cccb72227ba5027a8e30a831e2ec02a040f11c2ed5b4a7`

All promoted animations report zero Pixel Lab animation warnings. Physical-panel readability is deliberately still pending.

## `MossPage`

`host/moss_page.py` is a normal `streaming_ack_clock` interactive page. It owns presentation state only; no Bluetooth/Host/persistence/Terrarium dependency exists.

Modes:

- `normal`: passive Moss; Left/Right are global carousel controls; lever enters selector.
- `selector`: one 3×3 glyph in the top-right corner; Left/Right cycle Pet/Dance/Kisses/Back; lever executes.
- `action_animation`: glyph hidden; Pet/Dance/Kisses animation owns visual focus; Left/Right are swallowed; completion returns to selector.

Back immediately returns to normal mode and therefore restores global Left/Right navigation.

Passive behavior is intentionally sparse: deterministic weighted Look/Loaf/Sleep-Wake after long quiet windows, with no needs, hunger, health, guilt, inventory or simulation engine.

## Generic modal navigation

`host/interactive_pages.py` now gives the current visible page first refusal on a navigation event. If the page consumes it, `PageCarousel` remains on the current page; otherwise normal global wraparound occurs.

This is generic and has no `if moss` branch. Tests pin:

- selector Left/Right never pages away;
- action animation swallows navigation;
- normal Moss Left/Right remains global;
- buffered navigation+lever events preserve order and are applied at most once;
- no event leaks to the next page.

## Runtime 010

Files:

- `host/product_runtime_v4.py`
- `product/OPENDITOO-PRODUCT-RUNTIME-010.json`
- `scripts/cutover_runtime_010.sh`
- `tests/test_product_runtime_v4.py`

Runtime 010 uses revision `5` and the exact required grant text:

`Grant OPENDITOO-PRODUCT-RUNTIME-010`

The committed template is disabled. Current authority blockers are intentionally:

- `PRODUCT_AUTHORITY_MISSING`
- `PRODUCT_AUTHORITY_UNATTRIBUTED`
- `PRODUCT_AUTHORITY_SCOPE_MISMATCH`

The policy contains **36 exact code/asset hashes**, including `MossPage`, Pixel Lab compile/animation code and every JSON under `assets/pocket_moss/v1/`. Hash parity with the source tree is PASS.

The Host stays `3faf520f46ce824970f583c3d932e0168484b0f6ffa5975e6b38e77330c4900f`; ButtonProbe, target, session limits, pacing, reconnect, reclaim and webcam 006 are unchanged from Runtime 009.

The cutover is exact-grant gated, requires current policy 009, verifies Host/policy/offline gates before restart, materializes only a local mode-0600 authorized policy, and saves exact Runtime 009 rollback state. Rollback restores Runtime 009 tree+policy and requires revision-4 `product-check` before restart.

## Verification

Focused successor gate:

`python3 scripts/verify_interactive_pages_offline.py`

Result: **83/83 PASS** with:

- `PIXEL_ANIMATION_LAB_OFFLINE=PASS`
- `POCKET_MOSS_OFFLINE=PASS`
- `RUNTIME_010_SUCCESSOR_OFFLINE=PASS`

Runtime 010 synthetic product acceptance also proves Dashboard -> Slots -> Moss -> selector -> Dance -> selector inside **one Host session**, with exactly ordered inputs and zero reconnect/reclaim.

Broad legacy gate under WSL_MCP:

`python3 scripts/verify_day1_offline.py`

Result remains the exact baseline limitation: 326 tests run, four environment-only errors and one skip. Two errors are inaccessible staged ButtonProbe files under `/mnt/c`; two are missing Pillow in parked W9B optical tests. These were the same four errors before implementation; no new broad regression appeared. The real cutover script reruns the full gate from normal local WSL, where `/mnt/c` and the owner environment are available.

## Live boundary / next action

Do not transmit from WSL_MCP and do not infer authority from the existence of Runtime 010.

When the owner chooses to promote the successor:

1. confirm primary live checkout is still clean Runtime 009/main;
2. run the Runtime 010 cutover from the clean feature worktree in **normal local WSL**, not WSL_MCP;
3. this requires the explicit owner grant `Grant OPENDITOO-PRODUCT-RUNTIME-010`;
4. perform the smallest physical acceptance: Dashboard -> Slots -> Moss, observe passive Moss, selector cycle, Pet/Dance/Kisses, Back -> global navigation, page away/back, then one known reclaim/yield if needed;
5. if literal-panel art needs adjustment, return to Pixel Lab first; do not broaden live testing or rebuild transport.

No standing-product claim should be made until that physical acceptance passes.
