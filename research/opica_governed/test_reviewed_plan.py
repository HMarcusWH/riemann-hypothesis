"""Fail-closed controls for native OPICA cross-repository target selection."""
from pathlib import Path
import json
import unittest

PLAN = json.loads((Path(__file__).resolve().parent / "PLAN.json").read_text())

class ReviewedTargetControls(unittest.TestCase):
    def test_native_rh_not_an_admissible_arithmetic_constant(self):
        rows = PLAN["target_c1"]["allowed_lemmas"]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertNotIn("riemannHypothesis", row["declaration"])
            self.assertTrue(row["module"].endswith("CofinalMomentClosure"))
        self.assertFalse(PLAN["target_c1"]["no_direct_rh_certificate"] is False)

    def test_source_fingerprints_and_no_cross_version_mixing(self):
        self.assertEqual(PLAN["native_commit"],
                         "bb7c8184a135b2823c6296917c5ac893bebf2a71")
        self.assertEqual(PLAN["supplier_commit"],
                         "1b894f7511841e6607bc0398cf2657526bbb29d9")
        self.assertEqual(PLAN["supplier_source_tree"],
                         "69b331ce0e429c7632dac6aa642e5875a50b1218")
        self.assertEqual(PLAN["native_tree"],
                         "2b19357e1b65cc500f3e3a5b5d4df14601b02062")
        self.assertEqual(PLAN["supplier_lean"], "leanprover/lean4:v4.36.0")
        self.assertEqual(PLAN["supplier_compatibility"], "NOT_VERIFIED_WRAPPED_LEAN4_36") if "supplier_compatibility" in PLAN else None

    def test_registered_native_retrieval_targets_not_calibrations(self):
        self.assertEqual(PLAN["frozen_native_typed_targets"],
                         ["INTEGRATION_CLOSURE","INTEGRATION_SOURCE","INTEGRATION_INDEX"])
        self.assertEqual(PLAN["proof_gates"],
                         ["SOURCE","KERNEL","AXIOMS","INDEPENDENT_EXPECTED_TYPE"])
        self.assertEqual(PLAN["output_authority"]["rh"], "OPEN")
        self.assertEqual(PLAN["target_c1"]["declaration"],
                         "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds")

    def test_forbidden_circular_source_is_explicit(self):
        forbidden = PLAN["target_c1"]["forbidden_lemmas"]
        self.assertIn("Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis", forbidden)
        self.assertIn("_root_.riemannHypothesis", forbidden)
        self.assertTrue(PLAN["target_c1"]["no_raw_rh_axiom"])
        self.assertFalse(PLAN["output_authority"].get("proof_acceptance", False))

if __name__ == "__main__":
    unittest.main()
