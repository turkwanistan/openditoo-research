# OpenDitoo Day-1 static application-protocol leads — 2026-09-08

Scope: narrow offline triage of the two preserved exact-model-associated Ditoo Plus reference firmware branches. This is not purchased-unit transport proof and assigns no command IDs.

## Reproducible string evidence

Both:

- `artifacts/firmware/flag60_v60014.bin`
- `artifacts/firmware/flag42_v42016.bin`

contain the same relevant strings at the same file offsets:

| File offset | String |
|---:|---|
| `0x11880` | `SPP_GET_VOLTAGE` |
| `0x118AC` | `SPP_GET_STDB_MODE` |
| `0x12338` | `SPP_GET_TOOL_INFO:%d` |
| `0x12357` | `SPP_GET_DEVICE_INFO:` |
| `0x27458` | `divoom_disp_draw_ctrl_init` |

Additional nearby/application strings in both branches include `SPP_LIGHT_ADJUST_LEVEL`, `SPP_SET_SCENE`, `SPP_GET_ALARM_TIME_EXT2`, `SPP_GET_DIALY_TIME_EXT2`, `SPP_SET_GAME`, `SPP_GET_PLAY_VOICE_STATUS`, and display pixel/color routines.

## Day-1 interpretation

This is exact Ditoo Plus **reference-build** evidence that a named SPP device-information operation and a drawing-control subsystem exist in both preserved branches. It strengthens the Day-1 choice to prefer a stock device-information capture at M2 and to look for a drawing/live-preview stock action before M5.

It does **not** establish:

- that the purchased unit runs either preserved firmware;
- that the official app uses Classic SPP rather than BLE for the target action;
- any command number, payload, response length, wrapper, endpoint or channel;
- that Tivoo `0x80` is Ditoo device-info;
- that Tivoo `0x6F` / `0x58` are Ditoo drawing entry/paint;
- any volatility or flash-write property.

The next promotion gate remains an attributable stock transaction from the purchased unit. Static handler analysis may be used only to resolve ambiguity after that capture.
