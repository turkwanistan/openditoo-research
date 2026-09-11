from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import unittest
from host.moss_page import ASSET_ROOT
from host.pixel_animation import animation_quality, load_animation
from host.pixel_art import geometry, load_sprite

V4_ROOT = Path("assets/pocket_moss/v4")


def generator():
    spec = importlib.util.spec_from_file_location("moss_v4_art", "tools/moss_v4_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MossV4ArtTests(unittest.TestCase):
    def test_default_root_is_v4(self):
        self.assertEqual(ASSET_ROOT.parts[-2:], ("pocket_moss", "v4"))

    def test_idle_keeps_face_identity_centred_with_collar(self):
        path = V4_ROOT / "sprites" / "idle.json"
        raw = json.loads(path.read_text()); rows, pal = raw["rows"], raw["palette"]
        sprite = load_sprite(path)
        self.assertEqual(sprite.id, "moss.v4.idle")
        self.assertEqual([x for x, k in enumerate(rows[4]) if k == "e"], [5, 10])  # eyes, symmetric about 7.5
        self.assertEqual([x for x, k in enumerate(rows[7]) if k == "e"], [7, 8])   # nose on the centre line
        self.assertEqual([x for x, k in enumerate(rows[8]) if k == "p"], [7, 8])   # tongue on the centre line
        self.assertGreaterEqual(sum(r.count("b") for r in rows), 20)  # floppy ears
        self.assertGreaterEqual(sum(r.count("c") for r in rows), 14)  # muzzle + chest + paws
        self.assertIn("k", rows[9]); self.assertIn("l", "".join(rows))
        # No near-black fur (v1 brown-blob lesson): every fur/ear tone stays bright.
        for key in ("b", "s", "h", "l"):
            self.assertGreater(sum(pal[key]), 250, key)
        g = geometry(sprite)
        self.assertEqual(g["edge_touches"], []); self.assertEqual(g["single_pixel_islands"], 0)
        self.assertGreaterEqual(g["bbox_width"], 12); self.assertGreaterEqual(g["bbox_height"], 12)

    def test_active_animations_are_warning_free_and_keep_face_vocabulary(self):
        minimum_unique = {"dance": 8, "pet": 6, "kisses": 6, "look": 4, "loaf": 3, "sleep-wake": 5}
        for name, min_unique in minimum_unique.items():
            with self.subTest(name=name):
                a = load_animation(V4_ROOT / "animations" / f"{name}.json"); q = animation_quality(a)
                self.assertEqual(q["warnings"], []); self.assertGreaterEqual(q["unique_frame_count"], min_unique)
                for sprite in a.unique_frames():
                    rows = json.loads(sprite.source_path.read_text())["rows"]
                    self.assertGreater(sum(r.count("h") for r in rows), 20)
                    self.assertGreater(sum(r.count("c") for r in rows), 3)
                    self.assertGreater(sum(r.count("b") for r in rows), 10)

    def test_dance_phases_are_preserved(self):
        phases = [s.phase for s in load_animation(V4_ROOT / "animations" / "dance.json").steps]
        for phase in ("anticipate", "step_left", "step_right", "hop", "land", "wag_high", "wag_low", "settle"):
            self.assertIn(phase, phases)

    def test_committed_assets_are_exactly_the_generator_output(self):
        gen = generator()
        for name, rows in gen.SPRITES.items():
            self.assertEqual(json.loads((V4_ROOT / "sprites" / f"{name}.json").read_text())["rows"], rows, name)
        for name, seq in gen.ANIMS.items():
            doc = json.loads((V4_ROOT / "animations" / f"{name}.json").read_text())
            self.assertEqual([(Path(s["sprite"]).stem, s["hold_acks"], s["phase"]) for s in doc["sequence"]],
                             [tuple(s) for s in seq], name)
        self.assertEqual(len(list((V4_ROOT / "sprites").glob("*.json"))), len(gen.SPRITES))


if __name__ == "__main__":
    unittest.main()
