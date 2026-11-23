import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import reconcile as x

class CanonicalV3Policy(unittest.TestCase):
    def test_exact_native_and_prior_source(self):
        self.assertEqual(x.NATIVE_COMMIT,"bb7c8184a135b2823c6296917c5ac893bebf2a71")
        self.assertEqual(x.V2_COMMIT,"200777fa9afa8c00a193c0070866d58791f54fdc")
        self.assertEqual(len(x.PROTECTED),3)
    def test_incorrect_v2_digest_fails(self):
        with tempfile.NamedTemporaryFile(suffix=".zip") as f:
            with self.assertRaises((x.ReviewError,Exception)):
                x.read_v2(Path(f.name))
    def test_unreviewed_path_authority_rejected(self):
        self.assertNotIn(x.EXTRA_INDEX,x.PROTECTED)
        self.assertTrue(x.EXTRA_INDEX.startswith("research/RHRC/graph/compiler/"))
    def test_no_rh_promotion_in_runner(self):
        body=(Path(__file__).resolve().parent/"reconcile.py").read_text()
        self.assertIn('proof_acceptance":False',body)
        self.assertIn('successor_human_review"]="PENDING"',body)
        self.assertIn('status"]="V3_CURRENT_NATIVE_CANDIDATE_PREPARED_FOR_REVIEW"',body)
        self.assertNotIn("RH_PROVED",body)
if __name__=="__main__": unittest.main()
