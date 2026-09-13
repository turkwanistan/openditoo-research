import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ModelSentinel009Tests(unittest.TestCase):
    def test_one_byte_device_side_delta(self):
        old=(ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-PREMODEL-008-source.bin').read_bytes()
        new=(ROOT/'experiments/fixtures/OPENDITOO-VRAM8B-MODEL-SENTINEL-009-source.bin').read_bytes()
        self.assertEqual(len(old),0x410)
        self.assertEqual(len(new),0x411)
        self.assertEqual(new[:-1],old)
        self.assertEqual(new[-1],0xff)
        for suffix in ('01-prime.bin','02-voicetip.bin'):
            a=(ROOT/f'experiments/fixtures/OPENDITOO-VRAM8B-PREMODEL-008-{suffix}').read_bytes()
            b=(ROOT/f'experiments/fixtures/OPENDITOO-VRAM8B-MODEL-SENTINEL-009-{suffix}').read_bytes()
            self.assertEqual(a,b)
    def test_manifest_is_unauthorized_and_stops_before_callback(self):
        m=json.loads((ROOT/'experiments/OPENDITOO-VRAM8B-MODEL-SENTINEL-009.json').read_text())
        self.assertFalse(m['authority']['transmission_authorized'])
        self.assertFalse(m['authority']['authorization_consumed'])
        self.assertEqual(m['transport_budget']['custom_0x6c_declared_source_length'],0x411)
        self.assertTrue(m['safety_boundary']['predicted_model_byte_write'])
        self.assertFalse(m['safety_boundary']['predicted_callback_field_touched'])

if __name__=='__main__': unittest.main()
