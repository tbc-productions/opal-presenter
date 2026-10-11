"""Exercise release requests without contacting Gitea."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Release steps run on Linux')
class OpalReleaseWorkflowTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.calls = self.directory / 'calls.jsonl'
        self.workflow = (Path(__file__).resolve().parents[2] / '.gitea/workflows/release.yml').read_text()
        curl = self.directory / 'curl'
        curl.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['OPAL_CALLS']).open('a') as calls:
    calls.write(json.dumps(args) + '\\n')
if '-w' in args:
    Path(args[args.index('-o') + 1]).write_text('{}')
    print(os.environ['OPAL_POST_STATUS'], end='')
else:
    sys.exit(int(os.environ['OPAL_CURL_EXIT']))
''')
        curl.chmod(0o755)
        self.environment = {**os.environ, 'PATH': str(self.directory) + os.pathsep + os.environ['PATH'],
                            'OPAL_CALLS': str(self.calls), 'OPAL_POST_STATUS': '201', 'OPAL_CURL_EXIT': '0',
                            'OPAL_TAG': 'v4.0.3', 'OPAL_BUILD_FLATPAK': 'false', 'CI_TOKEN': 'test',
                            'GITHUB_REF_NAME': 'master', 'GITHUB_SERVER_URL': 'https://example.invalid',
                            'GITHUB_REPOSITORY': 'test/opal'}

    def run_step(self, name):
        step = self.workflow.split(f'      - name: {name}', 1)[1].split('      - name:', 1)[0]
        script = step.split('        run: |', 1)[1]
        script = '\n'.join(line[10:] for line in script.splitlines() if line.startswith('          '))
        script = script.replace('/tmp/release_response.json', str(self.directory / 'response.json'))
        return subprocess.run(['bash', '-c', script], env=self.environment, capture_output=True, text=True)

    def test_create_release_uses_requested_tag(self):
        result = self.run_step('Create Gitea release')
        self.assertEqual(result.returncode, 0, result.stderr)
        request = json.loads(self.calls.read_text().splitlines()[0])
        self.assertEqual(json.loads(request[request.index('-d') + 1])['tag_name'], 'v4.0.3')

    def test_conflict_requires_existing_release(self):
        self.environment['OPAL_POST_STATUS'] = '409'
        for exit_code in ('0', '22'):
            with self.subTest(exit_code=exit_code):
                self.environment['OPAL_CURL_EXIT'] = exit_code
                result = self.run_step('Create Gitea release')
                self.assertEqual(result.returncode == 0, exit_code == '0', result.stderr)
                request = json.loads(self.calls.read_text().splitlines()[-1])
                self.assertTrue(request[-1].endswith('/releases/tags/v4.0.3'))

    def test_release_channel_matches_tag(self):
        for tag, prerelease in [('4.0.4a2', True), ('4.0.4b1', True), ('4.0.4rc1', True), ('4.0.4', False)]:
            with self.subTest(tag=tag):
                self.environment['OPAL_TAG'] = tag
                result = self.run_step('Create Gitea release')
                self.assertEqual(result.returncode, 0, result.stderr)
                request = json.loads(self.calls.read_text().splitlines()[-1])
                self.assertEqual(json.loads(request[request.index('-d') + 1])['prerelease'], prerelease)

    def test_release_error_stops_workflow(self):
        self.environment['OPAL_POST_STATUS'] = '403'
        self.assertNotEqual(self.run_step('Create Gitea release').returncode, 0)

    def test_dispatch_preserves_tag_and_flatpak_choice(self):
        for flatpak in ('false', 'true'):
            with self.subTest(flatpak=flatpak):
                self.environment['OPAL_BUILD_FLATPAK'] = flatpak
                result = self.run_step('Trigger opal-presenter-packaging build')
                self.assertEqual(result.returncode, 0, result.stderr)
                request = json.loads(self.calls.read_text().splitlines()[-1])
                payload = json.loads(request[request.index('-d') + 1])
                self.assertEqual(payload['inputs']['opal_tag'], 'v4.0.3')
                self.assertEqual(payload['inputs']['build_flatpak'], flatpak)
                self.assertTrue(request[-1].endswith(
                    '/opal-presenter-packaging/actions/workflows/build.yml/dispatches'))
                self.assertIn('--fail-with-body', request)

    def test_dispatch_failure_stops_workflow(self):
        self.environment['OPAL_CURL_EXIT'] = '22'
        self.assertNotEqual(self.run_step('Trigger opal-presenter-packaging build').returncode, 0)


if __name__ == '__main__':
    unittest.main()
