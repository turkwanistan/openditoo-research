"""Offline btsnoop (Android HCI snoop) reader for exact-unit Ditoo evidence.

Turns a raw `btsnoop_hci.log` into attributable, filtered RFCOMM application
frames. Performs no I/O beyond reading the file it is given and no device access.

Privacy is a design constraint, not an option: a snoop log contains the whole
phone's Bluetooth traffic, and a prior capture held an official-app frame with
account metadata. Payload bytes are therefore withheld by default and summarized
by command id and SHA-256; a caller must name the command ids it wants in the
clear.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import struct
import zipfile

from host.ditoo_candidate_codec import CandidateStreamDecoder

MAGIC = b"btsnoop\x00"
# btsnoop timestamps are microseconds since 0000-01-01; this is the offset to the Unix epoch.
EPOCH_DELTA_US = 0x00DCDDB30F2F8000
UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

H4_COMMAND, H4_ACL, H4_SCO, H4_EVENT = 0x01, 0x02, 0x03, 0x04
EVT_CONNECTION_COMPLETE, EVT_DISCONNECTION_COMPLETE = 0x03, 0x05
L2CAP_SIGNALLING_CID = 0x0001
L2CAP_PSM_RFCOMM = 0x0003
SIG_CONNECTION_REQUEST, SIG_CONNECTION_RESPONSE = 0x02, 0x03
SIG_DISCONNECTION_REQUEST, SIG_DISCONNECTION_RESPONSE = 0x06, 0x07

RFCOMM_UIH = 0xEF
RFCOMM_PF = 0x10
RFCOMM_FRAME_TYPES = {0x2F: "SABM", 0x63: "UA", 0x0F: "DM", 0x43: "DISC", 0xEF: "UIH"}

HOST_TO_CONTROLLER = "tx"  # host -> controller -> peer
CONTROLLER_TO_HOST = "rx"


class BtsnoopError(ValueError):
    pass


def _crc8_table() -> list[int]:
    table = []
    for index in range(256):
        value = index
        for _ in range(8):
            value = (value >> 1) ^ 0xE0 if value & 1 else value >> 1
        table.append(value)
    return table


_CRC8 = _crc8_table()


def rfcomm_fcs(data: bytes) -> int:
    """RFCOMM/TS 07.10 frame check sequence."""
    crc = 0xFF
    for byte in data:
        crc = _CRC8[crc ^ byte]
    return 0xFF - crc


BUGREPORT_SNOOP_DIR = "FS/data/misc/bluetooth/logs/"
BUGREPORT_SNOOP_CURRENT = BUGREPORT_SNOOP_DIR + "btsnoop_hci.log"
BUGREPORT_SNOOP_PREVIOUS = BUGREPORT_SNOOP_CURRENT + ".last"


def load_capture(path: Path, zip_entry: str | None = None) -> tuple[bytes, dict]:
    """Return capture bytes plus provenance, accepting a raw log or a bugreport zip.

    Taking the zip directly means the operator never hand-extracts a snoop log, and the
    raw archive hash is recorded in the same step.
    """
    path = Path(path)
    raw = path.read_bytes()
    provenance = {"source_file": str(path), "source_sha256": hashlib.sha256(raw).hexdigest()}
    if not zipfile.is_zipfile(path):
        provenance["container"] = "raw_btsnoop"
        return raw, provenance

    with zipfile.ZipFile(path) as archive:
        available = [name for name in archive.namelist() if "btsnoop" in name.lower()]
        if not available:
            raise BtsnoopError("bugreport archive contains no btsnoop log")
        entry = zip_entry or (BUGREPORT_SNOOP_CURRENT if BUGREPORT_SNOOP_CURRENT in available else available[0])
        if entry not in available:
            raise BtsnoopError(f"entry not in archive: {entry}")
        data = archive.read(entry)
    provenance.update({
        "container": "android_bugreport_zip",
        "zip_entry": entry,
        "btsnoop_sha256": hashlib.sha256(data).hexdigest(),
        "other_btsnoop_entries": sorted(name for name in available if name != entry),
    })
    return data, provenance


@dataclass(frozen=True, slots=True)
class HciRecord:
    at: datetime
    direction: str
    h4_type: int
    payload: bytes


def parse_records(data: bytes):
    """Yield HciRecord in file order. Truncated trailing records are reported."""
    if not data.startswith(MAGIC):
        raise BtsnoopError("not a btsnoop file")
    if len(data) < 16:
        raise BtsnoopError("btsnoop header is truncated")
    version, datalink = struct.unpack(">II", data[8:16])
    if version != 1:
        raise BtsnoopError(f"unsupported btsnoop version {version}")
    offset = 16
    while offset < len(data):
        if offset + 24 > len(data):
            raise BtsnoopError("truncated btsnoop record header")
        original, included, flags, _drops, stamp = struct.unpack(">IIIIq", data[offset:offset + 24])
        offset += 24
        if offset + included > len(data):
            raise BtsnoopError("truncated btsnoop record payload")
        blob = data[offset:offset + included]
        offset += included
        if not blob or included != original:
            continue  # a snapped record cannot be parsed as a whole packet
        at = UNIX_EPOCH + timedelta(microseconds=stamp - EPOCH_DELTA_US)
        direction = CONTROLLER_TO_HOST if flags & 0x01 else HOST_TO_CONTROLLER
        yield HciRecord(at, direction, blob[0], blob[1:])
    return datalink


def format_bdaddr(little_endian: bytes) -> str:
    return ":".join(f"{byte:02X}" for byte in reversed(little_endian))


@dataclass
class TransportView:
    """What the capture establishes about the link, independent of payloads."""

    handles: dict = field(default_factory=dict)          # handle -> bdaddr
    rfcomm_cids: set = field(default_factory=set)
    psm_requested: set = field(default_factory=set)
    dlcis_seen: dict = field(default_factory=dict)       # dlci -> frame type counter
    fcs_failures: int = 0
    first_at: datetime | None = None
    last_at: datetime | None = None
    provenance: dict = field(default_factory=dict)


@dataclass
class ApplicationFrame:
    at: datetime
    direction: str
    dlci: int
    command: int
    length: int
    sha256: str
    hex: str | None  # populated only for explicitly requested commands


def _iter_l2cap(records, handles_for_peer: set | None):
    """Reassemble ACL fragments into L2CAP PDUs per handle and direction."""
    buffers: dict[tuple[int, str], bytearray] = {}
    expected: dict[tuple[int, str], int] = {}
    for record in records:
        if record.h4_type != H4_ACL or len(record.payload) < 4:
            continue
        handle_flags, data_len = struct.unpack("<HH", record.payload[:4])
        handle = handle_flags & 0x0FFF
        boundary = (handle_flags >> 12) & 0x03
        if handles_for_peer is not None and handle not in handles_for_peer:
            continue
        body = record.payload[4:4 + data_len]
        key = (handle, record.direction)
        if boundary == 0x01:  # continuation
            if key not in buffers:
                continue  # fragment without its start; the PDU is unrecoverable
            buffers[key].extend(body)
        else:
            buffers[key] = bytearray(body)
            if len(body) >= 2:
                expected[key] = struct.unpack("<H", body[:2])[0] + 4
        buffer = buffers.get(key)
        if buffer is None or key not in expected:
            continue
        if len(buffer) >= expected[key]:
            pdu = bytes(buffer[:expected[key]])
            del buffers[key]
            del expected[key]
            if len(pdu) >= 4:
                cid = struct.unpack("<H", pdu[2:4])[0]
                yield record.at, record.direction, cid, pdu[4:]


def read(path: Path, peer_bdaddr: str | None = None, server_channel: int = 1,
         reveal_commands: set[int] | None = None, zip_entry: str | None = None):
    """Parse one capture into (TransportView, [ApplicationFrame], decoder errors).

    `path` may be a raw btsnoop log or an Android bugreport zip.
    """
    reveal_commands = reveal_commands or set()
    data, provenance = load_capture(Path(path), zip_entry)
    records = list(parse_records(data))
    view = TransportView()
    if records:
        view.first_at, view.last_at = records[0].at, records[-1].at

    # Attribute ACL handles to peers so unrelated devices are excluded up front.
    for record in records:
        if record.h4_type != H4_EVENT or len(record.payload) < 2:
            continue
        code, length = record.payload[0], record.payload[1]
        params = record.payload[2:2 + length]
        if code == EVT_CONNECTION_COMPLETE and len(params) >= 10 and params[0] == 0:
            view.handles[struct.unpack("<H", params[1:3])[0]] = format_bdaddr(params[3:9])
        elif code == EVT_DISCONNECTION_COMPLETE and len(params) >= 3 and params[0] == 0:
            view.handles.pop(struct.unpack("<H", params[1:3])[0], None)

    handles = None
    if peer_bdaddr:
        wanted = peer_bdaddr.upper()
        handles = {handle for handle, address in view.handles.items() if address == wanted}
        if not handles:
            raise BtsnoopError(f"no completed ACL connection to {peer_bdaddr} in this capture")

    # Learn which L2CAP CIDs carry RFCOMM (PSM 3) before decoding any RFCOMM.
    application_dlci = (server_channel << 1)
    streams = {HOST_TO_CONTROLLER: CandidateStreamDecoder(), CONTROLLER_TO_HOST: CandidateStreamDecoder()}
    frames: list[ApplicationFrame] = []

    # One chronological pass. An L2CAP CID is only RFCOMM between its successful
    # connection response and its disconnection: CIDs are recycled to other PSMs
    # afterwards, and treating a stale CID as RFCOMM mis-frames unrelated traffic
    # into phantom application data.
    #
    # L2CAP signalling identifiers are also a small reused sequence, so a response
    # must be matched to a request with the same identifier travelling the other way.
    pending: dict[tuple[int, str], int] = {}
    live_cids: set[int] = set()

    for at, direction, cid, payload in _iter_l2cap(records, handles):
        if cid == L2CAP_SIGNALLING_CID:
            if len(payload) < 4:
                continue
            code, identifier, length = payload[0], payload[1], struct.unpack("<H", payload[2:4])[0]
            body = payload[4:4 + length]
            opposite = CONTROLLER_TO_HOST if direction == HOST_TO_CONTROLLER else HOST_TO_CONTROLLER
            if code == SIG_CONNECTION_REQUEST and len(body) >= 4:
                psm, scid = struct.unpack("<HH", body[:4])
                view.psm_requested.add(psm)
                if psm == L2CAP_PSM_RFCOMM:
                    pending[(identifier, direction)] = scid
            elif code == SIG_CONNECTION_RESPONSE and len(body) >= 6:
                dcid, scid, result = struct.unpack("<HHH", body[:6])
                key = (identifier, opposite)
                if key not in pending or result == 0x0001:
                    continue  # unrelated identifier, or a "pending" response
                if result == 0 and pending[key] == scid:
                    live_cids.update({dcid, scid})
                    view.rfcomm_cids.update({dcid, scid})
                pending.pop(key, None)
            elif code in (SIG_DISCONNECTION_REQUEST, SIG_DISCONNECTION_RESPONSE) and len(body) >= 4:
                dcid, scid = struct.unpack("<HH", body[:4])
                live_cids.difference_update({dcid, scid})
            continue

        if cid not in live_cids or len(payload) < 4:
            continue
        address, control = payload[0], payload[1]
        dlci = address >> 2
        frame_type = control & ~RFCOMM_PF
        label = RFCOMM_FRAME_TYPES.get(frame_type, f"0x{frame_type:02X}")

        index = 2
        length_byte = payload[index]
        if length_byte & 0x01:
            length, index = length_byte >> 1, index + 1
        else:
            length = (length_byte >> 1) | (payload[index + 1] << 7)
            index += 2
        # UIH covers only address+control; other frame types include the length field.
        covered = payload[:2] if frame_type == RFCOMM_UIH else payload[:index]
        if rfcomm_fcs(covered) != payload[-1]:
            view.fcs_failures += 1
            continue

        view.dlcis_seen.setdefault(dlci, {}).setdefault(label, 0)
        view.dlcis_seen[dlci][label] += 1
        if frame_type != RFCOMM_UIH or dlci != application_dlci:
            continue
        if control & RFCOMM_PF:
            index += 1  # credit-based flow control byte, not application data
        body = payload[index:index + length]
        if not body:
            continue
        for decoded in streams[direction].feed(body):
            frames.append(ApplicationFrame(
                at=at,
                direction=direction,
                dlci=dlci,
                command=decoded.command,
                length=len(decoded.wire),
                sha256=hashlib.sha256(decoded.wire).hexdigest(),
                hex=decoded.wire.hex() if decoded.command in reveal_commands else None,
            ))

    view.provenance = provenance
    errors = {direction: decoder.errors for direction, decoder in streams.items()}
    return view, frames, errors


def summarize(view: TransportView, frames: list[ApplicationFrame], errors: dict) -> dict:
    """A committable, payload-free summary. Revealed hex is included only if asked for."""
    by_command: dict[str, dict] = {}
    for frame in frames:
        entry = by_command.setdefault(f"0x{frame.command:02X}", {"count": 0, "directions": set(), "lengths": set()})
        entry["count"] += 1
        entry["directions"].add(frame.direction)
        entry["lengths"].add(frame.length)
    return {
        "provenance": view.provenance,
        "capture_window": {
            "first_record_utc": view.first_at.isoformat().replace("+00:00", "Z") if view.first_at else None,
            "last_record_utc": view.last_at.isoformat().replace("+00:00", "Z") if view.last_at else None,
        },
        "acl_handles": {f"0x{handle:04X}": address for handle, address in sorted(view.handles.items())},
        "l2cap_psm_requested": sorted(f"0x{psm:04X}" for psm in view.psm_requested),
        "rfcomm_cids": sorted(f"0x{cid:04X}" for cid in view.rfcomm_cids),
        "rfcomm_dlci_frames": {str(dlci): counts for dlci, counts in sorted(view.dlcis_seen.items())},
        "rfcomm_fcs_failures": view.fcs_failures,
        "application_frames": sum(entry["count"] for entry in by_command.values()),
        "application_commands": {
            command: {"count": entry["count"], "directions": sorted(entry["directions"]),
                      "wire_lengths": sorted(entry["lengths"])}
            for command, entry in sorted(by_command.items())
        },
        "decoder_errors": {direction: len(items) for direction, items in errors.items()},
        "payloads_withheld_by_default": True,
    }
