# OpenDitoo webcam integration route — adopted plan and amendments — 2026-09-09

## Status

`OPENDITOO-N980P-REALTIME-WEBCAM-IMPLEMENTATION-PLAN.md` (external research, in the repo root)
is **adopted as the route** for live webcam streaming, with the amendments in §3 below. Its
milestone ladder W0–W10 replaces the ad-hoc streaming sequence this project was following.

Its factual claims were checked against the repository rather than taken on trust. The R4/R5
figures it cites — 53 ms median ACK, 111 ms worst frame, 15.4 ms stdev, zero packet spacing,
zero inter-frame delay, payload not dominant — all match the frozen experiment artifacts.
Its authority section matches `AGENTS.md`, including never widening Runtime 002, no
pipelining, no raw send, and a fresh named grant per physical run.

## 1. What the plan changed in our design

**Pacing.** This project was about to make the Host *wait* when a frame arrived early. The
plan's ACK-clocked profile is better: the client sends only after the previous ACK, so it
cannot be early and the race that killed `OPENDITOO-S2-STREAM-RATE-001` cannot occur at all.
It is also R5's already-accepted shape rather than new behaviour. **Adopted.**

**Palette guard.** Our guard dropped channel low bits across the whole frame (a gradient fell
to 232 colours). The plan's §7.5 rule is strictly better and is now implemented: a 16×16 frame
holds at most 256 colours against a 255 cap, so one merge always suffices — find the closest
pair by weighted distance and repaint that single pixel. **Adopted; one pixel changes instead
of every pixel.**

**Architecture.** Camera capture and the hot transform belong in a Windows sidecar, with
WSL/Python kept in the control/manifest/testing role and out of the per-frame path. Agreed:
our measured loopback RTT is only ~2 ms, but Python has no business in a 60 fps capture loop.

## 2. What we built for it (this session, offline)

Implemented and offline-verified — **204 tests PASS**, no device I/O, no deployment:

- `ActivitySessionHost` gained named session profiles. `activity` is unchanged (150 ms floor,
  10 ms packet spacing) and is what an absent profile resolves to, so the MCP dashboard keeps
  its exact behaviour. `streaming_ack_clock` uses 0 ms packet spacing and a 40 ms floor.
- A profile is a **name**; the Host owns the constants each name resolves to, confirms the
  applied profile in its open response, and refuses an unknown name rather than defaulting.
  Timing is never a caller argument.
- `/v1/session/frame` now returns `hostFrameElapsedMs`, the Host's own send-to-ACK time. S2
  could only see HTTP round trip and had to infer the wire share.
- `frame_stream.stream_session()` dispatches ACK-clocked under that profile, and
  `FrameSetRenderer` gained ACK-advance with duplicate skipping — without which two identical
  consecutive frames deadlock, since an unchanged frame is never sent and no ACK ever arrives.
- The client refuses to send if the Host did not confirm the requested profile
  (`SESSION_PROFILE_NOT_CONFIRMED`).
- The verifier now pins the Python and C# streaming floors to each other, because a client
  that believes in a lower floor than the Host enforces gets a terminal refusal, not a slow
  frame.

Build: `runtime/windows/OpenDitoo.Day1.Host/bin/Streaming/net8.0`, SHA-256
`56e56e220b5175ce9318fe29984ad042456a9b1c8856675e40bf3b26de192328`, 0 warnings,
`HOST_SELFTEST_PASS cases=9 failures=0`.

**Deliberately built to a separate output directory.** The live product policy hash-checks the
repository's `bin/Release/net8.0` DLL, so an in-place rebuild would make the running dashboard
refuse to start with `PRODUCT_HOST_HASH_MISMATCH` on its next restart. `bin/Release/net8.0`
remains `fb750078…` and `product-check` still passes.

## 3. Amendments to the plan

**3.1 Keep a non-zero Host floor permanently.** The plan allows `minFrameIntervalMs` down to 0.
We keep 40 ms in the streaming profile forever, not just for the first trial. Under an ACK
clock it never gates — R5's median ACK is 53 ms — but the authority model requires the *Host*
to bound the rate, not the client. If ACKs ever returned instantly, this is what still holds.

**3.2 Expect 10–13 fps, not 15–18.** The plan predates
`OPENDITOO-S2-STREAM-RATE-001`, which measured the client path for the first time: dispatch to
ACK is median 66 ms / p95 93 ms through the HTTP session route, against R5's 53 ms at the wire.
Localhost HTTP plus our client costs ~13 ms per frame. ACK-clocked that is ~15 fps at the
median, but the 111 ms worst frames remain, so sustained expectation should be 10–13 fps. The
plan's §23 flags this as a risk; it should be the headline number instead.

**3.3 Jitter matters less here than our own notes imply.** R5's "budget below the ceiling"
advice came from precomputed animation, where a hitch breaks intended timing. Live webcam
content has no intended timing — a 111 ms frame is just a slightly staler frame. This is an
argument for ACK-clock over fixed-rate mode, and against spending effort smoothing cadence.

**3.4 Confirm the camera mode before building on it.** 640×480 YUY2 @60 is ~37 MB/s against
roughly 40 MB/s practical USB 2.0. Marginal. W1's enumeration must confirm the mode actually
exists on the owner's unit before any downstream work assumes it.

**3.5 The sidecar's palette guard must match ours byte for byte.** Same closest-pair rule, same
weighted distance, same scan-order tie-break. Otherwise offline previews stop predicting what
the device is sent, and every visual acceptance becomes unverifiable.

## 4. Gate 1 CLOSED OUT — Runtime 003 cutover is live

The operator authorized the Host deployment in-session ("deploy the host binary down. its ok if
it goes down for a bit, we'll get it back up."), and it is done.

- `refresh_openditoo_day1_host.ps1 -Apply` rebuilt and redeployed with its own staging, backup
  and automatic rollback: `WINDOWS_BUILD=PASS`, `REFRESH_STATUS=PASS_TYPED_IMAGE`,
  `OPENTIVOO_TASK=preserved`.
- Repository and installed DLL are byte-identical at
  `0da3a18b52647a91e4cf2b13349af09dc7c60fec6b3ac13067c1f3f31372decb`.
- `/v1/status` now reports `sessionProfile=activity`, `sendSpacingMs=10` — the profile plumbing
  is live and defaults to the dashboard's existing behaviour.
- **Runtime 003 policy** (`product/OPENDITOO-PRODUCT-RUNTIME-003.json` committed and deliberately
  unauthorized; the authorized copy is the local mode-0600 policy). It differs from Runtime 002
  only in the trusted Host hash: `runtime_revision` stays 2 because the Python supervisor is
  byte-identical, and every dashboard operating number — 150 ms floor, 200 ms cadence, budgets,
  reconnect/reclaim, no raw send, no target override — is unchanged. Its scope explicitly grants
  no streaming authority.
- Dashboard verified back up on the new binary: `status=connected`, 33 frames ACKed,
  `last_error=null`, `reconnects=0`, `reclaims=0`.

Rollback, if ever needed: `.openditoo-local/rollback-runtime-002/` holds the previous DLL
(`fb750078...`) and the previous local policy.

Runtimes 001 and 002 remain committed as records of what was reviewed against superseded Host
builds, and are deliberately no longer hash-valid — re-validating them would mean pretending an
old policy describes this binary. Tests assert exactly that.

## 5. Gate 2 — the only one still closed

**Any live streaming transmission** needs a new reviewed manifest and a grant naming its
experiment id, per `AGENTS.md`. No blanket pre-authorization is valid for this, including a
general "yolo mode" instruction: the rule exists precisely so that transmission authority cannot
be inherited from enthusiasm or from build/deploy capability.

## 5b. Where the plan's milestones now stand

| Milestone | State |
| --- | --- |
| W0 freeze baseline / contracts | done — `notes/OPENDITOO-STREAM-PRODUCER-CONTRACT-2026-09-09.md` |
| W4 Host streaming pacing profile, offline | **done** — implemented, built, self-tested, 204 tests |
| W1 camera enumeration + benchmark | **done** — see §8. Mode selected: NV12 640x480@60 |
| W2 16×16 visual shootout | after W1 |
| W3 live-source contract (repo side) | **done** — `source_kind: live`, envelope-freeze, `LiveFrameSource` |
| W3 bounded freshest-frame pipeline (sidecar) | after W1/W2 |
| W5 end-to-end dry run, no Ditoo | after W3; needs the Host deployed to be meaningful |
| W6/W7 first physical webcam trial | gated on §4 |

## 6. W1 blocker — RESOLVED

The camera was not attached when this was written; the owner plugged it in during the session
and W1 completed. §8 has the results. The original blocker text is kept below because its
reasoning about not building on an assumed mode list is what §8.2 went on to confirm.

### Original blocker

Checked on Windows this session:

- `Get-CimInstance Win32_PnPEntity` returns **no device** of `PNPClass` `Camera` or `Image`,
  none bound to the `usbvideo` service, and nothing matching `cam`, `N980`, `Webcam`, or
  `USB Camera`. 98 USB controller devices are present, so USB enumeration itself is healthy.
- `ffmpeg` is not installed on Windows, so the DirectShow `-list_options` fallback for mode
  enumeration is also unavailable.

So the N980P is not currently plugged into this machine. W1 cannot start, and nothing
downstream of it should be built on an assumed mode list — including the plan's recommended
640×480 @ 60 YUY2, which is ~37 MB/s against roughly 40 MB/s of practical USB 2.0 and needs
measurement rather than optimism.

To unblock: plug the N980P into the Windows host (a USB 3 port, so the marginal-bandwidth
question does not decide the mode for us), then W1's enumeration and camera-only benchmark can
run with no Ditoo authority at all. Installing `ffmpeg` on Windows would also give a second,
independent mode enumeration to cross-check the WinRT one.

## 7. What proceeded instead — the live-source contract

The plan's §10.4 is right that a webcam must not be forced into S1's directory-of-frames
abstraction. That work is camera-independent, so it went ahead: a `live` source kind whose
manifest freezes the **envelope** — the producer's code hashes, the session profile, lifetime,
floor and budgets — rather than a frame-set hash, exactly as the MCP dashboard already freezes
its renderer instead of its future pixels. It is exercised by a synthetic producer, so the
sidecar has a contract and a passing test to build against before the camera arrives.

## 8. W1 results — the camera is real, and two plan assumptions are refuted

Device: **NexiGo HD Webcam**, `USB\VID_0C45&PID_2690` (Sonix), `usbvideo`, status OK.
Tool: `runtime/windows/OpenDitoo.Webcam.Probe` (`enumerate` / `benchmark` / `snapshot`). It
references nothing of the Ditoo Host — no Bluetooth, no token, no HTTP — and cannot reach the
device. No Ditoo authority was involved in any of this.

### 8.1 Deployment constraint discovered first

`MediaCapture.InitializeAsync` fails with `COMException 0x80070490 (ERROR_NOT_FOUND)` for every
initialization strategy when the executable runs from `\\wsl.localhost\...`. Copied to a local
Windows path (`C:\temp\...`) the identical binary succeeds immediately.

**So the Windows camera sidecar must be deployed to a local Windows path, not run from the WSL
share.** The existing Ditoo Host already does this (`%LOCALAPPDATA%\OpenDitoo\Day1Host`), so the
precedent and the installer pattern both exist. This would otherwise have looked like a camera
or permission fault; camera privacy consent was checked and is `Allow` at HKCU, HKLM and
NonPackaged.

### 8.2 The mode table refutes the plan's recommended mode

50 formats exposed. Summarised:

| Subtype | Resolutions | Frame rates |
| --- | --- | --- |
| MJPG | 320×240 … 1920×1080 | 60, 30 at every resolution |
| NV12 | 320×240 … 1920×1080 | 60, 30 at every resolution |
| YUY2 | 320×240, 352×288, 640×480 | **30 max** |
| YUY2 | 800×600 / 1024×576 / 864×480 / 960×720 / 1280×720 | 20 / 15 / 10 / 10 / 10 |
| YUY2 | 1600×896, 1920×1080 | **5** |

**640×480 @ 60 YUY2 — the plan's provisional winner — does not exist on this device.** YUY2 caps
at 30 fps even at 480p. The bandwidth concern was correct; the camera resolves it by simply not
offering the mode. **NV12 @ 60 is exposed at every resolution**, which the plan did not consider,
and it is the better choice anyway: uncompressed planar YUV with no MJPEG decode step, at 12
bits/pixel rather than YUY2's 16.

### 8.3 Measured (12 s per mode, MediaFrameReader Realtime, TryAcquireLatestFrame)

| Mode | measured fps | interarrival p50/p95 | source age p50/p95 | callback p50 |
| --- | ---: | ---: | ---: | ---: |
| NV12 640×480@60 | 18.99 | 49.99 / 52.96 | 16.8 / 20.02 | 0.08 |
| MJPG 640×480@60 | 19.00 | 49.94 / 54.92 | 17.34 / 22.19 | 0.07 |
| NV12 1280×720@60 | 18.91 | 49.92 / 53.27 | 17.6 / 20.83 | 0.06 |
| NV12 640×480@30 | 18.00 | 50.66 | — / 35.21 | — |
| YUY2 640×480@30 | 18.11 | 50.65 | — / 33.12 | — |
| MJPG 320×240@60 | 18.36 | 49.94 | — / 18.16 | — |

**Realtime acquisition behaves exactly as the plan predicted.** Deliberate 100 ms consumer
stalls were injected three times per run; frame age immediately afterwards was p50 17.4 ms,
max 20.0 ms — indistinguishable from steady state. There is no FIFO and no growing buffer.
Zero null acquisitions. Callback cost is negligible (~0.08 ms).

### 8.4 The ~20 fps ceiling is the room, not the camera

Every mode lands at ~50 ms interarrival regardless of resolution (320×240 to 1280×720), format
(NV12/MJPG/YUY2) or requested rate (30 or 60). That rules out USB bandwidth — NV12 720p60 is
~83 MB/s against 480p60's ~28 MB/s, and they measure identically — and rules out MJPEG decode
and a lying mode descriptor.

`ExposureControl.Supported` is **false** on this camera, so exposure cannot be read or pinned
through WinRT. Measured instead: mean luma of captured stills is **~52/255**, i.e. a dark scene
*even with* a 50 ms shutter. 50 ms interarrival is exactly 1/20 s. The sensor is holding the
shutter open to reach a usable image and the frame rate falls out of that.

**This is not a blocker.** Our transport ceiling is ~10–13 fps, so even a dim-room 19 fps camera
is already faster than the display path — the plan's requirement that capture stay comfortably
ahead of transport is met as-is. Better light should restore 60 fps and shrink frame age further.

Follow-ups, neither on the critical path:
- re-run the benchmark in bright light to confirm 60 fps returns;
- if exposure must be pinned regardless of light, that needs DirectShow (which exposes camera
  property pages WinRT does not) — `ffmpeg`/DirectShow would also give the independent rate
  cross-check W1 asks for. Not installed on Windows.

### 8.5 Selected default mode

**NV12 640×480 @ 60** per the plan's own decision rule: 60 fps exposed, lowest p95 source age
(20.02 ms vs MJPG's 22.19), no decode stage, lowest bandwidth among the NV12 60 fps options, and
a 480×480 square crop still gives 30 source pixels per Ditoo pixel before zoom.

Stills for the W2 shootout: `C:\temp\openditoo-stills` — deliberately outside the repository.

## 9. W2 results — transform harness complete, default frozen, ranking outstanding

`host/frame_transform.py` is the reference transform; `tests/frame_transform_cases.json` is the
shared fixture the C# sidecar must reproduce, since a preview that does not equal what the
device receives makes every visual acceptance unverifiable. Sources in the fixture are
*generated from documented integer formulas* rather than stored, so both languages build them
identically.

Order: square ROI → optional quarter-turn → mirror → area average in linear light → optional
fixed adjustment → **palette guard last** (anything after it could reintroduce a 256th colour).

### 9.1 Measured, on the owner's PC, over real captured stills

| Candidate (plan §7.2) | p50 ms | p95 ms | rule 1 (p95 ≤ 5 ms) |
| --- | ---: | ---: | --- |
| A `srgb_area` (provisional default) | 1.83 | 4.25 | PASS |
| B `linear_area` | 3.18 | 4.45 | PASS |
| C `linear_bicubic` | 4.32 | 5.57 | **REJECT** |
| D `linear_lanczos` | 4.97 | 6.19 | **REJECT** |
| E `linear_area32_bicubic` | 3.34 | 4.64 | PASS |

Two optimisations were needed to get there, and both belong in the sidecar too:

- the area average is two `reduceat` passes, not a 256-iteration loop (verified equal to the
  per-cell mean for sides 480/337/271/16/17, including sides not divisible by 16);
- sRGB→linear is a **256-entry lookup**, since the source is uint8. That alone took the
  linear-light presets from ~15 ms to ~3 ms.

### 9.2 Decision: sRGB area stays the default

C and D are rejected on time. No remaining challenger clearly wins on a static scene — A and B
are near-indistinguishable at 16×16 — so the plan's rule applies: *if no challenger clearly
wins, keep sRGB area.* `frame_transform.DEFAULT` is frozen to it and a test asserts it.

**The auto-levels presets are deliberately not promoted despite looking best on a contact
sheet.** Plan §7.3 bars per-frame auto-levels in v1 because they pump brightness temporally —
and a still image is precisely the artefact that cannot show pumping. They are retained, named
`BENCHMARK_ONLY_*`, and carry a `violates_v1_preprocessing_policy` flag that a test enforces.
This is the one place where eyeballing the contact sheet would have picked the wrong winner.

### 9.3 What is still outstanding

The plan requires a blind rank across **seven scene classes** plus a motion/flicker class, with
a few seconds of footage each. That needs the owner in front of the camera; it cannot be
synthesised. Until then the default is frozen but the ranking is not done, so W2 is
**harness-complete, decision provisional**.

To capture a scene (repeat per class: desk-distance face, close face, hand/motion, colourful,
high-contrast, low light, fine detail/text):

```powershell
cd C:\temp\openditoo-webcam-probe
.\OpenDitoo.Webcam.Probe.exe snapshot NV12 640 480 60 12 C:\temp\openditoo-scenes\<scene-name>
```

### 9.4 Incidental findings

- The camera was mounted rotated during the first capture, which is why `quarter_turns` exists.
  The owner has since righted it, so the default stays 0 — but a mount-orientation knob is
  clearly load-bearing for a physical webcam and is kept.
- Scene mean luma is now ~152/255 with the room lit, against ~52 in the dark.

## 10. W3 results — freshest-frame pipeline proven, no Ditoo involved

`runtime/windows/OpenDitoo.Webcam.Probe` gained `FrameTransform.cs`, `LatestFrameSlot.cs` and a
`pipeline` mode. It references no Host project, holds no token, and contains no Bluetooth,
socket or endpoint string; a verifier check and a test both enforce that. The transport in this
milestone is a **delay, not a device**.

### 10.1 Cross-language transform parity — PASS

`OpenDitoo.Webcam.Probe.exe transform-selftest tests/frame_transform_cases.json` →
`TRANSFORM_SELFTEST_PASS cases=15 failures=0`, first run.

The C# port reproduces the Python reference bit for bit, including the parts most likely to
drift silently: numpy's half-to-even rounding (every `Math.Round` uses
`MidpointRounding.ToEven`), the per-row/column cell edges for sides not divisible by 16, and the
palette-merge tie-break order. Without this, a preview would stop predicting what the device is
sent and every visual acceptance would become unverifiable.

### 10.2 Exit criteria

| Criterion | Result | |
| --- | ---: | --- |
| p95 transform ≤ 5 ms | 2.15 ms (p50 1.32) | **PASS** |
| ≥18 sender iterations/s at a 54 ms cycle | 18.32/s | **PASS** |
| p95 source age at fake send ≤ 50 ms | 50.94 ms | miss by 0.94 ms |
| queue depths never exceed one | maxRaw 1, maxProcessed 1 | **PASS** |

Invariants observed over a 15 s run: 433 camera frames offered, **0 raw frames replaced before
use** (the processor always kept up), **168 processed frames replaced before use** (the sender
could not, so the newest won and the rest were dropped rather than queued), 264 sends, **1** idle
poll, and no frame ever sent twice.

The age miss is gated on camera frame rate, not on the pipeline: at 28.87 fps a frame waits up
to a full 54 ms sender cycle for a slot. In the earlier well-lit measurement the camera ran at
53 fps, where that wait roughly halves. This should be re-measured with the room lit before it
is treated as a real miss.

### 10.3 Three wrong turns, recorded because each was measured rather than assumed

1. **`Task.Delay` is not a 54 ms delay.** The Windows timer tick is ~15.6 ms, so the simulated
   ACK cycle was really 60.8 ms and failed the rate criterion for reasons that had nothing to do
   with the pipeline. Fixed with `timeBeginPeriod(1)` plus a short spin — a *simulation*
   artifact only; a real stream waits on an actual HTTP response and needs no timer.
2. **I blamed the BGRA conversion for the camera's rate, and was wrong.** Moving the
   BGRA→RGB conversion off the callback thread was still worth it (transform p95 2.84 → 1.22 ms,
   and the transform now reads BGRA in place with no intermediate copy), but a control run with
   *no* conversion measured the same 28.35 fps. Camera rate tracks exposure, as W1 established.
   The misleading comment has been corrected in the source.
3. **The rate accounting undercounted a saturated sender.** Dividing sends by wall-clock
   included camera start-up and the trailing partial cycle, reporting 17.6/s for a sender that
   was in fact running at its cycle rate. Measuring over the sender's own active span gives
   18.32/s. The wall-clock figure is still reported alongside it.


## 11. Correction to §8.4 — how the camera's frame rate actually behaves

§8.4 concluded "the ~20 fps ceiling is the room, not the camera" and offered mean output luma
as the evidence. The mechanism was wrong, and one step of the reasoning was backwards.

Re-measured with the room lit:

| Condition | mean output luma | interarrival | rate |
| --- | ---: | ---: | ---: |
| dark | 52 | 50.0 ms | 20 fps |
| lit (earlier) | 137–144 | 16.7 ms | 60 fps |
| lit, brighter output (now) | 165–179 | 33.3 ms | 30 fps |

Two things follow.

**The rate is quantised to integer multiples of 1/60 s.** 50.0, 33.3 and 16.7 ms are exactly
3/60, 2/60 and 1/60 second. That is the signature of auto-exposure constrained to whole
power-line periods (60 Hz anti-flicker), stepping 60 → 30 → 20 fps as it needs more light. It is
not a continuous response, which is why every measurement lands on a clean submultiple.

**Mean output luma is not a proxy for scene brightness, and using it as one was the error.**
Auto-exposure drives luma *toward its target*, so a longer exposure produces high luma from a
dimmer scene. Output luma of 179 at 1/30 s means less light reaching the sensor than luma 140 at
1/60 s, not more. The original conclusion happened to be right for the dark case and the
evidence offered for it did not support it.

Confirmed not responsible, by measurement rather than argument:

- **not USB bandwidth or format** — MJPG 640×480, NV12 320×240, NV12 640×480 and NV12 1280×720
  all deliver the same 33.3 ms, spanning ~3.7 to ~82.9 MB/s if they ran at 60;
- **not the requested format being ignored** — the probe now reports `negotiatedMode` from
  `source.CurrentFormat` alongside the request, and the device negotiates 60 fps while
  delivering 30;
- **not another process** — no camera consent entry shows in-use and no capture app is running;
- **not our BGRA conversion** — a control run without it measures the same rate.

`ExposureControl.Supported` is false on this camera, so exposure cannot be pinned through WinRT.
DirectShow property pages (via ffmpeg or a DirectShow host) are the remaining route if a fixed
frame rate is ever required.

**None of this blocks the objective.** 28–30 fps is still 2–3x our ~10–13 fps transport ceiling,
so capture stays comfortably ahead of the display path, which is what the plan requires. The one
consequence is for W3's `sourceAgeP95Under50ms` criterion: with a 33 ms camera interval and a
54 ms send cycle, a frame waits most of a cycle for a slot and p95 age lands at ~51–55 ms. That
criterion is only achievable when the camera interval is well under half the send cycle — i.e.
at 60 fps. It is environment-dependent, not a pipeline defect, and the queue-depth and
replacement invariants that actually prove the freshest-frame design all pass regardless.

## 12. W5 results — full dry path, no Ditoo involved

`OpenDitoo.Webcam.Probe.exe dryrun` runs the entire application path against an **in-memory
typed-Host stand-in**: capture → latest raw slot → transform → palette guard → canonical encoder
and hash → session semantics → ACK clock. No Bluetooth, no socket, no token, no Ditoo.

The stand-in is deliberately not a lenient mock. It **re-encodes every frame independently** and
refuses on hash mismatch exactly as the Host does, and enforces the same lifetime, frame and byte
budgets and the same 40 ms streaming floor. A dry run that passed against a permissive fake would
prove nothing; the point is to find refusals here rather than on the device.

### 12.1 Encoder parity — PASS

`encoder-selftest` → `ENCODER_SELFTEST_PASS cases=6 failures=0` against
`tests/ditoo_encoder_cases.json`, covering a 1-colour frame (1 bit/pixel), a 2-colour frame, two
255-colour frames (8 bits/pixel), and a 256-distinct-colour frame that only fits because the
palette guard merges one pixel.

This matters more than it looks: the sidecar computes the `expectedImagePacketSha256` that
`/v1/session/frame` checks, so an encoder that drifts by one byte gets every frame refused with
`IMAGE_ENCODER_HASH_MISMATCH`. Palette order is first-seen in row-major order, not sorted — the
index stream depends on it.

### 12.2 Thresholds, over a 20 s run with the real camera

| Threshold | Result | |
| --- | ---: | --- |
| p95 transform ≤ 5 ms | 3.42 ms (p50 0.99) | **PASS** |
| p95 source age at simulated send ≤ 75 ms | 53.07 ms (p50 25.8) | **PASS** |
| no queue depth > 1 | maxRaw 1, maxReady 1 | **PASS** |
| processing throughput > 100 fps | 729.5 fps | **PASS** |
| no encoder hash mismatch | 0 refusals in 291 frames | **PASS** |
| camera ≥ 58 fps for the 60 fps mode | 29.15 fps | **documented exception, §11** |

291 frames / 873 packets / 299,169 application bytes, clean `operator_stop / stopped_clean`,
**zero refusals of any kind**. Encode cost is negligible next to the transform (p50 0.03 ms
against 0.99 ms). Managed memory *fell* 1.2 MB over the run, so there is no allocation trend.

The replacement counts are the freshest-frame design working end to end: 583 camera frames
offered, **0 raw frames replaced before use**, **291 processed frames replaced before use** — the
sender consumed every second frame and the rest were dropped rather than queued.

### 12.3 The one exception

`cameraFpsAtLeast58` fails for the reason in §11: the camera quantises exposure to whole
power-line periods and is currently delivering 30 fps. The plan allows this — "unless hardware
evidence says otherwise" — and §11 is that evidence. It costs nothing here: 29 fps is still more
than double the ~10–13 fps transport ceiling, source age passed with 22 ms of margin, and the
processing path has ~25x the throughput it needs.

### 12.4 What W5 does not cover

The dry run exercises the fake Host's refusal paths by construction, but **camera disconnect
during a live session** and **a real Host fault** are not yet exercised end to end. Both are
listed in the plan's W5 offline tests. They need fault injection in the sidecar, which is the
first thing to add before W6 freezes a trial manifest.

## 13. W5 fault injection — verified 2026-09-09

Continued from clean HEAD `97c927b`; fresh baseline verifier: 234 tests PASS. Windows bridge
and read-only Host status work with sandbox escalation. Product status reports connected,
no errors, no authority blockers, runtime_revision 2. The installed Host hash was re-read:
`0da3a18b52647a91e4cf2b13349af09dc7c60fec6b3ac13067c1f3f31372decb`, matching Runtime 003.
No product stop, Host rebuild/deploy, experiment claim or Ditoo transmission was performed.

`DryRunSession` now owns the dry-run lifecycle. It validates the first transformed frame and
encoder hash before constructing the fake session (the simulated open/claim boundary).
Camera failure publishes a terminal stop before waiting for any in-flight ACK, then closes
once. Every refusal stops the sender; a failed frame or close remains terminal `unknown`.
The real camera's `MediaCapture.Failed` event and callback/transform exceptions use that path.
Cancellation during a simulated ACK can no longer increment the ACKed-frame count.

Correction to §12: the previous fake returned a nonterminal pacing refusal and the sender
continued after some refusals. The new pacing test proves the terminal behavior; the healthy
control proves the sender was not merely disabled to make the negative tests pass.

Reproduce from Windows (default is camera-free; add `-CameraFaults` for the real camera):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify_webcam_offline.ps1 -CameraFaults
```

The script builds only the webcam probe, copies it into a fresh Windows temporary directory,
and runs all checks there. It leaves that directory for inspection and writes no camera images.

- Build: zero warnings/errors.
- `fault-selftest`: 11 cases PASS (healthy, pre-open disconnect, mid-session disconnect,
  Host frame fault, ambiguous close, invalid first frame, frame/byte/lifetime ceilings,
  pacing refusal, cancelled ACK). Terminal-state negative controls attempt another send and
  cleanup and assert unchanged open/send/close counts.
- `transform-selftest`: 15 cases PASS; `encoder-selftest`: 6 cases PASS.
- Real NV12 640×480@60 capture with in-memory Host, 3 s envelope, 65 ms simulated ACK:

| Injected condition | Opens | Send attempts | Closes | Outcome |
| --- | ---: | ---: | ---: | --- |
| healthy control | 1 | 36 | 1 | stopped_clean |
| camera before open | 0 | 0 | 0 | not_opened |
| camera after first ACK | 1 | 1 | 1 | stopped_clean |
| Host loses second frame result | 1 | 2 | 1 | unknown |
| close loses result | 1 | 1 | 1 | unknown |

These are injected failures, not a physical unplug or actual Host outage. The fake is the only
transport. W2's owner-dependent ranking and §11's camera-rate exception remain unchanged.
The earlier 20 s allocation measurement is not a five-minute soak; that longer plan criterion
has not been demonstrated by these fault tests.

## 14. W6 prerequisite correction — live adapter is missing

The previous handoff implied that fault injection followed by a manifest was enough to reach
the grant boundary. Source inspection disproves that: `stream-run` dereferences
`frame_set.sha256` and never injects a `LiveFrameSource`; `stream-preview` also assumes a frame
set. The probe only runs its delay/in-memory transports. A manifest accepted by
`load_stream_manifest(..., require_authority=False)` is therefore not an executable webcam
trial, and the missing adapter's future code/build cannot yet be hash-frozen.

Before a grant-ready W6: connect the freshest-frame camera producer to the existing typed
session client, verify its camera-preflight-before-claim and terminal fault behavior offline,
then freeze all executable code/build hashes. Keep the probe's no-device boundary, one
controller, named profile and Runtime 003 identity. Do not weaken the sidecar boundary scan
or silently route the hot frame loop through WSL merely to make `stream-run` accept a camera.

The first trial remains bounded to 10 s on the exact Ditoo, with no retry/reconnect/reclaim.
Its concrete pacing and derived budgets must match the implemented adapter. Do not request
a live grant on the strength of the passing W5 fake alone.

### 14.1 Review envelope prepared, not grant-ready

`experiments/DAY1-WEBCAM-N980P-001.json` freezes the current producer sources and Windows
build artifacts, exact unit/firmware, and verified Host DLL. It explicitly declares the missing
adapter, missing adapter hash freeze and unproven five-minute allocation soak as blockers.
It contains no grant, expiry or claim; `transmission_authorized=false` and
`authorization_consumed=false`. This is partial W6 preparation, not a completed execution freeze.

Read-only review: `python3 scripts/check_webcam_trial.py`. It verifies every named producer
file (including build dependencies) exists and matches its hash, checks the repository Host
hash and existing claims, and reports `execution_ready=false`, `grant_ready=false`.
Use this checker for the review envelope: the existing `stream-preview` is frame-set-only.

The planned first trial preserves the external plan's **83 ms session interval**, above the
named profile's permanent **40 ms minimum**, for 10 s. Those are distinct limits, not a Host
profile change. A paced ACK-clock adapter must wait for both the previous ACK and the next
permitted actual-dispatch time. The current pure ACK-clock stream runner does not enforce
that local 83 ms limit, another reason this envelope must not be called executable.

Derived ceilings: `floor(10000 / 83) + 1 = 121` frames, 363 application packets, and
`121 × 1054 = 127534` application bytes (canonical worst-case encoder plus both preambles).
Future grant string, **only after all readiness blockers are resolved and the updated freeze
is reviewed**: `Grant OPENDITOO-WEBCAM-N980P-001`. No grant was requested or received here.

Final review verification: `verify_day1_offline.py` **236 tests PASS**; the W6 checker reports
valid hashes/budgets and all readiness blockers. Product status remains connected with no
errors or authority blockers and zero reconnects/reclaims. No experimental claim was created.


## 15. Interrupted W6 adapter checkpoint — recovered 2026-09-09

This section **supersedes §14's statement that the live adapter is missing**. The uploaded local
Codex transcript and the preserved worktree show that implementation continued after `da77b6f`
until the model token limit ended the session. The work was not a Ditoo experiment: there was no
new grant, no durable experiment claim, no product-controller stop and no device transmission.

### 15.1 What now exists

A Windows-native adapter now connects the already-proven freshest-frame camera producer to the
**existing typed Host session family only**:

- `runtime/windows/OpenDitoo.Webcam.Probe/WebcamFrames.cs` — exact N980P capture + capacity-one
  raw/ready slots + frozen transform;
- `runtime/windows/OpenDitoo.Webcam.Runner/{Program,Trial,TypedSession,OfflineTests}.cs` and the
  runner project — camera lifecycle, fixed typed Host requests, bounded sender and offline fake;
- `host/webcam_trial.py` — WSL-side review/claim coordinator;
- `cli/webcam.py` — one fixed-envelope execution entry point, with no target/rate/raw/retry knobs.

The adapter has no second Bluetooth stack. Its live transport is fixed to
`http://127.0.0.1:8796` and `/v1/status`, `/v1/session/open`, `/v1/session/frame`,
`/v1/session/close`. It keeps exactly one frame in flight, never resends an ambiguous frame,
never reconnects/reclaims, and verifies the Host-confirmed `streaming_ack_clock` profile.

The important authority fix is a **camera-ready-before-claim handshake**. The Windows runner
opens the exact NexiGo, obtains and encodes one fresh 16×16 frame, then emits a fresh nonce. Only
a matching WSL `execute:<nonce>` after a new durable claim may cross into `/v1/session/open`.
Camera missing/stale before that point therefore cannot consume the Ditoo experiment identity.

The interrupted source session recorded a successful Release build of
`OpenDitoo.Webcam.Runner`: **0 warnings, 0 errors**. That is useful build evidence, not a substitute
for the remaining Windows-local verification below.

### 15.2 Pacing correction made immediately before the token cutoff

The earlier W6 draft overloaded `min_frame_interval_ms=83` as both Host floor and desired client
cadence. That leaves essentially no arrival-time margin: a nominal 83 ms client dispatch can
reach the Host slightly early and a pacing refusal is terminal.

The recovered adapter separates the limits correctly:

- Host profile floor: **40 ms** (unchanged `streaming_ack_clock` authority bound);
- client minimum actual-dispatch cadence: **90 ms**;
- ACK gate: previous frame must also have completed;
- lifetime: **10 s**.

The frozen maximums therefore become:

`floor(10000 / 90) + 1 = 112 frames → 336 application packets → 112 × 1054 = 118,048 application bytes`.

These numbers replace §14.1's 83 ms / 121 / 363 / 127,534 draft. They target roughly 11 fps for
the first trial, inside the already-measured realistic 10–13 fps ACK-clock envelope while still
leaving the Host's independent 40 ms bound intact.

### 15.3 What is still unproven — and why W6 is not grant-ready

The current WSL_MCP sandbox re-ran `python3 scripts/verify_day1_offline.py`: **236 tests PASS**,
`device_io=false`. It can parse the recovered Python coordinator and validate the updated review
manifest/hashes. However, this sandbox exposes neither `powershell.exe` nor `/mnt/c`, and its
Host loopback is unavailable. It therefore cannot honestly reproduce Windows-local camera or
runner execution.

The remaining W6 blockers are exactly:

1. rebuild/stage the runner to a local Windows path and run `selftest` plus both transform/encoder
   parity fixtures;
2. re-verify the camera-ready-before-durable-claim handshake without opening a Ditoo session;
3. run the runner's **five-minute camera/allocation soak** against its in-memory typed Host and
   record the bounded-memory/camera result;
4. re-hash the final executing source/build artifacts and re-run `scripts/check_webcam_trial.py`.

`experiments/DAY1-WEBCAM-N980P-001.json` remains deliberately
`transmission_authorized=false`, `authorization_consumed=false`, `execution_ready=false` and
`grant_ready=false`. **Do not request or act on its future grant string yet.** Once the four
checks above pass and the final freeze is reviewed, W6 can close and the project stops at the W7
named-grant boundary.

### 15.4 Milestones after W6

- **W7:** one 10-second exact-unit physical webcam acceptance trial under a fresh named grant;
  judge transport cleanliness, freshness/orientation and owner-visible face/hand recognizability.
- **W8:** one bounded near-ceiling ACK-clock characterization after W7; do not repeat R1–R5 or
  invent a new protocol/rate ladder.
- **W9A:** after W8, add monotonic capture/source identity plus deterministic temporal-marker motion truth; keep transport unchanged.
- **W9B:** film the W9A stimulus and Ditoo together to measure unique visible transitions and actual optical scene→Ditoo latency; never report ACK/transport FPS as panel FPS.
- **W10:** only after experimental acceptance, add operator-friendly start/stop/preview polish; fixed-rate modes use monotonic absolute deadlines, skip missed logical slots without catch-up, and do not consume a transmit interval on duplicate/no-new-frame selection. Decide separately whether webcam merits its own standing product authority. Runtime 003 remains the MCP dashboard authority and is not widened by this work.


## 16. W6 continuation — pre-claim ownership hardening and one-command Windows verifier

A follow-up WSL_MCP session continued from `661446f`. With sandbox networking explicitly
enabled, the existing Host is reachable at `127.0.0.1:8796`; Runtime 003/product status was
healthy and the MCP dashboard owned an active `activity` session. The default no-network sandbox
was the reason earlier Host status probes appeared unavailable.

That observation exposed one useful ordering improvement in the recovered W6 coordinator. The
coordinator already required `openditoo-product.service` to be inactive before a webcam claim,
but the Host's own session-idle check lived in the Windows sender after the one-use WSL claim.
`host/webcam_trial.py` now performs an authenticated **read-only Host status/identity/ownership
precheck before claim consumption**. It requires the exact fixed Host identity/target, the typed
`activity-session` capability, no active activity session and no operation in progress. Against
the currently active dashboard it correctly fails with `HOST_PRECLAIM_CONTROLLER_NOT_IDLE`; no
webcam claim is created. Offline tests pin both the status validator and the ordering.

The repository now also contains `scripts/verify_webcam_w6_windows.ps1`, a single offline-only
Windows verification entry point. It:

1. rebuilds **only** `OpenDitoo.Webcam.Runner` and stages it to `C:\temp\openditoo-webcam-runner`;
2. runs adapter selftest plus transform/encoder parity fixtures;
3. exercises the real camera-ready nonce boundary with temporary synthetic identity
   `OPENDITOO-WEBCAM-N980P-998`, deliberately creating **no durable claim** and never writing
   `execute:<nonce>`, so the runner cannot reach `TypedSession.Live`;
4. runs the five-minute real-camera allocation soak against the in-memory typed Host; and
5. reports `device_io=false`, `host_session_io=false`, `claim_created=false`.

A unit test scans this verifier and forbids `StandardInput.Write`, `cli/webcam.py` and
`SessionClaim`, preserving the negative-control boundary. Current offline suite: **243 tests PASS**.

The remaining limitation is environmental, not inferred away: WSL_MCP's bubblewrap sandbox hides
`/mnt/c`, exposes no `powershell.exe`/Windows `dotnet`, breaks WSL PE interop because its `/proc`
view is isolated, and exposes no `/dev/video*`. Therefore this session cannot execute the Windows
camera verifier itself. **W6 remains not grant-ready until that script passes in a Windows-capable
local WSL session and the final executing build hashes are re-frozen.**


## 17. W6 Windows verification PASS and final grant-ready freeze — 2026-09-09

The operator executed `scripts/verify_webcam_w6_windows.ps1` from Windows PowerShell against the
post-`bb878f4` repository. The complete offline gate passed: Release build **0 warnings / 0 errors**;
adapter selftest PASS; **15/15** transform parity cases; **6/6** encoder parity cases; and the
`OPENDITOO-WEBCAM-N980P-998` camera-ready nonce negative control emitted a valid 32-hex nonce while
creating **no claim**, opening **no Host session**, and performing **no Ditoo I/O**.

The real NexiGo camera then completed the five-minute in-memory-Host soak: **300.1216216 s**,
**8,647 captured frames**, **5,376 freshest-frame replacements**, post-warmup managed-memory growth
**9,416 bytes**, transform mean **1.1741 ms**, p50 **0.9174 ms**, p95 **1.4380 ms**, max
**8.1827 ms**. Final line: `W6_WINDOWS_OFFLINE_PASS ... claim_created=false host_session_io=false
device_io=false`. Durable structured evidence is
`captures/OPENDITOO-WEBCAM-W6-WINDOWS-OFFLINE-RESULT-2026-09-09.json`.

The exact just-built producer/source hashes were re-frozen in
`experiments/DAY1-WEBCAM-N980P-001.json`; the runner csproj disables source-revision injection into
InformationalVersion so unrelated Git commits do not intentionally churn that binary identity. W6
engineering blockers are now empty and `grant_ready=true`; `execution_ready=false` remains correct
because transmission authority has not been granted and the live ownership preflight has not run.

**W7 is the next boundary.** It is one fixed 10-second physical trial at 40 ms Host floor / 90 ms
client dispatch cadence, at most 112 frames / 336 application packets / 118,048 application bytes,
one connection, one frame in flight, no retry/reconnect/reclaim. It must not start until the operator
provides the exact fresh named grant: `Grant OPENDITOO-WEBCAM-N980P-001`.


## 18. W7 attempt 001 consumed before Host open; status-contract correction — 2026-09-09

The operator granted and executed `OPENDITOO-WEBCAM-N980P-001` through the guarded W7 launcher.
The launcher passed the full offline gate, stopped Runtime 003 cleanly, and observed the Host idle.
The camera-ready handshake then created the durable one-use WSL claim. The trial terminated after
**27.6534 ms** with `outcome=not_opened`, `terminalReason=HOST_REQUEST_REFUSED`, **0 frames**, **0
packets**, and **0 bytes**. Cleanup restored Runtime 003, which reconnected under a fresh product
session. Attempt 001 is therefore consumed and must never be replayed.

The decisive diagnostic is that `.openditoo-local/session-ledger.jsonl` contains **no entry** for
`OPENDITOO-WEBCAM-N980P-001`. `TypedSession.Open()` sets `OpenAttempted=true` only after its initial
GET `/v1/status`, so `not_opened` plus no Host ledger entry proves the request never reached
`ActivitySessionHost.Open()` or Bluetooth connect.

Root cause: the established Day1 Host `/v1/status` route returns HTTP 200 with an identity/status
object but intentionally has **no `ok` property**. `TypedSession.Request()` incorrectly required
`result.ok == true` for every endpoint, while the offline `FakeHandler` incorrectly added
`ok=true` to its fake status response. That made all adapter selftests pass while the real Host
status document was rejected as `HOST_REQUEST_REFUSED`.

The correction is deliberately client-only so Runtime 003 / the deployed Host remain unchanged:

- GET `/v1/status` now accepts HTTP success without a POST-style `ok` field, then relies on the
  existing exact target/bind/port/controller checks;
- POST routes still require `ok=true`;
- generic HTTP refusals now retain the status code as `HOST_REQUEST_REFUSED_HTTP_<code>`;
- the fake status response now matches the real Host by omitting `ok`;
- runner mode `host-status-selftest <repository>` exercises the corrected C# parser against the
  **real Host status endpoint only**, validates exact Host identity/target, and reports
  `device_io=false host_session_io=false`.

Fresh identity `OPENDITOO-WEBCAM-N980P-002` is the only allowed W7 rerun candidate. It carries the
same 10-second / 40 ms Host floor / 90 ms client cadence / 112-frame / 336-packet / 118,048-byte
bounds and no retry/reconnect/reclaim. It is initially unauthorized and not grant-ready. Run
`scripts/prepare_webcam_w7_rerun_windows.ps1` first: rebuild/stage the corrected runner, run adapter
plus transform/encoder selftests, run the real-Host read-only status-contract selftest, and freeze
the exact new hashes. Only after that passes may the project request the distinct grant
`Grant OPENDITOO-WEBCAM-N980P-002`.


## 19. W7 rerun 002 preparation PASS — metadata recovered after wrapper-only failure

The operator reran `scripts/prepare_webcam_w7_rerun_windows.ps1` after the compile fix. The corrected Windows runner built with **0 warnings / 0 errors**; adapter selftest, **15/15** transform parity, and **6/6** encoder parity all passed. Most importantly, the staged runner's `host-status-selftest` succeeded against the real Day1 Host and reported `status_has_ok_field=false`, exact target `11:75:58:CE:DE:C7`, `device_io=false`, and `host_session_io=false`. This directly validates the attempt-001 contract correction.

The wrapper then failed only while trying to recover Git HEAD through `bash -lc` positional-parameter quoting. That happened **after** every required build/selftest/real-Host check and before any claim/session/device operation. The exact corrected build remained present under the repo; all frozen producer files matched except the newly rebuilt runner DLL, whose exact SHA-256 was recovered as `64b4582b068900785574c76b2510f6c406cb518d3196f51f0a8241818001792f` and frozen into rerun 002. Structured recovery evidence is `captures/OPENDITOO-WEBCAM-W7-RERUN-PREPARATION-2026-09-09.json`.

The prep wrapper is also corrected for future use: direct `wsl.exe ... git -C` and direct absolute-path Python invocations replace nested Bash quoting, and UTF-8 JSON writes are explicitly BOM-free for Windows PowerShell 5.1. These bookkeeping fixes do not alter producer/runtime behavior.

`OPENDITOO-WEBCAM-N980P-002` is now **grant-ready but unauthorized**, with no claim and no Host/device I/O. Its distinct future grant is `Grant OPENDITOO-WEBCAM-N980P-002`. The guarded W7 launcher is rebound to 002 and uses distinct rerun result paths so consumed attempt-001 evidence cannot be overwritten.


## 20. W7 physical webcam acceptance PASS — 2026-09-09

Fresh identity `OPENDITOO-WEBCAM-N980P-002` executed once after the exact named grant. The guarded launcher stopped Runtime 003, observed the Host idle, completed the camera-ready claim handshake, opened the reviewed `streaming_ack_clock` Host profile, and restored Runtime 003 after terminal close.

Measured result: **108 frames**, **324 application packets**, **110,532 application bytes** over **10,014.4804 ms** (~**10.78 fps**). HTTP/ACK round-trip was mean **34.58 ms**, p50 **27.17 ms**, p95 **57.37 ms**, max **91.18 ms**. Source age at send was mean **35.56 ms**, p50 **36.12 ms**, p95 **50.61 ms**, max **56.85 ms**; source age at ACK was mean **70.35 ms**, p50 **69.22 ms**, p95 **100.49 ms**, max **128.25 ms**. The terminal result was `lifetime_expired` / `stopped_clean` with **no retry, reconnect, or reclaim**.

The Host ledger independently records the exact reviewed open envelope (10 s, 40 ms floor, 112-frame ceiling, 118,048-byte ceiling, `streaming_ack_clock`, zero packet spacing) and the same terminal totals: 108 frames / 324 packets / 110,532 bytes, `ours_last_acked`. The operator visually confirmed that the live webcam feed genuinely worked on the Ditoo. Structured acceptance evidence is `captures/OPENDITOO-WEBCAM-W7-RERUN-002-ACCEPTANCE-2026-09-09.json`.

Post-trial recovery was separately checked after the launcher's immediate snapshot: Runtime 003 had started a fresh product run, reported `status=connected`, and owned a fresh active `activity` Host session with ACKed dashboard frames. W7 is therefore fully closed. Both 001 and 002 are consumed and replay-forbidden.

**Next boundary: W8.** If useful, perform one separately reviewed near-ceiling ACK-clock characterization. Do not create a new rate ladder and do not reuse either W7 grant. After W8, W9A adds source identity + deterministic motion truth, W9B combines unique-frame observation with optical scene-to-display latency, and W10 handles product/operator polish plus the fixed-rate absolute-deadline scheduler contract and separate standing webcam-authority decision.


## 21. W8 implementation checkpoint — 40 ms ACK-gated near-ceiling candidate

W7 changed the W8 pacing conclusion. The earlier external plan proposed an ACK-clock run with a zero client/Host floor, but the deployed `streaming_ack_clock` Host actually retains a permanent **40 ms frame-start backstop**, and W7 measured HTTP/ACK p50 **27.17 ms**. Therefore immediate dispatch on every ACK can arrive before the Host's accepted floor and trigger the same class of terminal 429 pacing refusal already seen during S2. W8 does **not** remove or modify that deployed Host backstop.

Fresh candidate `OPENDITOO-WEBCAM-N980P-003` instead uses the fastest safe shape supported by the current Host: **one frame in flight, prior ACK required, plus an absolute 40 ms client dispatch-start floor measured from the prior dispatch start**. If ACK takes >=40 ms, the newest processed frame goes immediately; if ACK returns earlier, the client waits only the remaining time to 40 ms. Packet spacing remains zero through the already-deployed profile. The 10-second reviewed ceiling is therefore `floor(10000/40)+1 = 251` frames, **753 packets**, and **264,554 application bytes** at the canonical 1,054-byte worst-case frame transaction. No rate ladder, pipelining, retry, reconnect, reclaim, raw send, target change, transform change, or Host deployment is introduced.

The Windows sender now reads its client floor from the manifest so historical W7 remains 90 ms while W8 is 40 ms. A dedicated fake-Host control returns ACKs in ~5 ms and asserts that the W8 sender still never violates the 40 ms Host floor. W8 telemetry is also expanded without retaining frame history: effective FPS, frames/FPS by run quarter, source-age-at-send by quarter, dispatch-interval jitter, HTTP request/ACK time, Host-reported send-to-ACK time, their difference as a localhost/serialization overhead estimate, duplicate source timestamps, camera captured/processed/replaced/taken counts, replacement percentage, transform timing, and raw/processed capacity-one queue-depth maxima.

The new review/check/execute path is separate from W7: `experiments/DAY1-WEBCAM-N980P-003.json`, `scripts/check_webcam_w8.py`, `scripts/prepare_webcam_w8_windows.ps1`, `scripts/run_webcam_w8_once.sh`, and `scripts/run_webcam_w8_windows.ps1`. The prep script is deliberately no-device: build/stage runner, adapter selftest (including the fast-ACK floor control), 15 transform fixtures, 6 encoder fixtures, real read-only Host status identity, then exact hash/evidence freeze. It refuses a pre-authorized or consumed manifest and contains no live CLI/claim/execute path.

Current static/offline state: **249 tests PASS**. Candidate 003 is valid but `grant_ready=false`, with only `WINDOWS_W8_RUNNER_BUILD_NOT_FROZEN` and `WINDOWS_W8_OFFLINE_SELFTEST_NOT_VERIFIED` as engineering blockers; authority is absent and no claim exists. The next permitted action is the Windows no-device prep command. Only after it passes may the project request `Grant OPENDITOO-WEBCAM-N980P-003`.


## 22. W8 attempt 003 pacing refusal; arrival-time margin correction — 2026-09-09

`OPENDITOO-WEBCAM-N980P-003` executed once after its exact named grant. The guarded launcher stopped Runtime 003, verified Host idle, consumed the fresh camera-ready claim, and opened the reviewed 10-second `streaming_ack_clock` session at a 40 ms Host floor and 40 ms client dispatch floor. Two frames ACKed successfully. The third frame POST was refused with `SESSION_PACING_VIOLATION`, so the client correctly terminated `outcome=unknown` with no retry, reconnect, reclaim, or same-identity replay. Machine totals were **2 frames / 6 packets / 2,102 bytes** over **297.4472 ms**. The two accepted HTTP/ACKs were 34.76/38.33 ms-class round trips, with Host-reported frame time 31 ms and mean HTTP-over-Host difference 5.55 ms. The client-side dispatch-interval sample was still just over the requested floor (mean 43.00 ms; one interval approximately 40.07 ms). Capacity-one queue invariants held and duplicate source frames were zero.

The Host ledger independently records the reviewed open envelope and then a terminal `SESSION_PACING_VIOLATION` after 2 frames / 6 packets / 2,102 bytes. Its own terminal cleanup is `stopped_clean`; this does **not** overwrite the client's `unknown` result, because a live frame request failed after session open. Attempt 003 is therefore consumed and replay-forbidden. Runtime 003 was restored and separately observed `status=connected`. Structured failure evidence is `captures/OPENDITOO-WEBCAM-W8-ACKCLOCK-003-FAILURE-2026-09-09.json`.

Root cause: W8-003 paced from a **client dispatch-start clock**, while the Host enforces its floor between **Host frame-start timestamps**. Request serialization/scheduling/localhost delivery occurs between those two points. If the earlier request has a few milliseconds more outbound latency than the next one, a client gap slightly above 40 ms can become a Host arrival/start gap below 40 ms. Matching the client floor exactly to the Host floor therefore provides no jitter margin. This is the same architectural lesson as S2, now observed in the streaming profile at a much smaller absolute scale.

Fresh identity `OPENDITOO-WEBCAM-N980P-004` is the only reviewed replacement. The Host remains unchanged at 40 ms; the client floor becomes **50 ms**, leaving **10 ms arrival-jitter margin** while retaining a **20 fps theoretical scheduling ceiling**, still sufficient to characterize the planned 15–18 fps region. The 10-second hard ceiling is `floor(10000/50)+1 = 201` frames, **603 packets**, and **211,854 application bytes**. No rate ladder, Host redeploy, pipelining, retry, reconnect, reclaim, raw send, transform change, or target change is introduced.

The offline adapter now contains a direct regression pair using an 8 ms alternating simulated request-arrival skew: the historical 40 ms client floor must reproduce `PACING_VIOLATION`, while the corrected 50 ms client floor must remain clean under the same skew and sustain at least 16 fps in the one-second fake-Host control. Candidate 004 is initially unauthorized and blocked only on its Windows rebuild/freeze plus this updated selftest. Run `scripts/prepare_webcam_w8_rerun_windows.ps1`; only after that no-device prep passes may the project request `Grant OPENDITOO-WEBCAM-N980P-004`.


## 23. W8 attempt 004 cross-clock telemetry false abort; fresh 005 — 2026-09-09

`OPENDITOO-WEBCAM-N980P-004` executed once after its exact named grant with the corrected **50 ms client / 40 ms Host** pacing margin. It did **not** reproduce the 003 pacing violation. The client accepted 8 frames before aborting `outcome=unknown` with `HOST_FRAME_ELAPSED_INVALID`; client-visible totals were 8 frames / 24 packets / 8,372 bytes over 714.57 ms, with no retry/reconnect/reclaim, zero duplicate source frames, and both capacity-one queues remaining at depth 1. Source age at send stayed fresh (p95 **51.27 ms**).

The Host ledger is decisive: it records **9 ACKed frames / 27 packets / 9,420 bytes** before the client requested close. Therefore frame 9 reached the Ditoo and ACKed successfully; only the client failed to advance its own counters because it rejected the already-successful response during telemetry validation. The Host then closed `stopped_clean`, while the client/claim correctly remains `unknown` because its own post-open execution path terminated unexpectedly. Attempt 004 is consumed and replay-forbidden. Runtime 003 was restored and observed connected. Structured failure evidence is `captures/OPENDITOO-WEBCAM-W8-RERUN-004-FAILURE-2026-09-09.json`.

Root cause is the W8-only telemetry assertion added after W7: `hostFrameElapsedMs` is measured inside the Host with **`Environment.TickCount64`**, while the client HTTP round-trip is measured in another process with high-resolution **`Stopwatch`**. The client incorrectly required `hostFrameElapsedMs <= clientRoundTrip + 10 ms`. Those values come from independent clock domains/resolutions; Windows tick quantization can make the Host integer elapsed value numerically exceed the client's high-resolution interval even when the Host response is fully valid. This was never a transport, packet, hash, target, ACK, or pacing failure.

The correction is intentionally narrow. Packet hash, frame number, packet totals, byte totals, exact target, session profile, one-frame-in-flight, 50 ms client pacing, and all no-retry/reconnect/reclaim rules remain unchanged. `hostFrameElapsedMs` must still exist, be non-negative, and remain within the manifest's reviewed **5,000 ms per-frame ACK budget**. The client now records a signed `clientMinusHostElapsedMs` residual for observation only; it no longer treats cross-process clock ordering as a fatal invariant. A dedicated fake-Host `coarse_clock` regression returns a valid Host elapsed value deliberately larger than the client-observed request duration and must remain clean.

Fresh identity `OPENDITOO-WEBCAM-N980P-005` preserves the **50 ms client / 40 ms Host** pacing and 10-second ceilings of **201 frames / 603 packets / 211,854 bytes**. It is initially unauthorized and blocked only on Windows rebuild/freeze plus the updated selftest bundle: historical 40 ms arrival-jitter failure reproduction, 50 ms margin PASS, cross-clock telemetry PASS, transform/encoder parity, and real Host read-only status identity. Run `scripts/prepare_webcam_w8_telemetry_rerun_windows.ps1`; only after that no-device prep passes may the project request `Grant OPENDITOO-WEBCAM-N980P-005`.


## 24. Cross-project high-FPS lesson review — roadmap update, no W8-005 transport change

The OpenTivoo 10→30 fps technical note was reviewed against the live OpenDitoo implementation after candidate 005 was staged. Its central portable lesson is to treat **source cadence, scheduler cadence, transport cadence and physical display refresh as separate systems**. The numerical Tivoo results are explicitly **not** portable to Ditoo. OpenDitoo already has its own exact-unit R5 evidence: about **18.46 fps** is the measured ceiling of the current full-colour synchronous one-ACK-per-frame protocol shape. Therefore this review does **not** reopen R1-R5, create a 10/20/30 rate ladder, alter candidate 005, or introduce pipelining.

Most architectural lessons are already present: N980P capture is independent of transform; raw and processed stages use capacity-one latest-frame slots; transformation runs while transport waits; the typed Host remains the single RFCOMM owner; no catch-up/reconnect loop exists; and W8 records source age, replacements, duplicates, queue depth and transport timing. Live webcam preconversion into a prerecorded bundle is specifically **not** adopted: the asynchronous transform worker already moves the ~1–2 ms resize/quantization work out of the sender's wait path while preserving genuine live capture.

Three roadmap changes are adopted:

1. **W9A — source identity + motion truth.** Add a monotonically increasing capture/source sequence ID at successful frame acquisition and propagate it through raw→transformed→selected/sent telemetry. Build a deterministic monitor stimulus with large temporal markers/frame counters that survive 16×16 transformation. This makes source duplicates, replacement/skipping and selected-frame uniqueness directly measurable instead of inferred from timestamps or nominal FPS. This work starts only after W8-005 is closed; it must not churn the frozen 005 producer.
2. **W9B — combined unique-frame + optical latency.** Film the W9A source stimulus and physical Ditoo together for at least 30 decodable transitions, correlating source identity, sender selection and transport evidence with visible transitions where possible. Report true scene→visible latency separately from ACK/source-age metrics and never infer panel refresh from transport rate.
3. **W10 fixed-rate scheduler contract.** Product fixed-rate modes use monotonic absolute deadlines (`next_due += interval`) so processing/ACK overhead is not blindly added to every nominal period. Missed deadlines advance/skip logical slots with **no catch-up burst**; duplicate/no-new-frame selection does not update the actual transmit/send-floor clock as though a frame was sent. ACK-clock mode remains governed by the separately accepted W8 contract.

A possible effort to exceed the synchronous one-ACK-per-frame ceiling is now explicitly **post-v1 and conditional**. It may be researched only if W9B demonstrates visible benefit from additional unique update cadence and the owner wants to pursue it. Potential protocol-shape changes (pipelining/batching, firmware buffering, alternate/delta semantics) require a new reviewed plan and authority; OpenTivoo's 30 fps and 54/56 fps figures are not evidence that Ditoo can or should use those rates.

## 25. W8-005 Windows preparation PASS — grant-ready, no device I/O — 2026-09-09

`scripts/prepare_webcam_w8_telemetry_rerun_windows.ps1` ran once from git head
`cce5b189b753df226f18cbcc2077c800063173ae` and reported
`W8_TELEMETRY_RERUN_PREP_PASS`. It is no-device preparation: `claim_created=false`,
`host_session_io=false`, `device_io=false`, and Runtime 003 was never stopped.

Verified coverage:

- runner rebuilt Release and staged to `C:\temp\openditoo-webcam-runner`;
- `ADAPTER_SELFTEST_PASS failures=0 device_io=false camera_io=false` across ten fault cases;
- `ADAPTER_W8_40MS_ARRIVAL_JITTER_REPRO_PASS frames=1 outcome=unknown reason=PACING_VIOLATION` —
  the historical 003 failure still reproduces under the 8 ms simulated arrival skew;
- `ADAPTER_W8_50MS_ARRIVAL_JITTER_PASS frames=17 client_interval_ms=50 outcome=stopped_clean` —
  the corrected client floor stays clean under the same skew;
- `ADAPTER_HOST_ELAPSED_CROSS_CLOCK_PASS frames=11 outcome=stopped_clean` — the coarse-clock
  control that would have aborted 004 now completes;
- `TRANSFORM_SELFTEST_PASS cases=15`, `ENCODER_SELFTEST_PASS cases=6`;
- real read-only Host status identity `target=11:75:58:CE:DE:C7`, `device_io=false`,
  `host_session_io=false`;
- exact producer/runner hash refreeze into the manifest.

Post-prep offline validation: `DAY1_OFFLINE_PASS tests=256`;
`check_webcam_w8_telemetry_rerun.py` reports `ok=true`, `manifest_valid=true`,
`grant_ready=true`, `execution_ready=false`, `claim_created=false`, `device_io=false`,
with blockers `TRANSMISSION_AUTHORITY_MISSING`, `AUTHORITY_GRANT_UNATTRIBUTED`,
`AUTHORITY_EXPIRY_MISSING`, `LIVE_PREFLIGHT_NOT_PERFORMED`.

Frozen identities: manifest `032dcc810385e14553468eb8fc8b75d9d2bd708459f26251b3d5d7b6ef2138fe`,
preparation evidence `55a717ca6d2939659a5eed7f0888dea9fb0c909a21166124fa2a372f0fc83e6d`
(`captures/OPENDITOO-WEBCAM-W8-TELEMETRY-005-PREPARATION-2026-09-09.json`).

No `OPENDITOO-WEBCAM-N980P-005` claim exists and the Host ledger contains no 005 entry;
its only recent activity is normal Runtime 003 product sessions. The candidate is
**grant-ready and unauthorized**. The single remaining gate is the exact operator grant
`Grant OPENDITOO-WEBCAM-N980P-005`, after which only
`scripts/run_webcam_w8_telemetry_rerun_windows.ps1` may execute, exactly once.

Note on file shape: the PowerShell writer emits CRLF, so `git diff --check` flags carriage
returns as trailing whitespace on this checkpoint. That matches the committed 004
preparation checkpoint (`d76b266`) and must not be normalized here — rewriting the bytes
would invalidate the recorded `evidence_sha256` and `manifest_sha256`.

## 26. W8-005 live characterization PASS — W8 transport result closed — 2026-09-09

`OPENDITOO-WEBCAM-N980P-005` executed exactly once after the exact named grant
`Grant OPENDITOO-WEBCAM-N980P-005` and is now **consumed and PASS**. This is the first W8
attempt to complete its full lifetime.

**Terminal state.** `outcome=stopped_clean`, `terminalReason=lifetime_expired`, over
10,009.43 ms. No retry, no reconnect, no reclaim, zero pacing violations, no
encoder/hash mismatch, no ambiguity.

**Transport totals — client and Host agree exactly.** Client counted 163 frames / 489
packets / 170,737 bytes. The Host ledger independently records `framesSent=163`,
`packetsSent=489`, `txBytesSent=170737`, `reason=lifetime_expired`,
`outcome=stopped_clean`, `displayState=ours_last_acked`. The 004 client/Host divergence
(8 vs 9) is gone: the telemetry correction was the whole defect. All totals sit well inside
the 201 / 603 / 211,854 budgets.

**Sustained rate.** 16.285 fps effective. Per-quarter fps was **15.6 / 16.4 / 16.4 / 16.8**
(39 / 41 / 41 / 42 frames) — stable and slightly improving, with no decay. This clears the
manifest's ≥15.5 fps acceptance target and sits sensibly below Ditoo's own measured R5
ceiling of ~18.46 fps for this synchronous one-ACK-per-frame shape.

**Timing.** ACK round-trip p50 42.31 ms / p95 69.58 ms / max 107.21 ms. Host frame elapsed
p50 47 ms / p95 63 ms / max 109 ms. Dispatch intervals p50 60.47 ms / p95 69.72 ms / max
107.49 ms — every interval above the 50 ms client floor, so the ACK clock, not the floor,
paced this run. Transform cost stayed negligible: p50 0.995 ms, p95 3.66 ms, max 7.18 ms.

**Freshness.** Source age at send p50 36.99 ms / p95 51.86 ms / max 57.78 ms, comfortably
under the 80 ms p95 target. By quarter the p95 was 52.13 / 50.70 / 51.33 / 53.28 ms — flat,
with no ageing trend. Source age at ACK was p50 80.87 ms / p95 107.22 ms.

**Cross-clock residual.** `clientMinusHostElapsedMs` p50 1.14 ms, mean 1.02 ms, p95 11.57 ms,
max 16.91 ms. It is recorded as a **signed observational residual only** and was never
ordered as an invariant. Two honest limits: the retained percentiles do not expose the
negative tail, so this run does not itself demonstrate the 004 coarse-clock case occurring
live — the offline `ADAPTER_HOST_ELAPSED_CROSS_CLOCK_PASS` control is what covers it — and
this residual must not be labelled literal HTTP overhead.

**Camera and queues.** 333 captured, 333 processed, 168 replaced (50.45 % latest-frame-wins
replacement), 164 taken, 0 raw replaced, **0 duplicate source frames**. Both capacity-one
slots stayed at depth 1. Replacement here is scheduler freshness behavior, not loss.

**One-controller rule held.** `W8T_PRODUCT_PRE_STATE=active` → `W8T_PRODUCT_STOP_PASS` →
`W8T_HOST_IDLE_PASS` → one bounded run → `W8T_RESTORE_PRODUCT_SERVICE_ACTIVE` →
`W8T_RESTORE_PRODUCT_CONNECTED_PASS`. Runtime 003 came back `status=connected`,
`last_error=null`, fresh `run_nonce=8d6f0892`, session `...000001`, first frame ACKed.
OpenTivoo and port 8779 were untouched.

Evidence: `captures/OPENDITOO-WEBCAM-W8-TELEMETRY-005-LIVE-RESULT-2026-09-09.json` and
`...-LIVE-RAW-2026-09-09.log`, both hash-pinned in the manifest's
`w8_telemetry_rerun_result`. Claim nonce `2eda653e90b644a28d8ee9d6697d2c36`, state
`finished` / `stopped_clean`.

**Transport FPS is not physical panel FPS.** 16.285 fps is ACK-completed transport cadence.
Visible unique-frame cadence and true scene-to-visible latency remain unmeasured and are
exactly what W9A/W9B exist to establish. Do not reopen >18.46 fps protocol work on the
strength of this result.

Attempt 005 is consumed and must never be replayed. W8's transport result is closed;
owner visual observation is recorded separately.
