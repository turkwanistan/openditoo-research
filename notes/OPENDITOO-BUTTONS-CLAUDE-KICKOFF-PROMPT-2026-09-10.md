Implement the current OpenDitoo physical-button navigation objective in `/home/wan/Projects/openditoo-research`. This is an execution/orchestration session, not another planning exercise. The live repository and its steering/state files outrank this prompt and prior chat history.

At handoff preparation the tree was clean at `5198f32` (`Promote AVRCP button route and implementation handoff`), on top of `24d0b70` (the separately prepared Host-headless task fix). Re-check Git state before doing anything and preserve any newer/concurrent work.

Hydrate progressively in this order:

1. `START_HERE.md`
2. `notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md`
3. `AGENTS.md`
4. `notes/OPENDITOO-BUTTON-AVRCP-RESEARCH-2026-09-10.md`
5. `notes/OPENDITOO-BUTTON-AVRCP-PAGINATION-PLAN-2026-09-10.md`
6. the W10 handoff and deeper M7/Host/session evidence only as the active milestone requires

Run the repository preflight expected by those files, including `python3 scripts/verify_day1_offline.py`, and independently check your local WSL/Windows capabilities (`powershell.exe`, OpenDitoo Host status, activity probe). Do not inherit WSL_MCP's environment limitations. The prior WSL_MCP verifier reached all 296 tests and had only two `PIL`-missing W9B optical errors after the steering changes were reconciled; establish the truth in your own environment.

## Mission

Execute the shortest evidence-driven chain to genuine physical pagination:

**BTN-0 -> BTN-1 -> BTN-2 ->, if BTN-2 passes, BTN-3/4/5.**

The target result is:

**live MCP dashboard -> physical Right -> looping animation -> physical Left -> live MCP dashboard**, with one event per press, no second RFCOMM controller, no firmware modification, and no accidental stock takeover from the arrows.

### BTN-0 — reproduce the AVRCP evidence offline

Make the preserved M7 HCI result executable with repository code. Extend the existing btsnoop/L2CAP parsing narrowly enough to recover the AVCTP/AVRCP PSM `0x0017` pass-through events while preserving existing RFCOMM behavior. Prefer a small `host/avctp.py`-style decoder rather than broad protocol machinery.

Repository code must independently reproduce the controlled exact-unit sequence:

- Left -> AVRCP `0x4C` press + `0xCC` release (Previous/Backward)
- Right -> `0x4B` + `0xCB` (Next/Forward)
- Left again -> `0x4C` again
- Lever -> `0x44` + `0xC4` (Play in the captured state), temporally correlated with proprietary RFCOMM `0xBD`

Add focused tests for press/release pairing, fragmentation/truncation, unrelated AVCTP traffic, and preservation of the current RFCOMM M7 results. Produce a **new derived** AVRCP evidence artifact; do not rewrite the historical M7 capture JSON. Update durable state when this closes. Suggested gate: `BTN0_AVRCP_REPRODUCTION=PASS`.

### BTN-1 — build the receive-only Windows ButtonProbe

Create a side-by-side `.NET 8` Windows diagnostic, expected path `runtime/windows/OpenDitoo.ButtonProbe/`. Use a process-owned hidden top-level HWND and SMTC (`ISystemMediaTransportControlsInterop::GetForWindow`) as the primary receive seam. Enable Previous, Next, Play and Pause. Log raw events as NDJSON with epoch, monotonic/UTC time, sequence, source, raw button and candidate normalization.

Candidate mapping, only after raw events are preserved:

- Previous -> `nav_left`
- Next -> `nav_right`
- Play or Pause -> `lever_candidate`

`WM_APPCOMMAND` may be logged as a separate diagnostic path, but do not merge/de-duplicate it with SMTC before exact measurement establishes what fires.

The probe must contain no Ditoo RFCOMM socket, Host token/API call, target override/address, image/session route, raw AVRCP send, firmware/update path or other device-write capability. Build/stage candidates without perturbing hash-bound live Host or webcam Studio outputs; honor the W10 build-output traps.

### BTN-2 — prove the physical controls on Windows

Once BTN-0 and BTN-1 are clean, use the local interactive Windows environment for the receive proof while the accepted Runtime 005 dashboard remains the normal display baseline.

Prepare everything first, then tell the owner exactly when to press:

`Left -> Right -> Left -> Lever`

with clear spacing, and repeat the sequence once after a quiet baseline.

Record what actually arrives rather than assuming the expected result. Correlate ButtonProbe output with Host/product telemetry so the test also establishes whether arrow presses leave the custom canvas/session alone and what the lever's simultaneous RFCOMM `0xBD` does.

Expected app-level sequence is `Previous -> Next -> Previous -> Play/Pause`, twice. If SMTC/WM_APPCOMMAND does not receive it, use the existing plan's Windows BTVS/HCI decision tree before changing architecture: distinguish "AVRCP reached Windows but media routing failed" from "Windows did not establish/retain the AVRCP profile". Neither branch justifies firmware/MassBoot work for these controls.

### If BTN-2 passes — continue to pagination

Do not stop merely because the probe works. Continue through the current plan unless an explicit authority/user-action gate requires the owner.

- **BTN-3:** harden the receiver into a typed ButtonBroker with process epoch, monotonically increasing sequence, gap/restart semantics, and a narrow local consumption surface.
- **BTN-4:** implement a side-by-side successor page router offline. Page 0 is the existing live MCP dashboard renderer. Page 1 is one frozen looping GIF-derived/animation frame set using the existing deterministic 16x16 RGB888 frame-stream primitive. Do not build a general menu framework.
- First semantics: Dashboard+Right -> animation; Animation+Left -> dashboard; Left on dashboard and Right on animation are no-ops. Log/ignore lever for pagination until its `0xBD` interaction is physically characterized.
- **BTN-5:** prepare and execute the smallest authorized physical pagination acceptance: Dashboard visible -> Right -> animation visibly running -> Left -> live dashboard restored -> one genuine MCP activity pulse still renders correctly. Measure event multiplicity, transition latency and session identity.

A new live pagination/display behavior is a successor product authority shape. Do not infer permission from Runtime 005 or webcam-product-004. Prepare the reviewed manifest/policy and frozen evidence first; when an explicit named owner grant is required, stop at that exact boundary and give the owner the precise grant/action needed. Never replay a consumed identity or retry an ambiguous live operation.

## Boundaries to preserve

- Do not modify the accepted Runtime 005 Host merely to receive standard AVRCP during BTN-0/1/2.
- Do not open a second Ditoo RFCOMM controller.
- Do not weaken the current non-ACK `canvas_invalidated` fence.
- Do not special-case lever `0xBD` as benign without exact physical evidence.
- Do not drift the granted webcam Studio files while button work is in progress.
- Do not re-open W9B, >18.46 fps work, firmware flashing, MassBoot/test mode, USB vendor commands or teardown for this objective.
- Preserve exact-target binding, OpenTivoo isolation, current rollback paths and the separately prepared Host-headless fix from `24d0b70`.
- That headless task change requires elevated PowerShell and is not assumed applied; until its current state is verified, do not close the visible terminal hosting `OpenDitoo.Day1.Host.exe`.

Keep durable findings, failures, evidence and next actions in the repository. Commit coherent milestone checkpoints without absorbing unrelated concurrent work. After two materially identical failures, reassess the hypothesis instead of repeating the same attempt. If context becomes large at a natural milestone, leave a current handoff before rotating.

Success for this session is BTN-2 physically proven and, if authority/operator interaction permits, BTN-5 physically accepted. If you must stop at a user action or grant boundary, leave the repository fully prepared and tell the owner exactly what to do next.
