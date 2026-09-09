# OpenDitoo 16x16 PNG examples

`openditoo-smile-16.png` is the first product-path fixture for the typed static-image runtime.

Accepted PNG input is intentionally narrow and deterministic:

- exactly 16x16 pixels;
- 8-bit, non-interlaced PNG;
- RGB, RGBA, indexed, grayscale or grayscale+alpha;
- alpha is composited onto black;
- at most 255 distinct RGB888 colors after compositing.

Offline inspection:

```bash
python3 cli/openditoo.py image-prepare --png examples/openditoo-smile-16.png --output-dir .openditoo-local/sample-prepare
```

Live display, after the typed Windows Host has been deployed and Android is not controlling the Ditoo:

```bash
python3 cli/openditoo.py image-show --png examples/openditoo-smile-16.png
```

There is deliberately no target argument and no raw packet/send option. The Host is fixed to the exact Day-1 Ditoo Plus and rebuilds the stock-derived image packet from 768 RGB888 bytes before transmission.
