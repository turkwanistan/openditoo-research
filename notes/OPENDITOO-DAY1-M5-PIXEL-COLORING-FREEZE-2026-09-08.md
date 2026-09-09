# OpenDitoo Day-1 M5 Pixel Coloring freeze — 2026-09-08

## Decision

The second exact-unit Android HCI capture is sufficient to freeze the first OpenDitoo 16x16 custom-frame trial without inheriting Tivoo drawing semantics.

The planned first custom frame is a single stock-format `0x44` RGB888 palette image, preceded by the exact two-packet image preamble observed from the official Divoom app, followed by local RFCOMM close after one valid wrapped `0x44` acknowledgement. M5 transmission remains unauthorized until explicitly approved.

## Private source boundary

Raw bugreport SHA-256:

`71821bde31fbd7aea82d8c2f83a9a1a505843b86df322d752d57a8c149acfe5e`

Extracted `btsnoop_hci.log` SHA-256:

`b373607316094b0fd529f3354ee379abb6645e89ab0b2c06ce865064428dbc9c`

The whole bugreport remains private and is not committed. Filtered exact-unit drawing evidence is in `captures/OPENDITOO-DAY1-PIXEL-COLORING-2026-09-08.json`.

## Exact-unit `0x58` drawing-pad semantics

The official app emitted 106 command-`0x58` frames in the capture. Every one has payload:

`R G B | count | row-major pixel index[count]`

All 106 satisfy `count == number of following index bytes`; the largest captured count is 12.

The operator's deliberately asymmetric marks resolve the index orientation unambiguously:

- red `FF0000` at indices `00 01` -> `(0,0) (1,0)`;
- green `00FF57` at `0F 1F 2F` -> `(15,0) (15,1) (15,2)`;
- blue `0066FF` at `E1 E0 F1 F0` -> bottom-left 2x2;
- gray `5A5A5A` at `78` -> `(8,7)`;
- white `FFFFFF` at `FF` -> `(15,15)`.

Therefore the exact purchased unit uses `index = y*16 + x` for this drawing-pad path and accepts RGB888 color bytes directly.

Independent Divoom APK reverse engineering names command `0x58` `CMD_DRAWING_PAD_CTRL`; this is supporting semantic evidence only. Exact-unit packet behavior above is primary.

## Exact-unit `0x44` static-image semantics

After brush edits, the official app repeatedly sent full command-`0x44` snapshots. The exact purchased-unit layout is:

`00 0A 0A 04 | AA | frame_size_le16 | F4 01 00 | color_count | RGB888 palette | packed row-major palette indices`

For the observed 6/7-color images, each pixel consumes 3 palette-index bits. Index bits are emitted least-significant-bit first and packed into bytes least-significant-bit first.

This is not a family-only guess: all **8/8** captured Pixel Coloring `0x44` snapshots were decoded to palette + 256 row-major pixel indices and re-encoded byte-for-byte exactly.

This also means OpenTivoo's RGB222 display constraint does **not** transfer to the Ditoo Plus `0x44` path. The stock Ditoo app uses RGB888 palettes.

## Entry semantics

Immediately before the first Pixel Coloring `0x44` snapshot, and repeatedly before later snapshots, the exact stock app emits:

1. `0103009fa20002`
2. `010400bd31f20002`
3. the `0x44` image frame

This exact sequence is frozen as the M5 image-transfer entry/preamble. The deeper meanings of `0x9F` and extended `0xBD/0x31` are not promoted beyond their observed image-transfer role.

Supporting community work on related/current Divoom generations independently identifies `0xBD/0x31` plus `0x9F` as an image preamble and `0x44` as static-image transfer, but exact-unit capture is the authority here.

## Exit semantics

After the final stock `0x44` acknowledgement at `2026-09-09T01:34:24.032817Z`, the Pixel Coloring session contains no separate RFCOMM application command attributable to exit.

Therefore M5 will **not invent an exit command**. The evidence-backed exit is local RFCOMM close after one complete, checksum-valid wrapped `0x44` acknowledgement.

## Persistence boundary

No Save/Publish/Upload action was used for the capture. The Pixel Coloring window contains no firmware-update operation, no `0x8B`/`0x8C` persistent/animation upload, and no separately identified commit operation.

Current classification:

**runtime display path with no observed persistent commit**

Persistence across a full device power cycle remains untested and must not be inferred from this capture. The first custom M5 trial will make no persistence claim beyond the absence of a commit/storage operation in the frozen sequence.

## Frozen diagnostic image

Palette:

1. `000000` black
2. `FF0000` red
3. `00FF00` green
4. `0000FF` blue
5. `FFFFFF` white
6. `5A5A5A` dim gray

Geometry, row-major:

- red: `00 01`
- green: `0F 1F 2F`
- blue: `E0 E1 F0 F1`
- white: `FF`
- gray: `77` = `(7,7)`
- all other pixels: black

Generated `0x44` wire frame is exactly 132 bytes, the same wire size as six-color stock Pixel Coloring snapshots.

SHA-256:

`db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b`

Encoder: `host/ditoo_pixel_coloring.py`.

## Frozen M5 packet sequence

Exactly three application packets on one already-paired RFCOMM channel-1 connection:

1. `0103009fa20002`
2. `010400bd31f20002`
3. the 132-byte diagnostic `0x44` frame frozen in `experiments/DAY1-M5-FRAME-PENDING.json`

Combined application TX bytes: 147.

No retry, no automatic reconnect, no second image. Accept only one checksum-valid response with outer `0x04`, inner `0x44`, tag `0x55`; its one-byte payload may vary because exact stock `0x44` acknowledgements varied there while preserving wrapper/checksum geometry. Then close locally.

M4 authority is consumed and does not transfer. M5 remains `transmission_authorized=false` until explicit approval of this exact sequence.
