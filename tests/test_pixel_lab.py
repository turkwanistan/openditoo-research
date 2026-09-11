from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from host.pixel_art import PixelArtError, changed_pixels, geometry, load_sprite, png_bytes
from host.pixel_animation import AckAnimationPlayer, animation_quality, cadence_intervals, load_animation

ROOT = Path(__file__).resolve().parents[1]
PALETTE = {".": [0, 0, 0], "b": [130, 80, 45], "c": [240, 215, 170], "e": [12, 8, 6]}
ROWS_A = ["................"] * 8 + [
    ".....bb.........", "....bccbb.......", "...bbceebbb.....", "...bbbbbbbb.....",
    "....bb..bb......", "....b....b......", "................", "................",
]
ROWS_B = ROWS_A.copy(); ROWS_B[8] = "......bb........"; ROWS_B[9] = "....bccbbb......"


class PixelLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.a = self.dir / "a.json"; self.b = self.dir / "b.json"; self.anim = self.dir / "anim.json"
        for path, sprite_id, rows in ((self.a, "dog.a", ROWS_A), (self.b, "dog.b", ROWS_B)):
            path.write_text(json.dumps({"schema": "openditoo.pixel-sprite.v1", "id": sprite_id,
                "width": 16, "height": 16, "palette": PALETTE, "rows": rows,
                "meta": {"anchor": [8, 13], "mirroring": "horizontal", "tags": ["test"]}}))
        self.anim.write_text(json.dumps({"schema": "openditoo.pixel-animation.v1", "id": "dog.look",
            "canvas": [16, 16], "loop": True, "sequence": [
                {"sprite": "a.json", "hold_acks": 3, "phase": "idle"},
                {"sprite": "b.json", "hold_acks": 2, "phase": "look"},
                {"sprite": "a.json", "hold_acks": 4, "phase": "settle"}]}))

    def tearDown(self): self.tmp.cleanup()

    def test_sprite_compiles_exact_rgb888_and_encoder_compatible(self):
        sprite = load_sprite(self.a)
        self.assertEqual(len(sprite.rgb888), 768)
        self.assertEqual(sprite, load_sprite(self.a))
        self.assertEqual(geometry(sprite)["anchor"], [8, 13])
        self.assertEqual(len(sprite.rgb_sha256), 64)

    def test_mirror_is_involution_and_moves_anchor(self):
        sprite = load_sprite(self.a)
        mirrored = sprite.mirrored()
        self.assertEqual(mirrored.anchor, (7, 13))
        self.assertEqual(mirrored.mirrored().rows, sprite.rows)
        self.assertEqual(mirrored.mirrored().rgb888, sprite.rgb888)

    def test_bad_geometry_rejected(self):
        raw = json.loads(self.a.read_text()); raw["rows"][0] = "short"
        self.a.write_text(json.dumps(raw))
        with self.assertRaises(PixelArtError): load_sprite(self.a)

    def test_png_writer_is_deterministic(self):
        sprite = load_sprite(self.a)
        first = png_bytes(sprite.rgb888, 16, 16, scale=8)
        self.assertEqual(first, png_bytes(sprite.rgb888, 16, 16, scale=8))
        self.assertTrue(first.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_animation_holds_advance_only_on_ack(self):
        animation = load_animation(self.anim); player = AckAnimationPlayer(animation)
        seen = []
        for _ in range(9):
            seen.append(player.step.phase); player.ack()
        self.assertEqual(seen, ["idle"] * 3 + ["look"] * 2 + ["settle"] * 4)
        self.assertEqual(player.loop_count, 1)

    def test_jitter_profile_is_seeded_and_contains_stall(self):
        a = cadence_intervals("jitter", 40, seed=22); b = cadence_intervals("jitter", 40, seed=22)
        self.assertEqual(a, b); self.assertGreater(max(a), 150)
        self.assertEqual(cadence_intervals("fps10", 3), [100.0, 100.0, 100.0])

    def test_quality_reports_frame_deltas_and_loop_seam(self):
        report = animation_quality(load_animation(self.anim))
        self.assertEqual(report["total_hold_acks"], 9)
        self.assertEqual(len(report["adjacent_changed_pixels"]), 2)
        self.assertEqual(report["loop_seam_changed_pixels"], 0)
        self.assertGreater(len(changed_pixels(load_sprite(self.a), load_sprite(self.b))), 0)

    def test_review_bundle_contains_exact_machine_readable_frames(self):
        out_root = self.dir / "reviews"
        result = subprocess.run(["python3", str(ROOT / "tools/pixel_lab.py"), "review-bundle", str(self.anim),
                                 "--output-root", str(out_root), "--profile", "jitter", "--seed", "7"],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        out = Path(result.stdout.strip())
        for name in ("manifest.json", "frames.json", "quality.json", "contact-sheet.png", "preview.html", "README.txt"):
            self.assertTrue((out / name).exists(), name)
        frames = json.loads((out / "frames.json").read_text())
        self.assertEqual(frames["sequence"][0]["hold_acks"], 3)
        self.assertEqual(len(frames["frames"][0]["rows"]), 16)
        self.assertEqual(len(frames["frames"][0]["rows"][0]), 16)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["cadence_profile"], "jitter")
        self.assertEqual(len(manifest["cadence_intervals_ms"]), 9)


if __name__ == "__main__": unittest.main()
