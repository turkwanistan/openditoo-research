# OpenDitoo MCP dashboard — accelerated status-transition acceptance

Date: 2026-09-09

## Purpose

Physically verify the dashboard's production status colours on the exact Ditoo Plus without waiting more than 20 minutes. This is a **visual acceptance profile only**; it does not change production status semantics.

Production remains:

- green: usable last activity age < 5 minutes
- yellow: 5 to < 20 minutes
- red: >= 20 minutes
- grey: no usable activity data (not a fourth age bucket)

## Test profile

`status_age_colors_v1` presents representative virtual states to the unchanged production `activity_render.status_for()` logic:

| Real test time | Production state represented | Expected panel |
| --- | --- | --- |
| 0-3 s | 1 minute old | green |
| 3-6 s | 10 minutes old | yellow |
| 6-9 s | 30 minutes old | red |
| 9-15 s | no usable activity timestamp | grey |

All three source columns change together for easy human inspection. The acceptance renderer does not collect MCP sources, write `.openditoo-local/activity-state.json`, alter the real 5/20-minute constants, or introduce a grey age threshold.

## Offline evidence

- production boundary tests remain pinned at 5 and 20 minutes;
- acceptance profile is the only allowed named test profile;
- persisted source state is not mutated;
- collection/save functions are never called by the profile;
- a full fake session emits exactly four changed frames and otherwise holds;
- `scripts/verify_day1_offline.py`: 157 tests PASS, zero device I/O.

## Live boundary

Fresh manifest: `experiments/DAY1-M9-ACTIVATION-008.json`.

One execution only, up to 15 seconds, one RFCOMM connection, expected four changed frames, hard ceiling 8 frames / 24 packets / 1,624 application bytes, ACK per frame, no retry/reconnect/reclaim/pipelining/streaming/unattended operation.

**Nothing is currently authorized.** 008 requires an explicit operator grant naming `OPENDITOO-M9-ACTIVATION-008`.
