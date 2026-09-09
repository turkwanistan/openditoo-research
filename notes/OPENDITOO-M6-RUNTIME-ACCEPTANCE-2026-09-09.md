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

## M6.4 Product-path acceptance — CLOSED (operator, 2026-09-09)

The operator invoked the product primitive once against the frozen fixture and
**reports the smile visible on the exact unit**. Evidence:
`captures/OPENDITOO-M6-IMAGE-SHOW-ACCEPTANCE-2026-09-09.json`.

The Host's new diagnostics recorded the transaction end to end:
`result=ok`, `lastCompletedStage=ack`, `connectionsAttempted=1`,
`packetsSentComplete=3/3`, `txBytesSentComplete=109/109`,
`inFlightPacketBytesUnknown=false`, `socketClosed=true`, `retry=false`, 216 ms —
against `imagePacketSha256 e4fe7ff4…37ea`, matching the frozen offline preparation
exactly, so the Python encoder and the C# encoder agreed before any Bluetooth I/O.

### Two operations — resolved

`operationsCompletedSinceHostStart` was **2**: `b7f8f263e448` at 04:05:47 UTC and
`7026e693402d` at 04:05:59 UTC, 12.5 s apart, same image packet. The operator confirmed
both were deliberate manual invocations. Each performed exactly one connection, and
neither the Host nor the CLI can retry or reconnect — consistent with the no-retry
boundary, with no unexplained traffic.

### Finding: the ACK payload is not a success constant

| Operation | Image packet | ACK payload |
| --- | --- | --- |
| M5 diagnostic (different image) | `db336e89…cb9b` | `0x12` |
| `b7f8f263e448` | `e4fe7ff4…37ea` | `0x75` |
| `7026e693402d` | `e4fe7ff4…37ea` (identical) | `0xF0` |

A byte-identical image packet produced two different ACK payload bytes. **MATCHED:**
the wrapped `0x44` ACK payload is not a fixed success code and must never be validated
as one. No meaning is assigned to it — counter, sequence, echo and unrelated state are
all still open. The CLI already gates on `ok`, packet count, packet hash, palette
count, connection count, socket close and `retry`, and deliberately not on the ACK
value; `test_cli_does_not_treat_the_ack_payload_as_a_success_constant` pins that.

### Finding: pixel geometry is physically confirmed

The fixture carries a 3-pixel yellow L-shaped asymmetry mark at `(1,1) (1,2) (2,1)`.
The operator reports **exactly 3 yellow pixels in the top-left corner**, with the frame
reading as an upright smile.

Corner plus pixel count excludes horizontal flip, vertical flip and 180° rotation. The
mark's L-shape is invariant under transposition, so it cannot exclude that on its own —
but a transposed, anti-transposed or 90°/270°-rotated smile would read as a sideways
"C", and it does not. **MATCHED:** all eight dihedral orientations are excluded, and the
encoder's row-major top-left-origin geometry is correct end to end.

### Still open after acceptance

- **Colour rendition** — partial. Yellow renders as yellow; magenta and cyan were not
  separately reported.
- **Persistence** — untested. A successful ACK and a visible frame say nothing about
  whether anything was written to the device, or whether the frame survives a power
  cycle or a stock page change. This is the one remaining unknown in the static
  primitive and it matters for M8/M9, which assume frames are volatile.

## M6 exit criteria status

| Criterion | State |
| --- | --- |
| Installed identity reconciled with repository | PASS (hash-identical before and after) |
| Status separates Host health, past transactions, unknown device state | PASS |
| Exact PNG → Host → device acceptance | **PASS** — operator-invoked, visually confirmed, recorded in `captures/OPENDITOO-M6-IMAGE-SHOW-ACCEPTANCE-2026-09-09.json`; orientation, colour rendition and persistence remain unconfirmed |
| Existing static behaviour and offline verification pass | PASS (29 tests, verifier PASS) |
| Startup needs no persistent user terminal | PASS — scheduled task `OpenDitoo Day1 Host`, at-logon, observed Running |
