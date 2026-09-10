# Runtime 007 + webcam 006 — first-frame-spacing Host re-bind (prepared, UNAUTHORIZED)

Branch `feat/host-first-frame-spacing` (off `main` at `0c7b522`). Nothing is deployed. The live product is still Runtime 006 + webcam 005 on Host `f7bd60d4…`.

## Why

A Host-ledger analysis (`captures/OPENDITOO-STREAMING-FIRST-FRAME-TIMEOUT-ANALYSIS-2026-09-10.json`) found that first-frame `IMAGE_RX_RECV_TIMEOUT` hits **5 of 19** `streaming_ack_clock` opens and **0 of 199** `activity` opens. After frame 1 ACKs, streaming sessions run thousands of frames. The only per-profile transport difference is intra-frame packet spacing (0 ms vs 10 ms). This is what failed HF3-002 and the 19:49Z webcam launch.

## What changes

| Piece | Change |
|---|---|
| Host `ActivitySessionHost.SendFrame` | a session's **first frame** uses `ActivitySendSpacingMs` (10 ms); later frames keep the profile's spacing |
| Host + Studio `.csproj` | `PathMap`, so DLL bytes no longer depend on the checkout path (the embedded PDB path differed between worktree and main) |
| Host DLL | `3faf520f46ce824970f583c3d932e0168484b0f6ffa5975e6b38e77330c4900f`, identical from worktree, AppData copy and clean rebuild |
| `product/OPENDITOO-PRODUCT-RUNTIME-007.json` | exactly Runtime 006 except the Host hash, `pagination_sha256` (its template/grant constants) and authority text. The loader refuses any 007 whose pages/probe differ from 006 |
| `product/OPENDITOO-WEBCAM-PRODUCT-006.json` | webcam 005 except the Host hash, policy id and the rebuilt Studio (`StudioTrial.PolicyId`, PathMap). Studio DLL `c259dca8…`. Selftest + 15 transform + 6 encoder parity cases PASS. Staged only to `C:\temp\openditoo-webcam-studio-candidate`; the installed Studio is untouched |
| `scripts/cutover_runtime_007.sh` | the cutover script described below |

`scripts/cutover_runtime_007.sh`:
1. Takes both exact grants.
2. Verifies main is clean and fast-forwardable, the local policies are 006/005, and the installed Host is `f7bd60d4`.
3. Waits out the young-link guard.
4. Saves exact-byte rollback (local policies, repo and installed Host + Studio, pre-merge commit) to `.openditoo-local/rollback-runtime-006/`.
5. Stops the dashboard and requires the Host to be idle.
6. Fast-forwards main.
7. Deploys the Host through the proven refresh script and verifies `3faf520f…` installed and in the repo.
8. Rebuilds the Studio and verifies the frozen hashes.
9. Runs the **full offline gate in main**.
10. Writes the 007 local policy, then product-check.
11. Restarts and requires `connected` with no error.
12. Installs the Studio and swaps webcam 005 → 006, then policy-check.

Any failure after the merge runs `--rollback`: `git revert` of the merged range, exact-byte restore, and Runtime 006 + webcam 005 back, verified.

## Verification

- Legacy suite on this branch: 326 tests. The 6 that read main's local one-use claims pass when pointed read-only at main's `session-claims`. Everything else passes.
- New `HostFirstFrameRebindTests` pins the re-bind-only diffs, PathMap, and the cutover's grant/rollback/gate order.
- The fix itself is **not yet proven on the device**. The first streaming opens after cutover (webcam launch or HF3-004) are that evidence. Watch the first-frame timeout rate.

## Grants required (owner)

`Grant OPENDITOO-PRODUCT-RUNTIME-007` and `Grant OPENDITOO-WEBCAM-PRODUCT-006`, then run:
`bash .openditoo-local/worktrees/host-first-frame-spacing/scripts/cutover_runtime_007.sh "Grant OPENDITOO-PRODUCT-RUNTIME-007" "Grant OPENDITOO-WEBCAM-PRODUCT-006"`

After cutover, `feat/high-fps-interactive-pages` must be rebased onto main (Host binding `f7bd60d4` → `3faf520f` in its HF-3 manifest), and HF3-004 is frozen fresh on the `PageCarousel` design.
