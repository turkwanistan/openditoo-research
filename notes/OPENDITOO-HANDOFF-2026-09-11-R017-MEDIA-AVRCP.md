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

## Immediate next step — do this first

From **Administrator PowerShell**, media paused/off:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp\scripts\diagnose_runtime_017_raw_acl_attribution.ps1"
```

Analyze `===== RAW-ACL ATTRIBUTION RESULT =====` and any printed tshark stderr. Goal: prove low-level per-handle ACL visibility and find OpenDitoo's fixed frame preambles without relying on tshark's stale address/RFCOMM conversation state. If proven, update `OpenDitoo.RawAvrcpBroker` to dynamically bind the Ditoo handle from known OpenDitoo traffic, never a hard-coded handle. If still empty, repair the raw ACL field extraction using the diagnostic output before exploring another architecture.

## Then

Rebuild/freeze broker identities if broker source changes; keep policy hash checks exact. Re-run focused tests and the interactive successor verifier. Then rerun receive-only active-media acceptance with the ownership sink: Left 5/5, Right 5/5, Lever 20/20, total 30, Tivoo negative control excluded, media reaction NO, helper orphans 0. Only after that should production elevation plumbing and the exact grant/cutover be considered.

## Guardrails

- Preserve Runtime 016 as exact rollback baseline and preserve main's unrelated untracked research note.
- Raw HCI captures/temp logs remain private; do not commit addresses or private capture payloads.
- No hard-coded current HCI handle or CID.
- No new transmit semantics are needed for this work; keep the raw input side receive-only.
- Do not silently weaken hash pins, grant gates, rollback checks, Host/session behavior, Dashboard/Slots/Moss behavior, or existing reconnect/reclaim semantics.
- A local Claude session may edit/test/commit freely on `feat/media-avrcp-input`; user interaction should be limited to truly necessary elevated Windows/device tests.
