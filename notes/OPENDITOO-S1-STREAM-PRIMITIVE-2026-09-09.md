# S1 — general bounded 16x16 frame streaming primitive — 2026-09-09

## What already existed (verified in this session, not inherited)

The streaming transport was already built and physically accepted; only the *source* side
was missing.

- `/v1/session/open|frame|heartbeat|close` on the typed Windows Host takes an arbitrary
  768-byte RGB888 frame per request, encodes it with the stock-derived Pixel Coloring
  encoder, and enforces lifetime, the 150 ms frame-start floor, 10 ms intra-frame packet
  spacing, and frame/byte budgets in its own watchdog. It consumes the experiment id in an
  on-disk ledger before the socket exists.
- `activity_session.run_session()` is already a generic ACK-gated frame loop driving an
  injected `render(now_ms)` callable, with change-only scheduling, a durable `O_EXCL`
  claim, and fail-closed terminal handling.
- `/v1/image/sequence` remains the frozen up-front A→B sequence route (≤1024 frames, whole
  clip in one request). It is unchanged and is not the streaming path.

**No Windows Host change was needed, and none was made.** Verified in-session:
repository `bin/Release/net8.0/OpenDitoo.Day1.Host.dll` and the deployed
`%LOCALAPPDATA%\OpenDitoo\Day1Host` DLL are byte-identical at
`fb750078e9f5d8e763e57e2f58d8a79b1faff1d886d2d04946274a29dd9af70f`.

Environment verified in-session: `powershell.exe` reachable from WSL, Host live on
`127.0.0.1:8796` (`.NET`, `rawSendEnabled=false`, `targetBound=true`), all three activity
sources reachable.

## What was missing, and was built

`host/frame_stream.py` — the frame-source half only. It opens nothing and reaches nothing.

- `frames_from_source()` — one ordered frame set from a `.rgb888` blob (N × 768 bytes) or a
  directory of 16×16 PNGs, sorted by filename.
- `quantize_to_palette_limit()` — the real gap for arbitrary content: the stock encoder
  carries one palette of at most **255** colours per frame, and a photographic 16×16 frame
  routinely has 256. Channel low bits are dropped one step at a time until the frame fits.
  Deterministic from the source bytes; runs **offline in prepare, never at send time**.
- `build_frame_set()` — encodes every frame once up front, so nothing is discovered
  mid-stream, and reports the worst-case application bytes per frame (image packet + both
  stock preambles).
- `FrameSetRenderer` — time-indexed playback. Indexing on the clock, not on ACKs, is
  load-bearing: an ACK-gated cursor deadlocks on two identical consecutive frames, because
  the shared scheduler holds them as unchanged and no ACK ever arrives to advance it. A
  slow transport therefore drops frames instead of stretching the clip.
- `load_stream_manifest()` — a reviewed `kind=frame_stream` manifest, validated
  fail-closed, returning the **shared** `SessionManifest` record. It freezes the frame-set
  hash and count, and the code that the stream path actually executes
  (`frame_stream.py`, `ditoo_pixel_coloring.py`, `activity_session.py`) — deliberately not
  the MCP renderer/collector, which a stream never runs. Budgets are **derived**: the clip
  or the lifetime, whichever ends first, fixes the frame count; packets and bytes follow.

CLI: `stream-prepare` (offline freeze + derived budgets), `stream-preview` (offline
authority review plus a full fake-transport replay on a fake clock), `stream-run` (live,
manifest-only, no operating arguments).

`host/activity_session.py` is hash-frozen by the live Runtime 002 product policy. It was
imported, never modified. MCP Dashboard v1 is untouched.

## Cadence ceiling of this primitive

`run_session` dispatches at `max(manifest floor, MCP_CLIENT_FRAME_INTERVAL_MS)` = **200 ms
(5 fps)**, inside hash-frozen code. A stream manifest asking for less is refused
(`STREAM_PLAYBACK_INTERVAL_INVALID`) rather than silently rounded up. So this first
primitive streams at ≤5 fps, well under the accepted 7.63 fps sustained / 18.46 fps
no-sleep ceilings. Going faster is a separate objective that would fork or revise the
shared runner, and needs its own evidence boundary.

## Offline state

`python3 scripts/verify_day1_offline.py` → **PASS, 187 tests** (was 170). A new
`verify_stream_boundary()` check refuses an armed stream manifest in the repository, any
second transport path inside `frame_stream.py`, and free-form operating arguments on the
stream CLI.

## First live trial — prepared, NOT authorized

`experiments/DAY1-S1-STREAM-SWEEP-001.json`, experiment id `OPENDITOO-S1-STREAM-001`.

- Content: `examples/stream-demo/sweep-bar.rgb888`, 48 distinct generated frames
  (`scripts/make_stream_demo_frames.py`) — a 1-pixel vertical bar crossing left→right once
  in red, once in green, once in blue, on black. 2 colours per frame.
- Frame set sha256 `6abd7a835fb243f705207384a0262910e21019222c5e409c8272acd3178fe20e`.
- Envelope: one connection, 12 s lifetime, 200 ms cadence, **48 frames / 144 packets /
  3408 application bytes**, one ACK per frame, 150 ms Host floor, no retry / reconnect /
  reclaim / replay / pipelining / raw send / target override / persistent write.
- Offline replay result: exactly 48 frames, 144 packets, 3408 bytes,
  `lifetime_expired / stopped_clean`, 192 unchanged holds. Sends match the stated budget
  exactly.
- Expected physical observation: three left-to-right single-column sweeps — red, green,
  blue — over ~9.6 s, then the final blue column held until the lifetime ends.

**Operational precondition:** the persistent MCP product supervisor currently owns the
device (`activitySession.active=true` at hydration). One controller at a time is real, so
the supervisor must be stopped for the trial and restarted immediately afterwards.

`authority.transmission_authorized` is `false` and no claim exists. Nothing has been
transmitted. The trial needs the explicit operator grant naming
`OPENDITOO-S1-STREAM-001`.

## What this trial will and will not prove

Proves: the general precomputed-frame streaming path on the exact unit through the accepted
transport. Proves nothing about video preprocessing, live/procedural generation, camera or
screen sources, audio synchronization, pipelining, or any rate above the tested cadence.
Those remain out of scope until the primitive is physically accepted.
