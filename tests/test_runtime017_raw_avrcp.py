import json
from pathlib import Path
import tempfile
import unittest

from host import product_runtime_v11 as r17

ROOT = Path(__file__).resolve().parents[1]


class Runtime017RawAvrcpTests(unittest.TestCase):
    def load(self, name):
        return json.loads((ROOT / 'product' / name).read_text(encoding='utf-8'))

    def test_runtime017_changes_only_input_surface_over_016(self):
        old = self.load('OPENDITOO-PRODUCT-RUNTIME-016.json')
        new = self.load('OPENDITOO-PRODUCT-RUNTIME-017.json')
        self.assertEqual(new['runtime_revision'], 12)
        for key in ('target', 'session', 'behavior', 'product_id', 'install', 'pages'):
            self.assertEqual(new[key], old[key], key)
        self.assertEqual(new['build']['host_dll_sha256'], old['build']['host_dll_sha256'])
        self.assertEqual(new['build']['button_probe_sha256'], old['build']['button_probe_sha256'])
        broker = new['pagination']['broker']
        self.assertEqual(broker['kind'], 'raw_avrcp_v1')
        self.assertEqual(broker['sink_status'], 'playing')
        self.assertEqual(broker['port'], 24353)
        self.assertEqual(broker['operations'], {
            '0x44': 'lever_candidate', '0x46': 'lever_candidate',
            '0x4B': 'nav_right', '0x4C': 'nav_left'})
        self.assertNotEqual(broker, old['pagination']['broker'])

    def test_template_is_unauthorized_and_source_hashes_match(self):
        raw = self.load('OPENDITOO-PRODUCT-RUNTIME-017.json')
        self.assertFalse(raw['authority']['persistent_runtime_authorized'])
        self.assertIsNone(raw['authority']['grant_text'])
        self.assertEqual(raw['authority']['required_grant_text'], 'Grant OPENDITOO-PRODUCT-RUNTIME-017')
        self.assertEqual(raw['authority']['supersedes'], 'OPENDITOO-PRODUCT-RUNTIME-016')
        self.assertEqual(raw['build']['code_sha256'], r17.code_hashes())
        self.assertIn('raw_avrcp_input_sha256', raw['build']['code_sha256'])
        self.assertIn('raw_avrcp_broker_program_sha256', raw['build']['code_sha256'])

    def test_cli_routes_revision_12_without_changing_revision_11(self):
        src = (ROOT / 'cli' / 'openditoo.py').read_text(encoding='utf-8')
        self.assertIn('if raw.get("runtime_revision") == 12:', src)
        self.assertIn('from host import product_runtime_v11', src)
        self.assertIn('if raw.get("runtime_revision") == 11:', src)
        self.assertIn('from host import product_runtime_v10', src)

    def test_runtime_uses_raw_cursor_and_raw_broker_not_legacy_smtc_cursor(self):
        src = (ROOT / 'host' / 'product_runtime_v11.py').read_text(encoding='utf-8')
        run = src[src.index('def run_product('):]
        self.assertIn('raw_avrcp_input.RawAvrcpBroker(', run)
        self.assertIn('raw_avrcp_input.RawAvrcpEvents(', run)
        self.assertNotIn('pagination.Broker(', run)
        self.assertNotIn('pagination.ButtonEvents(', run)

    def test_policy_rejects_input_contract_drift(self):
        raw = self.load('OPENDITOO-PRODUCT-RUNTIME-017.json')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'policy.json'
            raw['pagination']['broker']['sink_status'] = 'mirror'
            p.write_text(json.dumps(raw), encoding='utf-8')
            with self.assertRaises(Exception) as ctx:
                r17.load_policy(p, require_authority=False, verify_hashes=False, template_path=p)
            self.assertEqual(getattr(ctx.exception, 'code', None), 'PRODUCT_017_INPUT_CONTRACT_MISMATCH')

    def test_acceptance_harness_preserves_paths_with_spaces(self):
        src = (ROOT / 'scripts/accept_runtime_017_raw_input.ps1').read_text(encoding='utf-8')
        self.assertIn('function Quote-WindowsArg', src)
        self.assertIn('$psi.Arguments =', src)
        self.assertNotIn('ArgumentList.Add', src)
        self.assertNotIn('Start-Process -FilePath $exe -ArgumentList $args', src)
        self.assertIn('$psi.RedirectStandardError = $true', src)
        self.assertIn('BROKER_STDERR=', src)
        self.assertIn('R017_ACCEPT_PREEXISTING_HELPERS', src)

    def test_cutover_is_exact_grant_gated_hash_pinned_and_rolls_back_to_016(self):
        shell = (ROOT / 'scripts/cutover_runtime_017.sh').read_text(encoding='utf-8')
        stage = (ROOT / 'runtime/windows/stage_openditoo_raw_avrcp_broker.ps1').read_text(encoding='utf-8')
        self.assertIn('Grant OPENDITOO-PRODUCT-RUNTIME-017', shell)
        self.assertIn('OPENDITOO-PRODUCT-RUNTIME-016', shell)
        self.assertIn('rollback-runtime-016', shell)
        self.assertIn('stage_openditoo_raw_avrcp_broker.ps1', shell)
        self.assertIn('raw_avrcp_broker_sha256', shell)
        self.assertIn('raw_avrcp_dependencies_sha256', shell)
        self.assertIn("assert '__PENDING_' not in json.dumps(raw)", shell)
        self.assertIn("Step 'RAW_AVRCP_BROKER_SELFTEST' 'PASS'", stage)
        self.assertIn('Get-FileHash', stage)
        self.assertIn('OpenDitoo.RawAvrcpBroker.exe', stage)
        self.assertNotIn('--force', shell)
        self.assertNotIn('reset --hard', shell)

    def test_windows_sidecar_is_receive_only_exact_peer_and_health_bounded(self):
        src = (ROOT / 'runtime/windows/OpenDitoo.RawAvrcpBroker/Program.cs').read_text(encoding='utf-8')
        self.assertIn('bthci_acl.src.bd_addr == {options.Target}', src)
        self.assertIn('"--status", "playing"', src)
        for op in ('0x4C', '0x4B', '0x44', '0x46'):
            self.assertIn(op, src)
        self.assertIn('JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE', src)
        self.assertIn('pendingLine.Wait(250)', src)
        for forbidden in ('BluetoothClient', 'Rfcomm', 'Socket(', '/v1/session', '/v1/image'):
            self.assertNotIn(forbidden, src)


if __name__ == '__main__':
    unittest.main()
