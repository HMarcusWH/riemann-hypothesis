from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import checkpoint as c

class CheckpointControls(unittest.TestCase):
    def setup(self, root, *, phase="stage20", missing=False):
        w=Path(root)
        d=w/"verification";d.mkdir()
        stages=[{"status":"PASS"} for _ in range(20)]+[{"status":"NOT_RUN"} for _ in range(10)]
        if missing:stages[19]["status"]="INCOMPLETE"
        (d/"MODULAR_GATE_RECEIPT.json").write_text(json.dumps({
            "status":"PILOT_STAGE20_COMPLETE","stages":stages}))
        (d/"guard.process.json").write_text('{"status":"PASS"}')
        return w

    def test_actual_pilot_boundary_requires_all_20(self):
        with tempfile.TemporaryDirectory() as d:
            w=self.setup(d)
            s=c.check_stage_receipts(w,"stage20")
            self.assertEqual(s["stages"].count("PASS"),20)

    def test_incomplete_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            w=self.setup(d,missing=True)
            with self.assertRaises(c.PolicyError):
                c.check_stage_receipts(w,"stage20")

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            w=self.setup(d)
            (w/"verification"/"alias").symlink_to(w/"verification"/"guard.process.json")
            with self.assertRaises(c.PolicyError):
                c.inventory(w,"stage20")

    def test_seal_and_verify_without_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            w=self.setup(d)
            out=w/"checkpoints/stage20.json"
            with patch.object(c,"source_identity",return_value={"tree":"1"*40,"profile_sha256":"2"*64}):
                x=c.seal(w,"stage20","0"*40,out)
                verified=c.verify(w,out,c.sha256(out),"0"*40)
            self.assertEqual(verified["status"],"SEALED_EVIDENCE_VERIFIED_NOT_A_PROOF")
            self.assertFalse(verified["proof_acceptance"])
            self.assertFalse(x["stage_resume_authorized"])

    def test_tampered_object_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            w=self.setup(d)
            out=w/"checkpoints/stage20.json"
            with patch.object(c,"source_identity",return_value={"tree":"1"*40,"profile_sha256":"2"*64}):
                c.seal(w,"stage20","0"*40,out)
                expected=c.sha256(out)
                (w/"verification/guard.process.json").write_text('{"status":"CHANGED"}')
                with self.assertRaises(c.PolicyError):
                    c.verify(w,out,expected,"0"*40)

if __name__=="__main__":
    unittest.main()
