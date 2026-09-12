# OpenDitoo handoff — 2026-09-12 — firmware/input takeover R0

## Read order

1. `START_HERE.md`
2. **this file**
3. `notes/OPENDITOO-FIRMWARE-INPUT-TAKEOVER-PLAN-2026-09-12.md`
4. `notes/OPENDITOO-FULL-INPUT-TAKEOVER-RESEARCH-2026-09-11.md` for the detailed evidence trail
5. `notes/OPENDITOO-HANDOFF-2026-09-12-R018.md` only when touching the live product/runtime/input sidecar
6. `AGENTS.md` before any live operation

The repository is authoritative over chat history. Re-check Git/state in the new session; preserve concurrent/untracked work.

## Stopping-point state

### Live product is unchanged

**Runtime 018 remains live and accepted.** Policy `OPENDITOO-PRODUCT-RUNTIME-018`, `runtime_revision=13`, `host/product_runtime_v12.py`; main cutover was `f604c32`. Dashboard/Slots/Moss, Host/session/pacing/reconnect/reclaim and webcam policy 006 are unchanged by this firmware-research session. Runtime 017 remains the exact rollback described in the R018 handoff.

Do **not** turn firmware R&D into a Runtime 019 change. Keep the everyday product isolated unless an explicit product requirement emerges.

### Route A is physically proven

`OPENDITOO-SD-P1-001` is consumed and PASS:

- 32 GB FAT32 card already passed normal stock MP3 playback (SD-P0);
- frozen v42016 probe changed only the final stored-checksum byte, SHA-256 `acf0715fc98ecc1dd1abce483a0c68d8ca7b3bf98f676b03bdedacc72bc0ba43`;
- `/divoom/notupdate.bin` control boot: no updater UI;
- exact same bytes as `/divoom/divoomupdate.bin`: distinct stock download/update-to-tray UI, then normal startup/OpenDitoo returned;
- post-test file remained present and byte-identical;
- no checksum-valid package was supplied;
- later passive factory mode displayed `42 / 012`, independently confirming the installed firmware still reported v42012 after SD-P1.

Conclusion: **the exact purchased v42012 unit physically recognizes the SD updater path.** This proves delivery-path recognition, not safe custom flashing.

### Route B MassBoot is behaviorally supported but not externally usable yet

Static exact-model firmware:

- Lighting / key ID3 + GPIO30/external-power condition -> `0x1b8f4(1)` -> `enter massboot!` -> low-level transfer;
- M / key ID1 -> `0x1b8f4(0)` -> `enter test mode!`.

Physical trials:

- `OPENDITOO-MASSBOOT-ENUM-001`: Lighting-held boot did not complete normally, but Windows baseline/disconnected/candidate were 44/44/44 with zero new identity.
- `OPENDITOO-MASSBOOT-ENUM-002`: replacement-cable repeat again 44/44/44, zero new identity.
- both are consumed; no custom USB/SCSI/vendor command was ever issued.

Working conclusion: MassBoot is real/behaviorally supported, but **retail USB-C host enumeration is not demonstrated**. Do not burn time on more cable swaps unless new board/topology evidence appears.

### Factory/test mode is now confirmed

`OPENDITOO-FACTORY-TEST-OBS-001` is consumed. With SD removed, M held at normal startup, then released after alternate entry, and no further controls pressed:

- brief stock battery/startup icon;
- dark interval while M held;
- stable test display **`42` over `012`**;
- no stage advance and no persistent write observed.

This is strong direct on-device evidence for **product flag 42 / installed firmware v42012**, independent of the earlier stock Bluetooth version query.

Static strings/routines confirm this is `divoom_product_test` / stock factory mode, not MassBoot. It contains SPI-flash check, key test, charge and SD routines plus voice/audio/display diagnostics. Do not advance it blindly. The next useful factory-mode task is **offline state-machine mapping**, especially a safe route to `divoom_product_test_key_update` if one exists.

## Major static breakthrough: true keypad pipeline

The exact board configuration supplies both analog ranges and the physical→software table. High-confidence mapping:

| key ID | physical | short | long |
| ---: | --- | ---: | ---: |
| 0 | power/system | `0x47` | `0x47` |
| 1 | M | `0x43` | `0xFF` |
| 2 | + | `0x16` | `0x16` |
| 3 | Lighting | `0x67` | `0x67` |
| 4 | Left | `0x5F` | `0xFF` |
| 5 | - | `0x0C` | `0x0C` |
| 6 | Right | `0x60` | `0x60` |
| 7 | Lever | `0x15` | `0x6B` |

Power is a separate lifecycle path and should remain stock in early work.

The low-level runtime chain in **flag42 v42016** is now:

`ADC -> 0x52844 analog decoder -> key ID -> 0x52926 translation mapper -> 0x52656 common translated-event emitter -> 0xC6D7C queue/category 0x82 -> stock consumers`

For **flag60 v60014**, the corresponding offsets are `0x527B0`, `0x52892`, `0x525C2` respectively. After the branch's `-0x94` shift:

- emitter 48/48 bytes identical;
- ADC decoder 134/134 identical;
- translator 92/92 identical;
- surrounding keypad module 98.93% identical;
- emitter→ADC delta `0x1EE`, ADC→translator `0xE2`.

This is the best PATCH-R0 seam found so far: already-decoded physical input before feature-specific stock side effects fan out.

`scripts/locate_ditoo_keypad_pipeline.py` is now a fail-closed, **recognition-only** locator for those three conserved bodies. It successfully locates both preserved branches and validates the stable relative layout. It does not patch or make a flashable image.

## Firmware/recovery facts that still block a live custom patch

- Exact installed **v42012 bytes are not recovered**.
- Preserved official flag42 **v42016** is an exact-model newer image, not an exact restoration image for the owner's current state.
- Public/current Divoom OTA API appears to return latest by product flag; no historical-version selector has been established.
- Historical flag42 v42010 is documented by REvoom, but its old CDN object is no longer available from the known path.
- The checksum is understood well enough to reject/accept the observed container gate, but that does not by itself establish the complete flash/recovery contract.
- A large `0xFF` area before board config exists in both preserved branches; it is **not yet proven safe executable code space**.

Therefore: **no checksum-valid patched image on the physical device yet.**

## Consumed live experiments from this research checkpoint

- `experiments/OPENDITOO-SD-P1-001.json` — positive updater-path recognition
- `experiments/OPENDITOO-MASSBOOT-ENUM-001.json` — boot-path positive / host enumeration negative
- `experiments/OPENDITOO-MASSBOOT-ENUM-002.json` — replacement-cable host enumeration negative
- `experiments/OPENDITOO-FACTORY-TEST-OBS-001.json` — passive factory mode / `42 / 012`

All are one-use and consumed. **None may be re-armed.** No fresh physical experiment is authorized at handoff.

Private evidence under `captures/private/` remains private/ignored. The manifests preserve compact results and authority history.

## Next milestones — execute offline in parallel where useful

The detailed contract is in `notes/OPENDITOO-FIRMWARE-INPUT-TAKEOVER-PLAN-2026-09-12.md`. Priority order:

### 1. FIRM-R0 — finish the keypad hook contract

- annotate `0x52656` and `0xC6D7C` queue semantics;
- prove short/long/repeat and all desired analog keys flow through the common emitter;
- enumerate any bypass path;
- add regression fixtures/tests around the locator and structural deltas;
- produce a machine-readable keypad-pipeline analysis artifact.

### 2. UPDATE-R0 — fully annotate the SD updater

- marker/version/checksum gate;
- version/downgrade policy;
- flash target/erase/write/reset topology;
- failure ordering;
- offline parser/validator + negative fixtures.

### 3. FACTORY-R0 — map test stages without entering them

- stage index -> visible screen/function/advance condition;
- classify passive vs stateful vs persistent/unknown;
- find the exact built-in key-test stage and prove whether it is safe before proposing a new live observation.

### 4. RECOVERY-R0 — solve exact rollback/readback

- continue exact v42012 recovery search;
- investigate stock Bluetooth/SD software readback/export paths;
- analyze MassBoot protocol offline but do not assume retail USB accessibility;
- consider owner-assisted no-solder board photos only if they would resolve service-transport topology.

### 5. PATCH-R0 — non-flashable fail-open prototype

- signature-locate emitter; do not hardcode one build;
- validate executable placement before using any `0xFF` area;
- stock path must remain exact when claim inactive/expired;
- prototype patched outputs should intentionally retain an **invalid stored updater checksum** so they cannot accidentally pass the known SD gate;
- deterministic diff/disassembly/untouched-hash report;
- first eventual live revision reports one key while forwarding its stock action; suppression comes later.

### 6. TELEMETRY-R0

Find the least invasive way for that first patch to report a key—prefer reusing an already-initialized stock device→host SPP/notification path over adding a large subsystem.

## Desired firmware architecture

`physical key -> stock ADC decode -> OpenDitoo shim -> [claim inactive: exact stock forward] / [claim active: typed INPUT_EVENT + optional consume]`

Claim should be short-lived and heartbeat/TTL based. Disconnect/crash/expiry restores stock input automatically. Do not expose generic raw-memory mutation as the public API. Long term, typed capabilities can support local SD apps and a small sandboxed runtime, but that is after input takeover and recovery are proven.

## New-session execution posture

- Be aggressive/autonomous on **offline static analysis, tooling, tests and repo documentation**.
- Preserve Runtime 018 and unrelated work.
- Do not ask the owner for routine offline decisions that the evidence can settle.
- Stop at a live boundary: physical device interaction, new service/factory stage, MassBoot command, checksum-valid update, or any persistent device mutation requires a fresh reviewed manifest and exact named grant.
- Prefer one decisive live experiment over ladders/retries when a future live gate is actually justified.
- Keep evidence labels honest: exact v42016/v60014 static evidence does not magically become exact v42012 bytes.

## Useful commands at hydration

```bash
cd ~/Projects/openditoo-research
git status --short
git log -8 --oneline
python3 scripts/locate_ditoo_keypad_pipeline.py artifacts/firmware/flag42_v42016.bin
python3 scripts/locate_ditoo_keypad_pipeline.py artifacts/firmware/flag60_v60014.bin
python3 scripts/verify_day1_offline.py
```

If `verify_day1_offline.py` reports a known environment/build-artifact mismatch, compare against the handoff/current clean baseline rather than rewriting live product code to chase an unrelated firmware-R&D issue.
## Handoff verification

- `python3 -m py_compile scripts/locate_ditoo_keypad_pipeline.py` — PASS.
- locator against flag42 v42016 — PASS at emitter `0x52656`, ADC `0x52844`, translator `0x52926`.
- locator against flag60 v60014 — PASS at emitter `0x525C2`, ADC `0x527B0`, translator `0x52892`.
- all four new experiment manifests parse as JSON and are consumed with `physical_execution_authorized=false`.
- `git diff --check` — PASS.
- `python3 scripts/verify_day1_offline.py` ran 326 tests; the only two errors were unrelated W9B optical tests failing to import `PIL` because Pillow is absent in the WSL_MCP sandbox. No firmware-R&D test failed. Do not mutate product code or install dependencies merely to erase this environment-only handoff note.

