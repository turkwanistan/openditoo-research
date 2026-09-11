# OpenDitoo Pocket Moss v3 polish handoff — 2026-09-11

## Physical result that drives this successor

Runtime 011 / Moss v2 was the accepted live baseline immediately before Runtime 012, and the runtime/input path worked normally. Physical panel feedback established two important facts:

- v1 was a visual failure: Moss read as a brown blob rather than a dog.
- v2 fixed the identity problem. Owner feedback after trying the live v2 character/animations: **“yes this looks much better … it’s looking pretty great already.”** Remaining criticism is polish, not recognition: idle is a little derpy/flat/deformed-looking, likely from the 3/4 body anatomy and small palette; animations need to be more interesting.

Do not regress to low-contrast brown-on-brown silhouette art. Preserve the v2 face vocabulary: floppy ears, bright tan face, cream muzzle/chest, black eyes/nose, pink tongue/heart.

## Live acceptance / current baseline

Runtime 012 was granted with exact text `Grant OPENDITOO-PRODUCT-RUNTIME-012` and cut over successfully on 2026-09-11. The live main cutover commit is `5de631e` and the installed policy is `OPENDITOO-PRODUCT-RUNTIME-012` (`runtime_revision=7`). The guarded cutover reported:

- `R012_TEMPLATE_AND_INSTALLED_BINARIES_PASS`
- `R012_MAIN_OFFLINE_PASS`
- `R012_PRODUCT_CHECK_PASS`
- `R012_DASHBOARD_CONNECTED`
- `R012_WEBCAM_006_POLICY_CHECK_PASS`
- `R012_CUTOVER_PASS main=5de631e host=3faf520f46ce rollback=.openditoo-local/rollback-runtime-011`

Physical v3 review is accepted for the current milestone. The owner’s final disposition was **“okay this is good for now.”** Do not keep iterating Moss merely because further pixel polish is possible. Preserve Runtime 012 as the current accepted baseline and treat future Moss changes as optional incremental polish unless the owner explicitly reopens it.

Runtime 011 remains the exact rollback baseline under `.openditoo-local/rollback-runtime-011`.

## Runtime 012 implementation

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

## Authority / rollback state

The exact Runtime 012 grant was consumed for the accepted cutover:

`Grant OPENDITOO-PRODUCT-RUNTIME-012`

The committed template remains unauthorized by design; standing authority exists only in the local mode-0600 policy created by the cutover. The grant covered only the frozen Runtime 012 scope described in `product/OPENDITOO-PRODUCT-RUNTIME-012.json`.

If Runtime 012 must be rolled back, use the guarded helper from normal local WSL:

```bash
bash scripts/cutover_runtime_012.sh --rollback
```

## Physical acceptance completed

The v3 live pass was intentionally short because Runtime 012 changes only art/choreography. Idle and the richer actions were physically reviewed and the owner accepted the result as the current stopping point. No broad transport/product re-acceptance is required unless a systems symptom appears.

For a future session: begin from Runtime 012 as accepted truth. Do **not** reopen the v1/v2 identity problem, redo the transport stack, or repeat broad device testing. If Moss is revisited, prioritize small visual/animation polish while preserving the v2/v3 face vocabulary and Runtime 012 interaction semantics.
