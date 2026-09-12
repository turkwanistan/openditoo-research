# OpenDitoo — volatile RAM API / Bluetooth-parser exhaustion plan — 2026-09-12

## Objective

Determine, with a bounded and evidence-backed process, whether the owner's Ditoo Plus can gain a **volatile, RAM-resident OpenDitoo API over its existing Bluetooth stack** without opening the device, attaching hardware, or persistently modifying firmware.

The desired success state is not "find a crash." It is:

1. a reproducible stock Bluetooth/SPP ingress path that gives controlled influence over RAM or control flow;
2. a minimal, reversible RAM bootstrap that survives only until reboot/power loss;
3. a small OpenDitoo API/shim that can claim front-panel events before stock side effects and can call selected stock services while the claim is active;
4. deterministic fail-open behavior: if the host disappears, the claim expires and stock behavior resumes;
5. no flash erase/program, no SD firmware install, no MassBoot hardware work, no factory mode.

If no such path survives the exhaustion criteria below, close this route explicitly rather than continuing unbounded fuzzing.

## Authority / project boundaries

This phase is **software-first and exact-unit scoped**.

Allowed autonomously without a new physical grant:

- offline static analysis of preserved firmware/APK/captures;
- disposable-Lab disassembly, decompilation, emulation and fuzz harnesses;
- new recognition/taint/call-graph tools and machine-readable artifacts;
- public-source research and source ingestion with provenance;
- offline exploitability models that cannot transmit or create a persistent installable firmware image;
- tests, documentation, commits and pushes of validated owned work.

Not authorized merely by this plan:

- new Bluetooth transmission to the Ditoo;
- live malformed/crash probes;
- deliberate reboot/crash loops;
- firmware/flash write, erase, valid update package, factory-mode entry;
- MassBoot commands, UART, GPIO/reset manipulation, continuity measurements, SPI clip/programmer;
- interaction with any third-party device/system.

Every live parser probe needs its own reviewed manifest and exact owner grant. One ambiguous live outcome consumes that manifest; no blind retries.

`OPENDITOO-MASSBOOT-M2-UNPOWERED-MAP-001` is currently authorized/unconsumed but **deferred by the owner's present no-measure/no-attach preference**. Do not execute it merely because authority exists.

Runtime 018 is the accepted everyday product and must remain unchanged by this research.

## Current evidence to preserve

### Exact target / transport

- purchased Ditoo Plus, product flag 42, installed stock version **v42012** with high confidence from exact-unit `0x97` response;
- Classic RFCOMM/SPP channel 1 is the proven application-control transport;
- exact-unit application framing and additive checksum geometry are already reproduced;
- exact-unit `0x44` image and `0x58` drawing traffic are proven;
- unsolicited `0x09` / `0xBD` device-to-host reports are proven;
- Runtime 018 already receives Left/Right/Lever through the AVRCP sidecar but host-side reception cannot suppress stock handling for controls such as brightness/volume.

### Preserved exact-model branches

Primary static corpus:

- flag42 v42016 production;
- flag42 v42017 official test branch;
- flag60 v60014 production;
- flag60 official test object (API v60016 / internal v60017).

Related-family calibration only:

- original Ditoo flag46 v46032;
- OpenTivoo/AK1052D evidence where explicitly labelled as related/same-silicon evidence.

Exact v42012 bytes remain unrecovered. No static finding from a later branch may be silently promoted to exact-unit fact.

### Known SPP architecture

The exact Ditoo Plus production dispatcher covers commands `0x04..0xFE` (251 slots). Recovery work has already established:

- `0x93..0x96` are default/error on preserved Plus firmware;
- `0x97` is file-version query;
- `0x98/0x99` are update ingress, not readback;
- `0x9b/0x9d/0x9e/0x9f` are hot/update-content paths;
- `0xbd` is a narrow first-level EXTERN mux whose implemented Plus subrange is `0x13..0x1b`;
- stock SPP has no caller-controlled arbitrary flash-read chain within the analyzed graph;
- the centralized category-`0x82` key queue and its four producers are already pinned for a future RAM shim.

Do not reopen those closed questions unless new evidence directly changes them.

### Why this route is still open

The earlier input-takeover research listed **Route C — no-flash code execution through an application parser** as a research lead and then deprioritized it because SD/MassBoot looked cleaner. The recovery route is now blocked by the owner's hardware boundary, so Route C becomes the primary remaining path to a reversible in-device shim.

Public MiniToo work is methodology evidence only: on different silicon it independently treats a no-flash ACE path as "controlled Bluetooth-delivered data -> vulnerable parser -> executable RAM," and distinguishes useful controllability from crashes. Do not transfer its JPEG bugs, memory map, MPU result, command IDs or exploit mechanics to Ditoo Plus.

## Definition of "exhaust the Bluetooth/parser surface"

The phase is complete only when every **host-reachable, caller-data-consuming** surface in scope is represented in a machine-readable inventory and has one of these terminal classifications:

1. `CLOSED_BOUNDS_SAFE` — length/data propagation is sufficiently bounded for the candidate class;
2. `CLOSED_NO_CONTROL` — malformed data may fail/crash, but controlled bytes cannot plausibly influence useful RAM/control state;
3. `CLOSED_NOT_REMOTE` — parser exists but no stock Bluetooth path reaches it with caller-controlled content;
4. `EXCLUDED_PERSISTENT` — reaching it requires flash/SD persistent mutation outside this phase;
5. `EXCLUDED_THIRD_PARTY_PROFILE` — requires attacking unrelated peers/services rather than the owned Ditoo endpoint;
6. `PROMOTED_RAM_WRITE` — bounded caller-controlled RAM write primitive or equivalent state corruption is demonstrated offline;
7. `PROMOTED_CONTROL_FLOW` — caller-controlled PC/function-pointer/return/callback influence is demonstrated offline;
8. `PROMOTED_LIVE_CANDIDATE` — enough exact-model evidence exists to justify one bounded exact-unit probe.

A handler may have multiple parser stages; classify the deepest caller-controlled stage, not merely the top-level command.

The inventory must include explicit coverage totals so we can say what was actually exhausted.

## Surface scope and priority

### Tier 1 — direct stock RFCOMM/SPP ingress

Start here because OpenDitoo already owns the transport and exact-unit framing is proven.

Inventory all 251 dispatcher entries and every implemented nested EXTERN subcommand. For every real handler record:

- command/subcommand;
- branch target(s) per preserved firmware;
- minimum/maximum accepted packet/payload length if derivable;
- all explicit length checks;
- caller-controlled offsets/fields;
- destination type: stack, static RAM, heap, ring/cyclic buffer, flash staging, subsystem context;
- allocation size source;
- copy/write primitive and count source;
- downstream parser/decoder/callback;
- indirect calls or data-derived branch/table indices;
- cleanup/lifetime;
- response/error behavior;
- persistence side effects;
- lineage stability across flag42 v42016/v42017 and flag60.

Prioritize variable-length or multi-packet paths over tiny fixed setters/getters.

### Tier 2 — image/content/download parsers reachable from SPP

Exact-model strings prove a substantial Divoom content subsystem, including:

- `divoom_disp_download_file`;
- GIF load/write/read/info paths;
- movie load/write/read paths;
- `divoom_disp_picture_decode_rgb_data`;
- alarm GIF/voice paths;
- hot-content/update-content paths;
- drawing/pixel/image paths;
- generic download buffering (`divoom_down_file_check_buf_full`).

Map which of these receive bytes directly from SPP, which first persist to SPI, and which decode from RAM before commit. **Only no-flash paths remain candidates for the volatile API route.**

Do not assume a JPEG surface: unlike MiniToo, the current Ditoo string pass primarily exposes GIF/movie/RGB and audio/media decoders. Promote only parsers with Ditoo-specific reachability evidence.

### Tier 3 — Bluetooth profile/media parser surface

Audit only owned-device-relevant paths that Windows/Android can legitimately deliver to the Ditoo:

- AVRCP/AVCTP command/event parsing;
- A2DP/SBC/media packet handling;
- HFP command/codec control;
- PBAP/profile metadata only if the Ditoo is the receiving parser and the path can be exercised against the owner's unit without involving a third-party target.

These are lower priority than SPP because they are harder to control precisely and may be mediated by the OS Bluetooth stack.

### Tier 4 — local file/media decoders reachable through a nonpersistent Bluetooth path

The firmware contains a broad media stack (MP3/WMA/APE/FLAC/PCM/ADPCM/AAC/Vorbis/AMR/RA8/DRA/AC3/G711/SBC/SPEEX, movie/demux code). This is **not automatically an attack surface for this project**.

For each decoder, first prove a Bluetooth path can feed attacker-controlled bytes to it **without requiring persistent SD/flash mutation**. If not, classify `CLOSED_NOT_REMOTE` for this phase rather than fuzzing the codec in isolation.

## Phase VRAM-0 — corpus + reproducibility freeze

Deliver:

- hash-pinned corpus manifest for every firmware/app/capture used;
- branch-normalization helper so function relocation between v42016/v42017/flag60 can be expressed consistently;
- source/provenance note for any public comparator used;
- a new analysis artifact schema, suggested `artifacts/analysis/volatile_ram_api_surface.json`;
- one command that regenerates the report offline and fails closed on hash/byte drift.

Exit: corpus identity and report generation are deterministic.

## Phase VRAM-1 — complete SPP ingress atlas

Build `tools/ditoo_spp_surface.py` (name may vary) rather than hand-maintaining a prose table.

Required capabilities:

1. reconstruct all 251 top-level dispatcher targets for each preserved Plus branch;
2. distinguish default aliases from real handlers;
3. enumerate nested muxes (starting with `0xbd`) from byte-verified bounds/jump tables;
4. find handler-local and transitive calls to known allocation/copy/buffer/parser primitives;
5. record packet/payload length comparisons and data-derived indexes where statically recognizable;
6. emit a ranked list of handlers needing deeper taint analysis;
7. preserve unknowns instead of guessing semantics from nearby strings.

Use disposable Lab tooling (Capstone/radare2/Ghidra/headless scripts/angr/Unicorn if useful) for discovery, but re-express promoted conclusions as reproducible fail-closed invariants where practical.

Exit:

- 251/251 dispatcher slots accounted for per branch;
- every real handler has a first-pass size/dataflow classification;
- nested implemented mux coverage is explicit;
- report/tests reproduce without a GUI-only dependency for accepted facts.

## Phase VRAM-2 — caller-controlled dataflow / memory-safety triage

For each high-value handler, answer these questions in order:

1. **What bytes/lengths can the host control?**
2. **Where do they land?**
3. **How is destination capacity established?**
4. **Can count, offset, index or allocation arithmetic wrap/truncate?**
5. **Can a multi-packet state machine make advertised length diverge from accumulated length?**
6. **Can data outlive the packet buffer and become a pointer, callback, vtable/jump entry, return address, queue record, linked-list field or allocator metadata?**
7. **Does an error path free/reuse state while later packets retain a stale pointer?**
8. **Does a parser trust internal length fields after the SPP layer already accepted the outer frame?**
9. **Would corruption remain RAM-only, or does the path inevitably write flash?**

Prioritize patterns:

- host length -> allocation -> copy count mismatches;
- fixed stack/static buffers with variable copy length;
- signed/unsigned or 8/16-bit truncation;
- index/count products (`count * element_size`) without overflow guards;
- cumulative chunk offset + current length;
- parser recursion/nesting;
- function pointer tables adjacent to variable buffers;
- callback/context structs whose fields are populated from caller data;
- use-after-free / double-close / stale multi-packet session contexts;
- decompressor/decoder output-size mismatches.

Do not score a null dereference or simple out-of-range reject as useful unless controlled state survives to a meaningful sink.

Exit: every Tier-1 high-value handler is terminally classified or promoted.

### VRAM-0/1 + direct-SPP VRAM-2 status — CLOSED 2026-09-12

`tools/ditoo_spp_surface.py` and `artifacts/analysis/volatile_ram_api_surface.json` now provide the fail-closed direct-tier accounting: 251/251 top-level slots, 9/9 implemented EXTERN subcommands, 124/124 explicit non-default handlers terminally classified, and zero unresolved handlers. Fifty-four high-value handlers have byte/helper-level conclusions; seventy additional handlers are closed for Tier-1 bulk-parser/control-flow purposes by handler-local scalar/fixed-control screening.

No direct SPP candidate reached a controlled RAM write or caller-controlled indirect branch/call without crossing a persistent storage path. Therefore VRAM-2 exits by the planned negative condition and **no VRAM-5/VRAM-6 live candidate is created from Tier-1**.

Tier-2 has now resolved that seam: it is the resident `divoom_light_word` display path, not a generic media/codec decoder. The corrected stock reachability is `0x6e SPP_DRAWING_CTRL_MOVIE_PLAY` with nonzero control -> content mode `0x0b` -> subsequent `0x6c SPP_DRAWING_ENCODE_MOVIE_PLAY` same-mode copy. `0x6c` does not prime itself. The branch-specific veneer converges on resident `0x008012a8`, where the caller u16 from `0x6c` reaches a destination copy. `tools/ditoo_tier2_display_surface.py` promotes a 4/4-branch `CALLER_CONTROLLED_ADJACENT_HEAP_OVERWRITE` with a modeled maximum 1009 controlled bytes beyond the physical backing allocation and imports the deterministic placement artifact to prove that the mode-`0x0b` initializer cannot move the persistent display/runtime50 geometry.

Placement and invocation have now both passed their offline fail-closed gates. `tools/ditoo_tier2_placement.py` uses the recovered stage-1 transformed-callback bootstrap to prove `Fwl_MallocInit -> no intervening app-heap allocation -> 0x8dea`, promoting exact cold-start geometry (`display backing 0x00804470 -> controlled destination 0x00804778 -> runtime50 0x00804b80 -> callback 0x00804bb4`). `tools/ditoo_tier2_trigger.py` proves runtime50 `+0x34` is a real 4/4 `BLX` sink, stock btplayer + `0xa5` selector 2/model `0x22` creates the VoiceTip timeout state, and an exact 1088-byte `0x6c` source controls the callback while preserving the stock handles/deadline needed before `BLX`. The app-heap busy predicate is transient and period-1 dispatch retries. The companion VRAM-3 artifact proves `0x00804779` executable Thumb RAM and a minimal `BX LR` return witness. This promotes a controlled indirect branch **offline only**. The all-SPP `0x8a` mode-normalization route remains unpromoted because queue/preemption ordering is not closed. No live manifest or packet has been created.

## Phase VRAM-3 — execution environment and RAM-hook feasibility

Independently establish what a successful memory-corruption primitive would need on **AK1052D/Ditoo**, rather than importing MiniToo assumptions.

Map from exact firmware/same-silicon evidence:

- executable memory regions and normal code/data addresses;
- heap/static RAM ranges and allocator behavior;
- whether RAM is executable in the active Ditoo configuration;
- cache coherency requirements for newly written code;
- stack alignment/calling convention/Thumb state requirements;
- safe scratch/RAM ranges that can hold a tiny stage-0 payload without colliding with stock runtime;
- candidate writable callback/function-pointer/queue-dispatch seams;
- existing stock SPP response function suitable for a liveness marker;
- reboot/power-cycle as guaranteed rollback.

If executable RAM cannot be established, do not abandon immediately: classify whether a return-to-stock-code/ROP-style stage could call an existing copy/response primitive and establish a better loader. But keep complexity proportional; this is not an open-ended exploit project.

Exit: explicit `RAM_EXECUTABLE`, `RAM_NONEXECUTABLE`, or `UNKNOWN_WITH_NAMED_DISCRIMINATOR`, plus a concrete control-flow target model.

## Phase VRAM-4 — offline candidate harnesses

For each promoted parser candidate, build the smallest function-level harness possible.

Preferred order:

1. pure Python structural model for lengths/state machines;
2. native/emulated function harness (Unicorn/QEMU/function-lift) when instruction semantics matter;
3. mutation/property tests around exact boundary conditions;
4. targeted fuzzing of **one parser at a time**, seeded by valid stock packets and constrained to its real wire grammar.

Record for every interesting input:

- original valid seed hash;
- exact mutation recipe;
- modeled/emulated path;
- destination bytes/offsets changed;
- fault/control-flow result;
- repeatability;
- branch lineage comparison.

Never use "fuzzer found crash" as the artifact. Minimize each candidate to a deterministic reproducer and explain controllability.

Exit: either no candidate reaches useful RAM/control influence, or at least one deterministic offline primitive is promoted.

## Phase VRAM-5 — candidate ranking gate

Rank promoted candidates with a simple evidence rubric:

- exact SPP reachability on purchased-unit protocol: 0–3;
- controlled bytes: 0–3;
- controlled length/offset: 0–3;
- deterministic control-flow/RAM sink: 0–4;
- no persistent write required: 0–3;
- cross-branch stability: 0–3;
- clean recovery by reboot: 0–2;
- live observability without destructive state: 0–2.

A candidate should not reach live preparation unless:

- it is reachable through a stock interface already proven on the exact unit;
- no flash/factory/update write is required;
- the live packet sequence is bounded and frozen;
- expected outcomes are enumerated (normal reject, no-op, controlled response, crash/reboot);
- the device can recover by ordinary power cycle;
- there is a reason to believe the test distinguishes controllability, not merely parser fragility.

## Phase VRAM-6 — first live parser discriminator (fresh manifest/grant)

Prepare **only after VRAM-5**.

The first live experiment should be the smallest nonpersistent discriminator possible. Prefer:

1. a boundary input expected to alter a response/visible state without crashing;
2. then a controlled benign fault with a single ordinary reboot recovery if needed;
3. only later a control-flow proof.

Constraints:

- one RFCOMM connection unless the candidate inherently needs reconnect;
- exact packet count/bytes frozen in manifest;
- no generic raw-send escape hatch;
- no command enumeration;
- no retry after ambiguous response;
- Runtime 018 stopped/restored only if the experiment requires transport ownership, with exact pre/post state recorded;
- no flash/SD/factory/MassBoot path touched.

A crash is evidence only if it is deterministic, candidate-specific and followed by normal reboot recovery. Do not build a crash corpus on the physical unit.

## Phase VRAM-7 — volatile code-execution proof

Only if a promoted primitive supports it.

Stage 0 must do almost nothing:

- execute a tiny RAM-resident routine;
- emit a unique stock-SPP-framed liveness response or make another harmless, reversible RAM-only observation;
- return cleanly to stock dispatch;
- leave no persistent state;
- ordinary reboot/power cycle restores pristine stock state.

No input hook yet. No long-running resident loop. No flash.

Success is a reproducible `packet -> controlled transfer -> RAM routine -> liveness -> stock return` chain.

## Phase VRAM-8 — bounded RAM loader

Once stage-0 execution is proven, stop exploiting parser internals for every feature. Convert the primitive into a narrow loader protocol.

Desired loader properties:

- fixed reserved RAM destination window;
- explicit maximum payload size;
- chunk index + total length;
- CRC32/SHA-256 or equivalent end-to-end integrity check;
- no arbitrary destination address supplied by the host;
- no arbitrary call address supplied by the host;
- one fixed entry point after successful verification;
- version/magic handshake;
- duplicate/out-of-order chunks rejected;
- loader can be abandoned safely and disappears on reboot.

The host-side OpenDitoo transport should expose typed operations, not `poke(addr, bytes)` / `goto(addr)` APIs.

## Phase VRAM-9 — RAM-resident OpenDitoo API v0

Keep v0 intentionally tiny. Suggested wire contract over the already-proven SYS SPP channel:

- `API_INFO` — magic/version/capabilities/build hash;
- `CLAIM_INPUT(ttl_ms)` — bounded front-panel claim;
- `RENEW_INPUT(ttl_ms)`;
- `RELEASE_INPUT`;
- `INPUT_EVENT` device->host report;
- `PING` / `PONG` liveness;
- optional `GET_STOCK_STATE` for fields already safely exposed by stock APIs.

Input claim behavior:

```text
physical key event
  -> existing category-0x82 producer/consumer seam
  -> RAM shim
       claim inactive/expired: forward original stock event unchanged
       claim active: report typed key event and consume it
```

Hard requirements:

- TTL/fail-open if host disappears;
- emergency escape / power lifecycle untouched;
- long/repeat semantics explicit;
- no permanent mutation of stock structures outside the bounded hook state;
- release/expiry restores stock behavior without reboot;
- reboot is full rollback.

Do not add a general-purpose interpreter/FORTH/ARM execution surface in API v0. The product goal is a bounded OpenDitoo API, not a permanent debug monitor.

## Phase VRAM-10 — stock-service bridge

Only after API v0 is stable, expose selected stock capabilities through typed wrappers. Candidates:

- brightness/light level;
- volume/audio state where semantics are proven;
- existing image/frame operations;
- page/display mode transitions;
- device info/battery/status;
- known stock game/scene operations if useful.

Each wrapper should call an already-understood stock function or SPP semantic; do not reverse every subsystem merely to increase API size.

This is where brightness/volume takeover becomes valuable: with an in-device input claim, those buttons can be consumed **before** their stock handlers, then OpenDitoo can choose whether to call the original stock adjustment itself.

## Phase VRAM-11 — session-autonomous behavior

A RAM-resident shim can potentially continue operating after the bootstrap host disconnects, as long as its behavior does not require host input. Distinguish this carefully from cold-boot persistence:

- **session-autonomous:** injected after boot, then can run local logic until reboot/power loss;
- **cold-boot offline:** starts after power-on with no host injection.

This route can plausibly achieve the first. It **cannot claim the second** unless a later persistent delivery mechanism is solved.

If useful, a later RAM API may include a very small bounded local-app bytecode/state machine, but only after the input shim and stock-service bridge are proven. Do not jump directly to an arbitrary ARM-code upload product surface.

## Required artifacts

At minimum:

- `tools/ditoo_spp_surface.py` or equivalent reproducer;
- `artifacts/analysis/volatile_ram_api_surface.json`;
- per-candidate minimized offline fixtures under a clearly non-live research path;
- tests pinning dispatcher coverage, branch hashes, length/dataflow claims and candidate classification;
- `notes/OPENDITOO-VOLATILE-RAM-API-PARSER-PLAN-2026-09-12.md` (this file);
- updated handoff/START_HERE/PROJECT_STATE after each material phase;
- live manifests only when a candidate has passed the offline ranking gate.

Do not commit vendor-decompiled source if licensing/provenance policy forbids it; commit derived facts/tools/artifacts sufficient to reproduce accepted claims.

## Testing discipline

During exploration:

- run focused analyzer/unit/harness tests;
- use disposable Lab for heavyweight decompilation/fuzzing/emulation;
- do not run the entire historical suite after every small edit.

At meaningful checkpoints (surface atlas closed, first candidate promoted, before any live manifest, before merge/handoff):

- analyzer selfchecks;
- focused candidate tests;
- `git diff --check`;
- relevant hash-manifest verification;
- full `python3 scripts/verify_day1_offline.py` once, comparing against the known constrained-WSL missing-Pillow baseline rather than rewriting unrelated W9B code.

## Stop conditions

Close this route as **NO USEFUL VOLATILE SOFTWARE ENTRY FOUND** when all are true:

1. all 251 top-level SPP slots and implemented nested muxes are classified;
2. every remotely reachable variable-length/content parser has a terminal classification;
3. profile/media surfaces with legitimate owner-device reachability have been triaged;
4. no candidate reaches controlled RAM write or control-flow influence without persistent mutation; and
5. no materially different parser family remains unnamed.

Do **not** keep adding random malformed packets after that point.

If a candidate is promoted, the route remains open only through the staged live gates above. A parser that merely reboots the device but cannot be shaped into controlled state is not success.

## Milestone summary

- **VRAM-0** corpus/reproducibility freeze.
- **VRAM-1** complete SPP ingress atlas.
- **VRAM-2** caller-controlled memory/dataflow triage.
- **VRAM-3** AK1052D/Ditoo execution + RAM-hook model.
- **VRAM-4** deterministic offline harness/fuzz candidates.
- **VRAM-5** evidence ranking / live-candidate gate.
- **VRAM-6** one bounded exact-unit parser discriminator (new grant).
- **VRAM-7** tiny RAM code-execution + clean-return proof (new grant).
- **VRAM-8** bounded fixed-destination RAM loader.
- **VRAM-9** OpenDitoo API v0 + fail-open input claim.
- **VRAM-10** typed stock-service bridge (brightness/volume/etc.).
- **VRAM-11** optional session-autonomous local behavior; never confuse with cold-boot persistence.

## Immediate next action

VRAM-0/VRAM-1 and Tier-1 direct-SPP are closed. Tier-2 reachability is resolved with the corrected stock sequence: `0x6e(nonzero) -> content mode 0x0b -> 0x6c same-mode divoom_light_word -> resident 0x008012a8`. The `0x6c` copy can carry up to 2041 caller-controlled source bytes into a 1032-byte physical destination capacity, for a modeled maximum 1009-byte adjacent-heap overwrite. Do not reopen generic codec hunting without a concrete edge.

Immediate offline work is now:

1. treat deterministic cold-start placement as **closed positive**: `0x00804778 -> runtime50 0x00804b80 -> callback 0x00804bb4` is pinned 4/4 by stage-1 bootstrap ordering plus the exact allocator model;
2. treat corrected display reachability as **closed positive**: stock `0x6e` with `payload[1] != 0` selects content mode `0x0b` and immediately confirms it; `0x6c` is only the subsequent same-mode copy primitive. The mode-`0x0b` initializer may allocate a separate 0xC50 object but has no direct app-heap free edge, and the vulnerable display/runtime50 allocations are persistent;
3. treat the stock trigger as **closed positive under a deterministic stock btplayer precondition**: after the `0x6e` content prime, `0xa5` selector 2/model `0x22` creates VoiceTip state and the period-1 timeout eventually reaches `0x1fa8a`; keep the all-SPP `0x8a` BLUE normalization route separate/unpromoted until queue-preemption ordering is proven;
4. treat **VRAM-3 as closed positive**: `0x00804779` is executable Thumb RAM with no NX barrier, lies in a pristine `0xff`-filled unreferenced span, and the minimal returning witness is `70 47` (`BX LR`);
5. preserve the exact 1088-byte witness geometry: callback source offset `0x43c`; controlled runtime50 byte0=`0xff`, byte8=`0x22`, callback=`0x00804779`; last overwritten victim offset `+0x37`; preserve `+0x3c/+0x40/+0x44`;
6. the next gate is procedural, not analytical: if proceeding live, author a **fresh one-use reviewed manifest** with stock/manual btplayer plus the stock `0x6e(nonzero)` content prime as explicit preconditions, tiny returning stage-0 only, strict byte/time limits, explicit rollback/stop conditions, and no persistence; require explicit owner grant before any transmit;
7. do not expand immediately to a loader/API until a bounded live returning-stage-0 proof exists. A crash, reboot, or timing-only effect is not success and must never be used as the primary oracle.

Do not create or transmit a malformed/custom live `0x6c` packet until the new one-use manifest is reviewed and explicitly granted. Runtime 018 remains out of scope.
