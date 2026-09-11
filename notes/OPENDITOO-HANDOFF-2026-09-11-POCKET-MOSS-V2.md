# OpenDitoo handoff — Pocket Moss v2 readability successor — 2026-09-11

## Executive state

**Runtime 010 is live and functioning.** Its transport/page/modal-action implementation is accepted as working, but the owner rejected the physical v1 Moss artwork as a brown blob / not discernibly an animal.

A visual-only successor is prepared offline as **Runtime 011** (`runtime_revision=6`) on `feat/pocket-moss-v2-art`. It is intentionally unauthorized. No Runtime 011 device I/O has occurred.

Runtime 011 preserves Runtime 010's exact Ditoo target `11:75:58:CE:DE:C7`, firmware `v42012`, Host `3faf520f...`, one `streaming_ack_clock` session, ButtonProbe, page order, Moss selector/action behavior, pacing, reconnect/reclaim behavior and webcam 006 policy. The only product change is the hash-bound Moss v2 visual source plus the MossPage asset root.

## Read next

1. `notes/OPENDITOO-POCKET-MOSS-V2-ART-REVIEW-2026-09-11.md`
2. `notes/OPENDITOO-POCKET-MOSS-IMPLEMENTATION-PLAN-2026-09-11.md`
3. `notes/OPENDITOO-PIXEL-ANIMATION-LAB-PLAN-2026-09-11.md`
4. `AGENTS.md`

## v2 art result

`assets/pocket_moss/v2/` is a complete replacement vocabulary, not a one-frame patch. The promoted dog uses hanging dark-brown ears, bright tan fur, a large cream muzzle/chest, two black eyes, black nose and a small pink tongue. This direction was chosen only after several exact-pixel offline candidates were rejected and after programmatic nearest-neighbor + LED-dot/bloom review.

All active animations are warning-free. A new regression suite (`tests/test_moss_v2_art.py`) pins the high-salience dog cues and palette visibility so future edits cannot silently drift back toward the low-contrast v1 failure.

## Runtime 011 files

- `host/product_runtime_v5.py`
- `product/OPENDITOO-PRODUCT-RUNTIME-011.json`
- `scripts/cutover_runtime_011.sh`
- `tests/test_product_runtime_v5.py`
- `tests/test_moss_v2_art.py`
- `assets/pocket_moss/v2/**`

Policy state is deliberately unauthorized with blockers:

- `PRODUCT_AUTHORITY_MISSING`
- `PRODUCT_AUTHORITY_UNATTRIBUTED`
- `PRODUCT_AUTHORITY_SCOPE_MISMATCH`

Exact required grant: `Grant OPENDITOO-PRODUCT-RUNTIME-011`.

## Verification

Canonical successor gate:

`python3 scripts/verify_interactive_pages_offline.py`

Result: **91/91 PASS**, including `POCKET_MOSS_V2_ART_OFFLINE=PASS` and `RUNTIME_011_SUCCESSOR_OFFLINE=PASS`.

Runtime 011 has 36 exact code/asset hashes and hash parity is PASS. Cutover shell syntax is PASS. The v5 synthetic full-product test still proves Dashboard -> Slots -> Moss -> selector -> Dance -> selector in one Host session with zero reconnect/reclaim.

The 326-test historical `verify_day1_offline.py` is not authoritative from the linked worktree because numerous historical tests resolve git-ignored one-use claim/evidence files relative to the checkout. The real cutover script runs that broad gate in primary `main` after fast-forward and before restarting the service, where the normal local evidence/claim state and `/mnt/c` artifacts are available.

## Next action

Do not alter live Runtime 010 or transmit v2 without the fresh Runtime 011 grant.

After the owner grants Runtime 011, run `scripts/cutover_runtime_011.sh` from normal local WSL. The first physical acceptance is intentionally only: Dashboard/Slots -> Moss, then answer one question: **does idle Moss immediately read as a dog?** If not, stop and return to the Pixel Lab. Only after idle passes should Pet/Dance/Kisses be sampled.
