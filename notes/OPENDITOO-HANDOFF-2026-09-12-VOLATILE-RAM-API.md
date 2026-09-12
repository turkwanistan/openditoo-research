# OpenDitoo handoff — volatile RAM API / parser-exhaustion phase — 2026-09-12

## New active research route

The owner does **not** want the recovery project to depend on clips, continuity measurements, attached debug hardware or deeper disassembly. Physical MassBoot/SPI work is therefore deferred even though `OPENDITOO-MASSBOOT-M2-UNPOWERED-MAP-001` remains authorized/unconsumed.

The new active research objective is:

> **Exhaust the Ditoo Plus Bluetooth/parser surface for a reversible no-flash path to a RAM-resident OpenDitoo API.**

Authoritative plan:

`notes/OPENDITOO-VOLATILE-RAM-API-PARSER-PLAN-2026-09-12.md`

Read it before implementation.

## 2026-09-12 VRAM-0/1 + Tier-1 VRAM-2 checkpoint

The direct stock SPP tier is now **comprehensively closed for this route** on the preserved Plus corpus. Reproducible authority is:

- `tools/ditoo_spp_surface.py`;
- `artifacts/analysis/volatile_ram_api_surface.json`;
- `tests/test_day1_offline.py::VolatileRamApiSurfaceTests`.

Current machine-checkable coverage:

- 251/251 top-level dispatcher slots emitted across all four pinned Plus branches;
- 9/9 implemented first-level `0xbd` EXTERN subcommands terminally classified;
- 124/124 explicit non-default handlers terminally classified;
- 54 high-value/deep-audited handlers plus 70 handler-local scalar/fixed-control screens;
- 0 unresolved top-level handlers;
- no direct caller-controlled RAM-write primitive;
- no caller-tainted direct-SPP indirect branch/call promoted;
- no candidate for a live parser manifest.

Important negative/closure details include bounded destination writes for `0x44`, `0x50`, `0x56`, `0x58`, `0x5d`, `0x6c`, `0x75`, `0x81`, and `0x86`; read-only/source-overread classes at `0x18`/`0x3c` do not provide controlled RAM; and storage-backed GIF/file/content routes (`0x35`, `0x51`, `0x52`, `0x55`, `0x5c`, `0x7e`, `0x8b`, `0x8c`, update/file families, `0xb1`, `0xfa`, etc.) are explicitly excluded from the volatile route. Period-app command names are labeling evidence only; firmware dataflow is authoritative.

The 70 `CLOSED_SCALAR_CONTROL` entries are a deliberate Tier-1 bulk-parser/control-flow closure: they prove no packet pointer or outer caller length is forwarded from the direct handler into a content/copy parser and no caller-tainted direct control sink was found. They are **not** a claim that every scalar helper is mathematically free of every conceivable logic bug. Corpus/dispatcher drift or any newly unclassified explicit handler makes the atlas fail closed.

**Tier-1 handoff target (historical):** the branch-specific external veneer behind `0x6c` was the next unexpanded sink. Tier-2 has since shown that this is the resident `divoom_light_word` display handoff, not generic media/codec processing; see the Tier-2 checkpoint below.

Safety state at this checkpoint is unchanged: Runtime 018 was not touched; no device transmission, malformed live packet, reboot/crash probe, factory/update write, MassBoot action, measurement, SPI attachment, UART/GPIO/reset work or other physical action occurred.

## 2026-09-12 Tier-2 resident display checkpoint — RAM primitive promoted, live gate still closed

Reproducible authority:

- `tools/ditoo_tier2_display_surface.py`;
- `artifacts/analysis/volatile_ram_api_tier2_display.json`;
- `tests/test_day1_offline.py::VolatileRamTier2DisplayTests`.

The prior "external media/codec" description was too broad. Source provenance places the path in `divoom_light_word.c`; each preserved Plus branch calls through a branch-specific ARM veneer to the same resident Thumb routine at `0x008012a8`. No generic audio decoder is proven reachable from this command.

The exact stock path is now pinned with a sequencing correction: `0x6c` does **not** request/prime mode `0x0b` itself. `0x6e SPP_DRAWING_CTRL_MOVIE_PLAY` with a nonzero first payload byte takes the stock prime path at `0x112ba`: `r0=0x0b, r1=0 -> 0x71b8`, then immediately re-reads `0x12886` and compares the result with `0x0b`. That first transition runs the light-word initializer. Once content mode is already `0x0b`, `0x6c SPP_DRAWING_ENCODE_MOVIE_PLAY` reaches the same-mode handler `0x12cd4`, forwarding `packet+5` and the caller u16 at `packet+3` through the display function to the resident routine. The resident routine later performs `memcpy(ctx[0], source, caller_length)` with that u16. This corrected `0x6e(nonzero) -> mode 0x0b -> 0x6c same-mode copy` route is stable 4/4.

The size mismatch is deterministic in the static model:

- generic SPP assembler accepts declared inner lengths through `0x800`;
- maximum `0x6c` source after command/payload framing is 2041 caller-controlled bytes;
- display backing request is `0x708`;
- application allocator rounds to 16-byte units, so the physical block is `0x710`;
- exposed display pointer is backing+`0x308`;
- physical capacity from that pointer is `0x408` = 1032 bytes;
- therefore the path can write **up to 1009 caller-controlled bytes beyond the physical allocation**.

This promotes `CALLER_CONTROLLED_ADJACENT_HEAP_OVERWRITE` across 4/4 preserved Plus branches. It is RAM-only and does not require the update/file/persistent paths that Tier-1 excluded.

Historical note: this was the state at the first Tier-2 display checkpoint. Placement and control flow were still unproven there. The later placement/trigger/VRAM-3 checkpoint below supersedes that limitation and promotes deterministic cold-start placement plus a returning controlled indirect branch **offline only**.

No malformed/custom `0x6c` traffic has been transmitted. At that earlier Tier-2 display checkpoint no live manifest existed; the later grant-ready VRAM-6/7 manifest is recorded below and remains ungranted/unexecuted.


### Tier-2 placement + trigger + VRAM-3 checkpoint

Three fail-closed artifacts now separate the remaining gates:

- `tools/ditoo_tier2_placement.py` / `artifacts/analysis/volatile_ram_api_tier2_placement.json`;
- `tools/ditoo_tier2_trigger.py` / `artifacts/analysis/volatile_ram_api_tier2_trigger.json`;
- `tools/ditoo_vram3_execution_model.py` / `artifacts/analysis/volatile_ram_api_vram3_execution.json`.

**Placement:** the allocator is best-fit, uses 16-byte units, splits from the low-address edge, uses separate descriptors, and coalesces adjacent free extents. Placement is now **promoted deterministic 4/4**. The missing bootstrap edge was recovered through the transformed `0x002xxxxx` callback namespace: stage-1 explicitly zeros BSS, calls the branch-local `Fwl_MallocInit` veneer, performs a bounded framework-registration sequence, then calls transformed app main `0x8dea`. The only intervening constructor loop is empty (`start == end == 0x00802c08`), and the resident bootstrap callback table invokes its `+4` resident callback rather than the app allocator/free at `+8/+c`. Therefore the app heap is pristine at `0x8dea`. The exact startup model yields display backing `0x00804470`, controlled display-data destination `0x00804778`, runtime50 `0x00804b80`, and runtime50 callback `0x00804bb4`; callback source offset is `0x43c` and 1088 controlled bytes fully cover it while stopping at runtime50 `+0x37`.

Two simple placement strategies are now closed. The persistent display root has one direct constructor edge and no application-heap free in the audited display/backing service families, so ordinary stock teardown/recreate cannot be used to move the vulnerable block into a groomed hole. The 0x80 callback-bearing plugin family is real and free/recreate-capable, but has only two direct constructor sites, both reviewed as singleton subsystem lifecycles; it is not an unbounded stock heap spray.

**Control sink / trigger:** runtime50 is a persistent 0x50-byte object whose `+0x34` field is a genuine function pointer. The `0x1fa8a` family loads `object+0x34`, checks it for zero, and `BLX`es it; the `0x1fd6a` family stores its incoming callback value there. VoiceTip's period-1 microtask registration/dispatch remains proven 4/4. The deterministic stock composition is now pinned in the correct order: (1) put the unit in ordinary btplayer mode (mode 4); (2) send stock `0x6e SPP_DRAWING_CTRL_MOVIE_PLAY` with `payload[1] != 0` to prime content mode `0x0b`; (3) stock `0xa5 SPP_SET_ALARM_LISTEN` with nonzero start and selector 2 resolves to model `0x22`, constructs event `0x34c` with halfwords `(0x22, caller_arg, 0x003c, 0x0002)`, and the btplayer handler reaches the branch-local `0x1fd6a` VoiceTip setup; (4) an exact 1088-byte `0x6c` source takes the already-selected mode-`0x0b` same-mode copy path and controls runtime50 byte0=`0xff`, byte8=`0x22`, and callback=`0x00804779`, while preserving stock `+0x3c/+0x40/+0x44`. The mode-`0x0b` initializer owns a separate later 0xC50 object and has no direct app-heap free edge; placement evidence independently proves the display backing/runtime50 objects remain persistent at fixed addresses. Before the callback `BLX`, byte0=`0xff` follows an explicit no-op microtask-release path and byte8 reopens the same stock model. The worker timeout uses preserved `+0x40/+0x44`; its `0xbfe8` gate is merely the transient app-heap busy flag, which malloc/free wrappers clear before return, so a colliding tick defers and a later period-1 tick proceeds. This promotes **deterministic post-overwrite callback invocation and controlled indirect branch offline**. The all-SPP `0x8a` BLUE normalization candidate is intentionally not promoted because its event enqueue precedes selector mutation and static analysis has not excluded scheduler preemption; active btphone also blocks that branch.

**VRAM-3 execution environment:** exact Ditoo initialization pins the application heap to `0x00804000..0x0081cfff` (0x19000 bytes), inside the stock identity-mapped SRAM window `0x00803000..0x0081ffff`. Stage-1 enables the ARMv5T short-descriptor MMU and I/D caches. The mapping is cacheable/write-through/non-bufferable and ARMv5T short descriptors have no XN bit, so mapped heap SRAM is executable. The now-proven first target is Thumb `0x00804779`; the corresponding preserved-image span is `0xff` fill across 4/4 branches and has zero raw address references, reducing stale-I-cache concern for first use. The minimal offline stage-0 witness is exactly `70 47` (`BX LR`), which returns through the stock `BLX` callsite without persistent mutation. Larger/reused code would still need explicit I-cache maintenance.

**Current promotion state:** controlled adjacent heap overwrite = proven; executable heap RAM = proven; real indirect-call sink = proven; deterministic victim placement = **proven offline**; deterministic post-overwrite callback invocation = **proven offline**; minimal returning Thumb stage-0 target = **proven offline**. This is still not a live execution result. The one-use VRAM-6/7 manifest now exists and is reviewed offline, but remains explicitly unauthorized and unexecuted; the exact owner grant below is still required before any experiment RFCOMM open/transmit.

### VRAM-6/7 one-use live-gate preparation — READY / UNGRANTED / UNEXECUTED

`experiments/OPENDITOO-VRAM67-BXLR-001.json` is the reviewed one-use exact-unit live manifest. It binds the purchased-unit v42012 assumption to the prior M4 result, the four authoritative Tier-2/VRAM artifacts, and `artifacts/analysis/volatile_ram_api_vram67_fixture.json`. The frozen sequence is exactly three application frames on one RFCOMM connection: stock-shaped `0x6e` payload `01`, 40 ms, stock-shaped `0xa5` payload `01 02 01`, 40 ms, then exactly one custom `0x6c` carrying an exact 1088-byte source. The source starts `70 47` (`BX LR`), uses `0xff` fill, fixes runtime50 byte0=`0xff`, byte8/model=`0x22`, and callback=`0x00804779`; its SHA-256 is `7ec43cab8cd04da6b2d90983dcec868baee3a1615448d05f446aa5a1c2e3ce48`. The custom `0x6c` wire SHA-256 is `c3fbc813e2646b44ace4a2105163fe7bc2622d5e6cc61477ac6098d0b23b12cd`. No fourth liveness packet is allowed.

The dedicated runner accepts only the repo root; target and packets are frozen in source. It requires a local grant record bound to the committed manifest/fixture hashes, a stock-btplayer attestation, a fresh one-use nonce, and a Runtime 018 handover token. It atomically creates the one-use claim before `WSAStartup`/socket creation. The coordinator checks all authority/hashes first, requires accepted Runtime 018 healthy, stops `openditoo-product.service`, waits 18 seconds so the 15-second raw-AVRCP sidecar lease expires, runs the exact experiment once, then restores Runtime 018 and requires `product-status` connected with `last_error=null`. Any connect/send ambiguity, disconnect, crash/reboot, observation failure, or restore failure is stop/no-retry and is not PASS.

The live discriminator intentionally adds no output primitive: after the exact overwrite, the same RFCOMM connection must survive a 75-second observation window that extends beyond the stock VoiceTip `0x3c` deadline, and accepted Runtime 018 must reconnect cleanly afterward. Interpreted together with the promoted deterministic timeout->callback proof, that is the bounded returning-`BX LR` candidate discriminator. A timing-only effect is never success. The exact grant text is: **`Grant OPENDITOO-VRAM67-BXLR-001 -- stock btplayer selected`**. Do not materialize the local grant, stop Runtime 018, open experiment Bluetooth, or transmit until the owner sends that exact text.

Offline verification after preparation: all four analyzer selfchecks PASS; focused legacy Tier-2/VRAM plus new VRAM-6/7 suite = **24/24 PASS**; the coordinator was invoked without a grant and failed closed with `VRAM67_EXACT_GRANT_NOT_MATERIALIZED` before any Runtime 018/systemd or Bluetooth action. No local grant/claim/result was created.

Checkpoint verification in constrained WSL_MCP: focused display/placement/trigger/VRAM-3 tests = 17/17 PASS; `git diff --check` = PASS; `python3 scripts/verify_day1_offline.py` = 381 tests with exactly the two known unrelated W9B optical `ModuleNotFoundError: PIL` errors and zero new Tier-2/VRAM/recovery/product failures. Runtime 018 was not touched and no Ditoo packet was transmitted.

## Why this is worth doing

The firmware-input work already solved the *shim architecture* problem:

- category-`0x82` front-panel events have four pinned producers and a single consumer seam;
- a fail-open redirect model exists offline;
- the stock SYS-SPP response path is the preferred device->host telemetry channel;
- the exact-unit SD updater recognizes `/divoom/divoomupdate.bin`, but persistent install remains recovery-gated because exact v42012 bytes/rollback are unavailable.

So the missing piece is a **reversible delivery/bootstrap path**. Route C from the prior input-takeover research — no-flash code execution through a stock parser — was never exhausted. It is now promoted.

## State at handoff

Repo at handoff preparation began clean at `114a4fc` (`Record M2 unpowered mapping grant`). Preserve any later commits/state in the live repo over this note.

Everyday product:

- Runtime 018 remains live/accepted;
- do not modify/restart/cut over Runtime 018 merely for offline parser work;
- Left/Right/Lever external input remains working through raw AVRCP;
- brightness/volume exclusive takeover still needs in-device interception if stock side effects must be suppressed.

Recovery/software state:

- exact purchased unit: Ditoo Plus flag42, installed v42012 (version identity, not recovered bytes);
- exact-model preserved firmware: flag42 v42016/v42017 test, flag60 v60014/test;
- period Divoom Android 3.1.58 APK preserved and provenance-verified;
- SFR-1 arbitrary stock readback closed within analyzed graph;
- SFR-2 period-app historical selector closed;
- SFR-3 current API matrix closed;
- first SFR-4 lineage expansion closed;
- exact v42012 unrecovered;
- factory entry is unsafe for this route because initialization performs persistent SPI erase/write;
- valid custom SD firmware remains off-limits without recovery.

Physical state/authority:

- M1 was never granted/consumed;
- M2 unpowered map is `authorized_unconsumed`, but owner now says they are not willing to clip, measure or attach something; **do not execute it unless the owner later explicitly changes direction**;
- no hardware interaction is needed for VRAM-0..VRAM-5.

## Exact-model facts that matter for this phase

### Stock application transport

- Classic RFCOMM/SPP channel 1 proven on purchased unit;
- candidate additive-checksum framing reproduced across exact-unit captures;
- 251-entry top-level command dispatcher (`0x04..0xFE`) mapped on preserved Plus branches;
- nested EXTERN `0xbd` first-level implemented range `0x13..0x1b` is already bounded;
- exact-unit `0x44` image and `0x58` drawing-pad semantics proven;
- `0x97` exact-unit file-version query proven;
- `0x98/0x99` update ingress is push-only, not a readback primitive;
- `0x09`/`0xBD` unsolicited device reports prove device->host stock SPP reporting exists.

### Parser/content leads visible in Ditoo binaries

Current exact-model string/structure pass shows real Ditoo subsystems worth mapping:

- `divoom_disp_download_file`;
- GIF load/write/info paths and alarm GIF paths;
- movie load/write/read paths;
- `divoom_disp_picture_decode_rgb_data`;
- drawing/pixel/image handlers;
- generic download-buffer fullness logic;
- alarm/voice/content paths;
- broad audio/media decoder stack (MP3/WMA/APE/FLAC/PCM/ADPCM/AAC/Vorbis/AMR/RA8/DRA/AC3/G711/SBC/SPEEX).

Do not assume those codecs are remotely reachable. First prove a no-persistent-write Bluetooth path from caller bytes to each parser.

### MiniToo comparator

Current public `antiali.as/minitoo-forth` work is **methodology only**. It demonstrates on different Actions silicon that a no-flash path should be evaluated as:

`controlled Bluetooth input -> parser state corruption -> controlled RAM/control flow -> executable RAM`

and that deterministic controllability matters more than crash count. It does **not** authorize copying its JPEG bugs, command IDs, memory map or MPU assumptions to Ditoo Plus.

## 2026-09-12 final handoff checkpoint — Tier-2 offline chain complete

Source checkpoint entering handoff preparation: `8dddcb2` (`Promote Tier-2 offline control-flow chain`). Live Git state always outranks this note.

The analytical portion of the first-stage volatile-RAM route is now closed positive across all four pinned Plus firmware branches. Do **not** reopen placement, generic codec hunting, VoiceTip registration, RAM executability, or the old assumption that `0x6c` primes its own content mode unless a fail-closed artifact detects corpus drift.

Authoritative sequence:

`stock/manual btplayer -> stock 0x6e(nonzero) content-mode 0x0b prime -> stock 0xa5 selector 2/model 0x22 VoiceTip setup -> exact 1088-byte 0x6c same-mode overwrite -> runtime50 +0x34 callback 0x00804779 -> Thumb BX LR -> normal return`

Pinned facts:

- `0x6e SPP_DRAWING_CTRL_MOVIE_PLAY` with `payload[1] != 0` selects content mode `0x0b` through `0x71b8` and immediately confirms it through `0x12886`; `0x6c` **does not** prime itself.
- deterministic startup geometry: display backing `0x00804470`, controlled display pointer `0x00804778`, runtime50 `0x00804b80`, callback `0x00804bb4`;
- exact 1088-byte source reaches through callback `+0x34` and stops at runtime50 `+0x37`, preserving `+0x3c/+0x40/+0x44`;
- controlled victim values: runtime50 byte0=`0xff`, byte8/model=`0x22`, callback=`0x00804779`;
- VoiceTip period-1 timeout eventually reaches the callback; `0xbfe8` is only the transient app-heap busy flag and malloc/free clear it before return;
- `0x00804779` is executable Thumb RAM in the stock ARMv5T mapping; the minimal offline return witness is `70 47` (`BX LR`);
- the mode-`0x0b` initializer may allocate a separate 0xC50 light-word object but does not free/move the persistent display backing or runtime50 victim;
- the all-SPP `0x8a` BLUE normalization idea remains deliberately unpromoted because queue/preemption ordering is not closed; use a stock/manual btplayer precondition for the first live discriminator.

Verification at this checkpoint:

- Tier-2 display/placement/trigger + VRAM-3 focused suite: **17/17 PASS**;
- all four analyzer selfchecks: PASS;
- `git diff --check`: PASS;
- broad verifier: **381 tests**, exactly the two known unrelated W9B optical `ModuleNotFoundError: PIL` errors, zero new Tier-2/VRAM/recovery/product failures;
- no device I/O, live packet generation, Runtime 018 change, persistent mutation, MassBoot action, or physical work occurred.

### Exact next gate

The project is now at the **explicit owner-grant boundary** for `OPENDITOO-VRAM67-BXLR-001`. Do not do more parser archaeology or widen the payload. Rehydrate, rerun the focused fail-closed checks if this checkout changed, verify the committed manifest/fixture hashes, confirm no local claim/result exists, and present the owner with the exact grant text **`Grant OPENDITOO-VRAM67-BXLR-001 -- stock btplayer selected`**. No existing MassBoot, Runtime 018, SD-P1, or prior live grant transfers.

If and only if that exact grant is supplied, materialize a local grant record bound to the committed manifest/fixture hashes and fresh one-use nonce, execute `scripts/run_vram67_bxlr_001_once.sh` once, do not automatically retry any ambiguous/failing outcome, restore accepted Runtime 018, record the result, and stop for interpretation. Only after a clean returning-stage-0 result may VRAM-8 bounded-loader design begin. A crash, reboot, timeout, disconnect, or timing-only anomaly is not success.

## Immediate executor order

1. Preflight: `git status`, HEAD/upstream, preserve all concurrent/untracked work.
2. Read `START_HERE.md` current-state block, this handoff, then the volatile-RAM plan.
3. Read only the relevant closed evidence, especially:
   - `notes/OPENDITOO-FULL-INPUT-TAKEOVER-RESEARCH-2026-09-11.md` Route C + later FIRM/telemetry addenda;
   - `notes/OPENDITOO-SOFTWARE-FIRST-RECOVERY-R0-2026-09-12.md` dispatcher/readback closure;
   - `artifacts/analysis/software_recovery_surface.json`;
   - `artifacts/analysis/keypad_pipeline.json`;
   - period APK recovery artifact/provenance;
   - exact-unit framing/drawing capture notes as needed.
4. Treat **VRAM-0/VRAM-1 and Tier-1 direct-SPP VRAM-2 as CLOSED** unless the pinned corpus or atlas fails closed.
5. Treat the corrected Tier-2 sequence `0x6e(nonzero) prime -> 0xa5 VoiceTip setup -> exact 1088-byte 0x6c same-mode overwrite`, deterministic runtime50 placement, VoiceTip callback trigger, and returning Thumb `BX LR` witness as PROMOTED OFFLINE. The fresh one-use manifest is now `experiments/OPENDITOO-VRAM67-BXLR-001.json`; do not alter/widen or execute it until its exact named grant is supplied, and do not reopen generic codec hunting without a concrete drift signal.
6. Promote a parser only for deterministic controlled RAM/control-flow influence; source overreads/crashes alone remain negative evidence.
7. Use OptiPlex Lab for disposable heavyweight tools when useful; accepted conclusions should be reproducible from the WSL repo without depending on an opaque GUI state.
8. Continue autonomously through offline milestones until a true live-device boundary or a genuine technical blocker.

## Execution posture

YOLO within the project boundary:

- inspect, research, decompile, script, test, create artifacts/docs, commit and push autonomously;
- preserve legitimate concurrent work;
- prefer focused evidence-producing tests while iterating;
- run the broad verifier only at meaningful checkpoints;
- do not ask the owner routine offline questions the evidence can answer;
- do not drift into MassBoot/SPI/disassembly just because those notes exist;
- do not create a generic raw-packet/live fuzz surface as a product feature.

## Live boundary

When offline work identifies a worthy exact-unit candidate, stop and prepare a **fresh one-use manifest**. The owner must explicitly grant it before any malformed/custom parser packet is transmitted.

A live manifest must freeze:

- exact target and stock firmware identity assumption;
- connection count and packet bytes/count;
- expected outcomes and recovery procedure;
- no-retry rule;
- proof that no flash/factory/update write path is involved;
- Runtime 018 pre/post handling if transport ownership requires stopping it.

No existing M2 or product-runtime grant transfers to parser probing.

## Desired handoff result from the next session

Best case: one deterministic Ditoo-specific candidate progresses from SPP bytes to controlled RAM/control-flow influence and is ready for a bounded live discriminator.

Acceptable negative result: Tier-1 direct SPP surface is comprehensively closed with machine-checkable coverage and the route moves deliberately to Bluetooth profile/media surfaces.

Bad result: a pile of crashes/strings with no coverage accounting or controllability analysis. Avoid that.

## Handoff verification

At handoff preparation in constrained WSL_MCP:

- `git diff --check` — PASS;
- `python3 scripts/verify_day1_offline.py` — 381 tests, exactly the two known unrelated W9B optical errors from missing `PIL`, zero new parser/recovery/product failures;
- M2 authority remains `status=authorized_unconsumed`, `physical_execution_authorized=true`, `authorization_consumed=false`; it was not executed or consumed;
- no Ditoo transmission, Runtime 018 change, flash operation, MassBoot action or physical measurement occurred while preparing this handoff.
