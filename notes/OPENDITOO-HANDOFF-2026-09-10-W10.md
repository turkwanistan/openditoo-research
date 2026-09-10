# OpenDitoo handoff — W10 webcam productization CLOSED — 2026-09-10

Read this first. Repository state outranks this note. Detail and every run: `notes/OPENDITOO-W10-PLAN-2026-09-10.md`.

## State

- `main` clean, offline suite **296 PASS**, nothing pushed.
- **Dashboard:** Runtime **005** live (Host `f7bd60d4…`), `connected`, `last_error=null`.
  Rollbacks: `.openditoo-local/rollback-runtime-004/` (Host `4a735bab…` + 004 policy),
  `rollback-runtime-003/` (Host `0da3a18b…` + 003 policy).
- **On-demand webcam:** policy `OPENDITOO-WEBCAM-PRODUCT-004` granted (local mode-0600 only). Desktop
  shortcut **OpenDitoo Webcam** → `scripts/webcam_on_demand.sh`: policy check before touching anything,
  stop dashboard, idle + 8 s settle, one Studio session (≤30 min), always restore the dashboard.
  Close the window / Stop / a Ditoo button press all end it. Logs: `.openditoo-local/webcam-product-log/`.
- Studio (`runtime/windows/OpenDitoo.Webcam.Studio`, installed at `%LOCALAPPDATA%\OpenDitoo\WebcamStudio`):
  camera/mode display, zoom/pan/mirror/rotate, exact 16x16 preview, live Look (5 W2 presets) and
  Colours (255/64/32/16/8) pickers, absolute-deadline scheduler, duplicate/unchanged suppression with
  heartbeat, Host-confirmed stock-yield labelling. Preview/dryrun: `scripts/webcam_studio_windows.ps1`.

## What was proven on the device (all Host ledgers agree with the client)

| Run | Result |
| --- | --- |
| W10-001 / W10-002 | 500 frames @ 16.46 fps; live zoom/pan + Stop; owner visual PASS |
| webcam-product-001 `8f36a6d3` | 3 clean 500-frame rollovers, 4th reopen `IMAGE_RX_RECV_TIMEOUT` → one connection per launch |
| webcam-product-002 `e6e80228` | one connection, 5,786 frames / 5 min 52 s, ended by owner button press (stock yield) |
| webcam-product-003 `3c5398de` | looks switched live; owner keeps `srgb_area` default, normalized = sharp option (**W2 closed**); ended after 3,631 frames by `SESSION_PACING_VIOLATION` → root-caused to the Host's `TickCount64` floor (~46.9 ms effective), fixed in Runtime 005 |

16.4–16.5 fps is **ACKed transport, not panel refresh** (W9B deferred; still unmeasured). The pacing
fix in Runtime 005 has **not yet had a long device session**: the first launch of webcam 004 is its
evidence; a long clean run closes it.

## Traps paid for this session (also in the W10 note)

1. The 007 freeze covers every Runner/Probe webcam file — the Studio links them read-only.
2. SourceLink stamps the git commit into DLLs; Studio and Host csprojs now disable it. The frozen
   Runner does not — do not rebuild it before a 007 revival.
3. `dotnet publish`/`build` writes the repo `bin/Release` Host DLL that live policies hash-check. Build
   candidates with `-p:OutDir=<elsewhere>`; only the cutover may touch `bin/Release`.
4. Editing Studio sources on `main` invalidates the granted webcam policy (shortcut refuses until a
   new revision is granted). Develop Studio changes on a worktree branch.
5. The offline suite needs the main checkout's git-ignored local state (Host `bin/`, claims); in a
   worktree, symlink them for the run. `host/btsnoop.py` was hidden by `*btsnoop*`; now tracked.
6. The Host runs as a console exe from an Interactive task: a 09:34 outage exited `0xC000013A`
   (console close/Ctrl+C). Recovered by `Start-ScheduledTask`. Owner has not confirmed closing a
   window; a windowless launch is the candidate fix (task/refresh-script change, no policy hash change).

## Open, in rough value order

1. Long webcam session on Runtime 005 (evidence for the pacing fix) — happens with normal use.
2. Host console-window outage: confirm cause with the owner; windowless launch if confirmed.
3. Pagination (owner's next product idea) — would replace the shortcut's suspend/restore.
4. Older items unchanged: reboot/logon autostart observation, `product-status connecting` defect,
   genuine source outage never tested end to end. W9B stays deferred; >18.46 fps stays closed
   (precise pacing could reach only ~19–20 fps under the 50 ms client floor; owner declined).

## Addendum — Host console window confirmed as the outage cause (2026-09-10 ~10:30)

Second outage: the Host (restarted by the 10:03 cutover) exited `0xC000013A` at ~10:17; the owner's
shortcut then correctly refused (no Host) at 10:29/10:30. Restarting the task showed the mechanism
directly: a task-started Host is hosted in a **visible Windows Terminal window titled
`…\OpenDitoo.Day1.Host.exe`**; closing it kills the Host. Fix prepared: launch through
`conhost.exe --headless` (installer + refresh script updated; `runtime/windows/set_openditoo_day1_host_headless.ps1`
switches the existing task and restarts it; no binary change, so no policy hash moves). Applying it
needs an **elevated** PowerShell (the task was registered with admin rights; `Set-ScheduledTask` →
Access denied from the normal session). Until applied: do not close that terminal window.

**Headless applied (owner ran it elevated, 11:04 local):** task action is now `conhost.exe --headless …`,
Host PID under conhost, **0 Host windows**, dashboard `connected`. Console-close outages cannot recur.

**Launch `525d0122` (15:04:30Z) — no ACK on the first frame, second young-link case.** The headless
restart made the dashboard reconnect at 15:04:12; the owner's launch stopped that 6 s-old, 1-frame
connection at 15:04:18 and the webcam open at 15:04:30 (after the 8 s settle) got
`IMAGE_RX_RECV_TIMEOUT; NO_RETRY`, 0 frames; launch ended fail-closed, dashboard restored. Same shape as
W9B-006 (1-frame, seconds-old predecessor). Every clean launch followed a dashboard link up for minutes.
Mitigation (launcher only, not policy-bound): wait until the dashboard's current connection is ≥ 30 s
old before suspending it. Confidence in the young-link mechanism: moderate — two matching cases, still
not demonstrated; the webcam-product-001 session-4 reopen failure had a 30 s-old predecessor instead.

**Launch `365520cc` (15:07:55Z) — 3,513 frames, then `SESSION_PACING_VIOLATION` again, on the Runtime 005
Host.** The Host floor was now precise (hostFrameMs p50 36, no 15.6 ms steps), so the TickCount64 fix was
real but incomplete. Remaining cause: the Studio's 50 ms gap is measured from its dispatch stamp, taken
before encode/serialize/HTTP, while the Host's 40 ms is measured from its own frame start. A client stall
in between (dispatch gaps reached 116 ms) delays frame N's Host start while N+1 stays on schedule.
Fix (Studio only, **webcam policy 005**): the next send also waits ≥ 45 ms after
`receivedAt − hostFrameElapsedMs`, a safe upper bound on the Host's start now that both share the
machine's high-resolution clock. Selftest reproduces the refusal under the old rule and stays clean
under the new one (3/3 runs). Normal cadence unaffected (typical Host start is ~1 ms after dispatch).
Policy 005 prepared against the deployed Host; awaiting `Grant OPENDITOO-WEBCAM-PRODUCT-005`.
