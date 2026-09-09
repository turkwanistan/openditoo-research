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

## 4. Two gates that remain closed

Everything above is offline. Two things have **not** happened and each needs its own explicit
operator decision:

1. **Deploying the new Host binary.** It replaces the DLL the live MCP dashboard runs on and
   invalidates the standing `OPENDITOO-PRODUCT-RUNTIME-002` policy hash, so it requires a
   reviewed **Runtime 003** policy naming the new build, plus a brief dashboard outage during
   cutover. Uninstall/rollback is `bin/Release/net8.0` plus the existing Runtime 002 policy,
   both untouched.
2. **Any live streaming transmission**, which needs a new reviewed manifest and a grant naming
   its experiment id, per `AGENTS.md`. No blanket pre-authorization is valid for this.

## 5. Where the plan's milestones now stand

| Milestone | State |
| --- | --- |
| W0 freeze baseline / contracts | done — `notes/OPENDITOO-STREAM-PRODUCER-CONTRACT-2026-09-09.md` |
| W4 Host streaming pacing profile, offline | **done** — implemented, built, self-tested, 204 tests |
| W1 N980P enumeration + camera benchmark | next, and needs no Ditoo authority |
| W2 16×16 visual shootout | after W1 |
| W3 bounded freshest-frame pipeline | after W2 |
| W5 end-to-end dry run, no Ditoo | after W3; needs the Host deployed to be meaningful |
| W6/W7 first physical webcam trial | gated on §4 |
