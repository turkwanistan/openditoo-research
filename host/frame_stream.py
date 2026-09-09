"""General bounded 16x16 RGB888 frame streaming.

The device side of streaming already exists and is accepted evidence: the typed Host's
`/v1/session/*` family takes an arbitrary 768-byte RGB888 frame per request, encodes it
with the stock-derived encoder, and enforces lifetime, pacing floor and frame/byte
budgets itself. `activity_session.run_session` already drives that transaction shape
against an injected `render(now_ms)` callable. Nothing here adds a second Bluetooth
stack, a route, or a transport: this module supplies

1. a frozen frame SET (precomputed or generated offline, hashed as one file), and
2. a time-indexed frame source that hands `run_session` the frame for the current
   instant,

so any 16x16 source -- procedural, video-derived, screen-derived -- becomes a reviewed
stream by producing a `.rgb888` file, without touching the MCP dashboard's hash-frozen
renderer or the Windows Host.

`host/activity_session.py` is hash-frozen by the live product policy and is imported,
never modified.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from host import activity_session as _session
from host.ditoo_pixel_coloring import (IMAGE_PREAMBLE_A, IMAGE_PREAMBLE_B,
                                       encode_rgb888_static_image, sha256_hex)
from host.png16 import decode_png16_rgb

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
FRAME_BYTES = 16 * 16 * 3
# The stock-derived encoder carries one palette per frame, so a frame is only sendable
# with at most this many distinct colours. Arbitrary photographic 16x16 content routinely
# exceeds it, which is why quantisation happens offline in prepare, never at send time.
MAX_PALETTE_COLORS = 255
# Why a client may not dispatch AT the Host floor, measured rather than assumed.
#
# OPENDITOO-S2-STREAM-RATE-001 dispatched on a phase-stable 150 ms grid -- exactly
# `ActivitySessionHost.AcceptedMinFrameIntervalMs` -- and died on frame 10 with HTTP 429
# SESSION_PACING_VIOLATION. The Host times the interval on its own clock from when IT
# starts a frame, so a client gap of 149-151 ms can arrive early, and a pacing violation is
# terminal with no retry. The margin must therefore cover HTTP scheduling jitter, and it
# must be paid on every frame, not on average.
#
# 50 ms is the value the MCP dashboard has used across every activation and the whole
# product runtime without a single pacing refusal. Smaller margins are untested, and the
# failure mode is losing the session, so this takes the proven number rather than the
# tightest plausible one.
CLIENT_JITTER_MARGIN_MS = 50
MIN_PLAYBACK_INTERVAL_MS = _session.ACCEPTED_MIN_FRAME_INTERVAL_MS + CLIENT_JITTER_MARGIN_MS

# Session profiles, mirroring `ActivitySessionHost`. These are NAMES; the Host owns the
# constants each resolves to, and confirms in its open response which one it applied.
SESSION_PROFILE_ACTIVITY = "activity"
SESSION_PROFILE_STREAMING = "streaming_ack_clock"
SESSION_PROFILES = (SESSION_PROFILE_ACTIVITY, SESSION_PROFILE_STREAMING)
# Must equal ActivitySessionHost.StreamingMinFrameIntervalMs. A test asserts they agree
# against the C# source, because a client that believes in a lower floor than the Host
# enforces gets a terminal pacing refusal rather than a slow frame.
STREAMING_HOST_FLOOR_MS = 40
# Under an ACK clock the client cannot dispatch early -- it has no permission to send until
# the previous ACK returns -- so the S2 jitter margin is unnecessary, not merely reduced.
STREAMING_MIN_PLAYBACK_INTERVAL_MS = STREAMING_HOST_FLOOR_MS
# Unused by a stream: no frame is a pulse, so nothing can expire. Present because the
# shared manifest record requires it.
_STREAM_PULSE_FRESHNESS_SECONDS = 30
PREAMBLE_BYTES = len(IMAGE_PREAMBLE_A) + len(IMAGE_PREAMBLE_B)
SOURCE_KIND_FRAME_SET = "frame_set"
SOURCE_KIND_LIVE = "live"
SOURCE_KINDS = (SOURCE_KIND_FRAME_SET, SOURCE_KIND_LIVE)


def worst_case_frame_tx_bytes() -> int:
    """Application bytes of the largest frame the encoder can produce, computed not guessed.

    A live source has no frozen frame set to measure, so its byte budget has to come from the
    encoder's own worst case: a full 255-entry palette at 8 bits per pixel, plus both stock
    preambles.
    """
    frame = bytearray(FRAME_BYTES)
    for index in range(256):
        # 255 distinct colours over 256 pixels: the most the encoder will accept.
        value = min(index, MAX_PALETTE_COLORS - 1)
        frame[index * 3:index * 3 + 3] = bytes((value, (value * 7) % 256, (value * 29) % 256))
    wire, palette = encode_rgb888_static_image(quantize_to_palette_limit(bytes(frame))[0])
    assert palette <= MAX_PALETTE_COLORS
    return len(wire) + PREAMBLE_BYTES

SessionError = _session.SessionError
SessionClaim = _session.SessionClaim

# What the stream path actually executes. The MCP renderer/collector hashes are
# deliberately absent: a stream does not run them.
HASHED_MODULES = {
    "frame_stream_sha256": ROOT / "host" / "frame_stream.py",
    "encoder_sha256": ROOT / "host" / "ditoo_pixel_coloring.py",
    "session_sha256": ROOT / "host" / "activity_session.py",
}


def module_hashes() -> dict[str, str]:
    return {name: _session.sha256_file(path) for name, path in HASHED_MODULES.items()}


# --------------------------------------------------------------------------
# Frame sets
# --------------------------------------------------------------------------

def quantize_to_palette_limit(rgb: bytes) -> tuple[bytes, int]:
    """Reduce a 16x16 frame to <=255 distinct colours, deterministically, losing one pixel.

    A 16x16 frame is 256 pixels, so it can never hold more than 256 colours and the cap is
    255: at most ONE merge is ever required, and at exactly 256 colours every colour occurs
    exactly once. So the minimal correct fix is to find the closest pair and repaint the
    single pixel of the second with the first. Nothing else in the frame changes.

    This replaces an earlier whole-frame low-bit reduction, which cost every pixel precision
    (a gradient fell from 256 to 232 colours) to solve a one-pixel problem. Credit: the
    N980P webcam implementation plan, section 7.5.

    Distance is weighted for luma sensitivity, and ties break on scan order, so the output is
    a pure function of the input bytes. The C# sidecar's guard must implement this same rule
    or offline previews will not match what the device is sent.
    """
    if len(rgb) != FRAME_BYTES:
        raise SessionError("STREAM_FRAME_LENGTH", f"expected {FRAME_BYTES} bytes, got {len(rgb)}")
    pixels = [rgb[i:i + 3] for i in range(0, FRAME_BYTES, 3)]
    palette = sorted(set(pixels))
    if len(palette) <= MAX_PALETTE_COLORS:
        return rgb, len(palette)

    best, keep, drop = None, None, None
    for index, first in enumerate(palette):
        for second in palette[index + 1:]:
            dr, dg, db = first[0] - second[0], first[1] - second[1], first[2] - second[2]
            distance = 3 * dr * dr + 4 * dg * dg + 2 * db * db
            if best is None or distance < best:
                best, keep, drop = distance, first, second
    merged = bytearray(rgb)
    for index, pixel in enumerate(pixels):
        if pixel == drop:
            merged[index * 3:index * 3 + 3] = keep
    out = bytes(merged)
    colors = len({out[i:i + 3] for i in range(0, FRAME_BYTES, 3)})
    if colors > MAX_PALETTE_COLORS:
        raise SessionError("STREAM_FRAME_UNQUANTIZABLE",
                           f"{colors} colours remain after the single permitted merge")
    return out, colors


def frames_from_source(source: Path) -> list[bytes]:
    """Load an ordered frame set: one `.rgb888` blob, or a directory of 16x16 PNGs."""
    source = Path(source)
    if source.is_dir():
        pngs = sorted(p for p in source.iterdir() if p.suffix.lower() == ".png")
        if not pngs:
            raise SessionError("STREAM_SOURCE_EMPTY", f"no PNG frames in {source}")
        return [decode_png16_rgb(path) for path in pngs]
    if not source.is_file():
        raise SessionError("STREAM_SOURCE_MISSING", str(source))
    blob = source.read_bytes()
    if not blob or len(blob) % FRAME_BYTES:
        raise SessionError("STREAM_SOURCE_NOT_FRAME_ALIGNED",
                           f"{len(blob)} bytes is not a positive multiple of {FRAME_BYTES}")
    return [blob[i:i + FRAME_BYTES] for i in range(0, len(blob), FRAME_BYTES)]


@dataclass(frozen=True)
class FrameSet:
    frames: tuple[bytes, ...]
    sha256: str
    packet_sha256: tuple[str, ...]
    palette_colors: tuple[int, ...]
    max_frame_tx_bytes: int

    @property
    def count(self) -> int:
        return len(self.frames)

    def total_tx_bytes(self, frame_count: int) -> int:
        return frame_count * self.max_frame_tx_bytes


def build_frame_set(frames: list[bytes]) -> FrameSet:
    """Encode every frame once, offline, so nothing is discovered mid-stream."""
    packets, colors, widest = [], [], 0
    for index, rgb in enumerate(frames, start=1):
        if len(rgb) != FRAME_BYTES:
            raise SessionError("STREAM_FRAME_LENGTH", f"frame {index} is {len(rgb)} bytes")
        try:
            wire, palette = encode_rgb888_static_image(rgb)
        except ValueError as exc:
            raise SessionError("STREAM_FRAME_NOT_ENCODABLE", f"frame {index}: {exc}") from exc
        packets.append(sha256_hex(wire))
        colors.append(palette)
        widest = max(widest, len(wire) + PREAMBLE_BYTES)
    blob = b"".join(frames)
    return FrameSet(tuple(frames), hashlib.sha256(blob).hexdigest(),
                    tuple(packets), tuple(colors), widest)


def write_frame_set(frames: list[bytes], path: Path) -> FrameSet:
    frame_set = build_frame_set(frames)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(frame_set.frames))
    return frame_set


# --------------------------------------------------------------------------
# The frame source handed to run_session
# --------------------------------------------------------------------------

class FrameSetRenderer:
    """Playback of a frozen frame set, clock-indexed or ACK-advanced.

    Clock-indexed is the honest default for content with intended timing: a slow transport
    drops frames instead of stretching the clip, and two identical consecutive frames simply
    hold rather than stalling a cursor forever.

    ACK-advanced exists for the streaming profile, where the point is to run at whatever
    rate the device grants and the clip is a rate fixture rather than a timed animation.
    There the deadlock is real -- an unchanged frame is never sent, so no ACK ever arrives to
    advance the cursor -- so advancing explicitly skips duplicates.
    """

    def __init__(self, frame_set: FrameSet, playback_interval_ms: int, loop: bool = False,
                 ack_advanced: bool = False) -> None:
        self.frame_set = frame_set
        self.playback_interval_ms = playback_interval_ms
        self.loop = loop
        self.ack_advanced = ack_advanced
        self.last_index = -1
        self._cursor = 0

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        if self.ack_advanced:
            index = self._cursor
        else:
            step = max(0, now_ms) // self.playback_interval_ms
            index = step % self.frame_set.count if self.loop else min(step, self.frame_set.count - 1)
        self.last_index = index
        return self.frame_set.frames[index], False

    def frame_sent(self) -> None:
        """Advance the cursor in ACK-advanced mode; clock-indexed playback ignores ACKs."""
        if not self.ack_advanced:
            return
        sent = self.frame_set.packet_sha256[self._cursor]
        # Skip frames identical to the one just sent, bounded by one pass, so a clip of all
        # identical frames terminates instead of spinning.
        for _ in range(self.frame_set.count):
            nxt = self._cursor + 1
            if nxt >= self.frame_set.count:
                if not self.loop:
                    return  # hold the final frame; the lifetime ends the session
                nxt = 0
            self._cursor = nxt
            if self.frame_set.packet_sha256[self._cursor] != sent:
                return


# --------------------------------------------------------------------------
# The reviewed stream manifest
# --------------------------------------------------------------------------

def authority_blockers(path: Path, now_epoch: float | None = None) -> list[str]:
    return _session.authority_blockers(Path(path), now_epoch)


def load_stream_manifest(path: Path, *, verify_code_hashes: bool = True,
                         require_authority: bool = True,
                         now_epoch: float | None = None):
    """Parse and validate one stream manifest into a shared SessionManifest, or refuse.

    Returns `(manifest, frame_set, stream)`. Every refusal happens before any claim and
    before the Host is contacted. Reviewing a manifest arms nothing.
    """
    require = _session._require
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError("MANIFEST_UNREADABLE", str(exc)) from exc
    require(isinstance(data, dict), "MANIFEST_UNREADABLE", "top level is not an object")
    require(data.get("schema_version") == SCHEMA_VERSION, "MANIFEST_SCHEMA_VERSION",
            f"expected {SCHEMA_VERSION}, got {data.get('schema_version')!r}")
    require(data.get("kind") == "frame_stream", "MANIFEST_KIND_MISMATCH",
            "a stream manifest must declare kind=frame_stream")

    experiment_id = data.get("experiment_id")
    require(isinstance(experiment_id, str) and experiment_id.strip() != "",
            "MANIFEST_EXPERIMENT_ID_MISSING")

    target = data.get("target") or {}
    require(target.get("exact_unit_id") == _session.EXACT_UNIT_ID, "MANIFEST_TARGET_MISMATCH")
    require(target.get("installed_firmware") == _session.INSTALLED_FIRMWARE, "MANIFEST_FIRMWARE_MISMATCH")
    require(bool((data.get("transport") or {}).get("measured_endpoint")), "MANIFEST_ENDPOINT_UNBOUND")

    session = data.get("session") or {}
    stream = data.get("stream") or {}
    budgets = data.get("budgets") or {}
    authority = data.get("authority") or {}
    build = data.get("build") or {}
    stop_policy = data.get("stop_policy") or {}

    # -- authority ---------------------------------------------------------
    require(authority.get("experiment_id") == experiment_id, "AUTHORITY_EXPERIMENT_ID_MISMATCH",
            "the grant must name the experiment it authorizes")
    if require_authority:
        blockers = authority_blockers(path, now_epoch)
        require(not blockers, blockers[0] if blockers else "TRANSMISSION_AUTHORITY_MISSING",
                ", ".join(blockers))

    # -- lifetime and pacing ----------------------------------------------
    lifetime = session.get("lifetime_seconds")
    require(isinstance(lifetime, int) and 0 < lifetime <= _session.MAX_SESSION_LIFETIME_SECONDS,
            "SESSION_LIFETIME_INVALID", f"1..{_session.MAX_SESSION_LIFETIME_SECONDS} s")
    # The profile decides which Host floor applies, so it is read before the pacing checks.
    profile = (data.get("stream") or {}).get("session_profile", SESSION_PROFILE_ACTIVITY)
    require(profile in SESSION_PROFILES, "STREAM_SESSION_PROFILE_UNKNOWN",
            f"allowed: {', '.join(SESSION_PROFILES)}")
    streaming = profile == SESSION_PROFILE_STREAMING
    host_floor = STREAMING_HOST_FLOOR_MS if streaming else _session.ACCEPTED_MIN_FRAME_INTERVAL_MS
    interval = session.get("min_frame_interval_ms")
    require(isinstance(interval, int) and interval >= host_floor,
            "SESSION_PACING_BELOW_ACCEPTED_CEILING",
            f"the Host floor for profile {profile!r} is {host_floor} ms per frame start")
    poll_ms = session.get("poll_interval_ms")
    require(isinstance(poll_ms, int) and 10 <= poll_ms <= max(interval, 50),
            "SESSION_POLL_INTERVAL_INVALID")
    require(session.get("automatic_retry") is False, "SESSION_RETRY_NOT_DISABLED")
    require(session.get("automatic_reconnect") is False, "SESSION_RECONNECT_NOT_DISABLED")
    require(session.get("stock_screen_reclaim") is False, "SESSION_RECLAIM_NOT_DISABLED")
    require(session.get("replay_after_interruption") is False, "SESSION_REPLAY_NOT_DISABLED")

    # -- the source: a frozen frame set, or a live producer -----------------
    #
    # A camera's future pixels do not exist at review time, so a live manifest cannot freeze
    # them. It freezes the ENVELOPE instead -- the producer's code hashes, the profile, the
    # lifetime, the floor and the budgets -- exactly as the MCP dashboard freezes its renderer
    # rather than its future frames. Nothing else about the session differs.
    source_kind = stream.get("source_kind", SOURCE_KIND_FRAME_SET)
    require(source_kind in SOURCE_KINDS, "STREAM_SOURCE_KIND_UNKNOWN",
            f"allowed: {', '.join(SOURCE_KINDS)}")
    live = source_kind == SOURCE_KIND_LIVE
    if live:
        for absent in ("frame_set_file", "frame_set_sha256", "frame_count"):
            require(absent not in stream, "STREAM_LIVE_DECLARES_FRAME_SET",
                    f"a live source has no frozen frames; remove {absent}")
        producer = stream.get("live_source") or {}
        require(bool(producer.get("producer_description")), "STREAM_LIVE_PRODUCER_UNDESCRIBED")
        hashes = producer.get("producer_code_sha256")
        require(isinstance(hashes, dict) and hashes, "STREAM_LIVE_PRODUCER_UNHASHED",
                "freeze the code that produces pixels, since the pixels cannot be frozen")
        for name, expected in sorted(hashes.items()):
            require(isinstance(expected, str) and len(expected) == 64,
                    "STREAM_LIVE_PRODUCER_HASH_INVALID", name)
            candidate = (ROOT / name) if not Path(name).is_absolute() else Path(name)
            # A producer inside this repository is verified now. One outside it (the Windows
            # sidecar's own build) is verified by whoever deploys it; the manifest still
            # records the hash it was reviewed against.
            if candidate.is_file():
                require(_session.sha256_file(candidate) == expected,
                        "STREAM_LIVE_PRODUCER_HASH_DRIFT", name)
        frame_set = None
    else:
        frame_file = stream.get("frame_set_file")
        require(isinstance(frame_file, str) and frame_file, "STREAM_FRAME_SET_UNBOUND")
        frame_path = (ROOT / frame_file) if not Path(frame_file).is_absolute() else Path(frame_file)
        frame_set = build_frame_set(frames_from_source(frame_path))
        require(stream.get("frame_set_sha256") == frame_set.sha256, "STREAM_FRAME_SET_HASH_DRIFT",
                f"manifest {stream.get('frame_set_sha256')!r} != actual {frame_set.sha256}")
        require(stream.get("frame_count") == frame_set.count, "STREAM_FRAME_COUNT_MISMATCH",
                f"manifest {stream.get('frame_count')!r} != actual {frame_set.count}")
    playback_ms = stream.get("playback_interval_ms")
    if streaming:
        # ACK-clocked: the interval is not a dispatch schedule, it is the floor the Host
        # backstops with, so no jitter margin is required or meaningful.
        require(isinstance(playback_ms, int) and playback_ms >= STREAMING_MIN_PLAYBACK_INTERVAL_MS,
                "STREAM_PLAYBACK_INTERVAL_INVALID",
                f"the streaming Host floor is {STREAMING_HOST_FLOOR_MS} ms")
        require(playback_ms >= interval, "STREAM_PLAYBACK_FASTER_THAN_FLOOR")
    else:
        require(isinstance(playback_ms, int) and playback_ms >= MIN_PLAYBACK_INTERVAL_MS,
                "STREAM_PLAYBACK_INTERVAL_INVALID",
                f"the Host floor is {_session.ACCEPTED_MIN_FRAME_INTERVAL_MS} ms and a clock-paced "
                f"client must add {CLIENT_JITTER_MARGIN_MS} ms of jitter margin on top of it; see "
                "OPENDITOO-S2-STREAM-RATE-001")
        require(playback_ms >= interval + CLIENT_JITTER_MARGIN_MS,
                "STREAM_PLAYBACK_FASTER_THAN_FLOOR",
                f"a clock-paced stream must dispatch at least {CLIENT_JITTER_MARGIN_MS} ms slower "
                "than the floor it asks the Host to enforce")
    loop = stream.get("loop")
    if live:
        # A camera cannot loop; declaring it would be a claim about content that does not
        # exist yet.
        require(loop in (None, False), "STREAM_LIVE_CANNOT_LOOP")
        loop = False
    else:
        require(isinstance(loop, bool), "STREAM_LOOP_INVALID")
    require(stream.get("source_description"), "STREAM_SOURCE_DESCRIPTION_MISSING")

    # -- budgets: derived, not asserted ------------------------------------
    # A distinct frame can only be sent once per playback step, so the clip -- or the
    # lifetime, whichever ends first -- bounds the frame count. This is what stops a
    # stream manifest from quietly buying a bigger budget than its content needs.
    steps_in_lifetime = lifetime * 1000 // playback_ms + 1
    if streaming:
        # ACK-clocked, so how many frames actually land depends on the device's measured
        # turnaround, not on a schedule. The budget is therefore a reviewed CEILING -- what
        # the lifetime could admit at the floor, capped by the Host's own frame ceiling --
        # and a run that sends fewer ends on budget or lifetime, both clean.
        expected_frames = min(steps_in_lifetime, _session.MAX_SESSION_FRAMES)
    elif live:
        expected_frames = min(steps_in_lifetime, _session.MAX_SESSION_FRAMES)
    else:
        expected_frames = steps_in_lifetime if loop else min(frame_set.count, steps_in_lifetime)
    max_frames = budgets.get("max_frames")
    require(isinstance(max_frames, int) and 0 < max_frames <= _session.MAX_SESSION_FRAMES,
            "BUDGET_FRAME_COUNT_INVALID", f"1..{_session.MAX_SESSION_FRAMES}")
    require(max_frames >= expected_frames, "BUDGET_FRAMES_BELOW_CONTENT",
            f"{expected_frames} playback steps fit in this lifetime")
    require(max_frames <= expected_frames, "BUDGET_FRAMES_EXCEED_CONTENT",
            f"the content and lifetime admit at most {expected_frames} frames")
    require(budgets.get("max_application_packets") == max_frames * _session.PACKETS_PER_FRAME,
            "BUDGET_PACKETS_NOT_DERIVED", f"expected {max_frames * _session.PACKETS_PER_FRAME}")
    max_tx = budgets.get("max_tx_bytes")
    # A live source has no frame set to measure, so its per-frame worst case comes from the
    # encoder's own ceiling: a full 255-entry palette at 8 bits per pixel.
    per_frame = worst_case_frame_tx_bytes() if live else frame_set.max_frame_tx_bytes
    require(max_tx == max_frames * per_frame, "BUDGET_TX_BYTES_NOT_DERIVED",
            f"expected {max_frames * per_frame} "
            f"({max_frames} x worst-case {per_frame} application bytes)")
    require(budgets.get("connection_attempts") == 1, "BUDGET_CONNECTION_ATTEMPTS_INVALID")
    ack_timeout = budgets.get("ack_timeout_ms_per_frame")
    require(isinstance(ack_timeout, int) and 0 < ack_timeout <= 5000, "BUDGET_ACK_TIMEOUT_INVALID")

    # -- frozen code and build identity ------------------------------------
    code_hashes = build.get("code_sha256") or {}
    require(set(code_hashes) == set(HASHED_MODULES), "BUILD_CODE_HASHES_INCOMPLETE",
            f"expected {sorted(HASHED_MODULES)}")
    if verify_code_hashes:
        actual = module_hashes()
        drift = {k: {"manifest": code_hashes[k], "actual": actual[k]}
                 for k in actual if code_hashes[k] != actual[k]}
        require(not drift, "BUILD_CODE_HASH_DRIFT", json.dumps(drift, sort_keys=True))
    host_build = build.get("host_dll_sha256")
    require(isinstance(host_build, str) and len(host_build) == 64, "BUILD_HOST_HASH_MISSING")

    stop_conditions = stop_policy.get("stop_immediately_on")
    require(isinstance(stop_conditions, list) and stop_conditions, "STOP_POLICY_MISSING")
    require(stop_policy.get("on_ambiguous_outcome_resend") is False, "STOP_POLICY_PERMITS_RESEND")
    require(stop_policy.get("collection_continues_after_display_stop") is True,
            "STOP_POLICY_STOPS_COLLECTION")

    manifest = _session.SessionManifest(
        experiment_id=experiment_id,
        lifetime_seconds=lifetime,
        min_frame_interval_ms=interval,
        pulse_freshness_seconds=_STREAM_PULSE_FRESHNESS_SECONDS,
        poll_interval_ms=poll_ms,
        max_frames=max_frames,
        max_application_packets=budgets["max_application_packets"],
        max_tx_bytes=max_tx,
        ack_timeout_ms_per_frame=ack_timeout,
        activation_source=stream["source_description"],
        host_build_sha256=host_build,
        code_hashes=dict(code_hashes),
        stop_conditions=tuple(stop_conditions),
        acceptance_profile=None,
        path=Path(path),
        raw=data,
    )
    return manifest, frame_set, dict(stream)


def derived_budgets(frame_set: FrameSet, lifetime_seconds: int, playback_interval_ms: int,
                    loop: bool, session_profile: str = SESSION_PROFILE_ACTIVITY) -> dict:
    """The budget block a manifest for this content must state, so it is derived once."""
    steps = lifetime_seconds * 1000 // playback_interval_ms + 1
    if session_profile == SESSION_PROFILE_STREAMING:
        frames = min(steps, _session.MAX_SESSION_FRAMES)
    else:
        frames = steps if loop else min(frame_set.count, steps)
    return {
        "connection_attempts": 1,
        "max_frames": frames,
        "max_application_packets": frames * _session.PACKETS_PER_FRAME,
        "max_tx_bytes": frame_set.total_tx_bytes(frames),
        "ack_timeout_ms_per_frame": 5000,
    }


# --------------------------------------------------------------------------
# Stream dispatch
# --------------------------------------------------------------------------
# `run_session` is the MCP dashboard's loop and is hash-frozen by the live product
# policy, so it can be imported but not changed -- and two of its properties are wrong
# for a stream: it floors every client at 200 ms, and it records no per-frame timing.
# This loop reuses the frozen ChangeOnlyScheduler, claim and transport unchanged, and
# differs only in dispatching on the manifest's own floor and measuring what it did.

def stream_session(manifest, frame_set: FrameSet | None, stream: dict, transport,
                   clock, sleep, claim: SessionClaim | None = None,
                   renderer=None) -> dict:
    """Drive one bounded stream to a terminal or explicitly unknown result.

    Semantics are deliberately identical to `run_session` wherever they overlap: an
    ambiguous or failed frame ends the session as `unknown` with no resend, no reconnect
    and no reclaim frame; an unsolicited report means the canvas is no longer ours.
    """
    # A live source injects its own renderer; a frozen frame set builds one from the manifest.
    if renderer is None:
        if frame_set is None:
            raise SessionError("STREAM_NO_SOURCE", "a live stream must inject its renderer")
        renderer = renderer_for(frame_set, stream)
    interval_ms = renderer.playback_interval_ms
    # ACK-clocked: the previous ACK is the permission to send the next frame, so the client
    # cannot dispatch early and the pacing race that ended S2 cannot occur. The Host's floor
    # stays as a backstop but stops being the pacing mechanism. Still one frame in flight and
    # one ACK per frame -- this is R5's accepted shape, not pipelining.
    ack_clocked = stream.get("session_profile") == SESSION_PROFILE_STREAMING
    scheduler = _session.ChangeOnlyScheduler(
        0 if ack_clocked else interval_ms, manifest.pulse_freshness_ms)
    started_ms = clock()
    deadline_ms = started_ms + manifest.lifetime_ms
    timings: list[dict] = []
    result = {"experiment_id": manifest.experiment_id, "frames_sent": 0, "packets_sent": 0,
              "tx_bytes_sent": 0, "holds": {}, "terminal_reason": None, "outcome": "unknown",
              "acks": [], "frame_timings": timings, "playback_steps_dropped": 0}

    def hold(reason: str) -> None:
        result["holds"][reason] = result["holds"].get(reason, 0) + 1

    def finish(reason: str, outcome: str, detail: str = "") -> dict:
        elapsed = clock() - started_ms
        result.update(terminal_reason=reason, outcome=outcome, detail=detail,
                      display_state=scheduler.display_state(), elapsed_ms=elapsed)
        sent = result["frames_sent"]
        result["realized_fps"] = round(sent / (elapsed / 1000.0), 3) if elapsed > 0 else 0.0
        result["mean_frame_interval_ms"] = round(elapsed / sent, 2) if sent else None
        if timings:
            ordered = sorted(item["ack_latency_ms"] for item in timings)
            result["ack_latency_ms"] = {
                "min": ordered[0], "median": ordered[len(ordered) // 2], "max": ordered[-1],
                "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]}
        if claim is not None:
            claim.finish(outcome, {"terminal_reason": reason, "detail": detail,
                                   "frames_sent": sent, "packets_sent": result["packets_sent"],
                                   "tx_bytes_sent": result["tx_bytes_sent"],
                                   "realized_fps": result["realized_fps"],
                                   "display_state": result["display_state"]})
        return result

    try:
        transport.open(manifest)
    except Exception as exc:
        return finish("open_failed", "unknown", f"{type(exc).__name__}: {exc}")

    try:
        last_index = -1
        while True:
            now = clock()
            if now >= deadline_ms:
                return finish("lifetime_expired", "stopped_clean", "")

            for report in transport.poll_reports():
                kind = report.get("kind")
                if kind == "session_ended":
                    reason = report.get("reason") or "session_ended"
                    if reason == "canvas_invalidated":
                        scheduler.invalidate_canvas(reason)
                    return finish(reason, report.get("outcome") or "unknown",
                                  json.dumps(report, sort_keys=True))
                if kind != "ack":
                    scheduler.invalidate_canvas(kind or "unexpected_report")
                    return finish("canvas_invalidated", "stopped_yielded_to_stock",
                                  json.dumps(report, sort_keys=True))

            rgb, _ = renderer(now)
            # A step the clock passed over while we were sending is a dropped frame, not a
            # delayed one. Count it: for a live source this is the headroom measurement.
            # Meaningless under an ACK clock, where the cursor only ever moves on a send.
            if not ack_clocked and renderer.last_index > last_index + 1:
                result["playback_steps_dropped"] += renderer.last_index - last_index - 1
            last_index = renderer.last_index

            scheduler.observe(clock(), rgb)
            action, reason = scheduler.next_action(clock())
            if action == "hold":
                hold(reason)
                if ack_clocked:
                    # ACK-clocked, so there is no next step to wait for. A hold here means
                    # the clip has nothing new (its end, un-looped), and the lifetime is what
                    # ends the session -- so idle cheaply rather than spinning.
                    sleep(manifest.poll_interval_ms)
                else:
                    # Wake at the next playback step rather than on a poll grid: there is
                    # nothing else for a stream to do between frames.
                    sleep(max(1, interval_ms - (clock() - started_ms) % interval_ms))
                continue

            desired = scheduler.sending(clock())
            wire, palette_colors = encode_rgb888_static_image(desired.rgb)
            packet_sha = sha256_hex(wire)
            frame_bytes = len(wire) + PREAMBLE_BYTES
            if result["frames_sent"] + 1 > manifest.max_frames or \
                    result["tx_bytes_sent"] + frame_bytes > manifest.max_tx_bytes:
                return finish("budget_exhausted", "stopped_clean", "local budget ceiling reached")
            dispatched_ms = clock()
            try:
                ack = transport.send_frame(desired.rgb, packet_sha)
            except Exception as exc:
                return finish("transport_fault", "unknown", f"{type(exc).__name__}: {exc}")
            acked_ms = clock()
            scheduler.sent()
            # Only an ACKed frame advances the source, so pacing or a slow Host can never
            # silently skip content. Clock-indexed playback ignores this.
            renderer.frame_sent()
            result["frames_sent"] = scheduler.frames_sent
            result["packets_sent"] += _session.PACKETS_PER_FRAME
            result["tx_bytes_sent"] += frame_bytes
            result["acks"].append(ack.get("ackPayloadHex"))
            timings.append({"frame": result["frames_sent"], "playback_index": renderer.last_index,
                            "since_start_ms": dispatched_ms - started_ms,
                            "ack_latency_ms": acked_ms - dispatched_ms,
                            "palette_colors": palette_colors,
                            "application_bytes": frame_bytes})
    finally:
        try:
            transport.close(result.get("terminal_reason") or "runner_exit")
        except Exception:
            result.setdefault("close_error", True)


def clip_lifetime_seconds(frame_set: FrameSet,
                          playback_interval_ms: int = MIN_PLAYBACK_INTERVAL_MS) -> int:
    """The shortest whole-second lifetime that still admits every frame of the clip."""
    return -(-frame_set.count * playback_interval_ms // 1000)


class LiveFrameSource:
    """Newest-frame-wins adapter around a live producer.

    The producer is any callable returning the freshest 768-byte frame available, or None if
    it has nothing yet. Nothing is queued: a frame that was current two frames ago is stale,
    and stale is worse than skipped, so the newest always wins and the rest are dropped and
    counted. `frame_sent` exists only to satisfy the renderer contract -- a camera's timeline
    is not ours to advance.

    Ownership stays with the producer; this holds one frame at most and never blocks.
    """

    def __init__(self, producer: Callable[[int], bytes | None], playback_interval_ms: int) -> None:
        self.producer = producer
        self.playback_interval_ms = playback_interval_ms
        self.last_index = -1
        self.frames_offered = 0
        self.frames_stale_dropped = 0
        self._last: bytes | None = None

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        frame = self.producer(now_ms)
        if frame is None:
            # Nothing new. Repeat the last frame; the scheduler holds it as unchanged, which
            # is the correct behaviour for a source that has not moved.
            if self._last is None:
                return bytes(FRAME_BYTES), False
            return self._last, False
        if len(frame) != FRAME_BYTES:
            raise SessionError("STREAM_FRAME_LENGTH", f"live producer gave {len(frame)} bytes")
        self.frames_offered += 1
        if self._last is not None and frame != self._last:
            self.last_index += 1
        self._last = frame
        return frame, False

    def frame_sent(self) -> None:
        """A live timeline advances on its own; an ACK does not move it."""


def renderer_for(frame_set: FrameSet, stream: dict) -> FrameSetRenderer:
    return FrameSetRenderer(
        frame_set, int(stream["playback_interval_ms"]), bool(stream["loop"]),
        ack_advanced=stream.get("session_profile") == SESSION_PROFILE_STREAMING)
