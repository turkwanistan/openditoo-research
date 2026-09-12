# OpenDitoo handoff — MassBoot R2 recovery phase — 2026-09-12

## Start here

The active firmware/recovery objective is now **MassBoot R2: exact-v42012 recovery**, not the completed R1 static-analysis queue.

Read first:

1. `notes/OPENDITOO-MASSBOOT-R2-EXECUTION-PLAN-2026-09-12.md`
2. `notes/OPENDITOO-MASSBOOT-RENEWED-STRATEGY-2026-09-12.md`
3. `AGENTS.md`
4. use `notes/OPENDITOO-HANDOFF-2026-09-12-FIRMWARE-R0.md` only as the detailed R0/R1 technical record.

## Repository checkpoint

At handoff preparation, firmware R1 static work was closed and the renewed MassBoot strategy was committed locally after it. Key local history:

- `8e26b3d` — Close firmware R1 static analysis
- `e2278fa` — Renew MassBoot recovery strategy
- `c6224d3` — Record cross-project MassBoot handoff identity

The branch may be ahead of `origin/main`; inspect live Git rather than assuming push state.

## Why MassBoot was reopened

The two earlier negative Ditoo USB enumeration trials tested **MB-S**, a stock-firmware soft handoff into ROM MassBoot. They did not test the AK1052D's distinct reset-time **GPIO6 hardware boot strap (MB-H)**.

New offline evidence:

- AK1052D pin targets: RESET pin 3; USB_DM 22; USB_DP 23; GPIO6/UART0_TXD/boot-select 32; GPIO7/UART0_RXD 33.
- preserved Ditoo flag42 v42016 and flag60 v60014 share the same low-level MassBoot handoff body at `0x2968:0x29ee`.
- Ditoo application veneer targets resident Thumb stage1 around `0x00802969`; the body ends by `blx` through low-ROM vector `0x58`, not a reset-time ROM bootstrap.
- direct comparison against the physically recovered OpenTivoo AK1052D resident stage1 MassBoot body found 109/134 bytes identical; all 25 differing bytes are in relocated Thumb BL encodings and all non-call instruction bytes match.
- exact purchased v42012 still has no recovered image; recovery remains the blocker for persistent custom firmware.

Therefore the next research program separates **entry**, **physical routing**, and **protocol** rather than repeating cable/button tests.

## Current route priority

1. M1 exact-unit passive board photos.
2. M2 unpowered continuity/routing map.
3. M3 RX-only UART MassBoot liveness.
4. M4 reset-time GPIO6 hardware-bootstrap USB enumeration.
5. M5 read-only MassBoot calibration.
6. M6 exact v42012 acquisition.
7. M7 volatile takeover only if useful after recovery.

The already-proven TF/SD updater remains the preferred eventual persistent delivery route once rollback/recovery is solved.

## Prepared next physical milestone

`experiments/OPENDITOO-MASSBOOT-M1-PHOTOS-001.json` is a **prepared, unauthorized** photos-only exact-unit imaging manifest.

Required grant text when the owner is actually ready:

`Grant OPENDITOO-MASSBOOT-M1-PHOTOS-001`

The grant covers one controlled disassembly/photo session only. It does **not** cover continuity measurements, powered probing, UART connection, GPIO strapping, USB enumeration, MassBoot commands, firmware read/write or factory mode.

Do not silently widen it.

## M1 success artifact

After owner photos arrive, create a durable exact-unit board-map note/artifact that identifies or ranks:

- board revision/variant;
- AK1052D orientation/pin-1;
- USB-C D-/D+ route candidates;
- candidate accessible endpoints for GPIO6/UART0_TXD, GPIO7/UART0_RXD, RESET, GND and 3.3 V;
- SPI NOR exact marking/package and no-solder clip feasibility;
- candidate factory-pad clusters;
- unresolved mappings and the smallest unpowered M2 continuity tests that discriminate them.

Tag every mapping as photo-proven / geometry inference / unknown.

## Safety/authority state

- Runtime 018 remains the everyday product baseline and must not be modified by firmware recovery work.
- All previous MassBoot enumeration/factory manifests are consumed; do not re-arm them.
- Factory mode is closed: R1 proved initialization performs a destructive 4 KiB erase/write/read test.
- No checksum-valid custom firmware exists or is authorized.
- No MassBoot vendor/SCSI command is authorized by this handoff.
- No device write, RAM write, GOTO, flash erase/program or arbitrary protocol enumeration is authorized.
- No soldering route is part of the plan.
- Offline repo work and manifest/tool preparation may proceed autonomously.

## Existing solved pieces — do not redo

- FIRM R1: category-`0x82` producer fan-in + single consumer seam fully mapped.
- UPDATE R1: updater trailer/gates and BIOS1/BOAR1/PROG1 writer topology mapped.
- PATCH R0: fail-closed non-installable patch prototype exists.
- TELEMETRY R0: normal-firmware design selects typed stock SYS SPP device->host reports.
- FACTORY R1: factory entry is persistent-write/destructive and not a recovery route.
- Runtime 018: Left/Right/short-lever input already works through raw AVRCP and is unrelated to this recovery phase.

## Verification baseline

R2 handoff verification was rerun in the current WSL_MCP sandbox after creating the plan/manifest:

- `tools/thumbv5t_minidis.py --selfcheck` — PASS.
- `tools/ditoo_update_container.py --selfcheck` — PASS.
- `tools/keypad_pipeline_report.py flag42 flag60` — PASS, report `ok=true`.
- `scripts/verify_day1_offline.py` — **345 tests**, exactly **2 errors**, both the already-documented unrelated W9B optical tests caused by missing `PIL`; **zero firmware-R&D failures**.
- `git diff --check` — PASS.
- M1 manifest parses as JSON and remains `physical_execution_authorized=false`, `authorization_consumed=false`.

This exactly matches the prior constrained-sandbox baseline. Do not edit Runtime 018/product code to chase the missing-Pillow environment issue. Re-run the current verifier in the next session and record the live result rather than assuming the count.

Useful focused checks:

```bash
python3 tools/thumbv5t_minidis.py --selfcheck
python3 tools/ditoo_update_container.py --selfcheck
python3 tools/keypad_pipeline_report.py artifacts/firmware/flag42_v42016.bin artifacts/firmware/flag60_v60014.bin
python3 scripts/verify_day1_offline.py
git diff --check
```

## Immediate next action

Do all remaining M0/R2-0 preparation offline, verify the M1 photos manifest, and then stop. When the owner is ready, request exactly:

`Grant OPENDITOO-MASSBOOT-M1-PHOTOS-001`

After that grant, the next meaningful input is the owner's high-resolution exact-unit board photo set. Analyze those images before proposing M2 or any electrical action.
