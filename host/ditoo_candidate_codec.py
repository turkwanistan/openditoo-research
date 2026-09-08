"""Offline candidate codec for comparing captured Ditoo Plus application bytes.

This module performs no I/O. The framing implemented here is an OpenTivoo-derived
comparison hypothesis until an attributable Ditoo Plus stock transaction matches it.
It deliberately contains no command allowlist and no Ditoo transport endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass

START_MARKER = 0x01
END_MARKER = 0x02
MIN_NORMAL_INNER = 3
MIN_WRAPPED_INNER = 5
# Local defensive analysis cap only. This is NOT a claimed Ditoo device limit.
LOCAL_ANALYSIS_MAX_INNER = 0x10000 - 1


class FrameDecodeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NormalFrame:
    command: int
    payload: bytes
    wire: bytes


@dataclass(frozen=True, slots=True)
class WrappedFrame:
    outer_command: int
    command: int
    tag: int
    payload: bytes
    wire: bytes


def checksum16(body: bytes) -> int:
    return sum(body) & 0xFFFF


def encode_candidate_normal(command: int, payload: bytes = b"") -> bytes:
    """Build a comparison fixture only; callers must not treat it as Ditoo authority."""
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in one byte")
    payload = bytes(payload)
    inner = len(payload) + 3
    if inner > LOCAL_ANALYSIS_MAX_INNER:
        raise ValueError("candidate frame exceeds local analysis cap")
    prefix = inner.to_bytes(2, "little") + bytes((command,)) + payload
    check = checksum16(prefix)
    return bytes((START_MARKER,)) + prefix + check.to_bytes(2, "little") + bytes((END_MARKER,))


def _validate_common(data: bytes, minimum_inner: int) -> tuple[int, int]:
    if len(data) < minimum_inner + 4:
        raise FrameDecodeError("candidate frame shorter than minimum")
    if data[0] != START_MARKER:
        raise FrameDecodeError("missing candidate start marker 0x01")
    if data[-1] != END_MARKER:
        raise FrameDecodeError("missing candidate end marker 0x02")
    inner = int.from_bytes(data[1:3], "little")
    if not minimum_inner <= inner <= LOCAL_ANALYSIS_MAX_INNER:
        raise FrameDecodeError(f"candidate inner length {inner} outside local analysis bounds")
    if len(data) != inner + 4:
        raise FrameDecodeError(f"wire length {len(data)} != declared total {inner + 4}")
    stored = int.from_bytes(data[-3:-1], "little")
    calculated = checksum16(data[1:-3])
    if stored != calculated:
        raise FrameDecodeError(
            f"candidate checksum mismatch stored=0x{stored:04X} calculated=0x{calculated:04X}"
        )
    return inner, stored


def decode_candidate_normal(data: bytes) -> NormalFrame:
    data = bytes(data)
    inner, _ = _validate_common(data, MIN_NORMAL_INNER)
    payload_len = inner - 3
    return NormalFrame(data[3], data[4:4 + payload_len], data)


def decode_candidate_wrapped(data: bytes) -> WrappedFrame:
    """Decode the OpenTivoo wrapped-response shape as a Ditoo comparison only."""
    data = bytes(data)
    inner, _ = _validate_common(data, MIN_WRAPPED_INNER)
    payload_len = inner - 5
    return WrappedFrame(data[3], data[4], data[5], data[6:6 + payload_len], data)


class CandidateStreamDecoder:
    """Incrementally test captured streams for normal candidate framing.

    Malformed candidates are retained as error strings so negative evidence is not
    silently discarded. Garbage before 0x01 is skipped only for stream resync.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.errors: list[str] = []

    @property
    def buffered_bytes(self) -> bytes:
        return bytes(self._buffer)

    def feed(self, chunk: bytes) -> list[NormalFrame]:
        self._buffer.extend(bytes(chunk))
        out: list[NormalFrame] = []
        while True:
            try:
                start = self._buffer.index(START_MARKER)
            except ValueError:
                if self._buffer:
                    self.errors.append(f"discarded {len(self._buffer)} byte(s) before candidate start")
                self._buffer.clear()
                break
            if start:
                self.errors.append(f"discarded {start} byte(s) before candidate start")
                del self._buffer[:start]
            if len(self._buffer) < 3:
                break
            inner = int.from_bytes(self._buffer[1:3], "little")
            if not MIN_NORMAL_INNER <= inner <= LOCAL_ANALYSIS_MAX_INNER:
                self.errors.append(f"invalid candidate inner length {inner}")
                del self._buffer[0]
                continue
            total = inner + 4
            if len(self._buffer) < total:
                break
            candidate = bytes(self._buffer[:total])
            try:
                frame = decode_candidate_normal(candidate)
            except FrameDecodeError as exc:
                self.errors.append(str(exc))
                del self._buffer[0]
                continue
            del self._buffer[:total]
            out.append(frame)
        return out


def compare_application_frame(data: bytes) -> dict[str, object]:
    """Return explicit candidate matches without assigning Ditoo semantics."""
    raw = bytes(data)
    result: dict[str, object] = {
        "wire_hex": raw.hex(),
        "wire_length": len(raw),
        "normal_candidate_match": False,
        "wrapped_candidate_match": False,
        "normal": None,
        "wrapped": None,
        "errors": {},
    }
    errors: dict[str, str] = {}
    try:
        normal = decode_candidate_normal(raw)
        result["normal_candidate_match"] = True
        result["normal"] = {"command": normal.command, "payload_hex": normal.payload.hex()}
    except FrameDecodeError as exc:
        errors["normal"] = str(exc)
    try:
        wrapped = decode_candidate_wrapped(raw)
        result["wrapped_candidate_match"] = True
        result["wrapped"] = {
            "outer_command": wrapped.outer_command,
            "command": wrapped.command,
            "tag": wrapped.tag,
            "payload_hex": wrapped.payload.hex(),
        }
    except FrameDecodeError as exc:
        errors["wrapped"] = str(exc)
    result["errors"] = errors
    return result
