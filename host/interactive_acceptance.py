"""HF-3 one-use acceptance envelope for interactive profile/page switching.

One outer experiment id/grant covers a bounded sequence of uniquely identified Host child
sessions needed to exercise Dashboard <-> Slots profile switching. The outer SessionClaim is
consumed before any child transport opens. A clean page transition, bounded clean renewal, or
the exact known ``canvas_invalidated/stopped_yielded_to_stock`` outcome may advance to a fresh
child session. Any ambiguous open/send/transport failure ends the outer experiment immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable

from host import activity_session, frame_stream
from host.interactive_activity import run_interactive_activity
from host.interactive_pages import BufferedButtonEvents, RATE_ACTIVITY, RATE_STREAMING
from host.interactive_runtime import ProfilePageOrchestrator
from host.interactive_stream import run_interactive_stream

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KIND = "interactive_page_acceptance"
EXPERIMENT_ID = "OPENDITOO-INTERACTIVE-HF3-002"
REQUIRED_GRANT_TEXT = f"Grant {EXPERIMENT_ID}"
HOST_BUILD = activity_session.HOST_BUILD_DLL
BUTTON_PROBE_EXE = Path("/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo/ButtonProbe/OpenDitoo.ButtonProbe.exe")
BUTTON_PROBE_DLL = Path("/mnt/c/Users/Wanstation/AppData/Local/OpenDitoo/ButtonProbe/OpenDitoo.ButtonProbe.dll")

# Source that can influence pixels, state, input routing, or child-session behavior.
HASHED_MODULES = {
    "interactive_acceptance_sha256": ROOT / "host/interactive_acceptance.py",
    "interactive_pages_sha256": ROOT / "host/interactive_pages.py",
    "interactive_runtime_sha256": ROOT / "host/interactive_runtime.py",
    "interactive_stream_sha256": ROOT / "host/interactive_stream.py",
    "interactive_activity_sha256": ROOT / "host/interactive_activity.py",
    "dashboard_page_sha256": ROOT / "host/dashboard_page.py",
    "slots_page_sha256": ROOT / "host/slots_page.py",
    "activity_lightning_sha256": ROOT / "host/activity_lightning.py",
    "activity_lightning_renderer_sha256": ROOT / "host/activity_lightning_renderer.py",
    "frame_stream_sha256": ROOT / "host/frame_stream.py",
    "activity_session_sha256": ROOT / "host/activity_session.py",
    "activity_render_sha256": ROOT / "host/activity_render.py",
    "activity_ui_data_sha256": ROOT / "host/activity_ui_data.py",
    "mcp_activity_sha256": ROOT / "host/mcp_activity.py",
    "encoder_sha256": ROOT / "host/ditoo_pixel_coloring.py",
    "pagination_input_sha256": ROOT / "host/pagination.py",
    "cli_transport_sha256": ROOT / "cli/openditoo.py",
    "hf3_entry_sha256": ROOT / "scripts/interactive_hf3.py",
    "hf3_coordinator_sha256": ROOT / "scripts/run_interactive_hf3.sh",
}


class AcceptanceError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _require(ok: bool, code: str, detail: str = "") -> None:
    if not ok:
        raise AcceptanceError(code, detail)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_hashes() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in HASHED_MODULES.items()}


def authority_blockers(path: Path, now: datetime | None = None) -> list[str]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["MANIFEST_UNREADABLE"]
    authority = raw.get("authority") or {}
    blockers: list[str] = []
    if authority.get("transmission_authorized") is not True:
        blockers.append("TRANSMISSION_AUTHORITY_MISSING")
    if authority.get("authorization_consumed") is True:
        blockers.append("AUTHORITY_ALREADY_CONSUMED")
    if authority.get("grant_text") != REQUIRED_GRANT_TEXT or not authority.get("granted_by"):
        blockers.append("AUTHORITY_GRANT_UNATTRIBUTED")
    expires = authority.get("expires_at")
    if not isinstance(expires, str) or not expires:
        blockers.append("AUTHORITY_EXPIRY_MISSING")
    else:
        try:
            parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            current = now or datetime.now(timezone.utc)
            if parsed <= current:
                blockers.append("AUTHORITY_EXPIRED")
        except ValueError:
            blockers.append("AUTHORITY_EXPIRY_UNREADABLE")
    return blockers


@dataclass(frozen=True)
class AcceptanceManifest:
    path: Path
    raw: dict
    experiment_id: str
    lifetime_seconds: int
    max_child_sessions: int
    max_frames: int
    max_tx_bytes: int
    activity_child_max_frames: int
    streaming_child_max_frames: int
    target_profile_cycles: int
    host_dll_sha256: str
    button_probe_sha256: dict[str, str]

    def child_experiment_id(self, sequence: int) -> str:
        if not 1 <= sequence <= self.max_child_sessions:
            raise AcceptanceError("CHILD_SESSION_SEQUENCE_INVALID", str(sequence))
        return f"{self.experiment_id}-S{sequence:03d}"


def load_manifest(path: Path, *, verify_hashes: bool = True,
                  verify_button_probe: bool = True,
                  require_authority: bool = True,
                  now: datetime | None = None) -> AcceptanceManifest:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError("MANIFEST_UNREADABLE", str(exc)) from exc
    _require(raw.get("schema_version") == SCHEMA_VERSION, "MANIFEST_SCHEMA_VERSION")
    _require(raw.get("kind") == KIND, "MANIFEST_KIND_MISMATCH")
    _require(raw.get("experiment_id") == EXPERIMENT_ID, "MANIFEST_EXPERIMENT_ID_MISMATCH")

    target = raw.get("target") or {}
    _require(target.get("exact_unit_id") == activity_session.EXACT_UNIT_ID, "MANIFEST_TARGET_MISMATCH")
    _require(target.get("installed_firmware") == activity_session.INSTALLED_FIRMWARE,
             "MANIFEST_FIRMWARE_MISMATCH")
    _require(target.get("rfcomm_channel") == 1, "MANIFEST_RFCOMM_CHANNEL_MISMATCH")
    _require(target.get("target_override_enabled") is False, "MANIFEST_TARGET_OVERRIDE_ENABLED")

    transport = raw.get("transport") or {}
    _require(transport.get("measured_endpoint") == "Windows Classic RFCOMM channel 1",
             "MANIFEST_ENDPOINT_UNBOUND")
    _require(transport.get("one_controller") is True, "MANIFEST_ONE_CONTROLLER_MISSING")
    _require(transport.get("raw_send_enabled") is False, "MANIFEST_RAW_SEND_ENABLED")
    _require(transport.get("pipelining") is False, "MANIFEST_PIPELINING_ENABLED")
    _require(transport.get("retry_after_ambiguous") is False, "MANIFEST_RETRY_ENABLED")
    _require(transport.get("allowed_session_profiles") == [RATE_ACTIVITY, RATE_STREAMING],
             "MANIFEST_PROFILE_SET_MISMATCH")

    acceptance = raw.get("acceptance") or {}
    lifetime = acceptance.get("lifetime_seconds")
    max_sessions = acceptance.get("max_child_sessions")
    max_frames = acceptance.get("max_total_frames")
    max_tx = acceptance.get("max_total_tx_bytes")
    activity_child = acceptance.get("activity_child_max_frames")
    streaming_child = acceptance.get("streaming_child_max_frames")
    cycles = acceptance.get("target_profile_cycles")
    _require(isinstance(lifetime, int) and 1 <= lifetime <= 180, "ACCEPTANCE_LIFETIME_INVALID")
    _require(isinstance(max_sessions, int) and 4 <= max_sessions <= 48,
             "ACCEPTANCE_SESSION_BUDGET_INVALID")
    _require(isinstance(max_frames, int) and 1 <= max_frames <= 1500,
             "ACCEPTANCE_FRAME_BUDGET_INVALID")
    _require(isinstance(max_tx, int) and max_tx == max_frames * frame_stream.worst_case_frame_tx_bytes(),
             "ACCEPTANCE_TX_BUDGET_NOT_DERIVED")
    _require(isinstance(activity_child, int) and 1 <= activity_child <= max_frames,
             "ACCEPTANCE_ACTIVITY_CHILD_BUDGET_INVALID")
    _require(isinstance(streaming_child, int) and 1 <= streaming_child <= max_frames,
             "ACCEPTANCE_STREAMING_CHILD_BUDGET_INVALID")
    _require(cycles == 10, "ACCEPTANCE_CYCLE_TARGET_MISMATCH")
    _require(acceptance.get("long_lever_holds_mapped") is False, "ACCEPTANCE_LONG_HOLD_MAPPED")

    build = raw.get("build") or {}
    code_hashes = build.get("code_sha256") or {}
    _require(set(code_hashes) == set(HASHED_MODULES), "BUILD_CODE_HASH_SET_MISMATCH")
    host_hash = build.get("host_dll_sha256")
    _require(isinstance(host_hash, str) and len(host_hash) == 64, "BUILD_HOST_HASH_MISSING")
    probe_hashes = build.get("button_probe_sha256") or {}
    expected_probe_keys = {str(BUTTON_PROBE_EXE), str(BUTTON_PROBE_DLL)}
    _require(set(probe_hashes) == expected_probe_keys, "BUILD_BUTTON_PROBE_HASH_SET_MISMATCH")
    if verify_hashes:
        _require(module_hashes() == code_hashes, "BUILD_CODE_HASH_MISMATCH")
        _require(HOST_BUILD.is_file() and sha256_file(HOST_BUILD) == host_hash, "BUILD_HOST_HASH_MISMATCH")
    if verify_button_probe:
        for filename, expected in probe_hashes.items():
            candidate = Path(filename)
            _require(candidate.is_file() and sha256_file(candidate) == expected,
                     "BUILD_BUTTON_PROBE_HASH_MISMATCH", filename)

    authority = raw.get("authority") or {}
    _require(authority.get("required_grant_text") == REQUIRED_GRANT_TEXT,
             "AUTHORITY_REQUIRED_GRANT_MISMATCH")
    if require_authority:
        blockers = authority_blockers(path, now)
        _require(not blockers, blockers[0] if blockers else "TRANSMISSION_AUTHORITY_MISSING",
                 ",".join(blockers))

    return AcceptanceManifest(
        path=Path(path), raw=raw, experiment_id=EXPERIMENT_ID,
        lifetime_seconds=lifetime, max_child_sessions=max_sessions,
        max_frames=max_frames, max_tx_bytes=max_tx,
        activity_child_max_frames=activity_child, streaming_child_max_frames=streaming_child,
        target_profile_cycles=cycles, host_dll_sha256=host_hash,
        button_probe_sha256=dict(probe_hashes),
    )


def child_manifest(manifest: AcceptanceManifest, sequence: int, rate_mode: str,
                   remaining_frames: int, remaining_tx_bytes: int,
                   remaining_lifetime_seconds: int) -> activity_session.SessionManifest:
    """Derive one Host child envelope entirely from the frozen outer budget."""
    _require(rate_mode in (RATE_ACTIVITY, RATE_STREAMING), "CHILD_PROFILE_INVALID")
    _require(remaining_frames > 0 and remaining_tx_bytes > 0 and remaining_lifetime_seconds > 0,
             "CHILD_BUDGET_EXHAUSTED")
    per_child = (manifest.streaming_child_max_frames if rate_mode == RATE_STREAMING
                 else manifest.activity_child_max_frames)
    max_frames = min(remaining_frames, per_child, activity_session.MAX_SESSION_FRAMES)
    max_tx = min(remaining_tx_bytes, max_frames * frame_stream.worst_case_frame_tx_bytes())
    if rate_mode == RATE_STREAMING:
        floor = frame_stream.STREAMING_HOST_FLOOR_MS
        poll = 10
        raw = {"stream": {"session_profile": RATE_STREAMING}}
        source = "HF-3 interactive slots high-rate child session"
    else:
        floor = activity_session.ACCEPTED_MIN_FRAME_INTERVAL_MS
        poll = 50
        raw = {}
        source = "HF-3 MCP dashboard low-rate child session"
    return activity_session.SessionManifest(
        experiment_id=manifest.child_experiment_id(sequence),
        lifetime_seconds=min(remaining_lifetime_seconds, 60),
        min_frame_interval_ms=floor,
        pulse_freshness_seconds=30,
        poll_interval_ms=poll,
        max_frames=max_frames,
        max_application_packets=max_frames * activity_session.PACKETS_PER_FRAME,
        max_tx_bytes=max_tx,
        ack_timeout_ms_per_frame=5000,
        activation_source=source,
        host_build_sha256=manifest.host_dll_sha256,
        code_hashes={},
        stop_conditions=("page_transition", "canvas_invalidated", "transport_fault",
                         "lifetime_expired", "budget_exhausted", "operator_stop"),
        acceptance_profile=None,
        path=manifest.path,
        raw=raw,
    )


class OuterBudget:
    """Cross-child ceiling. Attempts are counted before open; frames/bytes only after ACK."""
    def __init__(self, manifest: AcceptanceManifest) -> None:
        self.manifest = manifest
        self.child_attempts = 0
        self.child_opens = 0
        self.frames_acked = 0
        self.tx_bytes_acked = 0
        self.child_ids: list[str] = []
        self.open_events: list[dict] = []
        self.ack_events: list[dict] = []

    @property
    def remaining_frames(self) -> int:
        return self.manifest.max_frames - self.frames_acked

    @property
    def remaining_tx_bytes(self) -> int:
        return self.manifest.max_tx_bytes - self.tx_bytes_acked

    def before_open(self, experiment_id: str, *, profile: str, at_monotonic: float) -> None:
        if self.child_attempts >= self.manifest.max_child_sessions:
            raise AcceptanceError("OUTER_CHILD_SESSION_BUDGET_EXHAUSTED")
        if experiment_id in self.child_ids:
            raise AcceptanceError("OUTER_CHILD_SESSION_REPLAY", experiment_id)
        self.child_attempts += 1
        self.child_ids.append(experiment_id)
        self.open_events.append({"child_experiment_id": experiment_id, "session_profile": profile,
                                 "attempted_at_monotonic": at_monotonic, "opened_at_monotonic": None})

    def session_opened(self, experiment_id: str, *, at_monotonic: float) -> None:
        self.child_opens += 1
        for event in reversed(self.open_events):
            if event["child_experiment_id"] == experiment_id:
                event["opened_at_monotonic"] = at_monotonic
                break

    def before_frame(self, frame_bytes: int) -> None:
        if self.frames_acked + 1 > self.manifest.max_frames:
            raise AcceptanceError("OUTER_FRAME_BUDGET_EXHAUSTED")
        if self.tx_bytes_acked + frame_bytes > self.manifest.max_tx_bytes:
            raise AcceptanceError("OUTER_TX_BUDGET_EXHAUSTED")

    def frame_acked(self, frame_bytes: int, *, child_experiment_id: str, profile: str,
                    at_monotonic: float) -> None:
        self.frames_acked += 1
        self.tx_bytes_acked += frame_bytes
        self.ack_events.append({"frame": self.frames_acked, "child_experiment_id": child_experiment_id,
                                "session_profile": profile, "acked_at_monotonic": at_monotonic,
                                "application_bytes": frame_bytes})

    def snapshot(self) -> dict:
        return {
            "child_attempts": self.child_attempts,
            "child_opens": self.child_opens,
            "frames_acked": self.frames_acked,
            "tx_bytes_acked": self.tx_bytes_acked,
            "remaining_frames": self.remaining_frames,
            "remaining_tx_bytes": self.remaining_tx_bytes,
            "child_ids": list(self.child_ids),
            "open_events": list(self.open_events),
            "ack_events": list(self.ack_events),
        }


class BudgetedTransport:
    """Delegate unchanged while enforcing the outer ceiling around successful ACKs."""
    def __init__(self, inner, budget: OuterBudget, clock_seconds: Callable[[], float]) -> None:
        self.inner = inner
        self.budget = budget
        self.clock_seconds = clock_seconds
        self.child_experiment_id: str | None = None
        self.profile = RATE_ACTIVITY

    def open(self, child) -> dict:
        self.child_experiment_id = child.experiment_id
        self.profile = (child.raw.get("stream") or {}).get("session_profile", RATE_ACTIVITY)
        self.budget.before_open(child.experiment_id, profile=self.profile,
                                at_monotonic=self.clock_seconds())
        opened = self.inner.open(child)
        self.budget.session_opened(child.experiment_id, at_monotonic=self.clock_seconds())
        return opened

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        wire, _ = frame_stream.encode_rgb888_static_image(rgb)
        frame_bytes = len(wire) + frame_stream.PREAMBLE_BYTES
        self.budget.before_frame(frame_bytes)
        ack = self.inner.send_frame(rgb, expected_packet_sha256)
        assert self.child_experiment_id is not None
        self.budget.frame_acked(frame_bytes, child_experiment_id=self.child_experiment_id,
                                profile=self.profile, at_monotonic=self.clock_seconds())
        return ack

    def poll_reports(self):
        return self.inner.poll_reports()

    def close(self, reason: str):
        return self.inner.close(reason)


def run_acceptance(manifest: AcceptanceManifest, pages: list, events: BufferedButtonEvents,
                   transport_factory: Callable[[], object], clock: Callable[[], int],
                   sleep: Callable[[int], None], *, stop_requested: Callable[[], bool] = lambda: False,
                   budget: OuterBudget | None = None) -> dict:
    """Run the bounded HF-3 child-session choreography under one already-reviewed envelope.

    This function creates no grant/claim itself so offline dry-runs are side-effect free. The live
    coordinator must consume the outer SessionClaim *before* calling here.
    """
    _require([(page.name, page.rate_mode) for page in pages] == [
        ("dashboard", RATE_ACTIVITY), ("slots", RATE_STREAMING)],
        "ACCEPTANCE_PAGE_SET_MISMATCH")
    budget = budget or OuterBudget(manifest)
    started_ms = clock()
    child_results: list[dict] = []
    orchestrator: ProfilePageOrchestrator | None = None

    def remaining_lifetime() -> int:
        elapsed = max(0, clock() - started_ms)
        return max(0, math.ceil((manifest.lifetime_seconds * 1000 - elapsed) / 1000))

    def runner_for(rate_mode: str):
        def runner(driver):
            if stop_requested():
                return {"terminal_reason": "operator_stop", "outcome": "stopped_clean",
                        "detail": "external stop requested"}
            life = remaining_lifetime()
            if life <= 0:
                return {"terminal_reason": "outer_lifetime_expired", "outcome": "stopped_clean"}
            if budget.remaining_frames <= 0 or budget.remaining_tx_bytes <= 0:
                return {"terminal_reason": "outer_budget_exhausted", "outcome": "stopped_clean"}
            if budget.child_attempts >= manifest.max_child_sessions:
                return {"terminal_reason": "outer_budget_exhausted", "outcome": "stopped_clean",
                        "detail": "child-session ceiling reached"}
            assert orchestrator is not None
            sequence = budget.child_attempts + 1
            child = child_manifest(manifest, sequence, rate_mode, budget.remaining_frames,
                                   budget.remaining_tx_bytes, life)
            transport = BudgetedTransport(transport_factory(), budget, lambda: clock() / 1000.0)
            if rate_mode == RATE_STREAMING:
                result = run_interactive_stream(
                    child,
                    {"session_profile": RATE_STREAMING,
                     "playback_interval_ms": frame_stream.STREAMING_MIN_PLAYBACK_INTERVAL_MS},
                    transport, clock, sleep, driver, stop_requested=stop_requested,
                    background_tick=getattr(pages[0], "background_tick", None))
            else:
                result = run_interactive_activity(
                    child, transport, clock, sleep, driver, stop_requested=stop_requested)
            result = {**result, "child_experiment_id": child.experiment_id,
                      "session_profile": rate_mode}
            child_results.append(result)
            return result
        return runner

    orchestrator = ProfilePageOrchestrator(
        pages, events,
        {RATE_ACTIVITY: runner_for(RATE_ACTIVITY), RATE_STREAMING: runner_for(RATE_STREAMING)},
        monotonic=lambda: clock() / 1000.0,
    )
    state = orchestrator.run(max_sessions=manifest.max_child_sessions + 1,
                             stop_requested=stop_requested)
    completed_cycles = state["profile_transitions"] // 2

    # Correlate each accepted physical input to the first later ACK across child-session
    # boundaries. Dedupe cumulative page snapshots by (epoch, seq). This measures the useful
    # interaction path without pretending transport ACK is panel-visible latency.
    accepted_inputs: dict[tuple[object, object], dict] = {}
    for child_result in child_results:
        input_state = child_result.get("input_state") or {}
        nav = input_state.get("navigation")
        if nav and nav.get("seq") is not None:
            accepted_inputs[(nav.get("epoch"), nav.get("seq"))] = {
                "epoch": nav.get("epoch"), "seq": nav.get("seq"), "type": nav.get("type"),
                "observed_at_monotonic": nav.get("observed_at_monotonic"),
            }
        for action in input_state.get("recent_actions") or []:
            if action.get("seq") is None:
                continue
            accepted_inputs[(action.get("epoch"), action.get("seq"))] = {
                "epoch": action.get("epoch"), "seq": action.get("seq"), "type": action.get("type"),
                "result": action.get("result"),
                "observed_at_monotonic": action.get("applied_at_monotonic"),
            }
    input_ack_latency = []
    for item in sorted(accepted_inputs.values(), key=lambda value: (str(value.get("epoch")), value.get("seq") or 0)):
        observed = item.get("observed_at_monotonic")
        ack = None if observed is None else next(
            (event for event in budget.ack_events if event["acked_at_monotonic"] > observed), None)
        latency = None if ack is None or observed is None else round(
            (ack["acked_at_monotonic"] - observed) * 1000.0, 1)
        input_ack_latency.append({**item, "first_later_ack_ms": latency,
                                  "ack_child_experiment_id": None if ack is None else ack["child_experiment_id"]})

    last = child_results[-1] if child_results else {}
    transport_outcome = "stopped_clean" if state["status"] in {"stopped", "session_ceiling"} \
        and not state.get("last_error") else "unknown"
    return {
        "experiment_id": manifest.experiment_id,
        "terminal_reason": last.get("terminal_reason") or (
            "operator_stop" if stop_requested() else state["status"]),
        "outcome": transport_outcome,
        "elapsed_ms": max(0, clock() - started_ms),
        "target_profile_cycles": manifest.target_profile_cycles,
        "completed_profile_cycles": completed_cycles,
        "cycle_target_met": completed_cycles >= manifest.target_profile_cycles,
        "orchestrator": state,
        "budget": budget.snapshot(),
        "input_to_first_later_ack": input_ack_latency,
        "child_results": child_results,
    }


def claim_outer(manifest: AcceptanceManifest, claim_dir: Path | None = None) -> activity_session.SessionClaim:
    claim = activity_session.SessionClaim(
        manifest.experiment_id,
        activity_session.CLAIM_DIR if claim_dir is None else Path(claim_dir))
    claim.claim({
        "manifest_file": str(manifest.path),
        "manifest_sha256": sha256_file(manifest.path),
        "code_hashes": module_hashes(),
        "host_build_sha256": manifest.host_dll_sha256,
        "claimed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    return claim


def finish_outer_claim(claim: activity_session.SessionClaim, result: dict) -> dict:
    return claim.finish(result.get("outcome") or "unknown", {
        "terminal_reason": result.get("terminal_reason"),
        "acceptance": result,
    })
