#!/usr/bin/env python3
"""Derive `host/activity_ui_data.py` from the approved UI reference frames.

The design arrived as PNG mockups, not as a table of pixels. Hand-transcribing them is
exactly the mistake this project already made once with a capture payload, so nothing is
transcribed: the layout, the four status roles, the crown and the blue override colour
are all *derived* from `assets/ui/reference/`, and `tests/test_day1_offline.py` re-runs
this derivation and asserts it still matches the committed file.

Offline. Reads local PNGs, writes one Python file. No device, no network.

    python3 scripts/generate_activity_ui_data.py [--check]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.png16 import decode_png16_rgb  # noqa: E402

REFERENCE = ROOT / "assets/ui/reference"
OUTPUT = ROOT / "host/activity_ui_data.py"

SIZE = 16
STATUSES = ("green", "yellow", "red", "grey")

# Column slots, from the approved spec: 5 px per source, x=15 spare.
SLOTS = {"optiplex_lab": 0, "optiplex_mcp": 5, "wsl_mcp": 10}

# Which reference frame shows which single column mid-activity.
ACTIVITY_FRAMES = {"optiplex_lab": "left", "optiplex_mcp": "mid", "wsl_mcp": "right"}

# Operator change, 2026-09-09: icons in the middle band, letters on the bottom.
# Applied as an explicit transform of the approved artwork rather than by editing pixels,
# so the mockups stay the source of truth and the change stays reviewable and reversible.
# Rows 0-2 (crown), 3-4 (spacer) and 10 (divider) are untouched; the two 5-row blocks swap.
LETTER_ROWS = range(5, 10)
ICON_ROWS = range(11, 16)
SWAP_LETTERS_AND_ICONS = True


def flip_row(y: int) -> int:
    if not SWAP_LETTERS_AND_ICONS:
        return y
    if y in LETTER_ROWS:
        return y + 6
    if y in ICON_ROWS:
        return y - 6
    return y


def flip_index(index: int) -> int:
    return flip_row(index // SIZE) * SIZE + index % SIZE


def load(name: str) -> list[tuple[int, int, int]]:
    rgb = decode_png16_rgb(REFERENCE / name)
    return [tuple(rgb[i:i + 3]) for i in range(0, len(rgb), 3)]


def classify(green, red) -> str:
    """Name a status role by how it renders green and red.

    Letters and the mushroom cap's mid tone are both pure green when fresh; they part
    company at red, where the cap turns (255,0,85) and the letters (255,0,0). That is
    why both frames are needed to tell them apart.
    """
    if green == (0, 170, 0):
        return "cap_dark"
    if green == (85, 255, 85):
        return "cap_light"
    if green == (0, 255, 0):
        return "cap_base" if red == (255, 0, 85) else "accent"
    raise SystemExit(f"unrecognised status role: green={green} red={red}")


def derive() -> str:
    frames = {status: load(f"all_{status}_16x16.png") for status in STATUSES}

    # Derived in the mockups' own coordinates throughout; flip_index is applied only at
    # emit time, so the crown and override derivations below still index the real frames.
    fixed: list[tuple[int, tuple[int, int, int]]] = []
    role_colors: dict[str, dict[str, tuple[int, int, int]]] = {}
    role_pixels: dict[str, list[int]] = {}
    for index in range(SIZE * SIZE):
        values = {status: frames[status][index] for status in STATUSES}
        if len(set(values.values())) == 1:
            if values["green"] != (0, 0, 0):
                fixed.append((index, values["green"]))
            continue
        role = classify(values["green"], values["red"])
        existing = role_colors.setdefault(role, values)
        if existing != values:
            raise SystemExit(f"role {role} is not consistent at pixel {index}")
        role_pixels.setdefault(role, []).append(index)

    # The crown: the only thing lit in rows 0-2, and only above the active column.
    crown: list[tuple[int, int, tuple[int, int, int]]] = []
    override: set[tuple[int, int, int]] = set()
    for source_id, prefix in ACTIVITY_FRAMES.items():
        active = load(f"{prefix}_activity_blue_override_16x16.png")
        base = SLOTS[source_id]
        shape = []
        for index in range(SIZE * 3):
            if active[index] == (0, 0, 0):
                continue
            x, y = index % SIZE, index // SIZE
            shape.append((x - base, y, active[index]))
        if crown and crown != shape:
            raise SystemExit(f"crown shape differs for {source_id}")
        crown = shape
        # Every status pixel in the active column takes the override colour; every
        # status pixel outside it keeps its own status colour.
        for role, pixels in role_pixels.items():
            for index in pixels:
                if base <= index % SIZE < base + 5:
                    override.add(active[index])
    if len(override) != 1:
        raise SystemExit(f"expected one blue override colour, found {sorted(override)}")

    lines = [
        '"""Approved 16x16 MCP activity UI, derived from the reference mockups.',
        "",
        "GENERATED by scripts/generate_activity_ui_data.py from assets/ui/reference/.",
        "Do not edit by hand: a test re-derives this file and fails if it drifts.",
        "",
        "Layout: rows 0-2 activity crown, 3-4 spacer, 5-9 icons, 10 divider, 11-15",
        "identity letters. Columns are 5 px per source; x=15 is spare. The approved",
        "mockups place letters above icons; the two blocks are swapped here at the",
        "operator's request, as an explicit transform (see generate_activity_ui_data.py).",
        "All colours are RGB222-legal (channels in 0/85/170/255), which is a strict",
        "subset of the RGB888 the Ditoo encoder already sends -- the palette is a design",
        "constraint inherited with the artwork, never a device constraint.",
        '"""',
        "from __future__ import annotations",
        "",
        f"SIZE = {SIZE}",
        f"STATUSES = {STATUSES!r}",
        "",
        "# source id -> leftmost x of its 5 px column",
        f"SLOTS = {SLOTS!r}",
        "",
        "# Pixels that never change: the sprite bodies, stems, ears and bones.",
        "FIXED = (",
    ]
    lines += [f"    ({index}, {color!r})," for index, color in sorted((flip_index(i), c) for i, c in fixed)]
    lines += [
        ")",
        "",
        "# Pixels that carry status, and the colour each role takes per status.",
        "ROLE_COLORS = {",
    ]
    for role in sorted(role_colors):
        entries = ", ".join(f"{status!r}: {role_colors[role][status]!r}" for status in STATUSES)
        lines.append(f"    {role!r}: {{{entries}}},")
    lines += ["}", "", "ROLE_PIXELS = {"]
    for role in sorted(role_pixels):
        lines.append(f"    {role!r}: {tuple(sorted(flip_index(i) for i in role_pixels[role]))!r},")
    lines += [
        "}",
        "",
        "# Activity crown, as (dx, dy, rgb) offsets from the active column's left edge.",
        f"CROWN = {tuple(crown)!r}",
        "",
        "# During activity every status pixel in that column takes this one colour.",
        f"OVERRIDE_RGB = {sorted(override)[0]!r}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed file has drifted")
    args = parser.parse_args()
    generated = derive()
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != generated:
            raise SystemExit("ACTIVITY_UI_DATA_DRIFT: regenerate with scripts/generate_activity_ui_data.py")
        print("ACTIVITY_UI_DATA_OK")
        return 0
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
