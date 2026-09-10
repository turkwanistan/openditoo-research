# OpenDitoo physical-control AVRCP research addendum — 2026-09-10

**Status:** evidence synthesis / no device I/O performed by this note.

**Source basis:** owner-supplied `OPENDITOO-BUTTON-AVRCP-UNLOCK-RESEARCH-2026-09-09(2).md`, the live OpenDitoo repository, and the already-preserved exact-unit M7 Android HCI capture. The uploaded research remains the detailed external-research dossier; this note preserves the project-critical conclusions and route inside the repository.

## Executive correction

The earlier M7 product conclusion that left/right/lever were Bluetooth-silent was too broad. That conclusion described the proprietary Divoom RFCOMM application stream only. Re-analysis of the same exact-unit HCI capture shows a separate AVCTP/AVRCP control channel on Bluetooth PSM `0x0017`.

Measured physical sequence from the preserved sweep:

| Physical action | Exact-unit Bluetooth observation | Standard meaning | Project interpretation |
| --- | --- | --- | --- |
| Left | AVRCP pass-through `0x4C` press + `0xCC` release | Previous / Backward | strong candidate `nav_left` |
| Right | AVRCP `0x4B` press + `0xCB` release | Next / Forward | strong candidate `nav_right` |
| Left again | AVRCP `0x4C` press + release | Previous / Backward | repeat confirmation |
| Lever | AVRCP `0x44` press + `0xC4` release | Play in captured state | `lever_candidate` |
| Lever, same pull | proprietary RFCOMM `0xBD`, ~1.7 ms before AVRCP | lever-correlated proprietary report | corroboration/fallback; must be de-duplicated if both paths are used |
| M | no comparable later AVRCP/SPP key-shaped event in its measured slot | unresolved/local-only in this context | bounded negative only |

The deliberate M7 action order was:

`left -> right -> left -> minus -> plus -> brightness -> lever -> M`

The recovered AVRCP sequence mirrors the first three controlled actions and the later lever slot. This makes an unrelated asynchronous media-event explanation implausible and supersedes the whole-device claim that the navigation controls were silent.

## Why M7 missed it

The existing `host/btsnoop.py` path was built to reconstruct the proprietary Divoom application stream over RFCOMM PSM `0x0003`. The same capture also established L2CAP channels for:

- `0x0003` — RFCOMM;
- `0x0017` — AVCTP, which carries AVRCP;
- `0x0019` — AVDTP.

The arrows did not need to appear on the proprietary RFCOMM application stream because they were already being exported as standard Bluetooth media-control commands.

The durable correction is therefore:

> left/right/lever were silent on the proprietary RFCOMM application stream under the original M7 parser; the preserved exact-unit HCI capture proves left/right/lever Bluetooth events on AVRCP.

Historical M7 evidence files remain immutable. A new derived AVRCP evidence artifact should be produced by repository code in BTN-0 rather than rewriting old capture JSON.

## Product consequence

The high-value problem is no longer firmware unlocking. The device-side export already exists. The immediate engineering problem is receiving the standard AVRCP controller events on Windows and normalizing them for OpenDitoo.

Target topology:

`Ditoo physical key -> AVRCP controller command -> Windows Bluetooth stack -> Windows media-control event -> OpenDitoo.ButtonProbe/ButtonBroker -> typed input -> page router`

No custom Ditoo Bluetooth command is needed to prove the input path.

## Recommended Windows receive seam

Primary diagnostic/product seam: a tiny receive-only Windows companion using System Media Transport Controls (SMTC) from a process-owned top-level HWND.

Enable only:

- Previous;
- Next;
- Play;
- Pause.

Log raw Windows events first. Candidate normalization only after measurement:

- Previous -> `nav_left`;
- Next -> `nav_right`;
- Play or Pause -> `lever_candidate`.

A secondary `WM_APPCOMMAND` observation path is useful as an independent diagnostic. Keep it separate from SMTC during proof so one physical press cannot be accidentally double-counted.

If Windows does not surface SMTC/WM_APPCOMMAND events, use Windows Bluetooth HCI tracing/BTVS as the ground-truth branch before considering any firmware work:

1. HCI sees AVRCP and SMTC sees it -> receiver solved;
2. HCI sees AVRCP but SMTC does not -> Windows media-session routing problem;
3. HCI does not see AVRCP -> Windows audio/profile connection-state problem;
4. none of these outcomes justify MassBoot/firmware work for left/right/lever.

## Important lever asymmetry

Left/right currently appear as clean AVRCP candidates. The lever is different: the exact M7 capture correlates the same pull with both AVRCP `0x44` and proprietary RFCOMM `0xBD`.

The accepted Runtime 005 Host treats an unsolicited non-ACK RFCOMM report as canvas invalidation and ends/yields the current display session. Therefore:

- prove lever reception in the same ButtonProbe experiment;
- do not use lever for the first pagination acceptance;
- do not teach the Host that `0xBD` is benign merely because it correlates with the lever;
- first measure whether a lever pull under the current Windows product context actually causes stock takeover/session yield;
- only after exact-unit evidence may a successor product decide whether AVRCP is canonical, `0xBD` is corroboration/fallback, and how de-duplication works.

## Immediate implementation route

The authoritative implementation plan is:

`notes/OPENDITOO-BUTTON-AVRCP-PAGINATION-PLAN-2026-09-10.md`

The shortest success chain is:

1. **BTN-0:** reproduce AVRCP from preserved HCI bytes with repository code;
2. **BTN-1:** build receive-only `OpenDitoo.ButtonProbe`;
3. **BTN-2:** exact Windows physical proof: Left -> Right -> Left -> Lever, twice;
4. **BTN-3:** harden to typed ButtonBroker with epoch/sequence semantics;
5. **BTN-4:** offline two-page router using current dashboard + frozen GIF-derived frame set;
6. **BTN-5:** physical acceptance: Dashboard -> Right -> animation -> Left -> live Dashboard;
7. only then cut a successor standing product policy/revision and separately productize lever behavior.

## First-page scope

The first physical pagination proof intentionally uses only two pages:

- page 0: the existing live MCP dashboard renderer;
- page 1: one looping animation produced offline as deterministic 16x16 RGB888 frames using the existing frame-stream primitive.

Navigation:

- Dashboard + Right -> animation;
- animation + Left -> dashboard;
- Left on dashboard -> no-op;
- Right on animation -> no-op;
- lever -> logged/ignored until its RFCOMM side effect is characterized.

This keeps the first acceptance about genuine physical input and page ownership rather than building a menu framework.

## Authority and preservation boundary

For the initial receiver proof:

- do not modify the Runtime 005 Host;
- do not open a second RFCOMM connection;
- do not add raw AVRCP send capability;
- do not add target selection or generic Bluetooth controls;
- do not modify firmware, MassBoot, update paths, USB vendor paths, or teardown state;
- keep Runtime 005 as rollback baseline;
- build pagination as a side-by-side successor product revision;
- any live display behavior beyond the current granted product policy still follows the repository's explicit authority rules.

The ButtonProbe itself should contain no Host token, Ditoo RFCOMM code, target override, image/session route, or device-write path.

## Public-reference set from the uploaded research

The detailed uploaded dossier cited the following relevant public references for standards/API semantics and comparative evidence:

- Bluetooth SIG Assigned Numbers — AVCTP PSM `0x0017` and AVRCP identifiers;
- AOSP `BluetoothAvrcp.java` — pass-through operation IDs `0x44`, `0x4B`, `0x4C` and release-bit handling;
- Microsoft Bluetooth Classic audio guidance — accessory AVRCP-controller / Windows-target role;
- Microsoft Windows Bluetooth profile support — AVCTP/AVRCP/A2DP/RFCOMM support;
- Microsoft System Media Transport Controls and `ISystemMediaTransportControlsInterop::GetForWindow`;
- Microsoft `WM_APPCOMMAND` media commands;
- Microsoft Bluetooth Virtual Sniffer (BTVS);
- Ditoo Plus manual — Previous/Next/Play-Pause physical semantics;
- `ismkdc/ditoo-clawdmeter` — comparative RFCOMM listener associating proprietary `0xBD` with lever pull;
- Anyka AK1052D and `minitoo-forth` references — deeper no-solder methodology only, explicitly not the current route.

## Bottom line

For left/right/lever, OpenDitoo should exploit the already-measured AVRCP seam first. The next decisive unknown is not whether the Ditoo emits the buttons over Bluetooth; it is whether the local Windows product environment can reliably receive them while Runtime 005 owns the display session. That is what BTN-0 through BTN-2 must settle before pagination implementation proceeds.
