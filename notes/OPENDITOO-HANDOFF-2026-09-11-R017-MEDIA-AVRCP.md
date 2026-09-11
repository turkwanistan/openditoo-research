# OpenDitoo Runtime 017 media-resilient raw AVRCP handoff — 2026-09-11

## State

Work only in `.openditoo-local/worktrees/media-avrcp` on branch `feat/media-avrcp-input`. Main remains the accepted Runtime 016 baseline; preserve its unrelated untracked `notes/OPENDITOO-FULL-INPUT-TAKEOVER-RESEARCH-2026-09-11.md`. Runtime 016 service is currently stopped after diagnostics. Runtime 017 (revision 12) is **not live and not authorized**. Do not cut over or request/consume the exact grant until live input acceptance passes.

Current feature checkpoint before this handoff: `c11ca8d` (`Fix Runtime 017 tshark field separators`). The successor broker, host integration, policy, stage/cutover scripts, acceptance harness and diagnostics are already committed. Broker/BTVS/tshark identities are frozen in policy. Focused tests are 17/17 PASS; existing interactive product verifier was 136/136 PASS.

## Root cause / selected architecture

Active Windows media can steal Ditoo AVRCP controls. Raw Bluetooth does not lose the lever: a saved 10-pull capture showed exactly 10 press transactions, alternating AVRCP Play `0x44` and Pause `0x46`. Fixed-Playing SMTC prevents the browser/media session from receiving Ditoo controls but its callbacks drop repeated lever presses. Therefore:

1. existing ButtonProbe `--status playing` = **ownership sink only**;
2. raw BTVS/tshark AVRCP = **authoritative input**;
3. normalize press-only `0x4C -> nav_left`, `0x4B -> nav_right`, `0x44|0x46 -> lever_candidate`; ignore releases.

Do not use proprietary RFCOMM reports as authoritative input; they were incomplete. Do not use the temporary SMTC re-arm experiment; it failed.

## Latest live evidence

- Initial Runtime 017 active-media acceptance: ownership worked (`MEDIA_REACTION=NO`) and helper cleanup was clean, but raw counts were 0 because the broker filtered on exact Bluetooth address and a mid-connection BTVS capture had no usable address mapping.
- Receive-only attribution diagnostic: all six Ditoo actions (Left, Right, four lever pulls) were on one ACL handle; Tivoo volume-knob negative control was on a different handle. Both address columns were zeroed. The observed numeric handles are diagnostic-only and must not be persisted/hard-coded.
- Media changed/paused during that attribution diagnostic because it intentionally omitted the Playing ownership sink; expected behavior.
- BTVS requires Administrator elevation on this Windows host. Do not solve that by elevating the whole OpenDitoo product; final production plumbing needs a narrow elevated helper/task or equivalent.
- Attempts to learn the handle from fresh L2CAP/RFCOMM open and known frame preambles initially printed no rows. Runtime telemetry proved a frame was sent+ACKed during the latter window, and review found the newer diagnostics were passing an invalid tshark field separator (`separator=\\t`). Commit `c11ca8d` corrected it and added better failure visibility.

## Update — dynamic attribution and receive-only acceptance PASS (2026-09-11 21:17Z)

The raw-ACL gate is closed. The pre-fix 20:34Z capture already held 410 rows (tshark printed a literal `\` separator; its tab escape is `/t`, so `c11ca8d` was still wrong). Those rows show OpenDitoo's outbound Pixel Coloring preambles A→B (`pb_flag 0`, RFCOMM UIH) only on the Ditoo's ACL handle, the same handle that carries its AVRCP. The Tivoo handle never carries them.

Broker now (`02a7055`, `b4d536e`, `14ff03f`):
- tshark runs with `--disable-protocol btrfcomm --disable-protocol btavctp`, so every channel stays raw `btl2cap.payload`. Without that, a freshly connected link (any reconnect) is dissected and the payload field vanishes (proven on a synthetic HCI pcap).
- `HandleBinder`: starts unbound, binds on an outbound A-then-B pair on one handle, unbinds on HCI Disconnection Complete for that handle, and accepts only inbound (`pb_flag 2`) presses on the bound handle. Any pass-through on another handle is logged `ignored_foreign_handle`. No handle or CID is persisted.
- Rows captured before broker start are dropped. `BTETWRTSession` keeps buffering while no consumer is attached and replayed 20-minute-old presses on connect.
- A flush-only `ControlTrace(FLUSH)` on `BTETWRTSession` runs every 50 ms. Without it, ETW real-time buffering added 1.1–2.1 s of input lag.
- The Playing ownership sink starts on the first bind.

Acceptance (`captures/OPENDITOO-R017-RAW-AVRCP-ACCEPTANCE-2026-09-11.json`):
- **21:01Z FAIL** — raw counts 5/5, 5/5, 20/20 = 30 but stale backlog, 1.77 s lag and media reaction YES. The Runtime 016 binding blip's mirror SMTC session competed with the sink.
- **21:16Z PASS** — reduced by owner request to 3/3, 3/3, 8/8 = 14. Tivoo excluded (2 rows), 0 unbinds, ETW flush OK, latency p50 104 / max 142 ms, 0 orphans, media reaction NO.
- Focused tests 16/16, broker selftest PASS, interactive verifier 136/136. Broker DLL + program hash refrozen in the Runtime 017 policy.

## Immediate next step — production elevation plumbing (blocks the grant)

Runtime 017 is **not grant-ready**. `product_runtime_v11` launches the broker from WSL with a normal token, and `btvs.exe` refuses without elevation (Win32 740). A cut-over 017 would therefore get zero input, and the broker would restart every 5 s. Needed:

1. A narrowly elevated launch for **only** `OpenDitoo.RawAvrcpBroker.exe`. Candidate: a scheduled task registered once from Administrator PowerShell with *Run with highest privileges*, hash-pinned exe/args, on-demand only. The WSL supervisor starts and stops it (`schtasks /run` / `/end`) and keeps reading the same NDJSON.
2. Liveness/stop semantics equivalent to today's child-process supervision, plus the Job Object helper cleanup.
3. Tests and policy/cutover updates for the task identity, then a short product-supervised live check: bind from the product's own frames, a few presses under media, a Ditoo power-cycle rebind.

Only then request `Grant OPENDITOO-PRODUCT-RUNTIME-017`.

Open follow-ups: `BTETWRTSession` outlives a killed BTVS and keeps buffering HCI (privacy/perf; consider stopping it on broker exit). The stale-drop path saw 0 rows in the PASS run.

## Guardrails

- Preserve Runtime 016 as exact rollback baseline and preserve main's unrelated untracked research note.
- Raw HCI captures/temp logs remain private; do not commit addresses or private capture payloads.
- No hard-coded current HCI handle or CID.
- No new transmit semantics are needed for this work; keep the raw input side receive-only.
- Do not silently weaken hash pins, grant gates, rollback checks, Host/session behavior, Dashboard/Slots/Moss behavior, or existing reconnect/reclaim semantics.
- A local Claude session may edit/test/commit freely on `feat/media-avrcp-input`; user interaction should be limited to truly necessary elevated Windows/device tests.
