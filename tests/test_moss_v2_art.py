from __future__ import annotations

import json
from pathlib import Path
import unittest

from host.moss_page import ASSET_ROOT
from host.pixel_animation import animation_quality, load_animation
from host.pixel_art import geometry, load_sprite


class MossV2ArtTests(unittest.TestCase):
    def test_default_asset_root_is_v2_and_idle_has_high_contrast_dog_cues(self):
        self.assertEqual(ASSET_ROOT.name, "v2")
        path = ASSET_ROOT / "sprites" / "idle.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        sprite = load_sprite(path)
        rows, palette = raw["rows"], raw["palette"]
        self.assertEqual(sprite.id, "moss.v2.idle")
        self.assertGreaterEqual(sum(r.count("b") for r in rows), 16)  # hanging ear/shadow mass
        self.assertEqual(rows[4].count("e"), 2)                       # two eye holes
        self.assertEqual(rows[7].count("e"), 1)                       # black nose
        self.assertGreaterEqual(rows[8].count("p"), 1)                # pink tongue
        self.assertGreaterEqual(sum(r.count("c") for r in rows), 12)  # cream muzzle/chest
        self.assertGreaterEqual(sum(palette["h"]), 400)                # fur must not collapse near black
        self.assertGreaterEqual(sum(palette["b"]), 220)                # ears remain panel-visible
        g = geometry(sprite)
        self.assertEqual(g["edge_touches"], [])
        self.assertEqual(g["single_pixel_islands"], 0)
        self.assertGreaterEqual(g["bbox_width"], 12)
        self.assertGreaterEqual(g["bbox_height"], 12)

    def test_active_v2_animations_are_warning_free_and_keep_face_vocabulary(self):
        for name in ("look", "loaf", "sleep-wake", "pet", "dance", "kisses"):
            with self.subTest(name=name):
                animation = load_animation(ASSET_ROOT / "animations" / f"{name}.json")
                self.assertEqual(animation_quality(animation)["warnings"], [])
                for sprite in animation.unique_frames():
                    raw = json.loads(sprite.source_path.read_text(encoding="utf-8"))
                    rows = raw["rows"]
                    self.assertGreater(sum(r.count("h") for r in rows), 25)
                    self.assertGreater(sum(r.count("c") for r in rows), 4)


if __name__ == "__main__":
    unittest.main()
