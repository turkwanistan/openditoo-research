## 2026-09-12 volatile-RAM API pivot — ACTIVE

The active research route is now `notes/OPENDITOO-HANDOFF-2026-09-12-VOLATILE-RAM-API.md` / `notes/OPENDITOO-VOLATILE-RAM-API-PARSER-PLAN-2026-09-12.md`: exhaust the owned Ditoo Plus Bluetooth/parser surface for a reversible RAM-resident OpenDitoo API before considering more physical recovery work. Start with complete SPP dispatcher/nested-mux coverage and caller-controlled memory/dataflow classification; a crash without controllability is not a promoted result. Runtime 018 remains the accepted everyday product and must not be changed by offline parser research. M2 unpowered mapping remains authorized/unconsumed but is deferred by the owner's current no-measure/no-attach preference. Any live custom/malformed parser probe requires a fresh reviewed one-use manifest and exact grant.

## 2026-09-12 current research/product checkpoint — Runtime 018 live; recovery research at software-first blocker

The everyday product is **Runtime 018** (`OPENDITOO-PRODUCT-RUNTIME-018`, `runtime_revision=13`, `host/product_runtime_v12.py`). Its raw-AVRCP input sidecar, pages, Host/session/pacing/reconnect/reclaim envelope and webcam policy 006 remain the accepted product baseline. Read `notes/OPENDITOO-HANDOFF-2026-09-12-R018.md` before product/runtime changes.

The current separate research route is the **recovery-gated software-first/MassBoot decision point**. Read `notes/OPENDITOO-SOFTWARE-FIRST-RECOVERY-R0-2026-09-12.md` first; use `notes/OPENDITOO-HANDOFF-2026-09-12-MASSBOOT-R2.md` only if the owner explicitly chooses the deferred physical fallback. SFR-1/2/3 and the first SFR-4 lineage expansion are closed: stock SPP exposes no analyzed caller-controlled flash-read chain, current/legacy app update services expose production/test branches but no historical selector, and a provenance-strong 2021 Divoom 3.1.58 client confirms the hidden test-version/test-server controls without revealing a recovery catalogue. Exact v42012 **bytes are still unrecovered**. The prepared MassBoot M1 remains photos-only, `prepared_unauthorized`, and unconsumed; no checksum-valid custom image or physical escalation is authorized.

Everything below that names Runtime 006 or an older objective as current is retained as historical evidence and is superseded by this checkpoint plus `START_HERE.md`.


## 2026-09-10 current product/input update — physical button pagination LIVE (Runtime 006)

The everyday product is now **Runtime 006** (`OPENDITOO-PRODUCT-RUNTIME-006`, granted by the owner 2026-09-10 17:44Z): the Runtime 005 MCP dashboard, byte-identical Host/session/pacing/reclaim envelope, plus physical-button pagination. Ditoo Left/Right page through a wrap-around list (`dashboard`, `spiral`); a short lever pull runs the current page's action (spiral: pause/resume). Input is AVRCP -> Windows SMTC -> the receive-only `OpenDitoo.ButtonProbe` (child of `openditoo-product.service`, `--status mirror`) -> read-only NDJSON cursor in `host/pagination.py`. Runtime 005 is the rollback (`scripts/cutover_runtime_006.sh --rollback`). The on-demand webcam policy `OPENDITOO-WEBCAM-PRODUCT-005` is unchanged. The Host headless task (`24d0b70`) is applied.

BTN-0..8a evidence chain: M7 HCI re-analysis reproduced by repository code (Left `0x4C`, Right `0x4B`, Lever `0x44` + RFCOMM `0xBD`); Windows receive proof (one SMTC event per arrow press); one-use physical pagination acceptance; lever characterization (short pull = one Play/Pause in mirror mode, play-direction pulls also send `0xBD` -> invisible 46-69 ms reclaim; long holds unreliable and can enter a Ditoo "recording" mode); YouTube media-key contention PASS. Some first arrow presses after a quiet period also send RFCOMM `0x09` -> invisible reclaim; page state lives outside Host sessions so both are harmless.

Next objective (owner-selected, not started): a high-FPS page on the Host's existing `streaming_ack_clock` profile (Python `frame_stream.stream_session` first), proven by a one-use trial that pages in/out ~10 times before any standing revision.

Authoritative current files:

- `notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md` (current handoff; read its "Next session" section first)
- `notes/OPENDITOO-BUTTON-AVRCP-RESEARCH-2026-09-10.md`
- `notes/OPENDITOO-BUTTON-AVRCP-PAGINATION-PLAN-2026-09-10.md`
- prior accepted baseline: `notes/OPENDITOO-HANDOFF-2026-09-10-W10.md`

Everything below remains evidence/history and is superseded wherever it states an older current objective or the pre-AVRCP M7 product conclusion.

## 2026-09-08 M5 first custom frame — PASS

The exact purchased Ditoo Plus successfully rendered the frozen custom diagnostic 16×16 frame over Windows-owned RFCOMM channel 1. The successful attempt sent the exact three-packet stock-derived sequence once, received wrapped `0x44` ACK payload `0x12`, closed cleanly, and visibly rendered the expected colored diagnostic marks. M5 authority is consumed and the one-shot runner is disarmed. This establishes a proven runtime image-control primitive suitable for bounded productization into typed PNG/image tooling; it does not by itself prove persistence across power cycle.

# OpenDitoo Research — Canonical Project State

**Target:** Divoom Ditoo Plus (pink purchased unit)  
**State date:** 2026-09-10
**Phase:** W10 product baseline accepted; AVRCP physical-control reception and two-page pagination route active.
**Safety posture:** preservation-first. No flashing, arbitrary proprietary writes, guessed service-mode entry, electrical probing, soldering, or destructive teardown has been authorized or performed.

This file is the human-readable synthesis of the static/reconnaissance base and the
2026-09-08 Day-1 execution. It supersedes ad-hoc chat summaries but does not replace raw
evidence, hashes, or provenance under `artifacts/`.

**Routing, 2026-09-10:** for current state read `START_HERE.md`, then
`notes/OPENDITOO-HANDOFF-2026-09-10-BUTTONS.md`, the AVRCP research addendum and the pagination plan.
The 2026-09-09 roadmap and earlier handoffs are historical context. Everything below that presents an older
"current objective" — including MassBoot/update/service-mode priorities and the original RFCOMM-only M7
navigation conclusion — is retained as history and must not override the current route.

## 0. 2026-09-08 Day-1 application-first execution update

The current objective is now stock characterization -> measured application-control transport -> codec verdict -> one bounded custom query -> one independently justified volatile 16x16 frame. This temporarily overrides the older ranked MassBoot/update priorities without deleting or weakening that research.

A synchronized WSL_MCP implementation checkout is established at `/home/wan/Projects/openditoo-research` and matches fetched `origin/main` at pre-Day-1 HEAD `0f000cbb2ff8ea79c7a48294f5886853ea906fba`. All 19 preserved artifact SHA-256 entries verify. The older OptiPlex checkout remains clean at `1e4fd070...`; updating it is blocked by unprovisioned project Git credentials.

OpenDitoo tooling includes a separate CLI/token, candidate frame comparator, exact diagnostic RGB source, completed M4/M5 evidence, and a separate authenticated Windows Host on `127.0.0.1:8796`, isolated from OpenTivoo on 8779. Post-M5 productization adds a typed static-image Host route and exact 16×16 PNG CLI path; as written on 2026-09-08 the installed Windows Host still had to be refreshed before that new route was live. **Superseded 2026-09-09 (M6/M8):** the refresh was performed and the installed `OpenDitoo.Day1.Host.dll` SHA-256 `092ed38d4dd7aaeb3eedbdab15c2c0a0f8dac07ea6134545e18ad15398fa636c` was verified byte-identical to the repository's `bin/Release/net8.0` build, deployed at `%LOCALAPPDATA%\OpenDitoo\Day1Host` under the at-logon scheduled task `OpenDitoo Day1 Host`. The Host now also carries the M8 `/v1/image/sequence` route. That identity was verified at M6 time and was **not** re-verified during the 2026-09-09 N1 documentation pass; re-check the hash before any build-sensitive step instead of inheriting it.

Exact purchased-unit stock capture now proves the official app control route is Bluetooth Classic BR/EDR -> L2CAP RFCOMM PSM 0x0003 -> SDP Serial Port 1 -> RFCOMM channel 1 on `Ditoo-Plus-audio` / `11:75:58:CE:DE:C7`. The filtered channel-1 stream contains 56 host-to-device and 36 device-to-host application frames; all 92 satisfy the candidate normal framing/checksum, and all 36 responses use outer command `0x04` with inner-command echo and tag `0x55`. This promotes framing/transport compatibility, not Tivoo command semantics. Raw Android bugreport material remains private; filtered evidence is preserved under `captures/OPENDITOO-DAY1-STOCK-RFCOMM-2026-09-08.json`.

The exact-unit stock initialization also contains `0x97 00` with wrapped payload `00 1c a4 00`. Independent Divoom application reverse engineering names `0x97` as `SPP_GET_FILE_VERSION`; the echoed selector plus little-endian `0xa41c` identifies installed version **v42012** with high confidence. This is a version-number observation, not a recovered v42012 firmware binary.

M4 physically passed from Windows: the exact one-shot `0x97` file-version request independently returned v42012, one connection/request was used, and the socket closed. Its authority is consumed and the M4 runner is disarmed.

A second exact-unit Pixel Coloring capture proves command `0x58` uses RGB888 plus row-major pixel indices and proves the complete command-`0x44` 16x16 palette-image encoding. Eight captured full snapshots re-encode byte-for-byte exactly, establishing orientation, palette construction and bit packing without inheriting Tivoo semantics. This path uses RGB888 palettes; OpenTivoo RGB222 is not a Ditoo `0x44` requirement. The first custom diagnostic `0x44` frame is frozen at SHA-256 `db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b`. M5 attempt 2 physically passed: all three packets sent once, wrapped `0x44` ACK payload `0x12` returned, socket closed, and the operator confirmed the diagnostic marks visibly rendered. M5 authority is consumed. Current post-M5 productization state is in `notes/OPENDITOO-POST-M5-TYPED-IMAGE-RUNTIME-2026-09-08.md`.

## 1. Project boundaries and evidence discipline

This is a separate project from OpenTivoo. OpenTivoo is prior art, a source of comparative artifacts, and a reusable methodology/tooling base only.

Evidence labels:

- **MATCHED** — exact Ditoo Plus evidence or exact Ditoo Plus firmware evidence.
- **RELATED / STRONG** — closely related Divoom-family evidence with a strong technical connection, not exact-unit truth.
- **LEAD ONLY** — useful hypothesis/search direction.
- **NO EVIDENCE / DIFFERENT** — explicitly not transferable.

Do not promote original Tivoo/Ditoo/Minitoo behavior to Ditoo Plus without independent evidence.

## 2. Purchased target

Purchased listing: pink Divoom Ditoo Plus, used/tested, sold with charger/cable and replacement box. The physical purchased unit has not yet been opened or subjected to service-mode experiments.

When it arrives, its own labels, firmware version, Bluetooth identities, USB behavior, PCB markings, and service behavior become the highest authority.

## 3. Exact regulatory evidence

FCC ID: **A8I-DITOO-PLUS**  
Applicant: Shenzhen Divoom Technology Co., LTD.  
Filing date: 2020-12-28.

Public FCC artifacts are mirrored locally under `artifacts/fcc/` with source URLs and SHA-256 values in `artifacts/fcc/SOURCES.json`.

Exact BDR/EDR test-report facts:

- hardware version: **REV:V1.1**
- software version: **`ditoo-plus(3128)_svn26520_v60001`**
- Classic Bluetooth BDR/EDR
- 2402–2480 MHz / 79 channels
- 1, 2, and 3 Mbit/s
- GFSK / π/4-DQPSK / 8-DPSK
- PCB antenna

Exact internal FCC photos show:

- green main logic PCB with an Anyka-branded SoC
- separate blue keyboard PCB
- black display-driver PCB with `DITOO-LED` silkscreen
- 16×16 LED matrix
- PCB trace antenna
- USB-C connector
- TF/microSD connector
- 3.7 V, 3000 mAh, 11.1 Wh battery, marking approximately `HYY 754860P 2010`
- modular connectorized boards/cables
- CHIPONE-branded display-board ICs; exact part numbers not yet promoted

The exact SoC package suffix is not yet readable enough from public imagery to promote `AK1052DN048` for Ditoo Plus.

FCC schematics, block diagram, and operational description are under permanent confidentiality and are not public-recovery targets.

## 4. Exact manual / normal device behavior

The exact Ditoo Plus manual establishes:

- companion Divoom/Divoom Smart app
- iOS pairing uses **`Ditoo-Plus-audio`** in Bluetooth settings and **`Ditoo-Plus-light`** inside the app
- Android can discover/connect the light/audio identities through app/settings
- USB-C charging
- TF card MP3 playback, up to 64 GB
- 3000 mAh / 3.7 V battery
- power button: press = battery status; **double press = disconnect Bluetooth**; hold = power on/off
- hold **M** = keyboard backlight on/off during normal operation

Important non-transfer rule: the Ditoo Plus double-power behavior must not be conflated with any Tivoo recovery/reset observation.

## 5. Exact physical opening / teardown

A Japanese exact-model teardown documents a simple solder-free initial opening path:

1. remove keycaps if needed for keyboard inspection; switches are OUTEMU MX-compatible
2. flip device over
3. remove the rear/bottom rubber foot
4. remove the single screw beneath it
5. release case/back-cover clips with small precision flat tools
6. opening exposes the battery
7. keyboard/switch PCB is accessible after screws and careful flex-cable disconnection

Source: `https://kbdbuild.vercel.app/blog/divoom_ditoo_plus_chage_keyswitch`

The article later desolders switches; that is outside the initial project plan.

### First-opening rules

- establish full stock operation first
- exterior and label photos before opening
- power off; remove USB and TF card
- screw map
- photograph every layer before moving it
- photograph connector orientation before unplugging
- macro both sides of every PCB
- capture PCB names/revisions/dates, IC markings, flash/RAM/audio ICs, crystals, antenna/feed, connectors, and test-pad labels
- battery may be connectorized; unplug only if convenient and document orientation first
- no soldering, scraping, shield removal, chip removal, electrical test-pad probing, or powered exposed-board experiments on first opening

## 6. Divoom firmware/product-flag ecosystem

Community REvoom evidence explicitly lists **both product flags 60 and 42 as Ditoo-Plus confirmed**. The reason for duplicate/alternate flags remains unresolved.

Useful references:

- `https://divoom.2a03.party/pflags.html`
- `https://divoom.2a03.party/fw/versions.html`
- `https://divoom.2a03.party/api/app.html`

Divoom update API: older reconnaissance used the GET-style `app.divoom-gz.com` form. The current app-family flow verified on 2026-09-12 is JSON `POST` to `https://appin.divoom-gz.com/GetUpdateFileV2` / `GetUpdateFileV3` with fields `Hardware`, `IsTest`, `Language`, `UpdateFlag`, and `DeviceId`. The bounded flag42/60 production/test matrix is preserved at `artifacts/provenance/getupdatefile_v2_v3_matrix_2026-09-12.json`; it did not enumerate undocumented parameters or other product/update flags.

Firmware CDN: `https://f.divoom-gz.com/`

### Historical Ditoo Plus records not recovered

Flag 60 / v60010:

- filename `L1ghbmA929aEUhOCAAAAAD9iqis747.bin`
- SHA-1 `017a40dcef6018f34be0ec9b83003d71c67e4a58`
- discovered 2021-03-19
- historical CDN path now 404

Flag 42 / v42010:

- filename `eEwpPWA93ECEIZjCAAAAAAHJLNEc371.bin` is **NOT** the historical filename; see provenance for the correct record.
- correct historical filename: `eEwpPWA93ECEIZjCAAAAAArkYGQ617.bin`
- SHA-1 `7c352e6b8f62af8d0a2d51d824f75d1dafc18050`
- discovered 2021-03-19
- historical CDN path now 404

Authoritative historical metadata is in `artifacts/provenance/historical_ditoo_plus_firmware_metadata.json`.

## 7. Exact-model Ditoo Plus firmware — locally preserved

Four official exact-model-associated OTA branches are now permanently preserved in this repo: two production responses and two `IsTest=true` branches. These are lineage/recovery evidence, **not** exact installed-unit bytes; the purchased unit's v42012 remains unrecovered.

### Flag 60 — v60014

- file: `artifacts/firmware/flag60_v60014.bin`
- size: 1,207,165 bytes
- server SHA-1: `0d2b2ac511d233e769dbd31f3371dc52cc589e17`
- local SHA-256: `02efa679cf1c152d6e6cf57f43223153218b411f41a787b65978e5caa77c1300`
- changelog decodes to `Fix Bugs!`
- application build string: `Jul 09 2021 10:21:19`

The FCC engineering sample uses `v60001`, so the flag-60 lineage currently has the cleaner exact regulatory connection.

### Flag 42 — v42016

- file: `artifacts/firmware/flag42_v42016.bin`
- size: 1,207,313 bytes
- server SHA-1: `4371b90f4a0846fbb8dc26b77ad03695962f7ffb`
- local SHA-256: `f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a`
- changelog decodes to `1:Fix bugs!`
- application build string: `Oct 11 2022 10:00:57`

The exact meaning of flag 42 versus flag 60 remains unresolved.

### Official test branch — flag 42 API/container v42017

- file: `artifacts/firmware/flag42_v42017_test.bin`
- size: 1,207,333 bytes
- server SHA-1: `180c5636050b871f3014894d4cea98deb06ed1f3`
- local SHA-256: `6ac3513fc6659e57816b33382cb4ac265c7870de822171955cb2b366384dafcc`
- API and file-internal version both 42017
- server changelog decodes to `1: Format hot information.`
- research/reference only; never installed on the exact unit

### Official test branch — flag 60 API v60016 / container v60017

- file: `artifacts/firmware/flag60_api60016_internal60017_test.bin`
- size: 1,207,313 bytes
- server SHA-1: `27f55d533d009f622c9c1d1afe26b26a69017dc6`
- local SHA-256: `05e406f1196d7ea351d58d9dcf6a0f83f0244d0857bf0d27a396be58acbcd339`
- API metadata says 60016; valid downloaded update container internally says 60017; both values are preserved
- server changelog decodes to `Fix Bug!`
- research/reference only; never installed on the exact unit

The bounded official API response matrix and per-object provenance records live under `artifacts/provenance/`. `artifacts/analysis/test_branch_lineage.json` records the offline SPP/readback lineage audit.

## 8. Firmware structure — exact Ditoo Plus findings

Both current payloads contain:

- Divoom/Anyka OTA header with `AAAAAAAA` at file `+0x20`
- `SPIP` metadata at `+0x44`
- board/Bluetooth configuration slot at file `0x6000`
- application image beginning at file `0x7000`
- application header `PROGV1.0.0.8`
- product strings `Speaker` / `Blue`
- `ZZZZ` at application `+0x40`
- same-style six-entry stage-1 service/veneer ABI beginning at application `+0x44`
- partition/update names `BIOS1`, `PROG`, `BOARD`, `PROG1`, `BOAR1`
- source paths including `divoom_app_protocol.c`, `divoom_update_device.c`, and `divoom_product_test.c`

The flag-60 and flag-42 4 KiB config slots are byte-identical:

`d837ef626ef2dc09bc17f30230b2340abd1d52f5122272848913eaea8230f57d`

## 9. SoC identity

Both exact Ditoo Plus firmware branches contain adjacent literals:

- `Anyka`
- `1052D`

followed by Anyka/AkOS version material.

**MATCHED: Ditoo Plus uses the Anyka 1052D family.**

The specific suffix **AK1052DN048** remains unproven for the target until an exact chip marking is read from the purchased unit or sufficiently clear exact imagery.

## 10. OpenTivoo lineage comparison

Against the locally preserved, hash-verified Tivoo 31102 OTA:

- Ditoo Plus flag-60 first-stage region is ~54.12% byte-identical at the same offsets
- flag-42 first-stage is ~54.03% byte-identical at the same offsets
- Ditoo Plus/Tivoo 4 KiB config slots are **97.36% byte-identical at the same offsets**
- application bodies diverge heavily, as expected for distinct products

Classification:

- **MATCHED:** reusable Divoom/Anyka OTA framework and board-config architecture
- **RELATED / STRONG:** shared loader/service ABI lineage
- **NOT TRANSFERRED:** Tivoo USB VID/PID, MassBoot vendor commands, memory addresses, flash geometry, exact package suffix, or physical key sequences

## 11. Native update-container format

Both current exact Ditoo Plus binaries end with:

`<version:u32 little-endian> + "DIVOOMUPDATE" + <checksum:u32 little-endian>`

v60014:

- version word `0x0000EA6E` = 60014
- marker `DIVOOMUPDATE`
- checksum `0x06AB2798`

v42016:

- version word `0x0000A420` = 42016
- marker `DIVOOMUPDATE`
- checksum `0x06AB2183`

For both binaries, the stored checksum exactly equals the unsigned additive sum of every preceding byte.

This establishes a native version/marker/checksum container family. It does **not** prove cryptographic authenticity or safe cross-version flashing.

## 12. Local TF/SD update path

Exact Ditoo Plus firmware contains UTF-16 paths:

- `divoom/divoomupdate.bin`
- `divoom/alarm.bin`
- `divoom/movie.bin`
- `divoomtest.bin`

**MATCHED:** stock Ditoo Plus firmware contains a filesystem update path that looks for `divoom/divoomupdate.bin`.

This strongly corroborates a 2022 exact-model Reddit report in which Divoom support emailed an owner a file named `divoomupdate.bin` and instructed them to use an SD card. The user's update did not successfully trigger despite testing FAT32 cards and filename variants; their card/slot did work for normal music playback.

Source thread: `https://www.reddit.com/r/Divoom_Products/comments/xt9r45`

The support-issued file itself has not been recovered.

**Do not place a public OTA or guessed update image onto the purchased unit's TF card before static compatibility analysis.**

## 13. App-push firmware protocol

Exact firmware contains:

`SPP_APP_UPDATE_FILE_INFO: ver: %d, size: %d, sum: %d, flag: %d`

The exact Ditoo Plus handler was disassembled and parses:

- file type / flag
- firmware version
- file size
- additive checksum

The exact Ditoo Plus handler emits command **`0x98`**.

Therefore:

- **MATCHED:** `0x98` = firmware-info/update-info command for this generation
- a separately reverse-engineered modern Divoom app maps `0x99` to firmware chunks in 256-byte units
- **RELATED / STRONG:** `0x99` is probably the Ditoo Plus firmware-data command, but it still requires exact receive-dispatch confirmation before promotion

## 14. Bluetooth/control architecture

Exact manual identities:

- `Ditoo-Plus-audio`
- `Ditoo-Plus-light`

Independent Windows driver inventory tied `Ditoo-Plus-light` to a BLE (`BTHLE`) identity. Exact FCC evidence establishes Classic BDR/EDR. The exact firmware itself contains both BLE/GATT and Classic RFCOMM/SPP stacks.

Exact firmware BLE evidence includes:

- `divoom start ble!!!!!!!!!!!!!!`
- `ak_ble_set_adv_enable`
- `anyka_blue_ble_change_speed`
- GATT base/user-service registration
- BLE-name setup
- ANCS/CTS client code

Exact Classic/SPP evidence includes:

- `eBT_SERVICE_SPP`
- RFCOMM handling
- SPP initialization/connect/disconnect handlers
- `SYS SPP init!`
- `[SYS:SPP]check sum err`
- numerous `SPP_*` protocol identifiers

**MATCHED:** Ditoo Plus firmware is dual-stack BLE/GATT + Classic/RFCOMM/SPP.

Transport assignment for every app operation remains to be measured on the purchased unit.

### Important correction

BLE UUID **FD72 must not be attributed to Ditoo Plus**. It was traced to an unrelated Logitech device (`VID 046D`) in the Windows inventory. Exact proprietary Ditoo Plus GATT service/characteristic UUIDs remain unknown.

Generic RFCOMM driver entries from the same Windows host also must not be treated as exact Ditoo Plus evidence by themselves.

## 15. Factory test / MassBoot startup path

Exact Ditoo Plus firmware contains active startup diagnostics:

- `no get system key!`
- `check system gpio:`
- `check system ain:`
- `enter massboot!`
- `enter test mode!`

The exact Thumb routine was disassembled. It:

1. loads the self-describing `key` configuration block
2. evaluates configured GPIO and/or analog-input key conditions
3. chooses a test-mode or MassBoot path
4. calls a dedicated MassBoot-entry routine when the MassBoot condition succeeds

**MATCHED: a stock Ditoo Plus MassBoot entry path exists.**

The caller logic has two distinct mode checks:

- mode selector 0 → test mode
- later, after an additional hardware GPIO `0x1E` check, mode selector 1 → MassBoot

No Tivoo USB descriptors, VID/PID, commands, memory map, or physical key sequence are promoted from this.

### Analog-key configuration

The firmware describes a seven-position analog resistor-ladder keypad with seven calibrated ADC ranges.

Startup selectors use:

- Ditoo Plus key ID **1** for test mode
- Ditoo Plus key ID **3** for MassBoot

A current original-Ditoo firmware (flag 46 / v46032) was acquired as family calibration. Its analog ranges are the same but IDs are shifted by one. Its test selector uses ID 0; independent public documentation says original Ditoo factory test is entered by holding **M** while powering on.

Therefore:

- **RELATED / STRONG:** Ditoo Plus key ID 1 maps to the M key and Ditoo Plus test-mode selection is associated with M
- MassBoot's Ditoo Plus key ID 3 physical label is still unresolved
- the additional GPIO `0x1E` role is unresolved

Do not try a guessed MassBoot combination yet.

## 16. Original-Ditoo calibration artifact

Current Divoom product flag 46 yielded original-Ditoo firmware v46032:

- file `artifacts/reference/ditoo_flag46_v46032.bin`
- size 1,183,237 bytes
- SHA-1 `a1ca1ac25d63b9c6adb5258e32ab26fb8b779221`
- SHA-256 `a7ee309ef2d0c07f8a72abb9dd9bb444f33bd8f952ca9009c7b7f8e385d7e3d2`

This is **related-family calibration only**.

## 17. Android app archaeology

Package: **`com.divoom.Divoom`**.

Period versions identified through REvoom include:

- 3.0.55 — 2021-01-11
- 3.0.57 — 2021-01-16
- 3.1.02 — 2021-02-04
- 3.1.04 — 2021-03-02
- **3.1.08 — 2021-03-18**
- 3.1.10 — 2021-04-19
- 3.1.12 — 2021-05-21
- 3.1.26 — 2021-07-28
- 3.1.32 — 2021-08-10
- 3.1.40 — 2021-09-15
- 3.1.46 — 2021-10-21
- 3.1.52 — 2021-11-11
- 3.1.58 — 2021-11-17

Known REvoom SHA-1 values:

- 3.1.58 `ac5158aad4a88f56772c5180887697d5c5b9415c`
- 3.1.12 `5da0fd4bd41a2eb8b91ffd4f3056f92629902acf`
- 3.1.10 `d8ba2ca4a48a6ae006b79151c1c1d29acb721810`
- 3.1.08 `ecb991f2e4a99d7da6c304a3910bd67f3b182db9`
- 3.1.04 `975f9505a3e26f8b9606b4d139b4950a54fc7f91`

**3.1.08 remains an interesting older historical target** because it predates the historical 60010/42010 Ditoo Plus firmware discovery by one day, but it is no longer an active blocker.

A provenance-strong **3.1.58 APK is now preserved** at `artifacts/apps/divoom_android_3.1.58.apk`. Its SHA-1 `ac5158aad4a88f56772c5180887697d5c5b9415c` exactly matches the historical REvoom value already listed above, and its signer matches APKMirror's independently published Divoom certificate fingerprints. Offline decompilation proves the period app had separate hidden switches for test firmware (`SP_TEST_VERSION` → `IsTest`) and the test server (`SP_TEST_SERVER` → `apptest.divoom-gz.com`). The firmware request has no historical target-version field; `UpdateFlag` is constructor-fixed to 2 with no override caller in this client. A bounded current query of the legacy test host returned the same 42016/42017 and 60014/60016 objects as the modern service. See `artifacts/analysis/period_app_recovery_surface.json`.

Older APKMirror 2.67 metadata found:

- package `com.divoom.Divoom`
- version 2.67 (41)
- size 41,168,797 bytes
- APK SHA-1 `6d7cad613872936d02fb25884f878fafb867efd4`
- APK SHA-256 `84392a97f684397c249256a674098e8c7515ec268cb9fa56a635d9da8304ef41`
- signing-cert SHA-256 `b54bda23c5c9239bb80a0581220f2d46c3f59962c3ec52e692202e65b5ac0955`

Static APK search targets if acquired:

- `GetUpdateFileV3`
- `SppProc`
- `BluetoothGatt`
- product flags 42 and 60
- `Ditoo-Plus`
- `divoomupdate.bin`
- BLE service/characteristic UUIDs
- firmware transfer commands
- `com.divoom.DIVOOM.SP_TEST_VERSION`

## 18. Current community protocol lead

A 2026 community project, `github.com/nowheremanx/ditoo-claude-meter`, directly controls a **Ditoo Mic** from macOS/Python over Bluetooth.

Its author explicitly does not claim Ditoo Plus compatibility.

Classification: **LEAD ONLY**. It becomes useful as a comparator after the purchased Plus's exact GATT/SPP topology is captured.

## 19. USB status

No exact Ditoo Plus public evidence has yet established:

- DFU
- USB firmware update
- service/download VID:PID
- USB data mode
- exact MassBoot USB protocol

The exact manual presents USB-C as charging.

First physical USB step is passive enumeration only. No vendor requests until descriptors and mode behavior are independently captured.

## 20. Public factory-tool status

REvoom documents factory flashing kits for several other Divoom devices (including Tivoo/Timebox-family products), but no exact Ditoo Plus factory flash kit has been recovered.

Anyka BurnTool/USB tooling is **family/lead-only** until the Ditoo Plus's exact service mode and USB identity are established.

## 21. Human-gated / missing artifacts

Not currently possessed:

1. Ditoo Plus v60010 binary
2. Ditoo Plus v42010 binary
3. support-issued historical `divoomupdate.bin`
4. confidential FCC schematic/block-diagram/operational-description exhibits

Potential human routes:

- contact REvoom maintainer (`flewkey@2a03.party` / `#revoom` on Libera) asking whether historical update bytes were retained
- contact the 2022 Reddit Ditoo Plus owner for the original support attachment/instructions
- ask Divoom support specifically for Ditoo Plus manual/recovery `divoomupdate.bin`
- pursue an older provenance-trackable APK only if a specific new discriminator appears; 3.1.58 is already preserved and analyzed

Any recovered file must be hashed and preserved before use.

## 22. Less-exhausted public research branches

These remain worthwhile but lower priority than exact firmware/device work:

- Chinese/Japanese repair-board and replacement-PCB listings
- additional exact teardown/repair videos
- patents
- Bluetooth SIG / additional regional regulatory databases
- Wayback/archive mirrors for 60010/42010
- exact factory/test-mode documentation for Plus
- exact CHIPONE display-driver identification
- exact main SoC package suffix from high-resolution purchased-unit photography

A Bilibili Ditoo Plus tutorial was found but did not expose meaningful internal technical evidence.

## 23. First physical session plan

### A. Stock baseline

- photograph exterior and labels/FCC ID
- boot/shutdown normally
- record all menus/screens
- verify speaker/audio
- verify RGB keyboard
- verify TF media playback
- record app-reported device and firmware version
- determine whether reported firmware belongs to the 60xxx or 42xxx lineage

### B. Passive Bluetooth

- identify `Ditoo-Plus-light` and `Ditoo-Plus-audio`
- record advertisements, MACs, names, and service UUIDs
- read-only BLE GATT discovery
- Classic SDP/profile enumeration
- ordinary pairing only
- no arbitrary proprietary writes

### C. Passive USB

- ordinary powered-off/on USB-C connection as appropriate
- enumerate descriptors only
- record whether anything enumerates and under what stock state
- no vendor control commands

### D. Optional teardown after stock baseline

- rubber foot → one screw → clips
- photograph each layer
- macro all chips, PCB silk/revisions, connectors, test pads
- no electrical probing or soldering

### E. Later controlled captures

- Android HCI snoop during one known official-app action at a time
- begin with low-risk actions such as brightness/static image
- derive protocol from known stock behavior before generating arbitrary commands

## 24. Explicitly prohibited early actions

Do not initially:

- flash v60014/v42016
- place firmware/update files on TF card
- invoke guessed test/MassBoot sequences
- send arbitrary USB/vendor commands
- transmit unexplained BLE/SPP writes
- short/probe test pads electrically
- desolder or remove shields/chips

## 25. Artifact preservation / repository state

Durable local repository:

`/home/mcp/projects/projects/openditoo-research`

Preserved artifact categories:

- exact Ditoo Plus current firmware v60014 and v42016
- original-Ditoo v46032 calibration firmware
- Tivoo v31102 comparison firmware
- 10 public FCC Ditoo Plus exhibits
- live OTA request/response provenance
- historical 60010/42010 metadata
- SHA-1 and SHA-256 manifests

All four binary artifacts were re-hashed after OptiPlex persistence. The 10 FCC PDFs match the hashes reported by the FCCID.io mirror.

The artifacts are committed into local Git so deletion from a vendor/CDN does not remove the project's copy.

## 26. Ranked next work

1. **Resolve MassBoot key ID 3 to an exact physical key label.**
2. **Resolve the role of startup GPIO `0x1E`.**
3. **Pin the exact Ditoo Plus firmware-data command `0x99` from its receive dispatcher.**
4. Recover `divoomupdate.bin` and compare it byte-for-byte to the native OTA container family.
5. Recover 60010/42010 from archives or human sources.
6. Acquire/verify Divoom 3.1.08 only if historical app-side GATT/device-selection logic remains useful.
7. Continue exact-model PCB/component research.
8. On device arrival, execute the passive first-session plan before any service-mode experiment.

## 27. Source index

Primary public leads used during reconnaissance:

- exact FCC record: `https://fccid.io/A8I-DITOO-PLUS`
- REvoom product flags: `https://divoom.2a03.party/pflags.html`
- REvoom firmware history: `https://divoom.2a03.party/fw/versions.html`
- REvoom app/API notes: `https://divoom.2a03.party/api/app.html`
- REvoom app versions: `https://divoom.2a03.party/app/versions.html`
- original Ditoo family reference: `https://divoom.2a03.party/devices/ditoo.html`
- exact-model teardown: `https://kbdbuild.vercel.app/blog/divoom_ditoo_plus_chage_keyswitch`
- support `divoomupdate.bin` field report: `https://www.reddit.com/r/Divoom_Products/comments/xt9r45`

Raw mirrored evidence and hashes should outrank these links if upstream sources change.

## Bottom line

We have progressed well beyond generic reconnaissance. The project now has exact current firmware, a recovered native update-container format, an exact filesystem update path, exact dual BLE/SPP firmware support, independent Anyka 1052D identification, a statically confirmed MassBoot/test-mode selector, and a strong map of what must be measured on the purchased unit next.

The largest remaining unknowns are not whether a service/update framework exists—they are the **exact physical MassBoot trigger, exact GPIO role, exact data-command dispatch, exact purchased-unit firmware/hardware revision, and exact proprietary Bluetooth topology**.
