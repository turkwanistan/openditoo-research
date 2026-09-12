# Kickoff prompt — OpenDitoo first live returning-stage-0 gate

You are continuing the owner's personally owned Divoom Ditoo Plus / OpenDitoo research through WSL_MCP. **The live `openditoo-research` repository is authoritative over this prompt and all prior chat history.** This is a focused execution/orchestration session, not a re-research session.

Hydrate token-consciously in this order:

1. `git status`, HEAD/upstream; preserve any newer/concurrent work.
2. Current block of `START_HERE.md`.
3. `notes/OPENDITOO-HANDOFF-2026-09-12-VOLATILE-RAM-API.md`, especially the final Tier-2 handoff checkpoint.
4. `notes/OPENDITOO-VOLATILE-RAM-API-PARSER-PLAN-2026-09-12.md`, especially Immediate next action.
5. The four fail-closed analyzers/artifacts only as needed:
   - `tools/ditoo_tier2_display_surface.py`
   - `tools/ditoo_tier2_placement.py`
   - `tools/ditoo_tier2_trigger.py`
   - `tools/ditoo_vram3_execution_model.py`

Do **not** re-open closed Tier-1 parser enumeration, generic codec hunting, allocator-placement archaeology, VoiceTip registration, or RAM-executability research unless a pinned analyzer fails closed.

## Proven offline chain

Across 4/4 preserved Plus firmware branches, the repo now proves:

`stock/manual btplayer -> stock 0x6e(nonzero) content-mode 0x0b prime -> stock 0xa5 selector 2/model 0x22 VoiceTip setup -> exact 1088-byte 0x6c same-mode overwrite -> runtime50 callback 0x00804779 -> Thumb BX LR -> normal return`

Critical facts to preserve:

- `0x6e`, not `0x6c`, primes content mode `0x0b`; `0x6c` requires the already-selected same mode.
- controlled source/destination geometry: `0x00804778 -> runtime50 0x00804b80 -> callback 0x00804bb4`, callback source offset `0x43c`.
- exact overwrite length: **1088 bytes**, ending at runtime50 `+0x37`; preserve `+0x3c/+0x40/+0x44`.
- controlled victim fields: byte0=`0xff`, byte8/model=`0x22`, callback=`0x00804779`.
- VoiceTip period-1 timeout eventually invokes `+0x34`; the heap-busy gate is transient.
- heap SRAM is executable under stock ARMv5T mapping; stage-0 witness is exactly `70 47` (`BX LR`).
- use **stock/manual btplayer** for the first discriminator. The all-SPP `0x8a` BLUE-normalization idea is intentionally unpromoted because queue/preemption ordering is not statically closed.
- Runtime 018 is accepted/live and out of scope except for narrowly documented transport ownership if the live manifest truly requires it.

## Mission

Advance exactly one gate: **prepare the first one-use exact-unit returning-stage-0 live discriminator (VRAM-6/7), then stop at the explicit owner-grant boundary.**

Work autonomously inside the offline/project boundary:

1. Re-run the four analyzer selfchecks plus the focused Tier-2/VRAM tests; compare against the handoff baseline. Do not run broad regression repeatedly.
2. Review existing experiment-manifest conventions in `experiments/` and create a **fresh, new one-use manifest** for this experiment. Do not reuse or inherit authority from MassBoot, Runtime 018, SD-P1, or any consumed grant.
3. The manifest must freeze, fail-closed:
   - exact purchased-unit identity assumption: Ditoo Plus flag42, installed v42012 version identity, exact v42012 bytes unrecovered;
   - required observable precondition: ordinary stock/manual btplayer mode;
   - stock `0x6e` nonzero content-mode prime;
   - stock `0xa5` VoiceTip setup using selector 2/model `0x22`;
   - **one** bounded custom `0x6c` overwrite only, with exact declared/source length and no retries;
   - stage-0 limited to the minimal returning `BX LR` witness—no loader, API, shell/interpreter, persistence, flash/update/factory/MassBoot path;
   - exact connection count, packet count, timing/window, pre/post checks, liveness/success discriminator, stop conditions, and rollback behavior;
   - Runtime 018 handling if transport ownership conflicts, with the smallest reversible intervention possible;
   - explicit statement that crash/reboot/timing-only change is **not** success and triggers stop/no retry.
4. Build any required packet/sequence **offline only** into a frozen hash-bound research fixture if repository policy supports that, but do not open Bluetooth, connect, or transmit. Prefer a manifest-driven executor that cannot run without the exact unconsumed grant rather than a generic raw-packet tool.
5. Add focused tests that prove the manifest/fixture exactly matches the four offline artifacts and cannot exceed the one-use bounds. Update handoff/START_HERE if material.
6. Run `git diff --check` and the relevant focused tests; run the broad offline verifier once at the checkpoint if changes are material. Commit and push coherent offline preparation.
7. **STOP BEFORE LIVE TRANSMIT.** Present the owner with the exact manifest summary, risks, expected observable success condition, and the precise grant text required. Do not infer authorization from this prompt or any prior grant.

## Authority / safety boundary

Until the owner explicitly grants the newly created one-use manifest: **no device transmission, no custom/malformed 0x6c, no Bluetooth connection for this experiment, no crash/reboot probe, no factory/update/flash write, no MassBoot command, no physical measurement/attachment, no Runtime 018 cutover.** No third-party targets.

If a live grant is later supplied, execute only the frozen manifest once. Do not automatically retry ambiguous or failed behavior. Record the result, restore the accepted runtime state, and stop for interpretation before designing VRAM-8.

Success for this session is **not live code execution**. Success is a fully reviewed, hash-bound, fail-closed one-use manifest/fixture committed and pushed, with the repo stopped exactly at the explicit owner-grant boundary.
