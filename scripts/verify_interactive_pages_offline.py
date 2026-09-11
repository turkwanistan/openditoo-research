#!/usr/bin/env python3
"""Canonical offline gate for the high-FPS interactive-pages successor work.

No Host or device access. This runs only deterministic Python tests and reports milestone gates
that may be consumed by future fresh sessions before any live manifest is prepared.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TEST_MODULES = (
    "tests.test_interactive_pages",
    "tests.test_activity_lightning",
    "tests.test_interactive_acceptance",
    "tests.test_product_runtime_v3",
)


def main() -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in TEST_MODULES)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        print("INTERACTIVE_PAGES_OFFLINE=FAIL")
        return 1
    print("UI1_LIGHTNING_OFFLINE=PASS")
    print("HF1_INTERACTIVE_PAGE_PRIMITIVE=PASS")
    print("GAME1_SLOTS_OFFLINE=PASS")
    print("HF2_PROFILE_ORCHESTRATOR=PASS")
    print("HF3_ACCEPTANCE_ENVELOPE_OFFLINE=PASS")
    print("HF4_RUNTIME_008_OFFLINE=PASS")
    print(f"INTERACTIVE_PAGES_OFFLINE=PASS tests={result.testsRun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
