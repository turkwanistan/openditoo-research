# OpenDitoo — HF-4 standing successor (Runtime 008) plan — 2026-09-10

**Status:** BUILT OFFLINE (2026-09-10): all gates PASS, template frozen and unauthorized. See the last section of `notes/OPENDITOO-HANDOFF-2026-09-10-HF3.md`. No authority until `Grant OPENDITOO-PRODUCT-RUNTIME-008`. HF-3 is PASS (`OPENDITOO-INTERACTIVE-HF3-008`, see `notes/OPENDITOO-HANDOFF-2026-09-10-HF3.md`). Live product: Runtime 007 + webcam 006 on Host `3faf520f…`. Runtime 007 is the rollback target.

## Accepted architecture (from HF-3 evidence, not design preference)

- **One `streaming_ack_clock` Host session carries every page** (`host/interactive_pages.PageCarousel`). Left/Right change pixels only. Never Host-close/reopen to change pages (HF3-002).
- **Low-rate pages** (dashboard) are held to ~200 ms change-only inside that session; Slots runs ACK-clocked.
- **Pacing** (`host/interactive_stream.InteractiveTransport`): 50 ms client floor **and** ≥ 45 ms after the Host's own previous frame start (`ACK receipt − hostFrameElapsedMs`). Without it: HF3-004 and HF3-005 got terminal 429s.
- **Stock yield:** 409 `SESSION_CANVAS_INVALIDATED`/`SESSION_NOT_ACTIVE` counts as the known yield **only** when the Host's own record says `canvas_invalidated/stopped_yielded_to_stock`; then reclaim the same page immediately. HF3-008: 22/22.
- **Hidden-page MCP collection** runs on a worker joined on navigation. A hidden pulse is consumed and never replayed (live-evidenced in HF3-008).
- **Host:** Runtime 007's first-frame 10 ms spacing (44/44 streaming first frames vs 5/19 failures before).

## Build (side-by-side; Runtime 007 files untouched)

1. `host/product_runtime_v3.py` (new) — a supervisor loop adapted from `product_runtime_v2.run_product`:
   - reuse `ReclaimLimiter`, state persistence and backoff semantics;
   - each session is `run_interactive_stream(carousel)` on a streaming manifest instead of `activity_session.run_session`;
   - page/game state lives on the carousel across sessions;
   - the ButtonProbe `Broker` lifecycle is reused from `host/pagination.py`.
2. **Session envelope** (policy-bound, Host ceiling 1800 s / 45 000 frames): e.g. 600 s lifetime / 15 000 frames per session. Rollover is then a Host-initiated close of an aged link, which is proven safe (HF3-001 and Runtime 006/007 rollovers).
   - Low-rate change-only pages send almost nothing, so no heartbeat storm. A 50 ms stationary poll is already in place.
3. **Reconnect after genuine unavailability:** v2 backoff `[1, 2, 5, 10, 30]`, which Runtime 007 exercised on 2026-09-10 (battery loss → 42 attempts → unattended reconnect).
4. **Pages v1:** `dashboard` (live MCP renderer with the UI-1 lightning) and `slots`. The Runtime 006/007 `spiral` is dropped unless the owner wants it kept.
5. **Telemetry (bounded):** selected page, session id and profile, realized-FPS window, last input seq/type/action, last input→first-ACK, reclaims/reconnects, slots round/stopped reels. Publish at the first ACK of each transition (fixes the Runtime 006 `first_ack_ms` null defect).
6. **Webcam coexistence:** `scripts/webcam_on_demand.sh` stops/starts `openditoo-product.service`. Verify Runtime 008 releases the Host and restores after the webcam closes. Webcam 006 is unchanged (same Host).
7. **Policy:** `product/OPENDITOO-PRODUCT-RUNTIME-008.json` plus a loader that pins pages, envelope, pacing constants and code hashes. `cli/openditoo.py` dispatches on `runtime_revision` 4. Add a cutover script with an exact-byte rollback to Runtime 007 (pattern: `cutover_runtime_007.sh`, including the in-main offline gate before restart and a saved gate log).

## Before building: merge prerequisite

This branch changes `host/frame_stream.py` (HF-1 idle poll), so the Runtime 007 template is not hash-valid here (3 expected legacy errors). Runtime 008 must re-hash `frame_stream.py` in its own policy, which is expected. At cutover, `main` fast-forwards to this branch, so Runtime 007's rollback must restore those source bytes too, via `git revert` of the merged range, as the 007 script does.

## Offline gates (before any grant)

- A fake-Host supervisor soak using the hardened `scripts/interactive_hf3.FakeHost` (40 ms floor, 12/0 ms arrival jitter, 20 ms ACKs, mid-send and watchdog yields). It must survive thousands of simulated frames, rollovers, and backoff after injected open failures.
- Page state survives reclaim, rollover and reconnect; no duplicate input; the dashboard pulse is never replayed.
- Full legacy + successor suites, and the policy loader refuses drift.

## Standing acceptance after grant (owner-present)

- Dashboard↔Slots repeated transitions.
- The **lightning visual** (still unaccepted: trigger it with the Dashboard visible).
- Lever reclaims.
- Device power-cycle while on the Dashboard and while on Slots.
- Webcam shortcut suspend → restore.
- Spotify/media contention.
- Windows logon startup (still pending from Runtime 001).

## Authority

Runtime 008 needs the exact grant `Grant OPENDITOO-PRODUCT-RUNTIME-008` against its frozen template. Webcam 006 stays as is (same Host). Offline build is within standing permission; nothing live without that grant.
