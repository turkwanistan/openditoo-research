# OpenDitoo handoff — volatile RAM API / parser-exhaustion phase — 2026-09-12

## 2026-09-13 VRAM-8B live iteration — 002 consumed before overwrite / 003 prepared — CURRENT

`OPENDITOO-VRAM8B-CANARY-002` is **consumed / transport-harness inconclusive, not VRAM-8 negative**. It completed one RFCOMM connection and exactly three stock application sends: B2 baseline SET, B3 baseline GET, and the stock `0x6e` prime. Baseline response synchronization therefore worked live. The run then stopped/no-retry waiting for a wrapped `0x6e` response that never arrived within the frozen 2000 ms receive budget. No `0xa5` and no custom `0x6c` overwrite were sent; stage-0 remains unmeasured. Runtime 018 revision 13 restored `connected`, `last_error=null`. Durable evidence: `captures/OPENDITOO-VRAM8B-CANARY-002-LIVE-RESULT-2026-09-13.json`.

Fresh successor `OPENDITOO-VRAM8B-CANARY-003` is **prepared / unauthorized**. All eight transmitted packet fixtures are byte-for-byte identical to 002. The only live-derived transport change is that the exact stock `0x6e` prime no longer creates a receive gate; after the send it continues on the normal inter-packet delay. Required exact B2/B3 replies, bounded optional matching A5/6C drains, one connection, one custom overwrite, 75-second hold, typed `0 -> 1 -> 0` discriminator, no retry/reconnect, and Runtime 018 restoration remain unchanged. Manifest SHA-256: `adcf33e0883bbb2885715f8a4a86a23c0fc101ca4b6304c0e5f20e2366ef03a0`; fixture-report SHA-256: `ebdb4be66725c15435d7ed0d24466ba06fb53b2225005d6e2cd13d25cf82161a`. Exact next grant text: **`Grant OPENDITOO-VRAM8B-CANARY-003 -- stock btplayer selected`**. No 003 grant/claim/result exists at preparation.

## 2026-09-13 VRAM-8B live attempt 001 consumed / response-synchronous 002 prepared — CURRENT

`OPENDITOO-VRAM8B-CANARY-001` is **CONSUMED / TRANSPORT-HARNESS INCONCLUSIVE, NOT A VRAM-8 NEGATIVE**. Its one-use claim was created and one RFCOMM connection opened, but the runner stopped after exactly two stock sends (`0xb2` baseline SET, `0xb3` baseline GET) with `VRAM8B_B3_WRAPPER_REJECTED`; **zero custom `0x6c` sends occurred and stage-0 was never reached**. Static 4/4 branch evidence explains the failure: stock `0xb2` converges on the same wrapped one-byte response sender as `0xb3`, so the runner consumed the queued `0xb2` reply as though it were the later `0xb3` reply. Durable result: `captures/OPENDITOO-VRAM8B-CANARY-001-LIVE-RESULT-2026-09-13.json`. 001 may never be replayed and its grant does not transfer. Accepted Runtime 018 restored successfully to revision 13, `connected`, `last_error=null`, and continued ACKing frames.

Fresh successor `OPENDITOO-VRAM8B-CANARY-002` is **PREPARED / UNAUTHORIZED**. Its eight transmitted frames are byte-for-byte identical to 001; only host receive sequencing changes. 002 consumes responses synchronously: exact `0xb2` zero ACK after each SET, exact typed `0xb3` replies, a required valid wrapped `0x6e` reply, and bounded optional matching drains for `0xa5`/`0x6c`; malformed, unrelated or mismatched frames stop/no-retry. Manifest SHA-256 `0f054872b6886a6eacea9ae71ab43f01ef393d1cf55e4e242535f73d6a1cc758`; fixture-report SHA-256 `6b87fe811a22614654bcb0fb30fd8ffcaa84442ef73291a7af4925920dc0fd9a`. `tools/ditoo_vram8b_live_gate_002.py --selfcheck` must PASS. No 002 grant, claim, result, Bluetooth open or Runtime 018 handover exists. The exact future grant text is **`Grant OPENDITOO-VRAM8B-CANARY-002 -- stock btplayer selected`**. Do not request/reuse the 001 grant. Do not begin live 8D/9 before a terminal 002 result. VRAM-8C remains CLOSED OFFLINE.


## 2026-09-13 VRAM-8C offline closure / VRAM-8B grant still unconsumed — CURRENT

**VRAM-8C is CLOSED OFFLINE.** New reproducible authority is `tools/ditoo_vram8c_context.py`, `artifacts/analysis/volatile_ram_api_vram8c_context.json`, `tools/ditoo_vram8c_installer_model.py`, `artifacts/analysis/volatile_ram_api_vram8c_installer.json`, and the exact stage-0/stage-1 binaries beside it. The hardware timer IRQ only marks MicroTask work pending; the IRQ-return path rewrites SPSR to `0x33` (Thumb + privileged SVC) and injects resident dispatcher `0x008015ed`, which later BLXes the VoiceTip worker. Thus the controlled runtime50 callback is deferred out of the IRQ handler and executes in privileged SVC context across 4/4 preserved Plus branches. `Fwl_Malloc` at app Thumb `0x0840bfbd` and `Fwl_Free` at `0x0840bfcf` are pinned 4/4; both bracket their inner allocator/free call with shared busy byte `0x008030c4`, and the already-promoted VoiceTip worker defers while that byte is set. The stock ARM I-cache invalidation helper at `0x00800ce0` is therefore callable from this specific callback context.

The bounded installer is now concrete rather than aspirational: one fixed **80-byte** stage-1 image (SHA-256 `d2a7a4fb116ba52261e4e2e345b6c190ab09bf6ff28d5a53a59730c12fa8ee2d`) is embedded as data at `0x00804900`; one fixed **160-byte** installer stage-0 (SHA-256 `a8cbfb748a890e7a473e994e9c7fd280f846334b3ed601006e9236aabb5126d8`) executes from fresh pristine/unreferenced Thumb entry `0x00804a81`, avoiding the 8B `0x00804901` I-cache line. It validates fixed magic/ABI/length/entry plus a whole-image additive integrity check, requests exactly `Fwl_Malloc(0x50)`, copies exactly 20 words, rechecks fixed guards, invalidates I-cache, derives only `allocation_base + 0x21`, installs that fixed callback and invokes it once. Any pre-allocation failure clears the custom callback; any post-allocation guard failure frees that exact allocation, clears the callback, and never executes stage-1. There is no host-selected address/length/entry, chunking, generic upload, arbitrary write/call target, interpreter, or shell. Stage-1 v0 is intentionally inert: self-locating header/state, one bounded heartbeat, existing typed energy byte set to `1` for future 8D liveness, then `BX LR`; no input interception or stock-service call. Reboot/power loss clears the retained allocation.

Verification: focused VRAM-8A/8B/8C suite 18/18 PASS; both 8C selfchecks PASS; `git diff --check` PASS. Broad `scripts/verify_day1_offline.py` ran 399 tests and had only the two established unrelated W9B missing-Pillow errors (`ModuleNotFoundError: PIL`), with no new VRAM/parser/product failures.

**Authority/order is unchanged:** `OPENDITOO-VRAM8B-CANARY-001` already has the owner's exact grant materialized locally but remains **authorized/unconsumed** because no claim, Runtime 018 handover, Bluetooth socket, experiment packet, or result has occurred. Do not request the 8B grant again. Do not execute or prepare live 8D authority ahead of 8B: first obtain a real 8B PASS/terminal result; only then may a separately reviewed 8D one-use manifest be prepared/granted. The older 8A artifact's embedded `DESIGN_ADVANCED_NOT_CLOSED` 8C snapshot is intentionally immutable because the existing 8B manifest/grant hash-binds it; this dedicated 8C checkpoint supersedes that historical snapshot without changing any 8A/8B bytes.

## 2026-09-12 VRAM-8A closure / VRAM-8B fresh-grant boundary — HISTORICAL SNAPSHOT

Historical preparation snapshot: VRAM-0..7 were closed, VRAM-8A was CLOSED OFFLINE, and VRAM-8B had not yet been granted. The 2026-09-13 checkpoint above supersedes this authority/status wording; the frozen 8B bytes themselves are unchanged and the owner's exact grant is now authorized/unconsumed.

Authoritative new evidence:

- `tools/ditoo_vram8_stage0_model.py`;
- `artifacts/analysis/volatile_ram_api_vram8_stage0.json`;
- `artifacts/analysis/volatile_ram_api_vram8_stage0.bin`;
- `tools/ditoo_vram8b_live_gate.py`;
- `artifacts/analysis/volatile_ram_api_vram8b_fixture.json`;
- `experiments/OPENDITOO-VRAM8B-CANARY-001.json` plus its frozen fixtures.

**Callback ABI, 4/4 branches:** at the controlled `BLX`, `r0` is the callback pointer itself, `r1` is runtime50 `0x00804b80`, `r2/r3` are unspecified caller-saved values, `r4` is callee-saved and stock-live after return, and LR is the Thumb return address. The stock callback immediately reloads `r0` after `BLX`, so the callback return value is ignored. Periodic-dispatch/worker/callback/wrapper stack frames are -24/-32/-8/-8 bytes and preserve SP mod 8. Task-vs-IRQ context is intentionally **not** overclaimed; therefore the promoted 8A payload is a bounded leaf with no allocator, locks, waits, helper calls, MMIO, cache helper or interrupt-state change.

**Exact nontrivial stage-0:** source `0x00804900`, Thumb entry `0x00804901`, controlled-source offset `0x188`, exact bytes `10b5034c6468e27b01235a40e27310bdf0308000`, SHA-256 `1cdd53f83a75021b47cedc65bbac9f5ee1d488863d029d5900d4687efcf5264b`. It executes eight Thumb instructions, saves/restores `r4/LR`, reads the stock state-object pointer at `0x008030f4`, XORs bit0 of exactly one byte at `*(u32*)0x008030f4 + 0x0f`, restores SP/r4 and returns. It has no branch/loop and no stock call. The source is deliberately relocated away from consumed VRAM67 entry `0x00804779`: `0x00804900..+0x3f` is pristine `0xff` and raw-unreferenced across all four preserved branches. This is a one-fixture first-execution cache premise, not permission for arbitrary rewritten code; resident/reused code still requires explicit I-cache maintenance.

**Positive canary:** `0xb2 SPP_SET_ENERGY_CTRL` and `0xb3 SPP_GET_ENERGY_CTRL` use a shared volatile state object rooted at `0x008030f0`; `[0x008030f4]` is its live object pointer and byte `+0x0f` is the typed energy-control value. Across 4/4 branches, the stock `0xb2` setter helper has exactly one direct caller, the `0xb3` getter has exactly one direct caller, and the canonical direct writer of that field is the stock setter. A future live 8B transcript is therefore precommitted to stock SET=0 -> GET=0, exact frozen trigger/stage-0, post-hold GET=1, then stock SET=0 -> GET=0 restoration. Crash, reboot, disconnect, watchdog, timeout, timing-only change or hardware side effect is never success.

**VRAM-8B prepared / unauthorized:** `OPENDITOO-VRAM8B-CANARY-001` freezes exactly eight application sends on one RFCOMM connection: baseline `0xb2`, baseline `0xb3`, stock `0x6e`, stock `0xa5`, exactly one custom `0x6c`, post-hold `0xb3`, restore `0xb2`, restore `0xb3`. Retry/reconnect are false; the post-overwrite hold is 75,000 ms. The source SHA-256 is `1f7d0761fd905e91b23ea3c3024b2b7f22f6025467dc4e06690757a6b10634ca`. Expected wrapped `0xb3` zero/one responses are themselves frozen fixtures. No runner, local grant, claim, handover, Bluetooth open, Runtime 018 stop or packet transmission was materialized. Previous grants never transfer.

**VRAM-8C design state at this historical checkpoint:** `DESIGN_ADVANCED_NOT_CLOSED` (superseded by the 2026-09-13 `CLOSED_OFFLINE` checkpoint above). Preferred resident storage is one deliberate retained app-heap allocation owned for the boot session, but only after callback task/IRQ context and allocator ABI/reentrancy are independently proven. Hardcoded free-looking heap, live display backing, runtime50/adjacent live objects and unreserved upper SRAM are rejected. The installer contract is fixed device-side destination, fixed entry, fixed magic/version/integrity, guard/bounds validation before copy/execute, mandatory I-cache maintenance, fail-closed validation, reboot rollback, and one fixed image unless measured size forces bounded chunking. Max image length remains intentionally unset until the stage-1 image actually exists and is measured.

**Exact stop boundary:** do not begin VRAM-8D or VRAM-9 and do not touch Runtime 018/device Bluetooth. A future live 8B execution requires the fresh exact owner grant `Grant OPENDITOO-VRAM8B-CANARY-001 -- stock btplayer selected`. That grant has **not** been given or materialized by this checkpoint.

**Checkpoint verification:** `ditoo_vram8_stage0_model.py --selfcheck` PASS; `ditoo_vram8b_live_gate.py --selfcheck` PASS; focused Tier-2 trigger + VRAM-3 + VRAM-8A + VRAM-8B suite **17/17 PASS**; `git diff --check` PASS. The required single broad `python3 scripts/verify_day1_offline.py` run executed **390 tests** and produced exactly the two established unrelated W9B optical `ModuleNotFoundError: PIL` errors (`test_both_regions_decode_from_one_filmed_frame`, `test_decoding_survives_a_perspective_skewed_region`), with no new VRAM/parser/product error. The broad verifier was intentionally not rerun.

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

**Current promotion state:** controlled adjacent heap overwrite = proven; executable heap RAM = proven; real indirect-call sink = proven; deterministic victim placement = **proven offline**; deterministic post-overwrite callback invocation = **proven offline**; minimal returning Thumb stage-0 target = **LIVE PASS under the precommitted composite trigger model** via consumed `OPENDITOO-VRAM67-BXLR-002`. `OPENDITOO-VRAM67-BXLR-001` remains consumed/transport-harness-inconclusive and 002 remains consumed/PASS; neither may be replayed. The active next objective is the offline **VRAM-8A callback-ABI + positive-canary proof**, governed by `notes/OPENDITOO-VRAM8-11-RAM-API-ROADMAP-2026-09-12.md`.

### VRAM-6/7 live attempt 001 — CONSUMED / INCONCLUSIVE BEFORE 0xA5 SEND

The owner granted `OPENDITOO-VRAM67-BXLR-001` with stock btplayer selected. After a separate pre-claim host-plumbing miss (`powershell.exe` absent from PATH, no Bluetooth/claim), the real claimed run opened the single RFCOMM connection and completed the exact 8-byte stock `0x6e` prime. It then stopped with `VRAM67_VOICETIP_0XA5_TIMEOUT; NO_RETRY`. Inspection of the frozen runner proves that timeout occurred while waiting for a second `FD_WRITE` **before** the `0xa5` `send()` call. Therefore `0xa5` and the custom 1088-byte `0x6c` overwrite were never sent. Runtime 018 restored connected with `last_error=null`. Durable result: `captures/OPENDITOO-VRAM67-BXLR-001-LIVE-RESULT-2026-09-12.json`. This is `TRANSPORT_HARNESS_INCONCLUSIVE_NOT_VRAM_NEGATIVE`; 001 may never be replayed and its grant does not transfer.

Root cause is the runner's Winsock model, not device behavior: `FD_WRITE` is the initial writable notification and is subsequently re-signaled after a `send()` returns `WSAEWOULDBLOCK` and space becomes available; it is not a fresh event before each normal send. The successor must preserve every payload byte while changing only this harness behavior.

### VRAM-6/7 successor 002 — CONSUMED / LIVE PASS UNDER PROMOTED OFFLINE TRIGGER MODEL

`OPENDITOO-VRAM67-BXLR-002` consumed its fresh one-use grant and completed the frozen sequence exactly once: one RFCOMM connection, all three exact application sends, exactly one custom `0x6c`, no retry, then 75,009 ms of continuous post-overwrite connection survival. The runner result is `candidate_pass_transport_observation`; the coordinator then restored accepted Runtime 018, which independently verified revision 13, `status=connected`, `last_error=null`, and a post-restore frame ACK in a fresh session. Durable evidence is `captures/OPENDITOO-VRAM67-BXLR-002-LIVE-RESULT-2026-09-12.json`.

Interpretation follows the precommitted composite discriminator: the deterministic placement, preserved VoiceTip deadline/handles, timeout-to-runtime50-callback path, executable Thumb heap mapping, and `0x00804779 -> 70 47 (BX LR)` witness were already promoted offline. Given the exact overwrite completed and the same RFCOMM connection remained healthy through the callback window before normal product liveness returned, **VRAM-6/7 is a live returning-stage0 PASS under that promoted trigger model**. There is intentionally no independent wire-level stage0 marker; do not overstate the result beyond that model.

Both 001 and 002 are consumed. Do not replay either. No authority transfers forward. **Offline VRAM-8A/8C design is now permitted; STOP before any VRAM-8+ live-device action unless a fresh reviewed one-use manifest is explicitly granted.**

### VRAM-6/7 one-use live-gate preparation 001 — HISTORICAL

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

### VRAM-8..11 roadmap planning checkpoint — READY FOR HANDOFF

The post-VRAM-7 roadmap is now adopted in `notes/OPENDITOO-VRAM8-11-RAM-API-ROADMAP-2026-09-12.md`. It deliberately separates four different proofs that were previously compressed into “bounded loader”: VRAM-8A callback ABI + positive nontrivial returning canary (offline), VRAM-8B exact-unit live canary (fresh grant), VRAM-8C resident-window + bounded installer proof (offline), and VRAM-8D resident-stage1 live install/liveness proof (fresh grant). VRAM-9 then splits into reversible ingress (9A), API_INFO/PING (9B), and fail-open physical input claim (9C) before any VRAM-10 brightness/volume/service bridge. VRAM-11 remains session-autonomous RAM behavior only, never cold-boot persistence.

Planning-session verification: focused VRAM67 gate tests = **14/14 PASS**; `git diff --check` = PASS; broad `python3 scripts/verify_day1_offline.py` = **381 tests with exactly the two known unrelated W9B optical `ModuleNotFoundError: PIL` errors**, no new VRAM/parser/product failures. No Ditoo traffic, Runtime 018 mutation, manifest grant, claim, flash/update path, MassBoot action, or physical work occurred while creating this roadmap.

### Exact next gate

VRAM-6/7 remains closed PASS under the precommitted composite discriminator. VRAM-8A is now CLOSED OFFLINE as recorded in the current checkpoint above. The exact next live boundary is the prepared-but-unauthorized `OPENDITOO-VRAM8B-CANARY-001`; VRAM-8C remains design-advanced but not closed, and VRAM-8D remains a later independent gate.

## Immediate executor order

1. Preflight: `git status`, HEAD/upstream, preserve all concurrent/untracked work.
2. Read `START_HERE.md` current-state block, this handoff, then the volatile-RAM plan.
3. Read `notes/OPENDITOO-VRAM8-11-RAM-API-ROADMAP-2026-09-12.md`, then only the closed evidence needed for the immediate proof: `artifacts/analysis/volatile_ram_api_tier2_trigger.json`, `artifacts/analysis/volatile_ram_api_tier2_placement.json`, `artifacts/analysis/volatile_ram_api_vram3_execution.json`, the corresponding analyzers, and preserved branch images/disassembly as referenced by them. Pull input-takeover/keypad research only when VRAM-9C begins.
4. Treat **VRAM-0..7 as CLOSED**. Do not reopen generic SPP/codec hunting unless a current pinned claim fails closed.
5. Start VRAM-8A by pinning the controlled callback ABI: register/stack/Thumb/LR/return-value expectations and interrupt/preemption constraints. Then rank positive reversible canary mechanisms and reject crash/timing/disconnect as observability.
6. Build deterministic stage-0 bytes + analyzer/artifact/tests offline. If the canary closes strongly, prepare (but do not grant/execute) one fresh VRAM-8B manifest and stop at the owner grant boundary.
7. In parallel, advance VRAM-8C only as far as evidence permits: rank resident RAM windows and prove a fixed-destination bounded installer with no host-selected addresses/call targets. Prefer a single fixed image before chunking.
8. Use OptiPlex Lab for disposable heavyweight tools when useful; accepted conclusions must be reproducible from the WSL repo. Continue autonomously through offline gates; do not ask routine questions whose answers can be derived from evidence.

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

Best case: VRAM-8A closes with exact callback-ABI evidence, a machine-checkable nontrivial returning stage-0, and one positive reversible RAM-only canary; a fresh VRAM-8B one-use manifest is fully frozen but unauthorized, while VRAM-8C has a ranked resident-window/installer design.

Acceptable partial result: callback ABI is closed but no trustworthy positive canary or resident window survives review. Persist the blocker and stop before live traffic rather than substituting crash/timing behavior.

Bad result: jumping directly to a generic loader/API, arbitrary address/call primitives, or a live experiment whose only oracle is crash/reboot/disconnect/timing. Avoid that.

## Handoff verification

At handoff preparation in constrained WSL_MCP:

- `git diff --check` — PASS;
- `python3 scripts/verify_day1_offline.py` — 381 tests, exactly the two known unrelated W9B optical errors from missing `PIL`, zero new parser/recovery/product failures;
- M2 authority remains `status=authorized_unconsumed`, `physical_execution_authorized=true`, `authorization_consumed=false`; it was not executed or consumed;
- no Ditoo transmission, Runtime 018 change, flash operation, MassBoot action or physical measurement occurred while preparing this handoff.


## VRAM-8B GRANT STATE — 2026-09-12

`OPENDITOO-VRAM8B-CANARY-001` has an exact owner grant materialized locally and remains **authorized but unconsumed**. No claim, handover, result, or live device action was created. Runtime 018 remained connected. Do not request another 8B grant unless this grant is consumed, revoked, or the frozen manifest changes.
