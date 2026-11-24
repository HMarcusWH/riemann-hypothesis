"""Adversarial nonaccepting source scanner controls."""
from pathlib import Path
import tempfile
import unittest
import scan

class FirstContactTests(unittest.TestCase):
    def test_real_import_syntax(self):
        s = "module\npublic import Statements\npublic meta import Lean\nprivate import Foo.Bar\nimport Test.A -- note\n"
        self.assertEqual(scan.imports_of(s), ["Statements", "Lean", "Foo.Bar", "Test.A"])

    def test_closure_explicitly_source_only(self):
        edges = {"Main": ["A", "B"], "A": ["C"], "B": ["C"], "C": ["Mathlib"]}
        res = scan.source_closure(["Main"], edges)
        self.assertEqual(res["source_module_count"], 4)
        self.assertIn("Mathlib", res["unresolved_import_examples"])

    def test_reject_path_traversal(self):
        for bad in ("../a.lean", "/abs.lean", "a.txt"):
            with self.assertRaises(scan.SourceSearchError):
                scan.module_name(bad)

    def test_no_proof_authority_from_lexical_hits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/"Main.lean").write_text(
                "module\npublic import Foo\n"
                "theorem riemannHypothesis : RiemannHypothesis := sorry\n",
                encoding="utf-8")
            (root/"Foo.lean").write_text("module\n-- Claim.zeta in a comment\n")
            r=scan.analyze({
                "frontier_roots":["Main"], "search_target":"TEST_TARGET",
            }, scan.source_scan(root,["riemannHypothesis","CofinalMomentSliceVanishingErrorBounds"]))
            self.assertFalse(r["proof_acceptance"])
            self.assertFalse(r["independent_C1_certificate_found"])
            self.assertFalse(r["native_compiler_compatible_without_rebuild"])
            self.assertEqual(r["native_C1_symbol_in_supplier_source"],0)
            self.assertEqual(r["source_import_frontier"]["Main"]["source_module_count"],2)

    def test_target_is_not_lean_proof(self):
        x=scan.read_target()
        self.assertFalse(x["proof_acceptance"])
        self.assertEqual(x["rh_status"],"OPEN")
        self.assertTrue(any("circular" in text.lower() for text in x["falsification"]))

if __name__ == "__main__":
    unittest.main()
