# OpenDitoo handoff — streaming + webcam phase — 2026-09-09

The live repository is authoritative over this note. Re-verify rather than inherit.

This recovery started from committed baseline `da77b6f`; the interrupted W6 adapter work was
recovered from the local Codex session and preserved as the next coherent checkpoint.
`python3 scripts/verify_day1_offline.py` passes **244 tests** with `device_io=false`. The source
session recorded a successful Windows Release build of `OpenDitoo.Webcam.Runner` with zero
warnings/errors. This WSL_MCP sandbox does **not** expose `powershell.exe`, `/mnt/c`, Windows
`dotnet`, or `/dev/video*`; direct PE launch also fails under its isolated `/proc`, so it cannot
honestly execute the Windows-local adapter/camera checks. With sandbox networking explicitly on,
the existing typed Host **is** reachable at `127.0.0.1:8796`; Runtime 003 is healthy and the MCP
dashboard currently owns an active session. No webcam grant, experiment claim, or Ditoo
transmission was created by the interrupted/recovery work.

## 0. Read in this order

1. this note;
2. `notes/OPENDITOO-WEBCAM-ROUTE-2026-09-09.md` — the adopted webcam route, all W-milestone
   results, and every measured correction;
3. `AGENTS.md` — the authority contract; then `START_HERE.md`;
4. `OPENDITOO-N980P-REALTIME-WEBCAM-IMPLEMENTATION-PLAN.md` — the external plan being followed,
   with amendments recorded in §3 of the route note.

Then run the capability checks in your own session:

```sh
python3 scripts/verify_day1_offline.py
command -v powershell.exe
python3 cli/openditoo.py status
python3 cli/openditoo.py product-status --policy .openditoo-local/product-runtime-policy.json
```

## 1. The one hard boundary

**Live device transmission requires a NEW reviewed manifest and an explicit operator grant
naming that manifest's experiment id.** No general approval carries it — not "yolo mode", not
"you have my approval", not possession of deploy rights or a working Host. This rule is in
`AGENTS.md` and it is the reason the streaming work below stops where it does.

Consumed and never re-armable: activations 001–009, R1–R5, `OPENDITOO-S1-STREAM-001`,
`OPENDITOO-S2-STREAM-RATE-001`. Claims are in `.openditoo-local/session-claims/`.

## 2. What is accepted and live

**MCP Dashboard v1** — unchanged, running, and the owner's daily display. Do not reopen it.

**Runtime 003** — the standing product policy now trusts Host build
`0da3a18b52647a91e4cf2b13349af09dc7c60fec6b3ac13067c1f3f31372decb`, which adds named session
profiles. It differs from Runtime 002 *only* in the trusted Host hash; every dashboard operating
number is unchanged. The committed template `product/OPENDITOO-PRODUCT-RUNTIME-003.json` is
deliberately unauthorized; the authorized copy is the git-ignored mode-0600
`.openditoo-local/product-runtime-policy.json`.

Rollback point: `.openditoo-local/rollback-runtime-002/` holds the previous DLL (`fb750078...`)
and the previous local policy.

Runtimes 001 and 002 remain committed as records and are deliberately **no longer hash-valid**.
Tests assert that re-validating them fails. Do not "fix" this.

**S1 general frame streaming** — accepted, transport and operator visual PASS. Precomputed
16×16 frame sets stream through the existing typed session transaction.

**Host session profiles** — `activity` (150 ms floor, 10 ms spacing; what an absent profile
means, so the dashboard is untouched) and `streaming_ack_clock` (40 ms floor, 0 ms spacing).
A caller picks a profile by NAME; the Host owns the constants, confirms which it applied, and
refuses an unknown name. **The streaming profile has never been exercised live.**

## 3. Measured facts — do not re-derive

- **Transport:** R5 = 18.46 fps ceiling of the synchronous ACK-per-frame shape, 53 ms median /
  111 ms max ACK at 1048 application bytes per frame. R4 = 7.63 fps sustained. Do not repeat.
- **Our client overhead:** 0.24 ms CPU + 2.17 ms WSL→Host loopback ≈ 2.5 ms/frame, about 4% of
  the budget. The client was never the constraint.
- **S2 measured dispatch→ACK through HTTP:** median 66 ms, p95 93 ms.
- **A pacing violation is terminal**, so a clock-paced client must pace against p95, not mean.
  `CLIENT_JITTER_MARGIN_MS = 50` is enforced by the validator. At the 150 ms activity floor that
  makes 200 ms the safe cadence — about 5 fps.
- **Realistic ACK-clocked target: 10–13 fps**, not the 17.5 the mean implied.
- **Palette:** a 16×16 frame is 256 pixels against a 255 cap, so exactly one merge is ever
  needed. The guard repaints one pixel. Colour depth is a non-issue; downscaling and exposure are
  where 16×16 fidelity is decided.
- **Camera:** NexiGo `VID_0C45&PID_2690`. YUY2 maxes at 30 fps (5 fps at 1080p) — the plan's
  640×480@60 YUY2 does not exist. **NV12@60 exists at every resolution and is the selected mode.**
  Frame rate is exposure-quantised to whole power-line periods (60/30/20 fps = 1/60, 2/60, 3/60 s)
  and is currently 30. Not bandwidth, not format, not our code — see route note §11.
- **Mean output luma is NOT a brightness proxy.** Auto-exposure drives luma toward its target, so
  high luma at a long exposure means *less* light. An earlier conclusion in §8.4 used it
  backwards and is corrected in §11.

## 4. Environment traps that cost real time

- **The camera sidecar cannot run from `\\wsl.localhost`.** `MediaCapture.InitializeAsync` fails
  with `COMException 0x80070490` for every init strategy; the identical binary from `C:\temp`
  works. Deploy to a local Windows path, as the Ditoo Host already does.
- **Never rebuild `runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0` casually.** The live
  product policy hash-checks that exact path, so an in-place rebuild stops the dashboard starting
  with `PRODUCT_HOST_HASH_MISMATCH`. Build elsewhere (`bin/Streaming/net8.0`) or accept that you
  must cut a new product policy. `refresh_openditoo_day1_host.ps1 -Apply` does a proper staged
  deploy with automatic rollback.
- **`Task.Delay` has ~15.6 ms granularity on Windows.** A "54 ms" simulated ACK is really ~61 ms.
  Only matters for simulation; real streaming waits on an HTTP response.
- ffmpeg is installed at
  `C:\Users\Wanstation\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe`
  (not on PATH from WSL). DirectShow exposes **no NV12**, which is why the WinRT/MediaFoundation
  backend was chosen.

## 5. Webcam milestone state

| Milestone | State |
| --- | --- |
| W0 contracts | done — `notes/OPENDITOO-STREAM-PRODUCER-CONTRACT-2026-09-09.md` |
| W1 enumeration + benchmark | done — NV12 640×480@60 selected |
| W2 transform shootout | **harness done, default frozen, ranking outstanding** |
| W3 freshest-frame pipeline | done — 3/4 exit criteria, 4th gated on camera rate |
| W4 Host streaming profile | done, built, **deployed** |
| W5 dry run + fault injection | **done** — healthy path + terminal fault boundaries verified offline |
| W6 freeze trial manifest | **PASS / grant-ready** — exact W6-passing Windows build frozen; adapter/parity tests, nonce negative control, and 300.12 s real-camera soak passed |
| W7 first physical trial | **PASS / consumed** — attempt 002 streamed 108 frames / 324 packets / 110,532 bytes in 10.0145 s (~10.78 fps), clean lifetime expiry, no retry/reconnect/reclaim; operator visually confirmed the webcam feed worked; Runtime 003 restored and verified connected |
| W8 near-ceiling ACK-clock trial | after W7 acceptance; one bounded identity, no new rate ladder |
| W9 optical latency | after W8 if useful; camera and Ditoo filmed together, separate from ACK latency |
| W10 product polish/authority | only after experimental acceptance; decide whether webcam gets separate standing product authority |

Sidecar: `runtime/windows/OpenDitoo.Webcam.Probe` with modes `enumerate`, `benchmark`,
`snapshot`, `pipeline`, `dryrun`, `transform-selftest`, `encoder-selftest`. It references no Host
project, holds no token, and contains no Bluetooth/socket/endpoint code; a verifier check and
tests enforce that (they strip comments and scan code).

Cross-language fixtures — both must keep passing, or offline previews stop predicting what the
device receives:

- `tests/frame_transform_cases.json` → `transform-selftest` (15 cases)
- `tests/ditoo_encoder_cases.json` → `encoder-selftest` (6 cases)

## 6. Next objective, in order

1. **W7 is closed PASS.** Preserve both consumed identities: 001 is the zero-I/O status-contract failure; 002 is the successful physical acceptance trial and must not be replayed.
2. W7 attempt 002 evidence: 108 frames / 324 packets / 110,532 bytes in 10.0145 s (~10.78 fps), ACK p50 27.17 ms / p95 57.37 ms, source age at send p50 36.12 ms / p95 50.61 ms, source age at ACK p50 69.22 ms / p95 100.49 ms, `lifetime_expired` / `stopped_clean`, no retry/reconnect/reclaim. Owner-visible acceptance PASS.
3. Runtime 003 cleanup is independently verified: a fresh product runtime session connected and the Host again owns an active `activity` session with ACKed dashboard frames.
4. **Next: W8**, one separately reviewed near-ceiling ACK-clock characterization if it still adds value. Do not infer or reuse W7 authority. W9 optical latency remains optional; W10 is product polish/separate webcam-authority decision.

## 7. Working style that earned its keep

Every conclusion in the route note that turned out wrong was caught by measuring rather than
arguing: the BGRA-conversion theory, the luma-as-brightness theory, the `Task.Delay` cycle, and
the saturated-sender accounting. Three of those looked plausible and were false. Prefer a control
run over a confident explanation, and record the correction rather than quietly editing history.
