# Frame-rate findings from OpenDitoo — shared with OpenTivoo

Date: 2026-09-09. **Outbound artifact — written to be carried out of this repository.**
Contains no device address, credential, host address or local path.

OpenDitoo is a preservation-first reverse-engineering project for a single purchased
Divoom **Ditoo Plus** (firmware v42012), driving it over Bluetooth serial from Windows.
It is a sibling effort to OpenTivoo, not a fork of it, and it deliberately inherits no
command semantics from it.

Over one session we took sustained frame rate from **0.90 fps to 18.46 fps** on that unit.
This note exists because one part of how we did it is very likely to apply to OpenTivoo
too — and because most of the rest of it is **not** transferable, which matters just as
much.

---

## Read this first: what transfers and what does not

**Does not transfer:** every absolute number below. They were measured on one Ditoo Plus
on one firmware over one Windows Bluetooth stack. Tivoo is different hardware with
different firmware, and its RGB222 palette makes its frames a different size from Ditoo's
RGB888 ones — a 255-colour Tivoo frame is likely several hundred bytes *smaller*. Please
do not adopt "18 fps" or "54 ms" as targets. Measure your own unit.

**Does transfer:** one measurement bug, one method, and one hypothesis to test.

---

## 1. The bug worth checking today

**Your ACK latency measurement may be silently including your own inter-packet delays.**

Our transport sent each frame as three packets with a deliberate 40 ms sleep between
them, then waited for one acknowledgement. It timed the acknowledgement as:

```
ackLatency = timeAckArrived - timeFrameStarted
```

That window **contains the two 40 ms sleeps**. For the entire life of the project we
recorded "~105 ms ACK latency" and believed it was how long the device took to answer.
It was 80 ms of our own sleeping plus roughly 25 ms of device.

The consequence was not academic. We reasoned that 10 fps — 100 ms per frame — was
unreachable "because it is below the ACK latency alone", and concluded that getting there
would require abandoning per-frame acknowledgement and pipelining instead. **That
conclusion was wrong, and it was wrong because it compared against a number that was
mostly us.** Once measured properly the device answers in about 27 ms, and 10 fps was
never the hard part.

If OpenTivoo times its acknowledgements across a window that includes any deliberate
delay, it has the same blind spot. This is a minutes-long check and it may be worth
several times your current rate.

## 2. The method

Nothing clever, but it worked and it is cheap:

1. Measure the achieved inter-frame interval over N frames.
2. Subtract every wait **you** added — inter-frame delay, inter-packet spacing.
3. What remains is the device plus your loop. That residual is the only real constraint.
4. Remove your waits one at a time, re-measuring after each, so a regression is
   attributable to the change that caused it.
5. Confirm each step **visually**, not just by acknowledgement. A valid ACK does not mean
   a correct image.

The residual barely moved as we accelerated: 114 ms, 122 ms, 125 ms as the delay went
1000 → 250 → 50 ms. That flatness was the signal that the delay was almost pure
self-imposed overhead, and it is what justified continuing.

## 3. The hypothesis worth testing (not a finding for you)

The stock Divoom app was observed leaving **40 ms between the three packets of one
frame**. That was the only timing value in our project taken from observed stock
behaviour rather than chosen by us, so we treated it as the one most likely to encode a
real device requirement.

On our Ditoo Plus it did not. We reduced it to 10 ms, then to 0 ms, and saw ten and then
a thousand frames render correctly with no malformed or missing acknowledgements.

**This is a hypothesis for Tivoo, not a result.** If the gap does matter on your hardware,
the symptom we watched for was a corrupt or partial image *with a perfectly valid
acknowledgement* — the one failure mode the transport cannot detect on its own.

---

## Context: what we measured, on our unit only

| Change | Interval | Rate |
| --- | --- | --- |
| Starting point (conservative 1000 ms delay) | 1114 ms | 0.90 fps |
| Delay 250 ms | 372 ms | 2.71 fps |
| Delay 50 ms | 175 ms | 5.70 fps |
| Inter-packet spacing 40 → 10 ms | 109 ms | 9.15 fps |
| Full-colour frames (71 → 1054 bytes) | 118 ms | 8.46 fps |
| Sustained, 512 frames over 67 s | 131 ms | 7.63 fps |
| All waits removed, 1024 frames over 56 s | **54 ms** | **18.46 fps** |

Four observations that may be worth testing on Tivoo:

- **Frame size was nearly free.** Raising frames 14.8× — from two colours to a full
  255-colour palette — cost 8.9 ms per frame. Marginal throughput worked out around
  107 KB/s, so at 16×16 even a maximum-palette frame was not the constraint. Our own
  pacing always was.
- **Short bursts overstate the sustainable rate by about 11 %.** Ten frames gave 118 ms;
  512 frames at identical settings gave 131 ms. Every rate figure we had before we ran a
  long test was mildly optimistic. Qualify with a run of at least a minute.
- **No degradation at zero idle.** 1024 frames with no gap between them held quarter
  means of 54.1 / 54.1 / 54.1 / 54.4 ms and flat acknowledgement latency.
- **But the device *is* modestly slower without idle time.** Its own turnaround rose from
  about 44 ms to 53 ms when denied any gap — roughly 20 %. Real, and far cheaper than the
  70 ms of waiting we removed, but the stock app's breathing room is doing *something*.
  We did not separate device behaviour from Windows Bluetooth stack behaviour here.

## What we did not establish

Stated plainly so nothing here is over-read:

- Anything beyond about one minute of continuous streaming. Ten minutes is a different
  question and we have not asked it.
- Any thermal measurement. "The operator did not report unusual warmth" is not data.
- Whether 18.46 fps is a device limit or a Windows Bluetooth stack limit. At that point
  the interval *is* the acknowledgement round trip, so the two are not separated.
- Anything about delta or partial-frame updates. Every frame we send is a full frame. A
  cheaper update command may exist in the protocol, but searching for one means
  enumerating commands, which this project prohibits.
- Anything about Tivoo. We hold no Tivoo evidence and make no claim about it.

## How this was recorded, if the format is useful

Each step above is a frozen experiment manifest committed before it ran, carrying its
objective, the single variable being changed, a numeric prediction, derived packet/byte/
time budgets, explicit stop conditions, and an authority block that must name an operator
grant. After execution the same file carries the measured result, findings tagged with a
confidence level, and an explicit "not claimed" list.

The habit that paid off most was writing the **prediction and what would falsify it**
before each run. It turned "did it work" into "was the model right", which is what caught
the acknowledgement-timing bug in section 1.

Every experiment here was individually authorized, bounded, supervised and consumed on
execution. None could be re-run without a new manifest and a new grant.
