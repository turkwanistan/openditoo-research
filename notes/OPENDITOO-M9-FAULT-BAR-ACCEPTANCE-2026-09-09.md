# OpenDitoo M9 fault-bar visual acceptance — 2026-09-09

Prepared one-shot experiment: **OPENDITOO-M9-ACTIVATION-009**.

Purpose: inspect the production `optiplex_lab` source-health fault marker on the exact Ditoo without causing a real Lab outage or modifying persisted MCP activity state. Frames are frozen from the real production renderer and current normalized state. Lab is currently healthy-but-grey because it has no activity history, making the comparison unusually clean.

Visual sequence: **grey Lab/no bar (3 s) → grey Lab + dim-red 3-pixel top bar (3 s) → grey Lab/no bar**. The middle frame changes only copied Lab health to `unavailable`; production renderer then sets `fault=true` and draws `FAULT_MARKER` at Lab x=1..3, y=0, RGB `(170,0,0)`.

The committed hash-frozen persistent product runtime is not modified. For live execution its service must be stopped to release the single-controller Host/session gate, the one-shot sequence run once, and the product service restarted immediately afterward. This is rendering acceptance only; it does not claim a real source outage was detected.

No live authority is embedded here. 009 requires an explicit grant naming its exact experiment id.
