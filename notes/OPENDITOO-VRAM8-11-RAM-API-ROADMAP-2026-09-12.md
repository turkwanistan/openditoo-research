# OpenDitoo VRAM-8..11 RAM API roadmap — 2026-09-12

## 2026-09-13 VRAM-8B live iteration — 004 consumed on unsolicited 0xBD / 005 prepared — CURRENT

`OPENDITOO-VRAM8B-CANARY-004` is **consumed / multiplexed-valid-report harness inconclusive, not VRAM-8 negative**. It completed one RFCOMM connection and exactly four stock application sends: B2 baseline SET, B3 baseline GET, stock `0x6e` prime, and stock `0xa5` VoiceTip setup. It then received a valid wrapped `0xBD` report during the optional A5 drain and stopped only because the 004 harness incorrectly required the next valid report to echo `0xa5`. `0xBD` is independently established elsewhere in this repo as unsolicited Ditoo state/input traffic. No custom `0x6c` overwrite was sent; stage-0 remains unmeasured. Runtime 018 revision 13 restored `connected`, `last_error=null`. Durable evidence: `captures/OPENDITOO-VRAM8B-CANARY-004-LIVE-RESULT-2026-09-13.json`.

Fresh successor `OPENDITOO-VRAM8B-CANARY-005` is **prepared / unauthorized**. All eight transmitted packet fixtures remain byte-for-byte identical to 004. Host receive handling is now explicitly multiplexed and bounded: required B2/B3 replies are correlated by inner command while skipping at most eight other valid wrapped reports within the same 2000 ms deadline; optional A5/6C drains accept up to four valid wrapped reports during the existing 150 ms window regardless of inner command. Malformed framing/checksum, required-response timeout, unrelated-frame budget exhaustion, disconnect, crash/reboot, or typed-oracle failure still stop/no-retry. The positive discriminator is unchanged: one connection, all eight sends, exactly one custom `0x6c`, 75-second survival, strict B3 `0 -> 1 -> 0`, and Runtime 018 restoration. Manifest SHA-256 `0248438e5b448858a31ed64d266a84314291332022f149e9bd25a4c99e37cc57`; fixture-report SHA-256 `43b55d41162dc12c4f98f8923fa5269affca28d3cdb1e3d96d0015630159e395`. Exact next grant text: **`Grant OPENDITOO-VRAM8B-CANARY-005 -- stock btplayer selected`**. No 005 grant/claim/result exists at preparation.

## 2026-09-13 VRAM-8B live iteration — 003 consumed at B2 reply semantics / 004 prepared — CURRENT

`OPENDITOO-VRAM8B-CANARY-003` is **consumed / transport-harness inconclusive, not VRAM-8 negative**. After the pre-claim local-directory bug was repaired without consuming authority, the rerun created its one-use claim, opened one RFCOMM connection, completed exactly the first stock B2 baseline SET, and received a valid wrapped one-byte B2 response. The payload was `0xE8` (232), not the harness-assumed `0x00`, so 003 stopped/no-retry before the baseline B3 GET. Exactly **1 application send** completed; **0 custom `0x6c` sends** occurred; stage-0 remains unmeasured. Runtime 018 revision 13 restored `connected`, `last_error=null`. Durable evidence: `captures/OPENDITOO-VRAM8B-CANARY-003-LIVE-RESULT-2026-09-13.json`.

Fresh successor `OPENDITOO-VRAM8B-CANARY-004` is **prepared / unauthorized**. Its eight transmitted packet fixtures are byte-for-byte identical to 003. The only live-derived behavior change is host-side B2 reply interpretation: both B2 SET responses must still be valid wrapped/checksummed `0xB2`/tag-`0x55` frames with exactly one payload byte, but that byte's value is intentionally unconstrained. The typed success oracle remains entirely on exact B3 readback `0 -> 1 -> 0`. The previously live-corrected `0x6e` no-response policy, bounded optional A5/6C drains, one connection, exactly one custom overwrite, 75-second hold, no retry/reconnect, and Runtime 018 restoration remain unchanged. Manifest SHA-256: `0906626243dd1859ce52cef62261ddee0bd14df72043c966d3a06b8665a26c24`; fixture-report SHA-256: `b85b0f104d6ed8b1d2781080bb8fa3acbe1a7c89c06d90a1bfd842e1564b9e2e`. `tools/ditoo_vram8b_live_gate_004.py --selfcheck` passes offline. No 004 grant/claim/result exists. Exact next grant text: **`Grant OPENDITOO-VRAM8B-CANARY-004 -- stock btplayer selected`**.

## 2026-09-13 VRAM-8B live iteration — 002 consumed before overwrite / 003 prepared — HISTORICAL

`OPENDITOO-VRAM8B-CANARY-002` is **consumed / transport-harness inconclusive, not VRAM-8 negative**. It completed one RFCOMM connection and exactly three stock application sends: B2 baseline SET, B3 baseline GET, and the stock `0x6e` prime. Baseline response synchronization therefore worked live. The run then stopped/no-retry waiting for a wrapped `0x6e` response that never arrived within the frozen 2000 ms receive budget. No `0xa5` and no custom `0x6c` overwrite were sent; stage-0 remains unmeasured. Runtime 018 revision 13 restored `connected`, `last_error=null`. Durable evidence: `captures/OPENDITOO-VRAM8B-CANARY-002-LIVE-RESULT-2026-09-13.json`.

Fresh successor `OPENDITOO-VRAM8B-CANARY-003` is **prepared / unauthorized**. All eight transmitted packet fixtures are byte-for-byte identical to 002. The only live-derived transport change is that the exact stock `0x6e` prime no longer creates a receive gate; after the send it continues on the normal inter-packet delay. Required exact B2/B3 replies, bounded optional matching A5/6C drains, one connection, one custom overwrite, 75-second hold, typed `0 -> 1 -> 0` discriminator, no retry/reconnect, and Runtime 018 restoration remain unchanged. Manifest SHA-256: `adcf33e0883bbb2885715f8a4a86a23c0fc101ca4b6304c0e5f20e2366ef03a0`; fixture-report SHA-256: `ebdb4be66725c15435d7ed0d24466ba06fb53b2225005d6e2cd13d25cf82161a`. Exact next grant text: **`Grant OPENDITOO-VRAM8B-CANARY-003 -- stock btplayer selected`**. No 003 grant/claim/result exists at preparation.

## 2026-09-13 VRAM-8B live attempt 001 consumed / response-synchronous 002 prepared — HISTORICAL

`OPENDITOO-VRAM8B-CANARY-001` is **CONSUMED / TRANSPORT-HARNESS INCONCLUSIVE, NOT A VRAM-8 NEGATIVE**. Its one-use claim was created and one RFCOMM connection opened, but the runner stopped after exactly two stock sends (`0xb2` baseline SET, `0xb3` baseline GET) with `VRAM8B_B3_WRAPPER_REJECTED`; **zero custom `0x6c` sends occurred and stage-0 was never reached**. Static 4/4 branch evidence explains the failure: stock `0xb2` converges on the same wrapped one-byte response sender as `0xb3`, so the runner consumed the queued `0xb2` reply as though it were the later `0xb3` reply. Durable result: `captures/OPENDITOO-VRAM8B-CANARY-001-LIVE-RESULT-2026-09-13.json`. 001 may never be replayed and its grant does not transfer. Accepted Runtime 018 restored successfully to revision 13, `connected`, `last_error=null`, and continued ACKing frames.

Fresh successor `OPENDITOO-VRAM8B-CANARY-002` is **PREPARED / UNAUTHORIZED**. Its eight transmitted frames are byte-for-byte identical to 001; only host receive sequencing changes. 002 consumes responses synchronously: exact `0xb2` zero ACK after each SET, exact typed `0xb3` replies, a required valid wrapped `0x6e` reply, and bounded optional matching drains for `0xa5`/`0x6c`; malformed, unrelated or mismatched frames stop/no-retry. Manifest SHA-256 `0f054872b6886a6eacea9ae71ab43f01ef393d1cf55e4e242535f73d6a1cc758`; fixture-report SHA-256 `6b87fe811a22614654bcb0fb30fd8ffcaa84442ef73291a7af4925920dc0fd9a`. `tools/ditoo_vram8b_live_gate_002.py --selfcheck` must PASS. No 002 grant, claim, result, Bluetooth open or Runtime 018 handover exists. The exact future grant text is **`Grant OPENDITOO-VRAM8B-CANARY-002 -- stock btplayer selected`**. Do not request/reuse the 001 grant. Do not begin live 8D/9 before a terminal 002 result. VRAM-8C remains CLOSED OFFLINE.


## 2026-09-13 VRAM-8C offline closure / VRAM-8B grant still unconsumed — CURRENT

**VRAM-8C is CLOSED OFFLINE.** New reproducible authority is `tools/ditoo_vram8c_context.py`, `artifacts/analysis/volatile_ram_api_vram8c_context.json`, `tools/ditoo_vram8c_installer_model.py`, `artifacts/analysis/volatile_ram_api_vram8c_installer.json`, and the exact stage-0/stage-1 binaries beside it. The hardware timer IRQ only marks MicroTask work pending; the IRQ-return path rewrites SPSR to `0x33` (Thumb + privileged SVC) and injects resident dispatcher `0x008015ed`, which later BLXes the VoiceTip worker. Thus the controlled runtime50 callback is deferred out of the IRQ handler and executes in privileged SVC context across 4/4 preserved Plus branches. `Fwl_Malloc` at app Thumb `0x0840bfbd` and `Fwl_Free` at `0x0840bfcf` are pinned 4/4; both bracket their inner allocator/free call with shared busy byte `0x008030c4`, and the already-promoted VoiceTip worker defers while that byte is set. The stock ARM I-cache invalidation helper at `0x00800ce0` is therefore callable from this specific callback context.

The bounded installer is now concrete rather than aspirational: one fixed **80-byte** stage-1 image (SHA-256 `d2a7a4fb116ba52261e4e2e345b6c190ab09bf6ff28d5a53a59730c12fa8ee2d`) is embedded as data at `0x00804900`; one fixed **160-byte** installer stage-0 (SHA-256 `a8cbfb748a890e7a473e994e9c7fd280f846334b3ed601006e9236aabb5126d8`) executes from fresh pristine/unreferenced Thumb entry `0x00804a81`, avoiding the 8B `0x00804901` I-cache line. It validates fixed magic/ABI/length/entry plus a whole-image additive integrity check, requests exactly `Fwl_Malloc(0x50)`, copies exactly 20 words, rechecks fixed guards, invalidates I-cache, derives only `allocation_base + 0x21`, installs that fixed callback and invokes it once. Any pre-allocation failure clears the custom callback; any post-allocation guard failure frees that exact allocation, clears the callback, and never executes stage-1. There is no host-selected address/length/entry, chunking, generic upload, arbitrary write/call target, interpreter, or shell. Stage-1 v0 is intentionally inert: self-locating header/state, one bounded heartbeat, existing typed energy byte set to `1` for future 8D liveness, then `BX LR`; no input interception or stock-service call. Reboot/power loss clears the retained allocation.

Verification: focused VRAM-8A/8B/8C suite 18/18 PASS; both 8C selfchecks PASS; `git diff --check` PASS. Broad `scripts/verify_day1_offline.py` ran 399 tests and had only the two established unrelated W9B missing-Pillow errors (`ModuleNotFoundError: PIL`), with no new VRAM/parser/product failures.

**Authority/order is unchanged:** `OPENDITOO-VRAM8B-CANARY-001` already has the owner's exact grant materialized locally but remains **authorized/unconsumed** because no claim, Runtime 018 handover, Bluetooth socket, experiment packet, or result has occurred. Do not request the 8B grant again. Do not execute or prepare live 8D authority ahead of 8B: first obtain a real 8B PASS/terminal result; only then may a separately reviewed 8D one-use manifest be prepared/granted. The older 8A artifact's embedded `DESIGN_ADVANCED_NOT_CLOSED` 8C snapshot is intentionally immutable because the existing 8B manifest/grant hash-binds it; this dedicated 8C checkpoint supersedes that historical snapshot without changing any 8A/8B bytes.

## Status and authority boundary

VRAM-6/7 is CLOSED LIVE PASS under the precommitted composite discriminator. `OPENDITOO-VRAM67-BXLR-001` and `OPENDITOO-VRAM67-BXLR-002` are both consumed and non-replayable. The accepted exact-unit result proves, under the already-promoted deterministic placement/VoiceTip trigger model, that a controlled Thumb callback at `0x00804779` can execute `70 47` (`BX LR`) and return without destabilizing the device.

This roadmap begins **after** that proof. It does not authorize any new Ditoo traffic. **VRAM-8A has now closed offline and `OPENDITOO-VRAM8B-CANARY-001` exists as a frozen `prepared_unauthorized` manifest; its existence is not authority.** No VRAM-8+ live grant has transferred or been materialized. Every new live experiment still requires its own frozen one-use manifest and exact owner grant under `AGENTS.md`.

The product objective remains narrow: turn the proven volatile execution primitive into a **RAM-resident, reboot-cleared OpenDitoo API**. Do not turn it into a general debugger, arbitrary memory editor, arbitrary ARM-code launcher, persistent firmware patch, or raw-packet product surface.

## Design principles that apply to every milestone

1. **Separate one question per live grant.** Do not combine “nontrivial code works”, “loader works”, “API ingress works”, and “input claim works” into one experiment.
2. **Prefer RAM-only reversible state.** No flash/update/factory paths, no MassBoot, no filesystem persistence, no permanent gallery writes.
3. **No host-selected addresses.** The host never supplies a destination address, call address, patch address, or arbitrary code pointer.
4. **One fixed target and one controller.** Continue to bind the exact purchased Ditoo and coordinate with Runtime 018 ownership.
5. **Fail closed during installation; fail open during product use.** Loader corruption/refusal must not execute. A lost API host must restore/forward stock behavior automatically.
6. **Restore original stock semantics.** Any RAM hook must retain the original target/word(s), support explicit release, and disappear fully on reboot.
7. **Crash/timing is never the oracle.** Success needs a positive, deterministic observation plus clean return/liveness.
8. **Keep v0 tiny.** API_INFO/PING and bounded input claim come before brightness/volume/service wrappers.

## Preferred architecture

The preferred end state is:

```text
stock Bluetooth SPP ingress
    -> narrowly hooked RAM-resident ingress seam
        -> fixed OpenDitoo API dispatcher
            -> API_INFO / PING
            -> bounded input-claim state
            -> later typed stock-service wrappers
        -> unclaimed/unknown traffic forwards through original stock path
```

Bootstrap remains separate from the steady-state API:

```text
stock btplayer precondition
 -> frozen 0x6e content prime
 -> frozen stock 0xa5 VoiceTip setup
 -> bounded custom 0x6c overwrite
 -> tiny returning stage-0
 -> fixed loader/install action
 -> return to stock firmware
```

The exploit/bootstrap path is therefore an installer for volatile RAM state, not the API’s normal command path.

---

## VRAM-8A — nontrivial returning stage-0 — CLOSED OFFLINE

### Question

Can a payload larger than `BX LR` obey the real callback ABI, perform one bounded reversible RAM-only action, and return cleanly?

### Work

1. Recover the callback calling convention precisely at the `0x1fa8a` family BLX site across all preserved Plus branches:
   - live register values and which are caller/callee-saved;
   - stack alignment and frame expectations;
   - LR/Thumb-state behavior;
   - whether callback return value is consumed;
   - whether interrupts/preemption create any additional preservation requirement.
2. Build a minimal Thumb stage-0 skeleton with explicit prologue/epilogue and branch-independent constants where possible.
3. Select **one positive canary effect** using this ranking:
   - preferred: mutate a proven volatile display/control field that stock code naturally observes, then restore it or let stock overwrite it;
   - acceptable: call one already-understood leaf stock routine whose effect is RAM-only/reversible, with exact ABI proven first;
   - fallback: create a RAM canary that can be positively observed through an already-proven typed readback path.
4. Reject canaries that rely on reboot, disconnect, timing, watchdog behavior, peripheral-register pokes, flash writes, or uncertain hardware side effects.
5. Emulate/symbolically walk the exact stage-0 bytes against the recovered ABI and prove all touched addresses lie in the reviewed volatile set.

### Required artifacts

- `tools/ditoo_vram8_stage0_model.py` or equivalent deterministic analyzer;
- `artifacts/analysis/volatile_ram_api_vram8_stage0.json`;
- exact stage-0 fixture bytes and disassembly listing under an offline fixture path;
- focused tests pinning ABI preservation, touched addresses, maximum instruction/byte count, and return path.

### Closure result

**CLOSED OFFLINE.** `tools/ditoo_vram8_stage0_model.py` proves the callback ABI across 4/4 preserved branches and freezes a 20-byte leaf at fresh Thumb entry `0x00804901`. Exact bytes are `10b5034c6468e27b01235a40e27310bdf0308000` (SHA-256 `1cdd53f83a75021b47cedc65bbac9f5ee1d488863d029d5900d4687efcf5264b`). The payload preserves `r4`/SP/LR, makes no calls, and toggles exactly the one-byte volatile energy-control field rooted through pointer cell `0x008030f4`. Stock `0xb2` establishes/restores baseline 0 and stock `0xb3` returns the raw byte, giving a precommitted positive `0 -> 1 -> 0` typed readback. Task-vs-IRQ context remains unknown, so the leaf/no-call restriction is part of the proof. The fresh `0x00804900` source span is pristine/unreferenced 4/4 and intentionally avoids the already-executed VRAM67 cache line.

---

## VRAM-8B — one-use live nontrivial returning canary — AUTHORIZED / UNCONSUMED

### Question

Does the exact-unit Ditoo execute a nontrivial stage-0 action and still return cleanly?

### Live shape

Freeze one new one-use manifest only after 8A closes. Keep the bootstrap packet count as small as the proven sequence allows. The manifest must bind:

- exact stage-0 bytes/hash;
- exact canary target/effect and its expected observation;
- exact target/version assumption;
- one connection / packet count / timing budget;
- no retry/reconnect;
- Runtime 018 suspend/restore procedure;
- explicit negative outcomes: crash, reboot, disconnect, timeout, ambiguous canary, or failed Runtime 018 restore are NOT PASS.


### Prepared manifest state

`experiments/OPENDITOO-VRAM8B-CANARY-001.json` and `artifacts/analysis/volatile_ram_api_vram8b_fixture.json` freeze the exact one-use candidate. The transcript is eight sends on one connection: stock baseline `0xb2`, baseline `0xb3`, stock `0x6e`, stock `0xa5`, exactly one custom `0x6c`, post-hold `0xb3`, restore `0xb2`, restore `0xb3`; retry/reconnect are false and the callback observation hold is 75 seconds. PASS requires typed readback `0 -> 1 -> 0`, normal liveness and Runtime 018 restoration. The manifest is `prepared_unauthorized`; no runner/grant/claim/handover has been created and no device I/O occurred. The only next live authority would be the exact fresh owner grant `Grant OPENDITOO-VRAM8B-CANARY-001 -- stock btplayer selected`. VRAM-8D remains a separate later grant.

### Success

All of the following must occur:

1. exact custom overwrite sent once;
2. the chosen positive canary is observed exactly as designed;
3. callback returns and device remains responsive;
4. Runtime 018 restores and ACKs a fresh product frame;
5. no retry or second experiment attempt occurs.

This closes “our code can safely do bounded work”, which is stronger than the VRAM-7 returning no-op proof.

---

## VRAM-8C — bounded resident-window and installer design — ADVANCED / NOT CLOSED

### Question

Where can a small resident stage-1 live safely for the remainder of the boot, and how can stage-0 install it without exposing arbitrary memory operations?

### Resident-window selection

Rank candidate RAM windows with hard evidence. A usable destination must be:

- writable + executable on the exact mapping;
- not stack, allocator metadata, runtime50, display backing that stock will immediately reuse, DMA/audio buffers, or a known global object;
- stable for the intended boot/session lifetime;
- large enough for stage-1 code + state + guard words;
- either statically reserved/unused or obtained through a deterministic stock allocator call whose lifetime is deliberately retained.

Prefer an allocated/reserved window over “unused-looking RAM”. If allocation is used, stage-0 owns allocation once, stores the pointer only in reviewed device-side state, and the host still never chooses the address.


### Current ranked result

The current offline ranking rejects hardcoded free-looking app-heap addresses, the live display backing, runtime50/adjacent live objects, and unreserved upper identity-mapped SRAM. The preferred design is **one deliberately retained application-heap allocation owned by OpenDitoo for the boot session**, but it is not promoted until callback task-vs-interrupt context and allocator ABI/reentrancy are closed. No stage-1 image exists yet, so a maximum image length must not be guessed; freeze it only after the single fixed image is built and measured. The future installer must perform explicit I-cache maintenance before stage-1 execution. That was the pre-closure state. The dedicated 2026-09-13 artifacts above now close 8C offline with a measured fixed image and bounded installer; 8D remains a separate future live gate and has no authority.

### Installer contract

Start with the smallest protocol that fits the evidence:

- fixed magic/version;
- fixed maximum image length;
- fixed destination chosen by device-side code/design, never host input;
- image length + integrity field;
- exact expected stage-1 build hash/version;
- copy only after all bounds checks pass;
- optional guard/canary words before and after the resident region;
- one fixed stage-1 entry point derived from the installed image layout;
- installation refusal on duplicate/inconsistent metadata;
- no execution when integrity fails.

If stage-1 fits safely inside one bootstrap source, prefer a **single-shot fixed-image installer first**. Add chunking only if size evidence requires it. If chunking becomes necessary, freeze chunk size/count, reject duplicates/out-of-order chunks, and keep total payload bounded; do not create a reusable arbitrary upload channel.

### Gate

Offline proof must show the installer cannot write outside the selected window under any accepted metadata and cannot branch anywhere except the one fixed stage-1 entry.

---

## VRAM-8D — live resident installer + stage-1 liveness proof

### Question

Can stage-0 install one fixed reviewed stage-1 image into the selected RAM window, invoke its fixed entry/init path, and return to stock firmware?

### Stage-1 v0 for this gate

Keep it intentionally inert. Suggested behavior:

- write/maintain a resident header: magic, ABI version, build ID, state=`installed`;
- optionally increment one bounded heartbeat/counter when invoked through a reviewed local path;
- perform no input interception and no stock-service call yet.

The positive observation should reuse the trustworthy canary/readout mechanism established in VRAM-8A/B rather than inventing a new ambiguous oracle.

### Success

- installer integrity passes;
- stage-1 init runs exactly once;
- positive installed/liveness marker observed;
- stock callback returns;
- device + Runtime 018 recover normally;
- no second install attempt under the same grant.

After PASS, the project has a proven volatile resident code container. Only then move to API ingress.

---

## VRAM-9A — RAM-resident API ingress seam, OFFLINE

### Question

What is the lowest-risk reversible RAM hook that can route a small reserved command family to stage-1 while forwarding everything else unchanged?

### Research order

1. Reuse the complete SPP atlas and dispatcher analysis; do not restart generic command enumeration.
2. Search first for RAM-resident indirection already used by stock firmware:
   - callback/function-pointer tables;
   - registered RX handlers;
   - task/message dispatch pointers;
   - copied parser tables or mutable category handlers.
3. Prefer replacing **one RAM pointer/table entry** over patching executable code bytes.
4. Pin the original target and exact forward path. Unknown/non-OpenDitoo commands must tail-call/forward stock behavior unchanged.
5. Define an OpenDitoo command discriminator that does not collide with any implemented stock command/subcommand in the pinned atlas.
6. Prove hook install, hook remove, duplicate install refusal, and reboot rollback offline.

### Reject

- ROM/flash text patching;
- generic parser replacement;
- host-selected hook addresses;
- stealing a stock command whose side effects are not fully understood;
- any ingress design that cannot forward unclaimed traffic exactly.

---

## VRAM-9B — API v0: API_INFO + PING/PONG

### Scope

First steady-state API should expose only liveness and identity:

- `API_INFO` -> magic, API version, build ID/hash prefix, capability bits;
- `PING(nonce)` -> `PONG(nonce)`;
- optional `API_RELEASE` if needed to uninstall the RAM hook cleanly.

No input claim, brightness, volume, arbitrary memory, or arbitrary execution yet.

### Protocol rules

- fixed framing and maximum message size;
- explicit version;
- bounded nonce/data sizes;
- malformed/unknown API packets rejected without touching stock state;
- non-API stock traffic forwarded unchanged;
- API state cleared on reboot;
- host command surface is typed only.

### Live gate

Use one fresh manifest to install the already-reviewed resident image and exercise a tiny fixed transcript (`API_INFO`, one or a few PING/PONGs, optional release). Prove stock behavior still works after release/expiry and Runtime 018 can resume.

---

## VRAM-9C — fail-open physical input claim

### Objective

Add the first useful OpenDitoo feature: temporarily claim the front-panel input path in RAM.

### Contract

- `CLAIM_INPUT(ttl_ms)` with strict min/max TTL;
- `RENEW_INPUT(ttl_ms)`;
- `RELEASE_INPUT`;
- typed `INPUT_EVENT` reports with key, press/release/repeat semantics;
- TTL expiration automatically restores stock forwarding;
- host loss must fail open;
- power lifecycle/emergency controls remain untouched;
- no long-hold mapping until semantics are explicitly proven safe.

### Implementation preference

Hook the already-mapped category-`0x82`/keypad producer-consumer seam only if a reversible RAM indirection exists. When claim is inactive, forward the original event unchanged. When active, consume only the explicitly supported input events and report them to the host.

### Acceptance ladder

1. offline synthetic event tests;
2. live short claim with one key family;
3. expiry without host traffic -> stock behavior restored automatically;
4. explicit release -> stock behavior restored;
5. host disconnect/power-cycle -> fail-open/reboot rollback.

Do not combine all acceptance cases into the first grant.

---

## VRAM-10 — typed stock-service bridge

Only after API_INFO/PING and fail-open input claim are stable, add useful wrappers one at a time. Recommended order:

1. **brightness** — map a claimed button to a reviewed stock brightness setter/state transition;
2. **volume/audio state** — only after exact semantics and media contention are understood;
3. **display/page mode** wrappers around already-proven stock paths;
4. **device info/battery/status** where safe read semantics exist;
5. selected image/scene operations if they reduce dependence on the external Host.

Every service is typed and bounded. Stage-1 may call only compiled-in reviewed stock entry points; the host never supplies a function address. Preserve an option to forward the original stock adjustment so OpenDitoo can consume a button yet still request the normal behavior deliberately.

Each new service gets focused offline proof and, when needed, its own narrow live acceptance rather than widening the entire API implicitly.

---

## VRAM-11 — session-autonomous behavior

After the API and service bridge are stable, allow small local logic to continue after the bootstrap host disconnects. This is **session-autonomous**, not cold-boot persistent.

Candidate uses:

- local button-to-page rules;
- tiny animation/state machines;
- bounded timers;
- simple display behavior using already-approved service wrappers.

Requirements:

- strict RAM/code/state budget;
- watchdog/fail-open behavior;
- no arbitrary interpreter, FORTH, shell, or uploaded ARM snippets;
- reboot/power loss fully clears it;
- explicit distinction in docs/UI between “installed for this boot” and “starts by itself”.

Cold-boot offline behavior remains out of scope unless a future separately reviewed persistent delivery mechanism exists.

---

## Milestone artifact discipline

At every material phase update the durable state, not chat memory:

- this roadmap;
- `START_HERE.md` current-state routing;
- `notes/OPENDITOO-HANDOFF-2026-09-12-VOLATILE-RAM-API.md` or a dated successor handoff;
- the main volatile-RAM plan;
- deterministic analysis JSON/tools/tests;
- one-use manifests only after an offline candidate freezes.

Use focused tests while iterating. At milestone/handoff boundaries run analyzer selfchecks, relevant unit suites, `git diff --check`, hash verification, and the broad `python3 scripts/verify_day1_offline.py` once, comparing against the known constrained-WSL missing-Pillow baseline rather than “fixing” unrelated W9B code.

## Immediate next-session executor target

The next session should work **offline through VRAM-8A and as much of VRAM-8C design as evidence permits**, beginning with the callback ABI and canary-selection problem. It should not create live authority merely to make progress. If VRAM-8A closes with a strong positive canary, prepare (but do not grant or execute) one fresh one-use VRAM-8B manifest and stop at the owner grant boundary.

Do not replay VRAM67-001/002. Do not begin API ingress/input hooks before a nontrivial returning canary and bounded resident installer are independently proven.