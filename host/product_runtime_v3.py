"""Runtime 008 (HF-4): the standing interactive-pages product in ONE streaming session.

Supervisor semantics are Runtime 007's (``product_runtime_v2.run_product``): every Host session is
a fresh, uniquely identified, bounded session; an aged session renews; a Host-confirmed stock yield
(arrow 0x09 / lever 0xBD) is reclaimed immediately behind the same ``ReclaimLimiter`` storm guard;
genuine unavailability waits on the same bounded monotonic backoff while MCP collection continues.

What changed is the session shape, exactly as accepted by HF-3 (``OPENDITOO-INTERACTIVE-HF3-008``):
- every page lives in one ``PageCarousel`` inside one ``streaming_ack_clock`` Host session, and
  Left/Right change pixels only -- never a Host close/reopen to change pages (HF3-002);
- ``run_interactive_stream`` paces it with ``InteractiveTransport`` (50 ms client floor plus the
  45 ms Host-anchored gap, HF3-004/005) and its Host-confirmed yield rule (HF3-006/007);
- the low-rate dashboard (UI-1 lightning) is held to ~200 ms change-only inside that session, and
  its collection runs on a joined worker while Slots is visible;
- page, game and input state live on the carousel/driver, above every Host session, so reclaim,
  renewal and reconnect never reset a page or re-apply an input.

A pulse that is hidden, or in flight when the device goes away, is dropped, never replayed.
Authority is the local mode-0600 policy only; the committed template stays unauthorized.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from typing import Callable

from host import activity_session, frame_stream, interactive_stream, mcp_activity, pagination, product_runtime_v2
from host.activity_lightning_renderer import LightningActivityRenderer
from host.dashboard_page import DashboardPage
from host.interactive_pages import BufferedButtonEvents, InteractivePageDriver, PageCarousel
from host.product_runtime_v2 import ObservedSessionTransport, ProductPolicyError, ReclaimLimiter, read_runtime_state  # noqa: F401
from host.slots_page import SlotsPage

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REVISION = 4
EXACT_UNIT_ID = activity_session.EXACT_UNIT_ID
TEMPLATE = ROOT / "product" / "OPENDITOO-PRODUCT-RUNTIME-008.json"
R007_TEMPLATE = ROOT / "product" / "OPENDITOO-PRODUCT-RUNTIME-007.json"
GRANT_TEXT = "Grant OPENDITOO-PRODUCT-RUNTIME-008"
STATE_FILE = product_runtime_v2.STATE_FILE
PAGES_STATE_FILE = pagination.PAGES_STATE_FILE  # product-status already reads this path

PAGES = [
    {"name": "dashboard", "kind": "live_mcp_dashboard_lightning", "rate_mode": frame_stream.SESSION_PROFILE_ACTIVITY,
     "lever": "none"},
    {"name": "slots", "kind": "slots_three_reel", "rate_mode": frame_stream.SESSION_PROFILE_STREAMING,
     "lever": "stop the next reel; after the third, start a new round"},
]
# The whole session envelope is pinned here, not merely in the policy. 600 s / 15000 frames sits
# inside the Host's own streaming ceiling (1800 s / 45000); lifetime, not frames, is the normal
# rollover (~18 fps x 600 s < 15000), and a rollover is a Host close of an aged link (proven safe).
SESSION = {
    "session_profile": frame_stream.SESSION_PROFILE_STREAMING,
    "lifetime_seconds": 600,
    "max_frames": 15000,
    "max_tx_bytes": 15000 * frame_stream.worst_case_frame_tx_bytes(),
    "host_floor_ms": frame_stream.STREAMING_HOST_FLOOR_MS,
    "client_min_dispatch_ms": interactive_stream.CLIENT_MIN_DISPATCH_MS,
    "host_anchored_gap_ms": interactive_stream.HOST_ANCHORED_GAP_MS,
    "low_rate_interval_ms": activity_session.MCP_CLIENT_FRAME_INTERVAL_MS,
    "idle_poll_interval_ms": 50,
    "pulse_freshness_seconds": 30,
    "ack_timeout_ms_per_frame": 5000,
}
HASHED_MODULES = {
    "product_runtime_v3_sha256": ROOT / "host/product_runtime_v3.py",
    "pagination_sha256": ROOT / "host/pagination.py",
    "cli_sha256": ROOT / "cli/openditoo.py",
    "frame_stream_sha256": ROOT / "host/frame_stream.py",
    "interactive_pages_sha256": ROOT / "host/interactive_pages.py",
    "interactive_stream_sha256": ROOT / "host/interactive_stream.py",
    "dashboard_page_sha256": ROOT / "host/dashboard_page.py",
    "slots_page_sha256": ROOT / "host/slots_page.py",
    "activity_lightning_sha256": ROOT / "host/activity_lightning.py",
    "activity_lightning_renderer_sha256": ROOT / "host/activity_lightning_renderer.py",
    "encoder_sha256": ROOT / "host/ditoo_pixel_coloring.py",
}
TELEMETRY_PERSIST_SECONDS = 1.0
FPS_WINDOW_SECONDS = 5.0


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_hashes() -> dict[str, str]:
    # Runtime 007's session/renderer/collector/ui-data set and product_runtime_v2 (reused
    # supervisor pieces), plus everything that can change Runtime 008 pixels, input or pacing.
    hashes = product_runtime_v2.runtime_hashes()
    hashes.update({name: _sha(path) for name, path in HASHED_MODULES.items()})
    return hashes


@dataclass(frozen=True)
class StandingPolicy(product_runtime_v2.ProductPolicy):
    raw: dict = field(default_factory=dict)


def _require(ok: bool, code: str, detail: str = "") -> None:
    if not ok:
        raise ProductPolicyError(code, detail)


def authority_blockers(path: Path) -> list[str]:
    try:
        authority = json.loads(Path(path).read_text(encoding="utf-8")).get("authority") or {}
    except (OSError, json.JSONDecodeError):
        return ["PRODUCT_POLICY_UNREADABLE"]
    blockers = []
    if authority.get("persistent_runtime_authorized") is not True:
        blockers.append("PRODUCT_AUTHORITY_MISSING")
    if authority.get("revoked") is True:
        blockers.append("PRODUCT_AUTHORITY_REVOKED")
    if authority.get("grant_text") != GRANT_TEXT or not authority.get("granted_by"):
        blockers.append("PRODUCT_AUTHORITY_UNATTRIBUTED")
    if authority.get("grant_scope") != authority.get("grant_scope_requested"):
        blockers.append("PRODUCT_AUTHORITY_SCOPE_MISMATCH")
    return blockers


def load_policy(path: Path, *, require_authority: bool = True, verify_hashes: bool = True,
                template_path: Path = TEMPLATE) -> StandingPolicy:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        template = json.loads(Path(template_path).read_text(encoding="utf-8"))
        r007 = json.loads(R007_TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductPolicyError("PRODUCT_POLICY_UNREADABLE", str(exc)) from exc
    _require(raw.get("runtime_revision") == RUNTIME_REVISION, "PRODUCT_RUNTIME_REVISION_MISMATCH")
    _require({k: v for k, v in raw.items() if k != "authority"} == {k: v for k, v in template.items() if k != "authority"},
             "PRODUCT_POLICY_DRIFTED_FROM_TEMPLATE")
    # Pins that hold even if the committed template itself is edited.
    _require(raw.get("pages") == PAGES, "PRODUCT_008_PAGES_MISMATCH")
    _require(raw.get("session") == SESSION, "PRODUCT_008_ENVELOPE_MISMATCH")
    for key in ("target", "behavior", "product_id", "install"):
        _require(raw.get(key) == r007[key], "PRODUCT_008_WIDENS_007", key)
    _require((raw.get("pagination") or {}).get("broker") == r007["pagination"]["broker"]
             and (raw.get("build") or {}).get("button_probe_sha256") == r007["build"]["button_probe_sha256"]
             and (raw.get("build") or {}).get("host_dll_sha256") == r007["build"]["host_dll_sha256"],
             "PRODUCT_008_CHANGES_INPUT_OR_HOST")
    if require_authority:
        blockers = authority_blockers(path)
        _require(not blockers, blockers[0] if blockers else "")
    build = raw["build"]
    _require(set(build.get("code_sha256") or {}) == set(code_hashes()), "PRODUCT_CODE_HASH_SET_MISMATCH")
    if verify_hashes:
        _require(code_hashes() == build["code_sha256"], "PRODUCT_CODE_HASH_MISMATCH",
                 json.dumps({"expected": build["code_sha256"], "actual": code_hashes()}, sort_keys=True))
        _require(activity_session.sha256_file(activity_session.HOST_BUILD_DLL) == build["host_dll_sha256"],
                 "PRODUCT_HOST_HASH_MISMATCH")
        for name, digest in build["button_probe_sha256"].items():
            _require(_sha(pagination.windows_path(name)) == digest, "PRODUCT_BUTTON_PROBE_HASH_MISMATCH", name)
    behavior = raw["behavior"]
    return StandingPolicy(
        path=Path(path), product_id=raw["product_id"],
        session_lifetime_seconds=SESSION["lifetime_seconds"], min_frame_interval_ms=SESSION["host_floor_ms"],
        poll_interval_ms=SESSION["idle_poll_interval_ms"], pulse_freshness_seconds=SESSION["pulse_freshness_seconds"],
        max_frames_per_session=SESSION["max_frames"], max_tx_bytes_per_session=SESSION["max_tx_bytes"],
        reconnect_backoff_seconds=tuple(behavior["reconnect_backoff_seconds"]),
        reclaim_on_canvas_invalidated=True, automatic_reconnect=True, start_at_windows_logon=True,
        code_hashes=build["code_sha256"], host_build_sha256=build["host_dll_sha256"],
        authority_grant_text=str((raw.get("authority") or {}).get("grant_text") or ""), raw=raw)


def session_manifest(policy: StandingPolicy, experiment_id: str) -> activity_session.SessionManifest:
    return activity_session.SessionManifest(
        experiment_id=experiment_id,
        lifetime_seconds=policy.session_lifetime_seconds,
        min_frame_interval_ms=SESSION["host_floor_ms"],
        pulse_freshness_seconds=policy.pulse_freshness_seconds,
        poll_interval_ms=SESSION["idle_poll_interval_ms"],
        max_frames=policy.max_frames_per_session,
        max_application_packets=policy.max_frames_per_session * activity_session.PACKETS_PER_FRAME,
        max_tx_bytes=policy.max_tx_bytes_per_session,
        ack_timeout_ms_per_frame=SESSION["ack_timeout_ms_per_frame"],
        activation_source="persistent Runtime 008 interactive pages product",
        host_build_sha256=policy.host_build_sha256,
        code_hashes=policy.code_hashes,
        stop_conditions=("Host session lifetime/budget reached: fresh bounded session",
                         "Host-confirmed stock yield: immediate reclaim of the same page",
                         "transport/Host/device unavailable: bounded reconnect backoff",
                         "worker stop requested"),
        acceptance_profile=None,
        path=policy.path,
        raw={"stream": {"session_profile": SESSION["session_profile"]}},
    )


class _SupervisedEvents:
    """The ButtonProbe cursor, restarting a dead probe (rate-limited) before each poll."""

    def __init__(self, events, broker) -> None:
        self.events, self.broker = events, broker

    def poll(self) -> list[dict]:
        if self.broker is not None:
            self.broker.ensure()
        return self.events.poll()


def run_product(policy: StandingPolicy, transport_factory, *, stop_requested: Callable[[], bool] = lambda: False,
                sleep: Callable[[float], None] = time.sleep, monotonic: Callable[[], float] = time.monotonic,
                max_sessions: int | None = None, config: dict | None = None, activity_state: dict | None = None,
                state_file: Path = STATE_FILE, pages_state_file: Path = PAGES_STATE_FILE,
                events=None, broker=None, pages: list | None = None,
                waiting_collector: Callable[[], None] | None = None) -> dict:
    """Run the standing supervisor. Tests inject every side effect."""
    config = config if config is not None else mcp_activity.load_config()
    activity_state = activity_state if activity_state is not None else mcp_activity.load_state()
    started = monotonic()
    clock = lambda: int((monotonic() - started) * 1000)  # one run clock: pages outlive sessions
    sleep_ms = lambda ms: sleep(ms / 1000.0)

    probe = policy.raw["pagination"]["broker"]
    if broker is None and events is None:
        broker = pagination.Broker(pagination.windows_path(probe["exe"]), probe["events_windows_path"],
                                   ROOT / probe["events_file"], monotonic=monotonic)
    if broker is not None:
        broker.ensure()
    events = events if events is not None else pagination.ButtonEvents(ROOT / probe["events_file"])
    if pages is None:
        pages = [DashboardPage(config, activity_state, renderer=LightningActivityRenderer(config, activity_state)),
                 SlotsPage()]
    carousel = PageCarousel(pages, low_rate_interval_ms=SESSION["low_rate_interval_ms"], background_thread=True)
    driver = InteractivePageDriver(carousel, BufferedButtonEvents(_SupervisedEvents(events, broker)), monotonic)

    def collect_waiting() -> None:
        # No display while waiting: collection continues so reconnect paints current data, and
        # any pulse it discovers is dropped (DashboardPage.background_tick), never replayed.
        carousel._join_worker()
        for page in carousel.pages:
            try:
                getattr(page, "background_tick", lambda _now: None)(clock())
            except Exception:
                pass  # a source problem must never hammer Bluetooth or kill the supervisor
    waiting_collector = waiting_collector or collect_waiting

    run_nonce = secrets.token_hex(4)
    limiter = ReclaimLimiter(monotonic)
    backoff_index = sequence = 0
    ack_times: deque[float] = deque()
    last_persist = [float("-inf")]
    runtime_state = {
        "version": 1, "product_id": policy.product_id, "runtime_revision": RUNTIME_REVISION,
        "status": "starting", "started_at": _utc(), "updated_at": _utc(), "run_nonce": run_nonce,
        "session_sequence": 0, "session_profile": SESSION["session_profile"],
        "connected_sessions": 0, "reclaims": 0, "reconnects": 0, "renewals": 0,
        "last_terminal_reason": None, "last_outcome": None, "last_error": None,
        "current_experiment_id": None, "retry_in_seconds": None,
        "current_session_opened_at": None, "current_session_frames_acked": 0,
        "last_frame_acked_at": None, "realized_fps_5s": None,
    }

    def persist(**changes) -> None:
        runtime_state.update(changes)
        runtime_state["updated_at"] = _utc()
        product_runtime_v2.save_runtime_state(runtime_state, state_file)
        last_persist[0] = monotonic()

    def publish() -> None:
        actions = [{k: a.get(k) for k in ("seq", "epoch", "type", "raw_button", "result", "first_ack_ms")}
                   for a in driver.actions[-5:]]
        slots = next((p.telemetry() for p in carousel.pages if p.name == "slots"), None)
        state = {"updated_at": _utc(), "runtime_revision": RUNTIME_REVISION,
                 "current_page": carousel.page.name, "pages": [p.name for p in carousel.pages],
                 "page_transitions": carousel.page_transitions,
                 "input_broker_alive": broker.alive if broker else None,
                 "broker_starts": broker.starts if broker else 0,
                 "input_epoch": getattr(events, "epoch", None), "last_input_seq": getattr(events, "last_seq", None),
                 "input_gaps": getattr(events, "gaps", 0), "inputs_applied": driver.inputs_consumed,
                 "last_input": actions[-1] if actions else None, "recent_actions": actions,
                 "slots": None if slots is None else {k: slots[k] for k in ("round", "state", "stopped_reels", "result")}}
        tmp = pages_state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(pages_state_file)

    def session_opened(_opened: dict) -> None:
        persist(status="connected", last_error=None, retry_in_seconds=None,
                current_session_opened_at=_utc(), current_session_frames_acked=0)

    def frame_acked(_ack: dict, count: int) -> None:
        now = monotonic()
        ack_times.append(now)
        while ack_times and ack_times[0] < now - FPS_WINDOW_SECONDS:
            ack_times.popleft()
        runtime_state.update(current_session_frames_acked=count, last_frame_acked_at=_utc(),
                             realized_fps_5s=round(len(ack_times) / FPS_WINDOW_SECONDS, 2))
        # First ACK after any newly applied input: stamp it and publish now (the Runtime 006
        # telemetry only published on input, so the last transition's first_ack_ms stayed null).
        fresh = [a for a in driver.actions[-5:] if "first_ack_ms" not in a]
        for action in fresh:
            action["first_ack_ms"] = round((now - action["applied_at_monotonic"]) * 1000, 1)
        if fresh:
            runtime_state["last_input_to_first_ack_ms"] = fresh[-1]["first_ack_ms"]
            publish()
        if fresh or now - last_persist[0] >= TELEMETRY_PERSIST_SECONDS:
            persist(status="connected", last_error=None)

    persist(status="running")
    publish()
    try:
        while not stop_requested():
            if max_sessions is not None and sequence >= max_sessions:
                break
            sequence += 1
            experiment_id = f"OPENDITOO-PRODUCT-{run_nonce}-{sequence:06d}"
            persist(status="connecting", session_sequence=sequence, current_experiment_id=experiment_id,
                    retry_in_seconds=None, current_session_opened_at=None, current_session_frames_acked=0)
            transport = ObservedSessionTransport(transport_factory(), on_open=session_opened, on_frame=frame_acked)
            result = interactive_stream.run_interactive_stream(
                session_manifest(policy, experiment_id),
                {"session_profile": SESSION["session_profile"],
                 "playback_interval_ms": frame_stream.STREAMING_MIN_PLAYBACK_INTERVAL_MS,
                 "idle_poll_interval_ms": SESSION["idle_poll_interval_ms"]},
                transport, clock, sleep_ms, driver, stop_requested=stop_requested,
                background_tick=carousel.background_tick)
            reason, outcome = result.get("terminal_reason"), result.get("outcome")
            if result.get("frames_sent", 0) > 0:
                runtime_state["connected_sessions"] += 1
                backoff_index = 0
            ack_times.clear()
            persist(status="recovering", last_terminal_reason=reason, last_outcome=outcome,
                    last_error=result.get("detail") or None, current_experiment_id=None,
                    current_session_opened_at=None, current_session_frames_acked=0, realized_fps_5s=None)
            publish()

            if stop_requested() or reason == "operator_stop":
                break
            if reason == "canvas_invalidated" and outcome in ("stopped_yielded_to_stock", "stopped_clean"):
                delay = limiter.delay_seconds()
                persist(reclaims=runtime_state["reclaims"] + 1, status="reclaiming")
                if delay:
                    waiting_collector()
                    sleep(delay)
                continue  # a button press reclaims immediately; the page resumes untouched
            if reason in ("lifetime_expired", "budget_exhausted") and outcome == "stopped_clean":
                persist(renewals=runtime_state["renewals"] + 1, status="renewing")
                continue
            # Genuine Host/device/transport failure (or an ambiguous send): no retry inside the
            # session; bounded monotonic backoff before a fresh one. An in-flight pulse is stale
            # after a multi-second outage, so it is dropped rather than resumed on reconnect.
            for page in carousel.pages:
                getattr(page, "drop_pulse", lambda: None)()
            backoff = policy.reconnect_backoff_seconds
            delay = backoff[min(backoff_index, len(backoff) - 1)]
            backoff_index = min(backoff_index + 1, len(backoff) - 1)
            persist(reconnects=runtime_state["reconnects"] + 1, status="waiting_for_host_or_device",
                    retry_in_seconds=delay)
            deadline = monotonic() + delay
            poll_s = max(0.2, float(config.get("poll_seconds", 2.0)))
            while monotonic() < deadline and not stop_requested():
                waiting_collector()
                remaining = deadline - monotonic()
                if remaining > 0:
                    sleep(min(poll_s, remaining))
    finally:
        carousel._join_worker()  # never exit mid-collection (it persists activity state)
        if broker is not None:
            broker.stop()
        persist(status="stopped", current_experiment_id=None)
        publish()
    return runtime_state

