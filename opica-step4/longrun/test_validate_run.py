import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import validate_run as v


class WorkflowReceiptControls(unittest.TestCase):
    def prepare(self, root, n=30, status="PASS", pilot=False, independent=True):
        work = Path(root)
        (work/"verification").mkdir(exist_ok=True)
        modular = {
            "status": "PILOT_STAGE20_COMPLETE" if pilot else status,
            "prior_round19_25_stage_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
            "stages": [{"status": "PASS" if i < (20 if pilot else n) else "NOT_RUN"}
                       for i in range(30)]}
        mp = work/"verification/MODULAR_GATE_RECEIPT.json"
        mp.write_text(json.dumps(modular))
        a = {
            "checked_head": "0"*40, "checked_tree": "1"*40,
            "execution_mode": "pilot_stage20" if pilot else "full",
            "longrun_profile_sha256": "a"*64,
            "modular_receipt_sha256": v.sha256(mp),
            "modular_pass": not pilot, "pilot_completed": pilot,
        }
        (work/"verification/LONGRUN_CONTROLLER_RECEIPT.json").write_text(json.dumps(a))
        if independent:
            (work/"independent-verification").mkdir(exist_ok=True)
            (work/"independent-verification/INDEPENDENT_RECEIPT.json").write_text(json.dumps({
                "status": "PASS", "stages": [{"status":"PASS"} for _ in range(7)]}))
        return work

    def run(self, work, mode, outcome):
        with patch.object(v, "source_identity", return_value={
            "tree":"1"*40,"profile_sha256":"a"*64,"original_source_manifest_sha256":"b"*64}):
            return v.evaluate(work, mode=mode, checked_head="0"*40,
                              independent_outcome=outcome)

    def test_pilot_never_becomes_theorem_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run(self.prepare(d, pilot=True, independent=False),
                            "pilot_stage20", "skipped")
            self.assertEqual(result["status"], "PILOT_COMPLETE_NO_PROOF_AUTHORITY")
            self.assertFalse(result["proof_acceptance"])

    def test_missing_last_modular_gate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run(self.prepare(d,n=29), "full", "success")
            self.assertEqual(result["status"], "NOT_ESTABLISHED")

    def test_missing_independent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run(self.prepare(d,independent=False), "full", "skipped")
            self.assertEqual(result["status"], "NOT_ESTABLISHED")

    def test_complete_receipts_only_review_not_proof_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run(self.prepare(d), "full", "success")
            self.assertEqual(result["status"], "COMPLETE_30_PLUS_7_RECEIPTS_REQUIRE_RESEARCH_REVIEW")
            self.assertFalse(result["proof_acceptance"])

    def test_modified_controller_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work=self.prepare(d)
            cp=work/"verification/LONGRUN_CONTROLLER_RECEIPT.json"
            data=json.loads(cp.read_text())
            data["modular_receipt_sha256"]="0"*64
            cp.write_text(json.dumps(data))
            self.assertEqual(self.run(work,"full","success")["status"], "NOT_ESTABLISHED")

    def test_pilot_forged_as_modular_pass_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work=self.prepare(d,pilot=True,independent=False)
            cp=work/"verification/LONGRUN_CONTROLLER_RECEIPT.json"
            data=json.loads(cp.read_text())
            data["modular_pass"]=True
            cp.write_text(json.dumps(data))
            self.assertEqual(self.run(work,"pilot_stage20","skipped")["status"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
