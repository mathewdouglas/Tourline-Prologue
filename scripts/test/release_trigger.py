"""Check the private-input build boundary after repository migration."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'release'))
from ci_build import validate_trigger


class ReleaseTriggerTests(unittest.TestCase):
    def test_trusted_main_and_numeric_versions(self):
        for ref in ('refs/heads/main', 'refs/tags/v0.2', 'refs/tags/v1.2.3'):
            with self.subTest(ref=ref):
                validate_trigger('mathewdouglas/Tourline-Prologue', ref)

    def test_other_repositories_are_rejected(self):
        for repo in (None, '', 'mathewdouglas/GT5P', 'other/Tourline-Prologue'):
            with self.subTest(repo=repo), self.assertRaises(ValueError):
                validate_trigger(repo, 'refs/heads/main')

    def test_untrusted_refs_are_rejected(self):
        for ref in ('', 'refs/pull/1/merge', 'refs/heads/feature/test',
                    'refs/tags/v0.2-rc1', 'refs/tags/vlatest', 'refs/tags/v0.2\n'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                validate_trigger('mathewdouglas/Tourline-Prologue', ref)


if __name__ == '__main__':
    unittest.main()
