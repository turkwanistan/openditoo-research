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

*This is not a fidelity problem and does not deserve a sophisticated quantiser.* 256 pixels
can never show more than 256 colours; being limited to 255 costs you exactly one merged
pair. We already reduce deterministically by dropping channel low bits until the frame fits
(`quantize_to_palette_limit`). If you prefer to do it upstream, fine — just guarantee ≤255
distinct colours and keep it deterministic. **Do not spend effort here.** At 16×16 the
fidelity budget is spent almost entirely on downscaling, not colour depth.

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

## 3. The rate budget — measured, not assumed

| Component | Cost per frame | Source |
| --- | --- | --- |
| Device wire: 3 packets + one ACK, full colour, no sleeps | **54.2 ms** | R5, 1024 frames / 55.54 s, operator confirmed no tearing |
| Same, sustained with 10 ms intra-frame spacing | 131.0 ms | R4, 512 frames / 67.2 s, no degradation |
| Our encode + sha256 + hex (250-colour frame) | 0.24 ms median | measured offline, this session |
| WSL → Windows Host loopback HTTP RTT | 2.17 ms median (p95 3.9) | measured offline, this session |
| **Our total client overhead** | **~2.5 ms** | sum of the above two |

**The client is ~4% of the frame budget.** Our software is not, and never was, the
constraint. `18.46 fps` (R5) is therefore very close to what this architecture can realize:
54.2 + 2.5 ≈ 57 ms ⇒ **~17.5 fps realizable ceiling**, synchronous, one ACK per frame.

What actually limits us today is two **policy constants**, neither of them physics:

| Constant | Value | Where | Cost to change |
| --- | --- | --- | --- |
| `MCP_CLIENT_FRAME_INTERVAL_MS` | 200 ms | `host/activity_session.py:503` | **already bypassed** — `frame_stream.stream_session()` dispatches on the manifest floor instead |
| `AcceptedMinFrameIntervalMs` | 150 ms | `ActivitySessionHost.cs` (C#) | Host rebuild → new DLL hash → **Runtime 003 product policy + grant**, because the live policy binds `fb750078...` |

So: **6.67 fps is available now** with no Host change. Going beyond it to ~15 fps is one
one-line C# change plus the product-policy ceremony that a new Host binary requires.

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

Glass-to-panel ≈ capture + downscale/quantise + one cadence period + 54 ms wire. At 150 ms
cadence that is roughly 210–260 ms; at a lifted 66 ms cadence, roughly 120–140 ms. The wire
is not the dominant term — the chosen cadence is.

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
