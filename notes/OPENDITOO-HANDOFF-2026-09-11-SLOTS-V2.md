# OpenDitoo Slots v2 / Runtimes 014–016 handoff — 2026-09-11 (LIVE, accepted)

## Why v2

Owner: the Runtime 013 Slots page was "straight up impossible". Reels hard-stopped at arbitrary pixel offsets, rows never lined up, and there was no win condition. Requested changes: snap-to-symbol stops, a reachable win, win and lose animations, and nicer art. "A little skill based" was wanted, and a new-round pull may wait until the result is over (no interrupt).

## What changed (host/slots_page.py only)

- **Snap stops.** A pull locks the next symbol that will reach the payline (y6–10). `brake_steps` runs to that alignment in steps of at most the spin speed, eases down to 1 px, then overshoots 1 px and settles back: at most 8 ACKed frames, no catch-up. All three reels always rest aligned. The result is fixed at the third pull, so `stopped_reels`/`state`/`result` stay synchronous. Added telemetry: `outcome`, `busy`.
- **Speeds.** Left 1 px/frame (aimable; a seeded aim model lands a chosen seven ~96%), middle and right 2 px/frame. Reels move down and start staggered 0/2/4 frames. A new round restarts from where the reels rested.
- **Strips and rules.** Each reel has 8 stops (3 cherry, 2 seven, bar, diamond, star) in a different order. Outcomes: small = left and middle match, big = three of a kind, jackpot = 7-7-7. Near miss = a small win where the right reel's next symbol would have made three. The seeded 50k simulation gives small 17.7%, big 5.8%, jackpot 1.6%, any win ~25%, near miss 7.4%.
- **Outcome animations, ACK-paced and bounded.** Lose 4 frames (chevron red/dim), small 10 (pulse), big 16 (plus gap-row sparkles), jackpot 24 (plus coin fountain and lamp chase). A lever pull during settle or animation returns `result_hold`.
- **Art.** Shaded 5×5 symbols (h/#/s tones, cherry has green stems, no near-black), off-payline rows at 45%, gold payline chevron at x15 y7–9, reel lamps at x15 y1–3.

## Trap found and fixed: ACK stall

The stream never sends an unchanged frame, so an ACK-advanced animation with two identical consecutive frames never gets its next ACK and stalls forever (see the `frame_stream` docstring). Every animation frame now differs from the previous one. `SlotsPageTests.tick` drives the page change-only like the stream. `test_stationary_slots_result_sends_once_then_holds` proves settle plus animation finish inside the real `run_interactive_stream` loop. A mutation back to paired pulse frames fails two tests.

## Runtime 014

Branch `feat/slots-v2-polish` (worktree `.openditoo-local/worktrees/slots-v2`). Mechanical clone of the 013 shape:

- `host/product_runtime_v8.py` (`runtime_revision=9`). The slots page was already hash-bound (`slots_page_sha256`); there are no new assets. Pages, session, target, behavior, install, Host `3faf520f…`, ButtonProbe and webcam 006 equal Runtime 013.
- `product/OPENDITOO-PRODUCT-RUNTIME-014.json` committed unauthorized (three expected blockers). `cli/openditoo.py` routes revision 9 to v8.
- `scripts/cutover_runtime_014.sh`: exact grant `Grant OPENDITOO-PRODUCT-RUNTIME-014`, requires live 013, rolls back to `.openditoo-local/rollback-runtime-013` via `--rollback`.
- Tests: new `test_product_runtime_v8` and rewritten `SlotsPageTests`. `test_day1_offline` treats 014 as current. `test_product_runtime_v7` is historical (its stored hashes differ from this tree only in `slots_page_sha256`/`cli_sha256`). Two `test_product_runtime_v3` harness tests were adjusted for the held new-round pull: ~1.2 s paced pulls now sometimes return `result_hold`, and a static result sends no frames.

## Offline verification (worktree)

- `verify_interactive_pages_offline.py`: PASS, 122 tests, including `SLOTS_V2_OFFLINE` and `RUNTIME_014_SUCCESSOR_OFFLINE`.
- `verify_day1_offline.py` in the worktree: 13 failures out of 326, identical to a clean `main` baseline worktree (git-ignored Release outputs). The cutover re-runs both full gates in main.
- R014 template precheck (the cutover's `template_ok`): PASS.

## Runtime 014 live, then Runtime 015 aim tuning

Owner granted exactly `Grant OPENDITOO-PRODUCT-RUNTIME-014`. `scripts/cutover_runtime_014.sh` reported `R014_CUTOVER_PASS main=a43a9a6 host=3faf520f46ce rollback=.openditoo-local/rollback-runtime-013`. Post-cutover `product-status`: connected, `last_error=null`, revision 9.

Panel feedback: "its pretty hard lol, i only managed 1 small win in a lot of rounds, maybe slow down rows 2 and 3 a little". Root cause: the 014 rule stopped on the *next* symbol to reach the payline. A pull lands 1–3 ACKs after the player sees a symbol centred, and by then that symbol has passed alignment, so aiming at what you see hit **0% at any speed**. Slowing the reels alone would not have helped.

Runtime 015 (`feat/slots-v2-aim`, `host/product_runtime_v9.py`, `runtime_revision=10`, `cutover_runtime_015.sh` requiring live 014, rollback to `.openditoo-local/rollback-runtime-014`):

- `brake_steps` stops on the symbol nearest the payline. If it passed alignment by at most `SLIP_BACK_MAX=3` px, the reel slips back 1 px per frame; otherwise it runs on. The 1 px bounce is kept, and every step stays within the spin speed.
- Middle and right reels use `REEL_STEPS=(1, 2)`, averaging 1.5 px/frame (was 2). Left stays at 1.
- Aimed hit rate (pull when centred, landing 1–3 frames late): left 100%, middle and right 67%, pinned by `test_aimed_pull_lands_the_symbol_seen_on_the_payline_despite_input_lag`. Random-timing odds are unchanged: any win ~25%, jackpot ~1.6%.
- Offline: `verify_interactive_pages_offline.py` PASS, 129 tests (`SLOTS_V2_AIM_OFFLINE`, `RUNTIME_015_SUCCESSOR_OFFLINE`). Day-1 in the worktree: 13 failures, identical to a clean Runtime 014 `main` baseline.

## Runtime 015 live, then Runtime 016 smooth reels

Owner granted exactly `Grant OPENDITOO-PRODUCT-RUNTIME-015`: `R015_CUTOVER_PASS main=55d882c host=3faf520f46ce rollback=.openditoo-local/rollback-runtime-014`, connected, revision 10.

Panel feedback: middle/right reels "pretty smooth but sometimes it will slow down then jump aheadish". Transport is ACK-clocked with a 50 ms client floor and no other cap; HF3-008 recorded client ACK p50 48 ms / p95 83 ms and 12–19 transport fps per session (panel FPS unmeasured). Cause: Runtime 015's alternating 1/2 px middle/right steps. A late ACK pauses the reel, and the following 2 px step reads as a jump. The left reel (steady 1 px) was fine.

Runtime 016 (`feat/slots-v2-smooth`, `host/product_runtime_v10.py`, `runtime_revision=11`, `cutover_runtime_016.sh` requiring live 015, rollback to `.openditoo-local/rollback-runtime-015`):

- `REEL_SPEEDS=(1, 1, 1)`, pinned by `test_every_reel_spins_a_steady_1px_per_frame`. Aim difficulty moves to `SLIP_BACK=(3, 2, 2)`.
- Aimed hit rate (pull when centred, 1–3 frames late): left 100%, middle/right 67%, same as 015. Random-timing odds unchanged: any win ~25%, jackpot ~1.6%.
- Offline: interactive gate PASS, 136 tests (`SLOTS_V2_SMOOTH_OFFLINE`, `RUNTIME_016_SUCCESSOR_OFFLINE`). Day-1 in the worktree: 13 failures, identical to a clean Runtime 015 `main` baseline.
- The successor clone is now scripted (scratch `gen_successor.py`). The cutover script is still authored by hand with the Write tool.

## Live acceptance (Runtime 016)

Owner granted exactly `Grant OPENDITOO-PRODUCT-RUNTIME-016`: `R016_CUTOVER_PASS main=2c4177b host=3faf520f46ce rollback=.openditoo-local/rollback-runtime-015`. Post-cutover `product-status`: connected, `last_error=null`, revision 11, policy `OPENDITOO-PRODUCT-RUNTIME-016`.

Owner verdict on the panel: **"okay its winnable now, but hard."** Runtime 016 is the accepted live baseline and Runtime 015 is the exact rollback. No transport/product re-acceptance was needed (Slots-page-only change).

## Next session

- Start from Runtime 016 as accepted truth. If the owner wants Slots easier, the lowest-risk knobs are a wider middle/right `SLIP_BACK` (3 → aimed 100%) or a fourth cherry per strip (raises the pair rate). Ship either as a fresh successor (Runtime 017, `product_runtime_v11`, revision 12).
- Still open: panel FPS and per-frame ACK timing are unmeasured live. The runtime only keeps `realized_fps_5s`. Occasional late ACKs show as brief reel pauses. Pacing (50 ms floor + 45 ms Host-anchored gap) was deliberately left unchanged. Revisit only if the pauses bother the owner.
- The review page (scratch tooling, not committed) was `https://claude.ai/code/artifact/27b79e3d-e27f-4acb-aedf-f821360db070`.
