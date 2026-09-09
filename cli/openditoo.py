#!/usr/bin/env python3
"""Typed OpenDitoo CLI.

The live surface is intentionally narrow: a fixed authenticated Host may show one
validated 16x16 PNG on the exact paired Ditoo. There is no target selector, raw
packet send, generic Bluetooth command, automatic retry, or firmware path.
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

CLI_VERSION = "0.2.0-static-image"
HOST_ORIGIN = "http://127.0.0.1:8796"
STATUS_URL = f"{HOST_ORIGIN}/v1/status"
IMAGE_SHOW_URL = f"{HOST_ORIGIN}/v1/image/show"
MIN_TOKEN_CHARS = 32

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFIG = 10
EXIT_HOST_UNAVAILABLE = 20
EXIT_AUTH = 21
EXIT_PROTOCOL = 22
EXIT_BLOCKED = 30
EXIT_DEVICE = 31


def local_dir() -> Path:
    return ROOT / ".openditoo-local"


def token_file() -> Path:
    return local_dir() / "host.token"


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
            body = json.loads(response.read(65537).decode("utf-8"))
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
            result = json.loads(response.read(65537).decode("utf-8"))
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
