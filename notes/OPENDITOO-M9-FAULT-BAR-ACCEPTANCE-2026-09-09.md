# OpenDitoo M9 fault-bar visual acceptance — 2026-09-09

Prepared one-shot experiment: **OPENDITOO-M9-ACTIVATION-009**.

Purpose: inspect the production `optiplex_lab` source-health fault marker on the exact Ditoo without causing a real Lab outage or modifying persisted MCP activity state. Frames are frozen from the real production renderer and current normalized state. Lab is currently healthy-but-grey because it has no activity history, making the comparison unusually clean.

Visual sequence: **grey Lab/no bar (3 s) → grey Lab + dim-red 3-pixel top bar (3 s) → grey Lab/no bar**. The middle frame changes only copied Lab health to `unavailable`; production renderer then sets `fault=true` and draws `FAULT_MARKER` at Lab x=1..3, y=0, RGB `(170,0,0)`.

The committed hash-frozen persistent product runtime is not modified. For live execution its service must be stopped to release the single-controller Host/session gate, the one-shot sequence run once, and the product service restarted immediately afterward. This is rendering acceptance only; it does not claim a real source outage was detected.

No live authority is embedded here. 009 requires an explicit grant naming its exact experiment id.


### Activation 009 result — Lab fault bar physically accepted

`OPENDITOO-M9-ACTIVATION-009` is consumed and PASS. The frozen production-renderer sequence sent exactly three frames in one connection (9 packets / 494 application bytes, ACKs 0x61/0x99/0xF4, 6413 ms total): healthy Lab grey/no bar -> render-only simulated `source_health=unavailable` Lab grey + dim-red crown fault bar -> healthy Lab grey/no bar. Operator observation: **"saw it, looks good"**. This physically accepts the fault-bar appearance/path on the exact Ditoo. It remains correctly labeled simulated source-health acceptance; it does not prove that a genuine Lab outage is detected end-to-end. Persistent product authority remains separate and active.
