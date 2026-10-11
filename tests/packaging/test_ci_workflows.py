"""Keep development checks manual and release checks mandatory."""
import unittest
from pathlib import Path


class OpalCiWorkflowTest(unittest.TestCase):
    def test_checks_run_manually_or_on_master(self):
        workflow = (Path(__file__).resolve().parents[2] / '.gitea/workflows/test.yml').read_text(encoding='utf-8')
        triggers = workflow.split('\njobs:\n', 1)[0]
        self.assertIn('  push:\n    branches: [master]\n', triggers)
        self.assertNotIn('  pull_request:', triggers)
        self.assertIn('  workflow_dispatch:\n', triggers)
        self.assertIn('  workflow_call:\n    inputs:\n      opal_ref:\n', triggers)
        self.assertEqual(workflow.count('          ref: ${{ inputs.opal_ref || github.ref }}\n'), 2)

    def test_release_waits_for_checks_on_the_requested_tag(self):
        workflow = (Path(__file__).resolve().parents[2] / '.gitea/workflows/release.yml').read_text(encoding='utf-8')
        checks, release = workflow.split('\n  release:\n', 1)
        self.assertIn('  windows-qt-packaging:\n    runs-on: windows\n', checks)
        self.assertIn('  pytest:\n    runs-on: macos\n', checks)
        self.assertNotIn('    uses: ./.gitea/workflows/test.yml\n', checks)
        self.assertEqual(checks.count('          ref: ${{ github.event.inputs.opal_tag || github.ref }}\n'), 2)
        self.assertIn('    needs: [windows-qt-packaging, pytest]\n', release)
        self.assertNotIn('    if:', release)


if __name__ == '__main__':
    unittest.main()
