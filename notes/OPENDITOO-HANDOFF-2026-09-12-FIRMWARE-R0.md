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

### 1. FIRM-R0 — keypad hook contract — SUBSTANTIALLY DONE (2026-09-12, offline)

Disassembly of both preserved branches (capstone, load base 0 confirmed — every BL resolves
to a known file offset) produced the full runtime event graph and a **material correction to
the hook-seam assumption**:

```
poll tick
  -> key_state_machine 0x52790  (debounce/hold timing: short <1000ms, long >=1000ms)
       -> get_current_key 0x526f2 -> [RAM driver ptr] ADC decoder 0x52844
            -> adc_read_veneer 0xc6764  (6-sample read, drop min+max, average)
       -> translated_event_emitter 0x52656   (short/long PRESS only)
            -> translation_mapper 0x52926     (pick short/long/repeat from the 4-byte record)
            -> queue_post 0xc6d7c (category 0x82)
       -> 500ms auto-repeat timer -> repeat_handler 0x52982
            -> queue_post 0xc6d7c (category 0x82)   <-- BYPASSES the emitter
```

Key findings:

- **The emitter `0x52656` is NOT the single common seam.** It catches only short/long
  *press* events. Auto-repeat and key-change *finalize* post to the queue **directly**,
  bypassing the emitter. The guaranteed single fan-in that catches short + long + repeat is
  the **category-`0x82` message-queue post `0xc6d7c`**. There are exactly **4** category-`0x82`
  producers (`0x52680` emitter press, `0x52916` release-finalize class 2, `0x529aa` repeat
  key-change class 2, `0x529ce` auto-repeat class 3). An adjacent producer `0x525a8` posts a
  different class `0x81` and is not a translated key event.
- `0xc6d7c` is a generic `os_post(category, event, u16 param)` ring-buffer enqueue; the key
  event class is the constant `0x82` loaded in `r0` at each producer.
- Translator return codes drive the emitter: `0`=emit translated byte, `1`=emit raw key id
  (no table), `2`=key not found → drop, `3`=repeat/third handler invoked → emitter emits
  nothing (the handler posts on its own).
- Timing constants (byte-verified): long-press threshold **1000 ms** (`0x7d<<3`), auto-repeat
  period **500 ms** (`0xff+0xf5`), scan reschedule **10 ms**.
- The whole subsystem including the far `queue_post` shifts by exactly **`-0x94`** in flag60
  (`queue_post` flag60 = `0xc6ce8`); category `0x82` is conserved verbatim in both branches.

Delivered offline:

- `tools/keypad_pipeline_report.py` — pure-Python (no capstone dep), fail-closed analyzer
  that re-locates the conserved bodies by signature, derives the per-branch shift, and
  **verifies against real bytes** that each category-`0x82` producer is `movs r0,#0x82` + BL
  to `queue_post`. Recognition + verification only; never patches, no flashable output.
- `artifacts/analysis/keypad_pipeline.json` — committed machine-readable artifact (PASS on
  both branches; pins live firmware sha256s).
- `tests/test_day1_offline.py::FirmwareKeypadPipelineTests` — 5 tests: locator PASS on both
  branches, locator FAIL-CLOSED on a mutated emitter byte, Thumb-BL decoder vs known targets,
  category-`0x82` fan-in verified on both branches, committed artifact matches live bytes.
  Full verifier now **331 tests PASS** in normal WSL (the two W9B optical errors were the
  WSL_MCP sandbox missing Pillow; they do not occur here).

Remaining FIRM-R0 (optional, lower value): annotate the exact consumer task that dequeues
category `0x82` (a consumer-side hook is an alternative single seam), and prove no *other*
category posts a front-panel key. The producer-side model above is already sufficient to
specify a fail-open consume-or-forward shim.

### 2. UPDATE-R0 — SD updater fully annotated + validator — SUBSTANTIALLY DONE (2026-09-12)

`divoom_check_update` disassembled (flag42 file `0x8394`; link base **`0x08400000`** — code BL
read as base 0 because PC-relative, but absolute string pointers use `0x08400000`; the note's
earlier "0x8394..0x89f9 update routine" was really the adjacent rodata string block).

**Container format (verified on both branches — last 20 bytes of file):**

```
[ version : u32 LE ][ "DIVOOMUPDATE" : 12 bytes ][ checksum : u32 LE ]
  file[-20:-16]        file[-16:-4]                 file[-4:]
```

flag42 version `42016`, checksum `0x06ab2183`; flag60 version `60014`, checksum `0x06ab2798`.
Additive checksum = `sum(file[:-4]) mod 2**32` (covers version + marker; excludes only the
stored u32). **No signature/HMAC** in this path.

**Acceptance gates, in firmware evaluation order (reject at first failure):**

1. **marker** — `memcmp(header+5, "DIVOOMUPDATE", 12)` at `0x8744` (`0xa2850`). Mismatch → reject
   ("flag err").
2. **version** — `0x878c-0x879a`: reject if `installed_version >= candidate_version`
   (no downgrade, no same-version reinstall), **UNLESS** a header flag byte `== 0x33` ('3')
   forces the update ("pass version").
3. **checksum** — `0x87be` `subs r2,#4` then additive sum of `file[:-4]` vs stored u32
   (`0x8820` compare). Mismatch → reject (no "start update").
4. **write** — only then `0x883c`: flash writer `0x3a824(mode=0, data_len, checksum, version)`
   → reset. Chunked reads use 1024-byte (`1<<0xa`) buffers.

This explains SD-P1 exactly: the checksum-poisoned probe passed marker + reached the updater UI
but failed the checksum gate, so no flash occurred and the file stayed byte-identical.

Delivered offline (read-only, produces no installable package):

- `tools/ditoo_update_container.py` — parser/validator + `--selfcheck`; reports each gate in
  firmware order. Correctly accepts v42016 as an upgrade from 42012 and rejects it as a
  reinstall on 42016.
- `tests/test_day1_offline.py::UpdateContainerTests` — 6 tests incl. negative fixtures
  (checksum poison → checksum gate; bad marker → marker gate before checksum; force-flag
  bypass; truncated → parse fail).

**Not yet done (deeper, lower priority):** erase granularity / partition map / write topology
inside `0x3a824`, and the exact reset/completion path. Documented as future work — the gate
model above is sufficient to review a candidate package before any (separately authorized)
live use.

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

