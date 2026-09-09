# OpenDitoo M7 — control inventory and operator capture worksheet — 2026-09-09

Prepared offline. **This worksheet is not transmission authority.** Every trial below
is stock operation through the official Divoom app or plain manual use — no custom
packets, no custom receive session, no boot combinations. M7.4's custom-owner receive
test (K8) needs its own manifest and explicit session authority and is deliberately
not runnable from this document.

One controller owns the Ditoo at a time. Before any trial the OpenDitoo Host must be
idle (`python3 cli/openditoo.py status` → `diagnostics.operationInProgress: false`).

## M7.1 Control inventory

Position-based IDs, assigned left→right, back row→front row as seen by a user facing
the device with the screen upright. Symbols are read from the exact-model FCC external
photos (`artifacts/fcc/5058743_external_photos.pdf`, page with the open-keyboard
three-quarter view) — they are photo-derived, not firmware-derived, and the operator
must confirm them against the purchased unit before any trial is recorded as exact.

| ID | Position | Visible symbol / colour | Notes |
| --- | --- | --- | --- |
| `K-B1` | back row, left | `m` — pink keycap, the only non-green key | Manual: hold = keyboard backlight toggle. Family evidence associates M with the boot-time test-mode selector; **never press at power-on.** |
| `K-B2` | back row, centre | `+` | plausibly volume/brightness up — unproven |
| `K-B3` | back row, right | sun / brightness glyph | unproven |
| `K-F1` | front row, left | left-pointing arrow | plausibly back/previous — unproven |
| `K-F2` | front row, centre | `−` | plausibly volume/brightness down — unproven |
| `K-F3` | front row, right | wave / tilde-like glyph (low confidence from photo) | **operator must confirm the printed symbol** |
| `J-R1` | right of the keyboard well | copper joystick/lever | throw directions and whether it clicks are unconfirmed |
| `P-S1` | right side panel, between microSD and USB-C | round `ON/OFF` button | Manual: press = battery status; **double press = disconnects Bluetooth**; hold = power state change |

Confirm or correct this table first. If a symbol cannot be established, add one front
and one top photo of the purchased unit rather than guessing a label.

### Known manual side effects — distinguish, do not invoke as gestures

- `P-S1` short press → battery display (changes the stock page under observation)
- `P-S1` double press → **disconnects Bluetooth**; this destroys the capture context
- `P-S1` hold → power state change
- `K-B1` hold → keyboard backlight toggle

Excluded from the whole sweep: any power-on key combination, `P-S1` double press,
test mode, MassBoot, USB vendor paths, teardown, and pressing more than one control at
once except in the single justified `K7` pair.

## M7.2 Capture procedure

### Decided capture method: Android HCI snoop

Trials `B0`-`K7` are captured with the **Android HCI snoop log**, the method already
proven twice on this exact unit (`captures/OPENDITOO-DAY1-STOCK-RFCOMM-2026-09-08.json`
and `captures/OPENDITOO-DAY1-PIXEL-COLORING-2026-09-08.json`).

Reasons, not preference:

- These trials require the **official Divoom app to be the controller**, because a key
  event that only exists as an app-visible report would be invisible under any other
  owner. The phone is the controller, so the phone is where the link is observable.
- It is the only capture layer here that sees both directions of the RFCOMM link
  without changing who owns the device.
- It is already proven on this unit with a hash-recorded provenance workflow, so a
  negative result stays attributable instead of being blamed on new tooling.

Windows/WSL capture was considered and rejected for these trials. Windows has no
low-friction equivalent: it needs Bluetooth ETW tracing plus `btetlparse` from the WDK
to convert ETL into btsnoop, and it would still only observe a link the **Windows Host**
owns — which is the one case where a sniffer is unnecessary, because our own Host can
log its receive path directly (see `K8` below). Extra tooling that answers no extra
question is not worth its failure modes.

### `K8` needs no sniffer

`K8` runs with the OpenDitoo Host as the controller. Instrument the Host's own RX path
rather than capturing the link. That is simpler, exactly attributable, and keeps one
owner. It still requires the M7.4 manifest and explicit authority before it runs.

### Raw capture handling — read before capturing

An Android HCI snoop log records **all** Bluetooth on the phone: other devices, audio,
notifications, and app payloads that may contain account metadata. A prior capture
already contained one official-app frame with account/application metadata, retained
only as a SHA-256.

Therefore:

- Keep the raw bugreport and `btsnoop_hci.log` **private and immutable**; they are never
  committed. Record their SHA-256 only.
- Commit only filtered, reviewed derivatives.
- Before capturing, disconnect other Bluetooth devices from the phone and stop audio
  playback, so the trial window is mostly Ditoo traffic.

### Per trial, record before anything else

`trial id | UTC start | stock page shown | app screen | audio state (idle/playing/profile) | firmware v42012 | controller (Android app / none) | connection identity`

Hashes are **not** recorded by hand: `capture-parse` takes the bugreport `.zip`
directly and emits both the archive SHA-256 and the inner `btsnoop_hci.log` SHA-256 in
its `provenance` block.

```sh
python3 cli/openditoo.py capture-parse \
  --capture ~/Downloads/bugreport-<device>-<build>-<timestamp>.zip \
  --output captures/private/trial-K1.json
```

Payloads stay withheld unless a command id is named with `--reveal 58` and similar.
Note that a bugreport also contains `btsnoop_hci.log.last`, the previous rotation; if a
trial window falls before a rotation, re-run with
`--zip-entry FS/data/misc/bluetooth/logs/btsnoop_hci.log.last`. The command lists the
other available entries in its `provenance` block so a rotation is visible rather than
silently missed.

Then run the block, and record the filtered TX/RX with direction/profile/channel, the
before/after stock state, and any gap in the capture.

Bracket every action block with a `B0` baseline, and restore stock state between
trials - restoration traffic is excluded from the trial window.

## M7.3 Classification (offline, after capture)

Classify each observation as exactly one of:

`raw_key_event` · `absolute_state_report` · `app_originated_reaction` ·
`unrelated_telemetry` · `no_event_observed` · `invalid_observation_window`

Preserve unknown payloads verbatim. Rules that must hold in the written result:

- `no_event_observed` is **not** proof of internal-only handling — report the tested
  context, duration, capture completeness and which profiles were actually observed.
- No visible page change is **not** proof of no side effect.
- If channel 1 is silent, inspect other already-captured profiles before concluding
  anything. Do **not** start BLE/HID discovery or invent an endpoint; a new protocol
  path is a separately scoped investigation.
- Never synthesise a press/release pair out of an absolute state report.

## M7.4 Receive-window gate (not yet authorized)

The image transaction closes its socket and must stay that way. A custom-owner receive
test needs a manifest fixing: target + firmware evidence, RFCOMM channel 1, exactly one
connection, a wall-clock duration ceiling, application TX budget **0**, an RX byte
ceiling, single controller, stop conditions, and no automatic reconnect. Receive-only
is still active transport behaviour.

If it ever runs, one owner parses the stream and routes frames by demonstrated
semantics — input observation must never consume an ACK belonging to a display
transaction.

## M7.5 What a positive result would buy

One reliably distinguishable event is enough to ship: it drives the M9 page cycle
`Summary → OptiPlex MCP → OptiPlex Lab → WSL MCP → Summary` and nothing else. Back /
select / home are added only when reliably distinguishable. No key is mapped to log
deletion, service restarts, shell execution or approvals in v1. If keys prove
disruptive or silent, M9 keeps local navigation and the limitation is documented — a
negative M7 does not block the product.

## Exit criteria tracking

| ID | Tested | Context | Event result | Side effects | Classification |
| --- | --- | --- | --- | --- | --- |
| `K-B1` | no | | | | |
| `K-B2` | no | | | | |
| `K-B3` | no | | | | |
| `K-F1` | no | | | | |
| `K-F2` | no | | | | |
| `K-F3` | no | | | | |
| `J-R1` | no | | | | |
| `P-S1` | no | manual-documented only | | battery / BT disconnect / power | not a candidate input |
