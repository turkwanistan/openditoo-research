# OpenDitoo N980P Near-Real-Time Webcam Implementation Plan

**Date:** 2026-09-09  
**Status:** research / analysis / implementation plan only — **no Ditoo transmission performed**  
**Target feature:** `NexiGo N980P live capture → freshest useful frame → square ROI/visual translation → 16×16 RGB888 → bounded OpenDitoo session → exact Ditoo Plus`

---

## 0. Executive recommendation

Build the webcam feature as a **Windows-native camera/transform sidecar** that feeds OpenDitoo's existing authenticated, exact-unit typed session Host. Keep Bluetooth ownership in the existing Windows Host; keep camera acquisition and the hot 16×16 transform entirely on Windows; keep WSL/Python in the control/manifest/testing role, not in the per-frame data path.

The chosen production capture API is **Windows `MediaCapture` + `MediaFrameReader` in `Realtime` acquisition mode**, with `TryAcquireLatestFrame()` and `SystemRelativeTime` timestamps. This is unusually well matched to the product requirement: Microsoft explicitly defines `Realtime` mode to drop frames when the application cannot keep up, and `TryAcquireLatestFrame()` returns the latest available frame. That is exactly the desired semantics for a webcam feeding a slower display.

The live scheduler should be **latest-frame-wins and ACK-clocked**:

```text
N980P @ 60 fps
   │
   ▼
MediaFrameReader (Realtime; never buffered FIFO)
   │ newest raw frame only
   ▼
latest-raw slot (capacity 1)
   │
   ▼
latest-only processor
   │ newest processed 16×16 RGB888 only
   ▼
latest-processed slot (capacity 1)
   │
   ├── preview/telemetry (non-blocking)
   │
   ▼
transport worker: ACK complete → choose newest processed frame → send immediately
   │ one frame in flight, no catch-up burst
   ▼
authenticated 127.0.0.1:8796 /v1/session/*
   │
   ▼
existing exact-unit RFCOMM transport → one ACK/frame → Ditoo
```

### Recommended starting camera mode

Target **640×480 @ 60 fps YUY2** as the first-choice N980P capture mode, with **1280×720 @ 60 fps MJPEG** as the deterministic fallback. The reason is not that 480p is visually superior in general; it is that a 16×16 destination only needs enough source samples to survive crop/zoom, while uncompressed 640×480 YUY2 at 60 fps is still plausibly within USB 2.0 bandwidth and avoids MJPEG decode latency. A 480×480 square crop still gives 30 source pixels per Ditoo pixel before zoom. The first camera-only benchmark must verify that this exact mode is actually exposed by the owner's device and that it wins on p95 frame age. If it does not, switch to the measured best 60 fps mode using the decision rules in Milestone 1.

### Recommended v1 visual transform

Use:

```text
latest camera frame
→ configurable square ROI, centered by default
→ manual zoom/offset (v1; no face tracking)
→ area/box downsample to 16×16
→ optional small fixed post-resize contrast/saturation adjustment chosen by offline shootout
→ deterministic ≤255-color guard
→ RGB888
```

Do **not** add RGB222. OpenDitoo's exact-unit encoder consumes RGB888 and the R4/R5 full-colour measurements show payload size was not the dominant bottleneck. Do **not** dither. For the encoder's 255-palette-entry limit, if a 16×16 frame contains 256 unique colours, merge exactly one pixel into its nearest existing colour rather than globally reducing all channel precision.

### Required transport change

S1 is accepted, but its shared activity runner deliberately caps at **200 ms / 5 fps**, and the current Host activity-session profile refuses frame starts faster than **150 ms** and inserts **10 ms** between the three packets of each frame. That is policy for the MCP activity product, not the device ceiling.

For webcam streaming, preserve the same `/v1/session/open|frame|heartbeat|close` endpoints and the same single-controller/exact-target/ledger model, but add a **narrow streaming pacing profile** that can use the already-proven R5 shape:

- one frame in flight;
- one ACK per frame;
- `sendSpacingMs = 0`;
- `minFrameIntervalMs` may be `0` for ACK-clock mode or a reviewed positive floor for the first bounded trial;
- no retry, reconnect, reclaim, raw send, target selection, pipelining, delta commands, or alternate Bluetooth path.

This is not a second transport stack. It is a typed pacing profile on the already-proven session transport.

### Expected performance

Repository evidence on the exact unit is authoritative:

- **R4:** ~7.63 fps sustained over 512 full-colour frames / ~67 seconds.
- **R5:** ~18.46 fps over 1024 full-colour frames / ~56 seconds with zero inter-frame sleep and one ACK per frame.
- R5 median frame/ACK cycle was about 53 ms; max about 111 ms; no tearing was observed.

The webcam implementation should therefore target **~15–18 fps sustained** in ACK-clock mode after localhost HTTP + live-source overhead, not promise 18.46 fps. Camera capture and image processing must remain comfortably faster than transport so that the Ditoo transaction, not the webcam pipeline, is the limiting stage.

### Estimated end-to-end latency target

Before physical optical measurement, a reasonable engineering target is:

- **p50 scene-to-visible:** roughly 70–120 ms;
- **p95 scene-to-visible:** roughly 120–180 ms;

but those values are hypotheses until the camera and panel are measured optically. Source-frame age at send/ACK is measurable in software; visible panel time is not. Do not equate ACK completion with visible update.

---

## 1. Relevant current OpenDitoo state

Live repo inspected:

```text
/home/wan/Projects/openditoo-research
```

Final state check during this research session:

- branch: `main`
- worktree: clean
- HEAD: `b9fd190f2fdb7af558592822794f6b26c7f28f77`
- HEAD subject: `Accept S1 general frame streaming on the exact unit`
- local branch was 52 commits ahead of `origin/main`
- offline verifier: `DAY1_OFFLINE_PASS`, 188 tests at hydration time

Important accepted facts:

- exact unit: `11:75:58:CE:DE:C7`
- firmware: `v42012`
- RFCOMM channel: `1`
- Windows Host: `127.0.0.1:8796`
- Host transport: authenticated, exact-target, single-operation gate
- existing typed session routes:
  - `/v1/session/open`
  - `/v1/session/frame`
  - `/v1/session/heartbeat`
  - `/v1/session/close`
- RGB input geometry: exactly 16×16×3 = 768-byte RGB888
- each frame is encoded into the stock Pixel Coloring transaction and sent as three application packets
- encoder palette cardinality: 1–255 distinct RGB888 colours
- Host owns lifetime, frame/byte budgets, pacing, watchdog, exact-target guard, one-use experiment ledger, and fail-closed transport termination
- session and image operations share the same Host `imageGate`; they cannot overlap
- no retry/reconnect/reclaim in experimental sessions

### 1.1 S1 general frame streaming

S1 is accepted and should be treated as the baseline, not reimplemented.

Relevant files:

- `notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`
- `host/frame_stream.py`
- `host/activity_session.py`
- `cli/openditoo.py`
- `runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs`
- `runtime/windows/OpenDitoo.Day1.Host/Program.cs`

S1 proves:

- deterministic precomputed 16×16 RGB888 frame sets;
- typed `stream-prepare`, `stream-preview`, and `stream-run` surfaces;
- reuse of the existing Host session transport rather than a second Bluetooth stack;
- clock-indexed playback that drops old reference frames instead of stretching time;
- bounded, manifest-gated live execution;
- 42 ACKed frames / 126 packets / 2,982 application bytes in its first accepted physical stream.

S1 does **not** prove:

- live camera capture;
- >5 fps through its shared runner;
- live-source timestamp/freshness metrics;
- ACK-clock streaming via `/v1/session/*`;
- optical scene-to-display latency.

### 1.2 Current S1/activity pacing limitation

`host/activity_session.py` defines a nominal client interval of 200 ms. S1's `MIN_PLAYBACK_INTERVAL_MS` inherits that floor. The Host currently defines:

```text
ActivitySessionHost.AcceptedMinFrameIntervalMs = 150
ActivitySessionHost.ActivitySendSpacingMs = 10
```

This is a deliberate safe activity-display policy. It is not compatible with the webcam objective if left unchanged.

The webcam work should **not** lower these activity defaults globally. Instead, add a narrow typed streaming profile so the dashboard/product baseline keeps exactly its current behavior.

### 1.3 Exact-unit rate evidence to reuse, not repeat

From the accepted repository handoff and R4/R5 artifacts:

| Evidence | Shape | Result | Meaning for webcam |
|---|---|---:|---|
| R4 | full-colour, one ACK/frame, sustained | ~7.63 fps for 512 frames / ~67 s | stable full-colour motion proven |
| R5 | full-colour, one ACK/frame, no inter-frame sleep | ~18.46 fps for 1024 frames / ~56 s | synchronous ACK-clock ceiling of the tested protocol shape |
| R5 timing | zero sleep | mean ~54.2 ms, median ~53 ms, max ~111 ms | transport can be the natural clock |
| R4/R5 payload comparison | high-entropy/full colour | payload size not dominant | do not reduce colour merely to chase transport rate |

Do not repeat R1–R5.

---

## 2. Relevant OpenTivoo lessons

OpenTivoo was inspected read-only at:

```text
/home/wan/Projects/opentivoo-research
```

Its repo was intentionally preserved with legitimate untracked media/evidence. The hydrate verifier was not forced because it attempted to create a cache lock under the required read-only sandbox.

The current useful TV/video lineage is D359 through D367+, with D367 the accepted absolute-deadline 10 fps TV baseline.

### Transfer these lessons

1. **Square crop before final resize.** A tiny 16×16 target benefits from using the full canvas for the subject instead of letterboxing wide video.
2. **Separate media/reference rate from transport rate.** A 60 fps camera can feed a ~15–18 fps display without trying to transmit every camera frame.
3. **Never catch up.** OpenTivoo's successful video path uses current-time selection and skips stale reference frames.
4. **One frame in flight.** A replaceable pending/latest target is the right model.
5. **Absolute deadlines matter when using fixed-rate pacing.** D366 showed that “wait one interval, then do work” silently adds hot-path overhead. D367 moved to absolute deadlines and restored ~10 fps.
6. **Hot-path authority work must be bounded/cached safely.** D365 showed that repeated expensive authority materialization can destroy video cadence even without Bluetooth payload work.
7. **Preview exact 16×16 output enlarged with nearest-neighbour.** This is essential for tuning a transformation that looks good on the real matrix.
8. **Telemetry must include skipped/replaced frames and clock/source age**, not only nominal FPS.

### Do not transfer these Tivoo-specific assumptions

- RGB222;
- Tivoo delta transport;
- Tivoo packet-count economics;
- Tivoo 10 fps ceiling;
- Tivoo command/authority semantics;
- Tivoo transport measurements.

OpenDitoo's RGB888/full-frame R4/R5 measurements remain authoritative.

---

## 3. NexiGo N980P capabilities and local-mode status

### 3.1 Current primary-source facts

NexiGo's N980P-specific current product/technical material agrees on:

- 2 MP / 1920×1080 maximum N980P resolution;
- 1920×1080 @ 60 fps;
- 1280×720 @ 60 fps;
- 640×480 @ 60 fps;
- 120° field of view;
- manual focus;
- low-light/automatic light correction;
- MJPEG and YUY2 video formats;
- Windows 7/8/10/11+ compatibility.

The N980P-specific technical page states `MJPEG/YUY2`, manual focus, and 60 fps.

### 3.2 Important NexiGo web-page inconsistency

The current N980P support/product pages also contain a second specification block describing a 4K, Sony STARVIS 2, HDMI-capable, fixed-focus device. That block conflicts with the N980P-specific product listing, N980P-specific specification block, N980P technical-information page, and N980P manual mirrors. It appears to be unrelated/contaminating product content and must **not** be treated as the owner's N980P specification.

Use the N980P-specific 1080p60 / manual-focus / 120° / MJPEG-YUY2 data as the planning baseline, then let local mode enumeration be final truth.

### 3.3 Local capture modes were not measurable in this research sandbox

The live WSL sandbox exposed:

```text
powershell.exe: absent
cmd.exe: absent
WSL_INTEROP: absent
/dev/video*: none
ffmpeg: /usr/bin/ffmpeg
ffprobe: /usr/bin/ffprobe
```

Therefore this research session did **not** claim local N980P capture modes, camera frame age, or backend latency. Milestone 1 must perform those measurements from the user's normal Windows environment.

---

## 4. Capture-backend comparison and selected backend

### 4.1 Selected: Windows MediaCapture + MediaFrameReader, Realtime mode

Use Windows `Windows.Media.Capture` / `Windows.Media.Capture.Frames` in a Windows .NET sidecar.

Why it wins:

- `MediaFrameReader.AcquisitionMode = Realtime` is explicitly designed to drop frames that arrive while the app is still processing the previous frame.
- `TryAcquireLatestFrame()` explicitly returns the latest frame from the source and is intended to be called from `FrameArrived`.
- `MediaFrameSource.SupportedFormats` gives the actual local source formats; `SetFormatAsync` selects one deterministically.
- `MediaFrameReference.SystemRelativeTime` is QPC-correlatable, enabling real frame-age telemetry rather than inferring freshness from callback time.
- `MediaCaptureMemoryPreference.Cpu` can force CPU-backed `SoftwareBitmap` frames for a simple 16×16 software transform.
- camera capture remains native to Windows, avoiding WSL USB/interop/copying.
- it is Microsoft's modern camera stack, unlike DirectShow.

Initial settings:

```text
SharingMode: ExclusiveControl during benchmark/product capture
MemoryPreference: Cpu
StreamingCaptureMode: Video
FrameReader AcquisitionMode: Realtime
Audio: disabled / not requested
```

Use exclusive control for the benchmark because format selection and camera controls must be deterministic. If coexistence with other applications becomes a product requirement later, test `SharedReadOnly` separately; do not sacrifice deterministic mode/control in v1.

### 4.2 Media Foundation IMFSourceReader

**Status:** fallback benchmark, not initial production choice.

Advantages:

- direct Media Foundation path;
- asynchronous callback mode;
- official `MF_LOW_LATENCY` attribute;
- optional converter disabling / explicit transform policy.

Disadvantages:

- substantially more COM/interoperability code in the current .NET project;
- easier to introduce lifetime/buffer bugs;
- weaker implementation value if `MediaFrameReader Realtime` already gives fresh frames.

Escalate to an `IMFSourceReader` prototype only if the camera benchmark shows unexplained buffering in MediaFrameReader, e.g. p95 source age is >40 ms worse than the best comparison backend while actual source FPS remains healthy.

### 4.3 DirectShow / FFmpeg DirectShow

FFmpeg's DirectShow input can list device options and explicitly select `video_size`, `framerate`, and pixel format. It is useful for **enumeration and an independent benchmark baseline**.

Do not use it as the default production capture architecture. Microsoft classifies DirectShow as legacy and recommends Media Foundation/modern capture APIs for new code. Community reports also show that low-latency FFmpeg/ffplay tuning is highly device/backend dependent.

### 4.4 OpenCV CAP_MSMF / CAP_DSHOW

Use only as a comparison harness if convenient; do not make OpenCV a production dependency in v1.

Reasons:

- OpenCV exposes multiple Windows backends but backend properties are not uniformly honored.
- `CAP_PROP_BUFFERSIZE` behavior is backend/platform dependent; issue reports show it may return false or have no effect.
- recent OpenCV issues continue to report camera-specific MSMF startup/behavior differences.
- wrapping a native API in OpenCV adds another layer without giving better freshness semantics than MediaFrameReader's explicit Realtime/latest-frame contract.

### 4.5 Backend decision rule

Production remains MediaFrameReader unless **another backend beats it by at least 10 ms on p95 capture-frame age**, while also meeting all of:

- ≥58 actual frames/s for a 60 fps mode over a 60-second camera-only run;
- no monotonic growth in frame age;
- no queue/backlog after deliberate 100 ms processing stalls;
- p95 interarrival ≤25 ms for a nominal 60 fps source;
- no corruption/timeouts;
- equal or lower operational complexity.

If no candidate clears that bar, MediaFrameReader wins even if another backend is a few milliseconds faster.

---

## 5. Chosen architecture and data-flow diagram

### 5.1 Architecture choice: B — small Windows camera/transform service feeds existing Host

Do **not** move capture into WSL. Do **not** make the Bluetooth Host itself a general camera framework unless profiling proves localhost IPC is materially limiting.

Create a small Windows-only .NET executable/service:

```text
OpenDitoo.Webcam
```

It has no Bluetooth APIs, no target selector, no raw-send path, and no firmware/device persistence code. It knows only:

- camera enumeration/capture;
- transform/preview/telemetry;
- the existing authenticated Host's typed `/v1/session/*` API;
- a frozen webcam experiment manifest.

The existing Host remains the **only** owner of:

- target identity;
- RFCOMM channel;
- Bluetooth connection;
- packet encoding verification;
- send/ACK;
- session lifetime/budgets/watchdog;
- one-controller gate;
- durable one-use experiment ledger.

### 5.2 Data flow

```text
+--------------------- Windows ----------------------+
|                                                    |
| NexiGo N980P                                       |
|   │ USB/UVC                                        |
|   ▼                                                |
| MediaCapture / MediaFrameReader (Realtime)         |
|   │ FrameArrived + QPC source timestamp            |
|   ▼                                                |
| LatestRawFrameSlot [capacity 1]                    |
|   │ replace old immediately                        |
|   ▼                                                |
| Latest-only transform worker                       |
|   │ square ROI / zoom / area resize / enhancement  |
|   │ palette ≤255 guard                             |
|   ▼                                                |
| LatestProcessedSlot [capacity 1, 768 bytes]        |
|   │                                                |
|   ├── source + 16×16 preview                       |
|   └── telemetry                                    |
|   │                                                |
|   ▼                                                |
| ACK-gated webcam sender                            |
|   │ authenticated HTTP loopback                    |
|   ▼                                                |
| OpenDitoo Host :8796 /v1/session/*                 |
|   │ exact target + budgets + encoder hash + gate   |
|   ▼                                                |
| RFCOMM ch1 → exact Ditoo → ACK                     |
|                                                    |
+----------------------------------------------------+

WSL/Python remains outside the per-frame path:
manifest validation / authority claim / offline verifier / orchestration.
```

### 5.3 Why not Host-owns-camera for v1

Embedding capture into the existing Host would eliminate a localhost call but would also:

- mix camera dependencies with the security-sensitive target/transport process;
- make camera bugs more likely to affect the Host lifecycle;
- make independent camera benchmarking harder;
- increase rollback blast radius.

At a ~54 ms R5 transport cycle, a correctly implemented loopback HTTP request should be a small fraction of the cycle. Measure it. Only collapse the sidecar into the Host if local profiling shows ≥8 ms p95 loopback/session overhead and that overhead is materially preventing the target rate.

---

## 6. Crop / ROI / zoom policy

### 6.1 v1 policy

Use a **stable manually configurable square ROI**.

Default:

```text
roi_center_x = 0.50
roi_center_y = 0.50
zoom = 1.00
mirror = false
```

For a source width `W`, height `H`:

```text
base_side = min(W, H)
side = base_side / zoom
center = normalized configurable (x, y)
clamp square ROI fully inside source bounds
```

`zoom` range for v1: **1.0–4.0**. This is enough to compensate for the N980P's wide FOV while preserving abundant source samples even at 480p.

### 6.2 Why manual ROI beats face tracking for v1

At 16×16, the biggest visual gain usually comes from filling the matrix with the intended subject. Manual ROI/zoom offers that benefit with:

- zero detector latency;
- no tracking jitter;
- no subject-switch surprises;
- no ML/model dependency;
- predictable framing for non-face scenes;
- trivial implementation and testability.

Face-aware crop is explicitly **post-v1**. Add it only if a later A/B test shows a large usability benefit and its ROI motion can be smoothed without visible 16×16 jitter.

### 6.3 Optional future face tracking gate

If tested later:

- detector may run at 5–10 Hz, not camera rate;
- apply deadband and velocity limits;
- smooth ROI center/scale with a critically damped filter;
- fall back to last manual ROI after detection loss;
- never let detector processing block capture or transport.

---

## 7. Exact 16×16 resize / preprocessing / colour policy

### 7.1 Baseline resampler

Use **area/box averaging** for the large downsample to 16×16.

Rationale:

- OpenCV documents area interpolation as preferred for decimation and moiré reduction;
- anti-aliasing/local averaging is the correct broad class of operation for an extreme reduction such as 480→16 or 720→16;
- it suppresses unstable single-pixel source details that would otherwise shimmer on the matrix.

Implement the production resampler directly in the sidecar rather than taking a heavyweight OpenCV dependency. At these sizes, a straightforward box accumulator over the selected ROI is inexpensive.

### 7.2 Required visual shootout

The final fixed default should be chosen by Milestone 2, using enlarged nearest-neighbour previews from the owner's N980P. Compare:

- A: sRGB box/area averaging — **provisional default**;
- B: linear-light box/area averaging via LUT;
- C: bicubic with antialiasing;
- D: Lanczos/stronger sinc-style resize;
- E: two-stage area → 32×32 then bicubic → 16×16.

The benchmark is required because linear-light resizing is mathematically defensible but can change perceived tiny-display contrast, and Lanczos/bicubic can produce ringing or unstable detail when collapsing a webcam scene to only 256 pixels.

Decision rule:

1. reject any method whose p95 transform time is >5 ms on the user's PC;
2. reject any method that produces obvious temporal shimmer/ringing in hand-motion footage;
3. blind-rank enlarged 16×16 previews across seven scene classes;
4. choose a challenger over sRGB area only if it wins a majority of scene classes **and** does not lose the motion/flicker class.

If no challenger clearly wins, keep sRGB area.

### 7.3 Preprocessing policy

Avoid per-frame automatic histogram equalization/auto-levels in v1 because it can pump brightness/contrast temporally.

Candidate fixed post-resize operations:

- contrast multiplier: 1.00, 1.08, 1.15;
- saturation multiplier: 1.00, 1.10;
- gamma: 1.00, 0.95 only;
- optional very mild 3×3 unsharp after resize.

Default before shootout: **neutral** (`contrast=1`, `saturation=1`, `gamma=1`, sharpening off).

Promote one fixed enhancement preset only if the visual shootout shows a consistent win across face, low-light, colourful, and motion scenes without flicker/halos.

### 7.4 Colour policy

Keep **RGB888** through the OpenDitoo boundary.

Do not add:

- RGB222;
- temporal dithering;
- ordered dithering;
- palette cycling;
- transport-driven colour reduction.

### 7.5 Deterministic 255-colour guard

The Ditoo encoder supports at most 255 distinct colours, while a 16×16 image can theoretically contain 256 unique colours.

Replace S1's whole-frame low-bit quantization for the live path with a lower-distortion rule:

1. count unique RGB values;
2. if ≤255, return unchanged;
3. if exactly 256, find the pair with smallest deterministic weighted RGB distance;
4. replace one pixel of the second colour with the first colour;
5. tie-break by pixel index / RGB integer so output is deterministic.

Suggested distance:

```text
d = 3*dr² + 4*dg² + 2*db²
```

Only one output pixel changes in the worst case. With at most 256 colours, the O(256²) comparison is trivial relative to the transport cycle.

---

## 8. Freshest-frame scheduler

### 8.1 Core invariant

**Displayed-frame age is more important than source-frame delivery ratio.**

A 60 fps camera feeding a ~15–18 fps Ditoo should drop roughly 70% of camera frames. That is correct.

### 8.2 Acquisition

`FrameArrived` must do minimal work:

1. call `TryAcquireLatestFrame()`;
2. record source sequence + `SystemRelativeTime` + callback QPC;
3. copy/convert the frame into a bounded reusable raw buffer;
4. atomically replace `LatestRawFrameSlot`;
5. signal processor;
6. dispose the frame reference immediately.

No FIFO.

### 8.3 Processing

Use a **latest-only continuous processor**, not “process every camera frame” and not “wait until transport is ready and then begin expensive decode.”

Loop:

```text
wait for latest-raw signal
snapshot newest raw sequence
transform to 16×16
if a newer raw frame appeared while processing:
    replace pending work on next iteration; never enqueue both
publish latest-processed frame + source timestamps
```

If transform takes 2–5 ms, it can comfortably keep up with 60 fps. If it ever falls behind, the raw slot replacement naturally drops stale frames.

### 8.4 Transport

Exactly one send may be active.

```text
open reviewed bounded session
last_sent_source_seq = none
while session live:
    if no processed frame newer than last_sent_source_seq:
        wait for processed-frame signal or stop/lifetime signal
        continue

    frame = atomic latest processed snapshot
    POST /v1/session/frame
    await HTTP response / device ACK
    record ACK + source age metrics
    last_sent_source_seq = frame.source_seq
    # loop immediately; select newest now, not the frame that was pending earlier
close session
```

Rules:

- no send queue;
- no catch-up burst;
- no retransmit;
- no duplicate send merely to maintain nominal FPS;
- acquisition/processing continue while the Host waits for ACK;
- if source pauses, transport waits rather than re-sending stale imagery;
- heartbeat is independent from frame traffic.

### 8.5 Fixed-rate mode

For the first physical webcam trial only, a manifest may set a positive `minFrameIntervalMs` (recommended 83 ms ≈ 12 fps). The sender still chooses the freshest frame each time.

If fixed-rate pacing is implemented client-side, use **absolute deadlines**, carrying forward the D367 OpenTivoo lesson. Never “sleep interval after ACK.”

### 8.6 ACK-clock mode

Near-ceiling mode should be:

```text
ACK completes → select newest processed camera frame → send immediately → await ACK
```

No artificial FPS timer.

---

## 9. Thread/process/buffer ownership

### Process 1: `OpenDitoo.Webcam` sidecar

#### Thread/task A — camera acquisition

Owns:

- `MediaCapture`;
- `MediaFrameReader`;
- frame-source selection;
- camera disposal/restart within the same bounded run only if no Ditoo session is active yet.

Writes only `LatestRawFrameSlot`.

#### Thread/task B — transform worker

Reads `LatestRawFrameSlot`, writes `LatestProcessedFrameSlot`.

Owns:

- ROI/zoom;
- resize;
- fixed enhancement;
- ≤255-colour guard;
- 16×16 preview image generation.

#### Thread/task C — transport worker

Owns:

- Host session client;
- one current HTTP request;
- sender state;
- heartbeat;
- frame/ACK/source-age telemetry.

Reads only `LatestProcessedFrameSlot`.

#### Thread/task D — preview/UI

Reads snapshots only. It must never hold a raw-frame lock or delay acquisition/transport.

### Process 2: existing OpenDitoo Host

Unchanged ownership of exact target/RFCOMM/packet/ACK/gate/budgets/ledger.

### Bounded memory

Use pooled buffers and at most:

- two raw source buffers (current write + published latest);
- two 768-byte processed buffers;
- one optional preview bitmap per surface;
- bounded telemetry ring or streaming JSONL writer.

There must never be a frame FIFO whose memory grows with camera or transport lag.

---

## 10. Integration with the current OpenDitoo streaming primitive / Host

### 10.1 Reuse

Reuse without semantic changes:

- exact target and RFCOMM transport;
- `/v1/session/open|frame|heartbeat|close` route family;
- Host `imageGate` single-controller ownership;
- encoder and encoder SHA verification;
- session budgets/lifetime/watchdog;
- durable one-use Host ledger;
- fail-closed on transport ambiguity/canvas takeover;
- manifest/code-hash/authority pattern;
- 8 MB CLI response bound/truncation protections where relevant.

### 10.2 Add a typed session pacing profile

Extend open-session schema with a constrained profile field, for example:

```json
{
  "sessionProfile": "activity" | "streaming_ack_clock"
}
```

Backward compatibility:

- omitted → `activity`
- `activity` preserves **exactly** the current 150 ms Host floor and 10 ms packet spacing
- `streaming_ack_clock` uses the reviewed manifest's min interval down to 0 and fixed packet spacing 0, matching already accepted R5 timing semantics

Do not make `sendSpacingMs` a free caller argument. The profile selects a frozen Host constant.

### 10.3 Session status additions

Return/record:

- `sessionProfile`;
- effective `minFrameIntervalMs`;
- effective packet spacing;
- frame start QPC/timestamp;
- ACK completion QPC/timestamp;
- per-frame Host elapsed ms if practical.

### 10.4 Do not use S1's precomputed `FrameSetRenderer` for webcam

`host/frame_stream.py` is intentionally file/frame-set based and time-indexed. A live camera has no ordered reference timeline to preserve. Share validation/manifest conventions where useful, but add a live-source path rather than forcing a webcam into a directory-of-frames abstraction.

---

## 11. Expected FPS policy

### Camera

- target acquisition: 60 fps;
- acceptance: ≥58 measured fps over stable 60-second runs in the selected mode, or document the camera/lighting-driven reason for lower output.

### Transform

- target sustained throughput: ≥120 transformed frames/s in synthetic benchmark;
- p95 transform latency: ≤5 ms;
- processing should therefore never be the Ditoo bottleneck.

### Ditoo

#### First physical webcam trial

- cap at ~12 fps (`83 ms` floor) for a short bounded validation;
- do not use a 6/8/10 ladder.

#### Near-ceiling trial

- ACK-clock (`0 ms` client/Host inter-frame floor, fixed zero packet spacing in streaming profile);
- target: **15–18 fps** sustained;
- success floor: ≥15.5 fps over a 10–20 second bounded run if the software path is healthy;
- investigate, rather than automatically fail, if rate is 13–15.5 fps but source-age/visual-latency targets are excellent and there are no transport errors.

Do not chase >R5 by pipelining or alternate protocol work in this project.

---

## 12. Detailed latency budget

The measurement chain is:

```text
physical scene
→ sensor exposure/acquisition
→ UVC/device buffering
→ Windows camera stack
→ MediaFrameReader callback
→ raw-frame copy/format conversion
→ latest-only processing
→ processed-slot wait
→ localhost Host submission
→ Host encode/hash verification
→ three-packet RFCOMM transaction
→ ACK
→ panel-visible update
```

### 12.1 Initial budget / targets

| Stage | Initial engineering budget | Evidence status |
|---|---:|---|
| sensor exposure + frame acquisition @60 fps | ~8–17 ms typical scale | hypothesis; camera-dependent |
| UVC + Windows capture path | p50 ≤20 ms, p95 ≤40 ms target | must measure with `SystemRelativeTime` |
| raw copy + transform | p50 ≤2 ms, p95 ≤5 ms | must benchmark locally |
| processed-slot age before send | typically ≤1 camera interval (~16.7 ms) | scheduler target |
| localhost request + Host encode/admin | p95 ≤5–8 ms target | must measure |
| exact-unit synchronous send/ACK | R5 median ~53 ms, mean ~54.2 ms | exact repo measurement |
| ACK → visibly updated panel | unknown | requires optical trial |

### 12.2 Software-computable metrics

For every sent frame record:

- source sequence;
- `SystemRelativeTime`;
- capture callback QPC;
- transform start/end QPC;
- processed publish QPC;
- sender selection QPC;
- Host POST start/end QPC;
- ACK completion time;
- source age at capture callback;
- source age at transform completion;
- source age at send start;
- source age at ACK;
- raw replacements since prior send;
- processed replacements since prior send.

Report p50 / p95 / max.

### 12.3 Do not misuse ACK time

ACK proves the tested transport transaction completed in the same sense already used by OpenDitoo. It does not prove the physical LEDs have visibly updated at that exact instant.

### 12.4 Optical scene-to-visible method

Use a separate high-frame-rate camera (120 or 240 fps is preferable) to record **both**:

1. a monitor/source region being viewed by the N980P, and
2. the Ditoo panel.

Run a source stimulus that alternates large, 16×16-friendly full-field patterns, e.g. black ↔ white or distinct solid quadrants, at known times. Count high-speed-camera frames between source transition and corresponding Ditoo transition.

Repeat at least 30 transitions. Report p50, p95, min, max in milliseconds. This directly measures scene-to-visible latency without firmware/device changes.

---

## 13. Metrics / telemetry

### Capture

- selected camera name/id;
- actual format: width, height, subtype, nominal FPS;
- received frame count;
- actual acquisition FPS;
- interarrival p50/p95/max;
- source timestamp age p50/p95/max;
- callback duration p50/p95/max;
- raw frames replaced before processing;
- camera faults/discontinuities.

### Processing

- raw frames consumed;
- processed frames published;
- raw frames skipped/replaced;
- transform latency p50/p95/max;
- selected ROI/zoom;
- unique colours before/after palette guard;
- palette-guard activations;
- processor CPU time.

### Transport

- frames attempted / ACKed;
- achieved Ditoo FPS;
- per-frame POST/ACK duration p50/p95/max;
- source age at send p50/p95/max;
- source age at ACK p50/p95/max;
- application packets/bytes;
- duplicate-source-frame sends (expected 0);
- session budget remaining/used;
- terminal reason/outcome;
- retry/reconnect/reclaim flags (must remain false in experimental run).

### Queue/freshness invariants

Expose:

```text
raw_queue_depth = 0 or 1
processed_queue_depth = 0 or 1
transport_in_flight = 0 or 1
```

Any observed depth >1 is a defect.

---

## 14. Minimal operator controls and previews

Keep v1 small.

### Required controls

- camera selector;
- mode selector (enumerated actual modes only);
- start/stop preview;
- ROI X/Y;
- zoom;
- mirror toggle;
- enhancement preset selector (`neutral` plus benchmark winner);
- start reviewed live experiment only via manifest-gated run path.

### Required status

- capture mode + actual FPS;
- achieved Ditoo FPS;
- source age p50/p95;
- frames received / raw replaced / processed / sent;
- transport state;
- camera error / Host error.

### Previews

1. normal source preview with ROI rectangle;
2. 16×16 output enlarged at least 16× or 24× with **nearest-neighbour only**;
3. optional side-by-side “source ROI” and “matrix view”.

A lightweight Windows Forms preview embedded in the sidecar is sufficient. Do not build a large web application.

---

## 15. Concrete module/file-level changes

The executor should re-check HEAD before editing, but against `b9fd190` the proposed layout is:

### New Windows sidecar project

```text
runtime/windows/OpenDitoo.Webcam/
  OpenDitoo.Webcam.csproj
  Program.cs
  CameraCatalog.cs
  CameraCapture.cs
  CameraMode.cs
  LatestFrameSlot.cs
  FrameTransform.cs
  PaletteGuard.cs
  HostSessionClient.cs
  WebcamManifest.cs
  WebcamMetrics.cs
  PreviewForm.cs              # optional in first code milestone, required before v1 done
```

Responsibilities:

- `CameraCatalog.cs`: enumerate source groups/sources and exact supported formats.
- `CameraCapture.cs`: initialize MediaCapture, set exact format, Realtime reader, timestamp/copy, shutdown.
- `LatestFrameSlot.cs`: lock-minimal bounded replacement slot with monotonically increasing sequence.
- `FrameTransform.cs`: ROI + box/area resize + fixed enhancement.
- `PaletteGuard.cs`: deterministic 256→255 nearest-colour merge.
- `HostSessionClient.cs`: authenticated typed session calls only; no Bluetooth API.
- `WebcamManifest.cs`: strict manifest parsing; no free target/rate overrides.
- `WebcamMetrics.cs`: QPC timestamps, histograms/percentiles, JSON result.
- `PreviewForm.cs`: source ROI + nearest-neighbour 16×16 preview.

### Existing Host

```text
runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs
runtime/windows/OpenDitoo.Day1.Host/Program.cs
```

Changes:

- add explicit session profile enum/validation;
- preserve current activity constants;
- add streaming-profile constants using R5-proven zero packet spacing and permitted zero frame floor;
- make effective pacing profile immutable for session lifetime;
- expose profile/timing in status/results;
- retain exact same packet builder/ACK semantics/image gate/ledger/target guard.

Do not add a raw-send endpoint.

### Python / repo validation

Likely additions:

```text
host/webcam_stream.py
scripts/verify_webcam_stream.py
tests/ or existing verifier fixtures as repo convention dictates
notes/OPENDITOO-N980P-REALTIME-WEBCAM-IMPLEMENTATION-PLAN.md   # only if owner later chooses to copy this plan into repo
```

`host/webcam_stream.py` should define manifest schema, authority checks, deterministic code-hash set, and offline result validation. It should not become a frame-forwarding loop.

### CLI

Extend `cli/openditoo.py` only with narrow orchestration commands if consistent with the live repo at implementation time, e.g.:

```text
webcam-manifest-check
webcam-result-check
```

Camera enumeration/benchmark may remain the Windows sidecar's typed CLI if invoking Windows executables from WSL would add fragile interop. Do not force per-frame WSL traversal merely for CLI uniformity.

---

## 16. Dependency-ordered implementation milestones

## Milestone W0 — freeze baseline and define webcam contracts

**Objective/value**
Prevent the webcam feature from accidentally widening S1, Runtime 002, or the activity session's accepted semantics.

**Implementation work**

- rehydrate current OpenDitoo HEAD/status/verifier;
- record exact S1 and R4/R5 evidence used;
- define `sessionProfile` contract with `activity` backward-compatible default and `streaming_ack_clock` new value;
- define webcam manifest schema;
- define telemetry/result schema;
- define no-device sidecar commands.

**Files/modules likely affected**

- new webcam schema module;
- verifier fixtures/tests;
- no live Host behavior yet.

**Dependencies**

- none beyond current clean repo.

**Offline tests**

- old S1/activity manifests parse identically;
- missing/unknown webcam profile fails closed;
- target/rate/raw-send fields not present or not caller-configurable;
- existing offline verifier remains green.

**Evidence produced**

- contract/schema note;
- test output.

**Ditoo authority required?** No.

**Exit criteria**

- all current tests pass;
- new schema tests pass;
- no behavior change to Runtime 002/S1.

---

## Milestone W1 — actual N980P enumeration and camera-only backend benchmark

**Objective/value**
Replace generic webcam assumptions with measurements from the owner's exact N980P and Windows installation.

**Implementation work**

- implement `OpenDitoo.Webcam enumerate` using MediaFrameSource `SupportedFormats`;
- enumerate width/height/subtype/FPS exactly;
- implement a 60-second camera-only benchmark;
- benchmark at minimum, if exposed:
  - 640×480@60 YUY2;
  - 640×480@60 MJPEG;
  - 1280×720@60 MJPEG;
  - 1280×720@60 YUY2 if exposed/actually viable;
  - 1920×1080@60 MJPEG;
- benchmark MediaFrameReader Realtime first;
- gather a short FFmpeg DirectShow or other independent baseline if available;
- deliberately sleep the consumer for 100 ms several times and verify frame age recovers immediately rather than replaying a FIFO.

**Files/modules likely affected**

- `OpenDitoo.Webcam.csproj`
- `CameraCatalog.cs`
- `CameraCapture.cs`
- `WebcamMetrics.cs`
- benchmark result fixtures/tests.

**Dependencies**

- W0 contracts.

**Offline/camera-only tests**

- no Host token required;
- no Host HTTP call;
- no Bluetooth assembly/reference in sidecar project if practical;
- mode selection rejects unenumerated mode;
- FrameReference always disposed;
- Realtime mode asserted.

**Benchmarks/evidence produced**

Per mode/backend:

- actual FPS;
- p50/p95/max interarrival;
- p50/p95/max source timestamp age;
- callback duration;
- stall recovery age;
- CPU;
- drops/discontinuities;
- 10–20 representative raw snapshots outside repo or in explicitly approved evidence path.

**Decision rule**

1. prefer 60 fps modes;
2. choose lowest p95 source age;
3. among modes within 5 ms p95 of best, prefer lowest CPU/bandwidth;
4. require 16×16 quality not to materially lose after manual zoom;
5. provisional winner is 640×480@60 YUY2; if unavailable or worse, use measured winner, likely 720p60 MJPEG.

**Ditoo authority required?** No.

**Exit criteria**

- exact local mode table captured;
- selected default source mode named with measurements;
- no growing buffer demonstrated.

---

## Milestone W2 — 16×16 visual-quality shootout

**Objective/value**
Select a deterministic transform that preserves recognizability, not merely speed.

**Implementation work**

- implement square ROI/manual zoom;
- implement sRGB area baseline;
- implement benchmark-only candidate resamplers/linear-light mode;
- implement neutral + candidate fixed enhancement presets;
- implement deterministic 255-colour guard;
- build preview export with nearest-neighbour enlargement.

**Representative scenes**

1. normal desk-distance face;
2. close face;
3. hand/motion;
4. colourful scene;
5. high-contrast scene;
6. low light;
7. fine detail/text.

Capture at least a few seconds per scene from the exact N980P so temporal stability can be judged, not just still images.

**Files/modules likely affected**

- `FrameTransform.cs`
- `PaletteGuard.cs`
- `PreviewForm.cs` or preview exporter;
- transform tests/fixtures.

**Dependencies**

- selected W1 mode.

**Offline tests**

- exact 768-byte output;
- deterministic output for same source/config;
- crop clamping;
- mirror correctness;
- zoom boundary behavior;
- unique colour count ≤255;
- 256-unique-colour fixture changes exactly one pixel;
- no dithering/time dependence.

**Benchmarks/evidence produced**

- enlarged contact sheets/GIFs for each candidate;
- p50/p95 transform time;
- CPU;
- blinded visual rank notes.

**Decision rule**

- sRGB area wins by default;
- promote another resampler/preset only under the explicit rule in §7.2;
- manual ROI/zoom is v1; face tracking is rejected unless later evidence changes the decision.

**Ditoo authority required?** No.

**Exit criteria**

- one exact default transform preset frozen;
- p95 transform ≤5 ms;
- no visible candidate-induced motion shimmer accepted.

---

## Milestone W3 — bounded freshest-frame pipeline, no Host/device

**Objective/value**
Prove camera → latest slots → transform → scheduler semantics without any Ditoo I/O.

**Implementation work**

- `LatestRawFrameSlot`;
- latest-only processor;
- `LatestProcessedFrameSlot`;
- simulated ACK transport with configurable 40–100 ms completion delay;
- sender that only selects after prior simulated ACK;
- heartbeat/cancellation/shutdown;
- JSON telemetry.

**Files/modules likely affected**

- `LatestFrameSlot.cs`
- `CameraCapture.cs`
- `FrameTransform.cs`
- `WebcamMetrics.cs`
- simulated Host client/test double.

**Dependencies**

- W1 mode + W2 transform.

**Offline tests**

- source 60 fps, fake transport 18 fps → no queue >1;
- source frames are replaced, not queued;
- after fake ACK, selected sequence is the newest available;
- no duplicate source frame sent if no newer frame exists;
- fake 200 ms transport stall does not produce a catch-up burst;
- cancellation closes cleanly;
- memory remains bounded.

**Benchmarks/evidence produced**

- camera FPS;
- processing throughput;
- source age at fake-send/fake-ACK;
- raw/processed replacement counts;
- CPU/memory;
- queue-depth invariant.

**Ditoo authority required?** No.

**Exit criteria**

- p95 transform ≤5 ms;
- fake 54 ms ACK cycle sustains ≥18 sender iterations/s where new camera frames exist;
- p95 source age at fake send ≤50 ms;
- queue depths never exceed one.

---

## Milestone W4 — add streaming pacing profile to existing Host, offline only

**Objective/value**
Make `/v1/session/*` capable of the already-proven R5 pacing shape without changing the activity product or adding a new Bluetooth surface.

**Implementation work**

- add `sessionProfile` to open request;
- preserve `activity` defaults 150 ms / 10 ms;
- add `streaming_ack_clock` fixed 0 ms packet spacing and accepted min interval down to 0;
- include effective profile/timing in response/ledger/result;
- update sidecar `HostSessionClient` to send manifest-frozen profile;
- never make packet spacing a free caller parameter.

**Files/modules likely affected**

- `runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs`
- `runtime/windows/OpenDitoo.Day1.Host/Program.cs`
- Host/session tests and offline verifier;
- `HostSessionClient.cs`.

**Dependencies**

- W0 contract.

**Offline tests**

- old activity request with no profile behaves byte/semantically as before;
- activity request below 150 ms still rejected;
- streaming profile permits 83 ms and 0 ms manifest floors;
- streaming profile always uses zero packet spacing;
- unknown profile rejected;
- budgets/watchdog/image gate/ledger unchanged;
- no raw route added;
- exact target remains compiled/frozen;
- existing verifier green.

**Benchmarks/evidence produced**

- local no-device unit timings;
- Host API contract fixtures.

**Ditoo authority required?** No.

**Exit criteria**

- all old tests pass;
- new profile tests pass;
- code review can show activity product timing unchanged.

---

## Milestone W5 — local end-to-end dry run through encoder/Host client boundary, no Ditoo

**Objective/value**
Prove the full application path and telemetry before physical authority.

**Implementation work**

Run:

```text
N980P → capture → latest raw → transform → 16×16 → palette guard
→ OpenDitoo encoder/hash → fake/in-memory typed Host session → ACK-clock scheduler
```

If useful, run the actual Host in a no-device/fake-transport test harness; do not connect to Bluetooth.

**Files/modules likely affected**

- sidecar integration;
- test transport/fake Host;
- result verifier.

**Dependencies**

- W3 + W4.

**Offline tests**

- encoder hash sidecar vs canonical OpenDitoo encoder fixtures;
- 255-colour bound;
- manifest/profile frozen;
- session lifetime/budget stop;
- camera disconnect before session open handled safely;
- simulated camera disconnect during session requests clean close, no retries;
- simulated Host fault → terminal unknown/fail closed.

**Benchmarks/evidence produced**

- selected camera FPS;
- p50/p95 capture age;
- p50/p95 transform;
- fake Host transaction overhead;
- source age at send/ACK;
- replacement counts;
- CPU/memory.

**Thresholds**

- ≥58 camera fps for selected 60 fps mode unless hardware evidence says otherwise;
- p95 transform ≤5 ms;
- p95 source age at simulated send ≤75 ms;
- no queue >1;
- processing throughput comfortably >100 fps;
- zero unbounded allocation trend over 5 minutes.

**Ditoo authority required?** No.

**Exit criteria**

- dry path passes all thresholds or exceptions are documented and plan updated before live work.

---

## Milestone W6 — freeze first bounded physical webcam trial

**Objective/value**
Prepare, but do not silently execute, the first exact-unit webcam activation.

**Implementation work**

Create a new reviewed experiment identity, suggested:

```text
OPENDITOO-WEBCAM-N980P-001
```

Freeze:

- exact Ditoo target + firmware + endpoint;
- selected exact N980P device/mode;
- ROI/zoom/preset;
- relevant source/code hashes;
- exact Windows Host build hash;
- `sessionProfile=streaming_ack_clock`;
- positive `minFrameIntervalMs=83` (~12 fps) for first trial;
- lifetime 10 seconds;
- max frames 125 (or tighter derived bound);
- max TX bytes derived from worst accepted RGB888 packet geometry;
- retry/reconnect/reclaim false;
- stop/failure policy;
- acceptance thresholds below.

**Files/modules likely affected**

- new experiment manifest/note only after code is frozen;
- verifier fixture.

**Dependencies**

- W5 pass;
- clean repo;
- exact Host build identified.

**Offline tests**

- manifest check;
- consumed-id rejection fixture;
- hash checks;
- budgets sufficient but bounded;
- Runtime 002 standing grant explicitly not used.

**Benchmarks/evidence produced**

- frozen preflight report.

**Ditoo authority required?** **Yes to execute, no to prepare.**

**Exit criteria**

- manifest reviewed;
- explicit operator grant names this exact experiment before any transmission;
- Runtime 002 remains unchanged.

---

## Milestone W7 — first bounded physical webcam acceptance trial

**Objective/value**
Prove that a true live N980P frame reaches the Ditoo with fresh-frame semantics and acceptable quality.

**Preconditions**

- explicit grant for the exact W6 manifest;
- product supervisor stopped intentionally so one controller owns the Ditoo;
- exact Host/build verified;
- N980P mode verified;
- no stock app holding RFCOMM;
- no consumed manifest reuse.

**Run**

- ~10 seconds;
- ~12 fps max via 83 ms floor;
- ordinary face/hand motion and one high-contrast source transition;
- one session, one connection, no retry/reconnect.

**Measure**

- requested/effective profile;
- camera actual FPS;
- ACKed Ditoo FPS;
- frames sent;
- source raw/processed replacements;
- source age at send/ACK p50/p95/max;
- ACK p50/p95/max;
- packets/bytes;
- camera/Host errors;
- visible recognizability;
- subjective lag.

**Acceptance**

- no transport fault/canvas invalidation;
- ≥11 fps achieved;
- p95 source age at send ≤100 ms;
- no queue >1;
- no catch-up bursts;
- output recognizable under chosen ROI;
- operator accepts visible quality;
- clean close and product supervisor can be restored afterward under its existing unchanged policy.

**Ditoo authority required?** Yes — exact one-use experiment.

**Exit criteria**

- accepted result frozen or failure documented without retrying same identity.

---

## Milestone W8 — near-ceiling freshness trial

**Objective/value**
Characterize the fastest sensible **existing one-ACK-per-frame** webcam policy using Ditoo's own R5 evidence. Do not import OpenTivoo's 30/54 fps numbers and do not create another rate ladder.

**Current implementation state**

Historical attempts 003 and 004 are consumed and replay-forbidden. Active candidate `OPENDITOO-WEBCAM-N980P-005` preserves the corrected bounded transport shape:

- `sessionProfile=streaming_ack_clock`;
- Host frame-start floor **40 ms**;
- ACK-gated client dispatch-start floor **50 ms**, leaving 10 ms request-arrival margin;
- zero packet spacing via profile;
- 10-second lifetime;
- max **201 frames / 603 application packets / 211,854 application bytes**;
- same N980P source, transform, encoder and Host protocol as accepted W7;
- one frame in flight; no retry/reconnect/reclaim/pipelining/catch-up.

Attempt 004 established that 50/40 pacing itself survived; it failed only because the client compared Host `Environment.TickCount64` telemetry to client `Stopwatch` as though they were one clock domain. Candidate 005 fixes only that telemetry invariant.

**Measure**

All W7 metrics plus:

- steady-state fps and source-age by quarters;
- client dispatch intervals;
- Host frame elapsed and client HTTP/ACK elapsed as **separate clock-domain telemetry**;
- signed `clientMinusHostElapsedMs` observational residual, never treated as literal HTTP overhead or an ordering invariant;
- percent of source frames replaced;
- duplicated source timestamps;
- p95 frame age at send/ACK;
- camera/transform counts and capacity-one queue-depth maxima.

**Acceptance target**

- ≥15.5 fps sustained is the original target, but characterize measured behavior even if lower;
- no tearing/faults visible;
- p95 source age at send ≤80 ms;
- no increasing age trend by run quarter;
- queue depth invariant;
- no retries/pipelining.

**Ditoo authority required?** Yes — fresh exact one-use experiment.

**Exit criteria**

- sustainable near-ceiling behavior characterized once; failures are preserved under consumed identities and are not retried;
- do not start a new rate ladder unless a specific measured defect requires one.

---

## Milestone W9A — source identity + deterministic motion truth

**Objective/value**
Make source uniqueness and scheduler skips directly observable before interpreting panel behavior. This carries forward the portable OpenTivoo lesson that source cadence, scheduler cadence, transport cadence and visible display cadence are separate systems.

**Implementation work**

- add a monotonically increasing **capture/source sequence ID** at successful N980P frame acquisition;
- propagate that ID through raw latest-frame slot → transformed 16×16 frame → sender selection telemetry without changing pixel/transport behavior;
- record bounded selection evidence sufficient to derive first/last source ID, duplicate selections, source-ID gaps/skips and sent-frame count;
- build a deterministic monitor stimulus for the N980P field of view with large temporal markers/frame counters that survive the 16×16 transform;
- keep camera acquisition, transform and transport decoupled; do not queue stale frames;
- do **not** change W8-005 before it runs, and do not preconvert live webcam frames into a prerecorded bundle. The existing asynchronous transform worker already keeps resizing/quantization outside the sender's transport wait.

**Offline tests**

- sequence ID is monotonic and preserved across transform;
- replacement of an older slot never reuses or rewinds identity;
- duplicate/no-new-frame selection is distinguishable from a newly captured frame;
- deterministic stimulus/frame-counter sequence is reproducible and decodable after the chosen 16×16 transform;
- no additional Bluetooth/Host ownership path.

**Evidence produced**

- camera/source IDs captured, transformed, selected and sent;
- duplicate-selection count;
- source sequence gaps and replacement/skipping statistics;
- deterministic motion-truth fixture/hash.

**Ditoo authority required?** No for implementation/offline stimulus validation.

**Exit criteria**

- source uniqueness can be distinguished from scheduler/transport/display repetition without inference from nominal FPS alone.

---

## Milestone W9B — combined unique-frame + optical physical-latency trial

**Objective/value**
Measure true scene-to-visible latency **and** determine whether unique source changes remain unique through the visible Ditoo output, rather than treating ACK or transport FPS as panel refresh.

**Implementation work**

- source monitor in N980P FOV displays the W9A deterministic temporal-marker stimulus;
- external high-speed camera records source monitor and Ditoo simultaneously;
- run the accepted webcam path for at least 30 clearly decodable transitions;
- correlate stimulus/source sequence, sender-selected source ID, Host/transport completion and visible Ditoo transition where evidence permits;
- keep display observations separate from transport claims.

**Offline tests**

- stimulus timing deterministic;
- frame-count/time conversion verified;
- source-ID correlation logic tested against known dropped/duplicated sequences.

**Benchmarks/evidence produced**

- true p50/p95/min/max scene-to-visible latency;
- visible unique-transition/repeat/skipped-transition counts;
- explicit separation of camera/source duplicate, scheduler skip, transport failure and visible panel repeat where the evidence is sufficient;
- operator observation of smoothness/tearing/artifacts.

**Dependencies**

- W7 pass; W8 characterization complete; W9A instrumentation complete.

**Ditoo authority required?** Yes for the bounded Ditoo run; external stimulus/filming setup itself does not.

**Exit criteria**

- optical latency is reported independently from source-age-at-ACK;
- no claim is made that transport FPS equals panel FPS.

---

## Milestone W10 — v1 productization / operator polish

**Objective/value**
Turn accepted experimental behavior into a small usable webcam application without widening the existing dashboard Runtime 003 authority.

**Implementation work**

- finalize camera selector/mode display;
- ROI/zoom controls;
- source + matrix preview;
- robust stop/camera-disconnect behavior;
- concise operator documentation;
- decide whether webcam gets a separate standing product authority only after experimental acceptance;
- for any **fixed-rate** webcam mode, use a monotonic absolute-deadline timeline (`next_due += interval`) rather than `sleep(interval)` after work/ACK;
- if a logical deadline is missed, advance/skip missed logical slots and select the newest frame; never catch up with a burst;
- duplicate/no-new-frame selection must not update the actual last-transmit/send-floor timestamp as though a frame was sent.

ACK-clock/near-ceiling mode remains separately defined by the accepted W8 transport contract; absolute-deadline product pacing must not silently weaken Host floors or one-frame-in-flight semantics.

**Files/modules likely affected**

- `PreviewForm.cs`;
- sidecar CLI/docs;
- scheduler/telemetry code as required;
- a **new** product policy only if explicitly approved later.

**Dependencies**

- W7 accepted;
- W8 characterized;
- W9A complete;
- W9B strongly preferred.

**Offline tests**

- absolute-deadline scheduler absorbs bounded work instead of accumulating it into every frame period;
- deliberately missed deadlines produce skipped logical slots, not catch-up sends;
- duplicate/no-new-frame input does not consume a transmit interval;
- no auto-start unless separately approved;
- no target selector/raw send;
- no mutation/widening of Runtime 003 dashboard authority;
- all original OpenDitoo verifier tests pass.

**Ditoo authority required?** No for coding/testing; **yes** for any live webcam product authority/cutover.

**Exit criteria**

- one-command/operator-friendly start/stop;
- accepted preview/ROI usability;
- no authority boundary regression;
- fixed-rate pacing has explicit deadline/skip telemetry and no catch-up behavior.

---

## Deferred post-v1 research — beyond the synchronous one-ACK-per-frame ceiling

Do **not** schedule this as part of W8-W10. OpenDitoo already measured about **18.46 fps** as the ceiling of the tested full-colour synchronous one-ACK-per-frame shape. OpenTivoo's 30 fps acceptance and 54/56 fps transport bracket are methodology references, not Ditoo capability evidence.

Only open a new research track if W9B shows that the physical Ditoo display visibly benefits from more unique update cadence and the user wants to pursue it. A separately reviewed plan could then investigate protocol-shape changes such as safe pipelining/batching, device/firmware buffering, or alternate/delta frame semantics. Such work requires fresh authority boundaries and must not be smuggled into webcam productization.

---

## 17. Camera/backend benchmark methodology and thresholds

### 17.1 Mode enumeration

Enumerate actual formats directly from `MediaFrameSource.SupportedFormats`; record:

```text
device stable id / display name
subtype
width × height
frame-rate numerator/denominator
```

Do not infer mode support by repeatedly calling “set” and trusting success.

### 17.2 Per-mode run

For each meaningful 60 fps mode:

1. warm camera for 3–5 seconds;
2. record 60 seconds;
3. no preview rendering in primary timing run;
4. collect QPC source/callback timing;
5. perform three deliberate 100 ms consumer stalls at known times;
6. verify post-stall callback returns to a current frame rather than draining old frames;
7. repeat winning two modes three times.

### 17.3 Backend candidates

Primary:

- MediaFrameReader Realtime.

Comparison only:

- IMFSourceReader async/low-latency if needed;
- FFmpeg DirectShow;
- OpenCV MSMF/DSHOW only if already convenient.

### 17.4 Selection hierarchy

1. freshness / p95 source age;
2. no hidden backlog;
3. stable 60 fps timing;
4. 16×16 visual quality at useful zoom;
5. CPU/bandwidth;
6. implementation complexity.

---

## 18. Visual-quality benchmark methodology

Create a deterministic capture set from the owner's N980P, not stock internet images.

For each of the seven scene classes, choose representative frames at multiple motion phases and produce:

- source crop;
- 16×16 raw result enlarged 24× nearest-neighbour;
- candidate A–E side by side;
- optional short animated nearest-neighbour preview.

Score:

- face/subject recognizability;
- silhouette/edge readability;
- colour identity;
- highlight/shadow preservation;
- temporal stability;
- ringing/haloing;
- perceived noise;
- processing time.

Fine text is an adversarial scene, not a requirement to make text readable at 16×16.

---

## 19. First bounded physical webcam acceptance trial

See W7. The central rule is: **do not use the first device run to discover basic camera/backend/transform issues**. Those must already be settled camera-only/offline.

Suggested manifest bounds:

```text
lifetime_seconds: 10
min_frame_interval_ms: 83
max_frames: 125
session_profile: streaming_ack_clock
retry: false
reconnect: false
reclaim: false
```

The exact `maxTxBytes` must be derived from the canonical encoder's worst-case accepted 255-colour frame cost plus the three-packet transaction, not guessed.

---

## 20. Near-ceiling and physical-latency follow-up trials

### Near-ceiling

One new identity, ACK-clock, zero floor, zero packet spacing via fixed profile. No rate ladder.

### Optical latency

One later bounded run under its own authority if needed. Film source and Ditoo simultaneously at high frame rate. Report actual optical latency distribution.

---

## 21. Failure / recovery / rollback behavior

### Camera fails before Host session open

- fail with typed camera error;
- do not consume Ditoo experiment authority if the repo's claim model permits safely validating camera before claim;
- no Host/device I/O.

### Camera disconnects after Host session opens

- stop sending immediately;
- request clean session close;
- if close outcome is ambiguous, record unknown and do not retry/reconnect under same experiment;
- do not send last frame repeatedly.

### Transform exception

- stop sender;
- close session cleanly if possible;
- freeze result/error;
- never substitute a malformed/raw frame.

### Host/HTTP fault during frame

- treat as transport ambiguity;
- no resend;
- no reconnect;
- no same-manifest rerun.

### Canvas invalidated / stock takeover

- yield immediately under existing Host semantics;
- no reclaim in experimental webcam session unless a later product policy explicitly establishes it.

### Operator stop

- cancel camera/processor;
- stop new frame submissions;
- close Host session;
- dispose reader/camera;
- restore product supervisor only as a separate existing operation, without modifying Runtime 002 policy.

### Rollback

The rollback is architectural: remove/disable the webcam sidecar and streaming profile usage; the existing S1/activity/product behavior remains intact because `activity` timing defaults were never changed.

---

## 22. Authority boundary

This boundary is non-negotiable.

Current standing authority:

```text
OPENDITOO-PRODUCT-RUNTIME-002
```

covers **MCP Dashboard v1 only**.

It does not authorize webcam streaming.

### No authority required

W0–W5:

- repo implementation;
- camera enumeration;
- camera-only benchmark;
- visual transforms/previews;
- fake transport;
- Host unit/offline tests;
- manifest preparation.

### Explicit new authority required

At the transition from **W6 prepared manifest → W7 physical execution**.

Every physical webcam run must have:

- a new reviewed experiment identity;
- exact target/firmware/endpoint;
- frozen code/build hashes;
- frozen session profile/rate/budgets;
- explicit operator grant naming that exact identity;
- one-use consumption.

### Never do as part of this feature

- widen or mutate Runtime 002;
- re-arm consumed manifests;
- add target selection;
- add raw send;
- add generic Bluetooth;
- enumerate proprietary Ditoo commands;
- modify firmware;
- create persistent Ditoo writes;
- enter service/MassBoot mode;
- pipeline multiple frames;
- add alternate Bluetooth protocols;
- modify OpenTivoo runtime/task/state/port.

---

## 23. Risks and evidence-backed alternatives

### Risk: MediaFrameReader still has unacceptable hidden latency on this webcam

**Detection:** high `nowQPC - SystemRelativeTime` despite Realtime mode, or age grows after induced stall.

**Alternative:** prototype asynchronous `IMFSourceReader` with `MF_LOW_LATENCY` and explicit native media type. Adopt only if it beats MediaFrameReader by ≥10 ms p95 and remains robust.

### Risk: 640×480 loses too much detail under zoom

**Detection:** visual W2 shootout fails face/hand recognizability versus 720p.

**Alternative:** 1280×720@60 MJPEG if p95 capture age remains within 10 ms of best mode. The destination is tiny, so source resolution should be increased only for measured crop/zoom quality.

### Risk: MJPEG decode adds frame age

**Detection:** 720p/1080p MJPEG source timestamps are materially older than uncompressed 480p YUY2.

**Alternative:** stay with 480p YUY2; do not chase source resolution.

### Risk: localhost HTTP/session overhead materially reduces R5-like rate

**Detection:** fake/local Host p95 frame POST overhead ≥8 ms, or near-ceiling physical throughput is far below R5 while Host send/ACK itself remains fast.

**Alternative:** first optimize allocations/serialization and use pooled buffers. Only then consider moving the sender into the existing Host or a tighter IPC mechanism. Do not create a second Bluetooth implementation.

### Risk: RGB hex JSON serialization costs too much

Current `/v1/session/frame` sends 768 bytes as hex (~1.5 KB plus JSON), trivial in bandwidth but it may allocate. At ~18 fps this is still tiny. Profile before changing API shape. A binary body is not justified unless measured overhead is material.

### Risk: 256 unique colours are frequent

**Mitigation:** nearest-colour one-pixel merge. Measure activation rate. If >50% frames and visually unstable (unlikely), compare a fixed 5/6-bit-per-channel quantizer as a separate offline visual test; do not default to RGB222.

### Risk: automatic exposure creates perceived lag or pumping

The N980P advertises automatic light correction and is manual focus. Keep room lighting stable for latency benchmarks. If auto exposure materially changes frame interval under low light, benchmark a fixed exposure setting as an operator-controlled camera configuration later, but do not make persistent camera/system configuration part of v1.

### Risk: preview hurts timing

Preview must read snapshots and run at an independently capped rate (e.g. 15–30 fps). Primary benchmark runs should support preview off.

---

## 24. Explicit non-goals

- firmware reversing;
- MassBoot/service mode;
- proprietary command enumeration;
- raw RFCOMM/Bluetooth send surfaces;
- target selection;
- multi-device support;
- pipelining multiple frames;
- delta transport discovery;
- alternate Bluetooth protocols;
- audio streaming/sync in v1;
- face tracking in v1;
- background/autostart productization before experimental acceptance;
- large web UI;
- RGB222 compatibility work;
- “deliver every camera frame” semantics;
- rate-ladder repetition of R1–R5.

---

## 25. Final definition of done

The webcam feature is done when all of the following are true:

1. The exact N980P's actual Windows modes are enumerated and frozen in evidence.
2. A measured default 60 fps camera mode is selected; 640×480@60 YUY2 remains preferred only if local evidence supports it.
3. MediaFrameReader Realtime is proven not to accumulate stale frames under induced stalls, or a benchmarked better backend is selected under the stated rule.
4. Manual square ROI/zoom is usable and stable.
5. One deterministic 16×16 transform preset is selected by the exact-camera visual shootout.
6. Every output is 768-byte RGB888 and ≤255 distinct colours without RGB222/dithering.
7. Capture → process → transport uses only latest-frame slots with capacity one.
8. Camera acquisition continues while Ditoo ACK is outstanding.
9. No catch-up bursts or stale FIFO delivery exist.
10. Transform p95 is ≤5 ms and the image pipeline is comfortably faster than Ditoo transport.
11. Existing `/v1/session/*` transport is reused; no second Bluetooth stack exists.
12. Existing activity/dashboard timing is unchanged.
13. A narrow `streaming_ack_clock` session profile is covered by offline tests and tied to reviewed webcam manifests.
14. First physical webcam trial passes at ~12 fps with fresh-frame metrics and operator-accepted visual quality.
15. One near-ceiling trial characterizes ACK-clock behavior, ideally ≥15.5 fps sustained, without new protocol work.
16. Software reports source age at send/ACK, replacements/drops, queue depth, ACK timing, and achieved FPS.
17. Optical scene-to-visible latency is measured independently of ACK time.
18. Runtime 002 remains untouched and webcam live authority remains separately reviewed/granted.
19. Camera disconnect, Host fault, canvas invalidation, stop, and ambiguous send all fail closed without silent retry/reconnect.
20. A fresh executor can reproduce build, benchmark, preview, bounded experiment preparation, and result verification from repo docs alone.

---

## 26. Source/evidence map

### Exact OpenDitoo repo evidence

Primary paths inspected:

- `notes/OPENDITOO-STREAMING-HANDOFF-2026-09-09.md`
- `notes/OPENDITOO-S1-STREAM-PRIMITIVE-2026-09-09.md`
- `notes/OPENDITOO-HANDOFF-2026-09-09.md`
- `AGENTS.md`
- `START_HERE.md`
- `host/frame_stream.py`
- `host/activity_session.py`
- `host/ditoo_pixel_coloring.py`
- `cli/openditoo.py`
- `runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs`
- `runtime/windows/OpenDitoo.Day1.Host/DitooStaticImageProtocol.cs`
- `runtime/windows/OpenDitoo.Day1.Host/Program.cs`
- `experiments/DAY1-R4-MOTION-SUSTAINED-001.json`
- `experiments/DAY1-R5-NOSLEEP-CEILING-001.json`

Evidence class: **exact-unit / exact-repo measurement**.

### OpenTivoo comparative evidence

Primary paths inspected read-only:

- `notes/OPENTIVOO-TV-VIDEO-IMPLEMENTATION-PLAN.md`
- `notes/OPENTIVOO-D365-TV-FRAMERATE-DIAGNOSIS-2026-09-09.md`
- `notes/OPENTIVOO-D366-TV-PACING-PHYSICAL-FAILURE-2026-09-09.md`
- `notes/OPENTIVOO-D367-TV-PRODUCT-ACTIVATION-2026-09-09.md`
- `host/tivoo_video_source.py`
- `runtime/windows/OpenTivoo.Host/TvProductCore.cs`

Evidence class: **exact OpenTivoo implementation/physical measurement; transferable scheduling lessons only**.

### Official NexiGo

- N980P product page: <https://www.nexigo.com/products/n980p-60fps-webcam>
- N980P technical information: <https://www.nexigo.com/pages/n980p-technical-information>
- N980P support: <https://www.nexigo.com/pages/n980p-support>

Evidence class: **official product documentation**, subject to the documented contaminated 4K/HelloCam-like block on current support/product pages.

### Official Microsoft camera/media documentation

- MediaFrameReader processing guide: <https://learn.microsoft.com/en-us/windows/apps/develop/camera/process-media-frames-with-mediaframereader>
- MediaFrameReader AcquisitionMode: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframereader.acquisitionmode>
- TryAcquireLatestFrame: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframereader.tryacquirelatestframe>
- MediaFrameSource SupportedFormats: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframesource.supportedformats>
- MediaFrameSource SetFormatAsync: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframesource.setformatasync>
- MediaFrameReference SystemRelativeTime: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframereference.systemrelativetime>
- MediaCapture memory preference: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapturememorypreference>
- MediaCapture sharing mode: <https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacaptureinitializationsettings.sharingmode>
- Media Foundation `MF_LOW_LATENCY`: <https://learn.microsoft.com/en-us/windows/win32/medfound/mf-low-latency>
- Source Reader attributes: <https://learn.microsoft.com/en-us/windows/win32/medfound/source-reader-attributes>
- DirectShow status: <https://learn.microsoft.com/en-us/windows/win32/directshow/directshow>

Evidence class: **official API semantics**.

### FFmpeg / image processing

- FFmpeg DirectShow device docs: <https://ffmpeg.org/ffmpeg-devices.html#dshow>
- OpenCV interpolation docs: <https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html>
- scikit-image anti-aliasing/downsampling docs: <https://scikit-image.org/docs/stable/auto_examples/transform/plot_rescale.html>
- ImageMagick resize/linear-light discussion: <https://usage.imagemagick.org/resize/>

Evidence class: **official/reputable technical documentation**.

### Community / implementation observations used only as secondary evidence

- OpenCV issue #27917 (MSMF camera initialization behavior): <https://github.com/opencv/opencv/issues/27917>
- OpenCV issue #17687 (MSMF camera-specific startup behavior): <https://github.com/opencv/opencv/issues/17687>
- OpenCV issue #23430 (`CAP_PROP_BUFFERSIZE` not necessarily honored): <https://github.com/opencv/opencv/issues/23430>

These observations support the decision not to assume an OpenCV wrapper provides reliable low-buffer semantics. They do not override local N980P measurements.

---

# Executor handoff summary

Implement in this order:

```text
W0 contract
→ W1 exact N980P mode/backend measurements
→ W2 exact-camera 16×16 visual shootout
→ W3 latest-frame dry pipeline
→ W4 narrow Host streaming pacing profile, offline only
→ W5 full no-device dry run
→ W6 freeze exact first experiment
→ explicit owner grant boundary
→ W7 12 fps physical webcam acceptance
→ W8 one ACK-clock near-ceiling characterization
→ W9A source identity + deterministic motion truth
→ W9B combined unique-frame + optical latency measurement
→ W10 product polish + absolute-deadline fixed-rate scheduler / separate authority decision
→ optional post-v1 protocol-shape research only if W9B shows visible benefit
```

The main engineering idea should remain simple throughout: **capture faster than the Ditoo, retain only the newest useful image, and let the existing one-ACK-per-frame Ditoo transaction be the clock.**
