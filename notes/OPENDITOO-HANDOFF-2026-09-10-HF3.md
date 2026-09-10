# OpenDitoo handoff — HF-3 interactive acceptance — 2026-09-10


Feature worktree: `feat/high-fps-interactive-pages`. Runtime 006 on `main` remains the live rollback baseline.

## HF3-001 — consumed, transport clean, acceptance NOT MET

Run from normal local WSL (with `/mnt/c` and `powershell.exe`). All pre-grant invariants were verified independently: manifest `7ad8ef4d…`, no claim, installed ButtonProbe `79521fba…`/`d85c1298…`, Host `f7bd60d4…` bound to `11:75:58:CE:DE:C7`, raw-send off, Runtime 006 `connected`, no second controller. The already-given grant was materialized at 19:33Z and the run went 19:34:09–19:35:39Z.

Result: `lifetime_expired` / `stopped_clean`, 90.0 s. Two activity children, 13 frames / 39 packets / 2,534 B, and the Host ledger agrees exactly. No retry, reconnect, reclaim or `IMAGE_RX_RECV_TIMEOUT`. **0 of 10 cycles, 0 SMTC events**: the owner did not press in time, because nothing marks when the window opens (the Dashboard looks the same before and after suspension). The only raw input was keyboard Volume-Down, correctly ignored. Runtime 006 was restored and independently verified `connected`. Afterwards Right switched pages under Runtime 006, so the SMTC path is healthy. Visual: not observed. Evidence: `captures/OPENDITOO-INTERACTIVE-HF3-001-LIVE-2026-09-10.json`. **Replay forbidden.**

Design finding: the 001 envelope could not have met 10 cycles at human pace anyway. 500 frames at about 18 fps of spinning is roughly 28 s of Slots. With BTN-7's every-other-pull `0xBD` reclaim, a cycle costs about 4 child attempts, so 28 attempts is about 6 cycles. The dry-run FakeHost modeled neither. A new negative-control test pins this.

## HF3-002 — prepared, grant-ready, UNAUTHORIZED

`OPENDITOO-INTERACTIVE-HF3-002`, manifest `experiments/DAY1-INTERACTIVE-HF3-002.json`. Same pages, profiles, target, Host and probe bytes. Changes:

- Envelope: 150 s, 48 child attempts, 1500 ACKed frames, 400 frames per streaming child, byte ceiling derived.
- `dry-run --paced` models human pace (~1.2 s between pulls) plus a `0xBD` reclaim on each Play pull. Result: 10 cycles, 41 attempts, 951 frames, 93 s simulated, 20 reclaims, 60/60 inputs correlated to a later ACK.
- `scripts/hf3_operator_assist.py` does no device or Host I/O. It shows a topmost **GO** popup when the first child opens and a **FINAL** popup on the last Dashboard. It then makes one genuine read-only WSL_MCP call so the lightning fires, and SIGINTs the runner. Popups are used instead of sounds because the Ditoo is itself a Windows audio endpoint.

Verifier: 39/39 PASS. Requires the new exact grant `Grant OPENDITOO-INTERACTIVE-HF3-002`; the 001 grant does not transfer.

Run: start `python3 scripts/hf3_operator_assist.py` in the background, then `bash scripts/run_interactive_hf3.sh`, after `python3 scripts/interactive_hf3.py grant 'Grant OPENDITOO-INTERACTIVE-HF3-002'` and `check`. Never use `--sandbox-skip-probe`.

WSL trap: this worktree's `.git` link pointed at the WSL_MCP mount (`/run/wsl-mcp/workspace`). `git worktree repair` from the main checkout fixes it.
