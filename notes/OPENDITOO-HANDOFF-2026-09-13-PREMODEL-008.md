# OpenDitoo handoff — exact-unit v42012 PREMODEL differential — 2026-09-13

This is the compact session-rotation handoff. The live repository is authoritative over this note and over chat history. Start with the current block of `START_HERE.md`, then this file. Pull older VRAM evidence only when these files point to it.

## Exact checkpoint

- Repository: `~/Projects/openditoo-research`
- Baseline implementation/evidence checkpoint: `ca2d2b71c9216527f20a04ecb6d79508fe72c6a4` (`ca2d2b7`), pushed to `origin/main` before this handoff-only commit.
- Exact purchased unit: Divoom Ditoo Plus, RFCOMM channel 1, installed-version observation v42012. Exact v42012 firmware bytes remain unrecovered; later-branch RAM addresses/layouts are hypotheses until live-calibrated.
- Everyday product: Runtime 018, revision 13. At the PREMODEL-008 readiness check it was `connected`, `last_error=null`.
- One controller owns the Ditoo. Experimental authority is one-use and exact-manifest-bound under `AGENTS.md`; a consumed/ambiguous attempt is never replayed.

## CONTROL-007 — terminal PASS

`OPENDITOO-VRAM8B-CONTROL-007` is consumed and PASS as the exact-unit stock VoiceTip baseline.

One RFCOMM connection sent only stock `0x6e 01` then stock `0xA5 01 02 01`. No custom `0x6c` was sent. Over the full 75-second receive-only window the exact unit emitted two valid wrapped `0xBD` reports:

- `elapsed_ms=23`, payload `13 01 4b 00`, wire `01090004bd5513014b007e0102`
- `elapsed_ms=65252`, payload `13 01 1e 00`, wire `01090004bd5513011e00510102`

Observation completed at 75,003 ms with the connection alive. Runtime 018 restored connected with no error.

Durable evidence: `captures/OPENDITOO-VRAM8B-CONTROL-007-LIVE-RESULT-2026-09-13.json`, SHA-256 `42f53970da762c86c585cd50013beea9620bd6c94ac6b7e7737beb184aa449a0`.

Interpretation: the exact-v42012 stock VoiceTip lifecycle/timing baseline is now known. It does **not** validate later-branch runtime50 or energy-state addresses.

## PREMODEL-008 — current live boundary

`OPENDITOO-VRAM8B-PREMODEL-008` is prepared and **UNAUTHORIZED / UNCONSUMED** at handoff.

Purpose: establish the pre-model side of a one-byte differential without executing custom code or touching the predicted callback field.

Frozen sequence on one connection:

1. stock `0x6e`
2. stock `0xA5`
3. exactly one custom `0x6c`, scheduled about 40 ms after A5
4. continue the A5-relative receive transcript through 75 seconds

The `0x6c` source is exactly `0x410` / 1040 bytes, all `0xFF`. Under the preserved later-branch geometry it reaches only predicted runtime50 `+0..+7`; it stops one byte before predicted model `+0x08` and far before callback `+0x34`. It contains no custom code and no callback pointer.

Frozen hashes:

- manifest: `experiments/OPENDITOO-VRAM8B-PREMODEL-008.json`
- manifest SHA-256: `201b55743131fa143abcbc360a76d9c22a85f5177217d897b3726802e6b5bbf8`
- fixture report: `artifacts/analysis/volatile_ram_api_vram8b_premodel_008.json`
- fixture-report SHA-256: `84edcd2ae29b90a7c9ccb7359a9aba4b8ba28cf23841360f9cfc3e5a90c963c3`
- source SHA-256: `a096f2c4317dc713fc5121a3a4521eeb396f3552fb1e768463dc1b8d756d8912`
- overwrite-frame SHA-256: `7f2df478e82e69583a31f31944788258cf09a0962b6c858b702ad24dd83451ff`

Gate at preparation: PASS; 3 application sends; one custom `0x6c`; source length `0x410`; predicted model/callback not reached; no grant materialized. The exact pushed `Premodel008` runner independently built with 0 warnings / 0 errors.

## Immediate next action

Do not redo broad hydration. Confirm HEAD/upstream/clean state, read the current `START_HERE.md` block plus this note, and run the 008 gate read-only.

The next live step requires the owner's **fresh exact grant**:

`Grant OPENDITOO-VRAM8B-PREMODEL-008 -- stock btplayer selected`

After that exact grant only:

1. Materialize the fresh one-use local grant against the frozen manifest/fixture hashes and a fresh nonce.
2. Re-run `python3 tools/ditoo_vram8b_premodel_008_gate.py --selfcheck`; require PASS and no claim/result.
3. Verify Runtime 018 revision 13 is connected with `last_error=null`.
4. Have the owner run locally:

```bash
cd ~/Projects/openditoo-research
bash scripts/run_vram8b_premodel_008_once.sh
```

5. On pasted output, immediately inspect local claim/execution/result. If a claim exists, 008 is consumed and must never be replayed. Verify Runtime 018 restoration, then persist the terminal result and update the current-state docs.

## 008 decision tree

If 008 preserves the CONTROL-007 lifecycle — especially the same semantic `0xBD` payload progression `13 01 4b 00` early and `13 01 1e 00` late, with full-window connection survival — treat it as the pre-model control. Then prepare **PREMODEL/MODEL-009** as a fresh independent experiment whose device-side delta is exactly one additional source byte: length `0x411`, making predicted runtime50 `+0x08` become `0xFF` while still remaining far short of callback `+0x34`. Require a fresh exact 009 grant before live execution.

If 008 itself changes the lifecycle, disconnects, produces malformed traffic, or otherwise differs materially from CONTROL-007, stop there. Do **not** advance automatically to 009; diagnose what the `+0..+7` overwrite changed on exact v42012.

Do not return to executable callback canaries or VRAM-8D from the 005/006 negatives until this data-only differential is closed. The key unresolved split is exact-v42012 victim geometry versus later-branch-derived canary/address assumptions.

## Minimal historical context

- 005 and 006 each reached one custom 1088-byte `0x6c`, survived the full callback window, and returned typed B3 `0`, so the later-branch-derived canary effect was not observed.
- Moving the canary execution site from `0x00804901` to pristine `0x00804A81` did not change that result, weakening a simple cache-line/site explanation.
- Those negatives are **not** proof that the v42012 callback never ran, because both callback/victim geometry and the B3 canary's absolute energy-state address were derived from later preserved firmware branches.
- CONTROL-007 therefore became the exact-unit calibration pivot, and PREMODEL-008 is now the sole live boundary.
