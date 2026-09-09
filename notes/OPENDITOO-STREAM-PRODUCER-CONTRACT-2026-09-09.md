# OpenDitoo stream producer contract — what a live 16x16 source must deliver

For designing a webcam → Ditoo pipeline. Everything here is measured on the owner's exact
Ditoo Plus `11:75:58:CE:DE:C7` (firmware v42012) or measured offline this session. Nothing
is estimated from datasheets or device-family resemblance.

## 1. The interface

Hand us **768 bytes: 16 × 16 × 3, RGB888, row-major, top-left first.** That is the entire
contract. We own encoding, packetisation, ACKs, pacing, budgets and failure handling.

## 2. Hard constraints — design around these, not around guesses

**At most 255 distinct colours per frame.** The device's stock-derived image packet carries
one palette per frame, capped at 255 entries. A 16×16 frame has 256 pixels, so a camera
frame will essentially always sit at 256 and must be reduced by at least one colour.

*This is not a fidelity problem.* 256 pixels can never show more than 256 colours, so at
exactly 256 every colour occurs exactly once and **one merge is always enough**.
`quantize_to_palette_limit` now finds the closest pair by weighted distance
(`3dr² + 4dg² + 2db²`), repaints that single pixel, and leaves the rest of the frame
untouched — one pixel changed, 255 colours out. (It previously dropped channel low bits
across the whole frame, which cost a gradient 24 colours to solve a one-pixel problem. The
N980P plan §7.5 was right to call that out.)

The C# sidecar's guard **must implement this same rule**, or offline previews will not match
what the device is sent. Cost is ~3.8 ms in Python and only when the frame is actually at
256 colours; in the sidecar's hot path it is negligible. At 16×16 the fidelity budget is
spent almost entirely on downscaling and exposure, not colour depth.

**Payload size is a solved question.** A 250-colour frame is 1039 application bytes. The
accepted R4/R5 rate ladder sent 1048 bytes per frame, sustained, for 512 and 1024 frames.
So full-colour camera payloads are inside already-proven territory — do not design around
bandwidth, and do not propose a lower colour count "to save bytes".

**Newest frame wins; never queue.** We drop a playback step rather than stretch the clip. A
live source must be sampled, not buffered — if a frame is late it is stale, and stale is
worse than skipped. Expose a target cadence as a parameter, not a hardcoded 30 fps.

**Deterministic means integer-only and seedless.** No dithering with a random seed, no
floating-point accumulation across frames, no wall-clock-dependent behaviour. The same input
frame must always produce the same 768 bytes, because manifests freeze code hashes and
results have to be reproducible.

## 3. The rate budget — measured, including one refuted assumption

| Component | Cost per frame | Source |
| --- | --- | --- |
| **Dispatch → ACK, 1039 bytes, 250 colours** | **median 66 ms, min 50, p95 93** | **S2, measured on the exact unit** |
| Device wire: 3 packets + one ACK, full colour, no sleeps | 54.2 ms | R5, 1024 frames / 55.54 s |
| Same, sustained with 10 ms intra-frame spacing | 131.0 ms | R4, 512 frames / 67.2 s |
| Our encode + sha256 + hex (250-colour frame) | 0.24 ms median | measured offline |
| WSL → Windows Host loopback HTTP RTT | 2.17 ms median (p95 3.9) | measured offline |

The S2 figure is the first clean isolation of per-frame round-trip cost — earlier ACK-latency
numbers in this project included our own packet-spacing sleeps and must not be compared
against it.

Our client CPU plus loopback is ~2.5 ms, so **our software is ~4% of the frame budget and was
never the constraint.**

### The ceiling is set by latency VARIANCE, not mean

S2 dispatched on a phase-stable 150 ms grid — exactly the Host's floor — and died on frame 10
with `HTTP 429 SESSION_PACING_VIOLATION`. The Host times the interval on its own clock from
when *it* starts a frame, so a client gap of 149–151 ms can still arrive early, and **a pacing
violation is terminal: there is no retry.**

Consequences:

- A client must pace against **p95 (93 ms), not median (66 ms)**, plus jitter margin. Every
  frame has to clear the bar; an average that clears it is not enough.
- `CLIENT_JITTER_MARGIN_MS = 50` is now enforced by the manifest validator. It is the margin
  the MCP dashboard has used across every activation and the whole product runtime with zero
  pacing refusals; smaller margins are untested and the failure mode is losing the session.
- **At the current 150 ms Host floor, the safe client cadence is therefore 200 ms — the same
  value the dashboard already used.** The client-side rate lift buys nothing until the Host
  floor drops. Plan for **~5 fps today.**

### What actually unlocks the rate

The Host refuses an early frame. It should **wait** for the floor to elapse and then send.
The device still never sees frames faster than the floor — the hard rate bound is unchanged —
but the session-killing race disappears, and with it the client's need for margin. Then the
cadence can approach the measured round-trip directly.

That is a small change to `ActivitySessionHost.SendFrame`, but it rebuilds the Host DLL, whose
hash the live product policy binds, so it needs a **Runtime 003 product policy and its own
grant**. Realistic target after it: **10–13 fps** (paced against p95 round-trip), not 17.5 —
the arithmetic ceiling assumed a mean, and means are not what a no-retry protocol can pace on.

## 4. Why we are not going to stop waiting for ACKs

The obvious way past 18.46 fps is pipelining — sending frame N+1 without waiting for N's
ACK. We are not doing that, and it should not be in the pipeline design:

- The one ACK per frame **is** the backpressure signal. Without it we have no idea whether
  the device kept up, and no way to pace against a real device rather than a guess.
- It is also the takeover detector. Physical button presses produce unsolicited reports on
  the same link; reading one ACK per frame is how `canvas_invalidated` is caught within one
  frame, which is what makes the dashboard's automatic reclaim work.
- 256 pixels does not need 30 fps. R4's 7.63 fps was recorded as visually smooth motion by
  the operator. 12–15 fps is comfortably past the point of diminishing returns here.

Pipelining buys perhaps 2× on a panel that does not need it, and pays with both of the
properties that make the transport trustworthy. It stays prohibited.

## 5. Latency, for a live source

Glass-to-panel ≈ capture + downscale/quantise + one cadence period + ~66 ms measured
round-trip. At today's safe 200 ms cadence that is roughly 280–330 ms. After the Host pacing
change, at a ~100 ms cadence, roughly 180–200 ms. The chosen cadence dominates, not the wire.

## 6. What still has to be built on our side for a LIVE source

S1 accepted *precomputed* streaming: a manifest freezes a hashed frame-set file. A webcam
cannot work that way — its future pixels do not exist at review time.

The pattern is already proven in this repository: the MCP dashboard freezes the **envelope**
instead — the exact unit, the code hashes that produce pixels, lifetime, pacing floor,
budgets and stop conditions. A live-source stream manifest needs the same shape: a
`live_source` block freezing the capture/downscale/quantise code hashes in place of
`frame_set_sha256`, with everything else unchanged.

That is a small extension, and it is deliberately **not built yet** — it should be written
against the real pipeline's actual module layout once the research lands, not guessed at now.

## 7. Where the fidelity actually comes from

Ranked by effect at 16×16, largest first:

1. **Area-average downscale over the full source frame**, done in linear light (undo sRGB
   gamma, average, re-apply). Nearest-neighbour or naive box averaging in gamma space is the
   single biggest quality loss available, and it is free to avoid.
2. **Per-frame auto-exposure / contrast normalisation.** A 16×16 crop of a webcam frame is
   dominated by dynamic range, not detail. This is where "clear visuals" is won or lost.
3. **Temporal smoothing of exposure only** (not of pixels), so brightness does not flicker
   frame to frame while motion stays crisp.
4. Colour depth: last, and nearly irrelevant, per §2.
