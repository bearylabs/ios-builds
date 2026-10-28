import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('age') and shutil.which('age-keygen'), 'age tools required')
class EncryptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root / 'private.agekey'
        subprocess.run(['age-keygen', '-o', str(self.key)], check=True, capture_output=True)
        self.recipient = subprocess.check_output(['age-keygen', '-y', str(self.key)], text=True).strip()
        self.env = dict(os.environ, RUNNER_TEMP=str(self.root), ARTIFACT_AGE_RECIPIENT=self.recipient)

    def run_script(self, script, *args, **extra):
        return subprocess.run(['bash', str(ROOT / 'scripts' / script), *map(str, args)],
                              env=dict(self.env, **extra), capture_output=True)

    def test_ipa_publication_is_encrypted(self):
        source = self.root / 'deliverables'
        source.mkdir()
        plaintext = b'private IPA including device profiles'
        (source / 'App.ipa').write_bytes(plaintext)
        (source / 'build.json').write_text(json.dumps({'source_sha': 'public metadata'}))
        result = self.run_script('encrypt-ipa.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        public = self.root / 'encrypted-deliverables'
        self.assertEqual({p.name for p in public.iterdir()}, {'App.ipa.age', 'build.json'})
        ciphertext = public / 'App.ipa.age'
        self.assertNotIn(plaintext, ciphertext.read_bytes())
        output = subprocess.check_output(['age', '-d', '-i', str(self.key), str(ciphertext)])
        self.assertEqual(output, plaintext)

    def test_decryption_removes_temporary_identity(self):
        plaintext = self.root / 'archive.zip'
        plaintext.write_bytes(b'synthetic archive')
        ciphertext = self.root / 'archive.zip.age'
        subprocess.run(['age', '-r', self.recipient, '-o', str(ciphertext), str(plaintext)], check=True)
        output = self.root / 'decrypted.zip'
        result = self.run_script('decrypt-artifact.sh', ciphertext, output,
                                 ARTIFACT_AGE_IDENTITY=self.key.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), plaintext.read_bytes())
        self.assertEqual(list(self.root.glob('artifact-identity.*')), [])

    def test_failed_decryption_removes_temporary_identity(self):
        ciphertext = self.root / 'invalid.age'
        ciphertext.write_bytes(b'not encrypted data')
        result = self.run_script('decrypt-artifact.sh', ciphertext, self.root / 'output',
                                 ARTIFACT_AGE_IDENTITY=self.key.read_text())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.root.glob('artifact-identity.*')), [])
        self.assertNotIn(b'AGE-SECRET-KEY-', result.stdout + result.stderr)

    def test_signing_diagnostics_are_encrypted(self):
        log = self.root / 'signing.log'
        log.write_text('private profile diagnostic')
        result = self.run_script('encrypt-signing-logs.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'signing-diagnostics.zip.age').exists())
        self.assertFalse((self.root / 'signing-diagnostics.zip').exists())


class PublicWorkflowTests(unittest.TestCase):
    def test_no_private_source_token_or_plaintext_artifact_paths(self):
        workflow = (ROOT / '.github/workflows/build-ios.yml').read_text()
        self.assertNotIn('SOURCE_READ_TOKEN', workflow)
        self.assertIn("repository['visibility'] != 'public'", workflow)
        self.assertNotIn('path: ${{ runner.temp }}/deliverables/', workflow)
        self.assertNotIn('${{ runner.temp }}/output/archive.zip\n', workflow)
        self.assertNotIn('path: ${{ runner.temp }}/output/xcodebuild.log', workflow)
        self.assertIn('archive.zip.age', workflow)
        self.assertIn('environment: ios-', workflow)


if __name__ == '__main__':
    unittest.main()
