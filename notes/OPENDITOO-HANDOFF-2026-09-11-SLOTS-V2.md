# OpenDitoo Slots v2 / Runtime 014 handoff — 2026-09-11

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
