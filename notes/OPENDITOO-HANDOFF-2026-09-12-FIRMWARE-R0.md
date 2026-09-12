# OpenDitoo handoff — 2026-09-12 — firmware/input takeover R0/R1

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
- no stage advance or visible indication of a persistent write during the observation.

This is strong direct on-device evidence for **product flag 42 / installed firmware v42012**, independent of the earlier stock Bluetooth version query. **R1 static analysis later proved that factory initialization itself invokes a destructive 4 KiB SPI erase/write/read test**, so the old observation must not be described as read-only merely because the mutation was not visually apparent. Do not repeat factory entry under the current evidence.

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

## R1 checkpoint — start here next

The detailed status is synchronized in `notes/OPENDITOO-FIRMWARE-INPUT-TAKEOVER-PLAN-2026-09-12.md` § **Next work (R1)**. Current result:

1. **N1 RECOVERY — UNRESOLVED / binding blocker.** Direct Wayback CDX/timemap requests could not be executed from this session, and WSL DNS was down. This is not an archive-negative. Exact v42012 is still unrecovered; owner/community v42012 is the strongest lead, with a future clean-network CDX retry for v42010 secondary.
2. **N2 FACTORY — DONE / destructive.** The SPI check erases+writes+reads 4 KiB at `ALARM.start_page + 0x2b00` and is invoked unconditionally during factory initialization.
3. **N3 FIRM — DONE.** A single consumer loop at `0xbc34` dequeues the ring; category `0x82` dispatch is a second viable single hook seam. Queue-post xrefs are completely enumerated.
4. **N4 UPDATE — DONE.** Writer topology is BIOS1/BOAR1/PROG1 with 256-byte pages, 4 KiB + 64 KiB erase modes, post-write flash checksum verification, then reset.
5. **N5 — BLOCKED.** There is no proven read-only route into factory mode because initialization itself mutates flash. No live manifest was prepared.
6. **N6 — BLOCKED by N1.** No checksum-valid custom package or live firmware operation is authorized.

**Single best next action:** recover a provenance-tracked exact v42012 image/restore source. Until then remain offline/non-flashable.

### Per-goal status (2026-09-12)

Detailed contract in `notes/OPENDITOO-FIRMWARE-INPUT-TAKEOVER-PLAN-2026-09-12.md`. Priority order:

### 1. FIRM-R0/R1 — keypad hook contract + consumer seam — DONE (2026-09-12, offline)

Disassembly of both preserved branches produced the full runtime event graph and a **material correction to the hook-seam assumption**. Earlier R0 work used Capstone; R1 cross-checks used the repository's byte-verifying analyzers plus `tools/thumbv5t_minidis.py` because WSL DNS prevented installing Capstone in the throwaway venv. Code BL targets are PC-relative/file-offset based; absolute pointers use link base `0x08400000`.

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
- The producer/queue/key-dispatch subsystem shifts by **`-0x94`** in flag60 (`queue_post`
  `0xc6d7c -> 0xc6ce8`, dequeue `0xc6df0 -> 0xc6d5c`, key dispatcher `0xe1374 -> 0xe12e0`).
  The **consumer loop itself stays fixed at `0xbc34`** in both preserved branches; 62/64 bytes
  are identical and only the two branch-relative call immediates to the shifted targets differ.
- The queue dequeue at `0xc6df0` has exactly **one** caller (`0xbc6a`). The consumer compares
  category `0x82` at `0xbc44` then dispatches it at `0xbc4c`; this is a viable alternative
  single consumer-side hook seam. Category `0x81` is compared separately at `0xbc40` and sent
  to its own fixed dispatcher `0xbbac`, confirming it is not the translated front-panel key class.
- Exhaustive halfword-aligned BL/BLX xref scanning finds exactly five direct callers of the
  queue post in each preserved branch: the four `0x82` producers plus the one `0x81` producer.
  There is no unresolved direct `0x82` producer in these images.

Delivered offline:

- `tools/keypad_pipeline_report.py` — pure-Python (no capstone dep), fail-closed analyzer
  that re-locates the conserved bodies by signature, derives the per-branch shift, and
  **verifies against real bytes** that each category-`0x82` producer is `movs r0,#0x82` + BL
  to `queue_post`. Recognition + verification only; never patches, no flashable output.
- `artifacts/analysis/keypad_pipeline.json` — committed machine-readable artifact (PASS on
  both branches; pins live firmware sha256s).
- `tests/test_day1_offline.py::FirmwareKeypadPipelineTests` — now 7 tests, adding byte-verified
  assertions for the single consumer/dequeue seam, the complete five-call queue xref set, and
  the fixed-consumer/shifted-target relationship across both branches.
- `tools/thumbv5t_minidis.py` — small read-only Thumb-1/ARMv5T inspection fallback with an
  assert-based self-check. Added because this session's DNS outage prevented installing Capstone;
  unknown encodings stay explicit instead of being guessed.

FIRM-R0/R1 is closed strongly enough for either producer-side or consumer-side hook design.

### 2. UPDATE-R0/R1 — SD updater gates + flash topology — DONE (2026-09-12, offline)

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

**R1 writer topology (byte-verified offline):** `0x3a824` resolves three named flash objects
through stock lookup: **BIOS1, BOAR1, PROG1**. The lookup returns byte capacity plus a u16
start-page; flash page size is **256 bytes**. For mode 0, helper `0x3a746` erases BIOS1 in
**4 KiB** sectors (`0x1beca`, 16 pages) and erases the combined PROG1+BOAR1 allocation in
**64 KiB** blocks (`0x1beea`, 256 pages). Streaming helper `0x3a4ec` maps logical update pages
BIOS1 -> BOAR1 -> PROG1 and writes one 256-byte page at a time via `0x1be82`. Completion helper
`0x3a356` re-reads the mapped pages via `0x1beaa`, recomputes the additive byte sum from flash,
and compares it to the expected checksum. Only a match enters `0x3a246`, which logs
`divoom_update_device_update_firmware; reset!` and calls non-returning reset primitive `0x1b60c`.
Named-object lookup/capacity failures happen before erase; a post-write checksum mismatch exits
without the completion/reset path. `tools/ditoo_update_container.py` now reports this topology
as read-only metadata; it still cannot create/fix an installable package.

### 3. FACTORY-R0/R1 — product-test SPI safety reclassified — PERSISTENT-WRITE (2026-09-12, offline)

Disassembled the product-test dispatcher/router (flag42 `0x16c52`-`0x16d82`) and the key-test
stage (`0x16ef6`). Findings:

- **Entry:** M-at-boot → `0x1b8f4(0)` → `enter test mode!` → `divoom_product_test`
  (`..\source\divoom_app\divoom_product_test.c`, string `0x16dc0`).
- **Stage routing (`0x16d3e`):** gated on product-test mode (`global[0]==2`). The **M key short
  event `0x43`** (`[r4]==0x43`, `[r4+1]==0`) is the advance/route key. Stages are dispatched by
  id (observed ids 4,5,6,7,8,9,0xc,0xd,0xe,0xf) via `0x2e522` (per-stage display/routine set).
- **Advance (`0x16d08`):** increments a volatile step index in RAM (`[state+4]+0xa`); on a
  stage's last step it moves to the next stage id. **Advancement is key-driven, never
  automatic** — this is why the passive observation stayed on stage 0 (`42 / 012`) with no
  controls pressed.
- **Stage 0:** passive; displays product flag / firmware version (`42 / 012`). **Read-only.**
- **Key-test stage (id 7, `0x16ef6`): READ-ONLY / SAFE.** It verifies the six controls
  +,Lighting,Left,-,Right,Lever (`0x16,0x67,0x5f,0x0c,0x60,0x15` = key IDs 2..7) are pressed
  **in order**, incrementing a volatile counter and calling advance on completion. No SPI/flash
  write; no persistent state mutation in the routine. `divoom_product_test_key_update: key test
  is over!` (`0x16e70`) logs completion.
- **`divoom_product_test_spiflash_check` is confirmed destructive/persistent-write.** The
  actual routine is `0x16a40` (the earlier `0x16b92` lead is an initializer, not the check). It
  allocates two 4 KiB buffers, fills the first with a test pattern, computes a target page, calls
  4 KiB erase wrapper `0x1beca`, writes 16 pages with `0x1be82`, reads 16 pages back with
  `0x1beaa`, then `memcmp`s 4096 bytes and logs `spiflash error!/ok!`. It does **not restore**
  previous contents.
- **Write target:** `divoom_main_get_gif_addr_info` (`0x34382`) looks up `ALARM`, returns
  `ALARM.start_page + 0x2a00`, and reports a 0x100-page (64 KiB) GIF region. The SPI test adds
  another `0x100` pages, so its 4 KiB target begins at page
  **`ALARM.start_page + 0x2b00`**: the first sector immediately after that computed 64 KiB GIF
  region. Static evidence supports that this was intended as a factory scratch location, but
  does not prove it is disposable on every retail unit; classification remains persistent-write.
- **Critical route correction:** `divoom_product_test_init` calls this routine **unconditionally**
  at `0x171ea -> 0x16a40`, immediately after initial display setup. Therefore merely entering
  factory/product-test mode can erase/write this sector; it is not a later stage that can be
  safely avoided after entry.
- **charge / sd / disp stages** (`divoom_product_test_charge_update` `0x172bc`,
  `_sd_update` `0x172ec`, `divoom_disp_test` `0x2e590`): read/measure + display-only; treat as
  read-only pending confirmation, below the key test in priority.

**Live safety conclusion:** there is **no read-only factory-entry route** proven by this image,
because initialization performs the erase/write test before key-test navigation. N5 is therefore
**BLOCKED**; do not prepare or execute a factory key-test manifest under the current plan. The
key-test routine itself remains read-only, but reaching the factory environment is not.

### 4. RECOVERY-R0 — rollback/readback search — STILL BLOCKED (2026-09-12)

Offline/public-source avenues exhausted this pass; the recovery gate remains **UNMET**:

- **Exact v42012:** not found. REvoom does not list v42012 at all — consistent with the OTA
  API returning latest-per-flag with no historical-version selector.
- **Documented older CDN objects are purged:** REvoom lists flag42 **v42010**
  (`http://f.divoom-gz.com/.../eEwpPWA93ECEIZjCAAAAAArkYGQ617.bin`) and flag60 **v60010**;
  both return **HTTP 404** on live HEAD checks (the `f.divoom-gz.com` nginx server is up, the
  objects are gone).
- **Wayback Machine: still UNRESOLVED after R1 retry.** Direct CDX/timemap requests from the
  web tool were rejected by its URL-safety layer before reaching Wayback, while the WSL
  environment had a deterministic DNS outage (also preventing GitHub/pip access). This is an
  environment/tooling block, **not evidence that no snapshot exists**. REvoom independently
  still confirms v42010 filename/SHA-1 `7c352e6b8f62af8d0a2d51d824f75d1dafc18050` and v60010
  SHA-1 `017a40dcef6018f34be0ec9b83003d71c67e4a58`.
- **No stock SPP firmware-readback route:** the entire SPP command set is status GETs, SET
  commands, and update-*push* (`SPP_APP_UPDATE_FILE_INFO`); there is **no** read/dump/export/
  backup command (only a generic `FILE_MODE_READ` file mode). So the proven SPP channel cannot
  export firmware.
- **MassBoot readback:** inaccessible via retail USB (ENUM-001/002 negative); unchanged.

**Best remaining leads (future):** (1) Wayback/CDX retry for the v42010 object from a clean IP —
if recovered, v42010 is exact-flag42 (older than v42012; a *downgrade*, updater-rejected unless
the `0x33` force flag, and NOT the exact original) but a useful third cross-check and possible
recovery target with a documented loss-of-v42012 tradeoff; (2) owner/community v42012 copies.
Until (a) exact v42012 restorable bytes + a credible restore path or (b) an owner-approved
recovery strategy exists, stay offline/non-flashable.

### 5. PATCH-R0 — non-flashable fail-open prototype — DONE (2026-09-12, offline)

`tools/openditoo_patch_prototype.py` composes FIRM-R0 (seam) + UPDATE-R0 (validator):

- **fail closed** — refuses any firmware the locator does not recognize (verified against
  `tivoo_31102.bin`);
- **signature-locates** the seam and derives the branch shift (0 / 0x94); no hardcoded build;
- **verifies original bytes** — every category-`0x82` producer site must be exactly
  `movs r0,#0x82` + `bl queue_post` or it refuses;
- **models the fail-open hook** — re-targets each of the 4 producer BLs to a caller-supplied
  `shim_entry` (correct Thumb-BL encoder, inverse of the decoder); the shim body (claim/
  heartbeat + forward-or-consume) and executable-cave placement are **explicitly NOT authored**
  — LIVE-gated;
- **non-installable by construction** — any emitted research image has a deliberately invalid
  stored updater checksum, and the tool re-runs the UPDATE-R0 validator to PROVE the updater
  rejects it (refuses to emit if it somehow passed);
- **reports changed regions** + untouched-region SHA-256 tamper witness.

Tests: `PatchPrototypeTests` (5) — BL encoder⇄decoder inverse; recognize+verify both branches;
emitted image rejected at the updater checksum gate (independently re-validated); fail-closed
on unknown firmware; refuse on original-byte mismatch. Verifier baseline before R1: **342 tests PASS**.

Still LIVE-gated (unchanged): authoring the shim machine code, proving an all-`0xFF` region is
a resident/executable cave, and any device write. The prototype deliberately stops at the
seam-redirect model.

### 6. TELEMETRY-R0 — least-invasive report channel — DECIDED (2026-09-12, offline)

**Recommendation: reuse the already-initialized stock SYS SPP device→host response path.**

Evidence (exact-model firmware strings + exact-unit observation):

- The firmware brings up a framed, checksummed SPP command/response service at boot:
  `SYS SPP init!: %x, %d` (`0xf72c`), `[SYS:SPP]check sum err` (`0xf7c4`),
  `SYS_SPP_OKCommandACK` (`0x22fe8`), and a large typed command set incl.
  `SPP_GET_DEVICE_INFO` (`0x12357`), `SPP_GET_TOOL_INFO`, `SPP_GET_VOLTAGE`, `SPP_SET_GAME`.
  This is the **same RFCOMM/SPP stack OpenDitoo already uses** for image transport, so the Host
  already speaks it and no new Bluetooth service, socket, or frame builder is needed.
- The device→host direction is independently proven on the exact unit: the stock firmware
  already emits unsolicited RFCOMM reports (`0x09`, `0xBD`) that reach Windows today (BTN-2 /
  BTN-7 captures).

**Design:** the first observe-only research revision emits one small typed SPP key-report per
claimed key (a new/spare typed report the Host can distinguish, reusing the existing SPP frame
builder + checksum) **while still posting the stock category-`0x82` event** (forward). This is
strictly additive and fail-open: if the SPP send fails, stock behavior is unaffected.

Ranked alternatives (rejected as primary): (2) piggyback the unsolicited `0x09`/`0xBD` RFCOMM
reports — lower-level but tied to specific stock behaviors and reclaim side effects, harder to
attribute cleanly; (3) AVRCP pass-through — that IS the stock action for Left/Right/lever and
does not exist for M/+/Lighting/-, so not a general telemetry channel.

Do **not** expose a generic raw-memory API; the eventual public surface stays typed/capability-
scoped (`GET_VERSION`, `CLAIM_INPUTS`, `RELEASE_INPUTS`, `INPUT_EVENT`, heartbeat).

## Desired firmware architecture

`physical key -> stock ADC decode -> OpenDitoo shim -> [claim inactive: exact stock forward] / [claim active: typed INPUT_EVENT + optional consume]`

Claim should be short-lived and heartbeat/TTL based. Disconnect/crash/expiry restores stock input automatically. Do not expose generic raw-memory mutation as the public API. Long term, typed capabilities can support local SD apps and a small sandboxed runtime, but that is after input takeover and recovery are proven.

## New-session execution posture

- **Start at the R1 plan (§ "Next steps — start here (R1)" above / plan N1–N6).** Recommended
  first move: N2 (offline), then N1.
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
# R0 offline tools delivered 2026-09-12:
python3 tools/keypad_pipeline_report.py artifacts/firmware/flag42_v42016.bin artifacts/firmware/flag60_v60014.bin
python3 tools/ditoo_update_container.py --selfcheck
python3 tools/openditoo_patch_prototype.py artifacts/firmware/flag42_v42016.bin
python3 scripts/verify_day1_offline.py   # expect 345 tests after R1 in a normal WSL with Pillow
# Read-only fallback when Capstone cannot be installed:
python3 tools/thumbv5t_minidis.py --selfcheck
# If network works, Capstone may still be installed only into a throwaway /tmp venv.
# Firmware link base for absolute pointers is 0x08400000; code BL is PC-relative.
```

If `verify_day1_offline.py` reports a known environment/build-artifact mismatch, compare against the handoff/current clean baseline rather than rewriting live product code to chase an unrelated firmware-R&D issue.
## Handoff verification

- `python3 -m py_compile scripts/locate_ditoo_keypad_pipeline.py` — PASS.
- locator against flag42 v42016 — PASS at emitter `0x52656`, ADC `0x52844`, translator `0x52926`.
- locator against flag60 v60014 — PASS at emitter `0x525C2`, ADC `0x527B0`, translator `0x52892`.
- all four new experiment manifests parse as JSON and are consumed with `physical_execution_authorized=false`.
- `git diff --check` — PASS.
- `tools/thumbv5t_minidis.py --selfcheck` — PASS.
- R1 focused firmware suites: 14/14 PASS.
- Full verifier: **345 tests discovered**; exactly two errors, both the documented unrelated W9B
  optical imports caused by missing Pillow in this sandbox. **No firmware-R&D test failed.**

