# OpenDitoo handoff — HF-4 closed, Runtime 009 live — 2026-09-11

## Current state

- **Live:** Runtime 009 (`OPENDITOO-PRODUCT-RUNTIME-009`, runtime_revision 4) and webcam 006, on Host `3faf520f…`. The service `openditoo-product.service` runs from `main`.
- **What it is:**
  - One `streaming_ack_clock` Host session per connection carries two pages, **Dashboard** (default at every start, with UI-1 lightning) and **Slots**.
  - Left/Right change pixels only. The lever is the page's own action: Slots stops the next reel, and after the third starts a new round.
  - Code: `host/product_runtime_v3.py`. Policy: `product/OPENDITOO-PRODUCT-RUNTIME-009.json` (pages, envelope, pacing and 16 code hashes pinned).
- **Rollback chain:** `bash scripts/cutover_runtime_009.sh --rollback` restores 008; 008's `--rollback` restores 007. Each restores the exact source tree and local policy, and saves its state in `.openditoo-local/rollback-runtime-00N/`.
- **Branch:** `feat/high-fps-interactive-pages` is fast-forwarded into `main`, and both are pushed.

## Accepted decisions (with their evidence)

- **Single-session carousel.** A Host close/reopen to change pages is unsafe (HF3-002); the carousel was accepted in HF3-008.
- **Pacing:** a 50 ms client floor plus a 45 ms Host-anchored gap (HF3-004/005). A 409 `SESSION_CANVAS_INVALIDATED`/`SESSION_NOT_ACTIVE` counts as a yield only when the Host's own record confirms it (HF3-006/007).
- **Supervisor semantics are Runtime 007's:** 600 s / 15 000-frame sessions renew; Host-confirmed yields reclaim immediately behind the storm guard; genuine unavailability backs off 1/2/5/10/30 s.
- **Lightning:** the glow draws only the icon's own pixels. The Runtime 008 aftershock pixels read as a stray spark (owner review), so 009 removed them.
- **Rollback method:** a merged range contains merge commits, which `git revert A..B` refuses. Rollbacks therefore use `git read-tree -u --reset <pre>` plus a forward commit and a tree-hash check.

## Verification

- **Offline:** legacy `verify_day1_offline.py` 326 PASS; successor `verify_interactive_pages_offline.py` 59 PASS. The FakeHost soak ran 247 sessions / 11 680 frames / 240 reclaims / 2 rollovers / 4 open failures.
- **Standing acceptance (owner-present, PASS):** Dashboard↔Slots and lever reclaims, lightning on all three sources, a live 600 s rollover, a power cycle on Dashboard and one on Slots (about 18 s and 8 s to reconnect), and two webcam suspend→restore runs. Evidence: `captures/OPENDITOO-RUNTIME-008-009-STANDING-ACCEPTANCE-2026-09-11.json`. Narrative: the last sections of `notes/OPENDITOO-HANDOFF-2026-09-10-HF3.md`.
- **Windows-logon startup:** PASS. After the 09-10 reboot the dashboard came up unattended 18 s after logon. The Host task's 72 h ExecutionTimeLimit was removed in the installer and on the live task (`PT0S`, verified).
- **First-frame timeouts on the current Host:** 1 in 100 streaming opens, absorbed by the backoff.

## Environment facts learned

- **An icon going grey right before its lightning strike is a clock problem.** This PC ran 0.6 s slow because the Windows Time service was Stopped, which made OptiPlex audit stamps look like the future.
  - Fixed: W32Time is Automatic, hourly, with `MaxAllowedPhaseOffset 0`; WSL chrony follows via `PHC0`.
  - Check `chronyc tracking` and `w32tm /query /status` before touching the code.
- Changing the Windows tasks needs an admin terminal. `Set-ScheduledTask -InputObject` fails with a `UserId` error; use `-Settings`.

## Open (optional)

- Spotify media-key contention (not tested).
- The Host records close reason `page_transition` on a service stop, because `run_interactive_stream` passes that `stop_reason`; this is cosmetic.
- Slots state and the selected page reset on service restart (logon, webcam hand-back). Keeping them would be a new revision.

## Next objective

None is committed; the owner chooses. Any change to a hashed module (pages, lightning, pacing, CLI, `frame_stream`) goes on a branch with a fresh reviewed revision and the exact named grant. Never re-arm consumed ids.
