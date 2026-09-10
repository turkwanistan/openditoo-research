# OpenDitoo W6 webcam adapter checkpoint — 2026-09-09

This checkpoint exists because the local Codex implementation session hit its token limit after
the W6 Windows adapter compiled but before verification/soak/documentation closure. The live repo
and `notes/OPENDITOO-WEBCAM-ROUTE-2026-09-09.md` remain authoritative.

## Recovered state

- Baseline commits already landed: `581c72e` (W5 fault boundaries), `da77b6f` (blocked W6 review envelope).
- Recovered adapter: `OpenDitoo.Webcam.Runner` + `WebcamFrames.cs` + WSL coordinator/CLI.
- Uploaded source session recorded a successful runner Release build: 0 warnings, 0 errors.
- Correct first-trial pacing: Host floor 40 ms, client actual-dispatch cadence 90 ms, ACK-gated.
- Correct 10-second ceilings: 112 frames, 336 application packets, 118,048 application bytes.
- No webcam grant, claim, or Ditoo transmission occurred.

## Finish W6 offline from a Windows-capable local WSL session

The WinRT camera binary must execute from a local Windows path, never `\wsl.localhost`.
The preferred path is now one command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify_webcam_w6_windows.ps1
```

That script rebuilds first, copies the Release output to `C:\temp\openditoo-webcam-runner`,
then runs only these **offline** runner modes before touching authority:

```text
OpenDitoo.Webcam.Runner.exe selftest
OpenDitoo.Webcam.Runner.exe transform-selftest <Windows path to tests/frame_transform_cases.json>
OpenDitoo.Webcam.Runner.exe encoder-selftest <Windows path to tests/ditoo_encoder_cases.json>
OpenDitoo.Webcam.Runner.exe soak
```

`soak` is five minutes, uses the real camera but an in-memory typed Host, and performs no Ditoo
I/O. The wrapper also exercises the `camera_ready` nonce negative control with a temporary
synthetic identity, creates no claim, and never sends `execute:<nonce>`, so `/v1/session/open` is
unreachable in that check. The WSL coordinator separately verifies exact Host identity and idle
controller ownership before any real one-use claim. After the wrapper passes, re-freeze hashes and run:

```text
python3 scripts/verify_day1_offline.py
python3 scripts/check_webcam_trial.py
```

Only after every blocker is removed should W6 be marked `grant_ready`. Stop there and obtain the
fresh exact named grant before W7. Do not use `cli/webcam.py run` during W6 verification.

## Post-W6 roadmap

W7 = first 10-second physical webcam acceptance. W8 = one near-ceiling ACK-clock measurement.
The later roadmap now splits W9 into W9A source identity/motion truth and W9B combined unique-frame + optical latency; W10 adds product polish, fixed-rate absolute-deadline scheduling, and a separate decision on standing webcam authority. W2's seven-scene owner ranking remains optional/owner-dependent and is not a W6 safety blocker.


## Closure

W6 closed PASS on 2026-09-09 from the operator's Windows PowerShell run of the one-command verifier.
Evidence: `captures/OPENDITOO-WEBCAM-W6-WINDOWS-OFFLINE-RESULT-2026-09-09.json`. The manifest is now
`grant_ready=true`, has no engineering blockers, and remains `execution_ready=false` /
`transmission_authorized=false`. Next action is W7 only after the fresh exact named grant
`Grant OPENDITOO-WEBCAM-N980P-001`.
