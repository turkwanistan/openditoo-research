# OpenDitoo cross-project high-FPS lessons — adopted decisions

Source reviewed: cross-project OpenTivoo note describing its progression from ~6–10 fps product playback to a physically proven manifest-bound 30 fps source-selection + RFCOMM path. This file records only the decisions adopted for OpenDitoo; the OpenTivoo numerical ceiling is **not** treated as Ditoo evidence.

## Already present in OpenDitoo

- separate camera acquisition, transform and transport ownership;
- capacity-one newest-frame slots instead of a latency-building queue;
- one long-lived typed Host/RFCOMM owner;
- no automatic reconnect/catch-up behavior in bounded webcam trials;
- exact-unit Ditoo rate evidence through R5 (~18.46 fps for the synchronous one-ACK-per-frame shape);
- live source-age, replacement, duplicate and queue-depth telemetry;
- transform cost far below the Ditoo transport cycle, so prerecorded preconversion is not needed for the live webcam path.

## Adopted after W8

### W9A — source identity + motion truth

Add a monotonic capture/source sequence ID and preserve it through transform and sender-selection telemetry. Add a deterministic monitor stimulus with temporal markers/frame counters that remain decodable after 16×16 conversion. Use it to distinguish source duplication, scheduler skipping/replacement and later visible repeats.

### W9B — unique-frame + optical latency

Film the source stimulus and Ditoo together. Measure scene→visible latency and visible unique/repeated transitions independently of ACK/transport timing. Do not claim transport FPS equals panel FPS.

### W10 — fixed-rate absolute-deadline scheduler

For product fixed-rate modes, use a monotonic absolute-deadline timeline instead of sleeping one interval after each completed frame. Skip missed logical slots without catch-up bursts. Duplicate/no-new-frame selections do not advance the actual last-transmit/send-floor timestamp. Keep near-ceiling ACK-clock behavior as a separate accepted policy.

## Explicitly not adopted

- no 30 fps Ditoo target merely because Tivoo proved 30 fps;
- no reuse of Tivoo's 54/56 fps transport bracket;
- no new Ditoo rate ladder before current W8 closes;
- no pipelining/batching/delta-protocol work in W8-W10;
- no prerecorded-frame-bundle abstraction for the live webcam.

Any work beyond the existing one-ACK-per-frame ceiling is a deferred post-v1 research track and requires W9B evidence of visible benefit, a separate plan, and fresh authority boundaries.
