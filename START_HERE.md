# OpenDitoo — Start Here

OpenDitoo is the preservation-first Divoom Ditoo Plus project. Exact-unit evidence and preserved artifacts outrank family resemblance, plans, and chat history.

## Current session route — 2026-09-08

1. Read `AGENTS.md` for the execution/authority boundary.
2. Read `notes/OPENDITOO-DAY1-EXECUTION-STATE-2026-09-08.md` for the current application-first milestone state and exact next action.
3. Read `PROJECT_STATE.md` for the comprehensive static/reconnaissance evidence base.
4. Treat `artifacts/` plus `artifacts/SHA256SUMS`, provenance JSON and raw evidence as authoritative for acquired artifacts.
5. Before changing or executing Day-1 code, run:

   ```sh
   python3 scripts/verify_day1_offline.py
   ```

6. Preserve the MATCHED / RELATED / LEAD evidence calibration in `PROJECT_STATE.md`; related Tivoo/Divoom behavior is not exact Ditoo Plus or exact purchased-unit truth.
7. Before any custom physical transmission, require a concrete exact-unit manifest and the authority gate in `AGENTS.md`. A plan/template is not authority.

## Current objective

Application-first Day 1:

`stock characterization -> measured application-control transport -> codec verdict -> one bounded custom query -> one independently justified volatile 16x16 frame`

The older MassBoot key/GPIO/update-dispatch research is preserved, but it is deferred for this objective. Do not restart USB/service-mode work merely because those static paths exist.

## Working topology

`WSL_MCP -> WSL project/CLI -> separate authenticated Windows OpenDitoo Host -> Windows Bluetooth -> Ditoo`

The WSL project is `openditoo-research` under `/home/wan/Projects`. The OpenDitoo Host must keep its endpoint, token, state and process ownership separate from OpenTivoo. Never replace OpenTivoo's Host, task or port 8779.

Current OpenDitoo Host candidate is status-only on `127.0.0.1:8796`: no Bluetooth transport or target is configured until exact-unit M1/M2 evidence exists.

## Prohibitions for current Day 1

No firmware updates, persistent uploads, teardown, service/test/MassBoot entry, USB vendor commands, arbitrary proprietary writes, command brute-forcing, inherited Tivoo permissions, or automatic resend after an ambiguous custom outcome.
