import datetime
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from config import load_app
from archive import validate

spec = importlib.util.spec_from_file_location('export_options', ROOT / 'scripts/export-options.py')
export_options = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_options)


class ConfigTests(unittest.TestCase):
    def test_openwhispr_has_all_extensions(self):
        config = load_app('openwhispr')
        self.assertEqual(config['bundle_ids'], [
            'com.bearylabs.openwhispr',
            'com.bearylabs.openwhispr.keyboard',
            'com.bearylabs.openwhispr.activity',
        ])
        self.assertEqual(len(config['default_ref']), 40)
        self.assertEqual(config['display_name'], 'OpenWhispr')

    def test_reject_path_traversal(self):
        for app in ('../openwhispr', '/tmp/app', 'hello\nworld', 'app;echo nope'):
            with self.subTest(app=app), self.assertRaises(ValueError):
                load_app(app)

    def test_reject_ref_injection(self):
        for ref in ('--help', 'main\nsha=evil', '$(id)', '../main'):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/config.py'),
                                     'openwhispr', f'--ref={ref}'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_archive_must_include_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp, 'Products/Applications/Example.app')
            app.mkdir(parents=True)
            (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.example.app'}))
            validate(tmp, ['com.example.app'])
            with self.assertRaises(ValueError):
                validate(tmp, ['com.example.app', 'com.example.app.keyboard'])

    def test_expo_wrapper_removes_upstream_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp, 'app.config.js')
            config_file.write_text('module.exports = () => ({owner:"upstream", ios:{appleTeamId:"OLD"}, extra:{eas:{projectId:"old"}}, updates:{url:"https://old"}});')
            env_file = Path(tmp, 'env')
            env = dict(os.environ, APP_CONFIG=json.dumps(load_app('openwhispr')), GITHUB_ENV=str(env_file))
            subprocess.run(['node', str(ROOT / 'scripts/prepare-expo.cjs'), tmp], env=env, check=True)
            result = subprocess.check_output(['node', '-e', f'console.log(JSON.stringify(require({json.dumps(str(config_file))})()))'], env=dict(env, APPLE_TEAM_ID='NEW'), text=True)
            result = json.loads(result)
            self.assertNotIn('owner', result)
            self.assertNotIn('eas', result['extra'])
            self.assertEqual(result['ios']['appleTeamId'], 'NEW')
            self.assertEqual(result['updates'], {'enabled': False})
            self.assertEqual(result['ios']['infoPlist']['CFBundleDisplayName'], 'OpenWhispr')
            self.assertIn('OPENWHISPR_IOS_BUNDLE_IDENTIFIER=com.bearylabs.openwhispr', env_file.read_text())
            self.assertIn('OPENWHISPR_DISPLAY_NAME=OpenWhispr\n', env_file.read_text())
            self.assertIn('OPENWHISPR_KEYBOARD_DISPLAY_NAME=OpenWhispr\n', env_file.read_text())


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            'UUID': '12345678-1234-1234-1234-123456789abc',
            'TeamIdentifier': ['TEAM123456'],
            'ApplicationIdentifierPrefix': ['TEAM123456'],
            'ExpirationDate': datetime.datetime(2099, 1, 1),
            'ProvisionedDevices': ['test-device'],
            'Entitlements': {'application-identifier': 'TEAM123456.com.example.app'},
        }

    def test_valid_ad_hoc(self):
        self.assertEqual(export_options.validate_profile(self.profile, 'TEAM123456', 'ad-hoc'), 'com.example.app')

    def test_wrong_team(self):
        with self.assertRaises(ValueError):
            export_options.validate_profile(self.profile, 'OTHER12345', 'ad-hoc')

    def test_expired(self):
        self.profile['ExpirationDate'] = datetime.datetime(2000, 1, 1)
        with self.assertRaises(ValueError):
            export_options.validate_profile(self.profile, 'TEAM123456', 'ad-hoc')

    def test_testflight_rejects_device_profile(self):
        with self.assertRaises(ValueError):
            export_options.validate_profile(self.profile, 'TEAM123456', 'testflight')

    def test_ad_hoc_rejects_app_store_profile(self):
        del self.profile['ProvisionedDevices']
        with self.assertRaises(ValueError):
            export_options.validate_profile(self.profile, 'TEAM123456', 'ad-hoc')
        self.assertEqual(export_options.validate_profile(self.profile, 'TEAM123456', 'testflight'), 'com.example.app')

    def test_reject_development_profile(self):
        self.profile['Entitlements']['get-task-allow'] = True
        with self.assertRaises(ValueError):
            export_options.validate_profile(self.profile, 'TEAM123456', 'ad-hoc')


if __name__ == '__main__':
    unittest.main()
