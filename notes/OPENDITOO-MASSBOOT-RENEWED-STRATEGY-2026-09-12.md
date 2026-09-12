# OpenDitoo — renewed MassBoot strategy (2026-09-12)

## Executive decision

MassBoot is re-promoted from a de-prioritized recovery fallback to a **high-value recovery research track**, but **not** by repeating the already-consumed Lighting+USB cable experiment.

The renewed strategy separates three independent questions that the earlier work had partially conflated:

1. **MB-S — firmware soft handoff:** the Ditoo application detects external-power/GPIO30 + Lighting/key-ID3, enters resident stage1, performs cleanup, then transfers through low-ROM vector `0x58`. This is the route behaviorally exercised by `OPENDITOO-MASSBOOT-ENUM-001/-002`; it changed exact-unit boot behavior but produced no host-visible retail-USB enumeration.
2. **MB-H — reset-time hardware bootstrap:** the AK1052D silicon has a separate **GPIO6 boot-mode-select strap** sampled during startup. Same-silicon OpenTivoo ROM evidence strongly predicts GPIO6 high/default pull-up -> SPI-NOR boot attempt, GPIO6 low at reset -> ROM MassBoot fallback. **This path has never been tested on the Ditoo.**
3. **Transport wiring:** regardless of how ROM MassBoot is entered, SoC `USB_DM`/`USB_DP` must physically reach a usable connector/pad pair. The Ditoo Plus manual calls the external USB-C connector a charging port, and the two consumed MB-S enumeration trials saw no PnP identity. The external connector may therefore be power-only from the SoC's point of view even if ROM MassBoot is alive.

This makes the next MassBoot work materially different from another cable/port retry.

The first objective is **exact v42012 recovery/readback**, not arbitrary code execution. If MassBoot gives us a safe path to recover the installed flash, it removes the binding rollback uncertainty and can make the already-proven SD updater the simpler eventual delivery mechanism for the input shim.

## Evidence that changes the route

### AK1052D public silicon contract

Anyka AK1052D Specification Rev 2.1.0 (December 2017) states:

- one USB2.0 Full-Speed Host/Slave interface;
- two bootstrap modes: **SPI NOR Flash Boot** and **USB Mass Storage Boot**;
- package pin 22 = `USB_DM`;
- package pin 23 = `USB_DP`;
- package pin 32 = `GPIO[6]/UART0_TXD`;
- GPIO6 reset state = input with internal pull-up;
- **GPIO6 is specially used as a boot mode select pin during system startup**;
- package pin 33 = `GPIO[7]/UART0_RXD`;
- RESET is active-low on package pin 3;
- GPIO6's internal pull-up is approximately 62K–112K;
- JTAG exists, but it uses several shared-function pins and is a fallback, not the first route.

Primary public source mirror:
`https://device.report/m/03949a04e04c7ed5ee9dd188dfdb23f4f67e4cf62d163f70da735a7cd1830dd8.pdf`

The datasheet explicitly says an `AK1052D Programmer's Guide` is required for the complete programming model. No reliable public copy was located in this research pass.

### Same-silicon OpenTivoo ROM evidence

OpenTivoo's exact owned 2018 Tivoo contains AK1052DN048 and has physically measured low ROM. Its reset flow:

- configures/samples GPIO-controller bit 6;
- if bit 6 is high, attempts the SPI-NOR `ANYKA_T2` loader;
- otherwise, or when that loader does not transfer control, converges on ROM MassBoot at `0x16F4`;
- ROM MassBoot enumerates as USB full-speed `04D6:038F`, MSC/BOT-like service mode, and supports a measured read-only UPLOAD primitive among other commands.

Combined with the AK1052D datasheet's GPIO6 boot-select definition and reset pull-up, this is **strong same-silicon inference** that reset-time GPIO6 low selects/forces the USB MassBoot side of the boot decision. It is not yet exact-Ditoo physical proof.

### Ditoo MB-S is a soft ROM handoff, not the hardware bootstrap

Flag42 v42016's application MassBoot veneer at file `0xA6460` targets Thumb `0x00802969`, i.e. resident-stage1 body at file/address `0x2968` / `0x00802968`.

The low-level body ends with:

```text
0x29e8  movs r0,#0x58
0x29ea  blx  r0
0x29ec  b    0x29ec
```

Thus the firmware Lighting route transfers through low-ROM vector `0x58` after stage1 cleanup; it does **not** exercise the reset-time GPIO6 bootstrap decision.

The 134-byte handoff body `file[0x2968:0x29ee]` is byte-identical in preserved flag42 v42016 and flag60 v60014:

`sha256 = 2f1ea36ac7ebc5f70b1f264fbb0e17338c6b598331b5e96b104ba797e11bc566`

The application veneer moves with the known branch layout (`flag42` literal at `0xa6468`, `flag60` at `0xa63d4`), while this low-level body remains fixed. This strengthens the conclusion that it is a stable platform handoff rather than a one-build quirk.

A cross-project byte comparison against OpenTivoo's physically recovered AK1052D resident stage1 (`sha256 6831853dc37bf479c4aa926141e2fb6cd9631020d288fa0a759163ff7e94f292`, Tivoo MassBoot body at `0x2230`) is stronger still: **109/134 bytes are identical, and every one of the 25 differing bytes lies inside Thumb `BL` displacement encodings. All non-call instruction bytes match.** In other words, Ditoo and Tivoo use the same MassBoot handoff instruction skeleton with helper calls relocated. This materially raises confidence that the controller/cache/flash-read/ROM-vector semantics learned on Tivoo are relevant to understanding Ditoo MB-S, while still not granting Ditoo command semantics by assumption.

### Public Ditoo Plus board evidence is useful but not exact-unit truth

FCC ID `A8I-DITOO-PLUS` internal photos show the main PCB, microSD connector, external USB-C receptacle, Anyka SoC area, and multiple exposed pads/vias. The filing's Bluetooth test report identifies the certification sample as hardware `REV:V1.1` and software `ditoo-plus(3128)_svn26520_v60001`.

Therefore the public FCC board is valuable **flag60-era exact-model reference evidence**, but it does not establish trace routing on the owner's flag42/v42012 unit. The FCC schematic/block diagram/operational description were requested as permanently confidential. Exact-unit macro photos and continuity measurements outrank these public images.

FCC sources:
- `https://fccid.io/A8I-DITOO-PLUS/Internal-Photos/Internal-Photos-5058744`
- `https://fcc.report/FCC-ID/A8I-DITOO-PLUS/5058750.pdf`
- `https://fccid.io/A8I-DITOO-PLUS`

The user manual explicitly describes the port as a `USB Type-C Charging port` and the supplied cable as a charging cable. That supports, but does not electrically prove, a power-only external-port hypothesis.

## Working model

```text
                    AK1052D reset
                         |
                   sample GPIO6
                         |
              +----------+----------+
              |                     |
          default/high              low
        (internal pull-up)       (MB-H candidate)
              |                     |
        SPI-NOR loader          ROM MassBoot
              |                     |
          stock boot          USB/UART service?

stock firmware later running
              |
GPIO30/external power + Lighting
              |
       Ditoo stage1 cleanup
              |
        ROM vector 0x58
              |
          ROM MassBoot              (MB-S, already behaviorally tested)
```

The crucial research question is now **not** merely “does MassBoot exist?” It is:

> Can we reach ROM MassBoot through the hardware bootstrap and can we reach its USB or UART service signals through a no-solder connection on the exact unit?

## Detailed execution plan

### M0 — offline closure and signal dossier

**Authority:** autonomous/offline.

1. Preserve the MB-S/MB-H distinction in current plans and future handoffs.
2. Treat the following AK1052D pins as the physical targets to map on the exact board:
   - pin 3: `RESET`, active-low;
   - pin 22: `USB_DM`;
   - pin 23: `USB_DP`;
   - pin 32: `GPIO6 / UART0_TXD`, reset input/pull-up, boot-select;
   - pin 33: `GPIO7 / UART0_RXD`.
3. Search preserved Ditoo firmware for runtime GPIO6/UART0 use so a future strap/receive-only tap has an explicit contention model.
4. Continue searching for the AK1052D Programmer's Guide, production/burning-tool documentation, or a board using the same reset-time bootstrap; do not block progress indefinitely on unavailable proprietary material.
5. Prepare a board-photo annotation template keyed to the 48-QFN pin assignment and FCC board orientation.

**Exit:** exact signals and hypotheses are frozen before touching the device.

### M1 — exact-unit passive board imaging

**Authority:** NEW reviewed physical manifest + exact named owner grant required. No powered probing.

Goal: replace flag60 FCC inference with exact flag42 board evidence.

Capture high-resolution macro photos of:

- both faces of the main PCB;
- board revision/date/silkscreen;
- AK1052D with pin-1 orientation visible;
- USB-C area and every component/trace immediately behind it;
- SPI NOR package and marking;
- all unpopulated pads, test pads, vias and headers near the SoC/USB/flash;
- battery/charge connector topology.

No soldering. Prefer battery disconnected before extended handling if mechanically straightforward.

**Exit:** enough geometry to propose candidate test points without probing QFN legs directly.

### M2 — unpowered continuity map

**Authority:** NEW reviewed physical manifest + exact named grant required.

With battery disconnected and no USB power:

1. Use a USB-C breakout/known cable rather than probing tiny receptacle contacts directly.
2. Map external D+/D- to candidate series resistors/ESD network/test pads and ultimately toward SoC pins 22/23.
3. Map accessible candidate pads/vias to GPIO6/pin32, GPIO7/pin33 and RESET/pin3.
4. Measure passive resistance from GPIO6 candidate to ground and 3.3-V rail to identify external strapping/loading before ever asserting the pin.
5. Avoid direct QFN-leg contact if a resistor/via/test pad endpoint exists; probe slips at a 0.4-mm QFN are a worse risk than the experiment deserves.

Decision tree:

- **D+/D- reach retail USB-C:** MB-H can use the external connector; proceed to M3/M4.
- **D+/D- reach internal pads only:** design a no-solder pogo/test-hook USB fixture; external USB-C is likely charge-only for service purposes.
- **No accessible USB pair:** prioritize UART liveness; JTAG/direct flash read remain fallback routes.

**Exit:** transport topology becomes measured, not inferred.

### M3 — receive-only UART liveness discriminator

**Authority:** NEW reviewed live manifest + exact named grant required.

Why this is high value: GPIO6 is also `UART0_TXD`, GPIO7 is `UART0_RXD`; the same AK1052D ROM on OpenTivoo emits the `SnowbirdT2_MassBoot>#` banner from its MassBoot path. UART observation can separate “ROM entered” from “USB not wired” without issuing a MassBoot command.

Use a 3.3-V high-impedance UART adapter in **receive-only** mode: device TX -> adapter RX + common ground; do not connect adapter TX initially.

Two bounded observations, each requiring its own reviewed boundary if not combined explicitly:

- **M3-S:** one MB-S Lighting soft-handoff entry while monitoring UART. A banner/consistent ROM output would prove the prior exact-unit behavior is true ROM MassBoot even though retail USB was silent.
- **M3-H:** one hardware-bootstrap attempt with GPIO6 deliberately held in the alternate state only across a true reset/startup sample, then released/tri-stated, while monitoring UART.

Do **not** hard-short an unidentified shared pin. The pull-down/open-drain fixture is designed only after M2 establishes the actual pad, passive loading and safe reference rails.

Interpretation:

- banner on S and/or H -> entry is proven; focus next on USB wiring/PHY;
- H banner but S silence -> hardware bootstrap is the superior entry route;
- S banner but H silence -> revisit strap/reset timing or pad identity;
- no banner -> UART may be unmuxed/unrouted; this alone does not disprove MassBoot.

### M4 — hardware-bootstrap USB enumeration only

**Authority:** NEW reviewed live manifest + exact named grant required.

Preconditions: M2 mapped GPIO6 and USB D+/D- route; reset/power sequencing is explicit; no ambiguous direct-pin poking.

Perform exactly one bounded MB-H cold/reset entry with GPIO6 in the alternate state. Capture only standard host enumeration/descriptors. Send **zero custom vendor/SCSI commands**.

Same-silicon OpenTivoo suggests, but does not require, a full-speed MSC/BOT-like identity around `04D6:038F`. Treat any actual Ditoo descriptor as new exact-unit evidence.

Outcomes:

- **Enumerates:** major breakthrough; freeze descriptors and proceed to M5.
- **UART MassBoot positive, USB negative:** boot entry is solved; troubleshoot physical USB routing/pull-up/mux/connector path rather than key combos.
- **Internal-pad USB works but retail USB-C does not:** definitive service-route answer; preserve a no-solder pogo fixture design.
- **Neither UART nor USB:** stop. Revisit strap/reset and board mapping offline rather than retrying combinations.

### M5 — read-only MassBoot identity/protocol calibration

**Authority:** NEW reviewed live manifests/grants, one semantic step at a time.

Do not immediately inherit OpenTivoo commands merely because the SoC and ROM family appear identical.

Progression:

1. preserve standard USB descriptors/interface/endpoint geometry;
2. use only standard read-only SCSI/MSC requests needed to characterize the shell;
3. after static/same-ROM confidence is sufficient, consider the smallest typed identity request equivalent to OpenTivoo `F1 01 IDENTIFY`;
4. only after command-parser identity is proven, consider a bounded read-only memory UPLOAD from an immutable ROM region and compare it against the physically recovered OpenTivoo boot ROM;
5. no POKE/DOWNLOAD/GOTO in the first characterization phase.

**Exit:** either same-ROM MassBoot semantics are independently established on Ditoo or the transfer assumptions are rejected before any write-capable command is used.

### M6 — exact v42012 recovery

**Authority:** separate reviewed recovery manifests/grants.

This is the most valuable MassBoot milestone.

A ROM memory-UPLOAD primitive does not automatically mean SPI flash is directly memory mapped in MassBoot. Resolve the actual readback mechanism before proceeding.

Preferred order:

1. use any independently proven ROM/service **read-only flash** primitive if one exists;
2. otherwise, only after safe RAM read/write/return semantics are proven, consider an OpenTivoo-style bounded RAM helper that reads SPI into preserved RAM and returns to MassBoot, followed by UPLOAD;
3. preserve every RAM preimage required by a helper and prove service liveness before and after each bounded action;
4. never erase/program flash during recovery acquisition;
5. assemble the exact unit's flash dump with offset coverage, per-chunk hashes and a final SHA-256/provenance manifest.

Validate recovered bytes against expected v42012 metadata/board config and preserve the untouched dump before deriving anything from it.

**Exit:** exact flag42 v42012 is recoverable/restorable enough to revisit the existing SD updater delivery path with materially lower preservation risk.

### M7 — optional volatile execution/input-hook proof

This is **not** the primary objective and should happen only after M6 materially closes recovery.

MassBoot owns the CPU while active, so “we can GOTO RAM” does not automatically imply “we can leave a hook resident and resume stock firmware.” First prove trivial RAM helper execution/return, then read-only helpers, then explicitly study whether a volatile hook can survive/rejoin normal stock boot.

If that transition is awkward, do not force the Tivoo architecture onto Ditoo. Once v42012 is safely recovered, a persistent fail-open shim delivered through the already-proven SD updater may be the cleaner route.

## Parallel fallback routes

These stay secondary to MB-H + UART/USB mapping:

- **Direct SPI-NOR read with a no-solder clip:** potentially the shortest exact-v42012 recovery route if the exact unit's flash package is accessible. It must be designed as an unpowered/read-only acquisition with voltage/back-power/bus-contention analysis; an in-circuit clip is not automatically safe.
- **JTAG:** AK1052D supports it, but several JTAG functions share normal peripheral pins. Use only if exact-unit board photos/continuity reveal a plausible factory pad set and MassBoot/flash-read routes fail.
- **Retail USB-C MB-S cable retries:** closed unless new board evidence proves D+/D- should reach the SoC. Two consumed trials are enough.
- **Factory mode:** not a recovery route; initialization performs a destructive 4-KiB flash test.

## Risk ladder

| Step | Persistence risk | Primary risk | Information value |
| --- | --- | --- | --- |
| M0 offline analysis | none | analytical error | high |
| M1 passive photos | none | mechanical handling | high |
| M2 unpowered continuity | none | probe slip / accidental back-power | very high |
| M3 UART RX-only | none intended | electrical mis-identification | very high |
| M4 MB-H enumeration | none intended | strap/reset electrical error | decisive |
| M5 read-only protocol | none intended | wrong command semantics / service wedge | high |
| M6 flash readback | none intended | helper/service liveness, RAM disturbance | decisive |
| write-capable MassBoot / custom firmware | persistent possible | brick/data loss | **outside this phase** |

## Stop rules

- No new physical step without a fresh reviewed manifest and exact owner grant.
- Never re-arm `MASSBOOT-ENUM-001/-002`.
- No more cable/port swaps without a signal-routing reason.
- No blind grounding of GPIO6 and no direct QFN probing when a mapped test pad can be used.
- No MassBoot write-capable command until read-only identity and recovery are established.
- No checksum-valid custom SD firmware while the current recovery gate is unmet.
- Preserve Runtime 018/everyday product and all hash-bound runtime files unchanged.

## Recommended immediate next action

Complete M0 offline and prepare—not execute—a **photos-only M1 manifest** for the owner's exact unit. The first physical action should be macro imaging, not strapping GPIO6.

The most valuable owner contribution after that is a set of sharp exact-unit mainboard photos. Those determine whether the next operation is simply an external USB-C MB-H test, a no-solder internal USB/UART pogo route, or a different recovery path entirely.
