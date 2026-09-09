#!/usr/bin/env python3
"""One fixed-envelope webcam trial. No target, timing, raw-send or retry switches."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import webcam_trial

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("command", choices=("run",))
parser.add_argument("--manifest", required=True)
args = parser.parse_args()
try:
    result = webcam_trial.run(Path(args.manifest))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["outcome"] == "stopped_clean" else 2)
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc), "outcome": "unknown"}))
    raise SystemExit(2)
