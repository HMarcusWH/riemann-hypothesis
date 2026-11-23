import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from qualify import QualifyError,check_axiom_log,source

ROOT=Path(__file__).resolve().parent
class SourceQualifierTests(unittest.TestCase):
  def test_original_source_and_no_claim(self):
    d=source()
    self.assertEqual(d["status"],"PASS_SOURCE_ONLY")
    self.assertFalse(d["proof_acceptance"])
    self.assertEqual(d["RH"],"OPEN")
  def test_forbidden_axiom_refused(self):
    with tempfile.TemporaryDirectory() as d:
      q=Path(d)/"log"
      q.write_text("OPICACommunityV436.suppliedRH relies on axioms: [propext, Some.badAxiom]\n")
      with self.assertRaises(QualifyError):check_axiom_log(q)
  def test_missing_ax_report_refused(self):
    with tempfile.TemporaryDirectory() as d:
      q=Path(d)/"log";q.write_text("Lean says OK\n")
      with self.assertRaises(QualifyError):check_axiom_log(q)
  def test_only_permitted_axioms_are_not_full_proof(self):
    with tempfile.TemporaryDirectory() as d:
      q=Path(d)/"log";q.write_text(
        "OPICACommunityV436.suppliedRH relies on axioms: [propext, Classical.choice, Quot.sound]\n")
      r=check_axiom_log(q)
      self.assertFalse(r["proof_acceptance"])
      self.assertFalse(r["full_50_roots"])
if __name__=="__main__":unittest.main()
