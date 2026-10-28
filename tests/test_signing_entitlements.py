import importlib.util
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from config import load_app

spec = importlib.util.spec_from_file_location('signing_entitlements', ROOT / 'scripts/signing-entitlements.py')
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)


class SigningEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.config = load_app('openwhispr')
        self.team = 'TEAM123456'

    def signed(self, bundle):
        return {
            **signing.required_entitlements(self.config, bundle),
            'application-identifier': f'{self.team}.{bundle}',
            'com.apple.developer.team-identifier': self.team,
            'get-task-allow': False,
        }

    def test_all_targets_need_shared_group(self):
        for bundle in self.config['bundle_ids']:
            required = signing.required_entitlements(self.config, bundle)
            self.assertEqual(required['com.apple.security.application-groups'],
                             ['group.com.bearylabs.openwhispr'])
            self.assertEqual('com.apple.developer.applesignin' in required,
                             bundle == self.config['bundle_id'])

    def test_regression_identity_only_signature_is_rejected(self):
        for bundle in self.config['bundle_ids']:
            signed = self.signed(bundle)
            signed.pop('com.apple.security.application-groups')
            with self.assertRaisesRegex(ValueError, 'application-groups'):
                signing.validate_entitlements(signed, signing.required_entitlements(self.config, bundle), bundle, self.team)

    def test_wrong_group_team_or_development_signature_rejected(self):
        bundle = self.config['bundle_id']
        for key, value in [('com.apple.security.application-groups', ['group.com.gizmolabs.openwhispr']),
                           ('com.apple.developer.team-identifier', 'OTHERTEAM'),
                           ('get-task-allow', True),
                           ('application-identifier', f'{self.team}.wrong.app'),
                           ('com.apple.developer.applesignin', [])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                signing.validate_entitlements({**self.signed(bundle), key: value},
                                              signing.required_entitlements(self.config, bundle), bundle, self.team)

    def test_verify_checks_actual_executable_entitlements_for_every_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp) / 'app.ipa'
            signatures = []
            with zipfile.ZipFile(ipa, 'w') as archive:
                for index, bundle in enumerate(self.config['bundle_ids']):
                    directory = 'Payload/App.app' if index == 0 else f'Payload/App.app/PlugIns/Extension{index}.appex'
                    archive.writestr(f'{directory}/Info.plist', plistlib.dumps({
                        'CFBundleIdentifier': bundle, 'CFBundleExecutable': 'Executable'}))
                    archive.writestr(f'{directory}/Executable', b'binary')
                    signatures.append(plistlib.dumps(self.signed(bundle)))
            with patch.object(signing.subprocess, 'check_output', side_effect=signatures) as command:
                signing.verify(ipa, self.config, self.team)
                self.assertEqual(command.call_count, 3)
            signatures[0] = plistlib.dumps({'get-task-allow': False})
            with patch.object(signing.subprocess, 'check_output', side_effect=signatures):
                with self.assertRaises(ValueError):
                    signing.verify(ipa, self.config, self.team)

    def test_seed_signs_inside_out_with_only_reviewed_entitlements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / 'archive/Products/Applications/App.app'
            profiles = root / 'profiles'
            profiles.mkdir()
            for index, bundle in enumerate(self.config['bundle_ids']):
                target = main if index == 0 else main / f'PlugIns/Extension{index}.appex'
                target.mkdir(parents=True)
                (target / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': bundle}))
                # A permitted-but-unrequested entitlement must not be granted.
                (profiles / f'{index}.mobileprovision').write_bytes(plistlib.dumps({
                    'Entitlements': {**self.signed(bundle), 'unrequested-capability': True}}))
            framework = main / 'Frameworks/Example.framework'
            framework.mkdir(parents=True)
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                if '--entitlements' in command:
                    ent = plistlib.loads(Path(command[command.index('--entitlements') + 1]).read_bytes())
                    self.assertNotIn('unrequested-capability', ent)
                    self.assertIn('com.apple.security.application-groups', ent)
            with patch.object(signing.subprocess, 'check_output', side_effect=lambda command: Path(command[-1]).read_bytes()), \
                 patch.object(signing.subprocess, 'run', side_effect=run):
                signing.seed(root / 'archive', profiles, root / 'keychain', self.config, self.team)
            self.assertEqual(commands[-1][-1], str(main))
            self.assertEqual(len(commands), 4)
            self.assertTrue((main / 'embedded.mobileprovision').exists())


if __name__ == '__main__':
    unittest.main()
