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
3. Save framing (writes `%LOCALAPPDATA%\OpenDitoo\webcam-framing.json`).
4. Live: only with a granted manifest; the same window streams, Stop / window close / Ctrl+C
   ends the session cleanly, camera unplug ends it cleanly, a Host fault ends it `unknown` with
   no retry.

## Status — 2026-09-10 (end of session)

**W10A: done offline.** `runtime/windows/OpenDitoo.Webcam.Studio` builds clean; `selftest` is 17/17
PASS (5 clock + 12 sender cases against the frozen in-memory Host), repeated 3x. Real-camera checks,
all with zero Host/Ditoo I/O:

- `preview`: camera name/mode/measured delivered fps (20–21 fps in room light, exposure-limited as
  in route §11), ROI box, exact matrix + packet SHA, saved framing reloads (zoom 0.5 → 240x240 at
  (320,72)), Pan X is screen-true under mirror, clean exit.
- `dryrun 30`: real camera + real window + W10 sender into the in-memory Host; the window was
  closed mid-session → `operator_stop` / `stopped_clean`, 79 frames, 0 duplicate / 0 out-of-order.
- Two defects found and fixed on the way: source age sampled before the take (false
  `camera_stale`), and a `MediaCapture` created on the STA UI thread (`RPC_E_WRONG_THREAD` on exit;
  the camera now lives in the MTA only).

**W10B: `OPENDITOO-WEBCAM-W10-001` prepared, grant-ready, unauthorized.** `scripts/prepare_webcam_w10.py`
built and staged to `C:\temp\openditoo-webcam-studio-w10`, ran selftest + transform (15) + encoder
(6) parity from the staged copy, checked Host identity read-only, froze all producer hashes.
Evidence: `captures/OPENDITOO-WEBCAM-W10-001-PREPARATION-2026-09-10.json`. Negative controls: both
`host/webcam_studio.py run` (`TRANSMISSION_AUTHORITY_MISSING`) and the staged Studio `live`
(`NAMED_GRANT_REQUIRED`) refuse before any claim or camera; no W10 claim exists. The 007 freeze is
intact (checker `grant_ready`, and a test now pins every 007 source hash). Offline suite 283 PASS.

Envelope: `max` mode (50 ms slots, 50 ms client floor, 40 ms Host floor), lifetime 60 s, 500 frames /
1500 packets / 527,000 bytes (Host cap), 8 s handover settle, heartbeat declared, framing
operator-adjustable (pixels only). A busy scene ends on budget at roughly 30 s; both terminals are clean.

Not yet exercised anywhere: the stdin claim handshake inside the Studio (a copy of the proven
Runner pattern), a physical camera unplug, and anything on the Ditoo.

### Operator workflow

```powershell
# Windows PowerShell — frame the shot; the Ditoo is untouched
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\wan\Projects\openditoo-research\scripts\webcam_studio_windows.ps1
# optional: same window streaming into the in-memory Host
... webcam_studio_windows.ps1 -Mode dryrun
```

Press **Save framing** (writes `%LOCALAPPDATA%\OpenDitoo\webcam-framing.json`; a live session starts
from it). Live, only after `Grant OPENDITOO-WEBCAM-W10-001`, from WSL: `bash scripts/run_webcam_w10_once.sh`
(stops Runtime 003, waits for an idle Host + 8 s, runs once, restores and verifies the dashboard). The
Studio window opens; adjust framing live; **Stop** or closing the window ends the session cleanly.

Changing any Studio source or the linked files after preparation invalidates W10-001 by hash — re-run
`python3 scripts/prepare_webcam_w10.py` (it refuses an authorized or claimed manifest). Rebuilding
*unchanged* sources is safe: the Studio csproj disables SourceLink/source-control queries, so the DLL
no longer changes per git commit (verified: `571ea1f2…` before and after commit `f647ca4`). Commit
`f647ca4` deliberately holds W10-001 in draft; `825db61` is the prepared state.

### Open decision (owner): W10C standing webcam authority

A continuous webcam longer than one session (500 frames ≈ 30 s busy at the W8 rate) needs fresh
session ids issued automatically, i.e. a Runtime-003-shaped *webcam* policy with its own review and
grant. Runtime 003 must not widen to cover it. Not built; nothing here assumes it.

## W10B closed PASS — 2026-09-10

| Attempt | Result | Terminal | Frames / packets / bytes | ACKed transport | Owner |
| --- | --- | --- | --- | --- | --- |
| W10-001 | PASS, consumed | `budget_exhausted` / `stopped_clean`, 30.38 s | 500 / 1500 / 501,200 | 16.458 fps, ACK p50/p95 35.7/68.5 ms | "worked clearly, looked great, not much latency, high FPS"; Stop and sliders not tried |
| W10-002 | PASS, consumed | `operator_stop` / `stopped_clean`, 17.53 s | 290 / 870 / 296,864 | 16.546 fps, ACK p50/p95 40.2/68.9 ms | "zoom pan and stop all worked as expected" (framing 1 → 0.34, pan 0.4/−0.05) |

Both: Host ledger identical to the client, 0 duplicate / 0 out-of-order selections, no
retry/reconnect/reclaim, 8 s handover settle then clean open, Runtime 003 restored `connected`.
The first W10-001 launch stopped at the offline gate (my readiness test still expected an
unauthorized manifest) before any claim or I/O; it did not spend the identity. W10-002 added only
"live window comes to the front". Transport FPS is not panel FPS; visible cadence stays unmeasured.

**Every further live webcam run still needs a fresh manifest + exact grant** (`prepare_webcam_w10.py NNN`,
then a `run_webcam_w10_NNN_once.sh`), until the owner decides W10C.
