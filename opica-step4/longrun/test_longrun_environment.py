from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import policy
import prepare_longrun


class LongrunProfileControls(unittest.TestCase):
    def test_frozen_profile_and_mathematical_contract(self):
        p = policy.profile()
        self.assertEqual(p["limits_seconds"]["guarded_kernel_import"], 14400)
        self.assertEqual(p["limits_seconds"]["canonical_compile"], 1800)
        self.assertEqual(p["proof_contract"]["selected_roots"], 50)
        self.assertFalse(p["proof_acceptance_from_profile"])

    def test_modified_limits_refused(self):
        p = policy.profile()
        modified = copy.deepcopy(p)
        modified["limits_seconds"]["guarded_kernel_import"] = 10000000
        with patch.object(policy, "read_json", return_value=modified):
            with self.assertRaises(policy.PolicyError):
                policy.profile()

    def test_axiom_relaxation_refused(self):
        p = policy.profile()
        modified = copy.deepcopy(p)
        modified["proof_contract"]["allowed_axioms"].append("myNewAxiom")
        with patch.object(policy, "read_json", return_value=modified):
            with self.assertRaises(policy.PolicyError):
                policy.profile()

    def test_duplicate_json_key_refused(self):
        with self.assertRaises(policy.PolicyError):
            policy._no_duplicates([("a", 1), ("a", 2)])

    def test_invalid_head_rejected_before_git(self):
        with self.assertRaises(policy.PolicyError):
            policy.source_identity("main")

    def test_unqualified_execution_rejected_without_work_creation(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "fresh"
            with self.assertRaises(policy.PolicyError):
                prepare_longrun.preflight(dest, "0"*40, "WRONG_PROFILE")
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
