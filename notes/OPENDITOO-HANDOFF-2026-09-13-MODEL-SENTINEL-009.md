# OpenDitoo handoff — exact-unit v42012 model-sentinel differential — 2026-09-13

This is the compact current handoff. The live repository is authoritative over this note and chat history. Start with the current block of `START_HERE.md`, then this file; pull older VRAM evidence only when these files point to it.

## Exact checkpoint

- Repository: `~/Projects/openditoo-research`.
- Exact purchased unit: Divoom Ditoo Plus, RFCOMM channel 1, installed-version observation v42012.
- Exact v42012 firmware bytes remain unrecovered; later preserved-branch RAM addresses/layouts remain hypotheses until exact-unit differentials support them.
- Everyday product: Runtime 018, revision 13. After PREMODEL-008 it restored `connected`, `last_error=null`.
- One controller owns the Ditoo. Experimental authority is one-use, exact-manifest-bound, and never transfers between experiment IDs.

## PREMODEL-008 — terminal PASS

`OPENDITOO-VRAM8B-PREMODEL-008` is **consumed / PASS_PREMODEL_CONTROL_MATCHES_CONTROL_007** and may never be replayed.

One connection sent stock `0x6e`, stock `0xA5`, then exactly one data-only custom `0x6c` at 44 ms after A5. Its source was exactly `0x410` / 1040 bytes of `0xFF`; under the later-branch hypothesis it reached predicted runtime50 `+0..+7` only, not model `+0x08` or callback `+0x34`.

The exact-unit receive transcript preserved CONTROL-007's semantic lifecycle byte-for-byte:

- early wrapped `0xBD`, payload `13 01 4b 00`, at 18 ms (CONTROL-007: 23 ms)
- late wrapped `0xBD`, payload `13 01 1e 00`, at 65,316 ms (CONTROL-007: 65,252 ms)
- connection survived through 75,014 ms
- Runtime 018 revision 13 restored connected with no error

Durable evidence: `captures/OPENDITOO-VRAM8B-PREMODEL-008-LIVE-RESULT-2026-09-13.json`, SHA-256 `1f41c44ef20a7cdceca2e89166cc29cb6b8bf79c642752fc7be319900e57ad7f`.

Interpretation: bytes predicted as runtime50 `+0..+7` did not perturb the observed stock VoiceTip lifecycle. This closes 008 as the pre-model side of the differential; it does **not** independently prove the later-branch runtime50 base address.

## MODEL-SENTINEL-009 — current sole live boundary

Fresh `OPENDITOO-VRAM8B-MODEL-SENTINEL-009` is **prepared / unauthorized / unconsumed**.

Its device-side delta from 008 is exactly one additional source byte:

- 008 source: `0x410` bytes of `0xFF`
- 009 source: `0x411` bytes of `0xFF`
- source prefix is byte-for-byte identical; the only new source byte is offset `0x410 = 0xFF`
- stock `0x6e` and `0xA5` frames are byte-for-byte identical to 008
- same one-connection, no-retry/no-reconnect policy
- same ~40 ms A5→overwrite target and same 75-second A5-relative capture window

Under the preserved later-branch geometry, the added byte reaches exactly predicted runtime50 model `+0x08` and changes it to `0xFF`; predicted callback `+0x34` remains unreachable. There is no custom code and no callback pointer.

Frozen hashes:

- manifest: `experiments/OPENDITOO-VRAM8B-MODEL-SENTINEL-009.json`
- manifest SHA-256: `c0687e106867da409de0747be7900e4df3d863cfc7daa2324f0f2579d645bb01`
- fixture report: `artifacts/analysis/volatile_ram_api_vram8b_model_sentinel_009.json`
- fixture-report SHA-256: `7292b0bdef25c9b5468dae905d13eb9b2fbc4e9b175a9220e7b9c35796f6c097`
- source SHA-256: `de3c1b8f05276b4b29099e1955834f49c8cee84c7bb1b216d17c7038571aa42a`
- overwrite-frame SHA-256: `9f80e0452c3f1876348482c289fdb1f9ee6ec99a4ebfef133d1b496d58de77e8`

Offline verification: `python3 tools/ditoo_vram8b_model_sentinel_009_gate.py --selfcheck` passes; focused one-byte-delta tests are 2/2 PASS; no 009 grant/claim/handover/execution/result exists. The WSL_MCP sandbox has no `dotnet`, so the C# runner was not compiled there; the frozen local-manual launcher performs a Windows Release build before any one-use claim or Bluetooth open and refuses on build/hash drift.

The exact future grant is:

`Grant OPENDITOO-VRAM8B-MODEL-SENTINEL-009 -- stock btplayer selected`

Do not infer that grant from a handoff/orchestration prompt.

## After an exact 009 grant

1. Materialize a fresh local mode-0600 one-use grant bound to the two frozen hashes and a fresh nonce.
2. Re-run the 009 gate and require no pre-existing claim/result.
3. Verify Runtime 018 revision 13 is `connected`, `last_error=null`.
4. Owner executes locally exactly:
   `cd ~/Projects/openditoo-research && bash scripts/run_vram8b_model_sentinel_009_once.sh`
5. Once a claim exists, 009 is consumed forever regardless of outcome. Inspect result immediately and verify Runtime 018 restoration.
6. Compare the 009 semantic transcript against both 008 and CONTROL-007 before preparing anything further.

If 009 changes the `4b -> 1e` lifecycle or otherwise materially diverges while 008 did not, that supports the predicted one-byte model-boundary hypothesis on the exact unit. If 009 remains semantically identical, the later-branch placement/model-semantic hypothesis is weakened; stop and reinterpret before any callback canary or VRAM-8D work. Do not return to executable callback canaries merely because 005/006 were negative.
