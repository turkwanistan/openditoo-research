# OpenDitoo media-contention / raw-AVRCP input route — 2026-09-11

Status: **root cause proven; raw input route proven; Runtime 017 successor implemented offline and unauthorized; live Runtime 016 source unchanged and currently stopped after diagnostics. Dynamic exact-Ditoo attribution is the remaining technical gate.**

## Problem

When Windows media is actively playing through a separate Bluetooth speaker, the Ditoo enters its stock now-playing/media-control behavior. OpenDitoo's existing SMTC ButtonProbe then loses reliable control ownership: Ditoo Left/Right become Previous/Next for the active Windows media session and the lever becomes Play/Pause. When media pauses, OpenDitoo input returns immediately. The OpenDitoo RFCOMM/frame session itself remains connected; this is input/media-session arbitration, not a data-link disconnect.

## Exact-unit evidence from 2026-09-11

1. Existing Runtime 016 / `--status mirror` is media-contention-sensitive. With YouTube playing through the separate Bluetooth speaker, Ditoo Left/Right/lever control the Windows media session instead of OpenDitoo.
2. Standalone ButtonProbe with `--status playing` retains Windows media-key ownership:
   - Left/Right reach OpenDitoo while YouTube remains unchanged.
   - An isolated lever pull can reach OpenDitoo without pausing YouTube.
3. Fixed-Playing SMTC is **not a reliable lever event source**. Repeated lever pulls are dropped at the SMTC callback boundary.
4. Raw HCI evidence localizes that loss above Bluetooth:
   - five physical lever pulls produced five complete AVRCP Pause press/release transactions and Windows ACCEPTED all five;
   - the fixed-Playing SMTC callback surfaced only a subset.
5. A temporary SMTC `Playing -> Paused -> Playing` re-arm experiment did not solve it (3/5 in a clean repeat, and media eventually reacted). Reject this route.
6. Proprietary RFCOMM state reports are not a complete lever source under contention. Five isolated pulls yielded: `0x09`, `0xBD`, none, `0x09`, `0xBD` — 4/5 any report, only 2/5 `0xBD`.
7. Raw AVRCP is complete. In a clean saved HCI capture of **10 physical lever pulls**, press commands were exactly:
   - five `0x46` Pause
   - five `0x44` Play
   - alternating, total **10/10**.
   The earlier apparent 5/10 was a diagnostic filter that matched `0x46` only and therefore discarded the Play half.
8. The raw pass-through mapping remains:
   - `0x4C` = Left / Previous -> `nav_left`
   - `0x4B` = Right / Next -> `nav_right`
   - `0x44` = Play -> `lever_candidate`
   - `0x46` = Pause -> `lever_candidate`
   Releases have bit 7 set and are not separate input events.

Raw HCI captures remain private. Do not commit them. Derived findings only are recorded here.

## Root cause

The Ditoo hardware and Windows Bluetooth/AVRCP stack are not dropping lever input. The lossy boundary is Windows **SMTC callback delivery when OpenDitoo advertises a fixed Playing state**. Fixed Playing is nevertheless useful as a media-ownership sink because it prevents the active browser/media session from receiving Ditoo controls.

## Selected route

Use two receive-only seams with separate responsibilities:

1. **SMTC ownership sink** — existing OpenDitoo.ButtonProbe in `--status playing`; its callbacks are not authoritative input.
2. **Raw AVRCP input broker** — BTVS live HCI -> tshark, filtered to the exact Ditoo ACL source and AVRCP panel PASS THROUGH press commands. Normalize raw `0x4C/0x4B/0x44/0x46` into the existing left/right/lever event vocabulary.

Do not hard-code today's ACL handle or L2CAP CID. Wireshark exposes ACL source/destination Bluetooth identity from the HCI connection state; the broker must filter to the exact hash-bound Ditoo target so Tivoo/EDIFIER AVRCP traffic cannot become OpenDitoo input.

Use a dedicated BTVS TCP port so an operator's normal/default Wireshark/BTVS session cannot collide with the product input broker.

## Offline implementation checkpoint

Worktree/branch: `feat/media-avrcp-input` under `.openditoo-local/worktrees/media-avrcp`.

Added, not yet committed:

- `runtime/windows/OpenDitoo.RawAvrcpBroker/`
  - receive-only Windows sidecar;
  - owns ButtonProbe Playing sink + BTVS + tshark children;
  - exact-peer ACL attribution;
  - accepts only AVRCP single-packet CONTROL panel PASS THROUGH presses;
  - maps both Play and Pause to the same lever candidate;
  - Windows Job Object is intended to kill its helper tree when the broker exits;
  - `--selftest` covers Left/Right/Play/Pause and rejects releases/responses/foreign profile/malformed input.
- `host/raw_avrcp_input.py`
  - rate-limited sidecar supervisor;
  - private bounded event/sink logs;
  - `RawAvrcpEvents` at-most-once NDJSON cursor accepting only `source=avrcp_raw`.
- `tests/test_raw_avrcp_input.py`
  - 4/4 Python tests PASS under WSL_MCP.

Local Windows checkpoint PASS: `dotnet build -c Release` completed with 0 warnings / 0 errors and `OpenDitoo.RawAvrcpBroker.exe --selftest` printed `RAW_AVRCP_BROKER_SELFTEST=PASS`. After that checkpoint the sidecar health loop was tightened so it checks sink/BTVS/tshark health every <=250 ms even when no button input is present; rebuild/selftest is required before live acceptance.

Runtime 017 is now authored side-by-side (`host/product_runtime_v11.py`, revision 12; `product/OPENDITOO-PRODUCT-RUNTIME-017.json`) and deliberately unauthorized. It preserves Runtime 016 target/session/behavior/install/pages/Host/ButtonProbe bytes and changes only the input broker. The committed policy currently contains explicit pending BTVS/tshark/broker-binary identity placeholders and therefore is **not grant-ready** until the exact locally-proven paths + SHA-256 values are frozen.

Offline results after successor wiring: dedicated raw-input/runtime tests 10/10 PASS; interactive product verifier 136/136 PASS. The broad Day-1 verifier cannot be interpreted directly from the linked worktree because git-ignored claims/Host build outputs/PIL are absent there; by design the cutover gate runs the full verifier again from main after fast-forward, as prior successor scripts do.

## Acceptance gates before product cutover

1. Windows build + broker `--selftest` **PASS**.
2. Receive-only live broker test under active Bluetooth media:
   - exact Ditoo attribution;
   - Left 5/5, Right 5/5, lever >=20/20;
   - no duplicate press/release counting;
   - browser/media playback receives 0 controls;
   - Tivoo controls and EDIFIER controls do not appear in OpenDitoo event log.
3. Stop broker and prove its BTVS/tshark/SMTC sink process tree is gone; media controls return to normal.
4. Freeze the exact broker/BTVS/tshark paths + SHA-256 identities into the committed Runtime 017 policy and add the exact-grant cutover/rollback script.
5. Run one receive-only live sidecar acceptance before product cutover: Left 5/5, Right 5/5, lever >=20/20; no media reaction; unrelated Tivoo/EDIFIER controls produce zero OpenDitoo events; broker stop kills its helper tree.
6. Runtime 017 requires a fresh exact owner grant. Runtime 016 authority does not widen to raw-HCI input observation.

## Offline successor gate status

- `tests.test_raw_avrcp_input` + `tests.test_runtime017_raw_avrcp`: **10/10 PASS**.
- `scripts/verify_interactive_pages_offline.py`: **136/136 PASS**, preserving all existing Dashboard / Slots / Moss gates.
- Runtime 017 committed template remains unauthorized and reports the expected authority blockers until an explicit `Grant OPENDITOO-PRODUCT-RUNTIME-017`.
- Runtime 016 source/policy remains the exact rollback baseline; no cutover has occurred.
## Live attribution diagnostic — 2026-09-11

A receive-only elevated BTVS/tshark diagnostic intentionally omitted the SMTC Playing ownership sink and captured seven AVRCP press commands:

- Ditoo Left, Right and four lever pulls all arrived on HCI handle `0x0100`.
- Tivoo volume-knob short press arrived on HCI handle `0x0200`.
- `bthci_acl.src.bd_addr` and `bthci_acl.dst.bd_addr` were `00:00:00:00:00:00` for every captured row because the live capture started after the ACL links already existed.
- Browser/media did react during this diagnostic (song changed / appeared to pause), as expected because this diagnostic did **not** run the fixed-Playing SMTC ownership sink. This does not contradict the prior sink-isolation result.

This proves current-handle separation is clean but exact-address attribution is unavailable when BTVS attaches mid-connection. Do **not** hard-code `0x0100`; reconnects can reassign handles. Runtime 017 must learn the Ditoo handle dynamically.

Selected next route: identify the Ditoo ACL handle from OpenDitoo's own validated RFCOMM traffic on that same ACL link, then accept AVRCP only on that learned handle. The existing product's RFCOMM traffic is uniquely attributable because OpenDitoo owns the typed Ditoo session and sends framed candidate packets/ACKs. This avoids dependence on historical HCI connection-complete events.

## Current handoff checkpoint — 2026-09-11 16:36 EDT

This section supersedes stale implementation-status wording above; keep earlier material as experiment history.

### What is now proven

- Runtime 017 is fully authored side-by-side as runtime revision 12 and remains deliberately unauthorized. Exact required grant remains `Grant OPENDITOO-PRODUCT-RUNTIME-017`; **do not grant/cut over yet**.
- Broker/BTVS/tshark binary identities are frozen in the Runtime 017 policy; there are no remaining pending hash placeholders.
- Focused successor tests are **17/17 PASS** after the latest diagnostic fixes; the previously-run interactive product verifier is **136/136 PASS**.
- Fixed-Playing ButtonProbe works as the ownership sink: in the earlier active-media acceptance attempt the operator reported **NO browser/media reaction** and helper cleanup was clean. That run produced 0 raw input events only because the exact-address tshark filter could not attribute an already-established ACL link.
- A receive-only attribution diagnostic without the ownership sink captured exactly the expected actions: Ditoo Left, Right and four lever pulls all used one HCI ACL handle; the Tivoo negative control used a different handle. Source/destination address fields were all zero because BTVS attached after the links already existed. The media changed/paused during that diagnostic because the ownership sink was intentionally absent.
- Therefore handle separation is real, but **never hard-code the observed handle**; reconnects may reassign it.
- BTVS itself requires an elevated Windows token on this host. Elevated acceptance is valid for research, but production Runtime 017 must use a narrowly-scoped elevated capture mechanism/task or another design that does not elevate the whole OpenDitoo runtime.

### What the empty handle/frame diagnostics mean

Two follow-up diagnostics printed empty result sets. Do not treat those as evidence against raw-handle learning. Runtime 016 telemetry proves a frame was sent and ACKed inside the frame-attribution capture window. The newer diagnostics also contained a concrete tshark output bug: they passed `separator=\\t` instead of the working `separator=\t`. Commit `c11ca8d` fixes the affected diagnostics, adds guards, and leaves the focused suite 17/17 PASS.

### Immediate next action

From **Administrator PowerShell**, with media paused/off, rerun only the corrected low-level ACL diagnostic:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\.openditoo-local\worktrees\media-avrcp\scripts\diagnose_runtime_017_raw_acl_attribution.ps1"
```

Expected output begins under `===== RAW-ACL ATTRIBUTION RESULT =====`. If it shows OpenDitoo's fixed frame preambles on the same handle that carries Ditoo AVRCP, implement dynamic handle binding below tshark's stale higher-level conversation state: broker starts unbound, observes known OpenDitoo traffic, binds the current Ditoo ACL handle, and only then emits `0x4C/0x4B/0x44/0x46` events from that handle. If it still emits no rows, use the now-visible tshark stderr/raw rows to repair the low-level field extraction before changing architecture again.

After dynamic attribution is implemented, repeat active-media acceptance with the fixed-Playing ownership sink: Left 5/5, Right 5/5, lever 20/20, total 30, Tivoo negative control excluded, zero media reaction, zero helper orphans. Only then revisit production elevation plumbing and the exact Runtime 017 grant/cutover.
