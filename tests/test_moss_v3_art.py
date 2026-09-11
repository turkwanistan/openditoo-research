from __future__ import annotations
import json
from pathlib import Path
import unittest
from host.moss_page import ASSET_ROOT
from host.pixel_animation import animation_quality, load_animation
from host.pixel_art import geometry, load_sprite

class MossV3ArtTests(unittest.TestCase):
    def test_default_root_is_v3_and_idle_keeps_dog_cues_with_depth_plane(self):
        self.assertEqual(ASSET_ROOT.parts[-2:], ("pocket_moss", "v3"))
        path=ASSET_ROOT/'sprites'/'idle.json'; raw=json.loads(path.read_text()); sprite=load_sprite(path)
        rows,pal=raw['rows'],raw['palette']
        self.assertEqual(sprite.id,'moss.v3.idle')
        self.assertGreaterEqual(sum(r.count('b') for r in rows), 12)
        self.assertGreaterEqual(sum(r.count('s') for r in rows), 10)
        self.assertEqual(rows[4].count('e'),2)
        self.assertEqual(rows[7].count('e'),1)
        self.assertGreaterEqual(sum(r.count('c') for r in rows),10)
        self.assertGreaterEqual(sum(r.count('p') for r in rows),1)
        self.assertGreater(sum(pal['h']),400); self.assertGreater(sum(pal['s']),250)
        g=geometry(sprite)
        self.assertEqual(g['edge_touches'],[]); self.assertEqual(g['single_pixel_islands'],0)
        self.assertGreaterEqual(g['bbox_width'],12); self.assertGreaterEqual(g['bbox_height'],12)

    def test_active_v3_animations_are_warning_free_and_materially_richer(self):
        minimum_unique={'dance':8,'pet':6,'kisses':5,'look':2,'loaf':2,'sleep-wake':4}
        for name,min_unique in minimum_unique.items():
            with self.subTest(name=name):
                a=load_animation(ASSET_ROOT/'animations'/f'{name}.json'); q=animation_quality(a)
                self.assertEqual(q['warnings'],[]); self.assertGreaterEqual(q['unique_frame_count'],min_unique)
                for sprite in a.unique_frames():
                    raw=json.loads(sprite.source_path.read_text()); rows=raw['rows']
                    self.assertGreater(sum(r.count('h') for r in rows),20)
                    self.assertGreater(sum(r.count('c') for r in rows),3)

    def test_dance_contains_anticipation_hop_landing_and_wag_phases(self):
        a=load_animation(ASSET_ROOT/'animations'/'dance.json')
        phases=[s.phase for s in a.steps]
        for phase in ('anticipate','step_left','step_right','hop','land','wag_high','wag_low','settle'):
            self.assertIn(phase,phases)

if __name__=='__main__': unittest.main()
