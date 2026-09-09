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

Per trial record, before anything else:

`trial id | UTC start | stock page shown | app screen | audio state (idle/playing/profile) | firmware v42012 | controller (Android app / none) | connection identity | capture tool + raw file SHA-256`

Then run the block, and record the raw capture, the filtered TX/RX with
direction/profile/channel, the before/after stock state, and any gap in the capture.
Raw captures stay private and immutable under the repository's ignored capture paths;
commit only sanitized derivatives plus provenance.

Bracket every action block with a `B0` baseline, and restore stock state between
trials — restoration traffic is excluded from the trial window.

| Trial | Action | Record |
| --- | --- | --- |
| `B0` | 10 s, no action | background telemetry, spontaneous state changes |
| `K1` | one short press/release of a single non-power control | display / audio / lighting / app / Bluetooth change, and any RX frame |
| `K2` | the same press in three isolated windows | same code and same side effect each time? |
| `K3` | the same control in one other stock context | identical or context-dependent |
| `K4` | one short press of a control that appeared inert in `K1` | any non-display effect or remote event |
| `K5` | one bounded hold/release on a key already characterised by short press | press vs release distinction, repeat cadence, long-press event |
| `K6` | two separated presses, then a shorter measured gap | two events, coalescing, duplicates or a lost action → sets the debounce floor |
| `K7` | one justified pair, pressed while normally running | chord, suppression, priority, or two separate events |
| `K8` | **gated** — a proven short press during an authorized custom-owner receive window | does the event survive without the official app |

Choose hold duration for `K5` from the manual's own behaviour; do not hold controls
whose hold effect is unknown.

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
