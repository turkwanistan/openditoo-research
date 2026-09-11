# OpenDitoo handoff — HF-3 interactive acceptance — 2026-09-10

## TL;DR for the next session

- **Live:** Runtime 007 + webcam 006 on Host `3faf520f…`, `connected`. Rollback: `bash scripts/cutover_runtime_007.sh --rollback` (from main).
- **HF-3 PASS** = `OPENDITOO-INTERACTIVE-HF3-008` (`captures/OPENDITOO-INTERACTIVE-HF3-008-LIVE-2026-09-10.json`). 001–007 are consumed; their failures and fixes are below, in order.
- **HF-4 / Runtime 008 is BUILT OFFLINE, frozen, grant-ready and UNAUTHORIZED** (see the last section). Going live needs exactly `Grant OPENDITOO-PRODUCT-RUNTIME-008`, then `bash scripts/cutover_runtime_008.sh "Grant OPENDITOO-PRODUCT-RUNTIME-008"` from this worktree.
- **Open:** the lightning-strike visual has never been owner-observed. Trigger it with the Dashboard visible.
- **Traps learned today (all evidenced below):**
  - streaming first-frame timeouts on the old Host;
  - never Host-close/reopen to change pages;
  - fast ACKs need the 50 ms client floor **and** the Host-anchored 45 ms gap;
  - lever `0xBD` mid-send surfaces as 409 `SESSION_CANVAS_INVALIDATED` **or** `SESSION_NOT_ACTIVE`, and counts as a yield only when the Host confirms;
  - start runs on the owner's first press (two ids were lost to a missed start cue);
  - the headless Host task orphans the Host on task stop;
  - the Ditoo battery can die mid-session.
- **Run pattern for any live experiment:** start `scripts/hf3_operator_assist.py` in the background, then `grant` → `check` → `bash scripts/run_interactive_hf3.sh`.


Feature worktree: `feat/high-fps-interactive-pages`. Runtime 006 on `main` remains the live rollback baseline.

## HF3-001 — consumed, transport clean, acceptance NOT MET

Run from normal local WSL (with `/mnt/c` and `powershell.exe`). All pre-grant invariants were verified independently: manifest `7ad8ef4d…`, no claim, installed ButtonProbe `79521fba…`/`d85c1298…`, Host `f7bd60d4…` bound to `11:75:58:CE:DE:C7`, raw-send off, Runtime 006 `connected`, no second controller. The already-given grant was materialized at 19:33Z and the run went 19:34:09–19:35:39Z.

Result: `lifetime_expired` / `stopped_clean`, 90.0 s. Two activity children, 13 frames / 39 packets / 2,534 B, and the Host ledger agrees exactly. No retry, reconnect, reclaim or `IMAGE_RX_RECV_TIMEOUT`. **0 of 10 cycles, 0 SMTC events**: the owner did not press in time, because nothing marks when the window opens (the Dashboard looks the same before and after suspension). The only raw input was keyboard Volume-Down, correctly ignored. Runtime 006 was restored and independently verified `connected`. Afterwards Right switched pages under Runtime 006, so the SMTC path is healthy. Visual: not observed. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-001-LIVE-2026-09-10.json`. **Replay forbidden.**

Design finding: the 001 envelope could not have met 10 cycles at human pace anyway. 500 frames at about 18 fps of spinning is roughly 28 s of Slots. With BTN-7's every-other-pull `0xBD` reclaim, a cycle costs about 4 child attempts, so 28 attempts is about 6 cycles. The dry-run FakeHost modeled neither. A new negative-control test pins this.

## HF3-002 — consumed/unknown: IMAGE_RX_RECV_TIMEOUT on the first profile switch

The owner granted `Grant OPENDITOO-INTERACTIVE-HF3-002`. The GO popup worked. At the owner's first Right (19:47:39.193Z), S001 (activity, 4.3 s old, 1 frame) closed cleanly and S002 (`streaming_ack_clock`) opened **29 ms later**. S002's first frame got `IMAGE_RX_RECV_TIMEOUT; NO_RETRY` (0 frames, `unknown_nothing_sent`). The run failed closed as `transport_fault`/`unknown` with no retry. Runtime 006 was restored and independently verified `connected` (nonce `7ef5a100`). Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-002-LIVE-2026-09-10.json`. **Replay forbidden.**

Diagnosis from exact-unit ledgers: a **Host-initiated close followed by a reopen**, most often of a seconds-old link, leaves the Ditoo silent. This is 4 cases: W9B-006, the W10 15:04 launch (after an 8 s settle), webcam-product-001 #4, and HF3-002. Device-ended `0xBD` sessions of the same age reopen cleanly in 46–69 ms (BTN-7), as do aged Host rollovers (HF3-001, Runtime 006). A longer settle is not the cure. The Host already encodes this lesson (W10C, "one connection"). HF-2's close-and-reopen-per-profile paging is therefore structurally unsafe. Do not retry that shape.

## Root cause revised: streaming first-frame timeout (not young links)

At 19:49:22Z the owner launched the webcam shortcut under its own policy. It stopped a **99 s-old** Runtime 006 session, and its streaming session opened 12 s later, then **also** got first-frame `IMAGE_RX_RECV_TIMEOUT`. That falsifies the young-link/fast-reopen explanation above.

The whole Host ledger (`scripts/analyze_first_frame_timeouts.py`, capture `captures/OPENDITOO-STREAMING-FIRST-FRAME-TIMEOUT-ANALYSIS-2026-09-10.json`) shows:

| Opens | First-frame `IMAGE_RX_RECV_TIMEOUT` |
|---|---|
| **5 of 19** `streaming_ack_clock` | 5 |
| **0 of 199** `activity` | 0 |

- Gap and predecessor age do not separate the outcomes.
- After frame 1 ACKs, streaming sessions run thousands of frames cleanly.
- The only per-profile transport difference is intra-frame packet spacing: 0 ms for streaming vs 10 ms for activity.

Hypothesis: the Ditoo sometimes drops a zero-spacing burst sent right after RFCOMM connect.

## HF3-003 — prepared, then grant WITHDRAWN before use

The owner granted `Grant OPENDITOO-INTERACTIVE-HF3-003` and I materialized it. I then withdrew it **before any claim or device I/O**, because HF3-003 needs about 21 streaming opens (1 plus about 20 `0xBD` reclaims). At a 26 % first-frame failure rate it would almost certainly fail. The manifest status is `grant_withdrawn_before_use`, and any re-arm needs a fresh grant. Its single-session `PageCarousel` design remains correct: it still removes planned close/reopen and is the right HF-4 shape.

## Candidate Host fix — built, NOT deployed (authority boundary)

`ActivitySessionHost.SendFrame`: every session's **first frame uses the proven 10 ms spacing**, and later frames use the profile's spacing.
- Source is on this branch. The static pin test is updated.
- Legacy suite: 321/322. The one error, `test_006_template_hashes_match_this_tree`, predates this change: `host/frame_stream.py` was already changed by `65723e6`.
- Successor suite: 40/40.
- Built side-by-side at `%LOCALAPPDATA%\OpenDitoo\build\host-firstframe\out`, DLL `07e44ee6…`. **Not installed.**

Installing it changes the Host hash that Runtime 006 (`f7bd60d4…`) and webcam policy 005 bind. Both then need re-bound successor revisions (precedent: Runtime 004 was a Host re-bind only) and owner grants.

**Prepared (2026-09-10):** Runtime 007 + webcam 006 on branch `feat/host-first-frame-spacing` (`46c8b9d`, off main). It has a reproducible Host `3faf520f…` (PathMap), an exact-byte rollback, and needs two grants. See that branch's `notes/OPENDITOO-HOST-FIRST-FRAME-REBIND-2026-09-10.md`. After cutover, rebase this branch onto main and re-freeze HF3-004 against `3faf520f…`.

**Next (owner decision):**
1. Approve a reviewed Host re-bind revision that installs the first-frame-spacing Host, with Runtime 006 → re-bound runtime and webcam 005 → re-bound policy, preserving rollback to the `f7bd60d4` Host.
2. Then run a fresh HF-3 (`…-HF3-004`) on the `PageCarousel` design.

The webcam shortcut is also affected (5/19 is mostly webcam launches), so this fix benefits the webcam product too.

## Runtime 007 live → HF3-004 prepared, grant-ready, UNAUTHORIZED

- **Runtime 007 + webcam 006:** live since 20:42Z. They run the first-frame-spacing Host `3faf520f…`. Evidence: `captures/OPENDITOO-RUNTIME-007-CUTOVER-2026-09-10.json`.
- **Merge:** `main` is merged into this branch. Only the Runtime 007 template hash tests fail here, and only on `frame_stream_sha256` (this branch's HF-1 change, inherent until HF-4).
- **HF3-004** (`experiments/DAY1-INTERACTIVE-HF3-004.json`, `e2a8790b…`) keeps HF3-003's single-session `PageCarousel` design and envelope (150 s / 32 / 1500, streaming only), bound to Host `3faf520f…`.
  - Paced dry-run: 10 cycles, 21 sessions.
  - Successor suite: 40/40.
  - It is also the first on-device evidence for the first-frame fix. The Host ledger's open record still shows the profile spacing (0); the first-frame 10 ms exception lives in `SendFrame`.
  - It needs the exact grant `Grant OPENDITOO-INTERACTIVE-HF3-004`. The run procedure is unchanged: operator-assist, then `grant`, `check`, and `run_interactive_hf3.sh`.

## HF3-004 — consumed/unknown (429 pacing); HF3-005 prepared, grant-ready, UNAUTHORIZED

**HF3-004** (20:48Z) opened one streaming session on the Runtime 007 Host, and the **first frame ACKed**. That is the first-frame fix's first on-device evidence (1/1). On the owner's Right, a Slots frame ACKed in **21 ms**. The ACK-clocked loop then dispatched inside the Host's 40 ms floor, which produced a terminal HTTP 429. No retry; Runtime 007 was restored `connected`. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-004-LIVE-2026-09-10.json`.

**HF3-005** (`experiments/DAY1-INTERACTIVE-HF3-005.json`, `c8057d04…`):
- `InteractiveTransport` adds a **50 ms client dispatch floor** (the W8/W10 margin).
- It also adopts the **W10 Studio's Host-confirmed stock-yield** rule, because a `0xBD` mid-send returns 409 `SESSION_CANVAS_INVALIDATED`.
- Hidden-page MCP collection (~150 ms measured) runs on a joined worker thread, so the reels don't hitch every 2 s.
- The dry-run FakeHost now enforces the floor, ACKs in 20 ms, and delivers every `0xBD` as a mid-send 409. Paced dry-run: 10 cycles, 21 sessions, 1053 frames. 43/43 successor tests. Legacy: only the 3 inherent Runtime 007 template/`frame_stream` hash errors.
- It needs `Grant OPENDITOO-INTERACTIVE-HF3-005`.

## HF3-005 — 1 cycle, then 429; HF3-006 prepared, grant-ready, UNAUTHORIZED

**HF3-005** (20:56Z) got the first real interactive evidence:
- **1 full cycle**, with each short pull stopping exactly one reel.
- **3/3 clean `0xBD` reclaims**, 2 through the Host-confirmed mid-send rule.
- **4/4 streaming first frames ACKed** on the Runtime 007 Host (5/5 including HF3-004).
- Input → first later ACK 18–243 ms.

It then failed: the reclaimed S004 got HTTP 429 at frame 11 even though the client dispatch gaps were ≥ 50 ms. The Host stamps frame start after the WSL→Windows hop, so arrival jitter beats a client-only margin. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-005-LIVE-2026-09-10.json`.

**HF3-006** (`c8057d04…` superseded; now `359b2a12…`) adds webcam policy 005's **Host-anchored gap**: wait ≥ 45 ms after the Host's own previous frame start, estimated as ACK receipt − `hostFrameElapsedMs`, which is never earlier than the true start. The FakeHost now models 12/0 ms arrival jitter. Negative controls reproduce both the HF3-004 and HF3-005 429s, and only the anchored path passes. Paced dry-run: 10 cycles / 21 sessions / 982 frames. 43/43 successor tests. It needs `Grant OPENDITOO-INTERACTIVE-HF3-006`.

## HF3-006 — 5 cycles, owner "looked great"; HF3-007 prepared, grant-ready, UNAUTHORIZED

**HF3-006** (21:01Z, 73 s):
- **5 complete cycles**; 35 inputs all applied in order.
- **15/15 device-ended reclaims** (13 `0xBD` + 2 arrow `0x09`); 16/16 first frames ACKed (21/21 on the new Host across HF3-004..006).
- Sustained sessions ran at 14–18 fps. Input → first later ACK: p50 58 ms / p95 210 ms.
- Owner: "looked great I did a bunch of loops no notable issues".

It ended when the Host watchdog caught a lever `0xBD` between frames: the next send got 409 `SESSION_NOT_ACTIVE`, which the rule didn't yet accept, even though the Host ledger recorded the known yield. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-006-LIVE-2026-09-10.json`.

**HF3-007** (`4f46ff9e…`):
- Accepts `SESSION_NOT_ACTIVE` as the known yield only on the Host's own `canvas_invalidated/stopped_yielded_to_stock` record.
- The FakeHost alternates both yield races.
- The envelope is re-sized from the observed pace (~13 s and ~2.9 sessions per cycle): 180 s / 48 sessions / 1500 frames.
- It needs `Grant OPENDITOO-INTERACTIVE-HF3-007`.

## HF3-007 — 0 presses (missed GO); HF3-008 starts on the owner's first press

HF3-007 was transport-clean (1 session, 3 frames, `lifetime_expired`), but the owner missed the GO popup, so the probe saw 0 presses. SMTC was verified healthy afterwards. This is the second id spent on start timing. **HF3-008** therefore suspends the dashboard, starts the probe, shows a 60 s topmost READY popup and waits. The owner's **first press starts the run**: the press is buffered and applied, and only then is the outer claim taken (after a second Host idle check). No press within 120 s means it exits with **no claim**: the grant stays unconsumed and the dashboard is restored. Everything else is HF3-007's code and envelope (180 s / 48 / 1500). 44/44 tests. Needs `Grant OPENDITOO-INTERACTIVE-HF3-008`.

## HF3-008 — **HF3_INTERACTIVE_LIVE=PASS**

Owner-started at 22:59:15Z. Just before it, the Ditoo's battery had died, and Runtime 007 reconnected unattended once the Ditoo was powered again.

- **11 complete Dashboard↔Slots cycles** (target 10) and 22 in-session page transitions.
- **66/66 inputs** applied exactly once and in order: 44 lever pulls gave exactly 11 × (reel 1, 2, 3, new round). Input → first later ACK p50 60 ms / p95 242 ms / max 273 ms.
- **23 sessions, 23/23 first frames ACKed** (44/44 on the new Host). 22 device-ended yields, all Host-confirmed.
- **923 frames / 139,366 B**, identical in the Host ledger. **0** `IMAGE_RX_RECV_TIMEOUT`, **0** pacing violations. Transport 12–18.7 fps per session (not panel FPS). Clean `operator_stop`; Runtime 007 restored.
- Owner visual: **"Great, no issues."**
- The genuine MCP event arrived while Slots was visible, so it was collected and its pulse **dropped, not replayed** (live evidence).
- **The lightning animation is still visually unaccepted.** It carries into HF-4 standing acceptance.

Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-008-LIVE-2026-09-10.json`.

**Accepted architecture for HF-4:**
- One `streaming_ack_clock` Host session carries all pages (`PageCarousel`), and Left/Right change pixels only.
- Low-rate pages are held to ~200 ms change-only.
- The interactive transport keeps a 50 ms client floor plus a ≥ 45 ms Host-anchored gap.
- A 409 `SESSION_CANVAS_INVALIDATED`/`SESSION_NOT_ACTIVE` counts as a stock yield only when the Host confirms it; the session is then reclaimed.
- Hidden-page MCP collection runs on a joined worker thread.
- Runtime 007's Host has first-frame 10 ms spacing.

**Next session:** HF-4, per `notes/OPENDITOO-HF4-STANDING-SUCCESSOR-PLAN-2026-09-10.md` (build side-by-side offline; Runtime 008 needs its own grant).

WSL trap: this worktree's `.git` link pointed at the WSL_MCP mount (`/run/wsl-mcp/workspace`). `git worktree repair` from the main checkout fixes it.

## HF-4 / Runtime 008 — built offline, frozen, grant-ready, UNAUTHORIZED (2026-09-10)

Pre-build state was verified live: Runtime 007 `connected` with `last_error` null, installed Host `3faf520f…`, webcam 006 `policy-check` ok, and HF3 claims 001/002/004–008 present. `main` was merged into this branch; the START_HERE/AGENTS conflicts were resolved.

- **`host/product_runtime_v3.py`** keeps the Runtime 007 supervisor semantics: fresh `OPENDITOO-PRODUCT-<nonce>-<seq>` bounded sessions, renewal on `lifetime_expired`/`budget_exhausted`, immediate reclaim of a Host-confirmed yield behind the same `ReclaimLimiter`, and `[1, 2, 5, 10, 30]` backoff that resets after a connected session.
  - Each session is `run_interactive_stream` over one `PageCarousel([dashboard + UI-1 lightning, slots])` on `streaming_ack_clock`, with the unchanged `InteractiveTransport`: 50 ms floor, 45 ms anchored gap and the Host-confirmed yield rule.
  - The carousel and driver outlive sessions, so page, game and input state survive reclaim, renewal and reconnect.
  - Hidden-page collection runs on the joined worker, and backoff collection joins it first.
  - An in-flight pulse is dropped at a genuine outage, and a hidden pulse is dropped, never replayed.
- **Telemetry (bounded):**
  - `product-runtime-state.json` adds `runtime_revision`, `session_profile`, `renewals`, `realized_fps_5s` and `last_input_to_first_ack_ms`, and is persisted at most about once a second while streaming.
  - `pagination-state.json` holds the page, the last 5 inputs with `first_ack_ms`, and the slots round/state/stopped reels.
  - It is **published at the first ACK after each input**, which fixes the Runtime 006 `first_ack_ms: null` defect.
- **Policy:** `product/OPENDITOO-PRODUCT-RUNTIME-008.json` (`runtime_revision` 4, unauthorized).
  - Pages, the full session envelope (600 s / 15 000 frames / 15 810 000 B; floors 40/50/45 ms; low-rate 200 ms; idle poll 50 ms) and 16 code hashes are pinned in code as well as in the template.
  - Target, behavior, install, broker, probe and Host must equal Runtime 007's.
  - `cli/openditoo.py` dispatches revision 4 to `product_runtime_v3`. The `spiral` page is dropped.
- **Cutover:** `scripts/cutover_runtime_008.sh` works like 007's: exact grant → template hash-valid on the branch → young-link guard → rollback saved to `.openditoo-local/rollback-runtime-007/` → service stop → Host idle → ff `main` → **in-main offline gates (both verifiers) with `offline-gate.log` kept** → local policy → `product-check` → start → `connected` → webcam 006 `policy-check`.
  - The Host and webcam are unchanged, so nothing on Windows is stopped or copied. The installed Host hash is asserted instead, so an owned-Host stop is not needed.
  - **Rollback:** the merged range contains merge commits, which `git revert A..B` refuses (verified). `--rollback` therefore restores the exact Runtime 007 tree with `git read-tree -u --reset <pre>` plus one forward commit, and proves the tree hash.
- **Offline gates (all PASS):**
  - FakeHost soak (hardened `interactive_hf3.FakeHost`: 40 ms floor, 12/0 ms jitter, 20 ms ACKs, alternating mid-send/watchdog yields) at the real 600 s envelope: 120 human-paced cycles around a 25 min idle Dashboard, 41 simulated min.
    - 247 sessions, 11 680 frames.
    - 240/240 Host-confirmed reclaims and 2 rollovers.
    - 4 injected open failures recovered, 0 pacing faults.
    - Every lever pull was applied once, in order.
  - Also tested: rollover without page reset, backoff 1/2/5/10/30/30 then reset, storm-guard cooldown after 8, one-batch inputs across a yield, first-ACK publish while running, no pulse replay after an outage, stop → one close + probe released, loader drift refusals, and CLI dispatch.
  - `verify_interactive_pages_offline.py` 56/56 (`HF4_RUNTIME_008_OFFLINE=PASS`). `verify_day1_offline.py` PASS, 326 tests: the current-template pointer moved to 008, so the 3 former 007 `frame_stream` errors are now superseded-record checks.
  - **Rehearsed on a scratch clone of main ff'd to this branch** with main's local state (no token): both gates PASS. Rehearsed `--rollback` tree restore: exact tree, and the live 007 policy `execution_ready` again.

**Next (owner):** grant `Grant OPENDITOO-PRODUCT-RUNTIME-008` → run the cutover → verify `connected` → owner-present standing acceptance: lightning visual (MCP event with the Dashboard visible), lever reclaims, power cycle on Dashboard and on Slots, webcam shortcut suspend → restore. Spotify contention and Windows-logon startup stay optional.
