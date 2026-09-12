# OpenDitoo MassBoot R2 execution plan — 2026-09-12

## Mission

Turn MassBoot from a promising family-level recovery hypothesis into a **measured, exact-unit recovery/readback path** for the owner's Ditoo Plus, without using soldering and without risking persistent device mutation during discovery.

The strategic payoff is **exact v42012 acquisition and a credible rollback path**. Custom execution/input takeover is intentionally downstream. Once exact v42012 is recoverable, the already-proven TF/SD updater remains the leading persistent delivery mechanism for the eventual fail-open input shim.

This plan operationalizes `notes/OPENDITOO-MASSBOOT-RENEWED-STRATEGY-2026-09-12.md`. That strategy note contains the research/evidence synthesis; this file is the execution contract.

## Current state and key correction

Two distinct MassBoot entry routes must never be conflated:

- **MB-S — software handoff:** stock Ditoo firmware sees external-power/GPIO30 + Lighting, enters resident stage1 cleanup, then transfers through low-ROM vector `0x58` into MassBoot. The exact purchased v42012 unit already showed altered boot behavior under this condition, but two bounded retail-USB enumeration trials produced no Windows USB/PnP identity.
- **MB-H — hardware bootstrap:** AK1052D reset-time boot selection through GPIO6. This path does not first boot stock Ditoo firmware and has **not** been exercised on the Ditoo.

Offline comparison strengthens MB-S substantially: preserved Ditoo flag42 v42016 and flag60 v60014 contain the same 134-byte handoff body at file `0x2968:0x29ee`; compared with the physically recovered OpenTivoo AK1052D stage1 MassBoot body, 109/134 bytes match and all 25 differences fall inside relocated Thumb `BL` displacement encodings. Non-call instruction bytes match.

The unresolved problem is therefore a conjunction of three independent questions:

1. **entry:** is ROM MassBoot actually running under MB-S and/or MB-H on the exact Ditoo?
2. **routing:** where do AK1052D USB D-/D+, GPIO6/UART0_TXD, GPIO7/UART0_RXD and RESET physically terminate on this exact board?
3. **protocol:** once a transport is reachable, what read-only subset is actually supported by this Ditoo ROM?

Do not use another cable/button-combo trial as a substitute for answering these separately.

## Evidence hierarchy

1. exact-unit photos, passive electrical measurements, USB descriptors/captures and read-only bytes;
2. exact purchased-unit v42012 behavior;
3. preserved exact-model flag42/flag60 firmware;
4. AK1052D silicon documentation;
5. physically measured OpenTivoo AK1052D ROM/stage1 as same-silicon comparative prior art;
6. FCC/reference boards and community material;
7. inference/plans/chat history.

Never promote a lower tier into exact-unit fact without measurement.

## Authority boundary

Offline static analysis, repo tooling, image annotation and manifest preparation may proceed autonomously.

Every physical step requires its own reviewed manifest and the owner's exact named grant before execution. This includes disassembly/photo capture, powered observation, continuity measurements, UART attachment, GPIO bootstrap, USB enumeration, MassBoot command transmission or flash readback. A consumed manifest is never re-armed.

Until M6 recovery is complete:

- no checksum-valid custom firmware;
- no flash erase/program;
- no MassBoot POKE/DOWNLOAD/GOTO merely to prove they exist;
- no unbounded command enumeration;
- no blind grounding/strapping of unidentified pads;
- no direct QFN-leg probing when an accessible pad/via/component endpoint can be used;
- no factory/test-mode entry (its initializer is now known to erase/write a 4 KiB sector);
- no change to Runtime 018/hash-bound everyday product files.

## Phase R2-0 — offline closure and operator package

**Purpose:** make the first exact-unit session high-yield and single-disassembly if possible.

### Tasks

1. Freeze a compact signal dossier for the AK1052D targets:
   - pin 3: active-low RESET;
   - pin 22: USB_DM;
   - pin 23: USB_DP;
   - pin 32: GPIO6 / UART0_TXD / reset-time boot-mode select;
   - pin 33: GPIO7 / UART0_RXD.
2. Preserve the MB-S vs MB-H distinction and the Ditoo↔Tivoo handoff identity result.
3. Search offline/current artifacts for any board silkscreen, flash-package, test-pad or connector clues already available; treat FCC photos as orientation only.
4. Keep a parallel public-source search open for the AK1052D Programmer's Guide / official burning or mass-production tool documentation, but do not block exact-board work on it.
5. Prepare the photo-only manifest `OPENDITOO-MASSBOOT-M1-PHOTOS-001` and validate that it authorizes **no powered/electrical/device-boot operation**.
6. Prepare the exact photo checklist below so the owner should not need a second disassembly merely because a useful angle was omitted.

### Exit

- reviewed M1 manifest exists, unauthorized;
- photo checklist frozen;
- current verifier baseline recorded;
- no device I/O performed.

**Handoff status:** DONE. M1 manifest/checklist are prepared; focused firmware checks pass; the full 345-test verifier reproduces only the two known missing-Pillow W9B environment errors. No physical action occurred.

## Phase R2-1 / M1 — exact-unit passive board imaging

**Manifest:** `experiments/OPENDITOO-MASSBOOT-M1-PHOTOS-001.json`  
**Grant required:** `Grant OPENDITOO-MASSBOOT-M1-PHOTOS-001`

This phase is mechanical/photo evidence only. No continuity test, powered probing, USB attachment, button-at-boot experiment, strap or device command is included.

### Pre-session conditions

- power the Ditoo fully off;
- disconnect USB/charger;
- remove microSD if present;
- do not intentionally power or boot the device while open;
- use ordinary nonconductive handling and avoid tools contacting multiple board points at once.

Battery disconnection is desirable if it is accessible through a normal connector without destructive disassembly, but the manifest does not authorize cutting/desoldering or forcing a glued/welded battery connection. If battery isolation is unclear, stop after photos rather than improvising.

### Required image set

Capture original full-resolution files; do not crop/delete originals.

1. **Exterior/reference**
   - front/rear/unit identity orientation;
   - connector side showing USB-C and microSD relationship.
2. **Main PCB, face A**
   - straight-on full-board overview;
   - second overview with a ruler/known scale if practical;
   - oblique left/right views for via/pad trace visibility.
3. **Main PCB, face B**
   - same overview + obliques.
4. **AK1052D macro**
   - marking fully legible;
   - package edges and pin-1 marker visible;
   - enough surrounding board to orient pins 3/22/23/32/33.
5. **USB-C region macro**
   - receptacle pins/anchor area as visible;
   - every nearby resistor/ESD/USB component, via and test pad;
   - both PCB faces corresponding to this region.
6. **SPI NOR macro**
   - full marking and package type;
   - nearby passives/test pads;
   - enough room to see whether a no-solder clip is mechanically possible.
7. **All test pads / unpopulated headers**
   - grouped straight-on macros with board orientation retained;
   - any labels such as TX/RX/USB/DP/DM/RST/GND/3V3/CLK/DAT or factory numbering.
8. **Power/battery region**
   - battery connector/wires and charge/power components;
   - where USB VBUS enters the board.
9. **Board identity**
   - all revision/date/lot/silkscreen/QR/barcode markings.
10. **Inter-board wiring**
    - every board-to-board flex/wire/connector before disconnecting anything that is removable.

Take extra images rather than relying on digital zoom. Keep focus on copper/vias/pad geometry, not just chip labels.

### Analysis deliverables after upload

The next session should ingest the images and create an exact-unit board map containing:

- board revision/variant evidence;
- SoC orientation and candidate pin geometry;
- USB-C D-/D+ candidate route(s);
- candidate GPIO6/UART0_TXD, GPIO7/UART0_RXD and RESET accessible endpoints;
- GND and likely 3.3-V reference points;
- SPI NOR identity/package and clip accessibility;
- candidate factory pad clusters with confidence labels;
- a list of measurements that would discriminate competing mappings.

Every candidate must be tagged **photo-proven**, **geometry inference**, or **unknown**. Do not label a pad `TX`, `DP`, etc. merely because it resembles a factory pad.

### Exit / decision

M1 succeeds when the images are sufficient to draft an **unpowered M2 continuity map** without touching QFN legs directly. If not, request only the missing image/angle; do not jump to powered probing.

## Phase R2-2 / M2 — unpowered continuity and passive resistance map

**Not authorized by M1. Requires a fresh manifest/grant.**

### Purpose

Settle the board-routing question before another MassBoot entry experiment.

### Preconditions

- exact-unit M1 board map complete;
- battery isolated if practical and safe;
- USB/charger absent;
- target pads/components identified by geometry with explicit alternatives;
- meter method chosen to avoid sourcing unsafe voltage/current.

### Measurements

1. Map USB-C D-/D+ from a known Type-C breakout/cable to board-side endpoints.
2. Determine whether those nets continue toward AK1052D pins 22/23, stop at unpopulated components, or terminate at internal test pads.
3. Map candidate GPIO6/pin32 and GPIO7/pin33 to accessible pad/via/component endpoints.
4. Map candidate RESET/pin3 endpoint.
5. Identify GND and 3.3-V rail references independently.
6. Before ever applying a boot strap, record passive resistance from the GPIO6 candidate to GND and 3.3 V so an external pull can be designed without hard-shorting a driven/shared net.
7. If SPI NOR clip fallback is attractive, map supply/hold/wp topology sufficiently to reason about back-power/bus contention before attaching a programmer.

### Decision outputs

- **External D+/D- confirmed to SoC network:** MB-H can later be tested through external USB-C.
- **D+/D- only accessible internally:** design a temporary no-solder pogo/test-hook USB fixture.
- **USB inaccessible but UART pads accessible:** prioritize UART liveness and use SPI clip/JTAG only as fallback.
- **No trustworthy no-solder access:** stop MassBoot physical work and compare direct SPI-NOR recovery effort instead.

## Phase R2-3 / M3 — RX-only UART liveness

**Fresh manifest/grant required.**

### Purpose

Answer “is ROM MassBoot actually alive?” independently of USB routing.

### Shape

- 3.3-V high-impedance UART receiver;
- device TX -> adapter RX plus common GND only;
- adapter TX remains disconnected;
- capture raw serial across a small, pre-declared baud set only if baud is not already established offline;
- no bytes sent to Ditoo.

### A/B

1. Observe one already-known MB-S Lighting handoff while listening.
2. After M2 proves a safe strap topology, observe one MB-H reset-time bootstrap while listening.

Same-silicon OpenTivoo ROM prints `SnowbirdT2_MassBoot>#`; an exact matching banner would be very strong evidence, but absence is not proof MassBoot is absent unless UART routing/baud/output are independently established.

### Exit

Classify MB-S and MB-H liveness separately: ROM-positive / transport-silent / unresolved.

## Phase R2-4 / M4 — hardware-bootstrap USB enumeration only

**Fresh manifest/grant required.**

### Preconditions

- GPIO6 endpoint measured;
- safe temporary pull/strap topology reviewed;
- RESET/cold-start sequence explicit;
- USB route measured;
- no need to touch QFN legs directly.

### Operation

Apply only the reviewed temporary GPIO6 alternate state across a true reset/cold bootstrap, then release/tri-state after the sample point. Capture standard USB enumeration/descriptors only. No custom/vendor/SCSI commands.

### Interpretations

- **enumerates:** freeze exact descriptors/endpoints; do not immediately reuse Tivoo commands.
- **UART MassBoot-positive, USB absent:** entry solved; troubleshoot board USB routing/PHY rather than buttons.
- **internal pads enumerate, external Type-C does not:** factory service transport is physically internal; keep the no-solder fixture.
- **neither UART nor USB:** stop and revisit exact strap/reset mapping offline.

## Phase R2-5 / M5 — read-only protocol calibration

**Fresh manifest(s)/grant(s), one semantic step at a time.**

Order:

1. standard descriptors/MSC/BOT behavior;
2. minimal identity operation only if parser evidence supports it;
3. bounded immutable low-ROM read and direct byte comparison with the physically recovered OpenTivoo AK1052D ROM;
4. map read-only memory-upload geometry/range behavior.

Do not transfer Tivoo POKE/DOWNLOAD/GOTO semantics by assumption. Explicitly defer writes and arbitrary command enumeration.

## Phase R2-6 / M6 — exact v42012 recovery

This is the primary success condition for the renewed MassBoot program.

Preferred order:

1. use a native read-only SPI/flash command if independently proven;
2. if unavailable, prove bounded RAM helper execution **and return/liveness** separately;
3. only then consider a read-only helper that copies SPI flash into preserved RAM for host upload;
4. never erase/program flash during acquisition;
5. preserve per-range pre/post/liveness evidence, chunk hashes, raw bytes, coverage and final SHA-256.

Validate the resulting image against exact-unit metadata and the known flag42/v42012 board/config evidence. Keep the original raw dump immutable.

### R2 success condition

A provenance-tracked exact v42012 image plus a credible restoration path, or an explicit evidence-backed conclusion that MassBoot cannot provide a no-solder recovery route and another route is superior.

## Phase R2-7 / M7 — optional volatile takeover research

Only after M6.

MassBoot GOTO does not automatically imply a useful resident input hook because MassBoot owns the CPU. Prove trivial helper-return first, then read-only helpers, then study whether a RAM hook can rejoin stock execution safely. If rejoin is awkward, do not force it: exact-v42012 recovery plus the already-proven SD updater is likely the cleaner persistent route.

## Parallel fallback: no-solder SPI-NOR acquisition

Keep this as a decision competitor, not a distraction. If M1 shows an accessible 8-pin SPI flash and M2 indicates in-circuit reading can be done without unsafe back-power/bus contention, a clip-based exact-v42012 dump may be shorter than MassBoot. It needs its own electrical analysis and manifest. Do not assume an in-circuit clip is safe merely because no soldering is required.

## Session discipline and stop rules

- Prefer one discriminating measurement over repeated retries.
- After two materially identical failures, stop and revise the model.
- Any ambiguous live result consumes its manifest; never “just retry.”
- Do not progress from observation -> command, or read -> write, inside one grant.
- Keep exact-unit evidence raw and immutable; derive annotated copies separately.
- Preserve negative results because USB/UART silence can constrain topology when preconditions are proven.
- A hardware route that requires soldering is a dead end for the owner's current constraint unless the owner explicitly changes that constraint.

## Immediate execution order for the next ChatGPT session

1. Bootstrap through `agent-skills/CHATGPT_START_HERE.md`, then hydrate this repository from `START_HERE.md`.
2. Verify Git status/HEAD; preserve existing work.
3. Read, in order:
   - this execution plan;
   - `notes/OPENDITOO-HANDOFF-2026-09-12-MASSBOOT-R2.md`;
   - `notes/OPENDITOO-MASSBOOT-RENEWED-STRATEGY-2026-09-12.md` selectively for evidence/rationale;
   - `AGENTS.md` for authority;
   - older firmware R0/R1 handoff only when a specific fact is needed.
4. Run `python3 scripts/verify_day1_offline.py` and compare against the current baseline; do not modify unrelated Runtime 018 code to chase known environment-only failures.
5. Complete any remaining **R2-0 offline** preparation that is still genuinely open.
6. Review `experiments/OPENDITOO-MASSBOOT-M1-PHOTOS-001.json` against this plan. If it remains correct, stop at the live boundary and ask only for the exact grant string when the owner is ready for M1.
7. After a valid M1 grant and photo upload, analyze the exact-unit images immediately and produce the board-map/M2 decision artifact before proposing any electrical action.

The new session should be autonomous on offline work and conservative only at physical boundaries.
