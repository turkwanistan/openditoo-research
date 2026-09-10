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

## W10C on-demand webcam — built, prepared, UNAUTHORIZED — 2026-09-10

Owner request: "open a desktop app … it starts up for me to mess around, when I close/stop it goes
back to the MCP dash". That needs back-to-back sessions (500-frame Host cap), so it is the standing
policy shape: `product/OPENDITOO-WEBCAM-PRODUCT-001.json` (committed, unauthorized) →
`.openditoo-local/webcam-product-policy.json` (mode 0600) only after `Grant OPENDITOO-WEBCAM-PRODUCT-001`.

- **Launch:** desktop shortcut `OpenDitoo Webcam` → `wsl.exe … scripts/webcam_on_demand.sh`:
  policy check (refuses before touching anything), stop Runtime 003, idle + 8 s settle, Studio
  `live-policy` from `%LOCALAPPDATA%\OpenDitoo\WebcamStudio`, always restore the dashboard.
- **Sessions:** `OPENDITOO-WEBCAM-LIVE-<run nonce>-<seq>`, fresh per session, durable claim against
  the Studio's per-session nonce; next session only after clean `budget_exhausted`/`lifetime_expired`;
  anything else ends the launch, no retry. 30 min / 60 sessions per launch.
- **Revoke:** `python3 host/webcam_studio.py policy-revoke`. Remove shortcut: delete the .lnk.
- **Evidence so far:** real-camera dry run rolls 5 sessions cleanly and a mid-run close ends as
  `operator_stop`; protocol tests against a fake Studio (rollover, launch cap, Studio dying → that
  claim `unknown`). Negative controls: launcher and Studio both refuse without the grant; dashboard untouched.
- **Not yet exercised on the device:** session rollover (re-open right after a clean close). Expect a
  brief freeze at each ~30 s boundary while the next session opens. The first granted launch is its evidence.
- Changing Studio sources invalidates the policy by hash: `python3 scripts/prepare_webcam_w10.py product`
  re-freezes the template; a granted local policy must then be revoked and re-granted.

**Granted 2026-09-10:** owner gave `Grant OPENDITOO-WEBCAM-PRODUCT-001`; local policy materialized
(mode 0600, `policy-check` PASS, template in git unchanged/unauthorized). Launch logs land in
`.openditoo-local/webcam-product-log/`. First device launch (rollover evidence) pending.

### First granted launch — run 8f36a6d3, 2026-09-10 12:51Z

Rollover worked on the device: sessions 001–003 each 500 frames / 1500 packets, `budget_exhausted` /
`stopped_clean`, ~16.4 fps ACKed transport, reopened 1.07–1.08 s after the previous close. Session
004 opened 1.04 s after 003 closed; the Host connected but got **no ACK for the first frame within
5000 ms** → Host `transport_fault` / `IMAGE_RX_RECV_TIMEOUT; NO_RETRY`, 0/0/0, `unknown_nothing_sent`;
client `SESSION_FRAME_FAIL_CLOSED;close_unconfirmed` → `unknown`. The launch ended as designed (no
retry) and Runtime 003 was restored `connected`, `last_error=null`. Owner: "it rolled over … but
eventually it shutdown".

Same signature as W9B-006 (a connection opened soon after another closed, device silent). This is a
second occurrence consistent with the fast-reopen theory, but it is **not demonstrated**: 002 and 003
reopened at the same ~1 s gap and worked, so the failure is intermittent (1 of 3 fast reopens here).
Log: `.openditoo-local/webcam-product-log/20260910T125111Z.json` (local); Host ledger entries for
`OPENDITOO-WEBCAM-LIVE-8f36a6d3-00{1..4}`.

## Option A — one connection per launch — 2026-09-10

Owner chose to remove rollovers instead of pacing them ("do A").

- **Host `4a735bab…`**: `streaming_ack_clock` has its own Host-owned ceiling, 1800 s /
  45000 frames (the lifetime at the 40 ms floor); `activity` keeps 900 s / 500. The per-session ACK
  list is bounded to the latest 500. The build is commit-independent (SourceLink off).
- **Runtime 004 cutover PASS** (`Grant OPENDITOO-PRODUCT-RUNTIME-004`): `scripts/cutover_runtime_004.sh`
  saved rollback (`.openditoo-local/rollback-runtime-003/`: DLL `0da3a18b…` + 003 local policy), stopped
  the dashboard, `refresh -Apply` → `PASS_TYPED_IMAGE`, OpenTivoo preserved, installed = repo DLL
  `4a735bab…`, local policy re-bound, `product-check` PASS, dashboard `connected`.
- Webcam 001 local policy revoked (`.openditoo-local/revoked/`). **Webcam 002** prepared against the
  deployed Host: one session of ≤30 min / 36001 frames per launch; unauthorized until
  `Grant OPENDITOO-WEBCAM-PRODUCT-002`.
- Trap paid: `dotnet publish -o <elsewhere>` still rebuilds the repo `bin/Release` DLL that the live
  product policy hash-checks. The supervisor only checks at start, so restoring the DLL at once was
  enough; build candidates somewhere that cannot touch `bin/Release`, or only at cutover.
- Not yet exercised on the device: a streaming session beyond 500 frames on the new Host.

**Webcam 002 granted 2026-09-10** (`Grant OPENDITOO-WEBCAM-PRODUCT-002`): local policy materialized
(mode 0600, `policy-check` PASS); committed template stays unauthorized. First launch pending.

### First webcam 002 launch — run e6e80228, 2026-09-10 13:05Z — PASS

One connection, 13:05:44 → 13:11:36 (5 min 52 s): **5,786 frames / 17,358 packets / 5,987,969 bytes**,
16.42 fps ACKed transport, frame budget 36001 of the new Host ceiling. Ended when the owner pressed
Ditoo buttons: Host `canvas_invalidated` / `stopped_yielded_to_stock` (`outer=0x04 inner=0x46`), the
designed stock yield; no retry; dashboard restored `connected`, `last_error=null`. Owner: "it ran great.
i clicked some buttons on the ditoo and that killed it but that should be expected."

This is the first streaming session beyond 500 frames on Host `4a735bab…`: the separate streaming
ceiling works on the device and no reopen occurred.

Known reporting defect (not fixed; would drift the frozen Studio hash and cost a re-prep + re-grant):
the Studio treats `SESSION_CANVAS_INVALIDATED` as a generic Host refusal and then fails to close a
session the Host already ended, so the client/launch log says `unknown` /
`SESSION_CANVAS_INVALIDATED;close_unconfirmed`. The Host ledger (authoritative) says
`stopped_yielded_to_stock`. Fix with the next Studio revision: map that code to a clean yield.

## W10D look pickers (branch `w10d-look-pickers`, preview only) — 2026-09-10

Owner: skip chasing FPS unless the gain is big (precise pacing would reach at most ~19–20 fps under the
50 ms client floor; more needs floor changes = the closed >18.46 line). Try colour instead.

- Studio preview gains **Look** (the five C#-parity W2 presets: `srgb_area`, `linear_area`,
  `linear_area_contrast108`, and the two `BENCHMARK_ONLY_…normalized` references) and **Colours**
  (255 / 64 / 32 / 16 / 8, deterministic median cut after the transform). Status line shows the
  actual palette and wire bytes per frame. Selftest: 16 colours → 194 B vs 1039 B full.
- Real camera: `linear_area` @ 16 colours = 209 B/frame. Framing file gains `Preset`/`Colours`; the
  installed policy-002 Studio ignores unknown fields, so live launches stay `srgb_area`/255 until a
  new Studio revision is prepared and the webcam policy re-granted (batch with the stock-yield label fix).
- Kept off `main` on purpose: editing Studio sources in the main checkout drifts the granted
  policy's hashes and would disable the working desktop shortcut.
- The median cut is Studio-only. No Python mirror is needed: the Studio preview renders the very bytes the
  live sender transmits, so there is no offline-preview/device split to keep in parity.

### Webcam policy 003 — looks switchable live, stock yield labelled correctly — 2026-09-10

Owner: "i dont know which is my favorite without seeing it live on ditoo". The Studio window is the
same in preview and live, so the Look/Colours pickers work mid-session. Also fixed: a Ditoo button
press is recorded as `canvas_invalidated` / `stopped_yielded_to_stock` only when the Host's own
session record for that exact id says so (otherwise `unknown`); covers both a refused frame and a
yield noticed by the Host's idle observer during a quiet scene. Selftests: confirmed yield, and an
unconfirmed one (record names another id) stays `unknown`. Envelope unchanged from 002.

### Host outage 09:34 local (13:34Z) — recovered

The Host process exited at ~13:34:01Z with `0xC000013A` (`STATUS_CONTROL_C_EXIT`: console Ctrl+C /
close event), 30.5 min after the Runtime 004 cutover restarted it at 13:03:32Z. Not a timeout (task
`ExecutionTimeLimit` is 72 h) and not a crash. The task runs the console-subsystem Host exe with an
Interactive logon, so the cutover restart gave it a console window on the owner's desktop; closing
that window produces exactly this code. Unconfirmed; owner asked. The dashboard supervisor exited once
(URLError), systemd restarted it, and it waited in `waiting_for_host_or_device` (25 reconnect tries).
Recovery: `Start-ScheduledTask 'OpenDitoo Day1 Host'` (same deployed `4a735bab…` build, no new
authority) → Host up, dashboard `connected`, `last_error=null`.

Candidate hardening (not done): a windowless Host launch. The policies bind only the Host DLL, so a
task-action change (or a WinExe apphost) would not move any policy hash, but `refresh_openditoo_day1_host.ps1`
asserts the task action equals the exe and would need the same change.

Also fixed: `prepare_webcam_w10.py product` named its evidence file after 002 and overwrote it when
preparing 003; the name now follows the policy id and the 002 record was restored from git.

**Webcam 003 granted 2026-09-10** (`Grant OPENDITOO-WEBCAM-PRODUCT-003`): local policy materialized (mode 0600,
`policy-check` PASS); 002 local was revoked at the merge. First 003 launch (live look switching) pending.

### First webcam 003 launch — run 3c5398de, 2026-09-10 13:49Z — looks PASS, pacing refusal found

Owner: "it looked great, default is maybe best but the first benchmark had really sharp colors, nice
options to have." **W2 is closed by owner ranking on the device**: `srgb_area` stays the default;
`BENCHMARK_ONLY_linear_area_normalized` noted as the sharp-colour alternative (framing at end: that
preset, zoom 0.2, 255 colours). The provisional status of `srgb_area` is resolved.

The launch did not end by operator choice: after **3,631 frames (13:49:41 → 13:53:21)** the Host refused
a frame with `SESSION_PACING_VIOLATION` and closed `stopped_clean`; client/launch `unknown`; no retry;
dashboard restored `connected`.

**Root cause (measured, not guessed):** the Host checks its 40 ms floor with `Environment.TickCount64`,
whose resolution here is ~15.625 ms — its own `hostFrameElapsedMs` values are quantized (W10-001 p50
32, p95 63 = 2 and 4 ticks). A difference of two quantized readings is < 40 only when it is ≤ 31.25,
i.e. whenever the true gap is under ~46.9 ms. The effective Host floor is therefore ~46.9 ms, so the
"10 ms" client margin (50 ms dispatch gap) is really ~3 ms of arrival-jitter tolerance. Short runs
never hit it; one stall in 3,631 frames did. Same family as W8-003 (margin) and W8-004 (coarse Host
clock), now with the combination identified.
