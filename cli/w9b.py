#!/usr/bin/env python3
"""W9B optical analysis of high-speed footage. Offline only: reads files, never a device.

Extract frames first, because ffmpeg already does that better than a wrapper would:

    ffmpeg -i slowmo.mov -vsync 0 /tmp/w9b/%06d.png

Then check the corner marks on ONE frame before analysing hundreds:

    python3 cli/w9b.py check --frame /tmp/w9b/000001.png \\
        --monitor 90,60 430,110 400,430 60,360 --ditoo 500,350 660,350 660,510 500,510

Then analyse:

    python3 cli/w9b.py analyse --frames /tmp/w9b --fps 240 \\
        --monitor ... --ditoo ... [--trial captures/<trial-result>.json]

Corners are four "x,y" points, clockwise from the top-left of the region as it appears upright.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import w9b_optical


def quad(values):
    if len(values) != 4:
        raise argparse.ArgumentTypeError("a region needs exactly 4 corners")
    return [tuple(float(part) for part in value.split(",")) for value in values]


parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("command", choices=("check", "analyse"))
parser.add_argument("--frame", help="one extracted frame, for `check`")
parser.add_argument("--frames", help="directory of extracted frames, for `analyse`")
parser.add_argument("--monitor", nargs=4, required=True, metavar="X,Y")
parser.add_argument("--ditoo", nargs=4, required=True, metavar="X,Y")
parser.add_argument("--fps", type=float, help="footage frame rate, for `analyse`")
parser.add_argument("--trial", help="trial result JSON to correlate against")
args = parser.parse_args()

try:
    monitor_quad, ditoo_quad = quad(args.monitor), quad(args.ditoo)
    if args.command == "check":
        if not args.frame:
            raise ValueError("--frame is required for check")
        image = w9b_optical.read_frame(Path(args.frame))
        # Both must decode before a long run is worth filming. A None here means a corner is
        # wrong, the region is out of focus, or the frame caught a mid-transition redraw.
        monitor = w9b_optical.decode_region(image, monitor_quad, mirrored=False)
        ditoo = w9b_optical.decode_region(image, ditoo_quad, mirrored=True)
        print(json.dumps({"ok": monitor is not None and ditoo is not None,
                          "monitor_counter": monitor, "ditoo_counter": ditoo,
                          "device_io": False}, sort_keys=True))
        raise SystemExit(0 if monitor is not None and ditoo is not None else 2)

    if not args.frames or not args.fps:
        raise ValueError("--frames and --fps are required for analyse")
    frames = sorted(p for p in Path(args.frames).iterdir()
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not frames:
        raise ValueError("no extracted frames found")
    report = w9b_optical.analyse_frames(frames, monitor_quad, ditoo_quad, args.fps)
    if args.trial:
        report["correlation"] = w9b_optical.correlate_with_trial(
            report, json.loads(Path(args.trial).read_text(encoding="utf-8")))
    report["device_io"] = False
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["meets_minimum_transitions"] else 2)
except SystemExit:
    raise
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc), "device_io": False}))
    raise SystemExit(2)
