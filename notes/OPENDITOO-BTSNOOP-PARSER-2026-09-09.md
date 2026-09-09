# OpenDitoo btsnoop capture parser — 2026-09-09

`host/btsnoop.py` plus `openditoo capture-parse`. Offline only: it reads a local file
and reaches no device. Built to remove the hand-parsing step that stood between an M7
capture and a classified result.

## Why it exists

The two prior captures were parsed ad hoc. M7 needs eight or more trials, each needing
the same filtering, so the parse is the bottleneck rather than the capture.

## What it does

`btsnoop record stream → HCI → ACL reassembly → L2CAP → serial-port channel → Ditoo
application frames`, reusing the existing `CandidateStreamDecoder` for application
framing so error preservation and resync behaviour are shared with the rest of the
project rather than reimplemented.

Attribution is enforced at the front: ACL handles are bound to peer addresses from
`HCI Connection Complete`, and a `--peer-bdaddr` filter drops every other device's
traffic before anything is decoded. Frame check sequences are validated, and failures
are counted and reported rather than silently dropped.

## Privacy

A snoop log holds the whole phone's Bluetooth traffic, and a prior capture contained an
official-app frame with account metadata. So **payload bytes are withheld by default**:
frames are summarized by command id, direction, wire length and SHA-256. A caller must
name command ids explicitly with `--reveal` to see bytes in the clear. A test asserts a
withheld payload does not appear anywhere in the summary.

Raw bugreports and snoop logs are now covered by `.gitignore` (`bugreport-*.zip`,
`*btsnoop*`) in addition to `captures/private/`. They were never committed — verified
against the full history, not just the working tree.

## Two bugs found by real data, both now regression-tested

Synthetic frames would not have caught either:

1. **Reused L2CAP signalling identifiers.** Matching a connection response on its
   identifier alone adopted *other* PSMs' channels (AVDTP, AVCTP) as serial-port
   channels and mis-framed their data into phantom application frames. A response is
   now matched only to a pending PSM-3 request travelling the opposite direction.
2. **Recycled CIDs.** An L2CAP CID is reassigned to another PSM once its channel
   closes. Treating a stale CID as the serial-port channel mis-framed unrelated later
   traffic. Channel membership is now time-varying, tracked in one chronological pass
   from connection response to disconnection.

Combined effect on the real Pixel Coloring capture: frame-check failures fell from
**120 to 2**, and 14 phantom channel numbers disappeared.

Both bugs produced *plausible-looking* extra frames. In M7 that is exactly the failure
that would invent a key event that never happened.

## Validation against frozen evidence

Run against the two exact captures the existing evidence was derived from (hashes
verified against `captures/OPENDITOO-DAY1-STOCK-RFCOMM-2026-09-08.json` and
`captures/OPENDITOO-DAY1-PIXEL-COLORING-2026-09-08.json`):

- Capture 1 reproduces the recorded transport exactly: ACL handle `0x000B` bound to the
  exact unit, L2CAP CIDs `0x0041`/`0x0044`, application DLCI 2, zero decoder errors.
- Capture 2 reproduces **all six** frozen stock drawing-pad frames byte-for-byte, plus
  both stock image preambles and the M4 file-version query.
- `count/length` self-consistency holds across every `0x58` frame, matching the frozen
  `count_length_mismatches: 0`.

These checks live in `BtsnoopAgainstFrozenEvidenceTests` and **skip automatically** when
the private captures are absent, so a clean checkout still verifies green.

## Unresolved discrepancy — recorded, not silently corrected

The parser finds **107** `0x58` frames in capture 2. The frozen
`captures/OPENDITOO-DAY1-PIXEL-COLORING-2026-09-08.json` records
`observed_0x58_frames: 106`. Everything else about that record reproduces exactly,
including `max_observed_count: 12` and `count_length_mismatches: 0`.

Also noted: only **11** of the 107 fall inside that file's recorded
`pixel_coloring_window` (01:34:02-01:34:24 UTC). The remaining 96 belong to earlier
freehand drawing sessions at 01:28 and 01:30 — and five of the six frozen "exact stock"
example frames come from the 01:30 session, not the recorded window. So the frozen
counting window and the frozen example frames were not drawn from the same span.

Three duplicate wire hashes appear twice each, which is a plausible but unproven
explanation for an off-by-one in a manual count.

The frozen record is left unchanged. The discrepancy is one frame in a statistic, it
changes no conclusion drawn from that capture, and the drawing-pad semantics are
independently confirmed by the six reproduced frames. Resolving it is not worth a
speculative edit to frozen evidence.
