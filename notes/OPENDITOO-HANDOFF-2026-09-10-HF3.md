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

**Next (owner decision):**
1. Approve a reviewed Host re-bind revision that installs the first-frame-spacing Host, with Runtime 006 → re-bound runtime and webcam 005 → re-bound policy, preserving rollback to the `f7bd60d4` Host.
2. Then run a fresh HF-3 (`…-HF3-004`) on the `PageCarousel` design.

The webcam shortcut is also affected (5/19 is mostly webcam launches), so this fix benefits the webcam product too.

WSL trap: this worktree's `.git` link pointed at the WSL_MCP mount (`/run/wsl-mcp/workspace`). `git worktree repair` from the main checkout fixes it.
