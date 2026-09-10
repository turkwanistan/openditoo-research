"""BTN-3/4: physical arrow-key pagination over the accepted Runtime 005 supervisor.

Two pages only: page 0 is the unchanged live MCP dashboard renderer, page 1 is one frozen
looping 16x16 animation. Input is the ButtonProbe's NDJSON event file (SMTC source only);
this module only READS it, so nothing here can create, replay or inject an event.

Display transport, pacing, budgets, reclaim and reconnect are Runtime 005's own
`product_runtime_v2.run_product`, reused unchanged through its `renderer_factory` seam.
A page switch is just a different frame from the renderer. Page state lives in the
router, outside any Host session, because BTN-2 proved an arrow press can itself end a
session (RFCOMM 0x09 -> canvas_invalidated); the next session resumes the selected page.

Authority: one-use `OPENDITOO-PAGINATION-ACCEPTANCE-001` only. The committed template is
unauthorized; `grant` materializes a local mode-0600 copy; `run` consumes a durable O_EXCL
claim before any device I/O and can never be re-armed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host import activity_session, frame_stream, product_runtime_v2  # noqa: E402

EXPERIMENT_ID = "OPENDITOO-PAGINATION-ACCEPTANCE-001"
TEMPLATE = ROOT / "product" / f"{EXPERIMENT_ID}.json"
LOCAL_POLICY = ROOT / ".openditoo-local" / "pagination-acceptance-policy.json"
EVENTS_FILE = ROOT / ".openditoo-local" / "button-events.ndjson"
STATE_FILE = ROOT / ".openditoo-local" / "pagination-runtime-state.json"
GRANT_TEXT = f"Grant {EXPERIMENT_ID}"
DASHBOARD, ANIMATION = "dashboard", "animation"
INPUT_TYPES = {"nav_left", "nav_right", "lever_candidate"}
MAX_LINE_BYTES = 4096


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ButtonEvents:
    """At-most-once reader of the ButtonProbe NDJSON file.

    Starts at the file's current end, so nothing written before this process began is
    ever replayed. Within one probe epoch `seq` must strictly increase: a repeat is
    dropped, a jump is counted as a gap (observable, never stitched). A new epoch is a
    new baseline. Only `source == "smtc"` events are typed input; the probe's diagnostic
    sources are ignored so one press can never count twice.
    """

    def __init__(self, path: Path = EVENTS_FILE) -> None:
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


class PageRouter:
    """Exactly one current page; Right enters the animation, Left returns. No wrap, no menu."""

    def __init__(self, monotonic: Callable[[], float] = time.monotonic) -> None:
        self.monotonic = monotonic
        self.page = DASHBOARD
        self.entered_at = monotonic()
        self.transitions: list[dict] = []
        self.ignored: list[dict] = []

    def apply(self, event: dict) -> bool:
        kind = event["type"]
        if kind == "nav_right" and self.page == DASHBOARD:
            target = ANIMATION
        elif kind == "nav_left" and self.page == ANIMATION:
            target = DASHBOARD
        else:
            # Lever stays informational until BTN-7; edge presses are no-ops.
            self.ignored.append({**event, "page": self.page, "applied_at_utc": _utc()})
            return False
        self.entered_at = self.monotonic()
        self.transitions.append({**event, "from": self.page, "to": target, "applied_at_utc": _utc(),
                                 "applied_at_monotonic": self.entered_at, "first_ack_ms": None})
        self.page = target
        return True


class PagedRenderer:
    """Per-session renderer. The router and event cursor outlive every session."""

    def __init__(self, router: PageRouter, events: ButtonEvents, dashboard, frame_set: frame_stream.FrameSet,
                 interval_ms: int) -> None:
        self.router, self.events, self.dashboard = router, events, dashboard
        self.frame_set, self.interval_ms = frame_set, interval_ms
        self.rendered_page: str | None = None

    def __call__(self, now_ms: int) -> tuple[bytes, bool]:
        for event in self.events.poll():
            self.router.apply(event)
        page = self.router.page
        if page == DASHBOARD and self.rendered_page == ANIMATION and hasattr(self.dashboard, "pulse_step"):
            # A pulse observed while the animation was up is stale on return; show current status.
            self.dashboard.pulse_step = None
            self.dashboard.pulse_sources.clear()
        dashboard_frame = self.dashboard(now_ms)  # always called: collection never pauses
        self.rendered_page = page
        if page == DASHBOARD:
            return dashboard_frame
        elapsed_ms = int((self.router.monotonic() - self.router.entered_at) * 1000)
        return self.frame_set.frames[(elapsed_ms // self.interval_ms) % self.frame_set.count], False

    def frame_sent(self) -> None:
        last = self.router.transitions[-1] if self.router.transitions else None
        if last and last["first_ack_ms"] is None and last["to"] == self.rendered_page:
            last["first_ack_ms"] = round((self.router.monotonic() - last["applied_at_monotonic"]) * 1000, 1)
        if self.rendered_page == DASHBOARD:
            sent = getattr(self.dashboard, "frame_sent", None)
            if callable(sent):
                sent()


# --------------------------------------------------------------------------
# One-use acceptance policy
# --------------------------------------------------------------------------

class PaginationPolicyError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code, self.detail = code, detail


def _require(ok: bool, code: str, detail: str = "") -> None:
    if not ok:
        raise PaginationPolicyError(code, detail)


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_hashes() -> dict[str, str]:
    hashes = product_runtime_v2.runtime_hashes()
    hashes["pagination_sha256"] = _sha(Path(__file__))
    hashes["cli_sha256"] = _sha(ROOT / "cli" / "openditoo.py")
    hashes["frame_stream_sha256"] = _sha(ROOT / "host" / "frame_stream.py")
    return hashes


def _windows_path(path: str) -> Path:
    drive, rest = path.split(":", 1)
    return Path("/mnt") / drive.lower() / rest.lstrip("\\").replace("\\", "/")


def load_policy(path: Path = LOCAL_POLICY, *, authority: bool = True, verify: bool = True) -> dict:
    try:
        policy = json.loads(Path(path).read_text(encoding="utf-8"))
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaginationPolicyError("PAGINATION_POLICY_UNREADABLE", str(exc)) from exc
    _require(policy.get("experiment_id") == EXPERIMENT_ID, "PAGINATION_POLICY_ID")
    reviewed = {k: v for k, v in template.items() if k != "authority"}
    _require({k: v for k, v in policy.items() if k != "authority"} == reviewed,
             "PAGINATION_POLICY_DRIFTED_FROM_TEMPLATE")
    if authority:
        grant = policy.get("authority") or {}
        _require(grant.get("pagination_acceptance_authorized") is True and grant.get("grant_text") == GRANT_TEXT
                 and bool(grant.get("granted_by")), "PAGINATION_AUTHORITY_MISSING")
    behavior = policy["behavior"]
    _require(behavior["raw_send_enabled"] is False and behavior["target_override_enabled"] is False
             and behavior["lever_action"] == "ignored", "PAGINATION_BEHAVIOR_WIDENED")
    if verify:
        build = policy["build"]
        _require(code_hashes() == build["code_sha256"], "PAGINATION_CODE_HASH_MISMATCH",
                 json.dumps({"expected": build["code_sha256"], "actual": code_hashes()}, sort_keys=True))
        _require(activity_session.sha256_file(activity_session.HOST_BUILD_DLL) == build["host_dll_sha256"],
                 "PAGINATION_HOST_HASH_MISMATCH")
        for name, digest in build["button_probe_sha256"].items():
            _require(_sha(_windows_path(name)) == digest, "PAGINATION_BUTTON_PROBE_HASH_MISMATCH", name)
        _require(_sha(ROOT / policy["animation"]["file"]) == policy["animation"]["sha256"],
                 "PAGINATION_ANIMATION_HASH_MISMATCH")
    return policy


def grant(grant_text: str, granted_by: str) -> Path:
    _require(grant_text == GRANT_TEXT, "PAGINATION_GRANT_TEXT_MISMATCH", f"expected exactly {GRANT_TEXT!r}")
    _require(activity_session.SessionClaim(EXPERIMENT_ID).read() is None, "AUTHORITY_ALREADY_CONSUMED")
    policy = load_policy(TEMPLATE, authority=False)
    policy["authority"] = {"pagination_acceptance_authorized": True, "grant_text": grant_text,
                           "granted_by": granted_by, "granted_at": _utc(), "one_use": True}
    LOCAL_POLICY.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(LOCAL_POLICY, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(policy, handle, indent=1, sort_keys=True)
    return LOCAL_POLICY


def product_policy(policy: dict) -> product_runtime_v2.ProductPolicy:
    session, behavior = policy["session"], policy["behavior"]
    return product_runtime_v2.ProductPolicy(
        path=LOCAL_POLICY, product_id=product_runtime_v2.PRODUCT_ID,
        session_lifetime_seconds=session["lifetime_seconds"], min_frame_interval_ms=session["min_frame_interval_ms"],
        poll_interval_ms=session["poll_interval_ms"], pulse_freshness_seconds=session["pulse_freshness_seconds"],
        max_frames_per_session=session["max_frames"], max_tx_bytes_per_session=session["max_tx_bytes"],
        reconnect_backoff_seconds=tuple(behavior["reconnect_backoff_seconds"]),
        reclaim_on_canvas_invalidated=True, automatic_reconnect=True, start_at_windows_logon=False,
        code_hashes=policy["build"]["code_sha256"], host_build_sha256=policy["build"]["host_dll_sha256"],
        authority_grant_text=policy["authority"]["grant_text"])


def run(policy: dict, transport_factory, *, stop_requested: Callable[[], bool],
        events: ButtonEvents | None = None, monotonic: Callable[[], float] = time.monotonic,
        state_file: Path = STATE_FILE, claim_dir: Path = activity_session.CLAIM_DIR,
        renderer_for_dashboard=activity_session.live_renderer, **supervisor) -> dict:
    """Consume the one-use claim, then run the two-page product loop until the deadline."""
    claim = activity_session.SessionClaim(EXPERIMENT_ID, claim_dir)
    claim.claim({"claimed_at": _utc(), "kind": "pagination_acceptance",
                 "code_sha256": policy["build"]["code_sha256"]})
    anim = policy["animation"]
    frame_set = frame_stream.build_frame_set(frame_stream.frames_from_source(ROOT / anim["file"]))
    router = PageRouter(monotonic)
    events = events or ButtonEvents(ROOT / policy["behavior"]["events_file"])
    deadline = monotonic() + policy["run"]["total_lifetime_seconds"]
    started = _utc()
    state = product_runtime_v2.run_product(
        product_policy(policy), transport_factory,
        stop_requested=lambda: stop_requested() or monotonic() >= deadline,
        monotonic=monotonic, state_file=state_file, **supervisor,
        renderer_factory=lambda cfg, st, manifest: PagedRenderer(
            router, events, renderer_for_dashboard(cfg, st, manifest), frame_set, anim["interval_ms"]))
    result = {"experiment_id": EXPERIMENT_ID, "started_at": started, "ended_at": _utc(),
              "final_page": router.page, "transitions": router.transitions, "ignored_inputs": router.ignored,
              "input_gaps": events.gaps, "input_epochs": events.epochs,
              "input_rejected_lines": events.rejected_lines, "runtime": state}
    claim.finish("completed", {"result": result})
    return result


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    try:
        if command == "check":
            load_policy(TEMPLATE, authority=False)
            consumed = activity_session.SessionClaim(EXPERIMENT_ID).read()
            print(json.dumps({"ok": True, "template_valid": True, "consumed": consumed is not None,
                              "local_policy_granted": LOCAL_POLICY.is_file()}))
        elif command == "grant":
            print(json.dumps({"ok": True, "policy": str(grant(argv[2], argv[3] if len(argv) > 3 else "owner"))}))
        elif command == "policy-check":
            load_policy()
            _require(activity_session.SessionClaim(EXPERIMENT_ID).read() is None, "AUTHORITY_ALREADY_CONSUMED")
            print(json.dumps({"ok": True, "execution_ready": True}))
        else:
            print("usage: pagination.py check | grant '<exact grant text>' [granted_by] | policy-check")
            return 64
    except PaginationPolicyError as exc:
        print(json.dumps({"ok": False, "error_code": exc.code, "detail": exc.detail}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
