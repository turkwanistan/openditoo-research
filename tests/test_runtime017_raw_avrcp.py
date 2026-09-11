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

    def test_acceptance_harness_uses_task_from_unelevated_caller(self):
        src = (ROOT / 'scripts/accept_runtime_017_raw_input.ps1').read_text(encoding='utf-8')
        self.assertIn("Need (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))", src)
        self.assertIn('python3 -m host.raw_avrcp_input verify-task', src)
        self.assertIn('& schtasks.exe /run /tn $task', src)
        self.assertNotIn('Process]::Start', src)  # never launches the broker directly
        self.assertIn('R017_ACCEPT_PREEXISTING_HELPERS', src)
        for auto in ('$pid ', '$input ', '$args '):
            self.assertNotIn(auto, src)
        # Lease expiry is proven before the orphan scan and gates PASS.
        self.assertLess(src.index('Stop-Job $leaseJob; $leaseStopped = $true'), src.index("'lease_expired'"))
        self.assertLess(src.index('R017_ACCEPT_LEASE_EXPIRY_EXIT'), src.index('$pass ='))
        self.assertIn('$expired -and $orphans.Count -eq 0', src)

    def test_acceptance_learns_handle_before_cues_and_requires_negative_control(self):
        src = (ROOT / 'scripts/accept_runtime_017_raw_input.ps1').read_text(encoding='utf-8')
        start = src.index("systemctl --user start openditoo-product.service")
        stop = src.index("systemctl --user stop openditoo-product.service")
        self.assertLess(src.index('R017_ACCEPT_BROKER_READY'), start)
        self.assertLess(start, src.index('"type":"handle_bound"'))
        self.assertLess(stop, src.index('R017_ACCEPT_HANDLE_BOUND'))
        self.assertLess(src.index('R017_ACCEPT_HANDLE_BOUND'), src.index('DITOO LEFT'))
        self.assertLess(src.index('R017_ACCEPT_SINK_AFTER_BIND'), src.index('Now start media playing'))
        self.assertLess(src.index('Now start media playing'), src.index('DITOO LEFT'))
        self.assertIn('$foreign -ge 1 -and $unbound -eq 0', src)
        self.assertIn('$latMax -ge 0 -and $latMax -le 500', src)

    def test_installer_is_elevated_hash_verified_admin_only_and_on_demand(self):
        src = (ROOT / 'runtime/windows/install_openditoo_raw_avrcp_task.ps1').read_text(encoding='utf-8')
        self.assertIn("Need ($principalNow.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))", src)
        self.assertLess(src.index('R017_TASK_SOURCES_VERIFIED'), src.index('Copy-Item'))  # verify before writing
        self.assertIn('installed hash mismatch', src)
        self.assertLess(src.index('R017_TASK_INSTALL_ROOT_ADMIN_ONLY'), src.index('Register-ScheduledTask'))
        self.assertIn("$root = 'C:\\Program Files\\OpenDitoo\\RawAvrcpBroker'", src)
        for needle in ('-RunLevel Highest', '-LogonType Interactive', '-MultipleInstances IgnoreNew',
                       'Must match host/raw_avrcp_input.task_arguments exactly'):
            self.assertIn(needle, src)
        self.assertNotIn('New-ScheduledTaskTrigger', src)

    def test_policy_elevated_launch_is_admin_only(self):
        raw = self.load('OPENDITOO-PRODUCT-RUNTIME-017.json')
        broker = raw['pagination']['broker']
        root = r17.RAW_AVRCP_INSTALL_ROOT + '\\'
        for key in ('exe', 'sink_exe', 'btvs_exe'):
            self.assertTrue(broker[key].startswith(root), key)
        self.assertTrue(all(k.startswith(root) for k in raw['build']['raw_avrcp_broker_sha256']))
        for path, digest in raw['build']['button_probe_sha256'].items():  # sink copies = exact 016 ButtonProbe
            self.assertEqual(raw['build']['raw_avrcp_broker_sha256'][root + 'sink\\' + path.rsplit('\\', 1)[1]], digest)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'policy.json'
            raw['pagination']['broker']['btvs_exe'] = 'C:\\BTP\\v1.14.0\\x86\\btvs.exe'
            p.write_text(json.dumps(raw), encoding='utf-8')
            with self.assertRaises(Exception) as ctx:
                r17.load_policy(p, require_authority=False, verify_hashes=False, template_path=p)
            self.assertEqual(getattr(ctx.exception, 'code', None), 'PRODUCT_017_ELEVATED_LAUNCH_MISMATCH')

    def test_cutover_is_exact_grant_gated_hash_pinned_and_rolls_back_to_016(self):
        shell = (ROOT / 'scripts/cutover_runtime_017.sh').read_text(encoding='utf-8')
        stage = (ROOT / 'runtime/windows/stage_openditoo_raw_avrcp_broker.ps1').read_text(encoding='utf-8')
        self.assertIn('Grant OPENDITOO-PRODUCT-RUNTIME-017', shell)
        self.assertIn('OPENDITOO-PRODUCT-RUNTIME-016', shell)
        self.assertIn('rollback-runtime-016', shell)
        self.assertNotIn('stage_openditoo_raw_avrcp_broker.ps1', shell)  # cutover never writes elevated files
        self.assertIn('R017_ELEVATED_SIDECAR_NOT_INSTALLED', shell)
        self.assertIn('python3 -m host.raw_avrcp_input verify-task', shell)
        self.assertIn('end_raw_task', shell[shell.index('--rollback'):])
        self.assertIn('raw_avrcp_broker_sha256', shell)
        self.assertIn('raw_avrcp_dependencies_sha256', shell)
        self.assertIn("assert '__PENDING_' not in json.dumps(raw)", shell)
        self.assertIn("Step 'RAW_AVRCP_BROKER_SELFTEST' 'PASS'", stage)
        self.assertIn('Get-FileHash', stage)
        self.assertIn('OpenDitoo.RawAvrcpBroker.exe', stage)
        self.assertNotIn('--force', shell)
        self.assertNotIn('reset --hard', shell)


    def test_raw_acl_attribution_diagnostic_uses_low_level_acl_bytes(self):
        src = (ROOT / 'scripts/diagnose_runtime_017_raw_acl_attribution.ps1').read_text(encoding='utf-8')
        self.assertIn("'-Y','bthci_acl'", src)
        self.assertIn("'-e','bthci_acl.chandle'", src)
        self.assertIn("'-e','bthci_acl.pb_flag'", src)
        self.assertIn("'-e','btl2cap.payload'", src)
        self.assertIn("'-e','data.data'", src)
        self.assertIn("'separator=/t'", src)  # tshark's tab escape; '\\t' prints a literal backslash
        self.assertNotIn('separator=\\', src)
        self.assertIn("'--disable-protocol','btrfcomm','--disable-protocol','btavctp'", src)
        self.assertIn("0103009fa20002", src)
        self.assertIn("010400bd31f20002", src)
        self.assertIn("systemctl --user start openditoo-product.service", src)
        self.assertIn("systemctl --user stop openditoo-product.service", src)

    def test_attribution_diagnostic_is_receive_only_and_outputs_handle_and_both_addresses(self):
        src = (ROOT / 'scripts/diagnose_runtime_017_attribution.ps1').read_text(encoding='utf-8')
        self.assertIn("'bthci_acl.chandle'", src)
        self.assertIn("'bthci_acl.src.bd_addr'", src)
        self.assertIn("'bthci_acl.dst.bd_addr'", src)
        self.assertIn("btl2cap.payload contains 11:0e:00:48:7c:44:00", src)
        self.assertNotIn('product-runtime', src)
        self.assertNotIn('/v1/session', src)

    def test_windows_sidecar_is_receive_only_exact_peer_and_health_bounded(self):
        src = (ROOT / 'runtime/windows/OpenDitoo.RawAvrcpBroker/Program.cs').read_text(encoding='utf-8')
        self.assertNotIn('bd_addr', src)  # mid-connection BTVS has zeroed addresses
        self.assertIn('class HandleBinder', src)
        self.assertIn('"--disable-protocol", "btrfcomm", "--disable-protocol", "btavctp"', src)
        self.assertIn('"separator=/t"', src)
        self.assertIn('bthci_evt.code == 0x05', src)
        self.assertIn('bthci_acl.pb_flag == 0 && (btl2cap.payload contains 01:03:00:9f:a2:00:02', src)
        self.assertIn('bthci_acl.pb_flag == 2 && btl2cap.payload contains 11:0e:00:48:7c', src)
        self.assertNotIn('0x0100', src[:src.index('internal static class Selftest')])  # no hard-coded handle
        run = src[src.index('internal int Run()'):]
        # ETW backlog replay is dropped, the ownership sink waits for the first bind, and ETW is flush-only.
        self.assertIn('captured < startEpoch', run)
        self.assertLess(run.index('seen.Change == "handle_bound" && sink is null'), run.index('"--status", "playing"'))
        self.assertIn('return ControlTraceW(0, session, buffer, 3);', src)
        self.assertEqual(src.count('ControlTraceW('), 2)  # declaration + the single FLUSH call
        self.assertNotIn('StartTrace', src)
        self.assertIn('Need(etw == 4201', src)
        self.assertIn('"--status", "playing"', src)
        for op in ('0x4C', '0x4B', '0x44', '0x46'):
            self.assertIn(op, src)
        self.assertIn('JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE', src)
        self.assertIn('pendingLine.Wait(250)', src)
        for forbidden in ('BluetoothClient', 'Rfcomm', 'Socket(', '/v1/session', '/v1/image'):
            self.assertNotIn(forbidden, src)


if __name__ == '__main__':
    unittest.main()
