# OpenDitoo M7 — comparison against OpenTivoo's input handling — 2026-09-09

Read-only review of `~/Projects/opentivoo-research` at the operator's request. That
repository has active concurrent work; nothing in it was modified.

**Evidence class: 5 — comparative prior art.** Nothing here is promoted to exact-unit
Ditoo truth. It is recorded because it independently corroborates a hypothesis and
supplies architecture, not because a shared command number means a shared meaning.

## Sources reviewed

- `notes/OPENTIVOO-D357-BLUETOOTH-INPUT-MAPPING-RESULT.md`
- `decisions/ADR-0012-prefer-bluetooth-input-observation-before-hardware-instrumentation.md`
- `host/tivoo_input_events.py`

## The convergences are striking

OpenTivoo reached these conclusions on different hardware, by a different route, before
this sweep existed:

| Observation | OpenTivoo (Tivoo) | OpenDitoo (this sweep) |
| --- | --- | --- |
| Frame wrapper | `01 \| len \| 04 \| cmd \| 0x55 \| data \| cksum \| 02` | identical |
| Volume control | wrapped `0x09`, one byte, **absolute volume state** — explicitly *not* a detent count or direction code | wrapped `0x09`, one byte, values `02 → 01 → 02` across volume-down then volume-up |
| Display/page change | wrapped `0x46`, **22-byte** display/state telemetry | wrapped `0x46`, **22-byte** payload, unsolicited after the page changed |
| A plain button press | volume-knob short press and CHANNEL button: **zero** normalized events, no visible change | left arrow, right arrow, joystick: **zero** frames, no visible change |
| Verdict on volume as navigation | rejected — "changes real audio volume" | same conclusion reached independently |

Two independent devices, same wrapper, same command numbers, same shapes, same dead
ends. That is a strong signal about the Divoom application layer as a family.

## What this does and does not settle

My open question was whether the Ditoo `0x09` byte is an **absolute volume level** or a
**key identifier**. OpenTivoo measured 24 `0x09` reports with "ordered one-step value
changes" and concluded absolute state.

That **raises confidence in the level reading; it does not settle it for the Ditoo.**
Family resemblance is exactly what this project's evidence hierarchy refuses to treat
as exact-unit truth, and the argument would be circular: I would be using Tivoo to
resolve a Ditoo question that a single 30-second Ditoo trial resolves directly.

**The four-press minus trial still stands, and is still the thing that settles it.**

Likewise `0x46`. OpenTivoo's own result is emphatic that its `0x46` has **no** proven
CW/CCW identity and that the runtime "must not label the action CW, CCW, previous, or
reverse". So there is no direction semantics available to inherit even if inheriting
were allowed — the thing a careless reading would import does not exist.

## What genuinely transfers: architecture, not semantics

These are device-independent handling disciplines, and reusing them is cheaper than
rediscovering them:

- **Absolute state, then delta, never a synthesised keystroke.** Treat the first sample
  as baseline only; infer a change from a sequential delta in a bounded context; fail
  closed on a large or discontinuous jump. This is exactly the trap my sweep is already
  positioned in front of.
- **Epoch and gap identity.** Events carry a session epoch and sequence so a reconnect
  or a dropped window cannot be silently stitched into a continuous stream.
- **`valid_observation_window`.** Only trials whose window is provably complete are
  accepted; incomplete windows are preserved as invalid rather than quietly used.
- **A canvas-invalidation fence.** This is the most directly useful piece for OpenDitoo.
  OpenTivoo treats a display-state observation as proof that the stock UI took the
  screen and its own canvas is gone.

## The fence matters for M9 right now

The sweep produced a fact that fits this exactly: **the brightness key cleared our
custom frame**, and the device announced it with an unsolicited `0x46`.

Combined with M8's finding that a frame survives indefinitely until stock takes over,
that gives M9 an honest display model with no new protocol semantics at all:

```
our frame is on screen
  → unsolicited 0x46 observed
  → our canvas is no longer ours
  → mark the display state unknown; do not claim the last frame is still shown
```

That is `0x46` used purely as "something took the screen", which is all either project
has evidence for. It needs no direction, no key identity, and no Tivoo meaning.

## Route priority is already right

ADR-0012 chose Bluetooth observation over hardware instrumentation, keeping UART and
service-mode work for controls that cannot be distinguished over Bluetooth. OpenDitoo
is on the same route by default, and this sweep is the same class of evidence, so no
change of direction is warranted.

One difference worth noting: OpenTivoo observed its reports **with its own Host as the
open owner**, not the official app. OpenDitoo's sweep used the official app. That means
a custom owner receiving these frames is proven on Tivoo and merely plausible on Ditoo
— it lowers the risk of the M7.4 receive-window experiment, and it does not replace it.
