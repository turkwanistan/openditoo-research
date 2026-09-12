# OpenDitoo firmware/input-takeover plan — 2026-09-12

## Goal

Reach a preservation-first, no-solder firmware augmentation that can claim the Ditoo Plus front-panel controls **before stock side effects**, while retaining stock boot/display/audio/Bluetooth/SD/power behavior as the hardware abstraction layer. The desired steady state is a small fail-open OpenDitoo shim, not a whole-OS replacement.

This plan is intentionally separate from the live product runtime. **Runtime 018 remains the accepted everyday runtime and must not be modified in place.** Firmware research may inspect preserved binaries and produce offline artifacts, but any new physical experiment still needs its own reviewed manifest and exact named operator grant under `AGENTS.md`.

## Current route decision

**Primary delivery route: TF/SD updater (Route A).** This is now physically proven on the purchased v42012 unit using a checksum-poisoned official v42016 container. The exact path `/divoom/divoomupdate.bin` produced stock updater UI; the control filename did not; the poisoned file remained byte-identical; normal operation returned.

**Recovery track: MassBoot (Route B), renewed 2026-09-12.** The two consumed Lighting+USB trials tested the firmware **soft-handoff** path and produced no host-visible retail-USB enumeration; do not repeat cable/port swaps. New silicon + same-chip ROM evidence establishes a materially different reset-time route: AK1052D GPIO6 is the hardware boot-mode-select strap, while the Ditoo's preserved soft-handoff body bypasses reset and transfers through ROM vector `0x58`. Treat boot entry and USB wiring as separate questions. The detailed no-solder strategy is `notes/OPENDITOO-MASSBOOT-RENEWED-STRATEGY-2026-09-12.md`; first physical step, if pursued, is exact-unit passive board imaging under a fresh manifest/grant—not GPIO strapping.

**Factory/test mode: diagnostic aid, not a delivery route.** Holding M at boot enters the stock product-test environment. Passive stage 0 shows `42` over `012`, directly supporting product flag 42 / installed firmware v42012. Do not traverse factory stages blindly; map them statically first.

## Locked evidence

### Exact installed target

- Purchased unit: Ditoo Plus, product/update flag **42**.
- Installed firmware: **v42012**.
- Evidence now includes the prior stock protocol version query and the passive factory/test screen `42 / 012`.
- **The v42012 firmware binary itself is still not recovered.** This remains the main preservation/recovery blocker.

### Preserved exact-model firmware

- `artifacts/firmware/flag42_v42016.bin`
  - size 1,207,313 bytes
  - SHA-256 `f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a`
- `artifacts/firmware/flag60_v60014.bin`
  - exact Ditoo Plus alternate branch
  - used as an independent structural cross-check

### Physical-key map

The board config provides the calibrated analog ladder and the 8-entry software-event table:

| ID | physical control | short | long | repeat/third |
| ---: | --- | ---: | ---: | ---: |
| 0 | power/system path | `0x47` | `0x47` | `0x47` |
| 1 | M | `0x43` | `0xFF` | `0xFF` |
| 2 | + | `0x16` | `0x16` | `0xFF` |
| 3 | Lighting | `0x67` | `0x67` | `0xFF` |
| 4 | Left | `0x5F` | `0xFF` | `0xFF` |
| 5 | - | `0x0C` | `0x0C` | `0xFF` |
| 6 | Right | `0x60` | `0x60` | `0xFF` |
| 7 | Lever | `0x15` | `0x6B` | `0xFF` |

Power remains a separate lifecycle path. The takeover goal is the ordinary seven-control front panel, with power kept stock/recovery-safe.

### Keypad pipeline — PATCH-R0 hook foundation

For flag42 v42016:

`ADC -> 0x52844 decoder -> physical key ID -> 0x52926 translator -> 0x52656 translated-event emitter -> 0xC6D7C event queue -> stock consumers`

For flag60 v60014 the same functions are shifted by `-0x94`:

- emitter `0x525C2`
- ADC decoder `0x527B0`
- translator `0x52892`

Cross-branch identity after alignment:

- translated emitter: **48/48 bytes identical**
- ADC decoder: **134/134 bytes identical**
- translation mapper: **92/92 bytes identical**
- surrounding keypad module: **98.93% identical**
- relative deltas are stable: emitter→ADC `0x1EE`, ADC→translator `0xE2`

`scripts/locate_ditoo_keypad_pipeline.py` recognizes all three conserved bodies, validates their relative layout, and fails closed. It is recognition-only: it does not patch, recompute checksums, or emit a flashable image.

### Updater physical proof

`OPENDITOO-SD-P1-001` is consumed and PASS. The frozen probe SHA-256 was `acf0715fc98ecc1dd1abce483a0c68d8ca7b3bf98f676b03bdedacc72bc0ba43`; it differs from official v42016 only in the final stored-checksum byte and therefore fails the observed additive gate by construction. Exact-path boot showed updater UI; control filename did not; the probe remained byte-identical afterward.

### MassBoot/test selectors

- boot selector `[1,3,5]`: Lighting / key ID3 -> MassBoot under GPIO30/external-power condition
- boot selector `[1,1,5]`: M / key ID1 -> factory/test mode
- `0x1b8f4(mode)` performs the stable-key check
- strings include `enter massboot!` and `enter test mode!`

`OPENDITOO-MASSBOOT-ENUM-001` and `-002` are consumed. Both produced zero Windows USB/PnP delta. Treat retail USB service transport as **not demonstrated**.

## Safety invariants

1. Keep Runtime 018 and its standing product authority untouched during firmware R&D.
2. Never re-arm a consumed manifest.
3. No checksum-valid patched SD package goes onto the device until the recovery gate below is met.
4. No MassBoot vendor/SCSI/service commands without a fresh manifest and exact grant.
5. No blind factory-mode progression. Map a stage offline before a physical visit to that stage.
6. Power stays stock/fail-safe in early firmware work.
7. Prefer offline patched copies whose **stored updater checksum is intentionally invalid**, so development artifacts cannot accidentally pass the known updater gate.
8. Do not infer that an all-`0xFF` region is an executable code cave until image mapping and references prove it safe.

## Work plan

### FIRM-R0 — finish the low-level keypad/event model

**Objective:** turn the conserved keypad pipeline into a sufficiently annotated contract for a one-hook consume-or-forward shim.

Tasks:

- semantically annotate `0x52656` / flag60 counterpart instruction-by-instruction;
- characterize `0xC6D7C` category `0x82` queue semantics and the exact `(event, action/state)` payload;
- prove press/release/long/repeat behavior through the state machine around `0x525B0..0x529D4` rather than relying only on table bytes;
- identify every caller/driver callback that reaches the common emitter and explicitly note any bypass path;
- extend the locator with regression fixtures/tests for both preserved branches and fail-closed mutation cases;
- write a machine-readable analysis artifact with offsets, signatures, hashes and structural assertions.

**Exit:** one documented hook seam catches the desired seven controls before stock feature-specific side effects, with no unresolved bypass for the intended input classes.

**Status (2026-09-12, offline): DONE through R1.** Disassembly of both preserved branches
pinned the full event graph and corrected the seam: the emitter `0x52656` catches only
short/long *press*; auto-repeat + finalize bypass it and post directly. The producer-side single
fan-in is the **category-`0x82` queue post `0xc6d7c`** with exactly four `0x82` producers; the
adjacent `0x525a8` is separate class `0x81`. R1 also proved one consumer at fixed `0xbc34`,
with the only dequeue call at `0xbc6a`, category-`0x82` dispatch at `0xbc4c`, and a separate
`0x81 -> 0xbbac` path. Exhaustive direct queue-post xrefs are exactly those four `0x82` callers
plus the one `0x81` caller. `tools/keypad_pipeline_report.py` and its committed JSON assert the
producer and consumer seams on both preserved branches; `FirmwareKeypadPipelineTests` now has
7 tests. Full verifier discovers **345 tests** after R1 (the WSL sandbox has only the two known
missing-Pillow W9B errors; no firmware-R&D failure). A consume-or-forward shim may therefore
hook either the verified producer seam or the verified consumer seam, **not** the emitter alone.

### UPDATE-R0 — make the SD updater fully modelled offline

**Objective:** know exactly what an accepted update changes before supplying one.

Tasks:

- annotate `divoom_check_update` from open through marker/version/checksum acceptance and write dispatch;
- establish exact checksum coverage and trailer fields for both preserved branches;
- resolve version comparison/downgrade rules;
- identify flash regions/partitions written, erase granularity, completion/reset behavior, and file delete/rename behavior;
- locate failure paths for malformed/truncated/invalid-checksum packages;
- build an offline parser/validator that reports acceptance-relevant fields but never writes a device;
- create synthetic negative fixtures and prove they fail before the accepted write path.

**Exit:** updater validation and flash-write topology are documented strongly enough that a future patch package can be reviewed byte-for-byte before any live use.

**Status (2026-09-12, offline): validation fully modelled; write topology deferred.**
`divoom_check_update` disassembled (flag42 `0x8394`, link base `0x08400000`). Trailer =
`[u32 version][12 "DIVOOMUPDATE"][u32 checksum]` (last 20 bytes); checksum = `sum(file[:-4])
mod 2**32`, no signature. Gate order marker → version → checksum → writer `0x3a824`. Version
policy: reject if `installed >= candidate` unless header flag byte `0x33` forces. Delivered
`tools/ditoo_update_container.py` (read-only validator, `--selfcheck`) + `UpdateContainerTests`
(6, negative fixtures). Explains SD-P1: checksum-poison reached updater UI but failed the
checksum gate → no flash. Remaining: erase/partition/write topology inside `0x3a824` and the
reset/completion path.

### RECOVERY-R0 — close rollback/readback before persistent custom firmware

**Objective:** obtain a credible recovery path for the exact purchased unit.

Parallel avenues, ranked:

1. recover exact flag42 v42012 from archives, old support packages, caches, app artifacts, mirrors or owner/community copies;
2. find a stock software readback/export mechanism over already-proven Bluetooth/SD interfaces;
3. continue static MassBoot protocol analysis **offline**, but do not assume retail USB reaches it;
4. use FCC/internal-board evidence to determine whether a no-solder internal connector/test-pad route exists; teardown/photos are optional owner-assisted evidence, not a prerequisite for current offline work;
5. official v42016 is a known exact-model recovery target, but upgrading to it is **not equivalent to restoring the original v42012** and must be described that way.

**Recovery gate for first persistent patch:** either (a) exact v42012 restorable bytes + credible restore path, or (b) another owner-approved recovery strategy with a clearly documented loss-of-v42012 tradeoff. Until then, stay offline/non-flashable.

### FACTORY-R0 — statically map the stock product-test state machine

**Objective:** use factory mode as a safe diagnostic oracle without wandering through manufacturing operations.

Known:

- M-at-boot enters test mode;
- passive stage 0 displays `42 / 012`;
- firmware contains product-test SPI-flash, key, charge and SD routines plus voice/audio diagnostics;
- stage transitions exist in `divoom_disp_test` / `divoom_product_test` code.

Tasks:

- map stage index -> visible UI -> function -> advancement condition;
- classify each stage as passive/read-only, stateful but reversible, persistent-write/calibration, or unknown;
- identify the exact stage containing `divoom_product_test_key_update` and which action advances into/out of it;
- determine whether the key-test itself merely records input state or mutates persistent factory status;
- only after a stage is proven safe, prepare a fresh observation manifest if physical confirmation is useful.

**Exit:** a documented safe route to the built-in key test, or an explicit decision that it is not worth entering.

**R1 exit decision:** there is no proven read-only factory-entry route. Initialization itself
performs the destructive SPI check, so live factory re-entry is not worth pursuing under the
current plan.

### PATCH-R0 — build a non-flashable fail-open prototype patcher

**Objective:** prove the proposed control-flow modification offline without creating an accidentally installable custom image.

Design target:

- signature-locate the common translated-key emitter instead of hardcoding one build offset;
- preserve the original stock path byte-for-byte when OpenDitoo claim is inactive;
- add the smallest practical branch/trampoline to a separately verified executable location;
- maintain a short-lived claim/heartbeat state; expiry restores stock behavior automatically;
- early prototype may recognize only one key;
- first live-capable revision must **observe/report** that key while still forwarding its stock event; suppression comes only in a later revision.

Implementation rules for this phase:

- validate executable image mapping before selecting any `0xFF` cave;
- if a cave is unsafe/unnecessary, prefer a small in-place or existing-slack strategy;
- produce patched analysis copies with an intentionally invalid stored updater checksum by default;
- emit a deterministic diff manifest: changed offsets, before/after bytes, disassembly, untouched-region hashes, checksum state and locator evidence;
- add a verifier that refuses unknown firmware, ambiguous signatures, unexpected original bytes, overlapping edits, or a checksum-valid output in this phase.

**Exit:** two preserved exact-model branches can be located and either safely simulated/patched offline or rejected; stock-forward behavior is demonstrably preserved when claim is inactive.

**Status (2026-09-12, offline): DONE.** `tools/openditoo_patch_prototype.py` recognizes the
seam (fail-closed on unknown firmware), derives the branch shift, verifies original bytes at
all 4 category-0x82 producer sites, models the fail-open redirect to a caller-supplied
`shim_entry` (real Thumb-BL encoder), and emits research images that are non-installable by
construction (invalid stored checksum, proven rejected by the UPDATE-R0 validator) with a
changed-region diff + untouched-hash witness. Shim machine code and executable-cave placement
remain LIVE-gated and unauthored. `PatchPrototypeTests` (5); verifier 342 PASS.

### TELEMETRY-R0 — choose the least invasive observation channel

Before LIVE-0, decide how the first firmware shim proves a physical key was seen without suppressing stock behavior. Prefer reusing a stock, already-initialized device→host path rather than adding a large new stack.

Research candidates:

- existing Bluetooth SPP device→host send path / notification framing;
- an existing harmless diagnostic/status event that the host can distinguish;
- a minimal visible diagnostic only if it can be implemented more safely than outbound telemetry.

Do not expose a generic raw-memory API. The eventual public API should be typed/capability-scoped (`GET_VERSION`, `CLAIM_INPUTS`, `RELEASE_INPUTS`, `INPUT_EVENT`, frame/state primitives, heartbeat), with raw mutation unavailable by default.

### LIVE-0 — first persistent custom-firmware acceptance (future gate)

Only after FIRM-R0 + UPDATE-R0 + PATCH-R0 and the recovery gate:

- fresh reviewed manifest + exact owner grant;
- one checksum-valid package, one install attempt, stable power;
- one previously unavailable physical key is reported while its stock action remains intact;
- no exclusive claim/suppression yet;
- verify boot, Bluetooth, stock UI/action, OpenDitoo Runtime 018 compatibility, firmware identity, and rollback procedure;
- stop after the first unambiguous result.

A later LIVE-1 may consume one key under an expiring claim. Full seven-control takeover follows only after that works fail-open.

## Next work (R1) — ordered execution plan (2026-09-12)

After the FIRM/UPDATE/PATCH/FACTORY/TELEMETRY-R0 pass, this is the concrete, ordered plan for
the next session. Items N1–N4 are **offline** (no grant needed); N5–N6 are **live-gated** and
must not start without a fresh reviewed manifest and the owner's exact named grant. Do them in
this order; N1 and N2 can proceed in parallel. All offsets are flag42 v42016 file offsets, link
base `0x08400000` (code BL is PC-relative → read as base 0; absolute pointers use the real base).

### N1 — RECOVERY-R0: recover exact-flag42 v42010 (highest leverage; the binding blocker)

**R1 status: UNRESOLVED / environment-blocked.** CDX/timemap requests were attempted, but this
session's web URL-safety layer rejected the direct archive URLs before request execution and WSL
had a deterministic DNS outage. Do **not** record this as an archive-negative. REvoom still
confirms the v42010/v60010 filenames and SHA-1 values. Owner/community v42012 remains the
strongest recovery lead.

**Why first:** no persistent flash step is justifiable until a rollback exists. v42010 is
exact-flag42 (older than the unit's v42012 → a *downgrade*, updater-rejected without the `0x33`
force flag, and NOT the exact original) but is a genuine third cross-check point and a
tradeoff-documented recovery target.

Tasks:
- Retry from a non-rate-limited context (this session hit Wayback `429`). Use the CDX endpoint,
  not just the availability API:
  `http://web.archive.org/cdx/search/cdx?url=f.divoom-gz.com/group1/M00/B8/F6/eEwpPWA93ECEIZjCAAAAAArkYGQ617.bin&output=json`
  (and the flag60 v60010 object `.../B8/1A/L1ghbmA929aEUhOCAAAAAD9iqis747.bin`).
- If a snapshot exists, fetch `http://web.archive.org/web/<timestamp>id_/<url>` (the `id_` suffix
  returns the raw bytes, not the Wayback wrapper).
- Validate any recovered file with `python3 tools/ditoo_update_container.py <file> --installed 0`
  (expect marker OK + checksum OK; version should read 42010). Run
  `python3 tools/keypad_pipeline_report.py <file>` and `scripts/locate_ditoo_keypad_pipeline.py <file>`
  to confirm the conserved pipeline is present (extends the cross-branch evidence to a third
  point). If it locates, add its shift to `keypad_pipeline_report.REF` handling if needed.
- If recovered, store it under `artifacts/firmware/` **only with provenance** (add an
  `artifacts/provenance/…json` and a `SHA256SUMS` line, matching the existing convention). If
  NOT recoverable, record the negative and pursue owner/community v42012 copies.
- **Exit:** either a provenance-tracked exact-flag42 v42010 (or v42012) artifact + validator
  PASS, or a documented dead end that moves recovery to owner-assisted options.

### N2 — FACTORY-R0: classify `divoom_product_test_spiflash_check` (safety gate)

**R1 status: DONE — CONFIRMED PERSISTENT-WRITE, and more restrictive than expected.**
`0x16a40` erases/writes/reads/compares a 4 KiB sector beginning at
`ALARM.start_page + 0x2b00`; `divoom_product_test_init` invokes it unconditionally at `0x171ea`.
Factory entry itself is therefore not proven read-only. N5 is blocked.

**Why:** it is currently flagged conservatively as *potentially persistent-write*, which blocks
defining any safe factory-visit route. Settle read/verify vs erase/write.

Tasks:
- Locate the routine. Leads: the stage jump table at `0x16c52–0x16d06` dispatches stage ids via
  `0x2e522`; the function called at `0x16ce6` (`0x16b92`) and the disp/product-test setter
  `0x2e522` are entry points. The `spiflash error!`/`spiflash ok!` strings (`0x16e08`/`0x16e1c`)
  are ADR-referenced by the routine — disassemble the code immediately preceding them.
- Determine whether it calls `Fwl_spiflash_write`/`Fwl_spiflash_erases` (`0x1bf08`/`0x163ac`
  neighbourhood) and, if so, **on what address/region** — a dedicated scratch/test sector vs a
  live config/calibration region.
- **Exit:** the SPI-flash stage is reclassified read-only-safe OR confirmed persistent-write with
  the target region named. Update FACTORY-R0 in the handoff + research note. If safe, the
  documented factory route (stage 0 → M → key-test id 7) can be extended; if not, keep the
  "do not enter" boundary.

### N3 — FIRM-R0 tail: annotate the category-`0x82` consumer

**R1 status: DONE.** One consumer loop at fixed `0xbc34`; its dequeue call at `0xbc6a` is the
only xref to the queue dequeue. Category `0x82` dispatches at `0xbc4c`; `0x81` takes a separate
`0xbbac` path. Exhaustive queue-post xrefs are exactly the four `0x82` producers plus one `0x81`.
The report/artifact now assert this on both preserved branches.

**Why:** a consumer-side hook is an alternative *single* seam, and confirming it closes "no other
category carries a front-panel key".

Tasks:
- `queue_post 0xc6d7c` writes a ring at `&queue_struct+0x80` (head/tail u16 at `+0x80`/`+0x82`).
  Find the task that reads that ring and dispatches by category; identify where category `0x82`
  is consumed first.
- Confirm no producer other than the 4 already enumerated (`0x52680`, `0x52916`, `0x529aa`,
  `0x529ce`) posts `0x82` for a front-panel key, and that `0x81` (`0x525a8`) is not a key class.
- Add the consumer offset + assertion to `keypad_pipeline_report.py` / the artifact if useful.
- **Exit:** the consumer seam is documented as a viable single hook point (or ruled out), with no
  unresolved `0x82` producer.

### N4 — UPDATE-R0 deepen: disassemble the flash writer `0x3a824`

**R1 status: DONE.** Named targets are BIOS1/BOAR1/PROG1; page size 256 B; BIOS1 erase is
4 KiB, PROG1+BOAR1 erase is 64 KiB; page writes are 256 B; completion re-reads flash and
checks the additive checksum before the non-returning reset path. The read-only validator now
reports this topology.

**Why:** needed before any candidate patch package could be reviewed end-to-end (erase
granularity, partition map, reset/completion, failure ordering after the accept gate).

Tasks:
- Disassemble `0x3a824(mode=0, data_len, checksum, version)` and the chunked-write loop it
  drives; map erase granularity, write target region(s), and the reset/completion path.
- Extend `tools/ditoo_update_container.py` docstring/report with the write topology (still
  read-only; never emit a writable package).
- **Exit:** write topology documented strongly enough to review a patch byte-for-byte.

### N5 — (LIVE-GATED) factory key-test observation — BLOCKED BY N2

**Do not prepare a live manifest under the current evidence.** N2 proved that factory/product-test
initialization itself unconditionally performs a 4 KiB erase/write/read/compare before key-test
navigation. The key-test routine is read-only, but the route into that environment is not. A future
N5 would require a new method that demonstrably bypasses the destructive initializer, then a fresh
reviewed manifest and the owner's exact named grant.

### N6 — (LIVE-GATED) LIVE-0 first observe-only firmware revision — BLOCKED BY N1

N4 and PATCH-R0 are closed offline, but N1/recovery remains unmet. Only after a credible recovery
path exists may this return to consideration.
Per the LIVE-0 contract below: one checksum-valid package, one install, report one key over the
SYS SPP channel (TELEMETRY-R0) while forwarding its stock action; no suppression yet.

**R1 checkpoint:** N2–N4 are closed offline; N1 remains unresolved. N5 is blocked by destructive
factory initialization and N6 is blocked by recovery. No live manifest is prepared or authorized.

## Long-term architecture after the hook is proven

1. persistent OpenDitoo shim initializes during normal stock boot;
2. no claim/client -> near-stock device behavior;
3. host claim + heartbeat -> selected input events are emitted to OpenDitoo and consumed before stock handlers;
4. disconnect/crash/TTL expiry -> stock behavior immediately resumes;
5. stock display/audio/SD/Bluetooth/power routines remain the HAL;
6. later, a small sandboxed SD app runtime may host local apps (Slots, Pocket Moss, clocks/games) using bounded primitives rather than arbitrary ARM code.

## Explicit non-priorities

- More retail USB cable/port MassBoot enumeration repeats without new evidence.
- Replacing the whole stock OS/boot chain.
- Soldering/electrical interception.
- Arbitrary ARM app execution from SD before the input shim/recovery path is mature.
- Reworking Runtime 018 product pages as part of firmware research.
- Shipping a checksum-valid patched image merely because the additive checksum is understood.
