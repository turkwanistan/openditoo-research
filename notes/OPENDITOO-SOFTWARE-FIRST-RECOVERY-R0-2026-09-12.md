# OpenDitoo — software-first recovery R0 — 2026-09-12

## Decision

The owner does **not** want to perform the MassBoot M1 disassembly/photo session right now and prefers to avoid hardware work beyond ordinary disassembly if possible.

This does **not** invalidate or consume the prepared MassBoot R2/M1 experiment. `experiments/OPENDITOO-MASSBOOT-M1-PHOTOS-001.json` remains the exact future physical boundary and must stay `prepared_unauthorized`, `physical_execution_authorized=false`, `authorization_consumed=false` until the owner explicitly grants it.

For now, MassBoot M1 is **deferred, not abandoned**. Recovery work pivots to a software-first branch whose primary objective remains a provenance-tracked exact flag42 **v42012** recovery/restore path.

The already-proven SD updater is intentionally **parked**. Do not spend more time building a checksum-valid/patched updater image until exact recovery/rollback is materially solved.

## Software-first workstreams

1. **Stock-firmware readback/diagnostic audit** — exhaust the existing Ditoo Plus command surface and internal flash-read call topology for a stock readback/export path that would not require MassBoot or board access.
2. **Divoom software-ecosystem archaeology** — mine app command enums, update orchestration, old APK metadata, updater endpoints and historical/manual-recovery evidence for a readback or recoverable firmware source.
3. **Comparative firmware archaeology** — compare preserved Ditoo Plus flag42/flag60 and original-Ditoo firmware to distinguish stable shared protocol architecture from branch-specific features and to identify lineage changes worth chasing.
4. **External exact-v42012 acquisition** — keep as an opportunistic branch only. A third-party copy is useful only with strong provenance/hash evidence; do not make the plan depend on finding one.

Everything in R0 is offline/read-only. No device traffic, firmware mutation, generated installable image or physical action is authorized by this note.

## R0 result — stock SPP recovery surface

New deterministic analyzer:

- `tools/ditoo_software_recovery_surface.py`
- generated artifact: `artifacts/analysis/software_recovery_surface.json`
- regression coverage: `SoftwareRecoverySurfaceTests` in `tests/test_day1_offline.py`

The analyzer is recognition-only. It verifies known firmware SHA-256 values before interpretation, does not construct packets, does not access a device, and does not modify firmware.

### Exact Ditoo Plus dispatcher map

The preserved flag42 v42016 and flag60 v60014 images contain the same stock SPP command-dispatch architecture:

- accepted top-level command range: `0x04..0xFE` (251 table entries);
- jump-table read base: `0x105e8`;
- jump base: `0x105e4`;
- primary default/error handler: `0x126e4`;
- secondary default/error path: `0x126ec`.

For a command byte `cmd`, the verified table lookup is:

```text
idx = cmd - 4
rel = u16le(file[0x105e8 + 2*idx : +2])
target = 0x105e4 + 2*rel
```

Recovery-relevant exact targets are identical in both preserved Plus branches:

| command | handler | classification |
| --- | ---: | --- |
| `0x48` | `0x11144` | real handler |
| `0x49` | `0x11bb8` | real update-state/query-family handler |
| `0x93` | `0x126e4` | **default/error** |
| `0x94` | `0x126e4` | **default/error** |
| `0x95` | `0x126e4` | **default/error** |
| `0x96` | `0x126e4` | **default/error** |
| `0x97` | `0x110cc` | real file-version handler; already proven on exact unit |
| `0x98` | `0x1115a` | real inbound update-info handler |
| `0x99` | `0x1124c` | real inbound update-data handler |
| `0x9b` | `0x10e78` | real hot-content/update handler |
| `0x9d` | `0x10ea2` | real hot-update-info handler |
| `0x9e` | `0x10f52` | real hot-update-data handler |
| `0x9f` | `0x10f3c` | real hot-update pause/state handler |
| `0xbd` | `0x10a88` | real nested EXTERN mux |

### Important negative result: the tempting SYS-update commands are not implemented

Public Divoom app-family enums give `0x93..0x96` diagnostic-sounding names such as system/device update, update data, continue update and get update address. On the exact-model preserved Ditoo Plus firmware, **all four commands resolve to the generic default/error handler** in both flag42 v42016 and flag60 v60014.

Therefore those app enum names do **not** expose a hidden Ditoo Plus stock firmware-readback/update-address surface.

### `0x98/0x99` remain push-only update ingress

The exact firmware independently confirms:

- `0x98` parses update metadata (type/flag, version, size, additive checksum) and enters the stock update receiver;
- `0x99` is the associated inbound update-data path.

Nothing in R0 promotes either command to a flash export/readback mechanism. They remain part of the **host/app -> device** update path.

### EXTERN (`0xbd`) is narrow on Ditoo Plus

Both preserved Plus branches byte-verify the same first-level EXTERN sub-dispatch at `0x10a88`:

```text
sub = payload[1] - 0x13
if sub >= 9: default
else: jump table
```

Thus the exact preserved Plus firmware implements only nested subcommands `0x13..0x1b` through this mux. A wider command enum in an Android app does not imply those additional subcommands exist in the device firmware.

No implemented EXTERN path identified in R0 provides a raw flash/memory export primitive.

### Raw SPI-read primitive is real but not directly reachable from SPP handlers

The stock low-level `Fwl_spiflash_read` wrapper is present at:

- flag42 v42016: `0x1beaa`;
- flag60 v60014: `0x1beaa`;
- original Ditoo flag46 v46032: `0x1bfb8`.

Exhaustive halfword-aligned Thumb BL/BLX scanning finds exactly **63 direct callers** in each of those three firmware images.

Critically, there are **zero direct callers from inside the stock SPP dispatcher/handler region** in all three images.

This is stronger negative evidence than a string search: the normal Bluetooth command handlers do not directly invoke the raw SPI-read wrapper.

**Scope limit:** direct-edge absence alone does not prove there is no *indirect* SPP -> helper -> ... -> flash-read path. R0 therefore continued into a bounded shortest-chain audit rather than stopping here.

### Important refinement: stock SPP does indirectly trigger flash reads — through fixed typed storage selectors

The first reverse-reachability pass found real indirect paths. This is important: the correct statement is **not** “SPP never reads SPI flash.” Several ordinary stock commands eventually read internal flash-backed configuration/state.

The shortest exact chains have now been byte-pinned in `software_recovery_surface.json` on **both** preserved Ditoo Plus branches:

| command | verified shortest chain | fixed selector evidence | current classification |
| --- | --- | --- | --- |
| `0x80` | SPP -> `0x18604` -> `Fwl_spiflash_read` | immediate `r0=0, r1=0, r2=72` before helper | fixed internal config/storage read |
| `0x81` | SPP -> `0x18604` -> `Fwl_spiflash_read` | immediate `r0=0, r1=0, r2=72` before helper | fixed internal config/storage read |
| `0x27` read subcase | SPP -> `0x18b64` -> `Fwl_spiflash_read` | `payload[1]==0`, then fixed `r0=28, r1=0`; helper reads one byte | fixed config-byte read |
| `0xba` | SPP -> state helper -> `0x18604` -> SPI read | inner call fixed `r0=22, r1=0, r2=0` | fixed state/config record |
| `0x6e` | SPP -> same state helper -> `0x18604` -> SPI read | inner call fixed `r0=22, r1=0, r2=0` | fixed state/config record |

The branch-shifted state helper is `0x38f2c` on flag42 and `0x38e98` on flag60; the lower storage helpers remain fixed. The analyzer deliberately resolves those targets from actual BL encodings and fails closed on drift.

A broader one-helper scan also found many SPP-invoked settings/state helpers that call the common config-read routines with **immediate, fixed first-argument selectors** (examples include `0`, `2`, `10`, `15`, `17`, `18`, `19`, `22`, `23`, `28`, `29`, `31`, `32`). This is exactly what a mature typed settings protocol should look like. It is evidence **against** a trivially exposed caller-selected flash address, while confirming that flash access is present underneath the stock command layer.

This was the right lead for SFR-1: **data flow**, not merely call existence. SFR-1 has now completed the deeper semantic pass. The bounded result is `SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH`: the stock SPP paths examined do reach raw SPI reads, but none lets command-controlled bytes become an arbitrary flash address/range or arbitrary firmware export buffer.

## R0 result — comparative firmware archaeology

### Flag42 v42016 versus flag60 v60014

The two exact-model-associated branches are highly conserved specifically where a hidden diagnostic/readback path would be expected to live:

| region | byte identity |
| --- | ---: |
| SPP dispatch monolith `0x103e0..0x1271e` | **96.353%** (8693/9022) |
| SPP jump table `0x105e8..0x107de` | **98.606%** (495/502) |
| EXTERN mux `0x10a88..0x10d6c` | **98.378%** |
| hot-update cluster `0x10e78..0x11020` | **98.349%** |
| app-update cluster `0x110cc..0x11278` | **96.028%** |
| SPI wrapper region `0x1be82..0x1bf00` | **96.032%** |

Of all 251 top-level SPP commands, **244/251 have the exact same handler target** in flag42 and flag60. The seven differences are small local handler relocations (`0x1b`, `0x51..0x54`, `0xb6`, `0xb7`); the recovery/update cluster above is unchanged.

### Original Ditoo flag46 v46032 comparison

The original-Ditoo reference firmware carries the same mature dispatcher architecture, shifted slightly in the image:

- table read base `0x105c8`;
- jump base `0x105c4`;
- primary default handler `0x12690`.

Classification comparison against flag42 Plus across all 251 command slots:

- **107 commands** are default in both;
- **143 commands** are real handlers in both;
- **one command (`0x23`)** is real in Plus but default in original Ditoo;
- **zero commands** are real in original Ditoo but default in Plus.

The complete recovery/update cluster (`0x48`, `0x49`, `0x93..0x99`, `0x9b..0x9f`) is structurally conserved after relocation.

The Plus-only `0x23` handler was inspected separately: it accepts a small enumerated payload and forwards a one-byte mode/value through an existing helper. It has no direct raw-SPI-read edge and is not promoted as a recovery/readback lead.

**Interpretation:** the stock Divoom SPP command surface is a mature, strongly conserved application protocol. A large hidden Plus-only firmware-dump namespace is now materially less likely. This remains comparative evidence, not proof about every byte of the unrecovered installed v42012 image.

## R0 result — Divoom software ecosystem

### Update service/API

Public REvoom documentation and current community reverse engineering identify the Divoom update-service family around `GetUpdateFileV2`/`GetUpdateFileV3`. Modern app archaeology additionally identified the current service as JSON `POST` requests to `https://appin.divoom-gz.com/GetUpdateFileV2` / `GetUpdateFileV3`. The service remains latest-by-product-flag rather than a discovered historical-version catalogue.

Public/community references used in this pass:

- `https://divoom.2a03.party/api/app.html`
- `https://divoom.2a03.party/fw/versions.html`
- `https://tangled.org/antiali.as/minitoo-forth`

A recent MiniToo community reverse-engineering project independently mapped modern Divoom app update orchestration and command enums. It is **family/app evidence only** because MiniToo uses different device silicon; exact Ditoo Plus firmware bytes remain authoritative. Useful cross-checks from that work include the same `0x98/0x99` app-update pairing and a narrow implemented EXTERN subset on their device.

On 2026-09-12, SFR-3 executed exactly the bounded 2×2×2 matrix already planned: endpoint V2/V3 × `Hardware=42/60` × `IsTest=false/true`, with `UpdateFlag=2`, language `en`, and a zero DeviceId. No product-flag, update-flag or undocumented-parameter enumeration was performed. The complete immutable response record is `artifacts/provenance/getupdatefile_v2_v3_matrix_2026-09-12.json`.

Results:

- V2 and V3 returned identical JSON objects for every one of the four Hardware/IsTest pairs.
- flag42 production remained **v42016**; `IsTest=true` exposed official **v42017**, SHA-1 `180c5636050b871f3014894d4cea98deb06ed1f3`.
- flag60 production remained **v60014**; `IsTest=true` API metadata exposed **v60016**, SHA-1 `27f55d533d009f622c9c1d1afe26b26a69017dc6`.
- The exact two test-branch CDN objects were downloaded for offline analysis only and verified against those server SHA-1s. Both are valid Divoom update containers. flag42's container also declares 42017. The flag60 object has a vendor metadata inconsistency: the API declares **60016** while the valid downloaded container internally declares **60017**. Both values are preserved; neither is silently normalized.
- No historical-version selector or exact-v42012 source was revealed by this bounded matrix.

Provenance is preserved in `artifacts/provenance/ota_flag42_v42017_test.json` and `artifacts/provenance/ota_flag60_test_api60016_internal60017.json`. These are research/reference artifacts only; no test firmware was sent to or installed on the Ditoo.

### Historical app archaeology

Period Divoom Android application versions remain useful because they can reveal:

- command enum history;
- hidden/test updater endpoint choices;
- old `IsTest`/`UpdateFlag` behavior;
- package/file naming conventions;
- historical CDN identifiers that no longer appear in current responses.

A period-relevant APKMirror record for Divoom Smart 2.67 (uploaded 2021-12-20, package `com.divoom.Divoom`) still exposes metadata/hash information, but the binary is no longer downloadable there at the developer's request. Third-party historical indexes independently list `com.divoom.Divoom` 3.1.58 (39.51 MB), 3.1.80 (42.35 MB) and 3.1.86 (42.65 MB). A separate CertFA analysis record corroborates the 3.1.86 package/version and checksum-like identifier `f1960db9b13363aa1a1d8f4ac9f2c1a5`. The indexed 3.1.58 APK CDN returned HTTP 403 during this pass, so **no period APK binary was acquired** and none of those third-party binaries are treated as trusted evidence yet.

Useful public indexes for provenance hunting only:

- `https://www.aiting.com/divoom-pixel-art-editor/com.divoom.Divoom/download/3.1.58`
- `https://www.aiting.com/divoom-pixel-art-editor/com.divoom.Divoom/download/3.1.80`
- `https://www.aiting.com/divoom-pixel-art-editor/com.divoom.Divoom/download/3.1.86`
- `https://certfa.com/lab/android-app/sha1/38c84f27a44e810bd081834da7b49570fb091490/`

Acquiring a provenance-trackable period APK remains worthwhile, but not as a blocker. Internet Archive/GitHub searches for the known flag42 v42010 filename and these old APK versions produced no useful archived binary in this pass.

### Historical firmware evidence

REvoom still preserves metadata for flag42 v42010:

- filename `eEwpPWA93ECEIZjCAAAAAArkYGQ617.bin`;
- SHA-1 `7c352e6b8f62af8d0a2d51d824f75d1dafc18050`;
- discovered 2021-03-19.

No reliable v42012 binary or hash was found in this pass. The known historical v42010 CDN object was already known to be gone from the live path. Failure to find v42012 publicly is **not** proof it was never distributed or archived.

The 2022 Ditoo Plus support report in which Divoom supplied an SD-card `divoomupdate.bin` remains useful evidence that support had manual recovery packages, but the attachment itself has not been recovered.

## What R0 changes

1. **Do not chase `0x93..0x96`.** Exact Plus firmware proves those app-family enum slots are default/error handlers.
2. **Do not treat `0x98/0x99` as backup commands.** They are update ingress.
3. **Do not assume a broad hidden EXTERN namespace.** Exact Plus firmware bounds the first-level mux to `0x13..0x1b`.
4. Stock SPP **does** indirectly read internal SPI flash for ordinary typed configuration/state operations, but SFR-1 now closes the deeper bounded data-flow question as `SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH`. The five analyzed direct raw-read caller families are config initialization, config-record read, config-byte read, a one-byte header parser, and screen-save/content scanning. The only raw-address-shaped helper is the one-byte parser; across both preserved Plus branches, every analyzed SPP provenance path feeds it a firmware-managed config/resource address rather than caller-supplied address bytes.
5. Comparative archaeology remains valuable: it can prove whether a lead is stable platform architecture or a branch-specific addition before any live experiment is considered.
6. External v42012 acquisition remains useful but low-confidence/opportunistic, matching the owner's concern about reliability.
7. **SD updater development stays parked** until recovery/rollback is solved.
8. **M1 stays deferred and unauthorized**; no hardware work is required by the immediate software-first queue.

## Next software-only queue

### SFR-1 — transitive readback reachability — CLOSED (2026-09-12, offline)

**Result:** `SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH`.

A Capstone-assisted disposable-Lab pass was used to map candidate call/control-flow, then every promoted semantic claim was re-expressed as fail-closed byte/BL invariants in `tools/ditoo_software_recovery_surface.py` and verified independently on both preserved Plus branches. The repository does **not** depend on Capstone/angr to reproduce the accepted assertions.

The direct raw-SPI-read callers reached by the analyzed stock-SPP graph reduce to five semantic families:

| family | flag42 | flag60 | raw-read semantics | caller control verdict |
| --- | ---: | ---: | --- | --- |
| config initializer | `0x184e8` | `0x184e8` | scans internal config-area metadata one byte at a time | no caller address |
| config-record reader | `0x18604` | `0x18604` | internal config base + validated record offset/length | typed record selector/key, not raw address |
| config-byte reader | `0x18b64` | `0x18b64` | one byte at internal config cursor/base | typed record matching, not raw address |
| one-byte raw-header parser | `0x3c12c` | `0x3c098` | **function argument is used as raw read address**, fixed length 1 | all analyzed SPP provenance paths supply managed internal addresses |
| screen-save/content scanner | `0x38b26` | `0x38a92` | object base `+0x0c` + bounded internal loop index, length 1 | managed content-area metadata |

The one-byte parser was the strongest remaining arbitrary-read candidate. Its three analyzed SPP address-provenance families close as follows on **both** Plus branches:

1. `0x2393a` obtains the address through config helpers that select fixed records `10/11` or `13/14`; `0x189a4` returns `internal config base + parsed record offset`. The packet may select a typed record/key, but not a raw flash address.
2. `0x2877a` / `0x287a0` loads the parser address from an internal resource context. Its initializer resolves the resource base through `0x34382` / `0x342ee` and can only choose that base or **base + `0x100`** through a boolean alternate-bank branch.
3. `0x32a22` / `0x32a7a` reloads an internal context address that was initialized by `0x3295c` / `0x329b4` from the same resource resolver **plus exactly `0x100`**.

This means the firmware contains raw flash-read primitives underneath SPP-visible operations, but the analyzed stock remote surface does not promote them into a generic read/dump/export mechanism. `0x17718` remains a separate record-stream routine that performs both reads **and writes** and is therefore not a safe live readback candidate.

**Explicit limits:** this is bounded static direct-call/control-flow analysis, not a whole-program formal proof. The monolithic SPP dispatcher makes naive per-command reachability counts over-approximate, so no exact count of remotely reachable read cases is claimed. Computed internal jump tables/callbacks are not globally proven absent; the top-level EXTERN mux is independently byte-pinned to `0x13..0x1b`. No live packet probing was used for SFR-1.

The machine-checkable artifact is `artifacts/analysis/software_recovery_surface.json` schema v3. If any pinned address/provenance instruction changes in a future firmware branch, the analyzer fails closed rather than carrying this conclusion forward.

### SFR-2 — period app acquisition and updater-diff archaeology

**Offline/public research.**

Prioritize a provenance-trackable Divoom `com.divoom.Divoom` APK from the 2021–2022 era (especially 3.1.x or the known 2.67 build if another trustworthy mirror exists). Preserve hash first, then compare:

- updater endpoint host/path;
- `GetUpdateFileV2/V3` request schema;
- `IsTest`/`UpdateFlag` behavior;
- product-flag/version lookup logic;
- `SppProc`/command enum changes;
- hard-coded CDN or filename history;
- any support/recovery-specific code path distinct from normal OTA.

Do not download random unverified APKs merely to increase source count.

### SFR-3 — bounded current update-API matrix — CLOSED (2026-09-12, read-only public network)

The exact planned eight requests were captured in `artifacts/provenance/getupdatefile_v2_v3_matrix_2026-09-12.json`; no broader enumeration occurred. V2 and V3 were identical across the matrix. `IsTest=true` was materially useful and returned distinct official test branches for both Ditoo Plus flags. It did **not** expose a historical selector or v42012.

This closes the bounded current-API question while adding two high-value lineage artifacts rather than a recovery image.

### SFR-4 — lineage expansion — FIRST EXPANSION COMPLETE (2026-09-12, offline)

The newly recovered official test branches were ingested immutably and audited by `tools/ditoo_test_branch_lineage.py`; the committed report is `artifacts/analysis/test_branch_lineage.json`.

Key results:

- flag42 v42017 has **251/251 identical top-level SPP handler targets** versus production v42016. `0x93..0x96` remain default/error and the recovery/update cluster is unchanged.
- flag42 v42017 is nevertheless an adversarial implementation cross-check rather than a trivial relocation: its config/storage internals are materially refactored. The fail-closed analysis still reduces stock-SPP raw-read reachability to the same five semantic families, and the refactored one-byte raw-address parser is fed only fixed/config-managed/resource-managed addresses on the analyzed paths. SFR-1 therefore survives this independent implementation change.
- the flag60 test object also has 63 direct raw-read callers, zero direct SPP→raw-read edges, and satisfies the accepted SFR-1 byte/data-flow invariants.
- flag42 v42017 and the flag60 test object have **251/251 identical top-level SPP dispatch targets**, further supporting a stable typed product protocol rather than a hidden branch-specific dump namespace.

Result remains `SPP_READBACK_NO_CALLER_CONTROLLED_CHAIN_WITHIN_ANALYZED_GRAPH`, with the same explicit bounded-static-analysis limits. Future newly recovered flag42/flag60 images should still be ingested and checked, especially anything at or below v42012.

## Stop / hardware flip condition

Software-first work should continue while it is producing new discriminating evidence. Do not declare exact v42012 externally recoverable merely because nearby firmware exists. SFR-1, SFR-3 and the first SFR-4 lineage expansion are now closed; the main remaining software discriminator is SFR-2 period-app/support-updater archaeology plus opportunistic provenance-trackable v42012 acquisition.

If all of the following become true:

1. SFR-1 remains closed without a reachable stock readback chain after the new lineage checks;
2. period app/support-updater archaeology yields no historical-v42012 source or recovery endpoint;
3. no provenance-trackable v42012 image emerges;

then the software-only route has reached a meaningful evidence-backed blocker. At that point, present the owner with the choice rather than silently escalating: keep the project recovery-gated, or return to the already-prepared **photos-only M1** disassembly session to determine whether MassBoot/SPI offers a simple no-solder route.

No electrical probing is implied by that choice.
## Verification checkpoint

R0 was verified in the authoritative WSL_MCP checkout after the software-first pivot:

- `python3 tools/ditoo_software_recovery_surface.py --selfcheck` — **PASS**;
- `python3 tools/ditoo_test_branch_lineage.py --selfcheck` — **PASS**;
- `SoftwareRecoverySurfaceTests` + `OfficialTestBranchLineageTests` — **12/12 PASS**;
- `python3 scripts/verify_day1_offline.py` — **357 tests**, exactly **2 errors**, both the pre-existing unrelated W9B optical tests caused by missing `PIL`; **zero software-recovery / firmware-R&D test failures**;
- `git diff --check` — **PASS**;
- M1 manifest authority remains unchanged: `status=prepared_unauthorized`, `physical_execution_authorized=false`, `authorization_consumed=false`.

No device I/O, physical action, updater image generation or Runtime 018/product modification occurred in this phase.

