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
        post_hash = None
        if pilot:
            primary = {"status": "PILOT_STAGE20_COMPLETE", "exit_code": 0}
            post = {"schema": v.PILOT_INTEGRITY_SCHEMA, "status": "PASS",
                    "proof_acceptance": False, "production_stage30_status": "NOT_RUN",
                    "primary_execution": primary, "original_modular_source_sha256": "c"*64,
                    "details": {"scope": "Synthetic metadata-only fixture; no proof execution"}}
            pp = work/"verification"/v.PILOT_INTEGRITY_FILE
            pp.write_text(json.dumps(post))
            post_hash = v.sha256(pp)
            modular.update(pilot_execution_outcome=primary, pilot_post_integrity=post,
                           pilot_post_integrity_sha256=post_hash)
        mp = work/"verification/MODULAR_GATE_RECEIPT.json"
        mp.write_text(json.dumps(modular))
        a = {
            "checked_head": "0"*40, "checked_tree": "1"*40,
            "execution_mode": "pilot_stage20" if pilot else "full",
            "longrun_profile_sha256": "a"*64,
            "modular_receipt_sha256": v.sha256(mp),
            "modular_pass": not pilot, "pilot_completed": pilot,
            "pilot_post_integrity_pass": pilot, "pilot_post_integrity_sha256": post_hash,
            "original_modular_source_sha256": "c"*64,
        }
        (work/"verification/LONGRUN_CONTROLLER_RECEIPT.json").write_text(json.dumps(a))
        if independent:
            (work/"independent-verification").mkdir(exist_ok=True)
            (work/"independent-verification/INDEPENDENT_RECEIPT.json").write_text(json.dumps({
                "status": "PASS", "stages": [{"status":"PASS"} for _ in range(7)]}))
        return work

    def evaluate_fixture(self, work, mode, outcome):
        with patch.object(v, "source_identity", return_value={
            "tree":"1"*40,"profile_sha256":"a"*64,"original_source_manifest_sha256":"b"*64}):
            return v.evaluate(work, mode=mode, checked_head="0"*40,
                              independent_outcome=outcome)

    def test_pilot_never_becomes_theorem_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.evaluate_fixture(self.prepare(d, pilot=True, independent=False),
                            "pilot_stage20", "skipped")
            self.assertEqual(result["status"], "PILOT_COMPLETE_NO_PROOF_AUTHORITY")
            self.assertFalse(result["proof_acceptance"])

    def test_missing_last_modular_gate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.evaluate_fixture(self.prepare(d,n=29), "full", "success")
            self.assertEqual(result["status"], "NOT_ESTABLISHED")

    def test_missing_independent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.evaluate_fixture(self.prepare(d,independent=False), "full", "skipped")
            self.assertEqual(result["status"], "NOT_ESTABLISHED")

    def test_complete_receipts_only_review_not_proof_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.evaluate_fixture(self.prepare(d), "full", "success")
            self.assertEqual(result["status"], "COMPLETE_30_PLUS_7_RECEIPTS_REQUIRE_RESEARCH_REVIEW")
            self.assertFalse(result["proof_acceptance"])

    def test_modified_controller_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work=self.prepare(d)
            cp=work/"verification/LONGRUN_CONTROLLER_RECEIPT.json"
            data=json.loads(cp.read_text())
            data["modular_receipt_sha256"]="0"*64
            cp.write_text(json.dumps(data))
            self.assertEqual(self.evaluate_fixture(work,"full","success")["status"], "NOT_ESTABLISHED")

    def test_pilot_forged_as_modular_pass_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work=self.prepare(d,pilot=True,independent=False)
            cp=work/"verification/LONGRUN_CONTROLLER_RECEIPT.json"
            data=json.loads(cp.read_text())
            data["modular_pass"]=True
            cp.write_text(json.dumps(data))
            self.assertEqual(self.evaluate_fixture(work,"pilot_stage20","skipped")["status"], "NOT_ESTABLISHED")

    def test_pilot_missing_post_integrity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work = self.prepare(d, pilot=True, independent=False)
            (work/"verification"/v.PILOT_INTEGRITY_FILE).unlink()
            self.assertEqual(self.evaluate_fixture(work,"pilot_stage20","skipped")["status"], "NOT_ESTABLISHED")

    def test_pilot_post_integrity_bytes_drift_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            work = self.prepare(d, pilot=True, independent=False)
            pp = work/"verification"/v.PILOT_INTEGRITY_FILE
            data = json.loads(pp.read_text())
            data["status"] = "FAIL"
            pp.write_text(json.dumps(data))
            self.assertEqual(self.evaluate_fixture(work,"pilot_stage20","skipped")["status"], "NOT_ESTABLISHED")


class CollectionMountControls(unittest.TestCase):
    def fixture(self, root, extra=""):
        work = Path(root)/"work"
        work.mkdir()
        mounts = Path(root)/"mountinfo"
        mounts.write_text("1 0 0:1 / / rw - overlay overlay rw\n"+extra)
        return work, mounts

    def test_unmounted_evidence_roots_allow_collection(self):
        with tempfile.TemporaryDirectory() as d:
            work, mounts = self.fixture(d)
            record = v.collection_mount_guard(work, mountinfo=mounts)
            self.assertEqual(record["status"], "PASS_NO_MOUNTED_EVIDENCE_SUBTREE")
            self.assertFalse(record["proof_acceptance"])

    def test_remaining_bound_object_view_refuses_without_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            work, mounts = self.fixture(d)
            for relative in ("native/bootstrap-logs/view", "verification/view", "independent-verification/mounts/0"):
                with self.subTest(relative=relative):
                    target = work/relative
                    mounts.write_text("1 0 0:1 / / rw - overlay overlay rw\n"+
                                      f"2 1 7:0 / {target} ro - squashfs /dev/loop0 ro\n")
                    record = v.collection_mount_guard(work, mountinfo=mounts)
                    self.assertEqual(record["status"], "REFUSED")
                    self.assertEqual(record["blocked_mount_targets"][0]["target"], str(target))
                    self.assertFalse(target.exists())  # Pure fixture, no actual mount/traversal.

    def test_unreadable_or_oversize_mount_inventory_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            work, mounts = self.fixture(d)
            mounts.unlink()
            self.assertEqual(v.collection_mount_guard(work, mountinfo=mounts)["status"], "REFUSED")
            mounts.write_bytes(b"x"*(v.MOUNTINFO_LIMIT+1))
            self.assertEqual(v.collection_mount_guard(work, mountinfo=mounts)["status"], "REFUSED")
            mounts.write_text("1 0 0:1 / / rw optional optional optional -\n")
            self.assertEqual(v.collection_mount_guard(work, mountinfo=mounts)["status"], "REFUSED")


if __name__ == "__main__":
    unittest.main()
