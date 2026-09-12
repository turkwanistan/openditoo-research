# Kickoff prompt — OpenDitoo volatile RAM API / Bluetooth parser phase

You are continuing the owner's personally owned Divoom Ditoo Plus / OpenDitoo project through WSL_MCP. The live `openditoo-research` repository is authoritative over this prompt and prior chat history.

Hydrate token-consciously: inspect git status/HEAD/upstream and preserve all concurrent/untracked work; read the current block of `START_HERE.md`, then `notes/OPENDITOO-HANDOFF-2026-09-12-VOLATILE-RAM-API.md` and `notes/OPENDITOO-VOLATILE-RAM-API-PARSER-PLAN-2026-09-12.md`. Pull in older evidence only when those files point to it.

The active goal is **not MassBoot, disassembly, SPI clipping, or persistent firmware**. Exhaust the stock Bluetooth/parser surface for a **reversible RAM-resident OpenDitoo API**: controlled stock Bluetooth input -> useful RAM/control-flow influence -> tiny RAM execution proof -> bounded loader -> fail-open input-claim API. Runtime 018 must remain untouched.

Operate in YOLO mode **inside the project boundary**: autonomously perform offline static analysis, public-source research, decompilation, disposable-Lab tooling, dataflow/call-graph work, harnesses/fuzzing, tests, artifacts, docs, commits and pushes. Prefer focused evidence-producing tests while iterating; run broad regression only at meaningful checkpoints. Do not ask me routine offline questions.

Start immediately with VRAM-0/VRAM-1 from the plan: build a reproducible machine-readable atlas of all 251 SPP dispatcher slots plus implemented nested muxes across the preserved Plus branches; classify real handlers by caller-controlled length/data, allocation/copy destination, downstream parser, indirect-control sinks, persistence, and lineage stability. Then drive VRAM-2 on the highest-value variable-length/content paths. A crash alone is not success: promote only deterministic candidates with plausible controlled RAM or control-flow influence. Explicitly close safe/dead paths so “exhaust” has measurable coverage.

Use the current MiniToo no-flash work only as methodology comparison; its SoC, bugs, memory map and command semantics are not Ditoo evidence. For Ditoo, prioritize exact SPP/content paths already visible in our binaries (download/GIF/movie/RGB/drawing/voice/media) and prove remote reachability before spending time on generic codecs.

Safety/authority boundary: no device transmission, malformed live packet, reboot/crash probe, factory mode, flash/update write, MassBoot command, UART/GPIO/reset work, continuity measurement or SPI attachment without a new reviewed one-use manifest and my exact grant. `OPENDITOO-MASSBOOT-M2-UNPOWERED-MAP-001` may still be authorized in the repo but is deferred by my current no-measure/no-attach preference; do not execute it. No third-party targets.

Continue autonomously until either (a) a specific Ditoo parser candidate is strong enough to justify a bounded live manifest, or (b) the direct SPP surface is comprehensively closed and the next named surface tier should begin. Keep accepted conclusions reproducible/fail-closed, update steering/handoff as milestones close, and commit/push coherent validated checkpoints.
