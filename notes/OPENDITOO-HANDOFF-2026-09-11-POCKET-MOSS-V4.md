# OpenDitoo Pocket Moss v4 / Runtime 013 handoff — 2026-09-11

## Why v4

Owner asked for an art/animation/style pass after accepting v3 "good for now": Moss is cute but should read more distinctly at 16×16, and the actions need polish. v4 was reviewed offline (exact-pixel and LED-dot simulation GIFs, v3 vs v4) and the owner asked to see it on the panel.

## What changed (art/choreography only)

- Front-facing seated body replaces v3's 3/4 body (the source of the "derpy/deformed" read). Cream chest, four cream paws, upright tail.
- Face centred on the eye axis: eyes x5/x10, 2 px nose and 2 px tongue at x7–8 (v3's nose sat 1 px off-centre).
- One light direction: `l` highlight top-left of the forehead, `s` amber shadow down the right side; still no dark outlines (v1 lesson).
- Teal collar `k` + gold tag `g` separate head from body and give Moss a signature accent. Sleep Z's are blue `z` so they never read as fur/cream.
- Every pose is composed by `tools/moss_v4_art.py` from one shared head/ear/face/body/tail model; `assets/pocket_moss/v4/` is its exact output (pinned by `tests/test_moss_v4_art.py`).
- Animations: Look (blink, head turn with pupil shift, ear lift), Loaf (perk, lying mound with paws, blink), Sleep-Wake (two drifting Z frames, yawn, blink), Pet (perk, lean, squish + blush, 2 wags), Dance (crouch, L/R/L/R sway with trailing ears, re-crouch, hop, squash land, wag), Kisses (perk, lean + long tongue + small heart, big heart, sparkle pop + wink, wag). 22 unique sprites; all Pixel Lab warning-free.

## Runtime 013

Branch `feat/pocket-moss-v4-polish` (worktree `.openditoo-local/worktrees/moss-v4`). A mechanical clone of the Runtime 012 successor shape:

- `host/product_runtime_v7.py` (`runtime_revision=8`) = v6 with the v4 asset set hash-bound (48 hashes); pages/session/target/behavior/install, Host `3faf520f…`, ButtonProbe and webcam 006 must equal Runtime 012 or the policy refuses.
- `product/OPENDITOO-PRODUCT-RUNTIME-013.json` committed unauthorized (three expected authority blockers); `cli/openditoo.py` routes revision 8 → v7.
- `host/moss_page.py`: `ASSET_ROOT` → v4 only.
- `scripts/cutover_runtime_013.sh`: exact grant `Grant OPENDITOO-PRODUCT-RUNTIME-013`, requires live policy 012, rollback to `.openditoo-local/rollback-runtime-012` via `--rollback`.
- Tests: new `test_moss_v4_art`, `test_product_runtime_v7`; `test_moss_v3_art`/`test_product_runtime_v6` now target v3/012 as historical; `test_day1_offline` treats 013 as current.

## Offline verification (worktree)

- `verify_interactive_pages_offline.py`: PASS, 111 tests, incl. `POCKET_MOSS_V4_ART_OFFLINE` / `RUNTIME_013_SUCCESSOR_OFFLINE`.
- R013 template precheck (same as the cutover's `template_ok`): PASS; `MossPage` renders `moss.v4.idle`.
- `verify_day1_offline.py` cannot pass inside a linked worktree: 13 failures identical to the untouched v3 worktree (missing git-ignored Release DLL); with main's build outputs symlinked in, 6 remain, all consumed-claim ledger checks for W8/W9B/W10 that read main's local claim state. The cutover runs both gates in main after the fast-forward and rolls back on failure.

## Physical review

Keep it short: page to Moss, judge idle, then run Pet / Dance / Kisses once. No transport/product re-acceptance unless a systems symptom appears. Runtime 012 is the rollback.
