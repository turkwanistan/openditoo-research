# Pocket Moss assets

`v1/` is the selected text-authored Pocket Moss visual set for the Runtime 010 successor.

The source of truth is JSON, not PNG/GIF. Every sprite is literal 16x16 palette-indexed geometry and every animation uses authored `hold_acks`. Use the reusable Pixel Animation Lab:

```bash
python3 tools/pixel_lab.py validate assets/pocket_moss/v1/animations/dance.json
python3 tools/pixel_lab.py review-bundle assets/pocket_moss/v1/animations/dance.json --profile measured16 --seed 7
python3 tools/pixel_lab.py serve assets/pocket_moss/v1/animations/dance.json
```

Generated review artifacts belong under `.openditoo-local/pixel-lab/` and are intentionally not committed. Runtime 010 hash-binds every JSON file under `v1/`.

The selected identity is the revised **A2 side-profile direction**: compact horizontal brown-and-cream dog, short legs/muzzle, low center of gravity, and expressive tail/head. The rejected exploratory A/B/C sources were deliberately not retained as product assets; the critique and decision trail is recorded in `notes/OPENDITOO-POCKET-MOSS-ART-REVIEW-2026-09-11.md`.
