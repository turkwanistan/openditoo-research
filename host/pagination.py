"""Runtime 006: standing physical-button pagination over the accepted Runtime 005 supervisor.

Pages are a wrap-around list; Left/Right move, a short lever pull runs the current page's
own action. Page 0 is the unchanged live MCP dashboard renderer; the other pages are small
`Page` objects. To add a page: write a class with `name`, `render(now_ms, dashboard_frame)`
and `lever()`, and append it in `build_pages`.

Input is the ButtonProbe's NDJSON event file (SMTC source only). This module only READS it,
so nothing here can create, replay or inject an event. The probe runs as a child of this
process in `--status mirror` (BTN-7: otherwise Windows drops lever Play), so it holds the
Windows media keys only while the dashboard product runs.

Display transport, pacing, budgets, reclaim and reconnect are Runtime 005's own
`product_runtime_v2.run_product`, reused unchanged through its `renderer_factory` seam.
Page state lives outside any Host session: BTN-2/BTN-7 proved an arrow (0x09) or a
play-direction lever pull (0xBD) can end a session; the next session resumes the page.

History: BTN-5 accepted the two-page shape under the consumed one-use
`OPENDITOO-PAGINATION-ACCEPTANCE-001` (code as of commit 63e8e25).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Callable

from host import activity_session, frame_stream, product_runtime_v2
from host.product_runtime_v2 import ProductPolicyError, read_runtime_state  # noqa: F401 (CLI surface)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REVISION = 3
EXACT_UNIT_ID = activity_session.EXACT_UNIT_ID
TEMPLATE = ROOT / "product" / "OPENDITOO-PRODUCT-RUNTIME-006.json"
R005_TEMPLATE = ROOT / "product" / "OPENDITOO-PRODUCT-RUNTIME-005.json"
PAGES_STATE_FILE = ROOT / ".openditoo-local" / "pagination-state.json"
GRANT_TEXT = "Grant OPENDITOO-PRODUCT-RUNTIME-006"
INPUT_TYPES = {"nav_left", "nav_right", "lever_candidate"}
MAX_LINE_BYTES = 4096
BROKER_RESTART_SECONDS = 5.0


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

class ButtonEvents:
    """At-most-once reader of the ButtonProbe NDJSON file.

    Starts at the file's current end, so nothing written before this process began is
    ever replayed. Within one probe epoch `seq` must strictly increase: a repeat is
    dropped, a jump is counted as a gap (observable, never stitched). A new epoch is a
    new baseline. Only `source == "smtc"` events are typed input; the probe's diagnostic
    sources are ignored so one press can never count twice.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self.offset = self.path.stat().st_size
        except FileNotFoundError:
            self.offset = 0
        self.pending = b""
        self.epoch: str | None = None
        self.last_seq = 0
        self.gaps = 0
        self.epochs = 0
        self.rejected_lines = 0

    def poll(self) -> list[dict]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []  # broker absent: no input, display carries on
        if size < self.offset:  # replaced/truncated by a new broker: read it from the start
            self.offset, self.pending = 0, b""
        if size == self.offset:
            return []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read(size - self.offset)
        self.offset += len(chunk)
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        if len(self.pending) > MAX_LINE_BYTES:
            self.pending, self.rejected_lines = b"", self.rejected_lines + 1
        events = []
        for line in lines:
            try:
                record = json.loads(line)
                epoch, seq = str(record["epoch"]), int(record["seq"])
            except (ValueError, KeyError, TypeError):
                self.rejected_lines += 1
                continue
            if epoch != self.epoch:
                self.epoch, self.epochs = epoch, self.epochs + 1
            elif seq <= self.last_seq:
                continue  # duplicate or replay within an epoch: consumed at most once
            elif seq != self.last_seq + 1:
                self.gaps += 1
            self.last_seq = seq
            if record.get("type") == "event" and record.get("source") == "smtc" \
                    and record.get("normalized_candidate") in INPUT_TYPES:
                events.append({"epoch": epoch, "seq": seq, "type": record["normalized_candidate"],
                               "raw_button": record.get("raw_button"), "at_utc": record.get("at_utc")})
        return events


class Broker:
    """The ButtonProbe as a child process. Killing the WSL-side child ends the Windows
    process (observed in BTN-7/8), so a stopped product never keeps the media keys."""

    def __init__(self, exe: Path, events_windows_path: str, events_file: Path,
                 popen=subprocess.Popen, monotonic: Callable[[], float] = time.monotonic) -> None:
        self.args = [str(exe), "--seconds", "0", "--status", "mirror", "--log", events_windows_path]
        self.events_file = Path(events_file)
        self.popen, self.monotonic = popen, monotonic
        self.process = None
        self.starts = 0
        self.last_start = float("-inf")

    def ensure(self) -> None:
        if self.alive:
            return
        if self.monotonic() - self.last_start < BROKER_RESTART_SECONDS:
            return  # a crashing probe must not spin
        self.last_start = self.monotonic()
        self.events_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.events_file.write_bytes(b"")  # new epoch, bounded file; the reader rebases on truncation
        self.events_file.chmod(0o600)
        self.process = self.popen(self.args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        self.starts += 1

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if self.alive:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

class DashboardPage:
    """Page 0: the live MCP dashboard, exactly as Runtime 005 renders it. No lever action yet."""
    name = "dashboard"

    def render(self, _now_ms: int, dashboard_frame: tuple[bytes, bool]) -> tuple[bytes, bool]:
        return dashboard_frame

    def lever(self) -> str | None:
        return None


class AnimationPage:
    """A frozen looping frame set; the lever pauses/resumes it."""

    def __init__(self, name: str, frame_set: frame_stream.FrameSet, interval_ms: int,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.name, self.frame_set, self.interval_ms, self.monotonic = name, frame_set, interval_ms, monotonic
        self.started = monotonic()
        self.paused_index: int | None = None

    def on_enter(self) -> None:
        self.started, self.paused_index = self.monotonic(), None

    def _index(self) -> int:
        return int((self.monotonic() - self.started) * 1000 // self.interval_ms) % self.frame_set.count

    def render(self, _now_ms: int, _dashboard_frame) -> tuple[bytes, bool]:
        index = self._index() if self.paused_index is None else self.paused_index
        return self.frame_set.frames[index], False

    def lever(self) -> str:
        if self.paused_index is None:
            self.paused_index = self._index()
            return "paused"
        # Resume from the frozen frame rather than jumping ahead.
        self.started = self.monotonic() - self.paused_index * self.interval_ms / 1000
        self.paused_index = None
        return "resumed"


class PageRouter:
    """One current page index over a wrap-around list. Every input is logged."""

    def __init__(self, pages: list, monotonic: Callable[[], float] = time.monotonic) -> None:
        if not pages or pages[0].name != "dashboard":
            raise ValueError("page 0 must be the dashboard")
        self.pages, self.monotonic = pages, monotonic
        self.index = 0
        self.transitions: list[dict] = []
        self.actions: list[dict] = []

    @property
    def page(self):
        return self.pages[self.index]

    def apply(self, event: dict) -> bool:
        if event["type"] == "lever_candidate":
            self.actions.append({**event, "page": self.page.name, "result": self.page.lever(),
                                 "applied_at_utc": _utc()})
            del self.actions[:-50]
            return False
        if len(self.pages) == 1:
            return False
        before = self.page.name
        self.index = (self.index + (1 if event["type"] == "nav_right" else -1)) % len(self.pages)
        getattr(self.page, "on_enter", lambda: None)()
        self.transitions.append({**event, "from": before, "to": self.page.name, "applied_at_utc": _utc(),
                                 "applied_at_monotonic": self.monotonic(), "first_ack_ms": None})
        del self.transitions[:-50]  # bounded history for telemetry
        return True


class PagedRenderer:
    """Per-session renderer. The router, pages, broker and event cursor outlive every session."""

    def __init__(self, router: PageRouter, events: ButtonEvents, dashboard,
                 on_input: Callable[[], None] = lambda: None, broker: Broker | None = None) -> None:
        self.router, self.events, self.dashboard = router, events, dashboard
        self.on_input, self.broker = on_input, broker
        self.rendered: str | None = None

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        if self.broker is not None:
            self.broker.ensure()
        events = self.events.poll()
        for event in events:
            self.router.apply(event)
        if events:
            self.on_input()
        page = self.router.page
        if page.name == "dashboard" and self.rendered not in (None, "dashboard") \
                and hasattr(self.dashboard, "pulse_step"):
            # A pulse observed while another page was up is stale on return; show current status.
            self.dashboard.pulse_step = None
            self.dashboard.pulse_sources.clear()
        dashboard_frame = self.dashboard(now_ms)  # always called: collection never pauses
        self.rendered = page.name
        return page.render(now_ms, dashboard_frame)

    def frame_sent(self) -> None:
        last = self.router.transitions[-1] if self.router.transitions else None
        if last and last["first_ack_ms"] is None and last["to"] == self.rendered:
            last["first_ack_ms"] = round((self.router.monotonic() - last["applied_at_monotonic"]) * 1000, 1)
        if self.rendered == "dashboard":
            sent = getattr(self.dashboard, "frame_sent", None)
            if callable(sent):
                sent()


def build_pages(raw: dict, monotonic: Callable[[], float] = time.monotonic) -> list:
    pages: list = [DashboardPage()]
    for spec in raw["pagination"]["pages"][1:]:
        frame_set = frame_stream.build_frame_set(frame_stream.frames_from_source(ROOT / spec["file"]))
        pages.append(AnimationPage(spec["name"], frame_set, spec["interval_ms"], monotonic))
    return pages


# --------------------------------------------------------------------------
# Standing policy (Runtime 006) — same CLI surface as product_runtime_v2
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class StandingPolicy(product_runtime_v2.ProductPolicy):
    raw: dict = field(default_factory=dict)


def _require(ok: bool, code: str, detail: str = "") -> None:
    if not ok:
        raise ProductPolicyError(code, detail)


def windows_path(path: str) -> Path:
    drive, rest = path.split(":", 1)
    return Path("/mnt") / drive.lower() / rest.lstrip("\\").replace("\\", "/")


def code_hashes() -> dict[str, str]:
    hashes = product_runtime_v2.runtime_hashes()
    hashes["pagination_sha256"] = _sha(Path(__file__))
    hashes["cli_sha256"] = _sha(ROOT / "cli" / "openditoo.py")
    hashes["frame_stream_sha256"] = _sha(ROOT / "host" / "frame_stream.py")
    return hashes


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
    return blockers


def load_policy(path: Path, *, require_authority: bool = True, verify_hashes: bool = True) -> StandingPolicy:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        r005 = json.loads(R005_TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductPolicyError("PRODUCT_POLICY_UNREADABLE", str(exc)) from exc
    _require(raw.get("runtime_revision") == RUNTIME_REVISION, "PRODUCT_RUNTIME_REVISION_MISMATCH")
    _require({k: v for k, v in raw.items() if k != "authority"} == {k: v for k, v in template.items() if k != "authority"},
             "PRODUCT_POLICY_DRIFTED_FROM_TEMPLATE")
    for key in ("target", "session", "behavior", "product_id"):
        _require(raw[key] == r005[key], "PRODUCT_006_WIDENS_005_ENVELOPE", key)
    if require_authority:
        blockers = authority_blockers(path)
        _require(not blockers, blockers[0] if blockers else "")
    build = raw["build"]
    if verify_hashes:
        _require(code_hashes() == build["code_sha256"], "PRODUCT_CODE_HASH_MISMATCH",
                 json.dumps({"expected": build["code_sha256"], "actual": code_hashes()}, sort_keys=True))
        _require(activity_session.sha256_file(activity_session.HOST_BUILD_DLL) == build["host_dll_sha256"],
                 "PRODUCT_HOST_HASH_MISMATCH")
        for name, digest in build["button_probe_sha256"].items():
            _require(_sha(windows_path(name)) == digest, "PRODUCT_BUTTON_PROBE_HASH_MISMATCH", name)
        for spec in raw["pagination"]["pages"][1:]:
            _require(_sha(ROOT / spec["file"]) == spec["sha256"], "PRODUCT_PAGE_ASSET_HASH_MISMATCH", spec["file"])
    session, behavior = raw["session"], raw["behavior"]
    return StandingPolicy(
        path=Path(path), product_id=raw["product_id"],
        session_lifetime_seconds=session["lifetime_seconds"], min_frame_interval_ms=session["min_frame_interval_ms"],
        poll_interval_ms=session["poll_interval_ms"], pulse_freshness_seconds=session["pulse_freshness_seconds"],
        max_frames_per_session=session["max_frames"], max_tx_bytes_per_session=session["max_tx_bytes"],
        reconnect_backoff_seconds=tuple(behavior["reconnect_backoff_seconds"]),
        reclaim_on_canvas_invalidated=True, automatic_reconnect=True, start_at_windows_logon=True,
        code_hashes=build["code_sha256"], host_build_sha256=build["host_dll_sha256"],
        authority_grant_text=str((raw.get("authority") or {}).get("grant_text") or ""), raw=raw)


def run_product(policy: StandingPolicy, transport_factory, *, stop_requested: Callable[[], bool] = lambda: False,
                monotonic: Callable[[], float] = time.monotonic, events: ButtonEvents | None = None,
                broker: Broker | None = None, pages: list | None = None,
                pages_state_file: Path = PAGES_STATE_FILE,
                renderer_for_dashboard=activity_session.live_renderer, **supervisor) -> dict:
    probe = policy.raw["pagination"]["broker"]
    if broker is None and events is None:
        broker = Broker(windows_path(probe["exe"]), probe["events_windows_path"], ROOT / probe["events_file"],
                        monotonic=monotonic)
    if broker is not None:
        broker.ensure()
    events = events or ButtonEvents(ROOT / probe["events_file"])
    router = PageRouter(pages or build_pages(policy.raw, monotonic), monotonic)

    def publish() -> None:
        last = (router.transitions + router.actions)[-1:] or [{}]
        state = {"updated_at": _utc(), "current_page": router.page.name, "pages": [p.name for p in router.pages],
                 "input_broker_alive": broker.alive if broker else None, "broker_starts": broker.starts if broker else 0,
                 "input_epoch": events.epoch, "last_input_seq": events.last_seq, "input_gaps": events.gaps,
                 "last_input_type": last[0].get("type"), "last_input_at": last[0].get("at_utc"),
                 "recent_transitions": router.transitions[-5:], "recent_actions": router.actions[-5:]}
        tmp = pages_state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(pages_state_file)

    publish()
    try:
        return product_runtime_v2.run_product(
            policy, transport_factory, stop_requested=stop_requested, monotonic=monotonic, **supervisor,
            renderer_factory=lambda cfg, st, manifest: PagedRenderer(
                router, events, renderer_for_dashboard(cfg, st, manifest), publish, broker))
    finally:
        if broker is not None:
            broker.stop()
        publish()
