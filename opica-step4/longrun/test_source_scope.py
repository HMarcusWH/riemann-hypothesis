from __future__ import annotations
import json
import unittest
from pathlib import Path
import policy


class SourceScopeControls(unittest.TestCase):
    def test_original_proof_bundle_unchanged_and_no_wider_diff(self):
        # This test needs a real git checkout with complete base history.
        actual_head = policy.git("rev-parse", "HEAD")
        data = policy.source_identity(actual_head, check_worktree=True)
        self.assertEqual(data["head"], actual_head)
        self.assertEqual(len(data["tree"]), 40)
        self.assertEqual(len(data["profile_sha256"]), 64)

    def test_manifest_lists_only_additions(self):
        manifest = policy.read_json(policy.HERE/"SOURCE_MANIFEST.json")
        self.assertEqual(manifest["schema"], "OPICA_LONGRUN_ADDITIVE_SOURCE_SCOPE_V1")
        self.assertEqual(manifest["original_parent"], policy.EXPECTED_BASE)
        files = manifest["files"]
        self.assertEqual(files, sorted(set(files)))
        self.assertIn("opica-step4/longrun/verify_modular_longrun.py", files)
        self.assertIn(".github/workflows/opica-longrun-verify.yml", files)
        self.assertNotIn("opica-step4/modular/verify_modular.py", files)
        self.assertFalse(manifest["proof_approval_from_scope"])


if __name__=="__main__":
    unittest.main()
