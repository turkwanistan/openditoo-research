# OpenDitoo handoff — W8 closed, W9A landed, W9B parked — 2026-09-10

Read this first, then `notes/OPENDITOO-WEBCAM-ROUTE-2026-09-09.md` §26–§29. Repository state is
authoritative over this note.

## Where things stand

Offline suite: **278 tests PASS**. Working tree clean. Nothing pushed.
Runtime 003 (MCP dashboard) is live, verified `connected`, `last_error=null`.

| Milestone | State |
| --- | --- |
| W8 near-ceiling webcam rate | **CLOSED PASS** — 005 consumed |
| W9A source identity + motion truth | **DONE, offline** — no device, no grant |
| W9B optical latency tooling | **DONE, offline** — verified end to end |
| W9B operator framing | **VERIFIED** — camera-only |
| W9B live trial 006 | **CONSUMED / unknown** — device never ACKed |
| W9B live trial 007 | **PREPARED, grant-ready, UNAUTHORIZED** — parked |
| W10 productization | not started |

## Accepted evidence

**W8-005 is the accepted transport result.** One 10 s run: 163 frames / 489 packets /
170,737 bytes, **16.285 fps**, per-quarter 15.6 / 16.4 / 16.4 / 16.8 with no decay. ACK p50
42.31 / p95 69.58 ms. Source age at send p50 36.99 / p95 51.86 ms, flat across quarters. Zero
duplicate source frames, both capacity-one queues at depth 1, 50.45 % latest-frame-wins
replacement. Terminal `lifetime_expired` / `stopped_clean`, no retry/reconnect/reclaim, no
pacing violation. **The Host ledger independently records the identical 163 / 489 / 170737.**
Owner visual observation: PASS — "looked great", no tearing versus the W7 ~10.78 fps baseline.

`clientMinusHostElapsedMs` (p50 1.14, p95 11.57, max 16.91 ms) is a signed observational
residual only. It is never a cross-process ordering invariant and is **not** HTTP overhead.

**Transport FPS is not physical panel FPS.** That distinction is unresolved and is exactly what
W9B exists for. Nothing in the accepted evidence licenses a claim about panel refresh.

## Decisions worth keeping

1. **Gray-coded stimulus counter.** Driven by measurement, not theory: a phone still decoded
   1255 against a screen readout of 1252, and a pre-Gray webcam still read 60 counts backwards
   (3579 → 3519 → 3579). Rolling shutter straddles repaints on *both* cameras. Under binary a
   carry flips several cells at once so the error is unbounded; under Gray exactly one cell
   changes per step, bounding a straddled read to ±1 count. Confirmed live afterwards: two
   independent thresholding methods disagreed on one frame by exactly 1.
2. **Fixed 128 decode threshold retained.** Adaptive k-means agreed on every frame except that
   one torn frame, so it buys nothing and adds a silent-misdecode path. Largest-gap was tried
   and rejected — the whites are spread, so the biggest gap can fall inside the white cluster.
   The four sync cells sit at the panel corners, the most vignetted positions, so they fail
   before interior data cells dim: **rejection is the failure mode, not silent bit flips.**
3. **A consumed manifest's producer hashes are history, not a gate.** `load_stream_manifest`
   was ignoring its own `verify_code_hashes=False`; it now honours it, and the checkers pass
   `False` once a manifest is consumed. This gates nothing — arming still needs unspent
   authority and an unclaimed one-use id, and the on-disk claim can never be released.
4. **Windows camera work must run from a locally staged copy under `C:\temp`.** Running the
   probe from the WSL UNC path fails `0x80070490`. `FrameServer` showing "stopped" is a red
   herring; it is on-demand and starts itself.

## Unresolved

**W9B attempt 006 failed and W9B has no optical evidence at all.** The Host opened the session,
got no ACK within the 5000 ms budget, and terminated `transport_fault` /
`IMAGE_RX_RECV_TIMEOUT; NO_RETRY`. Ledger 0/0/0, `displayState=unknown_nothing_sent`. Nothing
was displayed, so the operator footage of that attempt is unusable.

Client side was clean and **W9A instrumentation is exonerated**: 379 frames captured, transform
p95 2.50 ms, source id 76 selected with zero duplicate and zero out-of-order selections. A 007
that "fixes" the instrumentation would be treating the wrong thing; the 007 checker refuses a
manifest that drops the exoneration.

Root cause is held at **LOW confidence** and a test pins it there so the theory cannot harden by
repetition. Handover timing matched the successful runs almost exactly (002 4.15 s, 005 3.97 s,
006 3.99 s). The only observed difference: 006 stopped a product session that had sent **1**
frame, versus 347 and 220 for the runs that worked — so it had opened seconds earlier. A
Bluetooth link opened and torn down within seconds then reopened 4 s later is a plausible reason
for the device ignoring the new connection. **Plausible, not demonstrated.** It may simply be a
transient Bluetooth fault.

## Is W9B actually necessary?

**Recommendation: no, not now. It is optional and its value is conditional.**

W9B's purpose in the roadmap is to decide whether the physical Ditoo visibly benefits from more
unique update cadence — the gate on reopening >18.46 fps research. If that research is not
going to be pursued, W9B answers a question nobody is acting on.

What is already sufficient without it:

- the owner has visually accepted the webcam at 16.285 fps;
- W10 productization does not depend on it, and the W10 scheduler guidance (monotonic absolute
  deadlines, skip missed slots, no catch-up bursts, never consume a transmit interval on a
  duplicate) is sound regardless;
- the MCP dashboard, the actual daily driver, is unaffected.

What W9B would still uniquely provide: true scene→visible latency and a count of visible unique
transitions versus repeats. Genuinely interesting, but it is the most expensive remaining step —
physical rig, filming, a fresh grant per attempt — and it has already cost one consumed identity
for zero evidence.

The expensive groundwork is done and preserved, so deferring costs almost nothing: the stimulus,
the decoder, the correlation tooling, the verified framing and a grant-ready 007 all survive. If
the question ever becomes worth answering, it is one grant away.

**If W9B is deferred, the honest position to keep stating is that panel refresh and visible
unique-frame cadence are UNMEASURED.** Do not let 16.285 fps drift into being described as what
the panel does.

## Next objective

Either:

- **W10 productization** (recommended): camera/mode display, ROI/zoom, source and exact 16×16
  matrix preview, robust stop/disconnect, concise operator workflow. Fixed-rate modes use
  monotonic absolute deadlines (`next_due += interval`), advance/skip missed logical slots,
  select the newest transformed frame, never issue catch-up bursts, and never treat a duplicate
  or no-new-frame selection as a transmitted interval or update the Host-floor clock. Standing
  webcam authority is a **separate** explicit decision; Runtime 003 is dashboard authority only
  and must not silently widen.
- or **W9B-007**, if the latency question is wanted after all. See below.

## If W9B-007 is resumed

`OPENDITOO-WEBCAM-N980P-007` is prepared and **grant-ready but unauthorized**. Preparation
passed with `claim_created=false`, `host_session_io=false`, `device_io=false`; no 007 claim
exists and the Host ledger has no 007 entry. Manifest
`2ef724294b779b7d516cee98d037af5cd2fcefee5b7115586c05e2219a3eab22`.

Transport, pacing, budgets, camera, transform, Host and W9A instrumentation are **unchanged**
from 006, because none of them failed. The only change is operational: an 8 s handover settle
window after the product service stops and the Host reports idle, before opening. That is
insurance against the low-confidence handover theory, not a proven fix.

Before running: confirm the monitor, webcam and Ditoo have not moved since framing verification,
and reload the stimulus page. Then the exact grant `Grant OPENDITOO-WEBCAM-N980P-007`, then only
`scripts/run_webcam_w9b_optical_007_windows.ps1`, once, with the operator filming from a couple
of seconds before the grant until well after.

**A second consecutive `IMAGE_RX_RECV_TIMEOUT` falsifies the handover theory.** Do not retry it
a third time on the same reasoning — diagnose instead.

## Invariants (unchanged)

Exact-unit evidence outranks family resemblance and plans. Repository state outranks any note.
One Ditoo controller at a time. Runtime 003 dashboard authority does not authorize webcam. Every
live identity gets one fresh exact grant; consumed identities (002, 003, 004, 005, 006) are never
replayed. No automatic retry after ambiguity. No raw send, no target override, no second
Bluetooth stack, no firmware or persistent mutation work. Never touch OpenTivoo Host or port
8779. Do not pursue >18.46 fps protocol work during W8–W10.
