# OpenDitoo handoff — AVRCP physical controls + pagination — 2026-09-10

**Read this first for the next implementation session. Repository state outranks this note.**

The owner has selected physical button navigation as the next objective. W10 webcam productization is closed; Runtime 005 and webcam-product-004 are the accepted baseline. The goal now is to prove the exact Ditoo Plus left/right/lever controls can be captured by the local Windows environment over Bluetooth, then use left/right for the smallest physical pagination proof: **live MCP dashboard -> looping animation -> live MCP dashboard**.

For a fresh local Claude Code session, the prepared kickoff prompt is `notes/OPENDITOO-BUTTONS-CLAUDE-KICKOFF-PROMPT-2026-09-10.md`. It is a convenience entry point; this handoff and the live repository remain authoritative.

## Progress log (newest last; repository state outranks it)

- **BTN-0 PASS (2026-09-10).** `python3 cli/openditoo.py capture-avrcp-parse --capture bugreport-husky-CP1A.260505.005-2026-09-09-00-59-46.zip` reproduces Left `0x4C`/`0xCC`, Right `0x4B`/`0xCB`, Left `0x4C`/`0xCC`, Lever `0x44`/`0xC4` from the raw M7 bytes (Ditoo-initiated AVCTP, CIDs rx `0x0045` / tx `0x0043`; every press and release ACCEPTED by the phone). Lever `0x44` follows RFCOMM `0xBD` by 1.698 ms. Derived artifact `captures/OPENDITOO-M7-AVRCP-KEY-SWEEP-2026-09-09.json`; historical M7 JSON untouched and hash-pinned. Two things the research note did not have: (1) the historical "unresolved" 0x09 report at 04:58:11.706 precedes the **first Left** press by 2.7 ms (repeat Left and Right had none) — so BTN-2 must check session identity across every arrow press; (2) an unattributed burst of 8 alternating Play/Pause pairs at 04:57:03–05, i.e. the lever's AVRCP op can alternate with state. L2CAP channel tracking for AVCTP is direction-scoped because M7 reuses CID `0x0043` for AVDTP rx and AVCTP tx. Offline suite 306 PASS locally (no PIL errors in this environment).
- **BTN-1 PASS (2026-09-10).** `OpenDitoo.ButtonProbe` builds with `dotnet.exe build <UNC csproj> -c Release -p:OutDir=%LOCALAPPDATA%\OpenDitoo\ButtonProbe\` (no hash-bound output touched). Selftest `BUTTONPROBE_SELFTEST=PASS`. Live smoke from WSL interop: `smtc.acquired=true`, `rawinput_registered=true`. Positive control: one injected `VK_MEDIA_NEXT_TRACK` produced `rawinput_keyboard` (device `none(injected)`) then `smtc Next` 10 ms later — the probe's receive path works while hidden. Windows side: `Ditoo-Plus-audio Avrcp Transport` (0x110C/0x110E) present, device `IsConnected=True`; no AVRCP-derived HID node exists, so Ditoo keys are expected to arrive injected (device `none`), not as a HID consumer device. Host headless task verified applied (`conhost.exe --headless`).

## Current route

Read, in order:

1. `START_HERE.md`;
2. this handoff;
3. `AGENTS.md`;
4. `notes/OPENDITOO-BUTTON-AVRCP-RESEARCH-2026-09-10.md`;
5. `notes/OPENDITOO-BUTTON-AVRCP-PAGINATION-PLAN-2026-09-10.md`;
6. `notes/OPENDITOO-HANDOFF-2026-09-10-W10.md` only for the accepted Runtime 005/webcam baseline and traps that still matter;
7. deeper M7/session/Host evidence only as the active milestone requires.

Before changes, run `git status`, inspect HEAD/upstream, preserve any legitimate concurrent/untracked work, and run `python3 scripts/verify_day1_offline.py`. During handoff preparation a concurrent Host-headless fix landed cleanly as commit `24d0b70` (`Host outages root-caused: task-started Host lives in a closable terminal window`). It updates the install/refresh scripts, adds `runtime/windows/set_openditoo_day1_host_headless.ps1`, and appends the W10 handoff. Preserve it as legitimate concurrent work. The fix is prepared but applying it requires an **elevated Windows PowerShell** because the existing scheduled task was registered with admin rights; until applied, do not close the visible Windows Terminal hosting `OpenDitoo.Day1.Host.exe`. Re-check all of this because repository state may advance again before you start. Re-run the historical capability probes in your own environment rather than inheriting WSL_MCP's limitations:

```sh
command -v powershell.exe
python3 cli/openditoo.py status
python3 cli/openditoo.py activity-probe
```

A local Claude Code session in WSL is expected to have better Windows access than WSL_MCP, but this must be measured, not assumed.

## Accepted baseline to preserve

- exact target: Ditoo Plus `11:75:58:CE:DE:C7`, installed firmware `v42012`;
- MCP Dashboard v1 is accepted everyday product behavior;
- current dashboard policy is Runtime 005, local granted policy only; committed template remains unauthorized;
- accepted Host build hash: `f7bd60d4a56de4f4740bd84f7c645e201ddfd7ce29bf6c0f1e7512b1b67cd34e`;
- Host console-window failure mode is now root-caused; headless-task switch is prepared in commit `24d0b70` but not assumed applied; preserve that work and current task state;
- on-demand webcam policy `OPENDITOO-WEBCAM-PRODUCT-004` is separately granted; do not drift its frozen Studio files while doing button work;
- one RFCOMM controller owns Ditoo at a time;
- current Host/session path already receives unsolicited proprietary reports and treats a non-ACK report as canvas invalidation;
- `host/frame_stream.py` already supplies deterministic 16x16 RGB888 frame-set playback suitable for the second pagination page;
- W9B remains deferred; panel refresh remains unmeasured; >18.46 fps work remains closed by default.

Do not modify accepted Runtime 005/Host bytes in place merely to receive buttons. A successor pagination product revision is side-by-side until explicitly cut over.

## New exact-unit evidence that supersedes the old M7 whole-device conclusion

The preserved M7 Android HCI capture contains a separate AVCTP/AVRCP channel on PSM `0x0017`. The controlled physical sequence reconstructs as:

- Left -> AVRCP `0x4C` press + `0xCC` release -> Previous/Backward;
- Right -> AVRCP `0x4B` + `0xCB` -> Next/Forward;
- Left again -> `0x4C` again -> independent repeat confirmation;
- Lever -> AVRCP `0x44` + `0xC4` -> Play in the captured state;
- the same lever pull also correlates with proprietary RFCOMM `0xBD` about 1.7 ms earlier;
- M has no comparable later key-shaped event in its measured slot and remains bounded negative evidence only.

Therefore the old statement "left/right/lever are Bluetooth-silent" is no longer valid as a whole-device conclusion. They were silent on the proprietary RFCOMM application stream that M7 originally decoded. The current implementation problem is Windows event reception, not firmware unlocking.

## Immediate execution mission

### BTN-0 — executable AVRCP evidence, offline

Extend the existing btsnoop path narrowly enough to reproduce the preserved event sequence from the exact HCI bytes.

Preferred shape from the plan:

- add a small `host/avctp.py` decoder;
- extend L2CAP tracking without regressing current RFCOMM output;
- decode only the AVRCP pass-through subset needed here;
- produce a new derived exact-unit AVRCP evidence artifact; never rewrite the historical M7 capture JSON;
- add tests for Left/Right/Left/Lever, press/release pairing, fragmentation/truncation, unrelated AVCTP traffic, and preservation of existing RFCOMM results.

Exit only when repository code independently produces the measured sequence. Suggested durable gate: `BTN0_AVRCP_REPRODUCTION=PASS`.

### BTN-1 — receive-only Windows ButtonProbe

Create a side-by-side `.NET 8` Windows project, expected path:

`runtime/windows/OpenDitoo.ButtonProbe/`

Build a tiny hidden top-level WinForms/Win32 window and use SMTC/`ISystemMediaTransportControlsInterop::GetForWindow` as the primary receive seam. Enable Previous, Next, Play and Pause. Log raw events first as NDJSON with process epoch, monotonic + UTC timestamps, sequence, source, raw button and candidate normalization.

Candidate normalization after raw logging:

- Previous -> `nav_left`;
- Next -> `nav_right`;
- Play or Pause -> `lever_candidate`.

`WM_APPCOMMAND` may be logged as a second diagnostic channel, but do not merge/de-duplicate the two paths before exact measurement tells us what fires.

The probe must contain **no** Ditoo RFCOMM socket code, Host token, Host HTTP route, target address/override, image/session route, firmware/update path or device-write path.

Build it without perturbing hash-bound live Host/Studio outputs. Remember the W10 trap: ordinary `dotnet build/publish` can write repository output locations that standing policies hash-check. Use isolated output/staging for candidates until a deliberate cutover.

### BTN-2 — exact Windows physical receive proof

Once BTN-0/1 are clean and the local Windows environment is verified:

1. keep the accepted dashboard/runtime operating normally;
2. start ButtonProbe in the interactive user session;
3. establish a quiet baseline;
4. have the owner perform `Left -> Right -> Left -> Lever`, with clear spacing;
5. repeat the same sequence once;
6. record raw SMTC and any `WM_APPCOMMAND` observations separately;
7. correlate Host/product telemetry so arrow presses can be checked for stock takeover/session invalidation and lever behavior can be characterized.

Expected receive sequence is `Previous -> Next -> Previous -> Play/Pause`, twice. Do not silently turn that expectation into evidence; record what actually arrives.

If Windows app-level events are absent, use the plan's BTVS/HCI decision tree before changing the Ditoo or pursuing firmware:

- AVRCP visible at Windows HCI + absent at SMTC -> fix Windows media-session routing;
- AVRCP absent at Windows HCI -> inspect Windows audio/AVRCP profile state;
- neither outcome is permission to start MassBoot/firmware work for these controls.

BTN-2 is receive-only with respect to new OpenDitoo functionality. Do not invent or send proprietary Divoom commands for it. Existing standing dashboard authority remains exactly what its current local policy grants.

## After BTN-2 passes

Proceed through the plan rather than improvising a menu system:

- **BTN-3:** harden ButtonProbe into ButtonBroker with epoch + sequence + gap semantics and a tiny authenticated/local consumption surface;
- **BTN-4:** side-by-side successor product/page router, offline first;
- **BTN-5:** physical two-page acceptance.

First pagination page model:

- page 0 = existing live MCP dashboard renderer;
- page 1 = one frozen looping animation/GIF-derived frame set using the existing 16x16 RGB888 stream primitive.

First navigation semantics:

- dashboard + Right -> animation;
- animation + Left -> dashboard;
- Left on dashboard -> no-op;
- Right on animation -> no-op;
- lever -> log/ignore until its simultaneous RFCOMM `0xBD` behavior is characterized.

BTN-5 acceptance target:

**Dashboard visible -> physical Right -> animation visibly running -> physical Left -> live dashboard restored -> one genuine MCP activity pulse still renders correctly.**

Measure button-to-visible transition latency, event multiplicity and session identity. Do not optimize before it works reliably.

## Lever warning

The lever is not equivalent to the arrows. Exact M7 evidence correlates the same pull with both AVRCP Play and proprietary `0xBD`. Runtime 005 currently treats any unsolicited non-ACK RFCOMM report as a canvas invalidation/yield.

So:

- prove the lever in BTN-2;
- keep it out of first pagination semantics;
- observe whether it invalidates/yields the dashboard under Windows;
- do not special-case `0xBD` as benign without physical display evidence;
- only later decide whether AVRCP is canonical, `0xBD` is fallback/corroboration, and how duplicates are suppressed.

## Authority / stop conditions

The implementation session may freely perform repository edits, builds, offline tests, receive-only Windows diagnostics and other non-transmitting preparation consistent with the repo contract.

Do **not** infer authority for a new display/transmission shape from the existing Runtime 005 grant. Any new experimental display run or successor persistent pagination policy must follow `AGENTS.md`: reviewed manifest/policy, frozen hashes where required, explicit named owner grant, no replay of consumed identities, no retry after ambiguity, and rollback preserved.

Do not:

- flash/update firmware;
- enter/guess MassBoot or test-mode combinations;
- open a second Ditoo RFCOMM controller;
- add raw-send or generic Bluetooth control surfaces;
- weaken the exact-target boundary;
- modify the current Host merely to receive standard AVRCP;
- drift granted webcam Studio files while button work is in progress;
- re-open W9B or >18.46 fps research as part of this objective.

## Durable checkpoint expectations

At each natural boundary, update the plan/current handoff with what was actually proven and the exact next action. Preserve failed/negative results instead of retrying an ambiguous live operation. After two materially identical failures, reassess rather than repeat.

Useful milestone checkpoint boundaries are BTN-0 reproduction, BTN-1 Windows build/selftest, BTN-2 physical receive proof, BTN-4 offline pagination, and BTN-5 physical pagination acceptance.

## Definition of success for this handoff

The immediate implementation objective is complete when the exact Ditoo's arrows have been physically proven as usable Windows/OpenDitoo input and the device has demonstrated **Dashboard -> Right -> animation -> Left -> live Dashboard** without firmware modification, a second RFCOMM controller, duplicate input, or accidental stock takeover from the arrows. Lever productization is explicitly later unless its behavior turns out clean enough to close alongside the arrow work without weakening evidence discipline.
