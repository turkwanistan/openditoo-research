# OpenDitoo Day-1 execution state — 2026-09-08

## Objective

Current application-first objective:

`stock unit -> characterized identity -> measured application-control transport -> packet compatibility verdict -> one bounded custom operation -> one independently justified volatile 16x16 frame`

This execution intentionally overrides the older MassBoot/update priority for Day 1 without deleting that research.

## Repository / topology reconciliation

### WSL_MCP registration

WSL_MCP project discovery is root-based, not an independent per-project registry. The configured WSL project root exposes direct child repositories under `/home/wan/Projects`; `openditoo-research` is therefore a supported discovered project at:

`/home/wan/Projects/openditoo-research`

`project_preflight` confirms it is readable, writable, a Git repository, sandbox-ready/fail-closed, and independently addressable as WSL_MCP project `openditoo-research`.

### OpenDitoo synchronization

Before Day-1 edits:

- WSL branch: `main`
- WSL HEAD: `0f000cbb2ff8ea79c7a48294f5886853ea906fba`
- upstream: `origin/main`
- fresh fetch: PASS; HEAD equals fetched `origin/main`
- parent/base with OptiPlex clone: `1e4fd0704a4e6d95f9b139ea383307765aa38dcb`
- `0f000cbb...` adds only the WSL workspace scaffolding/layout note.

The older OptiPlex checkout remains clean at `1e4fd070...`. Its dedicated Git pull operation was blocked because project-specific Git credentials are not provisioned. No destructive or alternative credential workaround was attempted. The WSL checkout is the current synchronized implementation checkout; the OptiPlex copy remains preserved as an older clean evidence clone.

All 19 entries in `artifacts/SHA256SUMS` verify in WSL after transfer. Representative exact Ditoo Plus firmware hashes remain:

- flag60 v60014: `02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300`
- flag42 v42016: `f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a`

These are reference firmware artifacts, not proof of the purchased unit's installed firmware.

### OpenTivoo isolation

OpenTivoo was fetched and hydrated without merge/reset/cleanup. Current live state during this execution:

- branch `master`
- HEAD `8f3a1afe429f10d8385149fb07f587cbc356cbff`
- `verify_cached.py fast --profile hydrate`: PASS, `canonical_trust=false`
- canonical operational state: D-359 TV/video physical trial active, one session not started
- existing untracked media/build/session work preserved

No Tivoo Host, scheduled task, pairing, target, token, port or physical authority was altered or consumed.

## Minimum separate Ditoo control plane prepared

Target topology remains:

`WSL_MCP -> WSL OpenDitoo CLI -> Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

Only the offline/status-safe part is enabled so far.

### WSL CLI

`cli/openditoo.py` provides only:

- `auth-init` — creates a separate local token under `.openditoo-local/` with 0600 permissions;
- `status` — authenticated status request to fixed `http://127.0.0.1:8796`;
- `codec-compare` — offline candidate frame comparison;
- `capture-compare` — offline comparison of filtered application TX/RX fixtures;
- `frame-preview` — offline 16x16 diagnostic RGB artifact generation;
- `manifest-check` — fail-closed readiness review.

There is no device target argument, URL override, Bluetooth discovery/pairing, raw-send operation or transmission command.

### Windows Host candidate

Prepared:

- `runtime/windows/OpenDitoo.Day1.Host/`
- `runtime/windows/install_openditoo_day1_host.ps1`

Identity is deliberately separate:

- service: `OpenDitoo Day1 Host`
- port: `127.0.0.1:8796`
- scheduled task candidate: `OpenDitoo Day1 Host`
- Windows runtime root: `%LOCALAPPDATA%\OpenDitoo\Day1Host`
- token: OpenDitoo-specific `.openditoo-local/host.token`
- capabilities: status only
- `masterTransmitEnabled=false`
- `bluetoothTouched=false`
- `transportConfigured=false`
- `targetBound=false`

The installer only observes whether OpenTivoo's port 8779/task exist and explicitly preserves them. It refuses an ambiguous existing 8796 listener or pre-existing OpenDitoo task rather than replacing either automatically.

### Current Windows validation state

WSL_MCP's sandbox exposes no `powershell.exe`, `cmd.exe` or WSL interop, and this WSL environment has no `dotnet` SDK, so Windows execution remains an operator action. On Windows, the status-only Host dry run built successfully and reported `DEVICE_IO=false`, `BLUETOOTH_CONFIGURED=false`, `TARGET_BOUND=false`, with OpenTivoo observed separately on 8779.

The first `-Apply` attempt copied the isolated OpenDitoo runtime payload under `%LOCALAPPDATA%\OpenDitoo\Day1Host`, then failed at `Register-ScheduledTask` with `(14,8):UserId` before task launch or localhost status proof. Root cause was the installer using unqualified `$env:USERNAME` for the task principal. The installer was aligned with the proven OpenTivoo registration pattern: resolve `[System.Security.Principal.WindowsIdentity]::GetCurrent().Name`, require a fully qualified `authority\user`, bind both the `-AtLogOn -User` trigger and principal to that identity, build a task object, and register the object.

The patched installer then applied successfully. `OpenDitoo Day1 Host` registered for `WANSTATION\Wanstation`, preserved `OpenTivoo Product Runtime`, and completed `INSTALL_STATUS=PASS_STATUS_ONLY`.

No Bluetooth stack or Ditoo target was touched by environment setup. The WSL CLI still has no fallback port or raw/device transmission surface.

## Offline portability preparation

### Candidate codec

`host/ditoo_candidate_codec.py` implements the OpenTivoo normal and wrapped framing only as a comparison hypothesis:

- start/end marker candidate;
- little-endian length candidate;
- additive checksum candidate;
- normal and wrapped candidate decoders;
- fragmented/concatenated stream handling;
- retained malformed/checksum errors.

It contains no Ditoo command allowlist and treats its receive bound as a local analysis cap, not a Ditoo device limit.

### Exact-firmware application leads

A narrow string pass over both preserved exact-model-associated reference branches found the same `SPP_GET_DEVICE_INFO`, `SPP_GET_TOOL_INFO`, `SPP_GET_VOLTAGE`, `SPP_GET_STDB_MODE`, and `divoom_disp_draw_ctrl_init` strings at matching file offsets. This strengthens device-info as the preferred M2 stock capture and confirms a drawing subsystem is worth targeting later, but it assigns no command IDs/transport/persistence semantics. See `notes/OPENDITOO-DAY1-STATIC-APPLICATION-LEADS-2026-09-08.md`.

### Diagnostic frame

`host/diagnostic_frame.py` implements the exact Day-1 16x16 pattern as 768-byte RGB888 source data. Device quantization/packing is intentionally unresolved until M5 semantics are proven.

Current diagnostic RGB SHA-256:

`fb69505977b1be5d067e907a29d4ca1ed4d18de9b66bfc6921762cda81940955`

### Intake / capture templates

Prepared `experiments/DAY1-UNIT-INTAKE-PENDING.json` and `captures/DAY1-STOCK-TRANSACTION-TEMPLATE.json` so M0/M2 observations can be persisted with privacy separation, timing, packet references and reassembled application bytes.

### Pending manifests

Prepared fail-closed templates:

- `experiments/DAY1-M4-QUERY-PENDING.json`
- `experiments/DAY1-M5-FRAME-PENDING.json`

Both have `transmission_authorized=false` and no automatic retry. M4 currently reports these blockers:

1. `exact_unit_id_unbound`
2. `installed_firmware_unbound`
3. `measured_endpoint_unbound`
4. `semantic_evidence_missing`
5. `application_tx_unfrozen`
6. `transmission_authority_missing`

No physical authorization is being requested yet because the concrete transaction is not reviewable.

## Verification

`python3 scripts/verify_day1_offline.py`:

`DAY1_OFFLINE_PASS artifacts=19 tests=11 host=status_only port=8796 device_io=false transmission_authorized=false`

Source hashes at this gate:

- `cli/openditoo.py`: `5eb20384c15ddbf5882ef5405dff3c178e393de7ee24d7cfc56e9d00bf449f8e`
- `host/ditoo_candidate_codec.py`: `4631a421ae69175884d1dee70db4e4b917938828d424698a1c9f6a3bba77cc96`
- `host/diagnostic_frame.py`: `a4a58ef5d2b5d87ed6778db90a9c7f21f037f7dba9f42a2e64c7fd42ebe30a4d`
- Windows Host `Program.cs`: `e4da750034acf2ad50aa85d949b3c3ff7af5334faddedfcfc80f08b8d86172f8`
- Windows installer: `108023eeb44038b3fb615cf5cd688de7d85bea1db888b3e38529220c51bd451f`
- pending M4 manifest: `ac3f7ea2de4a320f0c11074859202ec8b5e78b1271858a55f1c17a5639795195`
- pending M5 manifest: `ebeca7284820b0a1322e4e38733a6accce59a19a14bf1a53d945e116f3e91401`

## Windows status-only environment proof

The patched installer was applied successfully from Windows PowerShell. It preserved the existing `OpenTivoo Product Runtime` task and observed OpenTivoo on port 8779 without modifying it. The separate task registered as `OpenDitoo Day1 Host` for `WANSTATION\Wanstation` and completed `INSTALL_STATUS=PASS_STATUS_ONLY`.

A subsequent authenticated probe from WSL_MCP through `cli/openditoo.py status` reached the fixed endpoint `http://127.0.0.1:8796` and returned:

- `service=OpenDitoo Day1 Host`
- `port=8796`
- `capabilities=[status]`
- `masterTransmitEnabled=false`
- `bluetoothTouched=false`
- `transportConfigured=false`
- `targetBound=false`
- `deviceIo=false`

This proves the environment/control-plane portion of `WSL_MCP → WSL CLI → Windows Host` while leaving the Windows Bluetooth → Ditoo portion intentionally unconfigured until M0/M1 evidence collection.

## M0 exact-unit evidence — partial

Operator-provided photographs establish the purchased unit is the expected pink Ditoo Plus family unit. The bottom label reads `Model: Ditoo-plus`, `FCC ID: A8I-DITOO-PLUS`, `Input: 5V==2A`, and `CMIIT ID: 2021DP1493`. A powered-on front photograph shows an active 16x16 display and active RGB keyboard backlighting. The source photographs remain private/uncommitted; only their SHA-256 values and non-sensitive observations are recorded in `experiments/DAY1-UNIT-INTAKE-PENDING.json`.

The operator has an Android phone available. Android will be used only as a stock-app observation/capture instrument for M1 if needed. The intended custom-control topology remains `WSL_MCP -> WSL CLI -> Windows Host -> Windows Bluetooth -> Ditoo`, matching the OpenTivoo architecture at the control-plane level.

Additional Android screenshots establish a stock Bluetooth audio identity `Ditoo-Plus-audio` at device address `11:75:58:CE:DE:C7`, shown active by Android with 10% reported battery and audio/call profiles enabled. The official Divoom app is connected to the same named device and exposes brightness, Device settings, and application functions including Design, Animation, Leditor and Pixel Coloring. This proves stock app/device interaction exists, but it does not establish whether application control is Classic SPP, BLE/GATT, or another endpoint. No installed firmware version or explicit firmware-update prompt is visible in the supplied screenshots, so those remain unresolved.

M0 is materially advanced but not yet closed because ordinary physical controls/speaker behavior and the installed firmware version remain unobserved.

## Milestone status

| Milestone | State | Gate |
|---|---|---|
| Environment | PASS | WSL_MCP → CLI → authenticated Windows Host proven on 127.0.0.1:8796; status-only, zero device I/O |
| M0 intake/stock baseline | PARTIAL | exact label/display/backlight plus stock Android/app identity observed; physical controls, speaker and installed firmware still pending |
| M1 transport/capture | READY TO CAPTURE | stock app connection confirmed; exact application-control transport/endpoint still unmeasured |
| M2 attributable stock transaction | NOT EXECUTED | no exported application payload capture |
| M3 offline compatibility verdict | PREPARED, BLOCKED ON INPUT | candidate comparator/tests/manifests ready; needs reassembled attributable stock TX/RX |
| M4 bounded custom query | BLOCKED | exact transaction and authority not yet reviewable |
| M5 volatile frame | BLOCKED | entry/paint/exit + persistence evidence not established |

## Exact next action

Begin M1 with Android Bluetooth HCI snoop enabled, then capture the official app performing one tightly attributable stock interaction. Prefer a device-info/settings refresh if the app exposes one; otherwise use one deterministic stock brightness change and record the before/after value. Export a whole Android bugreport privately and preserve it unmodified; derive and commit only filtered Ditoo-specific payload evidence after review. Android is the measurement sidecar only; no Android-based custom control path is being adopted. Do not issue any custom Ditoo transaction before M2/M3 evidence exists and a concrete M4 manifest passes review.
