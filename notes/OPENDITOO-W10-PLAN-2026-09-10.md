# W10 webcam productization — plan against the actual code — 2026-09-10

Repository state outranks this note. W9B stays deferred; nothing here depends on it.

## Hard facts from the code that shape W10

1. **The 007 freeze covers every webcam source file.** `experiments/DAY1-WEBCAM-N980P-007.json`
   hash-binds all of `OpenDitoo.Webcam.Runner/*` (sources *and* `bin/`), plus the shared Probe
   files `WebcamFrames.cs`, `LatestFrameSlot.cs`, `FrameTransform.cs`, `DitooEncoder.cs`, and
   `host/webcam_trial.py`, `cli/webcam.py`. Editing any of them silently makes 007 non-grant-ready.
   So W10 is a **new project** (`runtime/windows/OpenDitoo.Webcam.Studio`) that links those files
   read-only and adds new files only. The one real duplication is camera acquisition
   (`StudioCamera` vs `WebcamFrames`): `WebcamFrames` hard-codes `FrameTransform.Default` inside
   its processor thread, and ROI/zoom needs a live-adjustable preset.
2. **The Host caps one session at 500 frames / 900 s** (`ActivitySessionHost.MaxFrames`,
   `MaxLifetimeSeconds`; every experiment id is one-use in the Host ledger). At ~16 fps a session
   ends by budget after ~31 s. A continuous, minutes-long webcam therefore needs several sessions,
   i.e. several ids — which is exactly the standing-authority shape Runtime 003 has for the
   dashboard (fresh bounded session ids created automatically inside a granted policy). That is
   the owner's separate decision. Until then, a W10 run is one bounded session under one fresh
   manifest and one exact grant.
3. **Worker liveness is `/v1/session/heartbeat`, not frames** (`WorkerSilenceGraceMs = 30_000`).
   Because W10 refuses to transmit unchanged frames, a static scene is legitimately silent; the
   sender heartbeats instead of resending. The heartbeat is part of the existing typed session
   family — no new route.
4. The frozen W7–W9 `Sender` paces "since last dispatch". W10 replaces that, in the new project
   only, with the settled design.

## Scheduler (settled — implemented, not re-derived)

- Logical slots are `start + k * interval`. The earliest permitted send is
  `max(next_due, last_sent + 50 ms)`; the 50 ms is the proven W8-005 client margin over the 40 ms
  Host floor, and it is the Host-floor clock.
- A send at time `t` serves the newest slot `<= t`; every slot passed over is counted as
  `skippedSlots` and `next_due` jumps past `t`. One frame in flight, so there is never a burst.
- Only a real transmission advances either clock. No new source frame, the same `SourceId`
  again, or byte-identical 16x16 content is dropped and counted (`duplicateSelections`,
  `unchangedFrames`), never sent to hit a rate.
- Modes: `max` (50 ms grid, the W8-005 shape), `10fps` (100 ms), `5fps` (200 ms).

## Phases

| Phase | Content | Authority |
| --- | --- | --- |
| W10A | Studio app: camera/mode display, ROI/zoom/offset/mirror/rotate, source preview with ROI box, exact 16x16 matrix preview (the 768 bytes that would be sent, plus packet SHA), framing save/load, camera disconnect + reconnect in preview; deadline scheduler and sender with robust stop/disconnect, all tested offline against the in-memory Host | none needed: no Host session, no Ditoo I/O |
| W10B | One bounded live Studio session under a fresh reviewed manifest (`OPENDITOO-WEBCAM-W10-001`), WSL coordinator with the same camera-ready-before-claim handshake, product supervisor stopped/restored around it | fresh manifest + exact named grant |
| W10C | Standing webcam authority (policy-shaped, multi-session) | owner decision; not built |

## Operator workflow (target)

1. `scripts/webcam_studio_windows.ps1` (stages to `C:\temp`, opens the preview window; camera
   only, the Ditoo is untouched).
2. Frame the shot with the sliders; the right pane is the exact matrix the Ditoo would get.
3. Save framing (writes `.openditoo-local/webcam-framing.json`).
4. Live: only with a granted manifest; the same window streams, Stop / window close / Ctrl+C
   ends the session cleanly, camera unplug ends it cleanly, a Host fault ends it `unknown` with
   no retry.
