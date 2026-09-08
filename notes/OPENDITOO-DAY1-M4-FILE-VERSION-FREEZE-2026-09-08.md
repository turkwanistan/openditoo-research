# OpenDitoo Day-1 M4 file-version semantic freeze — 2026-09-08

## Decision

Freeze the first custom OpenDitoo operation as the exact stock-observed, read-only firmware file-version query on the purchased Ditoo Plus.

No custom transmission is authorized by this document.

## Exact-unit evidence

Purchased unit:

- label: `Ditoo-plus`, FCC `A8I-DITOO-PLUS`
- stock Bluetooth identity: `Ditoo-Plus-audio`
- address: `11:75:58:CE:DE:C7`
- measured control route: Classic BR/EDR -> L2CAP PSM `0x0003` -> RFCOMM -> SDP `Serial Port 1` -> server channel 1
- exact current stock app: `com.divoom.Divoom` 3.8.34 / versionCode 634 on Android 16

The stock app emitted exactly one request of interest during initialization:

- TX `01040097009b0002`
- TX SHA-256 `6260dc0995cdaa13dadd614eb7f25b5b9ecf4c8a555f6da96bc84c62b5c31780`
- normal-frame decode: command `0x97`, payload `00`

The exact unit replied:

- RX `010900049755001ca400b90102`
- RX SHA-256 `d312a0a59165ca6c65aaa156465b3d3ad84acc4af7ef70bfc75a7338de800cc0`
- wrapped decode: outer `0x04`, inner `0x97`, tag `0x55`, payload `00 1c a4 00`

The payload begins with the same file selector `00`; the next two bytes are little-endian `0xa41c` = **42012**. The final `00` is retained as observed but is not assigned a meaning here.

## Semantic evidence

Evidence is intentionally layered:

1. **Exact purchased-unit stock traffic:** the installed official app emitted `0x97 00` during normal connection initialization and the unit returned a deterministic four-byte payload.
2. **Recent official-app reverse engineering:** independent decompilation of Divoom's Android application maps command `0x97` to `SPP_GET_FILE_VERSION`. Source: `https://tangled.org/antiali.as/minitoo-forth/commit/10542d4bcdcd550d34c17deea3c9d3fa67d946b4` (accessed 2026-09-08).
3. **Version-family consistency:** OpenDitoo already preserves Ditoo Plus 42xxx evidence for historical v42010 and current reference v42016. The exact-unit decoded value 42012 lies in that same product-flag lineage.

Verdict: **high-confidence exact-unit installed version = v42012**. This identifies the version number, not a byte-for-byte installed firmware image; no v42012 binary is currently preserved.

## Frozen M4

The only proposed custom application bytes are:

`01040097009b0002`

One RFCOMM connection attempt, one application send, one complete response, no retry, then local close.

Expected response geometry:

`01 | lenLE | 04 | 97 | 55 | 00 | versionLE16 | trailing-byte | checksumLE | 02`

The observed response is `010900049755001ca400b90102` and decodes to version 42012.

Budgets are frozen in `experiments/DAY1-M4-QUERY-PENDING.json`: 1 connection attempt, 15 s connect deadline, 1 request, 5 s response deadline, 20 s total, 8 TX bytes max, 13 RX bytes max. Any timeout, ambiguous send, malformed response, wrong command/tag, trailing bytes, or unexpected state closes locally with **no resend**.

## Persistence / safety verdict

This operation is a read-only version query. The exact same bytes were already emitted by the official stock app during normal initialization. It does not request firmware update, upload, drawing mode, persistent storage, service mode, or any state change.

The manifest remains `transmission_authorized=false`. Explicit user authority for this exact frozen operation is the final physical gate.
