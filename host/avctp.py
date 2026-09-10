"""Offline AVCTP/AVRCP pass-through decoder for exact-unit Ditoo HCI evidence (BTN-0).

Decodes only what the button route needs: AVRCP PASS THROUGH commands carried on
AVCTP (L2CAP PSM 0x0017). Everything else on the channel (vendor-dependent
metadata, notifications, fragmented AVCTP packets) is counted, never interpreted.
Performs no I/O beyond reading the capture it is given and no device access.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from host import btsnoop

AVRCP_PROFILE_ID = 0x110E
AVCTP_SINGLE_PACKET = 0
CTYPE_CONTROL = 0x00
RESPONSE_ACCEPTED = 0x09
SUBUNIT_PANEL = 0x48  # subunit type 9 (panel) << 3 | id 0
OPCODE_PASS_THROUGH = 0x7C
STATE_RELEASED = 0x80

# Standard AV/C panel operation ids, named only for the ids the exact unit emitted.
OPERATION_LABELS = {0x44: "play", 0x46: "pause", 0x4B: "forward", 0x4C: "backward"}


@dataclass(frozen=True, slots=True)
class PassThrough:
    at: object          # datetime
    direction: str      # btsnoop "rx" (peer -> phone) or "tx"
    label: int          # AVCTP transaction label
    is_response: bool
    ctype: int          # command type, or response code when is_response
    operation: int      # 7-bit operation id
    released: bool


def decode(at, direction: str, pdu: bytes) -> PassThrough | None:
    """Return a PassThrough for one AVCTP PDU, or None if it is anything else.

    Fails closed: a fragmented/short/foreign PDU yields None rather than a guess.
    """
    if len(pdu) < 3:
        return None
    header = pdu[0]
    if (header >> 2) & 0x03 != AVCTP_SINGLE_PACKET or int.from_bytes(pdu[1:3], "big") != AVRCP_PROFILE_ID:
        return None
    if header & 0x01:  # IPID: profile not supported by the receiver
        return None
    frame = pdu[3:]
    # ctype | subunit | opcode | operation(state bit + id) | operation data length
    if len(frame) < 5 or frame[1] != SUBUNIT_PANEL or frame[2] != OPCODE_PASS_THROUGH:
        return None
    if len(frame) != 5 + frame[4]:
        return None  # truncated or padded pass-through; do not synthesize an event
    return PassThrough(at, direction, header >> 4, bool(header & 0x02), frame[0] & 0x0F,
                       frame[3] & 0x7F, bool(frame[3] & STATE_RELEASED))


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """One press paired with its release, both as commands from the same controller."""
    operation: int
    direction: str
    pressed_at: object
    released_at: object
    press_accepted: bool
    release_accepted: bool


def pair_presses(items: list[PassThrough]) -> tuple[list[KeyEvent], list[PassThrough]]:
    """Pair each CONTROL press with the next release of the same operation.

    Returns (events, unpaired). Press and release carry different transaction labels,
    so pairing is by operation and order; acceptance is by label + operation match of
    the response travelling the other way. A second press before a release leaves the
    first press unpaired rather than inventing a release for it.
    """
    commands = [item for item in items if not item.is_response and item.ctype == CTYPE_CONTROL]
    accepted = {(item.direction, item.label, item.operation, item.released)
                for item in items if item.is_response and item.ctype == RESPONSE_ACCEPTED}

    def was_accepted(command: PassThrough) -> bool:
        back = btsnoop.HOST_TO_CONTROLLER if command.direction == btsnoop.CONTROLLER_TO_HOST else btsnoop.CONTROLLER_TO_HOST
        return (back, command.label, command.operation, command.released) in accepted

    events: list[KeyEvent] = []
    unpaired: list[PassThrough] = []
    open_press: dict[tuple[str, int], PassThrough] = {}
    for command in commands:
        key = (command.direction, command.operation)
        if not command.released:
            if key in open_press:
                unpaired.append(open_press[key])
            open_press[key] = command
        elif key in open_press:
            press = open_press.pop(key)
            events.append(KeyEvent(command.operation, command.direction, press.at, command.at,
                                   was_accepted(press), was_accepted(command)))
        else:
            unpaired.append(command)
    unpaired.extend(open_press.values())
    unpaired.sort(key=lambda item: item.at)
    return events, unpaired


def read(path: Path, peer_bdaddr: str | None = None, zip_entry: str | None = None):
    """Parse a capture into (provenance, [PassThrough], counts of non-pass-through AVCTP PDUs)."""
    data, provenance = btsnoop.load_capture(Path(path), zip_entry)
    records = list(btsnoop.parse_records(data))
    handles = btsnoop.peer_handles(btsnoop.acl_handles(records), peer_bdaddr)
    items: list[PassThrough] = []
    other = {"rx": 0, "tx": 0}
    for at, direction, pdu in btsnoop.channel_pdus(records, handles, btsnoop.L2CAP_PSM_AVCTP):
        item = decode(at, direction, pdu)
        if item is None:
            other[direction] += 1
        else:
            items.append(item)
    return provenance, items, other


CORRELATION_WINDOW_MS = 100


def _utc(at) -> str:
    return at.isoformat().replace("+00:00", "Z")


def derive_evidence(path: Path, peer_bdaddr: str, zip_entry: str | None = None) -> dict:
    """Committable, payload-minimal AVRCP key evidence plus RFCOMM report correlation.

    Revealed bytes are limited to AVRCP operation ids and the peer's unsolicited
    wrapped 0x04 device-state reports within the correlation window of a press;
    both were already committable under M7. Phone-originated payloads stay withheld.
    """
    provenance, items, other = read(path, peer_bdaddr, zip_entry)
    events, unpaired = pair_presses(items)
    _, frames, _ = btsnoop.read(path, peer_bdaddr=peer_bdaddr, reveal_commands={0x04}, zip_entry=zip_entry)
    reports = [frame for frame in frames if frame.direction == btsnoop.CONTROLLER_TO_HOST and frame.hex]
    records = []
    for event in events:
        nearby = []
        for frame in reports:
            offset_ms = (frame.at - event.pressed_at).total_seconds() * 1000
            if abs(offset_ms) <= CORRELATION_WINDOW_MS:
                wire = bytes.fromhex(frame.hex)
                nearby.append({"at_utc": _utc(frame.at), "offset_ms_from_press": round(offset_ms, 3),
                               "reported_command": f"0x{wire[4]:02X}", "wire_hex": frame.hex})
        records.append({
            "operation": f"0x{event.operation:02X}",
            "release_operation_byte": f"0x{event.operation | STATE_RELEASED:02X}",
            "evidence_label": OPERATION_LABELS.get(event.operation, "unlabelled"),
            "direction": "peer_to_phone" if event.direction == btsnoop.CONTROLLER_TO_HOST else "phone_to_peer",
            "pressed_at_utc": _utc(event.pressed_at),
            "released_at_utc": _utc(event.released_at),
            "hold_ms": round((event.released_at - event.pressed_at).total_seconds() * 1000, 3),
            "press_accepted": event.press_accepted,
            "release_accepted": event.release_accepted,
            "rfcomm_reports_within_window": nearby,
        })
    return {
        "provenance": provenance,
        "peer": peer_bdaddr.upper(),
        "l2cap_psm": f"0x{btsnoop.L2CAP_PSM_AVCTP:04X}",
        "correlation_window_ms": CORRELATION_WINDOW_MS,
        "pass_through_pdus": len(items),
        "non_pass_through_avctp_pdus": other,
        "unpaired_pass_through": [{"at_utc": _utc(item.at), "operation": f"0x{item.operation:02X}",
                                   "released": item.released} for item in unpaired],
        "key_events": records,
    }
