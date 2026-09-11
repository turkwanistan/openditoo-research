# OpenDitoo Pocket Moss v3 polish handoff — 2026-09-11

## Physical result that drives this successor

Runtime 011 / Moss v2 is live on the exact Ditoo Plus and the runtime/input path works normally. Physical panel feedback established two important facts:

- v1 was a visual failure: Moss read as a brown blob rather than a dog.
- v2 fixed the identity problem. Owner feedback after trying the live v2 character/animations: **“yes this looks much better … it’s looking pretty great already.”** Remaining criticism is polish, not recognition: idle is a little derpy/flat/deformed-looking, likely from the 3/4 body anatomy and small palette; animations need to be more interesting.

Do not regress to low-contrast brown-on-brown silhouette art. Preserve the v2 face vocabulary: floppy ears, bright tan face, cream muzzle/chest, black eyes/nose, pink tongue/heart.

## Runtime 012 candidate

Branch: `feat/pocket-moss-v3-polish`

Runtime 012 is intentionally narrow. It preserves Runtime 011's exact:

- Ditoo target `11:75:58:CE:DE:C7`, firmware `v42012`, RFCOMM channel 1;
- Windows Host hash `3faf520f46ce824970f583c3d932e0168484b0f6ffa5975e6b38e77330c4900f`;
- ButtonProbe binaries and receive-only input contract;
- one-session Dashboard / Slots / Moss page topology;
- `streaming_ack_clock` pacing, renewal, reconnect and reclaim behavior;
- Moss selector controls and Pet / Dance / Kisses / Back semantics;
- webcam policy 006.

Only the hash-bound Moss default asset root and authored v3 art/choreography change.

## v3 art direction

`assets/pocket_moss/v3/`

- Keeps the v2 recognizable dog face and floppy ears.
- Adds an amber shadow/depth plane between dark ear brown and bright tan to separate cheek, neck, chest and rear body.
- Uses a cleaner consistent body model rather than redrawing anatomy differently in each movement frame.
- Idle is a clearer compact seated/standing hybrid with a readable cream chest and one shaded body side.
- Passive Look/Loaf/Sleep-Wake stay sparse.
- Sleep has closed eyes plus a tiny Z cue.

## Richer authored actions

Pixel Lab quality reports are warning-free.

- **Dance:** 9 authored steps, **8 unique frames** — anticipation crouch → clean step left → clean step right → step left → paws-up hop → landing → high tail wag → low tail wag → settle.
- **Pet:** 7 authored steps, **6 unique frames** — notice → lean into pet → eyes-closed squish → two-position tail wag → settle.
- **Kisses:** 5 authored steps, **5 unique frames** — notice → small heart → larger heart → happy wag → settle.

This is intentionally more expressive without becoming rapid/spastic.

## Offline verification

- All v3 sprite/animation files validate in Pixel Animation Lab.
- Active v3 animations: zero quality warnings.
- Current Runtime 012 policy hash map: 42 exact runtime/code/asset hashes.
- Runtime 012 committed template is unauthorized with the expected three authority blockers.
- Historical Runtime 011/v2 tests explicitly target v2 and remain PASS.
- The three broad current-template assumptions that caused the first Runtime 011 cutover rollback now explicitly treat Runtime 012 as current and Runtime 011 as historical.
- Canonical successor suite: **100/100 PASS**.
- `scripts/cutover_runtime_012.sh`: shell syntax PASS; rollback target Runtime 011.

## Authority boundary

Do not perform Runtime 012 device I/O without exact fresh grant:

`Grant OPENDITOO-PRODUCT-RUNTIME-012`

The committed policy remains unauthorized. A grant authorizes only the frozen Runtime 012 scope described in `product/OPENDITOO-PRODUCT-RUNTIME-012.json`.

After grant, from normal local WSL, run from the v3 worktree:

```bash
bash scripts/cutover_runtime_012.sh "Grant OPENDITOO-PRODUCT-RUNTIME-012"
```

## Minimal physical acceptance

Keep this short. After a clean `R012_CUTOVER_PASS`:

1. Page to Moss and judge idle anatomy/depth first.
2. Run Dance once; confirm it is clearly more interesting while Moss stays recognizable throughout.
3. Run Pet once; confirm lean/squish/tail-wag reads cleanly.
4. Run Kisses once only if the first two are good.
5. Stop. Do not repeat broad product acceptance unless a systems symptom appears; Runtime 012 changes art/choreography only.
