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

M4 is authorized at `experiments/DAY1-M4-QUERY-PENDING.json` as `OPENDITOO-DAY1-M4-FILE-VERSION-001`; M5 remains a fail-closed template at `experiments/DAY1-M5-FRAME-PENDING.json`. M4 has explicit one-shot authority; M5 remains `transmission_authorized=false`. Neither permits automatic retry.

The M4 manifest binds the exact purchased unit, stock-measured RFCOMM channel 1 endpoint, high-confidence installed firmware version v42012, exact stock-observed read-only `0x97` file-version semantics, exact 8-byte TX, expected 13-byte wrapped response geometry, and one-shot budgets. The user explicitly authorized Windows pairing/discovery if needed and exactly one frozen M4 RFCOMM exchange, with no retries or other commands. `manifest-check` now reports `execution_ready=true` with no blockers.

The semantic/evidence freeze is documented in `notes/OPENDITOO-DAY1-M4-FILE-VERSION-FREEZE-2026-09-08.md`. A dedicated no-argument Windows runner now enforces the exact operation and checks Windows pairing before any RFCOMM connect. No custom Ditoo transmission has occurred yet.

## Verification

`python3 scripts/verify_day1_offline.py`:

`DAY1_OFFLINE_PASS artifacts=19 tests=12 host=status_only port=8796 device_io=false m4_completed=true m4_authorized=false m5_authorized=false`

Source hashes at this gate:

- `cli/openditoo.py`: `5eb20384c15ddbf5882ef5405dff3c178e393de7ee24d7cfc56e9d00bf449f8e`
- `host/ditoo_candidate_codec.py`: `4631a421ae69175884d1dee70db4e4b917938828d424698a1c9f6a3bba77cc96`
- `host/diagnostic_frame.py`: `a4a58ef5d2b5d87ed6778db90a9c7f21f037f7dba9f42a2e64c7fd42ebe30a4d`
- Windows Host `Program.cs`: `e4da750034acf2ad50aa85d949b3c3ff7af5334faddedfcfc80f08b8d86172f8`
- Windows installer: `108023eeb44038b3fb615cf5cd688de7d85bea1db888b3e38529220c51bd451f`
- frozen M4 manifest: `a855c68ac9c666388263e260b8a400be2da3fc49439e2e9534751667d53d0cef`
- filtered stock RFCOMM evidence: `9581469a4267db3b229e5167c73cbd0c9a056fa1c95c4709d4fb62a23fea3d70`
- M4 semantic freeze note: `1d47d927533341ee6db735d123429ef83accc100cc2c705616ef3b2b1b41ea2c`
- M4 exact protocol source: `bbf0bdf08a7e0c03c28297c17b432f9b8da541d7ceb8c566c64d78a854882dc4`
- M4 bounded RFCOMM source: `ac0e8187dcc252e214681e1178a38c09c93156882d2dfaaabc504a57113056ad`
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

This proves the environment/control-plane portion of `WSL_MCP → WSL CLI → Windows Host`. The installed/running Host intentionally remains status-only even after M1/M3 transport discovery; the frozen M4 RFCOMM implementation is currently offline/unreferenced source and cannot be invoked by `Program.cs`.

## M0 exact-unit evidence — partial

Operator-provided photographs establish the purchased unit is the expected pink Ditoo Plus family unit. The bottom label reads `Model: Ditoo-plus`, `FCC ID: A8I-DITOO-PLUS`, `Input: 5V==2A`, and `CMIIT ID: 2021DP1493`. A powered-on front photograph shows an active 16x16 display and active RGB keyboard backlighting. The source photographs remain private/uncommitted; only their SHA-256 values and non-sensitive observations are recorded in `experiments/DAY1-UNIT-INTAKE-PENDING.json`.

The operator has an Android phone available. Android will be used only as a stock-app observation/capture instrument for M1 if needed. The intended custom-control topology remains `WSL_MCP -> WSL CLI -> Windows Host -> Windows Bluetooth -> Ditoo`, matching the OpenTivoo architecture at the control-plane level.

Additional Android screenshots establish a stock Bluetooth audio identity `Ditoo-Plus-audio` at device address `11:75:58:CE:DE:C7`, shown active by Android with 10% reported battery and audio/call profiles enabled. The official Divoom app is connected to the same named device and exposes brightness, Device settings, and application functions including Design, Animation, Leditor and Pixel Coloring. The later HCI capture independently resolves the application-control route as Classic RFCOMM/SPP channel 1.

The same exact-unit stock capture contains official-app request `01040097009b0002` and wrapped response `010900049755001ca400b90102`. Supporting Divoom application reverse engineering maps command `0x97` to `SPP_GET_FILE_VERSION`; selector `00` is echoed and response bytes `1c a4` decode little-endian to decimal **42012**. The installed version is therefore frozen as **v42012 with high confidence**. This identifies the installed version number, not byte identity with a preserved firmware binary; the project does not currently possess a v42012 image.

M0 is materially advanced but remains partial only because ordinary physical-control and speaker behavior have not yet been explicitly recorded.

## M1/M2/M3 stock-capture result — PASS

A private Android 16 bugreport from the exact purchased unit was analyzed without committing the raw archive. Source SHA-256 is `a263e98039d4624b7d1fdd0b6c1021bc3bebf4242ec021bd7f704b7b31258a65`; extracted `btsnoop_hci.log` SHA-256 is `a00ed50b2dc78bc38167de6d0d73ee4c0f63a4e0faf4b33a56ff5f56898b3d43`. One official-app frame contained account/application metadata; its contents are omitted and only SHA-256 `11d7ade7a5b95032c1c423a119be8777327d7da98f569689368abba874b56e66` is retained. Filtered evidence is `captures/OPENDITOO-DAY1-STOCK-RFCOMM-2026-09-08.json`.

Measured exact-unit route:

`11:75:58:CE:DE:C7 -> Bluetooth Classic BR/EDR ACL -> L2CAP PSM 0x0003 -> RFCOMM mux -> SDP Serial Port 1 -> RFCOMM server channel 1 / DLCI 2`

The same Classic link also carries ordinary audio/telephony profiles on other RFCOMM channels. No Ditoo-attributable LE connection-complete event was observed during this capture. This proves the observed application-control route is Classic RFCOMM/SPP for this stock session; it does not claim the device has no BLE capability.

Application framing verdict is **MATCH**. All 56 host-to-device application frames and all 36 device-to-host application frames in the filtered channel-1 stream satisfy the candidate additive-checksum frame geometry. All 36 device responses use outer command `0x04`, inner-command echo, tag `0x55`, and inner payload. No captured channel-1 frame failed the checksum rule. The capture itself did not exercise application-frame fragmentation or concatenation.

Representative official-app transaction:

- request `01 03 00 31 34 00 02` -> normal command `0x31`, no payload;
- response `01 06 00 04 31 55 5D ED 00 02` -> outer `0x04`, inner `0x31`, tag `0x55`, payload `0x5D`.

This transaction is fully attributable to the official Divoom app over measured RFCOMM channel 1. Its exact Ditoo semantic label is intentionally not promoted yet. OpenTivoo independently maps family command `0x31` to a read-only display-light-level getter, and the live Ditoo value `0x5D` is compatible with the high light-intensity stock setting visible in the operator screenshot, but this remains supporting family/correlation evidence until exact-Ditoo semantics are frozen.

Android package metadata also closes two M0 fields: Android 16 / build `CP1A.260505.005`, Divoom app `3.8.34` / versionCode `634`. The stock `0x97` transaction closes the installed version number as v42012; see the M4 semantic freeze note for evidence layering.

## Milestone status

| Milestone | State | Gate |
|---|---|---|
| Environment | PASS | WSL_MCP → CLI → authenticated Windows Host proven on 127.0.0.1:8796; status-only, zero device I/O |
| M0 intake/stock baseline | PARTIAL | exact label/display/backlight/app identity and v42012 version established; explicit physical controls/speaker confirmation remains |
| M1 transport/capture | PASS | exact purchased-unit stock route measured as Classic RFCOMM/SPP channel 1 |
| M2 attributable stock transaction | PASS | official-app channel-1 request/response bytes frozen, including exact stock file-version query |
| M3 offline compatibility verdict | PASS | 92/92 observed application frames match candidate checksum/frame geometry; all 36 responses match outer-0x04/tag-0x55 wrapping |
| M4 bounded custom query | PASS / AUTHORITY CONSUMED | Windows independently completed the exact one-shot 0x97 file-version query; v42012 returned; one connect, one request, socket closed, no retry |
| M5 volatile frame | FROZEN / AUTHORITY BLOCKED | exact Pixel Coloring capture proves RGB888 row-major 0x58 drawing, exact 0x44 image packing via 8/8 byte-perfect re-encodes, stock image preamble, no distinct wire exit, and no observed persistence commit; exact three-packet frame trial is frozen |

## Windows M4 compile proof

The operator compiled `runtime/windows/OpenDitoo.Day1.Host/OpenDitoo.Day1.Host.csproj` on Windows with `.NET 8`, Release configuration, `--no-restore`, and `--nologo`. Result: **Build succeeded, 0 warnings, 0 errors** in 1.24 seconds. This was compile-only: the installed Host was not restarted or replaced, `Program.cs` remained status-only, and no Bluetooth discovery, pairing, connection, or Ditoo transmission occurred.

## M4 live result — PASS

The authorized Windows runner completed successfully against the exact paired target `11:75:58:CE:DE:C7` on RFCOMM channel 1. It sent exactly `01040097009B0002`, decoded version **42012**, reported one request and one connection attempt, and closed the socket. No retry or second application command was issued. Result evidence is `captures/OPENDITOO-DAY1-M4-LIVE-RESULT-2026-09-08.json`. The one-shot M4 authority is consumed and the current runner is disarmed against replay.

## M5 Pixel Coloring capture result — PASS

The second private Android bugreport was analyzed without committing the raw archive. Filtered evidence is `captures/OPENDITOO-DAY1-PIXEL-COLORING-2026-09-08.json`; the semantic freeze is `notes/OPENDITOO-DAY1-M5-PIXEL-COLORING-FREEZE-2026-09-08.md`.

Exact-unit command `0x58` is proven as `RGB888 | count | row-major pixel index[count]` with `index=y*16+x`. The operator's asymmetric red/green/blue/gray/white marks independently resolve orientation. Exact-unit command `0x44` is proven as a full palette-indexed 16x16 snapshot using RGB888 palette entries and least-significant-bit-first packed row-major palette indices. All eight captured `0x44` snapshots were decoded and re-encoded byte-for-byte exactly.

The exact stock image-transfer preamble is `0103009fa20002` then `010400bd31f20002`. No distinct Pixel Coloring exit command was observed after the final `0x44` acknowledgement, so the custom exit is local RFCOMM close rather than an invented command. No save/publish/firmware/persistent-commit operation was observed; persistence across a full power cycle remains untested.

The frozen first custom frame is a 132-byte six-color RGB888 `0x44` image on black background with the Day-1 corner/center diagnostic geometry. SHA-256: `db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b`. The full three-packet sequence is 147 application bytes total and is recorded in `experiments/DAY1-M5-FRAME-PENDING.json`.

## Exact next action

Request explicit authority for `OPENDITOO-DAY1-M5-STATIC-DIAGNOSTIC-001`: one already-paired RFCOMM channel-1 connection and exactly three sends (`0x9F` stock image preamble, `0xBD/0x31` stock image preamble, one 132-byte custom `0x44` diagnostic image), no retry or reconnect, accept one checksum-valid wrapped `0x44` acknowledgement, then close locally. M5 is currently `transmission_authorized=false`; M4 authority is consumed and does not transfer.


## M5 attempt 1 — local runner failure, no image packet sent

The first authorized M5 attempt connected to the exact paired Ditoo and successfully sent packet 1 (`0103009fa20002`). The runner then failed closed with `M5_SEND_READY_2_TIMEOUT; NO_RETRY` before packet 2. Packet 2 and the 132-byte `0x44` diagnostic image packet were not sent; no retry occurred. This is attributed to repeated `FD_WRITE` readiness waits in the Windows nonblocking Winsock runner, not to a Ditoo protocol rejection. Evidence: `captures/OPENDITOO-DAY1-M5-ATTEMPT1-2026-09-08.json`.

The transport was corrected offline to wait for initial `FD_WRITE` once after connect, then perform exactly one `send()` call for each frozen packet. Any partial send, `WSAEWOULDBLOCK`, or later error still fails closed with no resend. Windows compile-only validation of the corrected disarmed runner passed with 0 warnings and 0 errors in 0.90 s. Attempt-1 authority is consumed; attempt 2 requires fresh explicit authority.
