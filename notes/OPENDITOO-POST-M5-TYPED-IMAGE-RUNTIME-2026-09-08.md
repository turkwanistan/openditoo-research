# OpenDitoo post-M5 typed image runtime — 2026-09-08

## Proven baseline

Day-1 M5 is PASS on the exact purchased Ditoo Plus (`11:75:58:CE:DE:C7`, installed version v42012). Attempt 2 sent the frozen three-packet stock-derived image sequence over Windows RFCOMM channel 1, received wrapped `0x44` ACK payload `0x12`, closed cleanly, and visibly rendered the planned diagnostic marks. Evidence is `captures/OPENDITOO-DAY1-M5-ATTEMPT2-PASS-2026-09-08.json`. M5 authority is consumed and the one-shot runner is disarmed.

## Productization implemented after M5

The next runtime is intentionally narrower than a generic Bluetooth API:

`exact local 16x16 PNG -> WSL CLI -> authenticated loopback Host -> fixed Ditoo -> one static image transaction`

### PNG decoder

`host/png16.py` is dependency-free and accepts only:

- exactly 16x16;
- 8-bit non-interlaced PNG;
- grayscale, RGB, indexed, grayscale+alpha or RGBA;
- valid PNG chunk CRCs;
- alpha composited deterministically onto black.

The resulting RGB888 image must contain at most 255 distinct colors, matching the observed one-byte palette-count field.

### Deterministic encoder

`host/ditoo_pixel_coloring.py` now includes `palette_and_indices_from_rgb888()` and `encode_rgb888_static_image()`. The product encoder uses deterministic first-seen row-major palette ordering. This may produce different packet bytes from the frozen M5 diagnostic's manually chosen palette order while rendering identical pixels; M5 evidence remains immutable.

### CLI

`cli/openditoo.py` adds:

- `image-prepare --png <path> [--output-dir <dir>]` — offline only; validates PNG and reports RGB/image-packet hashes.
- `image-show --png <path>` — one explicit live static-image action through the authenticated Host.

There is no target argument, raw packet argument, generic command ID, generic Bluetooth operation or automatic retry.

### Windows Host

The Host on `127.0.0.1:8796` adds only `POST /v1/image/show`. Request data is typed: exactly 768 RGB888 bytes encoded as hex plus the CLI's expected image-packet SHA-256. The Host independently rebuilds the stock-derived `0x44` packet and rejects a hash mismatch **before Bluetooth I/O**. It is permanently bound in source to the exact Ditoo MAC and RFCOMM channel 1.

Each successful live call performs:

1. exact paired-target precheck;
2. one RFCOMM channel-1 connection;
3. stock-observed preamble A once;
4. stock-observed preamble B once;
5. one deterministic `0x44` static image packet;
6. one wrapped `0x44` ACK read;
7. local socket close.

No automatic retry or reconnect exists. Concurrent image calls are rejected by a single-operation gate.

### Deployment ownership

`runtime/windows/refresh_openditoo_day1_host.ps1` refreshes only the existing `OpenDitoo Day1 Host` task/runtime after verifying its owned executable path. It observes/preserves `OpenTivoo Product Runtime`, never stops OpenTivoo, never kills arbitrary processes, stages a rollback copy, and fails closed if port 8796 does not release after stopping only its own task.

The original installer has also been updated so a future clean install expects the typed-image Host rather than the historical status-only Host.

## Offline fixture

`examples/openditoo-smile-16.png` is a four-color asymmetric test image intended to validate PNG -> Host -> Ditoo orientation independently of the frozen M5 diagnostic.

Frozen local preparation result:

- PNG SHA-256: `def0d19fbac3d8ebae47b674009cbda392996a634ce9774a9d303ac13770f382`
- decoded RGB SHA-256: `fbed71941831927c926c15f897f3335de45d9becc53c28793c9fefa146f96067`
- palette colors: 4
- deterministic product `0x44` packet bytes: 94
- deterministic product packet SHA-256: `e4fe7ff42632495cdcb5eceb9131a720eb77fccad2183dc98dcf0e881b2e37ea`

## Current validation state

Offline Python/unit boundary checks are PASS. Windows `.NET` compilation and live Host refresh are still operator-side because WSL_MCP has no Windows shell/SDK bridge.

Exact next validation sequence:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\runtime\windows\refresh_openditoo_day1_host.ps1
```

Dry run must compile/publish and end with `REFRESH_DRY_RUN_PASS`, with no task/runtime/device changes.

Then:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\runtime\windows\refresh_openditoo_day1_host.ps1 -Apply
```

Expected gate: `REFRESH_STATUS=PASS_TYPED_IMAGE`.

With Android Bluetooth disconnected, validate the fixed Host from WSL:

```powershell
wsl.exe -d Ubuntu -- bash -lc "cd /home/wan/Projects/openditoo-research && python3 cli/openditoo.py status && python3 cli/openditoo.py image-show --png examples/openditoo-smile-16.png"
```

If `image-show` passes, record the returned ACK/hash and operator visual observation, then freeze the typed runtime as the post-M5 baseline. If it fails before Bluetooth due to encoder hash mismatch, reconcile C#/Python encoding offline; do not bypass the hash gate. If it fails after a send with an ambiguous transport result, do not auto-retry.
