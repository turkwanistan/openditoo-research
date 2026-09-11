# Pocket Moss v2 art review — 2026-09-11

## Why v2 exists

Runtime 010 proved the complete Pocket Moss transport, page, modal input and action path on the physical Ditoo, but the owner rejected the literal-panel character read: the v1 side-profile dog was "mostly a brown blob" and not discernibly a dog/animal. This is a visual acceptance failure only; Runtime 010 itself is functioning.

Do not "fix" this by adding more brown shading. On the 16x16 panel, the old low-luminance outline (`d=[50,29,19]`) and several adjacent brown masses collapsed perceptually. The v1 direction is preserved as rollback evidence under `assets/pocket_moss/v1/`.

## Iteration method

No image generation was used. The revision was text-authored as literal 16x16 rows, rendered programmatically at exact nearest-neighbor scale, then reviewed again with a simple LED-dot/bloom simulation and with the brown tones collapsed toward one fur color. Several intermediate directions were rejected offline before promotion:

1. brighter seated/front and full-body profiles — cleaner but still generic creature / fox / horse ambiguity;
2. exaggerated side-profile anatomy — readable silhouette, but still too dependent on interpreting the body;
3. face-forward variants with high ears — tended bear/fox;
4. low hanging/floppy ears + cream muzzle + nose + tongue — first direction that remained clearly dog-like after color collapse and LED-dot simulation.

## v2 visual grammar

Promoted source: `assets/pocket_moss/v2/`.

The dog identity now comes from high-salience landmarks rather than subtle shading:

- high-luminance tan fur (`h=[240,145,65]`);
- visible dark-brown hanging ears (`b=[150,80,45]`), not near-black outline pixels;
- two black eye holes embedded inside the tan face;
- large cream muzzle and chest (`c=[255,235,185]`);
- one black nose pixel inside the cream muzzle;
- tiny pink tongue (`p=[255,75,150]`);
- compact seated body subordinate to the face;
- Kisses retains a detached pink heart only during the action, when the selector glyph is hidden.

The idle bbox is 14x14 (`[1,1,14,14]`), has 122 occupied pixels, no edge touches and no one-pixel islands. The face is intentionally large because the physical acceptance criterion is immediate recognition, not anatomical detail.

## Animation review

The entire pose vocabulary was redrawn in the same face language: Idle, Look, Happy, Loaf, Sleep, Wake, Pet Lean, Dance Left, Dance Right and Kiss. The face remains stable while motion is concentrated in eyes/body/pose rather than replacing the character silhouette.

A lab pass caught and fixed two issues before freeze: Sleep initially still had open eyes; Wake was byte-identical to Idle and produced a duplicate-consecutive-frame warning. Final Sleep uses closed eye lines and a compressed resting body; Wake is a distinct one-eye-opening intermediate.

Final active animations (`look`, `loaf`, `sleep-wake`, `pet`, `dance`, `kisses`) all report `warnings=[]` from `host.pixel_animation.animation_quality`.

## Automated readability regression

`tests/test_moss_v2_art.py` pins the cues that matter physically instead of trying to encode an aesthetic score:

- default Moss asset root is v2;
- visible ear/shadow mass exists;
- two eye holes, one nose, tongue and cream muzzle/chest remain present;
- fur/ear palette luminance cannot regress toward the near-black v1 outline;
- idle has no edge touches or one-pixel islands and remains at least 12x12;
- every active v2 animation is warning-free and retains substantial tan + cream face vocabulary.

This does not replace literal-panel owner judgment. It prevents obvious regression between physical reviews.

## Runtime boundary

Runtime 010 remains the accepted live baseline and exact rollback. v2 is frozen only in Runtime 011 (`runtime_revision=6`) on `feat/pocket-moss-v2-art-r2`. Runtime 011 changes no Host DLL, target, ButtonProbe, pacing, session topology, navigation, selector/action semantics, reconnect/reclaim behavior or webcam policy.

Physical v2 acceptance still requires the fresh exact grant:

`Grant OPENDITOO-PRODUCT-RUNTIME-011`

The first live review should be deliberately tiny: page to Moss and judge the idle dog. If the idle is still not immediately dog-readable, stop and iterate offline again before exercising actions.
