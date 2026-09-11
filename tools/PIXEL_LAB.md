# OpenDitoo Pixel Animation Lab

Use `tools/pixel_lab.py` as the default offline author/review loop for literal 16×16 art. The source of truth is palette-indexed JSON (`openditoo.pixel-sprite.v1` and `openditoo.pixel-animation.v1`); PNG/HTML outputs are derived review artifacts.

Typical loop:

```bash
python3 tools/pixel_lab.py validate assets/pocket_moss/animations/idle.json
python3 tools/pixel_lab.py review-bundle assets/pocket_moss/animations/idle.json --profile measured16
python3 tools/pixel_lab.py compare assets/pocket_moss/sprites/candidate-a.json assets/pocket_moss/sprites/candidate-b.json
```

A future ChatGPT session should read `frames.json` and `quality.json` from the generated review directory, reconstruct the literal rows/palette if useful, critique silhouette/timing/continuity itself, revise the authored JSON, and rerun the bundle before asking the owner for visual review. Do not treat a browser preview as proof of physical panel refresh or appearance.

Cadence profiles are transport/ACK-opportunity simulations only. Authored animation timing is `hold_acks`; elapsed milliseconds are derived review telemetry. A long simulated stall never causes a catch-up burst.
