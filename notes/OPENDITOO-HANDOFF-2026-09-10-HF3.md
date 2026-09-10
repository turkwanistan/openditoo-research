# OpenDitoo handoff — HF-3 interactive acceptance — 2026-09-10


Feature worktree: `feat/high-fps-interactive-pages`. Runtime 006 on `main` remains the live rollback baseline.

## HF3-001 — consumed, transport clean, acceptance NOT MET

Run from normal local WSL (with `/mnt/c` and `powershell.exe`). All pre-grant invariants were verified independently: manifest `7ad8ef4d…`, no claim, installed ButtonProbe `79521fba…`/`d85c1298…`, Host `f7bd60d4…` bound to `11:75:58:CE:DE:C7`, raw-send off, Runtime 006 `connected`, no second controller. The already-given grant was materialized at 19:33Z and the run went 19:34:09–19:35:39Z.

Result: `lifetime_expired` / `stopped_clean`, 90.0 s. Two activity children, 13 frames / 39 packets / 2,534 B, and the Host ledger agrees exactly. No retry, reconnect, reclaim or `IMAGE_RX_RECV_TIMEOUT`. **0 of 10 cycles, 0 SMTC events**: the owner did not press in time, because nothing marks when the window opens (the Dashboard looks the same before and after suspension). The only raw input was keyboard Volume-Down, correctly ignored. Runtime 006 was restored and independently verified `connected`. Afterwards Right switched pages under Runtime 006, so the SMTC path is healthy. Visual: not observed. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-001-LIVE-2026-09-10.json`. **Replay forbidden.**

Design finding: the 001 envelope could not have met 10 cycles at human pace anyway. 500 frames at about 18 fps of spinning is roughly 28 s of Slots. With BTN-7's every-other-pull `0xBD` reclaim, a cycle costs about 4 child attempts, so 28 attempts is about 6 cycles. The dry-run FakeHost modeled neither. A new negative-control test pins this.

## HF3-002 — consumed/unknown: IMAGE_RX_RECV_TIMEOUT on the first profile switch

The owner granted `Grant OPENDITOO-INTERACTIVE-HF3-002`. The GO popup worked. At the owner's first Right (19:47:39.193Z), S001 (activity, 4.3 s old, 1 frame) closed cleanly and S002 (`streaming_ack_clock`) opened **29 ms later**. S002's first frame got `IMAGE_RX_RECV_TIMEOUT; NO_RETRY` (0 frames, `unknown_nothing_sent`). The run failed closed as `transport_fault`/`unknown` with no retry. Runtime 006 was restored and independently verified `connected` (nonce `7ef5a100`). Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-002-LIVE-2026-09-10.json`. **Replay forbidden.**

Diagnosis from exact-unit ledgers: a **Host-initiated close followed by a reopen**, most often of a seconds-old link, leaves the Ditoo silent. This is 4 cases: W9B-006, the W10 15:04 launch (after an 8 s settle), webcam-product-001 #4, and HF3-002. Device-ended `0xBD` sessions of the same age reopen cleanly in 46–69 ms (BTN-7), as do aged Host rollovers (HF3-001, Runtime 006). A longer settle is not the cure. The Host already encodes this lesson (W10C, "one connection"). HF-2's close-and-reopen-per-profile paging is therefore structurally unsafe. Do not retry that shape.

## HF3-003 — prepared, grant-ready, UNAUTHORIZED

`OPENDITOO-INTERACTIVE-HF3-003`, manifest `experiments/DAY1-INTERACTIVE-HF3-003.json` (`ab9cecdc…`).

- **`PageCarousel`** (`host/interactive_pages.py`) runs Dashboard and Slots inside **one** `streaming_ack_clock` session. Left/Right change pixels only.
- The Dashboard keeps its ~200 ms change-only cadence by repeating its last ACKed frame, which the scheduler holds.
- Child lifetime and frames equal the outer envelope, so no rollovers are planned. The only session boundaries left are device-ended canvas yields.
- Allowed profiles are narrowed to `streaming_ack_clock`. Envelope: 150 s, 32 child attempts, 1500 frames.
- Paced dry-run: 10 cycles, 21 sessions (1 + 20 `0xBD` reclaims), 951 frames, 60/60 inputs correlated.
- Fast dry-run: 20 page transitions in 1 session. 40/40 PASS.

It requires the exact grant `Grant OPENDITOO-INTERACTIVE-HF3-003`. The GO/FINAL operator-assist is unchanged.

Run: start `python3 scripts/hf3_operator_assist.py` in the background, then `bash scripts/run_interactive_hf3.sh`, after `python3 scripts/interactive_hf3.py grant 'Grant OPENDITOO-INTERACTIVE-HF3-003'` and `check`. Never use `--sandbox-skip-probe`.

**HF-4 implication:** the standing successor must page in-session the same way, and must never Host-close a young link to change pages.

WSL trap: this worktree's `.git` link pointed at the WSL_MCP mount (`/run/wsl-mcp/workspace`). `git worktree repair` from the main checkout fixes it.
