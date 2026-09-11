#!/usr/bin/env python3
"""Typed OpenDitoo CLI.

The live surface is intentionally narrow and exact-target bound. Experimental/manual
commands retain one-shot authority and no automatic retry. A separate persistent
`product-runtime` supervisor may reconnect/reclaim only when a locally authorized,
hash-frozen product policy explicitly grants that behavior. Neither surface exposes a
target selector, raw packet send, generic Bluetooth command, or firmware path.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.diagnostic_frame import write_artifacts  # noqa: E402
from host.ditoo_candidate_codec import compare_application_frame  # noqa: E402
from host.ditoo_pixel_coloring import encode_rgb888_static_image, sha256_hex as pixel_sha256_hex  # noqa: E402
from host.png16 import Png16Error, decode_png16_rgb, png_sha256  # noqa: E402
from host import activity_render  # noqa: E402
from host import btsnoop  # noqa: E402
from host import avctp  # noqa: E402
from host import mcp_activity  # noqa: E402
from host import activity_session  # noqa: E402
from host import frame_stream  # noqa: E402
from host import product_runtime  # noqa: E402
from host import product_runtime_v2  # noqa: E402

CLI_VERSION = "0.3.0-mcp-product"
HOST_ORIGIN = "http://127.0.0.1:8796"
STATUS_URL = f"{HOST_ORIGIN}/v1/status"
IMAGE_SHOW_URL = f"{HOST_ORIGIN}/v1/image/show"
IMAGE_SEQUENCE_URL = f"{HOST_ORIGIN}/v1/image/sequence"
SESSION_OPEN_URL = f"{HOST_ORIGIN}/v1/session/open"
SESSION_FRAME_URL = f"{HOST_ORIGIN}/v1/session/frame"
SESSION_HEARTBEAT_URL = f"{HOST_ORIGIN}/v1/session/heartbeat"
SESSION_CLOSE_URL = f"{HOST_ORIGIN}/v1/session/close"
MIN_TOKEN_CHARS = 32
# Responses scale with frame count: a 512-frame sequence returns per-frame timings, ACKs
# and packet hashes, which came to 90 KB and silently overran the old 64 KB read. Still
# bounded, and truncation is now detected rather than surfacing as a parse error.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFIG = 10
EXIT_HOST_UNAVAILABLE = 20
EXIT_AUTH = 21
EXIT_PROTOCOL = 22
EXIT_BLOCKED = 30
EXIT_DEVICE = 31
EXIT_SOURCE = 40


def local_dir() -> Path:
    return ROOT / ".openditoo-local"


def token_file() -> Path:
    return local_dir() / "host.token"


def read_json_response(response) -> dict:
    """Read one bounded JSON response, refusing a truncated read instead of misparsing it.

    Reading a fixed cap and parsing whatever came back turns an oversized response into a
    JSONDecodeError, which the callers then report as HOST_UNAVAILABLE -- a successful
    512-frame run was misreported as a transport failure exactly this way.
    """
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"RESPONSE_TOO_LARGE: over {MAX_RESPONSE_BYTES} bytes")
    return json.loads(body.decode("utf-8"))


def emit(value: object) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def auth_init(_: argparse.Namespace) -> int:
    directory = local_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    path = token_file()
    created = False
    if path.exists():
        read_token()
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (secrets.token_hex(32) + "\n").encode("ascii"))
        finally:
            os.close(fd)
        path.chmod(0o600)
        created = True
    emit({"ok": True, "command": "auth-init", "created": created, "token_file": str(path), "secret_emitted": False})
    return EXIT_OK


def read_token() -> str:
    path = token_file()
    try:
        info = path.stat()
    except FileNotFoundError as exc:
        raise RuntimeError("OpenDitoo token not initialized; run 'openditoo auth-init'") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise RuntimeError("OpenDitoo token must be a regular 0600 file")
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < MIN_TOKEN_CHARS:
        raise RuntimeError("OpenDitoo token is too short")
    return token


def host_status(_: argparse.Namespace) -> int:
    try:
        token = read_token()
    except RuntimeError as exc:
        emit({"ok": False, "command": "status", "error_code": "LOCAL_AUTH_CONFIG", "message": str(exc)})
        return EXIT_CONFIG
    request = urllib.request.Request(
        STATUS_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": f"OpenDitoo-CLI/{CLI_VERSION}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3.0) as response:
            body = read_json_response(response)
    except urllib.error.HTTPError as exc:
        emit({"ok": False, "command": "status", "error_code": "HOST_AUTH_REJECTED" if exc.code == 401 else "HOST_PROTOCOL", "http_status": exc.code})
        return EXIT_AUTH if exc.code == 401 else EXIT_PROTOCOL
    except Exception as exc:
        emit({"ok": False, "command": "status", "error_code": "HOST_UNAVAILABLE", "message": f"{type(exc).__name__}: {exc}"})
        return EXIT_HOST_UNAVAILABLE

    required = {
        "apiVersion": 1,
        "service": "OpenDitoo Day1 Host",
        "hostRuntime": ".NET",
        "bind": "127.0.0.1",
        "port": 8796,
        "masterTransmitEnabled": True,
        "bluetoothTouched": False,
        "transportConfigured": True,
        "targetBound": True,
        "rawSendEnabled": False,
    }
    if (
        not isinstance(body, dict)
        or any(body.get(k) != v for k, v in required.items())
        or "image-show" not in body.get("capabilities", [])
    ):
        emit({"ok": False, "command": "status", "error_code": "HOST_IDENTITY_MISMATCH"})
        return EXIT_PROTOCOL
    emit({"ok": True, "command": "status", "host_origin": HOST_ORIGIN, **body})
    return EXIT_OK


def codec_compare(args: argparse.Namespace) -> int:
    try:
        raw = bytes.fromhex(args.hex)
    except ValueError as exc:
        emit({"ok": False, "command": "codec-compare", "error_code": "INVALID_HEX", "message": str(exc)})
        return EXIT_USAGE
    emit({"ok": True, "command": "codec-compare", "evidence_class": "candidate_only", **compare_application_frame(raw)})
    return EXIT_OK


def capture_compare(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        emit({"ok": False, "command": "capture-compare", "error_code": "INPUT_NOT_FOUND"})
        return EXIT_USAGE
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
        transactions = source["transactions"]
        if not isinstance(transactions, list):
            raise ValueError("transactions must be a list")
        results = []
        for index, item in enumerate(transactions):
            if not isinstance(item, dict) or item.get("direction") not in {"tx", "rx"} or not isinstance(item.get("application_hex"), str):
                raise ValueError(f"transaction {index} requires direction tx/rx and application_hex")
            raw = bytes.fromhex(item["application_hex"])
            results.append({"index": index, "direction": item["direction"], **compare_application_frame(raw)})
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        emit({"ok": False, "command": "capture-compare", "error_code": "INVALID_CAPTURE_FIXTURE", "message": str(exc)})
        return EXIT_USAGE
    emit({"ok": True, "command": "capture-compare", "evidence_class": "candidate_only", "source_file": str(path), "transactions": results})
    return EXIT_OK


def frame_preview(args: argparse.Namespace) -> int:
    result = write_artifacts(Path(args.output_dir))
    emit({"ok": True, "command": "frame-preview", "device_io": False, **result})
    return EXIT_OK


def image_prepare(args: argparse.Namespace) -> int:
    path = Path(args.png)
    if not path.is_file():
        emit({"ok": False, "command": "image-prepare", "error_code": "INPUT_NOT_FOUND", "source_file": str(path)})
        return EXIT_USAGE
    try:
        rgb, wire, palette_colors = _prepare_png(path)
    except (OSError, Png16Error, ValueError) as exc:
        emit({"ok": False, "command": "image-prepare", "error_code": "INVALID_16X16_PNG", "message": str(exc)})
        return EXIT_USAGE

    output_dir = Path(args.output_dir) if args.output_dir else None
    outputs: dict[str, str] = {}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        rgb_path = output_dir / "image.rgb888"
        packet_path = output_dir / "image.packet.bin"
        rgb_path.write_bytes(rgb)
        packet_path.write_bytes(wire)
        outputs = {"rgb_path": str(rgb_path), "packet_path": str(packet_path)}

    emit({
        "ok": True,
        "command": "image-prepare",
        "device_io": False,
        "source_file": str(path),
        "source_png_sha256": png_sha256(path),
        "rgb_bytes": len(rgb),
        "rgb_sha256": pixel_sha256_hex(rgb),
        "palette_colors": palette_colors,
        "image_packet_bytes": len(wire),
        "image_packet_sha256": pixel_sha256_hex(wire),
        **outputs,
    })
    return EXIT_OK


def _prepare_png(path: Path) -> tuple[bytes, bytes, int]:
    rgb = decode_png16_rgb(path)
    wire, palette_colors = encode_rgb888_static_image(rgb)
    return rgb, wire, palette_colors


def image_show(args: argparse.Namespace) -> int:
    path = Path(args.png)
    if not path.is_file():
        emit({"ok": False, "command": "image-show", "error_code": "INPUT_NOT_FOUND", "source_file": str(path)})
        return EXIT_USAGE
    try:
        rgb, wire, palette_colors = _prepare_png(path)
        token = read_token()
    except (OSError, Png16Error, ValueError, RuntimeError) as exc:
        emit({"ok": False, "command": "image-show", "error_code": "LOCAL_PREPARE_FAILED", "message": str(exc)})
        return EXIT_USAGE if not isinstance(exc, RuntimeError) else EXIT_CONFIG

    expected_packet_sha = pixel_sha256_hex(wire)
    body = json.dumps({
        "pixelsRgb888Hex": rgb.hex(),
        "expectedImagePacketSha256": expected_packet_sha,
    }, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        IMAGE_SHOW_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"OpenDitoo-CLI/{CLI_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25.0) as response:
            result = read_json_response(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read(65537).decode("utf-8"))
        except Exception:
            detail = {"http_status": exc.code}
        code = EXIT_AUTH if exc.code == 401 else (EXIT_BLOCKED if exc.code in {400, 409} else EXIT_DEVICE)
        emit({"ok": False, "command": "image-show", "error_code": "HOST_REJECTED", "http_status": exc.code, "detail": detail})
        return code
    except Exception as exc:
        emit({"ok": False, "command": "image-show", "error_code": "HOST_UNAVAILABLE", "message": f"{type(exc).__name__}: {exc}"})
        return EXIT_HOST_UNAVAILABLE

    if not isinstance(result, dict) or result.get("ok") is not True:
        emit({"ok": False, "command": "image-show", "error_code": "HOST_PROTOCOL", "detail": result})
        return EXIT_PROTOCOL
    required = {
        "apiVersion": 1,
        "command": "image-show",
        "deviceIo": True,
        "packetCount": 3,
        "imagePacketSha256": expected_packet_sha,
        "paletteColors": palette_colors,
        "connectionsAttempted": 1,
        "socketClosed": True,
        "retry": False,
    }
    if any(result.get(key) != value for key, value in required.items()):
        emit({"ok": False, "command": "image-show", "error_code": "HOST_RESULT_MISMATCH", "detail": result})
        return EXIT_PROTOCOL
    emit({
        "ok": True,
        "command": "image-show",
        "source_file": str(path),
        "source_png_sha256": png_sha256(path),
        "rgb_sha256": pixel_sha256_hex(rgb),
        **result,
    })
    return EXIT_OK


def sequence_run(args: argparse.Namespace) -> int:
    """Run one frozen frame sequence, exactly as its reviewed manifest specifies.

    There are no frame, target, delay or packet arguments: everything comes from the
    manifest, and every frozen hash in it is re-verified locally before the request.
    A manifest without live authority, or whose authority is already consumed, is
    refused here before the Host is contacted.
    """
    path = Path(args.manifest)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "command": "sequence-run", "error_code": "INVALID_MANIFEST", "message": str(exc)})
        return EXIT_USAGE

    authority = manifest.get("authority", {})
    if authority.get("transmission_authorized") is not True:
        emit({"ok": False, "command": "sequence-run", "error_code": "TRANSMISSION_AUTHORITY_MISSING",
              "experiment_id": manifest.get("experiment_id")})
        return EXIT_BLOCKED
    if authority.get("authorization_consumed") is True:
        emit({"ok": False, "command": "sequence-run", "error_code": "AUTHORITY_ALREADY_CONSUMED",
              "experiment_id": manifest.get("experiment_id"),
              "message": "this manifest has already been executed; a repeat needs a new grant"})
        return EXIT_BLOCKED
    experiment_id = manifest.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        emit({"ok": False, "command": "sequence-run", "error_code": "MANIFEST_EXPERIMENT_ID_MISSING"})
        return EXIT_USAGE

    operation = manifest.get("operation", {})
    sources = operation.get("source_frames", {})
    budgets = manifest.get("budgets", {})
    order = operation.get("frame_order") or ["a", "b"]
    prepared: dict[str, dict] = {}
    frames = []
    for key in order:
        if key in prepared:
            frames.append(prepared[key])
            continue
        source = sources.get(key)
        if not isinstance(source, dict):
            emit({"ok": False, "command": "sequence-run", "error_code": "MANIFEST_FRAME_MISSING", "frame": key})
            return EXIT_USAGE
        png = ROOT / source["file"]
        if not png.is_file():
            emit({"ok": False, "command": "sequence-run", "error_code": "FRAME_FILE_NOT_FOUND", "frame": key, "file": str(png)})
            return EXIT_USAGE
        try:
            rgb, wire, palette_colors = _prepare_png(png)
        except (OSError, Png16Error, ValueError) as exc:
            emit({"ok": False, "command": "sequence-run", "error_code": "FRAME_PREPARE_FAILED", "frame": key, "message": str(exc)})
            return EXIT_USAGE
        actual = {
            "png_sha256": png_sha256(png),
            "rgb_sha256": pixel_sha256_hex(rgb),
            "packet_sha256": pixel_sha256_hex(wire),
            "palette_colors": palette_colors,
        }
        drift = {name: {"manifest": source.get(name), "actual": value}
                 for name, value in actual.items() if source.get(name) != value}
        if drift:
            emit({"ok": False, "command": "sequence-run", "error_code": "FROZEN_FRAME_DRIFT", "frame": key, "drift": drift})
            return EXIT_BLOCKED
        prepared[key] = {"pixelsRgb888Hex": rgb.hex(), "expectedImagePacketSha256": actual["packet_sha256"]}
        frames.append(prepared[key])

    try:
        token = read_token()
    except RuntimeError as exc:
        emit({"ok": False, "command": "sequence-run", "error_code": "LOCAL_AUTH_CONFIG", "message": str(exc)})
        return EXIT_CONFIG

    # Durable one-use authority, claimed BEFORE dispatch and never releasable -- the same
    # gate the activity session uses. Until this existed, sequence-run only checked the
    # manifest's own flags and consumption was manual bookkeeping after the fact, so a
    # crash mid-run left the authority looking re-usable.
    claim = activity_session.SessionClaim(experiment_id)
    try:
        claim.claim({"manifest_file": str(path), "command": "sequence-run",
                     "claimed_at": mcp_activity.iso(mcp_activity.utc_now())})
    except activity_session.SessionError as exc:
        emit({"ok": False, "command": "sequence-run", "error_code": exc.code,
              "experiment_id": experiment_id, "detail": exc.detail})
        return EXIT_BLOCKED

    delay_ms = int(budgets.get("inter_frame_delay_ms", 0))
    total_budget_ms = int(budgets.get("total_wall_clock_ms", 0))
    # Absent means the Host's stock-derived default. Only a reviewed manifest may lower it.
    spacing = budgets.get("send_spacing_ms")
    request_body = {"frames": frames, "interFrameDelayMs": delay_ms, "totalBudgetMs": total_budget_ms}
    if spacing is not None:
        request_body["sendSpacingMs"] = int(spacing)
    body = json.dumps(request_body, separators=(",", ":")).encode("utf-8")
    timeout = max(30.0, int(budgets.get("total_wall_clock_ms", 20000)) / 1000.0 + 10.0)
    request = urllib.request.Request(
        IMAGE_SEQUENCE_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": f"OpenDitoo-CLI/{CLI_VERSION}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = read_json_response(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read(65537).decode("utf-8"))
        except Exception:
            detail = {"http_status": exc.code}
        claim.finish("unknown", {"terminal_reason": "host_rejected", "http_status": exc.code})
        emit({"ok": False, "command": "sequence-run", "error_code": "HOST_REJECTED", "http_status": exc.code, "detail": detail})
        return EXIT_AUTH if exc.code == 401 else (EXIT_BLOCKED if exc.code in {400, 409} else EXIT_DEVICE)
    except Exception as exc:
        claim.finish("unknown", {"terminal_reason": "host_unavailable"})
        emit({"ok": False, "command": "sequence-run", "error_code": "HOST_UNAVAILABLE", "message": f"{type(exc).__name__}: {exc}"})
        return EXIT_HOST_UNAVAILABLE

    expected = {
        "ok": True,
        "command": "image-sequence",
        "deviceIo": True,
        "frameCount": len(order),
        "packetCount": budgets.get("application_packets"),
        "txBytesTotal": budgets.get("application_tx_bytes_total"),
        "connectionsAttempted": budgets.get("connection_attempts"),
        "interFrameDelayMs": delay_ms,
        "sendSpacingMs": int(spacing) if spacing is not None else 40,
        "socketClosed": True,
        "retry": False,
        "reconnect": False,
        "imagePacketSha256Ordered": [sources[key]["packet_sha256"] for key in order],
    }
    mismatch = {key: {"expected": value, "actual": result.get(key)}
                for key, value in expected.items() if result.get(key) != value}
    if mismatch:
        claim.finish("unknown", {"terminal_reason": "budget_or_result_mismatch", "mismatch": mismatch})
        emit({"ok": False, "command": "sequence-run", "error_code": "BUDGET_OR_RESULT_MISMATCH",
              "mismatch": mismatch, "detail": result})
        return EXIT_PROTOCOL
    claim.finish("stopped_clean", {"terminal_reason": "sequence_complete",
                                   "frames_sent": result.get("frameCount"),
                                   "packets_sent": result.get("packetCount"),
                                   "tx_bytes_sent": result.get("txBytesTotal")})
    emit({"ok": True, "command": "sequence-run", "experiment_id": experiment_id,
          "claim_file": str(claim.path), "manifest_file": str(path), **result})
    return EXIT_OK


def capture_parse(args: argparse.Namespace) -> int:
    """Offline: filter one raw btsnoop capture to attributable Ditoo evidence.

    Payload bytes are withheld unless a command id is explicitly named with --reveal,
    because a snoop log carries the whole phone's Bluetooth traffic.

    This reads a local file and reaches no device. The transport acronym is spelled out
    only in host/btsnoop.py: a boundary test asserts the CLI source contains no
    Bluetooth transport vocabulary, and that guard is worth more than the wording here.
    """
    path = Path(args.btsnoop)
    if not path.is_file():
        emit({"ok": False, "command": "capture-parse", "error_code": "INPUT_NOT_FOUND", "source_file": str(path)})
        return EXIT_USAGE
    reveal: set[int] = set()
    if args.reveal:
        try:
            reveal = {int(item, 16) for item in args.reveal.split(",") if item.strip()}
        except ValueError:
            emit({"ok": False, "command": "capture-parse", "error_code": "INVALID_REVEAL_LIST"})
            return EXIT_USAGE
    try:
        view, frames, errors = btsnoop.read(path, peer_bdaddr=args.peer_bdaddr,
                                            server_channel=args.server_channel, reveal_commands=reveal,
                                            zip_entry=args.zip_entry)
    except btsnoop.BtsnoopError as exc:
        emit({"ok": False, "command": "capture-parse", "error_code": "INVALID_BTSNOOP", "message": str(exc)})
        return EXIT_USAGE

    summary = btsnoop.summarize(view, frames, errors)
    summary["revealed_commands"] = sorted(f"0x{value:02X}" for value in reveal)
    summary["payloads_withheld_by_default"] = not reveal
    result = {
        "ok": True,
        "command": "capture-parse",
        "device_io": False,
        "peer_bdaddr": args.peer_bdaddr,
        "rfcomm_server_channel": args.server_channel,
        **summary,
    }
    if reveal:
        result["revealed_frames"] = [
            {"at": frame.at.isoformat().replace("+00:00", "Z"), "direction": frame.direction,
             "command": f"0x{frame.command:02X}", "wire_hex": frame.hex, "sha256": frame.sha256}
            for frame in frames if frame.hex
        ]
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        result["output_file"] = args.output
    emit(result)
    return EXIT_OK


def capture_avrcp_parse(args: argparse.Namespace) -> int:
    """Offline (BTN-0): recover the peer's AVRCP pass-through key events from one capture.

    Reads a local file and reaches no device. Only operation ids and the peer's own
    device-state reports near each press are revealed; see host/avctp.py.
    """
    path = Path(args.btsnoop)
    if not path.is_file():
        emit({"ok": False, "command": "capture-avrcp-parse", "error_code": "INPUT_NOT_FOUND", "source_file": str(path)})
        return EXIT_USAGE
    try:
        evidence = avctp.derive_evidence(path, args.peer_bdaddr, zip_entry=args.zip_entry)
    except btsnoop.BtsnoopError as exc:
        emit({"ok": False, "command": "capture-avrcp-parse", "error_code": "INVALID_BTSNOOP", "message": str(exc)})
        return EXIT_USAGE
    result = {"ok": True, "command": "capture-avrcp-parse", "device_io": False, **evidence}
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        result["output_file"] = args.output
    emit(result)
    return EXIT_OK


def _activity_config():
    return mcp_activity.load_config()


def activity_probe(_: argparse.Namespace) -> int:
    """Source diagnostics: reachability and cost, separate from device health."""
    try:
        report = mcp_activity.probe(_activity_config())
    except mcp_activity.SourceError as exc:
        emit({"ok": False, "command": "activity-probe", "error_code": str(exc)})
        return EXIT_SOURCE
    emit({"ok": True, "command": "activity-probe", "device_io": False, "sources": report})
    return EXIT_OK


def activity_status(args: argparse.Namespace) -> int:
    state = mcp_activity.load_state()
    new_counts: dict[str, int] = {}
    if args.collect:
        try:
            config = _activity_config()
        except mcp_activity.SourceError as exc:
            emit({"ok": False, "command": "activity-status", "error_code": str(exc)})
            return EXIT_SOURCE
        new_counts = mcp_activity.collect_once(config, state, poll_seconds=float(config.get("poll_seconds", 2.0)))
        mcp_activity.save_state(state)
    emit({
        "ok": True,
        "command": "activity-status",
        "device_io": False,
        "collected": bool(args.collect),
        "new_activity": new_counts,
        "sources": state["sources"],
        "display": activity_render.describe(state, pulses={k for k, v in new_counts.items() if v}),
    })
    return EXIT_OK


def activity_preview(args: argparse.Namespace) -> int:
    """Offline: render the current normalized state to exact and enlarged PNGs."""
    state = mcp_activity.load_state()
    new_counts: dict[str, int] = {}
    if args.collect:
        try:
            config = _activity_config()
        except mcp_activity.SourceError as exc:
            emit({"ok": False, "command": "activity-preview", "error_code": str(exc)})
            return EXIT_SOURCE
        new_counts = mcp_activity.collect_once(config, state, poll_seconds=float(config.get("poll_seconds", 2.0)))
        mcp_activity.save_state(state)
    pulses = {key for key, value in new_counts.items() if value}
    rgb = activity_render.render_rgb888(state, pulses=pulses)
    outputs = activity_render.write_previews(Path(args.output_dir), rgb, scale=args.scale)
    wire, palette_colors = encode_rgb888_static_image(rgb)
    emit({
        "ok": True,
        "command": "activity-preview",
        "device_io": False,
        "pulsing": sorted(pulses),
        "rgb_sha256": pixel_sha256_hex(rgb),
        "palette_colors": palette_colors,
        "image_packet_bytes": len(wire),
        "image_packet_sha256": pixel_sha256_hex(wire),
        "legend": activity_render.LEGEND,
        "display": activity_render.describe(state, pulses=pulses),
        **outputs,
    })
    return EXIT_OK


def _post(url: str, body: dict, token: str, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body, separators=(",", ":")).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": f"OpenDitoo-CLI/{CLI_VERSION}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return read_json_response(response)


class _HostSessionTransport:
    """Drives one reviewed session through the separate authenticated Host.

    It carries the experiment identity, not just frames and budgets: the Host consumes
    that id on disk before it opens anything, and enforces lifetime, pacing and budgets
    itself. This client cannot loosen any of them, and never retries or reconnects.
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.session_id: str | None = None
        self.opened: dict = {}

    def open(self, manifest) -> dict:
        body = {
            "experimentId": manifest.experiment_id,
            "lifetimeSeconds": manifest.lifetime_seconds,
            "minFrameIntervalMs": manifest.min_frame_interval_ms,
            "maxFrames": manifest.max_frames,
            "maxTxBytes": manifest.max_tx_bytes,
        }
        # A profile is a NAME, never timing numbers: the Host owns the constants each name
        # resolves to. Omitting it keeps the activity dashboard's exact behaviour, so this
        # is invisible to every existing caller.
        profile = (manifest.raw.get("stream") or {}).get("session_profile")
        if profile:
            body["sessionProfile"] = profile
        self.opened = _post(SESSION_OPEN_URL, body, self.token, timeout=30.0)
        if self.opened.get("ok") is not True or not self.opened.get("sessionId"):
            raise activity_session.SessionError("SESSION_OPEN_REJECTED", json.dumps(self.opened, sort_keys=True))
        if profile and self.opened.get("sessionProfile") != profile:
            # The Host is the authority on what profile it actually applied. If it did not
            # confirm ours, we are not running the reviewed shape and must not send.
            raise activity_session.SessionError(
                "SESSION_PROFILE_NOT_CONFIRMED",
                json.dumps({"requested": profile, "host": self.opened.get("sessionProfile")},
                           sort_keys=True))
        self.session_id = self.opened["sessionId"]
        return self.opened

    def send_frame(self, rgb: bytes, expected_packet_sha256: str) -> dict:
        result = _post(SESSION_FRAME_URL, {
            "sessionId": self.session_id,
            "pixelsRgb888Hex": rgb.hex(),
            "expectedImagePacketSha256": expected_packet_sha256,
        }, self.token, timeout=30.0)
        if result.get("ok") is not True or result.get("imagePacketSha256") != expected_packet_sha256:
            raise activity_session.SessionError("SESSION_FRAME_REJECTED", json.dumps(result, sort_keys=True))
        return result

    def poll_reports(self) -> list[dict]:
        """Prove liveness and read the session's state, without sending anything.

        A change-only display can legitimately send nothing for minutes, so liveness
        cannot be inferred from frames -- and the worker must not have to send one to
        discover that the session has already ended.
        """
        session = _post(SESSION_HEARTBEAT_URL, {"sessionId": self.session_id},
                        self.token, timeout=15.0).get("session", {})
        if session.get("active") is True:
            return []
        return [{"kind": "session_ended",
                 "reason": session.get("terminalReason") or "session_ended",
                 "outcome": session.get("terminalOutcome") or "unknown",
                 "display_state": session.get("displayState"),
                 "frames_sent": session.get("framesSent"),
                 "tx_bytes_sent": session.get("txBytesSent")}]

    def close(self, reason: str) -> dict:
        """Close, tolerating the Host having already closed it.

        The Host enforces the lifetime with its own watchdog, so a session that runs to
        its full lifetime is normally terminated Host-side a moment before the worker
        gets here. That 409 means "already closed cleanly", not a fault, and recording it
        as a close error made a clean run look ambiguous.
        """
        if self.session_id is None:
            return {"closed": False}
        try:
            return _post(SESSION_CLOSE_URL, {"sessionId": self.session_id, "reason": reason},
                         self.token, timeout=15.0)
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                return {"closed": True, "already_terminated": True}
            raise


def session_check(args: argparse.Namespace) -> int:
    """Offline, fail-closed review of one activation manifest. Grants nothing."""
    try:
        # Reviewed WITHOUT requiring the grant, so a pending manifest is fully checkable.
        # The grant is then reported as a blocker rather than hidden behind an error.
        manifest = activity_session.load_session_manifest(Path(args.manifest), require_authority=False)
    except activity_session.SessionError as exc:
        emit({"ok": False, "command": "session-check", "device_io": False,
              "execution_ready": False, "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED
    claim = activity_session.SessionClaim(manifest.experiment_id)
    existing = claim.read()
    blockers = activity_session.authority_blockers(Path(args.manifest))
    if existing is not None and "AUTHORITY_ALREADY_CONSUMED" not in blockers:
        blockers.append("AUTHORITY_ALREADY_CONSUMED")
    emit({
        "ok": True, "command": "session-check", "device_io": False,
        "execution_ready": not blockers,
        "execution_blockers": blockers,
        "experiment_id": manifest.experiment_id,
        "lifetime_seconds": manifest.lifetime_seconds,
        "min_frame_interval_ms": manifest.min_frame_interval_ms,
        "max_frames": manifest.max_frames,
        "max_application_packets": manifest.max_application_packets,
        "max_tx_bytes": manifest.max_tx_bytes,
        "activation_source": manifest.activation_source,
        "host_build_sha256": manifest.host_build_sha256,
        "repository_host_build_sha256": activity_session.sha256_file(activity_session.HOST_BUILD_DLL)
        if activity_session.HOST_BUILD_DLL.is_file() else None,
        "code_hashes_verified": True,
        "existing_claim": existing,
        "stop_conditions": list(manifest.stop_conditions),
    })
    return EXIT_OK


def session_preview(args: argparse.Namespace) -> int:
    """Offline: run one scenario through render, scheduler and a fake transport.

    Nothing is dispatched and no authority is claimed. This is how a session's real
    behaviour -- what it would send, and everything it would decline to send -- is
    reviewed before any grant is requested.
    """
    try:
        manifest = activity_session.load_session_manifest(Path(args.manifest), verify_code_hashes=False,
                                                          require_authority=False)
    except activity_session.SessionError as exc:
        emit({"ok": False, "command": "session-preview", "error_code": exc.code, "detail": exc.detail})
        return EXIT_USAGE
    try:
        scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "command": "session-preview", "error_code": "INVALID_SCENARIO", "message": str(exc)})
        return EXIT_USAGE

    steps = scenario["steps"]
    # Same pacing, budgets and stop policy; only the window is the scenario's length,
    # so the run ends because the script ended and not as an unknown device outcome.
    import dataclasses
    manifest = dataclasses.replace(manifest, lifetime_seconds=len(steps) * manifest.poll_interval_ms // 1000)
    clock = {"ms": 0}
    reports = {int(k): v for k, v in scenario.get("reports_after_frame", {}).items()}
    transport = activity_session.FakeSessionTransport(reports=reports)
    index = {"i": 0}

    def render(_now_ms: int):
        step = steps[min(index["i"], len(steps) - 1)]
        index["i"] += 1
        state = mcp_activity.blank_state()
        for source_id, view in step["sources"].items():
            state["sources"][source_id].update(view)
        pulses = set(step.get("pulses", []))
        return activity_render.render_rgb888(state, now=mcp_activity.parse_timestamp(step["now"]),
                                             pulses=pulses), bool(pulses)

    def advance(ms: int) -> None:
        clock["ms"] += ms

    result = activity_session.run_session(
        manifest, transport, render, lambda: clock["ms"], advance,
        claim=None, max_iterations=len(steps) + 8)
    emit({"ok": True, "command": "session-preview", "device_io": False, "dispatched": False,
          "scenario_file": str(args.scenario), "frames_that_would_be_sent": len(transport.frames),
          "would_send": transport.frames, "result": result})
    return EXIT_OK


def activity_session_run(args: argparse.Namespace) -> int:
    """Run ONE reviewed activation manifest, exactly as written.

    There are no lifetime, rate, budget or target arguments: everything comes from the
    manifest. The experiment id is claimed durably here and again by the Host before
    anything is dispatched, and neither claim can be released. A failed or ambiguous
    session needs a new manifest under a new grant, never a reset.
    """
    try:
        manifest = activity_session.load_session_manifest(Path(args.manifest))
        token = read_token()
    except activity_session.SessionError as exc:
        emit({"ok": False, "command": "activity-session", "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED
    except RuntimeError as exc:
        emit({"ok": False, "command": "activity-session", "error_code": "LOCAL_AUTH_CONFIG", "message": str(exc)})
        return EXIT_CONFIG

    if manifest.acceptance_profile is None:
        try:
            config = _activity_config()
        except mcp_activity.SourceError as exc:
            emit({"ok": False, "command": "activity-session", "error_code": str(exc)})
            return EXIT_SOURCE
    else:
        # A reviewed visual-acceptance profile is deterministic and must not depend on
        # private source endpoints, source reachability, or collection side effects.
        config = {}

    claim = activity_session.SessionClaim(manifest.experiment_id)
    try:
        claim.claim({"manifest_file": str(manifest.path), "code_hashes": manifest.code_hashes,
                     "host_build_sha256": manifest.host_build_sha256,
                     "claimed_at": mcp_activity.iso(mcp_activity.utc_now())})
    except activity_session.SessionError as exc:
        emit({"ok": False, "command": "activity-session", "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED

    state = mcp_activity.load_state()
    render = activity_session.live_renderer(config, state, manifest)
    transport = _HostSessionTransport(token)
    import time
    started = time.monotonic()
    result = activity_session.run_session(
        manifest, transport, render,
        lambda: int((time.monotonic() - started) * 1000),
        lambda ms: time.sleep(ms / 1000.0),
        claim=claim)
    emit({"ok": result["outcome"] != "unknown", "command": "activity-session",
          "manifest_file": str(manifest.path), "claim_file": str(claim.path),
          "host_session": transport.opened, **result})
    return EXIT_OK if result["outcome"] != "unknown" else EXIT_DEVICE


def _product_runtime_module(path: Path):
    """Select a frozen product runtime revision from the local/committed policy."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return product_runtime
    if raw.get("runtime_revision") == 9:
        from host import product_runtime_v8
        return product_runtime_v8
    if raw.get("runtime_revision") == 8:
        from host import product_runtime_v7
        return product_runtime_v7
    if raw.get("runtime_revision") == 7:
        from host import product_runtime_v6
        return product_runtime_v6
    if raw.get("runtime_revision") == 6:
        from host import product_runtime_v5
        return product_runtime_v5
    if raw.get("runtime_revision") == 5:
        from host import product_runtime_v4
        return product_runtime_v4
    if raw.get("runtime_revision") == 4:
        from host import product_runtime_v3
        return product_runtime_v3
    if raw.get("runtime_revision") == 3:
        from host import pagination
        return pagination
    return product_runtime_v2 if raw.get("runtime_revision") == 2 else product_runtime


def product_check(args: argparse.Namespace) -> int:
    """Offline review of the persistent product policy. Never touches the Host/device."""
    path = Path(args.policy)
    runtime = _product_runtime_module(path)
    try:
        policy = runtime.load_policy(path, require_authority=False)
    except (product_runtime.ProductPolicyError, product_runtime_v2.ProductPolicyError) as exc:
        emit({"ok": False, "command": "product-check", "device_io": False,
              "execution_ready": False, "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED
    blockers = runtime.authority_blockers(path)
    emit({
        "ok": True, "command": "product-check", "device_io": False,
        "execution_ready": not blockers, "execution_blockers": blockers,
        "product_id": policy.product_id, "policy_file": str(path),
        "exact_unit_id": runtime.EXACT_UNIT_ID,
        "session_lifetime_seconds": policy.session_lifetime_seconds,
        "min_frame_interval_ms": policy.min_frame_interval_ms,
        "max_frames_per_session": policy.max_frames_per_session,
        "max_tx_bytes_per_session": policy.max_tx_bytes_per_session,
        "automatic_reconnect": policy.automatic_reconnect,
        "reclaim_on_canvas_invalidated": policy.reclaim_on_canvas_invalidated,
        "start_at_windows_logon": policy.start_at_windows_logon,
        "reconnect_backoff_seconds": list(policy.reconnect_backoff_seconds),
        "code_hashes_verified": True,
        "host_build_sha256": policy.host_build_sha256,
        "runtime_revision": getattr(runtime, "RUNTIME_REVISION", 1),
    })
    return EXIT_OK


def product_status(args: argparse.Namespace) -> int:
    policy_path = Path(args.policy)
    runtime = _product_runtime_module(policy_path)
    state = runtime.read_runtime_state(Path(args.state_file))
    blockers = runtime.authority_blockers(policy_path) if policy_path.exists() else ["PRODUCT_POLICY_MISSING"]
    result = {"ok": True, "command": "product-status", "device_io": False,
              "policy_file": str(policy_path), "authority_blockers": blockers,
              "runtime_revision": getattr(runtime, "RUNTIME_REVISION", 1),
              "runtime": state}
    pages_state = getattr(runtime, "PAGES_STATE_FILE", None)
    if pages_state is not None and pages_state.is_file():
        result["pages"] = json.loads(pages_state.read_text(encoding="utf-8"))
    emit(result)
    return EXIT_OK


def product_runtime_run(args: argparse.Namespace) -> int:
    """Persistent product supervisor. Only an explicitly authorized local policy may run."""
    path = Path(args.policy)
    runtime = _product_runtime_module(path)
    try:
        policy = runtime.load_policy(path, require_authority=True)
        token = read_token()
        config = _activity_config()
    except (product_runtime.ProductPolicyError, product_runtime_v2.ProductPolicyError) as exc:
        emit({"ok": False, "command": "product-runtime", "error_code": exc.code,
              "detail": exc.detail, "device_io": False})
        return EXIT_BLOCKED
    except (RuntimeError, mcp_activity.SourceError) as exc:
        emit({"ok": False, "command": "product-runtime", "error_code": "PRODUCT_CONFIG_INVALID",
              "detail": str(exc), "device_io": False})
        return EXIT_CONFIG

    import signal
    import threading
    stop = threading.Event()

    def request_stop(_signum, _frame):
        stop.set()

    previous = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, request_stop)
    try:
        state = runtime.run_product(
            policy, lambda: _HostSessionTransport(token),
            stop_requested=stop.is_set,
            config=config,
            state_file=Path(args.state_file),
        )
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    emit({"ok": True, "command": "product-runtime", "device_io": True,
          "stopped": True, "runtime_revision": getattr(runtime, "RUNTIME_REVISION", 1),
          "runtime": state})
    return EXIT_OK


def manifest_check(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        emit({"ok": False, "command": "manifest-check", "error_code": "INVALID_MANIFEST", "message": str(exc)})
        return EXIT_USAGE

    missing: list[str] = []
    for key in ("schema_version", "experiment_id", "milestone", "target", "transport", "operation", "budgets", "authority", "stop_policy"):
        if key not in data:
            missing.append(key)
    blockers: list[str] = []
    target = data.get("target", {}) if isinstance(data.get("target"), dict) else {}
    transport = data.get("transport", {}) if isinstance(data.get("transport"), dict) else {}
    operation = data.get("operation", {}) if isinstance(data.get("operation"), dict) else {}
    authority = data.get("authority", {}) if isinstance(data.get("authority"), dict) else {}
    if not target.get("exact_unit_id"):
        blockers.append("exact_unit_id_unbound")
    if not target.get("installed_firmware"):
        blockers.append("installed_firmware_unbound")
    if not transport.get("measured_endpoint"):
        blockers.append("measured_endpoint_unbound")
    if not operation.get("semantic_evidence"):
        blockers.append("semantic_evidence_missing")
    if not operation.get("application_tx_hex"):
        blockers.append("application_tx_unfrozen")
    if authority.get("transmission_authorized") is not True:
        blockers.append("transmission_authority_missing")

    executable = not missing and not blockers
    emit({
        "ok": not missing,
        "command": "manifest-check",
        "missing_fields": missing,
        "execution_ready": executable,
        "execution_blockers": blockers,
        "device_io": False,
    })
    return EXIT_OK if not missing else EXIT_USAGE


# --------------------------------------------------------------------------
# General bounded 16x16 frame streaming
# --------------------------------------------------------------------------

def stream_prepare(args: argparse.Namespace) -> int:
    """Offline: freeze any 16x16 source into one hashed `.rgb888` frame set.

    Nothing here reaches the Host or the device. It also reports the exact budget block
    a manifest for this content must state, so budgets stay derived rather than guessed.
    """
    try:
        frames = frame_stream.frames_from_source(Path(args.source))
    except frame_stream.SessionError as exc:
        emit({"ok": False, "command": "stream-prepare", "device_io": False,
              "error_code": exc.code, "detail": exc.detail})
        return EXIT_USAGE
    except Png16Error as exc:
        emit({"ok": False, "command": "stream-prepare", "device_io": False,
              "error_code": "STREAM_SOURCE_PNG_REJECTED", "detail": str(exc)})
        return EXIT_USAGE

    quantized = 0
    if args.quantize:
        prepared = []
        for rgb in frames:
            reduced, _ = frame_stream.quantize_to_palette_limit(rgb)
            quantized += reduced != rgb
            prepared.append(reduced)
        frames = prepared

    output = Path(args.output)
    try:
        frame_set = frame_stream.write_frame_set(frames, output)
    except frame_stream.SessionError as exc:
        emit({"ok": False, "command": "stream-prepare", "device_io": False,
              "error_code": exc.code, "detail": exc.detail,
              "hint": "re-run with --quantize to fit the 255-colour encoder limit"})
        return EXIT_USAGE
    emit({
        "ok": True, "command": "stream-prepare", "device_io": False,
        "source": str(args.source), "frame_set_file": str(output),
        "frame_set_sha256": frame_set.sha256, "frame_count": frame_set.count,
        "frames_quantized": quantized,
        "palette_colors_min_max": [min(frame_set.palette_colors), max(frame_set.palette_colors)],
        "max_frame_application_bytes": frame_set.max_frame_tx_bytes,
        "image_packet_sha256_first": frame_set.packet_sha256[0],
        "image_packet_sha256_last": frame_set.packet_sha256[-1],
        "distinct_frames": len(set(frame_set.packet_sha256)),
        "playback_interval_ms": frame_stream.MIN_PLAYBACK_INTERVAL_MS,
        "clip_seconds": frame_set.count * frame_stream.MIN_PLAYBACK_INTERVAL_MS / 1000.0,
        # Straight one-pass playback of this clip, which is what a stream manifest for it
        # must state. Anything else (a longer lifetime, looping) is a different reviewed
        # manifest and derives its own numbers from the same function.
        "derived_budgets_single_pass": frame_stream.derived_budgets(
            frame_set, frame_stream.clip_lifetime_seconds(frame_set),
            frame_stream.MIN_PLAYBACK_INTERVAL_MS, False),
        "code_sha256": frame_stream.module_hashes(),
    })
    return EXIT_OK


def stream_preview(args: argparse.Namespace) -> int:
    """Offline: review one stream manifest and replay it through a fake transport."""
    try:
        manifest, frame_set, stream = frame_stream.load_stream_manifest(
            Path(args.manifest), require_authority=False)
    except frame_stream.SessionError as exc:
        emit({"ok": False, "command": "stream-preview", "device_io": False,
              "execution_ready": False, "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED

    claim = frame_stream.SessionClaim(manifest.experiment_id)
    existing = claim.read()
    blockers = frame_stream.authority_blockers(Path(args.manifest))
    if existing is not None and "AUTHORITY_ALREADY_CONSUMED" not in blockers:
        blockers.append("AUTHORITY_ALREADY_CONSUMED")

    # A fake clock advanced by the runner's own sleeps replays the whole lifetime
    # deterministically, in milliseconds, without waiting for it.
    clock = {"ms": 0}
    transport = activity_session.FakeSessionTransport()
    result = frame_stream.stream_session(
        manifest, frame_set, stream, transport,
        lambda: clock["ms"], lambda ms: clock.__setitem__("ms", clock["ms"] + max(ms, 1)),
        claim=None)
    emit({
        "ok": True, "command": "stream-preview", "device_io": False, "dispatched": False,
        "execution_ready": not blockers, "execution_blockers": blockers,
        "experiment_id": manifest.experiment_id,
        "frame_set_sha256": frame_set.sha256, "frame_count": frame_set.count,
        "playback_interval_ms": stream["playback_interval_ms"], "loop": stream["loop"],
        "lifetime_seconds": manifest.lifetime_seconds,
        "max_frames": manifest.max_frames, "max_tx_bytes": manifest.max_tx_bytes,
        "frames_that_would_be_sent": len(transport.frames),
        "packets_that_would_be_sent": transport.packets,
        "tx_bytes_that_would_be_sent": transport.tx_bytes,
        "host_build_sha256": manifest.host_build_sha256,
        "repository_host_build_sha256": activity_session.sha256_file(activity_session.HOST_BUILD_DLL)
        if activity_session.HOST_BUILD_DLL.is_file() else None,
        "existing_claim": existing,
        "result": result,
    })
    return EXIT_OK


def stream_run(args: argparse.Namespace) -> int:
    """Run ONE reviewed stream manifest, exactly as written.

    No lifetime, rate, budget, loop or target arguments: everything comes from the
    manifest. The experiment id is claimed durably here and again by the Host before
    anything is dispatched, and neither claim can be released.
    """
    try:
        manifest, frame_set, stream = frame_stream.load_stream_manifest(Path(args.manifest))
        token = read_token()
    except frame_stream.SessionError as exc:
        emit({"ok": False, "command": "stream-run", "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED
    except RuntimeError as exc:
        emit({"ok": False, "command": "stream-run", "error_code": "LOCAL_AUTH_CONFIG",
              "message": str(exc)})
        return EXIT_CONFIG

    claim = frame_stream.SessionClaim(manifest.experiment_id)
    try:
        claim.claim({"manifest_file": str(manifest.path), "code_hashes": manifest.code_hashes,
                     "host_build_sha256": manifest.host_build_sha256,
                     "frame_set_sha256": frame_set.sha256,
                     "claimed_at": mcp_activity.iso(mcp_activity.utc_now())})
    except frame_stream.SessionError as exc:
        emit({"ok": False, "command": "stream-run", "error_code": exc.code, "detail": exc.detail})
        return EXIT_BLOCKED

    transport = _HostSessionTransport(token)
    import time
    started = time.monotonic()
    result = frame_stream.stream_session(
        manifest, frame_set, stream, transport,
        lambda: int((time.monotonic() - started) * 1000),
        lambda ms: time.sleep(ms / 1000.0),
        claim=claim)
    emit({"ok": result["outcome"] != "unknown", "command": "stream-run",
          "manifest_file": str(manifest.path), "claim_file": str(claim.path),
          "frame_set_sha256": frame_set.sha256, "frame_count": frame_set.count,
          "host_session": transport.opened, **result})
    return EXIT_OK if result["outcome"] != "unknown" else EXIT_DEVICE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openditoo", description="OpenDitoo typed CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("auth-init", help="create a separate OpenDitoo local Host token")
    p.set_defaults(func=auth_init)
    p = sub.add_parser("status", help="query the separate authenticated OpenDitoo Host")
    p.set_defaults(func=host_status)
    p = sub.add_parser("codec-compare", help="compare one application frame against candidate framing")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=codec_compare)
    p = sub.add_parser("capture-compare", help="compare filtered captured application transactions")
    p.add_argument("--file", required=True)
    p.set_defaults(func=capture_compare)
    p = sub.add_parser("frame-preview", help="materialize the deterministic 16x16 diagnostic frame offline")
    p.add_argument("--output-dir", default=str(local_dir() / "diagnostic-frame"))
    p.set_defaults(func=frame_preview)
    p = sub.add_parser("image-prepare", help="validate and encode one exact 16x16 local PNG offline")
    p.add_argument("--png", required=True)
    p.add_argument("--output-dir")
    p.set_defaults(func=image_prepare)
    p = sub.add_parser("image-show", help="show one exact 16x16 local PNG on the fixed paired Ditoo")
    p.add_argument("--png", required=True)
    p.set_defaults(func=image_show)
    p = sub.add_parser("sequence-run", help="run one reviewed frame-sequence manifest against the fixed paired Ditoo")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=sequence_run)
    p = sub.add_parser("capture-parse", help="offline: filter a raw btsnoop capture to Ditoo serial-port application evidence")
    p.add_argument("--capture", "--btsnoop", dest="btsnoop", required=True,
                   help="an Android bugreport .zip, or an already-extracted btsnoop log")
    p.add_argument("--zip-entry", help="which log inside the archive (default: the current btsnoop_hci.log)")
    # Offline analysis filter over a local file. This selects which captured peer to
    # report on; it is not a device target and reaches nothing.
    p.add_argument("--peer-bdaddr", default="11:75:58:CE:DE:C7")
    p.add_argument("--server-channel", type=int, default=1, help="Bluetooth serial port (SPP) server channel to filter")
    p.add_argument("--reveal", help="comma-separated command ids to include in the clear, e.g. 58,44")
    p.add_argument("--output")
    p.set_defaults(func=capture_parse)
    p = sub.add_parser("capture-avrcp-parse", help="offline: recover AVRCP pass-through key events from a raw btsnoop capture")
    p.add_argument("--capture", "--btsnoop", dest="btsnoop", required=True,
                   help="an Android bugreport .zip, or an already-extracted btsnoop log")
    p.add_argument("--zip-entry", help="which log inside the archive (default: the current btsnoop_hci.log)")
    # Offline analysis filter over a local file; not a device target.
    p.add_argument("--peer-bdaddr", default="11:75:58:CE:DE:C7")
    p.add_argument("--output")
    p.set_defaults(func=capture_avrcp_parse)
    p = sub.add_parser("activity-probe", help="diagnose the three MCP activity sources (read-only)")
    p.set_defaults(func=activity_probe)
    p = sub.add_parser("activity-status", help="normalized MCP activity state; collection health is separate from device health")
    p.add_argument("--collect", action="store_true", help="poll the sources once before reporting")
    p.set_defaults(func=activity_status)
    p = sub.add_parser("activity-preview", help="render the activity display offline to exact and enlarged PNGs")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--scale", type=int, default=16)
    p.add_argument("--output-dir", default=str(local_dir() / "activity-preview"))
    p.set_defaults(func=activity_preview)
    p = sub.add_parser("session-check", help="offline fail-closed review of one activation manifest")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=session_check)
    p = sub.add_parser("session-preview", help="offline: replay a scenario through render, scheduler and a fake transport")
    p.add_argument("--manifest", required=True)
    p.add_argument("--scenario", required=True)
    p.set_defaults(func=session_preview)
    p = sub.add_parser("activity-session", help="run one reviewed activation manifest against the fixed paired Ditoo")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=activity_session_run)
    p = sub.add_parser("stream-prepare", help="offline: freeze a 16x16 frame source into one hashed frame set")
    p.add_argument("--source", required=True, help="a .rgb888 frame blob, or a directory of 16x16 PNGs")
    p.add_argument("--output", required=True, help="frame-set file to write")
    p.add_argument("--quantize", action="store_true",
                   help="reduce frames deterministically to the 255-colour encoder limit")
    p.set_defaults(func=stream_prepare)
    p = sub.add_parser("stream-preview", help="offline: review one stream manifest and replay it against a fake transport")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=stream_preview)
    p = sub.add_parser("stream-run", help="run one reviewed frame-stream manifest against the fixed paired Ditoo")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=stream_run)
    p = sub.add_parser("product-check", help="offline fail-closed review of the persistent MCP product policy")
    p.add_argument("--policy", default=str(product_runtime.DEFAULT_POLICY))
    p.set_defaults(func=product_check)
    p = sub.add_parser("product-status", help="read persistent MCP product supervisor state; no device I/O")
    p.add_argument("--policy", default=str(product_runtime.DEFAULT_POLICY))
    p.add_argument("--state-file", default=str(product_runtime.STATE_FILE))
    p.set_defaults(func=product_status)
    p = sub.add_parser("product-runtime", help="run the explicitly-authorized persistent MCP dashboard supervisor")
    p.add_argument("--policy", default=str(product_runtime.DEFAULT_POLICY))
    p.add_argument("--state-file", default=str(product_runtime.STATE_FILE))
    p.set_defaults(func=product_runtime_run)
    p = sub.add_parser("manifest-check", help="fail-closed review of a Day-1 experiment manifest")
    p.add_argument("--file", required=True)
    p.set_defaults(func=manifest_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
