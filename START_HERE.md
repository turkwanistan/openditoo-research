# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

## Current session route — 2026-09-09 (handoff)

1. **Read `notes/OPENDITOO-HANDOFF-2026-09-09.md` first.** It carries current accepted
   work, findings with confidence levels, authority state, open questions, the next
   objective and the traps not to repeat.
2. Read `AGENTS.md` for the execution/authority boundary.
3. Run `python3 scripts/verify_day1_offline.py` before changing or executing anything.
4. Read the milestone evidence only as needed:
   - `notes/OPENDITOO-M6-RUNTIME-ACCEPTANCE-2026-09-09.md` — runtime, diagnostics, physical acceptance
   - `notes/OPENDITOO-M7-CONTROL-WORKSHEET-2026-09-09.md` + `captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json` — physical input result
   - `notes/OPENDITOO-M7-OPENTIVOO-COMPARISON-2026-09-09.md` — comparative prior art, class 5
   - `notes/OPENDITOO-M8-SEQUENCE-EVIDENCE-2026-09-09.md` — repeated frames and the rate ceiling
   - `notes/OPENDITOO-M9-SOURCE-DISCOVERY-2026-09-09.md` — the three MCP sources and the collector
   - `notes/OPENDITOO-DAY1-EXECUTION-STATE-2026-09-08.md` — the M0-M5 trail
5. `PROJECT_STATE.md` is the static/reconnaissance base. Its service-mode priorities are
   superseded by the application-first route.
6. Treat `artifacts/` plus `artifacts/SHA256SUMS` and provenance JSON as authoritative
   for acquired artifacts, and preserve the MATCHED / RELATED / LEAD calibration.

### Milestone state

| Milestone | State |
| --- | --- |
| M0-M5 | complete; authorities consumed |
| M6 static runtime + diagnostics | complete; physically accepted; pixel geometry proven |
| M7 keyboard/button mapping | complete as a **bounded negative**; no usable physical navigation |
| M8 repeated frames | complete; accepted ceiling ~1118 ms/frame, measured twice |
| M9 activity application | offline half complete and tested; display activation not started |

### Authority state

**Nothing is currently authorized.** Every experiment manifest is consumed;
`sequence-run` exits 30 on all of them. Any live operation needs a new manifest and an
explicit operator grant naming its experiment id. Continuous or unattended display is a
larger authority shape than any bounded run so far.

### Next objective

M9 display activation — see section 8 of the handoff note for what its manifest must
cover. Offline work available without any grant:

```sh
python3 cli/openditoo.py activity-probe
python3 cli/openditoo.py activity-status --collect
python3 cli/openditoo.py activity-preview --collect
```

## Current objective

M0-M5 are complete through a visibly successful custom 16x16 frame. Current objective is the bounded product runtime:

`exact local 16x16 PNG -> deterministic RGB888 decode -> stock-derived image packet -> authenticated fixed-target Windows Host -> Ditoo`

The older MassBoot key/GPIO/update-dispatch research is preserved but deferred. Do not restart USB/service-mode work merely because those static paths exist.

## Working topology

`WSL_MCP -> WSL project/CLI -> separate authenticated Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

The WSL project is `openditoo-research` under `/home/wan/Projects`. The OpenDitoo Host must keep its endpoint, token, state and process ownership separate from OpenTivoo. Never replace OpenTivoo's Host, task or port 8779.

The post-M5 OpenDitoo Host remains isolated on `127.0.0.1:8796` but is now a typed static-image runtime: fixed exact Ditoo target, fixed RFCOMM channel 1, one `image-show` route, no target override and no raw-send route. The currently installed Windows Host may still be the older status-only build until `runtime/windows/refresh_openditoo_day1_host.ps1 -Apply` is run and validated.

## Prohibitions for current Day 1

No firmware updates, persistent uploads, teardown, service/test/MassBoot entry, USB vendor commands, arbitrary proprietary writes, command brute-forcing, inherited Tivoo permissions, or automatic resend after an ambiguous custom outcome.
