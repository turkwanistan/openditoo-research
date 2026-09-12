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

**Next named surface tier:** external media/codec processing reachable behind `0x6c -> 0x34144 -> fixed fallback 0xA6490 / registered media callback`. Start from the exact SPP-to-media call chain and prove which caller bytes reach which external parser before auditing any generic decoder. Do not import MiniToo codec bugs/addresses/semantics.

Safety state at this checkpoint is unchanged: Runtime 018 was not touched; no device transmission, malformed live packet, reboot/crash probe, factory/update write, MassBoot action, measurement, SPI attachment, UART/GPIO/reset work or other physical action occurred.

Checkpoint verification in constrained WSL_MCP: `python3 -m unittest tests.test_day1_offline.VolatileRamApiSurfaceTests -v` = 3/3 PASS; `git diff --check` = PASS; `python3 scripts/verify_day1_offline.py` = 364 tests with exactly the two known unrelated W9B optical `ModuleNotFoundError: PIL` errors and no new VRAM/parser/recovery failure.

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
5. Begin the named Tier-2 external media/codec reachability pass at `0x6c -> 0x34144 -> 0xA6490 / registered media callback`; map caller-byte provenance before decoder-specific work.
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
- `python3 scripts/verify_day1_offline.py` — 364 tests, exactly the two known unrelated W9B optical errors from missing `PIL`, zero new parser/recovery/product failures;
- M2 authority remains `status=authorized_unconsumed`, `physical_execution_authorized=true`, `authorization_consumed=false`; it was not executed or consumed;
- no Ditoo transmission, Runtime 018 change, flash operation, MassBoot action or physical measurement occurred while preparing this handoff.
