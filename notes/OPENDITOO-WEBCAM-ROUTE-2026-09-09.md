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
