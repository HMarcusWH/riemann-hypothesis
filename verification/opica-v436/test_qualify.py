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

  def test_exact_public_inventory_and_independent_accounting(self):
    from qualify import PUBLIC_ROOTS,check_public_axiom_log
    from independent_38 import ROOTS,acceptance
    from common import Failure
    self.assertEqual(len(ROOTS),38)
    self.assertEqual(len(set(ROOTS)),38)
    self.assertEqual(len(PUBLIC_ROOTS),5)
    sample=("con-leche: read: emitting records from 38 constants\n"
            "con-leche: parse done: 100 fold records — the file's 100, 0 built-in prelude records synthesised\n"
            "con-leche: check done: 100 declarations\n"
            "con-leche: accepted 100 declarations (--verified)\n")
    self.assertEqual(acceptance(sample,38,complete_prelude=True),100)
    for bad in (sample.replace("38 constants","37 constants"),
                sample.replace("0 built-in","1 built-in"),sample+"internal error: injected\n",
                sample.replace("accepted 100","accepted 99")):
      with self.assertRaises(Failure):acceptance(bad,38,complete_prelude=True)
    with tempfile.TemporaryDirectory() as td:
      q=Path(td)/"log"
      names=(*PUBLIC_ROOTS,"OPICACommunityV436.suppliedRH")
      raw="".join("'"+n+"' depends on axioms: [propext, Classical.choice, Quot.sound]\n" for n in names)
      q.write_text(raw)
      self.assertEqual(set(check_public_axiom_log(q)["roots"]),set(PUBLIC_ROOTS))
      q.write_text(raw.replace("'LFunction_eq_zero_re' depends on axioms: [propext","'LFunction_eq_zero_re' depends on axioms: [bad.axiom"))
      with self.assertRaises(QualifyError):check_public_axiom_log(q)
  def test_multiline_actual_lean_axiom_reports(self):
    from qualify import _named_axiom_report
    text="'riemannHypothesis' depends on axioms: [propext,\n  Classical.choice,\n  Quot.sound]\n"
    self.assertEqual(_named_axiom_report(text,"riemannHypothesis"),["Classical.choice","Quot.sound","propext"])
    for bad in (text+text,text.replace("Quot.sound","sorryAx"),text.replace("]","")):
      with self.assertRaises(QualifyError):_named_axiom_report(bad,"riemannHypothesis")
  def test_dispatch_and_independent_reader_use_same_topic_ref(self):
    topic="refs/heads/research/opica-community-v436-supplier-qualification-20261123"
    workflow=(ROOT.parents[1]/".github/workflows/opica-v436-supplier.yml").read_text()
    reader=(ROOT/"independent_38.py").read_text()
    self.assertIn("github.ref == '"+topic+"'",workflow)
    self.assertIn('os.environ.get("GITHUB_REF")=="'+topic+'"',reader)
    self.assertIn("inputs.verify_head == github.sha",workflow)
    self.assertNotIn("github.ref == 'refs/heads/main'",workflow)
  def test_combined_candidate_preserves_exact_original_50_roots(self):
    from combined_50 import bridge_contract, COMBINED, NATIVE_ROOTS, named_axioms
    from common import Failure
    self.assertEqual(len(COMBINED),50)
    self.assertEqual(len(NATIVE_ROOTS),12)
    self.assertEqual(len(bridge_contract()["source_blobs"]),6)
    good="'x' depends on axioms: [propext,\n  Classical.choice,\n  Quot.sound]\n"
    self.assertEqual(named_axioms(good,["x"])["x"],["Classical.choice","Quot.sound","propext"])
    for bad in (good+"error: broken",good.replace("Quot.sound","sorryAx"),good+good):
      with self.assertRaises(Failure):named_axioms(bad,["x"])
if __name__=="__main__":unittest.main()
