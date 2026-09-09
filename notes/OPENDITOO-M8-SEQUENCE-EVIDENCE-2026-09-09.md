# OpenDitoo M8.1 — repeated-frame sequence chosen from evidence — 2026-09-09

M8.1 asks which repeated-frame shape is the least-change supported path: repeated
complete transactions, or a sequence inside one session. That is now answered from the
exact-unit capture rather than assumed, using `openditoo capture-parse` against
`btsnoop b373607316094b0fd529f3354ee379abb6645e89ab0b2c06ce865064428dbc9c`.

## What the official app actually does

Filtered to the exact unit's serial channel, the Pixel Coloring session contains **41
image packets (`0x44`) inside one open session**. The channel is opened once and the
app sends frame after frame without reconnecting between them.

| Measurement | Value |
| --- | --- |
| Image packets | 41 |
| ACKs received | 41 — **none missing** |
| ACK latency | min 30.5 ms, median 45.6 ms, max 160.9 ms |
| Inter-image gap | min 0.148 s, median 1.013 s, max 213.6 s |
| Reconnects between frames | none |
| Image packet wire lengths | 56, 91, 132, 135 bytes |

**Decision: a same-session sequence, not repeated complete transactions.** Repeating a
full connect/disconnect per frame would be a shape the stock app never uses, and would
add a reconnect to every update for no observed benefit.

## Preambles are kept

Each image is preceded by preamble frames. Both orders appear in the capture
(`0x9F -> 0xBD` and `0xBD -> 0x9F`), and one early `0x44` was ACKed with no immediately
preceding preamble at all.

That last observation is **not** treated as licence to drop the preambles. It is a
single unexplained instance, our own proven M5/M6 path always sends
`preamble A -> preamble B -> image`, and removing an entry packet to save 15 bytes is
exactly the kind of unforced deviation from stock the project rules warn against. The
sequence repeats the full three-packet group per frame.

## Pacing derived from the measurement

- Inter-frame delay for the first experiment: **1000 ms**, the stock median gap. Stock
  sustained a 148 ms minimum, so this is about 7x more conservative than demonstrated.
- ACK timeout per frame: the existing 5000 ms budget, about 31x the slowest observed
  stock ACK.

Faster pacing is a separate decision that needs its own authority. The measured stock
floor of 148 ms is an observation about the official app, not a rate this project has
earned.

## Frozen A -> B fixtures

| | Frame A | Frame B |
| --- | --- | --- |
| File | `examples/openditoo-m8-a-topleft-16.png` | `examples/openditoo-m8-b-bottomright-16.png` |
| Content | 3x3 white block, rows 0-2 / cols 0-2 | 3x3 white block, rows 13-15 / cols 13-15 |
| PNG SHA-256 | `36c4361020c65a1f…` | `9924d0f4e620e388…` |
| Packet SHA-256 | `42f6a81e9eb3c821…` | `004dfc38f2acd3aa…` |
| Packet bytes | 56 | 56 |
| Palette colours | 2 | 2 |

Opposite corners are unmistakable at a glance, so the operator can report render order
without measuring anything. Because M6.4 already proved top-left/bottom-right geometry,
a wrong order cannot be explained away as a flip.

Both packets are 56 bytes — the same wire length as the smallest stock `0x44` frames in
the capture, which is a small independent sign the encoder's frame shape matches stock.

## Manifest

`experiments/DAY1-M8-AB-SEQUENCE-PENDING.json` freezes the sequence, budgets (1
connection, 6 application packets, 142 TX bytes, 2 ACKs, 20 s ceiling), expected
observations, persistence analysis, stop conditions and a no-retry / no-reconnect
policy.

`openditoo manifest-check` reports `execution_ready: false` with exactly one blocker,
`transmission_authority_missing`. That is the intended state: **the manifest grants
nothing.**

## Executed 2026-09-09 — M8.3 step 1 PASS

The operator granted authority for `OPENDITOO-M8-AB-SEQUENCE-001` and it ran once.

| | Budget | Actual |
| --- | --- | --- |
| Connections | 1 | 1 |
| Application packets | 6 | 6 |
| TX bytes | 142 | 142 |
| ACKs | 2 | 2 (`0xE5`, `0x33`) |
| Wall clock | <= 20000 ms | 1320 ms |
| Retry / reconnect | none | none |

Operator observation: *"a white box moved from corner to corner."*

**MATCHED:** the exact unit accepts and physically renders two different frames inside
one connection, each with its own ACK and no reconnect. That is the M8 primitive.

Residual detail: the report names movement but not which corner came first, and a
reversed order would look the same. It is settleable for free — frame B (bottom-right)
was sent last, so a display currently resting bottom-right confirms A-then-B. Recorded
as open rather than assumed.

The ACK payloads were `0xE5` and `0x33`, different from each other and from the earlier
`0x12`, `0x75` and `0xF0`. Five distinct payloads across successful sends now; the byte
is not a success constant, and still has no assigned meaning.

Authority is consumed. `sequence-run` on the same manifest now exits 30.

## What is deliberately not built yet

The Host sequence route is now implemented and deployed: `ExchangeSequenceOnce` is the
single transport core and `ExchangeOnce` delegates to it, so `image-show` and the
sequence share one code path and the source still has exactly one connect and one send
call site. Every frame is hash-checked before any device I/O, identical frames are
rejected, and the sequence shares `image-show`'s single-operation gate.

Still not built, and each needs its own manifest and grant:

- **Any loop.** M8.3 step 2 is a short finite loop at a measured rate. A two-frame pass
  is not standing authority for repetition.
- **Any rate above 1000 ms inter-frame.** The 148 ms stock floor remains an observation
  about the official app, not an earned rate.
- **Driving the display from the M9 collector.** M9 stays offline until a rate ceiling
  is accepted.
