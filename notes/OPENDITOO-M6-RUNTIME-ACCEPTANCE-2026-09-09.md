# OpenDitoo M6 — static runtime acceptance and diagnostics — 2026-09-09

Milestone M6 of `OPENDITOO-IMPLEMENTATION-PLAN-2026-09-09.md`. No device I/O was
performed in this session. `image-show` was not invoked.

## M6.1 Installation reconciliation

The earlier post-M5 handoff said Windows compilation and Host refresh were
"operator-side because WSL_MCP has no Windows shell/SDK bridge". That is **no longer
true for a local Claude Code session in WSL**: `/proc/sys/fs/binfmt_misc/WSLInterop`
is enabled and `powershell.exe`, `cmd.exe` and `dotnet.exe`
(`C:\Program Files\dotnet\dotnet.exe`) are reachable, including building the project
over `\\wsl.localhost\Ubuntu\...`. Windows build/deploy is therefore in-session work,
not an operator gate. Bluetooth transmission remains an operator gate for separate
authority reasons, not tooling reasons.

Read-only probe before any change (2026-09-09):

| Evidence class | Observation |
| --- | --- |
| Source implemented | typed static-image Host in `runtime/windows/OpenDitoo.Day1.Host` |
| Build validated | `dotnet publish` Release PASS (dry run, no task/runtime change) |
| Installed | `%LOCALAPPDATA%\OpenDitoo\Day1Host`, task `OpenDitoo Day1 Host` = Running |
| Installed identity | pre-change `OpenDitoo.Day1.Host.dll` SHA-256 `ce8b2bdb693ba334349ff3cc5db6af53223a71806370befd30814609044571b4` — **byte-identical** to the repository's `bin/Release/net8.0` build |
| Host reachable | `openditoo status` PASS over loopback from WSL |
| Physical PNG acceptance | **not recorded** — still an operator gate |

So the deployed build already matched source before this session; the post-M5 note's
"may still be the older status-only build" text was stale. No refresh was performed to
replay installation — the refresh below exists only to deploy the M6.2 diagnostics.

Incidental observation: the installed directory also contains a `web.config`
(2026-09-09 02:50 UTC) that the publish output does not produce. It is inert for the
Kestrel self-host and was left untouched.

`OpenTivoo Product Runtime` was observed Running before and after and was never
stopped, replaced or rebuilt. OpenDitoo stayed on port 8796; OpenTivoo's 8779 was not
touched.

## M6.2 Honest operation diagnostics

New `runtime/windows/OpenDitoo.Day1.Host/ImageOperationDiagnostics.cs` adds a bounded
in-memory record (last 5 operations, nothing persisted). `/v1/status` now separates:

- Host readiness/capabilities (unchanged existing fields — all previous CLI callers still pass);
- `statusPerformsDeviceIo = false` — status never touches Bluetooth;
- `deviceConnectivity = "unknown"` with `deviceConnectivityBasis = "no_active_observation"` — a past ACK is never reported as present connectivity;
- `operationHistoryScope = "volatile_since_host_start"` — after a restart prior observations are absent, not replayed;
- `diagnostics.operationInProgress` / `inProgressOperation`;
- `diagnostics.lastOperation` / `recentOperations`, each carrying operation id, start/end UTC, duration, source image packet SHA-256, palette colors, last completed stage, terminal result, planned vs. actually-completed packets/bytes, `inFlightPacketBytesUnknown`, `socketClosed`, ACK payload and a bounded error code.

Stage vocabulary, recorded by the transport as it progresses:
`received → validation → target_precheck → connect → send_ready → packet_1..3_sent → ack`.
A send that does not complete sets `inFlightPacketBytesUnknown = true` before the
throw, so partially-sent bytes are reported as unknown rather than counted. `retry`
is constant `false`; there is still no automatic retry or reconnect.

No token, Authorization header, request pixel payload or raw-packet API is exposed,
and the diagnostics module performs no file writes.

Live status after deployment (excerpt):

```json
{"deviceConnectivity":"unknown","deviceConnectivityBasis":"no_active_observation",
 "statusPerformsDeviceIo":false,"operationHistoryScope":"volatile_since_host_start",
 "diagnostics":{"operationInProgress":false,"operationsCompletedSinceHostStart":0,
 "lastOperation":null,"recentOperations":[]}}
```

Deployment: `refresh_openditoo_day1_host.ps1` dry run `WINDOWS_BUILD=PASS` /
`REFRESH_DRY_RUN_PASS`, then `-Apply` → `OPENTIVOO_TASK=preserved`,
`REFRESH_STATUS=PASS_TYPED_IMAGE`. Post-deploy installed
`OpenDitoo.Day1.Host.dll` SHA-256
`c53f8d36165b8b6107cb378154cfd5dd78261477ce376c7a06b2bffe8a376591` matches the
repository build exactly.

## M6.3 Encoder/CLI boundary verification

`tests/test_day1_offline.py` gains `M6RuntimeAcceptanceTests` (7 cases, no device I/O):

- asymmetric 7-colour image survives PNG decode → encode, verified by an independent
  packet unpacker that rebuilds RGB888 from the palette and packed indices — any
  transpose/flip/row-column swap fails;
- corrupted PNG chunk CRC is rejected;
- transaction is exactly three packets and the C# preambles equal the Python
  stock-derived constants byte for byte; CLI still requires `packetCount == 3` and `retry == False`;
- the Python/C# packet-hash gate is proven to appear before both the pairing precheck
  and any `ExchangeOnce` call, i.e. before Bluetooth I/O;
- `/v1/status` source contains no device-I/O call and reports unknown connectivity;
- diagnostics are bounded, volatile and free of tokens/pixels/persistence;
- transport stage progress and the unknown-in-flight-bytes flag are wired, with
  `SendOutcomeUnknown()` proven to precede the `IMAGE_SEND_FAILED` throw.

Existing coverage already held alpha-on-black compositing, indexed PNG, >255 colours
and wrong geometry, so those were not duplicated.

`scripts/verify_day1_offline.py` no longer prints a hardcoded `tests=22`; it parses
the real count from the unittest run.

`DAY1_OFFLINE_PASS artifacts=19 tests=29 host=typed_image port=8796 device_io=false m4_completed=true m4_authorized=false m5_authorized=false`

## M6.4 Product-path acceptance — OPEN OPERATOR GATE

`examples/openditoo-smile-16.png` is prepared and frozen offline:

- PNG SHA-256 `def0d19fbac3d8ebae47b674009cbda392996a634ce9774a9d303ac13770f382`
- RGB888 SHA-256 `fbed71941831927c926c15f897f3335de45d9becc53c28793c9fefa146f96067`
- palette colours 4, image packet 94 bytes, packet SHA-256 `e4fe7ff42632495cdcb5eceb9131a720eb77fccad2183dc98dcf0e881b2e37ea`

No existing capture records a physical acceptance of this image, so the send has not
been replaced by prior evidence. It was **not** performed here: `image-show` is
authorized only by the operator's own explicit invocation.

Operator action, with the Ditoo powered on and the Android app's Bluetooth
disconnected (one controller at a time):

```sh
cd /home/wan/Projects/openditoo-research
python3 cli/openditoo.py image-show --png examples/openditoo-smile-16.png
```

Then record: returned `imagePacketSha256` (must equal the frozen packet hash above),
`ackPayloadHex`, `operationId`, `lastCompletedStage`, and the physical observation of
orientation, marks and colours. `python3 cli/openditoo.py status` afterwards will show
the same operation in `diagnostics.lastOperation`.

If the result is ambiguous after transmission, stop: do not re-run. A successful ACK
is transport evidence only — not visual acceptance and not proof that nothing
persisted.

## M6 exit criteria status

| Criterion | State |
| --- | --- |
| Installed identity reconciled with repository | PASS (hash-identical before and after) |
| Status separates Host health, past transactions, unknown device state | PASS |
| Exact PNG → Host → device acceptance | OPEN — operator gate, command frozen above |
| Existing static behaviour and offline verification pass | PASS (29 tests, verifier PASS) |
| Startup needs no persistent user terminal | PASS — scheduled task `OpenDitoo Day1 Host`, at-logon, observed Running |
