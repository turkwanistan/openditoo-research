"""Bounded activity-display session: authority lifecycle and change-only scheduling.

Three separable pieces, in dependency order:

1. `SessionManifest` — the reviewed contract. A dynamic display cannot pretend all
   future pixels were frozen in a static frame list, so what is frozen instead is the
   *envelope*: exact unit, renderer and collector code hashes, the Host build that may
   carry it, lifetime, budgets, pacing floor and stop conditions.
2. `SessionClaim` — durable one-use authority. Claimed before dispatch, atomically, by
   file creation. A crash leaves the claim standing with an unknown outcome; nothing
   here can reset it. A repeat needs a new manifest and a new grant.
3. `ChangeOnlyScheduler` — desired versus sent state. The Host hard acceptance floor is
   150 ms between frame starts. The MCP client deliberately dispatches at a nominal 200 ms
   cadence (5 fps), leaving 50 ms for cross-process/HTTP jitter while remaining far below
   the measured 18.46 fps no-sleep ceiling. It is not a heartbeat:
   an unchanged scene sends nothing, a burst coalesces to
   the newest frame, and a pulse that misses its freshness window is dropped rather
   than replayed later.

Nothing in this module opens a connection or touches the device. It drives an injected
transport, which is a fake in every test and in the offline preview.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Protocol

from host import activity_render
from host import mcp_activity

ROOT = Path(__file__).resolve().parents[1]
CLAIM_DIR = ROOT / ".openditoo-local" / "session-claims"

SCHEMA_VERSION = 2
EXACT_UNIT_ID = "11:75:58:CE:DE:C7"
INSTALLED_FIRMWARE = "v42012"

# Hard Host acceptance floor after the exact-unit R1-R5 ladder. R4 sustained full-colour
# motion at 131.0 ms/frame (7.63 fps) for 67 s and R5 reached 54.2 ms/frame (18.46 fps)
# with no sleeps. A manifest may ask the Host to enforce a slower floor; it may not ask
# for less than 150 ms without a new evidence boundary. The MCP client itself runs slower
# (see MCP_CLIENT_FRAME_INTERVAL_MS) because HTTP arrival jitter exists across processes.
ACCEPTED_MIN_FRAME_INTERVAL_MS = 150
# Client-side nominal cadence for the MCP dashboard. The Host enforces the hard 150 ms
# arrival floor on its own clock, while HTTP scheduling/jitter means a client dispatch
# exactly 150 ms after its previous dispatch can still arrive sooner than 150 ms server-side.
# 200 ms preserves 50 ms of cross-process timing headroom while remaining a responsive 5 fps.
MCP_CLIENT_FRAME_INTERVAL_MS = 200
# A first bounded activation is supervised. Anything longer is a different authority
# shape and needs its own evidence, not a bigger number here.
MAX_SESSION_LIFETIME_SECONDS = 900
MAX_SESSION_FRAMES = 500
PACKETS_PER_FRAME = 3

# Code whose bytes the manifest freezes: change either and the reviewed frame envelope
# is no longer the one that was reviewed.
HASHED_MODULES = {
    "renderer_sha256": ROOT / "host" / "activity_render.py",
    "ui_data_sha256": ROOT / "host" / "activity_ui_data.py",
    "collector_sha256": ROOT / "host" / "mcp_activity.py",
    "session_sha256": ROOT / "host" / "activity_session.py",
}
HOST_BUILD_DLL = ROOT / "runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0/OpenDitoo.Day1.Host.dll"


class SessionError(Exception):
    """Fail-closed session refusal. The message is a stable error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_hashes() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in HASHED_MODULES.items()}


# --------------------------------------------------------------------------
# 1. The reviewed contract
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionManifest:
    experiment_id: str
    lifetime_seconds: int
    min_frame_interval_ms: int
    pulse_freshness_seconds: int
    poll_interval_ms: int
    max_frames: int
    max_application_packets: int
    max_tx_bytes: int
    ack_timeout_ms_per_frame: int
    activation_source: str
    host_build_sha256: str
    code_hashes: dict[str, str]
    stop_conditions: tuple[str, ...]
    path: Path
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def lifetime_ms(self) -> int:
        return self.lifetime_seconds * 1000

    @property
    def pulse_freshness_ms(self) -> int:
        return self.pulse_freshness_seconds * 1000


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise SessionError(code, detail)


def authority_blockers(path: Path, now_epoch: float | None = None) -> list[str]:
    """The authority reasons this manifest may not run, as codes. Empty means granted.

    Split out from the loader so a PENDING manifest can still be fully reviewed and
    previewed offline. Reviewing one never arms it.
    """
    try:
        authority = (json.loads(Path(path).read_text(encoding="utf-8")).get("authority") or {})
    except (OSError, json.JSONDecodeError):
        return ["MANIFEST_UNREADABLE"]
    blockers = []
    if authority.get("transmission_authorized") is not True:
        blockers.append("TRANSMISSION_AUTHORITY_MISSING")
    if authority.get("authorization_consumed") is True:
        blockers.append("AUTHORITY_ALREADY_CONSUMED")
    if not authority.get("granted_by") or not authority.get("grant_text"):
        blockers.append("AUTHORITY_GRANT_UNATTRIBUTED")
    expires_at = authority.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at:
        blockers.append("AUTHORITY_EXPIRY_MISSING")
    else:
        try:
            now = mcp_activity.utc_now().timestamp() if now_epoch is None else now_epoch
            if now >= mcp_activity.parse_timestamp(expires_at).timestamp():
                blockers.append("AUTHORITY_EXPIRED")
        except ValueError:
            blockers.append("AUTHORITY_EXPIRY_UNREADABLE")
    return blockers


def load_session_manifest(path: Path, *, verify_code_hashes: bool = True,
                          require_authority: bool = True,
                          now_epoch: float | None = None) -> SessionManifest:
    """Parse and fully validate one activation manifest, or refuse with a code.

    Every refusal here happens before any claim is taken and before the transport is
    contacted, so a bad manifest can never leave a half-armed session behind.

    `require_authority=False` reviews a PENDING manifest -- everything except the grant
    itself. Only the live path leaves it True, and reviewing arms nothing either way.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError("MANIFEST_UNREADABLE", str(exc)) from exc
    _require(isinstance(data, dict), "MANIFEST_UNREADABLE", "top level is not an object")
    _require(data.get("schema_version") == SCHEMA_VERSION, "MANIFEST_SCHEMA_VERSION",
             f"expected {SCHEMA_VERSION}, got {data.get('schema_version')!r}")

    experiment_id = data.get("experiment_id")
    _require(isinstance(experiment_id, str) and experiment_id.strip() != "",
             "MANIFEST_EXPERIMENT_ID_MISSING")

    target = data.get("target") or {}
    _require(target.get("exact_unit_id") == EXACT_UNIT_ID, "MANIFEST_TARGET_MISMATCH")
    _require(target.get("installed_firmware") == INSTALLED_FIRMWARE, "MANIFEST_FIRMWARE_MISMATCH")
    _require(bool((data.get("transport") or {}).get("measured_endpoint")),
             "MANIFEST_ENDPOINT_UNBOUND")

    session = data.get("session") or {}
    budgets = data.get("budgets") or {}
    authority = data.get("authority") or {}
    build = data.get("build") or {}
    stop_policy = data.get("stop_policy") or {}

    # -- authority ---------------------------------------------------------
    # A grant that does not name its experiment is not a grant for THIS experiment, so
    # this one holds even while reviewing a pending manifest.
    _require(authority.get("experiment_id") == experiment_id, "AUTHORITY_EXPERIMENT_ID_MISMATCH",
             "the grant must name the experiment it authorizes")
    if require_authority:
        blockers = authority_blockers(path, now_epoch)
        _require(not blockers, blockers[0] if blockers else "TRANSMISSION_AUTHORITY_MISSING",
                 ", ".join(blockers))

    # -- lifetime and pacing ----------------------------------------------
    lifetime = session.get("lifetime_seconds")
    _require(isinstance(lifetime, int) and 0 < lifetime <= MAX_SESSION_LIFETIME_SECONDS,
             "SESSION_LIFETIME_INVALID", f"1..{MAX_SESSION_LIFETIME_SECONDS} s")
    interval = session.get("min_frame_interval_ms")
    _require(isinstance(interval, int) and interval >= ACCEPTED_MIN_FRAME_INTERVAL_MS,
             "SESSION_PACING_BELOW_ACCEPTED_CEILING",
             f"the product operating floor is {ACCEPTED_MIN_FRAME_INTERVAL_MS} ms per frame start")
    freshness = session.get("pulse_freshness_seconds")
    _require(isinstance(freshness, int) and 0 < freshness <= 120, "SESSION_PULSE_FRESHNESS_INVALID")
    poll_ms = session.get("poll_interval_ms")
    _require(isinstance(poll_ms, int) and 50 <= poll_ms <= interval, "SESSION_POLL_INTERVAL_INVALID",
             "the render tick must run at least as often as a frame may be sent")
    _require(bool(session.get("activation_source")), "SESSION_ACTIVATION_SOURCE_MISSING")
    _require(session.get("automatic_retry") is False, "SESSION_RETRY_NOT_DISABLED")
    _require(session.get("automatic_reconnect") is False, "SESSION_RECONNECT_NOT_DISABLED")
    _require(session.get("stock_screen_reclaim") is False, "SESSION_RECLAIM_NOT_DISABLED")
    _require(session.get("replay_after_interruption") is False, "SESSION_REPLAY_NOT_DISABLED")

    # -- budgets: derived, not asserted ------------------------------------
    max_frames = budgets.get("max_frames")
    _require(isinstance(max_frames, int) and 0 < max_frames <= MAX_SESSION_FRAMES,
             "BUDGET_FRAME_COUNT_INVALID")
    ceiling = lifetime * 1000 // interval + 1
    _require(max_frames <= ceiling, "BUDGET_FRAMES_EXCEED_LIFETIME",
             f"{lifetime} s at {interval} ms admits at most {ceiling} frame starts")
    _require(budgets.get("max_application_packets") == max_frames * PACKETS_PER_FRAME,
             "BUDGET_PACKETS_NOT_DERIVED", f"expected {max_frames * PACKETS_PER_FRAME}")
    max_tx = budgets.get("max_tx_bytes")
    _require(isinstance(max_tx, int) and max_tx > 0, "BUDGET_TX_BYTES_INVALID")
    _require(budgets.get("connection_attempts") == 1, "BUDGET_CONNECTION_ATTEMPTS_INVALID")
    ack_timeout = budgets.get("ack_timeout_ms_per_frame")
    _require(isinstance(ack_timeout, int) and 0 < ack_timeout <= 5000, "BUDGET_ACK_TIMEOUT_INVALID")

    # -- frozen code and build identity ------------------------------------
    code_hashes = build.get("code_sha256") or {}
    _require(set(code_hashes) == set(HASHED_MODULES), "BUILD_CODE_HASHES_INCOMPLETE",
             f"expected {sorted(HASHED_MODULES)}")
    if verify_code_hashes:
        actual = module_hashes()
        drift = {k: {"manifest": code_hashes[k], "actual": actual[k]}
                 for k in actual if code_hashes[k] != actual[k]}
        _require(not drift, "BUILD_CODE_HASH_DRIFT", json.dumps(drift, sort_keys=True))
    host_build = build.get("host_dll_sha256")
    _require(isinstance(host_build, str) and len(host_build) == 64, "BUILD_HOST_HASH_MISSING")

    stop_conditions = stop_policy.get("stop_immediately_on")
    _require(isinstance(stop_conditions, list) and stop_conditions, "STOP_POLICY_MISSING")
    _require(stop_policy.get("on_ambiguous_outcome_resend") is False, "STOP_POLICY_PERMITS_RESEND")
    _require(stop_policy.get("collection_continues_after_display_stop") is True,
             "STOP_POLICY_STOPS_COLLECTION",
             "a Bluetooth fault stops the display; collection keeps running")

    return SessionManifest(
        experiment_id=experiment_id,
        lifetime_seconds=lifetime,
        min_frame_interval_ms=interval,
        pulse_freshness_seconds=freshness,
        poll_interval_ms=poll_ms,
        max_frames=max_frames,
        max_application_packets=budgets["max_application_packets"],
        max_tx_bytes=max_tx,
        ack_timeout_ms_per_frame=ack_timeout,
        activation_source=session["activation_source"],
        host_build_sha256=host_build,
        code_hashes=dict(code_hashes),
        stop_conditions=tuple(stop_conditions),
        path=Path(path),
        raw=data,
    )


# --------------------------------------------------------------------------
# 2. Durable one-use authority
# --------------------------------------------------------------------------

class SessionClaim:
    """One experiment id, claimed exactly once, on disk, before any dispatch.

    `O_EXCL` is the whole mechanism: the filesystem, not a flag inside the manifest,
    decides who got there first. A worker or Host that dies mid-session leaves the
    claim in `claimed` state, which reads as an unknown outcome and refuses re-entry.
    There is deliberately no release, reset or un-consume path.
    """

    def __init__(self, experiment_id: str, directory: Path = CLAIM_DIR) -> None:
        self.experiment_id = experiment_id
        self.path = directory / f"{experiment_id}.json"
        self.directory = directory

    def read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def claim(self, record: dict) -> dict:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        body = {"experiment_id": self.experiment_id, "state": "claimed",
                "outcome": "unknown", **record}
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            existing = self.read() or {}
            raise SessionError(
                "AUTHORITY_ALREADY_CONSUMED",
                f"experiment {self.experiment_id} was already claimed "
                f"(state={existing.get('state')!r}, outcome={existing.get('outcome')!r}); "
                "cut a new manifest with a new id under a new grant",
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(body, handle, sort_keys=True, indent=1)
        return body

    def finish(self, outcome: str, detail: dict) -> dict:
        """Record a terminal result over the claim. The claim itself stays consumed."""
        body = {**(self.read() or {}), "state": "finished", "outcome": outcome, **detail}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, sort_keys=True, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
        return body


# --------------------------------------------------------------------------
# 3. Change-only scheduling
# --------------------------------------------------------------------------

@dataclass
class _Desired:
    frame_sha256: str
    rgb: bytes
    observed_at_ms: int
    from_pulse: bool


class ChangeOnlyScheduler:
    """Desired versus last-sent frame, with pacing, coalescing and pulse expiry.

    Time is passed in as milliseconds so every case is testable on a fake clock.
    """

    def __init__(self, min_frame_interval_ms: int, pulse_freshness_ms: int) -> None:
        self.min_frame_interval_ms = min_frame_interval_ms
        self.pulse_freshness_ms = pulse_freshness_ms
        self.desired: _Desired | None = None
        self.last_sent_sha256: str | None = None
        self.last_send_started_ms: int | None = None
        self.canvas_ours = True
        self.frames_sent = 0
        self.dropped_expired_pulses = 0

    def observe(self, now_ms: int, rgb: bytes, from_pulse: bool = False) -> None:
        """Take the newest render. A burst coalesces here: nothing is queued."""
        digest = hashlib.sha256(rgb).hexdigest()
        if self.desired is not None and self.desired.frame_sha256 == digest:
            # Same image again: keep the ORIGINAL observation time, so a scene that
            # simply persists cannot renew a pulse's freshness window indefinitely.
            return
        self.desired = _Desired(digest, rgb, now_ms, from_pulse)

    def invalidate_canvas(self, reason: str = "stock_takeover") -> None:
        """Someone else owns the screen. We do not know what is displayed, and we
        never send a reclaim frame to find out."""
        self.canvas_ours = False
        self.canvas_lost_reason = reason
        self.desired = None

    def display_state(self) -> str:
        if not self.canvas_ours:
            return "unknown_not_ours"
        return "ours_last_acked" if self.last_sent_sha256 else "unknown_nothing_sent"

    def next_action(self, now_ms: int) -> tuple[str, str]:
        """Return (action, reason); action is 'send' or 'hold'."""
        if not self.canvas_ours:
            return "hold", "canvas_invalidated"
        if self.desired is None:
            return "hold", "no_render_yet"
        if self.desired.frame_sha256 == self.last_sent_sha256:
            return "hold", "unchanged"
        if self.desired.from_pulse and now_ms - self.desired.observed_at_ms > self.pulse_freshness_ms:
            # Its moment has passed. Dropping it is correct; showing it late would be
            # a replay of activity that is no longer current.
            self.desired = None
            self.dropped_expired_pulses += 1
            return "hold", "pulse_expired"
        if self.last_send_started_ms is not None and \
                now_ms - self.last_send_started_ms < self.min_frame_interval_ms:
            return "hold", "pacing"
        return "send", "changed"

    def sending(self, now_ms: int) -> _Desired:
        assert self.desired is not None
        self.last_send_started_ms = now_ms
        return self.desired

    def sent(self) -> None:
        assert self.desired is not None
        self.last_sent_sha256 = self.desired.frame_sha256
        self.frames_sent += 1


# --------------------------------------------------------------------------
# The transport contract, and a fake that satisfies it offline
# --------------------------------------------------------------------------

class SessionTransport(Protocol):
    def open(self, manifest: SessionManifest) -> dict: ...
    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict: ...
    def poll_reports(self) -> list[dict]: ...
    def close(self, reason: str) -> dict: ...


class FakeSessionTransport:
    """Records what would have been sent. Scripted reports drive takeover and fault
    cases. Used by the offline preview and every test; it reaches nothing."""

    def __init__(self, reports: dict[int, list[dict]] | None = None,
                 fail_on_frame: int | None = None) -> None:
        self.reports = reports or {}
        self.fail_on_frame = fail_on_frame
        self.opened = False
        self.closed_reason: str | None = None
        self.frames: list[dict] = []
        self.tx_bytes = 0
        self.packets = 0

    def open(self, manifest: SessionManifest) -> dict:
        self.opened = True
        return {"sessionId": "fake", "experimentId": manifest.experiment_id}

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        index = len(self.frames) + 1
        if self.fail_on_frame == index:
            raise SessionError("TRANSPORT_FAULT", f"scripted fault on frame {index}")
        from host.ditoo_pixel_coloring import encode_rgb888_static_image
        wire, palette_colors = encode_rgb888_static_image(rgb)
        self.packets += PACKETS_PER_FRAME
        self.tx_bytes += len(wire) + 7 + 8  # image packet plus the two stock preambles
        record = {"frame": index, "imagePacketSha256": expected_packet_sha256,
                  "paletteColors": palette_colors, "ackPayloadHex": "0x00"}
        self.frames.append(record)
        return record

    def poll_reports(self) -> list[dict]:
        return list(self.reports.get(len(self.frames), []))

    def close(self, reason: str) -> dict:
        self.closed_reason = reason
        return {"closed": True, "reason": reason}


# --------------------------------------------------------------------------
# The session runner
# --------------------------------------------------------------------------

TERMINAL_OK = ("lifetime_expired", "budget_exhausted", "operator_stop")


def run_session(manifest: SessionManifest, transport: SessionTransport,
                render: Callable[[int], tuple[bytes, bool]],
                clock: Callable[[], int], sleep: Callable[[int], None],
                claim: SessionClaim | None = None,
                max_iterations: int = 100_000) -> dict:
    """Drive one bounded activation to a terminal or explicitly unknown result.

    `render(now_ms)` returns the current 16x16 RGB888 frame and whether new activity
    was observed in this poll. Collection failures are the caller's business: a source
    that cannot be read still renders, as an unavailable indicator, and never stops
    the display.
    """
    from host.ditoo_pixel_coloring import (IMAGE_PREAMBLE_A, IMAGE_PREAMBLE_B,
                                           encode_rgb888_static_image, sha256_hex)
    # The budget is stated in APPLICATION bytes and the Host is the authority on it, so
    # count the whole three-packet group -- the image packet plus both stock preambles --
    # not just the image. Counting only the image under-reports against a shared ceiling.
    preamble_bytes = len(IMAGE_PREAMBLE_A) + len(IMAGE_PREAMBLE_B)

    scheduler_interval_ms = max(manifest.min_frame_interval_ms, MCP_CLIENT_FRAME_INTERVAL_MS)
    scheduler = ChangeOnlyScheduler(scheduler_interval_ms, manifest.pulse_freshness_ms)
    started_ms = clock()
    deadline_ms = started_ms + manifest.lifetime_ms
    result = {"experiment_id": manifest.experiment_id, "frames_sent": 0,
              "packets_sent": 0, "tx_bytes_sent": 0, "holds": {},
              "terminal_reason": None, "outcome": "unknown", "acks": []}

    def hold(reason: str) -> None:
        result["holds"][reason] = result["holds"].get(reason, 0) + 1

    next_tick_ms = started_ms

    def wait_for_next_tick(_tick_started_ms: int) -> None:
        nonlocal next_tick_ms
        # Keep render ticks on one phase-stable grid. Transport/ACK work consumes the tick
        # budget; if it overruns a tick, skip that missed tick rather than shifting every
        # future tick later. This lets a 50 ms render tick service the 200 ms MCP send
        # cadence at 0/200/400/... while still tolerating e.g. 70 ms of send/ACK work.
        next_tick_ms += manifest.poll_interval_ms
        now_ms = clock()
        while next_tick_ms <= now_ms:
            next_tick_ms += manifest.poll_interval_ms
        sleep(max(0, next_tick_ms - now_ms))

    def finish(reason: str, outcome: str, detail: str = "") -> dict:
        result["terminal_reason"] = reason
        result["outcome"] = outcome
        result["detail"] = detail
        result["display_state"] = scheduler.display_state()
        result["dropped_expired_pulses"] = scheduler.dropped_expired_pulses
        result["elapsed_ms"] = clock() - started_ms
        if claim is not None:
            claim.finish(outcome, {"terminal_reason": reason, "detail": detail,
                                   "frames_sent": result["frames_sent"],
                                   "packets_sent": result["packets_sent"],
                                   "tx_bytes_sent": result["tx_bytes_sent"],
                                   "display_state": result["display_state"]})
        return result

    try:
        transport.open(manifest)
    except Exception as exc:
        return finish("open_failed", "unknown", f"{type(exc).__name__}: {exc}")

    try:
        for _ in range(max_iterations):
            now = clock()
            if now >= deadline_ms:
                break

            for report in transport.poll_reports():
                kind = report.get("kind")
                if kind == "session_ended":
                    # The Host ended it. Adopt ITS reason and outcome rather than
                    # reporting a fault we merely inferred from a refusal.
                    reason = report.get("reason") or "session_ended"
                    if reason == "canvas_invalidated":
                        scheduler.invalidate_canvas(reason)
                    return finish(reason, report.get("outcome") or "unknown",
                                  json.dumps(report, sort_keys=True))
                if kind != "ack":
                    # An unsolicited state report means the canvas is no longer ours.
                    # A late ACK cannot give it back, and no reclaim frame is sent.
                    scheduler.invalidate_canvas(kind or "unexpected_report")
                    return finish("canvas_invalidated", "stopped_yielded_to_stock",
                                  json.dumps(report, sort_keys=True))

            rgb, from_pulse = render(now)
            scheduler.observe(now, rgb, from_pulse)
            action, reason = scheduler.next_action(now)
            if action == "hold":
                hold(reason)
                wait_for_next_tick(now)
                continue

            desired = scheduler.sending(now)
            wire, _ = encode_rgb888_static_image(desired.rgb)
            packet_sha = sha256_hex(wire)
            frame_bytes = len(wire) + preamble_bytes
            if result["frames_sent"] + 1 > manifest.max_frames or \
                    result["tx_bytes_sent"] + frame_bytes > manifest.max_tx_bytes:
                return finish("budget_exhausted", "stopped_clean", "local budget ceiling reached")
            try:
                ack = transport.send_frame(desired.rgb, packet_sha)
            except Exception as exc:
                # Ambiguous or failed: stop the display, keep collection, record what
                # is known and what is not. Never resend, never reconnect.
                return finish("transport_fault", "unknown", f"{type(exc).__name__}: {exc}")
            scheduler.sent()
            frame_sent = getattr(render, "frame_sent", None)
            if callable(frame_sent):
                frame_sent()
            result["frames_sent"] = scheduler.frames_sent
            result["packets_sent"] += PACKETS_PER_FRAME
            result["tx_bytes_sent"] += frame_bytes
            result["acks"].append(ack.get("ackPayloadHex"))
            wait_for_next_tick(now)
        else:
            return finish("iteration_ceiling", "unknown", "runner iteration ceiling reached")
        return finish("lifetime_expired", "stopped_clean", "")
    finally:
        try:
            transport.close(result.get("terminal_reason") or "runner_exit")
        except Exception:  # a close failure cannot resurrect the session
            result.setdefault("close_error", True)


# --------------------------------------------------------------------------
# Offline rendering source used by the preview and by live runs alike
# --------------------------------------------------------------------------

class LiveActivityRenderer:
    """Decouple source polling from the faster display tick and own the four-stage pulse.

    Source adapters keep their configured multi-second poll cadence. The display may render
    every 150 ms while an animation is active without hammering SSH/files six times a
    second. A pulse stage advances only after `run_session` records an ACK, so pacing or a
    slow Host cannot silently skip an approved stage. New events coalesce into the newest
    pulse; no old animation is queued or replayed.
    """

    def __init__(self, config: dict, state: dict) -> None:
        self.config = config
        self.state = state
        self.source_poll_ms = max(100, int(float(config.get("poll_seconds", 2.0)) * 1000))
        self.next_collect_ms = 0
        self.pulse_sources: set[str] = set()
        self.pulse_stage: int | None = None

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        if now_ms >= self.next_collect_ms:
            try:
                counts = mcp_activity.collect_once(
                    self.config, self.state, poll_seconds=self.source_poll_ms / 1000.0)
            except mcp_activity.SourceError:
                counts = {}
            mcp_activity.save_state(self.state)
            new_pulses = {key for key, value in counts.items() if value}
            if new_pulses:
                # Coalesce to the newest observed activity. Nothing waits behind it.
                self.pulse_sources = new_pulses
                self.pulse_stage = 0
            self.next_collect_ms = now_ms + self.source_poll_ms

        if self.pulse_stage is not None:
            return (activity_render.render_rgb888(
                        self.state, pulses=self.pulse_sources, pulse_stage=self.pulse_stage),
                    True)
        self.pulse_sources.clear()
        return activity_render.render_rgb888(self.state), False

    def frame_sent(self) -> None:
        """Advance animation only after the current stage was ACKed."""
        if self.pulse_stage is None:
            return
        self.pulse_stage += 1
        if self.pulse_stage >= len(activity_render.PULSE_COLORS):
            self.pulse_stage = None
            self.pulse_sources.clear()


def live_renderer(config: dict, state: dict) -> LiveActivityRenderer:
    return LiveActivityRenderer(config, state)


# --------------------------------------------------------------------------
# Receive framing, mirrored by the Host's C# assembler
# --------------------------------------------------------------------------
# The device does not only answer. Physical controls produce unsolicited wrapped
# reports on the same link (M7), so an open session reads a stream, not a reply: a
# read may deliver a fragment, an exact frame, or an ACK and a state report coalesced
# together. This assigns no new command semantics; it answers one question -- is this
# our ACK, or something else that means we must stop?
#
# `runtime/windows/.../DitooSessionReport.cs` implements the same rules, and both are
# exercised against the SAME fixture: `tests/receive_assembler_cases.json`, replayed
# here by the offline suite and by the Host's `--selftest` argument.

MAX_REPORT_BYTES = 256
ACK_OUTER_COMMAND = 0x04
ACK_INNER_COMMAND = 0x44
ACK_TAG = 0x55


class ReportFramingError(Exception):
    """Fail-closed receive framing failure. The first word is the shared error code."""


def classify_report(wire: bytes) -> str:
    """'ack' for our wrapped 0x44 answer, 'state_report' for anything else valid."""
    from host.ditoo_candidate_codec import FrameDecodeError, decode_candidate_wrapped
    try:
        frame = decode_candidate_wrapped(wire)
    except FrameDecodeError as exc:
        code = "IMAGE_RX_CHECKSUM_REJECTED" if "checksum" in str(exc) else "IMAGE_RX_BOUNDARY_REJECTED"
        raise ReportFramingError(f"{code} {exc}") from exc
    if (frame.outer_command, frame.command, frame.tag) == (ACK_OUTER_COMMAND, ACK_INNER_COMMAND, ACK_TAG) \
            and len(frame.payload) == 1:
        return "ack"
    return "state_report"


class ReportAssembler:
    """Bounded, fail-closed reassembly. Unlike the offline capture decoder it never
    resynchronizes past garbage: on a live link, bytes we cannot parse end the session."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[str]:
        self._buffer.extend(chunk)
        if len(self._buffer) > MAX_REPORT_BYTES:
            raise ReportFramingError(f"IMAGE_RX_OVERSIZE BYTES={len(self._buffer)}")
        return self.drain()

    def drain(self) -> list[str]:
        kinds: list[str] = []
        while True:
            if len(self._buffer) < 3:
                return kinds
            if self._buffer[0] != 0x01:
                raise ReportFramingError(f"IMAGE_RX_BAD_START BYTE=0x{self._buffer[0]:02X}")
            inner = int.from_bytes(self._buffer[1:3], "little")
            total = inner + 4
            if inner < 5 or total > MAX_REPORT_BYTES:
                raise ReportFramingError(f"IMAGE_RX_LENGTH_REJECTED INNER={inner}")
            if len(self._buffer) < total:
                return kinds
            kinds.append(classify_report(bytes(self._buffer[:total])))
            del self._buffer[:total]
