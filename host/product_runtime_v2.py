"""OpenDitoo MCP dashboard supervisor — Runtime 002 telemetry revision.

This is deliberately a supervisor over the already-accepted bounded activity-session
transport. It does not open Bluetooth itself and exposes no raw-send/target override.

Product semantics:
- exact Ditoo only, via the existing fixed Windows Host;
- keep MCP collection alive while connected or waiting for the device;
- renew bounded Host sessions before they become long-lived hidden state;
- if a physical input invalidates our canvas, immediately open a fresh bounded session
  and restore the current MCP dashboard;
- if the device/Host is genuinely unavailable, retry with bounded backoff;
- graceful stop closes the active session through the normal session runner.

Persistent transmission authority is a different shape from one-shot experiment grants.
It is carried only by a local, git-ignored policy file created after an explicit product
grant; the committed template remains disabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from typing import Callable, Protocol

from host import activity_session, mcp_activity

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / ".openditoo-local" / "product-runtime-policy.json"
STATE_FILE = ROOT / ".openditoo-local" / "product-runtime-state.json"
POLICY_SCHEMA_VERSION = 1
RUNTIME_REVISION = 2
PRODUCT_ID = "OPENDITOO-MCP-DASHBOARD-V1"
EXACT_UNIT_ID = activity_session.EXACT_UNIT_ID
INSTALLED_FIRMWARE = activity_session.INSTALLED_FIRMWARE
DEFAULT_RECONNECT_BACKOFF_SECONDS = (1, 2, 5, 10, 30)
MAX_RECLAIMS_IN_WINDOW = 8
RECLAIM_WINDOW_SECONDS = 10
RECLAIM_COOLDOWN_SECONDS = 1


class ProductPolicyError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise ProductPolicyError(code, detail)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_hashes() -> dict[str, str]:
    hashes = activity_session.module_hashes()
    hashes["product_runtime_sha256"] = sha256_file(Path(__file__))
    return hashes


@dataclass(frozen=True)
class ProductPolicy:
    path: Path
    product_id: str
    session_lifetime_seconds: int
    min_frame_interval_ms: int
    poll_interval_ms: int
    pulse_freshness_seconds: int
    max_frames_per_session: int
    max_tx_bytes_per_session: int
    reconnect_backoff_seconds: tuple[int, ...]
    reclaim_on_canvas_invalidated: bool
    automatic_reconnect: bool
    start_at_windows_logon: bool
    code_hashes: dict[str, str]
    host_build_sha256: str
    authority_grant_text: str


def authority_blockers(path: Path = DEFAULT_POLICY) -> list[str]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["PRODUCT_POLICY_UNREADABLE"]
    authority = raw.get("authority") or {}
    blockers: list[str] = []
    if authority.get("persistent_runtime_authorized") is not True:
        blockers.append("PRODUCT_AUTHORITY_MISSING")
    if authority.get("revoked") is True:
        blockers.append("PRODUCT_AUTHORITY_REVOKED")
    if not authority.get("granted_by") or not authority.get("grant_text"):
        blockers.append("PRODUCT_AUTHORITY_UNATTRIBUTED")
    if authority.get("grant_scope") != authority.get("grant_scope_requested"):
        blockers.append("PRODUCT_AUTHORITY_SCOPE_MISMATCH")
    return blockers


def load_policy(path: Path = DEFAULT_POLICY, *, require_authority: bool = True,
                verify_hashes: bool = True) -> ProductPolicy:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProductPolicyError("PRODUCT_POLICY_MISSING", str(path)) from exc
    except json.JSONDecodeError as exc:
        raise ProductPolicyError("PRODUCT_POLICY_INVALID_JSON", str(exc)) from exc

    _require(raw.get("schema_version") == POLICY_SCHEMA_VERSION,
             "PRODUCT_POLICY_SCHEMA_VERSION")
    _require(raw.get("runtime_revision") == RUNTIME_REVISION,
             "PRODUCT_RUNTIME_REVISION_MISMATCH")
    _require(raw.get("product_id") == PRODUCT_ID, "PRODUCT_POLICY_ID_MISMATCH")
    target = raw.get("target") or {}
    _require(target.get("exact_unit_id") == EXACT_UNIT_ID, "PRODUCT_TARGET_MISMATCH")
    _require(target.get("installed_firmware") == INSTALLED_FIRMWARE,
             "PRODUCT_FIRMWARE_MISMATCH")

    authority = raw.get("authority") or {}
    if require_authority:
        _require(authority.get("persistent_runtime_authorized") is True,
                 "PRODUCT_AUTHORITY_MISSING")
        _require(authority.get("revoked") is not True, "PRODUCT_AUTHORITY_REVOKED")
        _require(bool(authority.get("granted_by")) and bool(authority.get("grant_text")),
                 "PRODUCT_AUTHORITY_UNATTRIBUTED")
        _require(authority.get("grant_scope") == authority.get("grant_scope_requested"),
                 "PRODUCT_AUTHORITY_SCOPE_MISMATCH")

    behavior = raw.get("behavior") or {}
    _require(behavior.get("automatic_reconnect") is True,
             "PRODUCT_AUTO_RECONNECT_REQUIRED")
    _require(behavior.get("reclaim_on_canvas_invalidated") is True,
             "PRODUCT_RECLAIM_REQUIRED")
    _require(behavior.get("raw_send_enabled") is False, "PRODUCT_RAW_SEND_FORBIDDEN")
    _require(behavior.get("target_override_enabled") is False,
             "PRODUCT_TARGET_OVERRIDE_FORBIDDEN")
    _require(behavior.get("start_at_windows_logon") is True,
             "PRODUCT_STARTUP_REQUIRED")

    session = raw.get("session") or {}
    lifetime = session.get("lifetime_seconds")
    _require(isinstance(lifetime, int) and 60 <= lifetime <= activity_session.MAX_SESSION_LIFETIME_SECONDS,
             "PRODUCT_SESSION_LIFETIME_INVALID")
    interval = session.get("min_frame_interval_ms")
    _require(isinstance(interval, int) and interval >= activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS,
             "PRODUCT_SESSION_PACING_INVALID")
    poll = session.get("poll_interval_ms")
    _require(isinstance(poll, int) and 50 <= poll <= interval,
             "PRODUCT_POLL_INTERVAL_INVALID")
    freshness = session.get("pulse_freshness_seconds")
    _require(isinstance(freshness, int) and 0 < freshness <= 120,
             "PRODUCT_PULSE_FRESHNESS_INVALID")
    max_frames = session.get("max_frames")
    _require(isinstance(max_frames, int) and 1 <= max_frames <= activity_session.MAX_SESSION_FRAMES,
             "PRODUCT_FRAME_BUDGET_INVALID")
    max_tx = session.get("max_tx_bytes")
    _require(isinstance(max_tx, int) and max_tx > 0, "PRODUCT_TX_BUDGET_INVALID")
    ceiling = lifetime * 1000 // interval + 1
    _require(max_frames <= ceiling, "PRODUCT_FRAME_BUDGET_EXCEEDS_LIFETIME")

    backoff = tuple(behavior.get("reconnect_backoff_seconds") or ())
    _require(bool(backoff) and all(isinstance(v, int) and 1 <= v <= 60 for v in backoff),
             "PRODUCT_BACKOFF_INVALID")
    _require(tuple(sorted(backoff)) == backoff, "PRODUCT_BACKOFF_NOT_MONOTONIC")

    build = raw.get("build") or {}
    expected_hashes = build.get("code_sha256") or {}
    _require(set(expected_hashes) == set(runtime_hashes()), "PRODUCT_CODE_HASH_SET_MISMATCH")
    if verify_hashes:
        actual = runtime_hashes()
        _require(actual == expected_hashes, "PRODUCT_CODE_HASH_MISMATCH",
                 json.dumps({"expected": expected_hashes, "actual": actual}, sort_keys=True))

    host_hash = build.get("host_dll_sha256")
    _require(isinstance(host_hash, str) and len(host_hash) == 64,
             "PRODUCT_HOST_HASH_MISSING")
    if verify_hashes:
        _require(activity_session.HOST_BUILD_DLL.is_file(), "PRODUCT_HOST_BUILD_MISSING")
        _require(activity_session.sha256_file(activity_session.HOST_BUILD_DLL) == host_hash,
                 "PRODUCT_HOST_HASH_MISMATCH")

    return ProductPolicy(
        path=Path(path), product_id=PRODUCT_ID,
        session_lifetime_seconds=lifetime,
        min_frame_interval_ms=interval,
        poll_interval_ms=poll,
        pulse_freshness_seconds=freshness,
        max_frames_per_session=max_frames,
        max_tx_bytes_per_session=max_tx,
        reconnect_backoff_seconds=backoff,
        reclaim_on_canvas_invalidated=True,
        automatic_reconnect=True,
        start_at_windows_logon=True,
        code_hashes=dict(expected_hashes), host_build_sha256=host_hash,
        authority_grant_text=str(authority.get("grant_text") or ""),
    )


def product_session_manifest(policy: ProductPolicy, experiment_id: str) -> activity_session.SessionManifest:
    stop_conditions = (
        "Host session lifetime reached",
        "Host frame or byte budget reached",
        "worker stop requested",
        "physical input invalidates canvas: supervisor immediately starts a fresh bounded session",
        "transport/Host/device unavailable: supervisor uses bounded reconnect backoff",
    )
    return activity_session.SessionManifest(
        experiment_id=experiment_id,
        lifetime_seconds=policy.session_lifetime_seconds,
        min_frame_interval_ms=policy.min_frame_interval_ms,
        pulse_freshness_seconds=policy.pulse_freshness_seconds,
        poll_interval_ms=policy.poll_interval_ms,
        max_frames=policy.max_frames_per_session,
        max_application_packets=policy.max_frames_per_session * activity_session.PACKETS_PER_FRAME,
        max_tx_bytes=policy.max_tx_bytes_per_session,
        ack_timeout_ms_per_frame=5000,
        activation_source="persistent MCP dashboard product runtime",
        host_build_sha256=policy.host_build_sha256,
        code_hashes=policy.code_hashes,
        stop_conditions=stop_conditions,
        acceptance_profile=None,
        path=policy.path,
        raw={},
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save_runtime_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_runtime_state(path: Path = STATE_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


class TransportFactory(Protocol):
    def __call__(self): ...


class ObservedSessionTransport:
    """Telemetry-only wrapper around the accepted Runtime 001 session transport.

    Every operation delegates unchanged. Callbacks run only after a successful Host open
    or frame ACK, so Runtime 002 can publish truthful live state without changing bytes,
    pacing, ACK semantics, session ownership, reconnect/reclaim policy, or device scope.
    """

    def __init__(self, inner, *, on_open: Callable[[dict], None],
                 on_frame: Callable[[dict, int], None]) -> None:
        self.inner = inner
        self.on_open = on_open
        self.on_frame = on_frame
        self.frames_acked = 0

    def open(self, manifest: activity_session.SessionManifest) -> dict:
        opened = self.inner.open(manifest)
        self.on_open(opened)
        return opened

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        ack = self.inner.send_frame(rgb, expected_packet_sha256)
        self.frames_acked += 1
        self.on_frame(ack, self.frames_acked)
        return ack

    def poll_reports(self) -> list[dict]:
        return self.inner.poll_reports()

    def close(self, reason: str) -> dict:
        return self.inner.close(reason)


class ReclaimLimiter:
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self.now = now
        self.events: list[float] = []

    def delay_seconds(self) -> int:
        current = self.now()
        self.events = [at for at in self.events if current - at <= RECLAIM_WINDOW_SECONDS]
        self.events.append(current)
        return RECLAIM_COOLDOWN_SECONDS if len(self.events) > MAX_RECLAIMS_IN_WINDOW else 0


def _collect_waiting(config: dict, state: dict) -> None:
    try:
        mcp_activity.collect_once(config, state, poll_seconds=float(config.get("poll_seconds", 2.0)))
        mcp_activity.save_state(state)
    except Exception:
        # Source health belongs on the display; a source collection problem must never
        # become a reason to hammer Bluetooth or kill the product supervisor.
        pass


def run_product(policy: ProductPolicy, transport_factory: TransportFactory,
                *, stop_requested: Callable[[], bool] = lambda: False,
                sleep: Callable[[float], None] = time.sleep,
                monotonic: Callable[[], float] = time.monotonic,
                max_sessions: int | None = None,
                config: dict | None = None,
                activity_state: dict | None = None,
                state_file: Path = STATE_FILE,
                renderer_factory: Callable[[dict, dict, activity_session.SessionManifest], object] | None = None,
                waiting_collector: Callable[[dict, dict], None] | None = None) -> dict:
    """Run the persistent supervisor. Tests inject every side effect.

    The supervisor never retries *inside* one Host session. Recovery always creates a new,
    uniquely identified bounded session, so every connection epoch remains auditable in
    the existing Host ledger.
    """
    config = config or mcp_activity.load_config()
    activity_state = activity_state or mcp_activity.load_state()
    renderer_factory = renderer_factory or activity_session.live_renderer
    waiting_collector = waiting_collector or _collect_waiting
    started_at = _iso_now()
    backoff_index = 0
    sequence = 0
    run_nonce = secrets.token_hex(4)
    connected_sessions = 0
    reclaims = 0
    reconnects = 0
    limiter = ReclaimLimiter(monotonic)
    runtime_state = {
        "version": 1, "product_id": policy.product_id, "status": "starting",
        "started_at": started_at, "updated_at": started_at, "run_nonce": run_nonce, "session_sequence": 0,
        "connected_sessions": 0, "reclaims": 0, "reconnects": 0,
        "last_terminal_reason": None, "last_outcome": None, "last_error": None,
        "current_experiment_id": None, "retry_in_seconds": None,
        "current_session_opened_at": None, "current_session_frames_acked": 0,
        "last_frame_acked_at": None,
    }

    def persist(**changes) -> None:
        runtime_state.update(changes)
        runtime_state["updated_at"] = _iso_now()
        save_runtime_state(runtime_state, state_file)

    persist(status="running")

    while not stop_requested():
        if max_sessions is not None and sequence >= max_sessions:
            break
        sequence += 1
        experiment_id = f"OPENDITOO-PRODUCT-{run_nonce}-{sequence:06d}"
        manifest = product_session_manifest(policy, experiment_id)
        render = renderer_factory(config, activity_state, manifest)
        inner_transport = transport_factory()
        session_started = monotonic()
        persist(status="connecting", session_sequence=sequence,
                current_experiment_id=experiment_id, retry_in_seconds=None,
                current_session_opened_at=None, current_session_frames_acked=0)

        def session_opened(_opened: dict) -> None:
            persist(status="connected", last_error=None, retry_in_seconds=None,
                    current_session_opened_at=_iso_now(), current_session_frames_acked=0)

        def frame_acked(_ack: dict, count: int) -> None:
            persist(status="connected", last_error=None, retry_in_seconds=None,
                    current_session_frames_acked=count, last_frame_acked_at=_iso_now())

        transport = ObservedSessionTransport(
            inner_transport, on_open=session_opened, on_frame=frame_acked)
        result = activity_session.run_session(
            manifest, transport, render,
            lambda: int((monotonic() - session_started) * 1000),
            lambda ms: sleep(ms / 1000.0),
            claim=None, stop_requested=stop_requested,
        )
        reason = result.get("terminal_reason")
        outcome = result.get("outcome")
        if result.get("frames_sent", 0) > 0:
            connected_sessions += 1
            backoff_index = 0
        persist(status="recovering", connected_sessions=connected_sessions,
                last_terminal_reason=reason, last_outcome=outcome,
                last_error=result.get("detail") or None, current_experiment_id=None,
                current_session_opened_at=None, current_session_frames_acked=0)

        if stop_requested() or reason == "operator_stop":
            break

        if reason == "canvas_invalidated":
            reclaims += 1
            delay = limiter.delay_seconds()
            persist(reclaims=reclaims, status="reclaiming")
            if delay:
                waiting_collector(config, activity_state)
                sleep(delay)
            # Normal button presses reclaim immediately; no reconnect backoff.
            continue

        if reason in {"lifetime_expired", "budget_exhausted"} and outcome == "stopped_clean":
            # Routine bounded-session renewal. The displayed frame persists across the
            # brief socket rollover; the fresh session redraws current state immediately.
            persist(status="renewing")
            continue

        # Genuine Host/device/transport failure: bounded monotonic backoff. Source state
        # is still collected during the wait so reconnect paints current data.
        reconnects += 1
        delay = policy.reconnect_backoff_seconds[min(backoff_index, len(policy.reconnect_backoff_seconds) - 1)]
        backoff_index = min(backoff_index + 1, len(policy.reconnect_backoff_seconds) - 1)
        persist(reconnects=reconnects, status="waiting_for_host_or_device",
                retry_in_seconds=delay)
        deadline = monotonic() + delay
        poll_s = max(0.2, float(config.get("poll_seconds", 2.0)))
        while monotonic() < deadline and not stop_requested():
            waiting_collector(config, activity_state)
            remaining = deadline - monotonic()
            if remaining > 0:
                sleep(min(poll_s, remaining))

    persist(status="stopped", current_experiment_id=None,
            connected_sessions=connected_sessions, reclaims=reclaims, reconnects=reconnects)
    return runtime_state
