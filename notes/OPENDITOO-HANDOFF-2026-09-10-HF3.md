# OpenDitoo handoff — HF-3 interactive acceptance — 2026-09-10


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

WSL trap: this worktree's `.git` link pointed at the WSL_MCP mount (`/run/wsl-mcp/workspace`). `git worktree repair` from the main checkout fixes it.
