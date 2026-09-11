# Pocket Moss autonomous art review — 2026-09-11

## Decision

Pocket Moss v1 uses the revised **A2 side-profile** identity under `assets/pocket_moss/v1/`.

This is an offline visual decision only. Physical Ditoo panel appearance is still pending Runtime 010 owner acceptance.

## Candidate pass

The first lab pass created three materially different idle directions plus look variants:

- **A — side profile:** strongest horizontal quadruped read, but the first draft touched the left edge.
- **B — slight three-quarter/upright:** rejected because the enlarged literal pixels read too blocky/upright and weakened the low canine silhouette.
- **C — compact/chibi:** charming, but the face/cream band read more like a mask and the body was less recognizably Moss-like.

A was revised into **A2** by moving the usable silhouette off the edge while keeping the long low body. A2 became the base identity. The exploratory candidate files were then discarded rather than promoted as product assets.

Final idle objective geometry:

- bbox `[1, 3, 14, 12]`;
- 74 occupied pixels;
- no edge touches;
- no disconnected one-pixel islands;
- six actually-used RGB colors;
- canonical sprite hash `4eb552b2098e23793994a6aae8630a2f40ed25b834bae4c11b0b1936d82e4bba`.

## Pose/animation self-critique cycle

The first authored v1 sheet was reconstructed independently from the exact JSON rows and visually inspected, not judged only from metrics.

### Look

First pass translated too much of the body and touched the left edge. It was revised into a head-led look while the body/feet remain anchored.

Final `look` animation:

- adjacent deltas `17 -> 17` pixels;
- no quality warnings;
- animation hash `9b8276d7088bdccbd25e8794c1528210b2d573291c33be6003961908335ad88c`.

### Dance

First pass moved roughly 70 pixels between alternating frames. Visually it read as whole-dog sliding rather than dancing. The rewrite keeps the torso anchored and uses alternating paw/tail acting.

Final `dance`:

- adjacent deltas `9, 9, 9, 27, 26` pixels;
- no quality warnings;
- animation hash `3c6d979e53addd1947121c216a67039a7d04bc26af965930ff942c787ca1144e`.

### Kisses

First pass put the heart behind/far from Moss. It was moved beside/above the head so it visually originates from the affectionate pose.

Final `kisses`:

- adjacent deltas `23, 32, 26` pixels;
- no quality warnings;
- animation hash `47ffdf13f4ec1cd4f9cccb72227ba5027a8e30a831e2ec02a040f11c2ed5b4a7`.

### Pet selector glyph

The first 3x3 Pet glyph looked like the letter `A` in the actual enlarged selector preview. It was replaced by a paw-like five-pixel arrangement. Dance remains cyan, Kisses pink, Back grey, and only one glyph is visible at once in the reserved top-right 3x3 area.

### Other sequences

- `loaf`: hash `ec5e6d8faae3f0e36860dc400a9124d4e05759f25f3d81311fbf2d39e9914c95`, no animation warnings.
- `sleep-wake`: hash `e77cbe23dc3319df0be81f6db5c1c2457ecc6fb0b5041c3ca401561cd6baf0f6`, no animation warnings.
- `pet`: hash `6ab19a27e7032926f5364b6b89dc8147902f8123fe9646834a88736fb0c5ccb3`, no animation warnings. `pet_lean` intentionally reaches the left edge as the contact/lean pose; it clips no authored pixel and the rest of the vocabulary stays inside the canvas.

## Review bundles

Fresh bundles for Look, Loaf, Sleep/Wake, Pet, Dance and Kisses were generated under:

`.openditoo-local/pixel-lab/reviews/`

Each bundle contains exact `frames.json`, `quality.json`, deterministic cadence metadata/hashes, a contact sheet and standalone `preview.html`. After the first real consumer exposed sandbox-specific provenance paths, the lab was improved so bundle paths are project-relative and portable between WSL_MCP sessions.

## Promotion position

The offline identity and animation set is strong enough for the first physical 16x16 panel acceptance. Do not expand the sprite vocabulary before that UAT; if the literal panel reveals a readability problem, iterate in the lab first.
