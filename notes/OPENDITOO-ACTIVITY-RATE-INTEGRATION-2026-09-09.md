# OpenDitoo activity-rate integration — 2026-09-09

## Result

The measured R1-R5 rate ladder is now wired into the **source** for the MCP activity
display. This was an offline implementation only: no device I/O, Bluetooth operation,
Windows build, install, Host refresh, or transmission authority was used.

The product operating floor is **150 ms between frame starts (6.67 fps)**. This is a
policy below the measured ceiling, not a new device measurement. It was chosen because:

- R4 physically sustained full-colour motion at **131.0 ms/frame (7.63 fps)** for 512
  frames over 67 s with flat quarter timing and operator-confirmed smooth motion;
- R5 physically sustained **54.2 ms/frame (18.46 fps)** for 1024 full-colour frames over
  56 s with one ACK per frame, but its worst frame was 111 ms and jitter was material;
- the handoff explicitly recommends **6-7 fps** for the activity product rather than
  operating at the ceiling; and
- four 150 ms display stages produce a readable **~0.60 s** activity pulse.

The activity-session Host source now uses the already accepted **10 ms intra-frame packet
spacing** from R2b/R3/R4. It does not use R5's zero-idle timing as the product default.
Pipelining is unchanged and unimplemented.

## Source changes

- `host/activity_session.py`
  - enforces a 150 ms minimum frame-start interval in reviewed future session manifests;
  - schedules ticks start-to-start, so HTTP/Bluetooth/ACK work consumes the 150 ms budget
    rather than being added on top;
  - decouples the display tick from source collection, preserving each source's configured
    multi-second polling cadence;
  - advances activity animation only after the current stage is ACKed; and
  - coalesces new activity instead of queueing or replaying old pulses.
- `host/activity_render.py` implements the approved four-stage family:
  cyan -> blue -> light blue -> cyan. The crown, identity letter and icon accent change
  together, then return to the current age/health colour. Static reference rendering is
  preserved for the eight approved mockups.
- `runtime/windows/OpenDitoo.Day1.Host/ActivitySessionHost.cs` independently enforces the
  same 150 ms floor and fixes activity-session packet spacing at the accepted 10 ms.
- `scripts/verify_day1_offline.py` now verifies the current pacing source even though the
  historical M9 manifests are consumed; those immutable 1118 ms manifests remain valid
  evidence and are not rewritten.

## Offline verification

After the integration:

```text
151/151 tests PASS
DAY1_OFFLINE_PASS artifacts=19 tests=151 host=typed_image port=8796 device_io=false
m4_completed=true m4_authorized=false m5_authorized=false ui=approved_mcp_page
m9_activation_authorized=false
```

New regression coverage proves:

1. all four approved pulse colours are rendered on crown + active identity/accent;
2. a 150 ms display tick does not turn source collection into a 6.67 Hz poll;
3. a simulated 70 ms transport/ACK cost still produces frame starts at 0/150/300/450 ms,
   rather than 0/220/440/...; and
4. Host/Python source agree on the 150 ms floor and Host source pins 10 ms packet spacing.

## Capability boundary of the implementing session

Read-only probes in this WSL_MCP session produced:

- `command -v powershell.exe` -> unavailable;
- `python3 cli/openditoo.py status` -> `HOST_UNAVAILABLE`, connection refused;
- `python3 cli/openditoo.py activity-probe` -> command succeeded without device I/O, but
  all three sources returned `SOURCE_READ_FAILED`.

Therefore this note establishes **offline/source verification only**. It does not establish
a Windows build, installed identity, transport acceptance, visual acceptance of the new
four-stage pulse, stock-yield behaviour, or physical fault-bar behaviour. The previously
accepted R1-R5 device measurements are the evidence used to choose the policy; this source
change itself has not been physically exercised.

## Remaining boundary

Before any live trial, a capable environment must build the changed Windows Host, verify
the exact repository/installed identities, and verify the required activity sources. Only
then should a **new** manifest with a **new** experiment id be frozen and presented for an
explicit named operator grant. No current manifest is authorized, and no consumed manifest
may be re-armed.

Stock-yield and the fault bar remain **NOT TESTED on hardware** and must not be closed with
a simulated failure. Streaming beyond one minute and the two M8 `operator_visual_order`
fields remain open but lower value.
