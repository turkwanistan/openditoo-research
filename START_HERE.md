# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

## Current session route — 2026-09-09

1. Read `AGENTS.md` for the execution/authority boundary.
2. Read `notes/OPENDITOO-M6-RUNTIME-ACCEPTANCE-2026-09-09.md` — installed-Host
   reconciliation, honest status diagnostics, and the one open operator gate.
3. Read `notes/OPENDITOO-M9-SOURCE-DISCOVERY-2026-09-09.md` — the three MCP activity
   sources, the collector/renderer, and what is deliberately not built yet.
4. Read `notes/OPENDITOO-M7-CONTROL-WORKSHEET-2026-09-09.md` before any keyboard work.
5. Read `notes/OPENDITOO-POST-M5-TYPED-IMAGE-RUNTIME-2026-09-08.md` and
   `notes/OPENDITOO-DAY1-EXECUTION-STATE-2026-09-08.md` for the M0-M5 evidence trail.
6. Read `PROJECT_STATE.md` for the comprehensive static/reconnaissance evidence base.
7. Treat `artifacts/` plus `artifacts/SHA256SUMS`, provenance JSON and raw evidence as
   authoritative for acquired artifacts.
8. Before changing or executing project code, run:

   ```sh
   python3 scripts/verify_day1_offline.py
   ```

9. Preserve the MATCHED / RELATED / LEAD evidence calibration in `PROJECT_STATE.md`;
   related Tivoo/Divoom behavior is not exact Ditoo Plus or exact purchased-unit truth.
10. The proven product `image-show` command is authorized only by an operator's explicit
    invocation for that one validated PNG. Any new protocol family/semantic, persistence
    behavior, streaming mode, retry behavior or target must return to the
    experiment/authority gate in `AGENTS.md`.

### Milestone state

| Milestone | State |
| --- | --- |
| M0-M5 | complete; authority consumed |
| M6 static runtime acceptance + diagnostics | **complete** — code, build, deployment, offline verification and operator-confirmed physical PNG acceptance (2026-09-09) |
| M7 keyboard/button mapping | worksheet prepared; **blocked on operator capture** |
| M8 bounded repeated frames | **not started**; needs its own experiment manifest and authority |
| M9 three-MCP activity application | sources discovered, collector + renderer + previews **complete and tested offline**; worker install and physical updates wait on M8 |

**Exact next action** — M6 is fully closed: physical acceptance and pixel geometry
are both confirmed (2026-09-09). One cheap operator check remains before M8, because
M8 and M9 both assume displayed frames are volatile:

- **Persistence check.** Power-cycle the Ditoo and report what the screen shows. No
  new authority needed — it is an observation, not a transmission. If the custom frame
  survives a power cycle, the volatility assumption behind M8/M9 is wrong and must be
  revisited before any repeated-frame work.

Then, in either order:

- **M7 operator capture** using `notes/OPENDITOO-M7-CONTROL-WORKSHEET-2026-09-09.md`
  (stock observation only, one controller at a time).
- **M8 experiment manifest** for a frozen A→B sequence, which needs explicit authority
  before it runs.

Offline, with no device involved:

```sh
python3 cli/openditoo.py activity-probe
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
