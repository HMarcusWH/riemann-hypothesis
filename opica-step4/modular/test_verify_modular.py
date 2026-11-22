"""Adversarial controls for the new certificate identity and claim boundary.

These are runner tests; passing them establishes no C1/RH theorem.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import verify_modular as gate


class StreamControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_stream(self, code, **kwargs):
        return gate.stream_command([sys.executable, "-c", code], cwd=self.root, env=dict(os.environ),
            log=self.root / "stderr.log", record=self.root / "record.json",
            timeout=kwargs.pop("timeout", 3), max_bytes=kwargs.pop("max_bytes", 1024), **kwargs)

    def record(self):
        return json.loads((self.root / "record.json").read_text())

    def test_exact_binary_stdout_preserved(self):
        data = b"\x00\xff\r\nA\n\x80"
        path = self.root / "stdout.bin"
        row = self.run_stream("import os; os.write(1," + repr(data) + ")",
                              expected_sha=hashlib.sha256(data).hexdigest(), stdout_path=path)
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(row["stdout_bytes"], len(data))
        self.assertEqual(row["status"], "PASS")
        self.assertEqual(self.record()["stdout_sha256"], hashlib.sha256(data).hexdigest())

    def test_stream_hash_is_not_normalized(self):
        with self.assertRaisesRegex(gate.GateFailure, "SHA256 differs"):
            self.run_stream("import os; os.write(1,b'A\\r\\n')",
                            expected_sha=hashlib.sha256(b"A\n").hexdigest())
        self.assertEqual(self.record()["status"], "FAIL")

    def test_partial_stdout_nonzero_is_rejected(self):
        with self.assertRaisesRegex(gate.GateFailure, "exited with 7"):
            self.run_stream("import os; os.write(1,b'good'); raise SystemExit(7)",
                            expected_sha=hashlib.sha256(b"good").hexdigest())
        self.assertEqual(self.record()["exit_code"], 7)

    def test_warning_with_zero_exit_is_rejected(self):
        with self.assertRaisesRegex(gate.GateFailure, "diagnostic"):
            self.run_stream("import os; os.write(1,b'x'); os.write(2,b'warning: invalid export\\n')")

    def test_empty_stream_is_rejected(self):
        with self.assertRaisesRegex(gate.GateFailure, "empty stream"):
            self.run_stream("pass")

    def test_oversized_stream_is_rejected(self):
        with self.assertRaisesRegex(gate.GateFailure, "byte limit"):
            self.run_stream("import os; os.write(1,b'x'*1025)")
        self.assertEqual(self.record()["status"], "FAIL")

    def test_timeout_with_stdout_still_open_is_incomplete(self):
        with self.assertRaises(gate.GateIncomplete):
            self.run_stream("import os,time; os.write(1,b'x'); time.sleep(10)", timeout=0.2)
        self.assertEqual(self.record()["status"], "INCOMPLETE")
        self.assertIsNotNone(self.record()["exit_code"])

    def test_timeout_after_stdout_eof_is_incomplete(self):
        with self.assertRaises(gate.GateIncomplete):
            self.run_stream("import os,time; os.write(1,b'x'); os.close(1); time.sleep(10)", timeout=0.2)
        self.assertEqual(self.record()["status"], "INCOMPLETE")

    def test_timeout_kills_descendant_after_producer_leader_exits(self):
        code = ("import os,time,signal; pid=os.fork(); "
                "open('child.pid','w').write(str(pid)) if pid else None; "
                "os._exit(0) if pid else None; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(10)")
        with self.assertRaises(gate.GateIncomplete):
            self.run_stream(code, timeout=0.2)
        pid = int((self.root / "child.pid").read_text())
        state = Path(f"/proc/{pid}/stat")
        for _ in range(100):
            try:
                process_state = state.read_text().split()[2]
            except FileNotFoundError:
                break
            if process_state in ("Z", "X"):
                break
            time.sleep(0.01)
        try:
            process_state = state.read_text().split()[2]
        except FileNotFoundError:
            pass  # A reaped child has no /proc entry.
        else:
            self.assertIn(process_state, ("Z", "X"))

    def test_existing_output_is_rejected_without_overwrite(self):
        path = self.root / "output.bin"
        path.write_bytes(b"old")
        with self.assertRaises(gate.GateFailure):
            self.run_stream("print('new')", stdout_path=path)
        self.assertEqual(path.read_bytes(), b"old")


class GateControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("external", "native", "integration"):
            (self.root / name).mkdir()
        self.args = argparse.Namespace(external=self.root / "external", native=self.root / "native",
            integration=self.root / "integration", output=self.root / "output", external_lib=None,
            external_evidence=gate.HERE / "external-evidence", external_head=None, native_receipt=None,
            lake=Path(sys.executable), exporter=Path(sys.executable), comparison_helper=Path(sys.executable),
            comparator_lake=None, exporter_source=None, jobs=1, max_heartbeats=1600000,
            compile_timeout=30, replay_timeout=30, fresh_timeout=30, export_timeout=30, comparison_timeout=30)

    def tearDown(self):
        self.temp.cleanup()

    def test_initial_receipt_cannot_claim_original_gate_or_closed_theorem(self):
        obj = gate.ModularGate(self.args)
        self.assertFalse((obj.output / "COMBINED_GATE_RECEIPT.json").exists())
        data = json.loads((obj.output / "MODULAR_GATE_RECEIPT.json").read_text())
        self.assertEqual(data["schema"], gate.GATE_VERSION)
        self.assertEqual(data["closure_claim"], "NOT_ESTABLISHED")
        self.assertEqual(data["supplier_kernel_execution"], "NOT_ESTABLISHED")
        self.assertEqual(data["full_combined_export_kernel_execution"], "NOT_RUN_BY_THIS_GATE")
        self.assertEqual(data["prior_round19_25_stage_gate"], "NOT_RUN_OR_BLOCKED_UNCHANGED")
        self.assertTrue(all(row["status"] == "NOT_RUN" for row in data["stages"]))

    def test_published_evidence_validates_with_external_scope(self):
        obj = gate.ModularGate(self.args)
        row = obj.external_validation_evidence()
        self.assertEqual(row["accepted_supplier_declarations"], 1468418)
        self.assertEqual(obj.receipt["supplier_kernel_execution"], "EXTERNAL_PUBLISHED_RECEIPT")
        self.assertEqual(obj.receipt["supplier_certificate_identity"], "NOT_ESTABLISHED")

    def test_changed_published_log_is_rejected(self):
        evidence = self.root / "evidence"
        shutil.copytree(gate.HERE / "external-evidence", evidence)
        with (evidence / "con-leche-master.log").open("ab") as stream:
            stream.write(b"\nmodified\n")
        self.args.external_evidence = evidence
        obj = gate.ModularGate(self.args)
        with self.assertRaisesRegex(gate.GateFailure, "verification log changed"):
            obj.external_validation_evidence()

    def test_supplier_export_cannot_shrink_to_five_headlines(self):
        obj = gate.ModularGate(self.args)
        self.assertEqual(len(obj.spec["supplier_export_targets"]), 38)
        original = Path("/workspace/scratch/ba87d581091d/research_round19/large-proof/export-targets.txt")
        if original.exists():
            self.assertEqual(tuple(original.read_text().split()), gate.SUPPLIER_TARGETS)
        self.assertEqual(obj.spec["external_theorem"], "riemannHypothesis")
        self.assertEqual(obj.spec["external_endpoint"], "Main")
        self.assertEqual(obj.spec["closed_comparison_module"], gate.CLOSED_MODULE)

    def test_all_used_native_proofs_are_targets(self):
        obj = gate.ModularGate(self.args)
        self.assertEqual(len(obj.spec["native_proof_targets"]), 9)
        self.assertIn("Zeta23.OPICARound19.ReceiverAudit.exactReceiver", obj.spec["native_proof_targets"])
        self.assertIn("Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative", obj.spec["native_proof_targets"])

    def test_modified_auxiliary_roots_fail_closed(self):
        spec = json.loads((gate.FROZEN / "GATE_SPEC.json").read_text())
        spec["export_auxiliary_targets"].remove("Quot.sound")
        with self.assertRaises(gate.GateFailure):
            gate.modular_spec(spec)

    def test_required_stages_include_both_proof_and_semantic_checks(self):
        required = {"complete_native_fresh_kernel_replay", "guarded_kernel_import",
            "fresh_closed_kernel_construction",
            "actual_closed_object_audit", "closed_type_and_axiom_audit", "closed_module_kernel_replay",
            "final_native_proof_export_identity", "canonical_statement_definition_comparison",
            "final_supplier_certificate_identity", "comparison_controls", "final_input_integrity"}
        self.assertTrue(required <= set(gate.STAGES))

    def test_manifest_rejects_duplicate_entries(self):
        line = "a" * 64 + "  solution.ndjson\n"
        with self.assertRaises(gate.GateFailure):
            gate.parse_sha_manifest(line + line)

    def test_manifest_rejects_traversal(self):
        with self.assertRaises(gate.GateFailure):
            gate.parse_sha_manifest("a" * 64 + "  ../solution.ndjson\n")

    def test_cli_does_not_require_giant_comparator(self):
        args = gate.arguments(["--external", "a", "--integration", "b", "--lake", "c",
                              "--exporter", "d", "--comparison-helper", "e"])
        self.assertIsNone(args.comparator_lake)

    def test_empty_success_log_is_bound_but_empty_proof_is_rejected(self):
        obj = gate.ModularGate(self.args)
        path = obj.output / "quiet.log"
        path.touch()
        self.assertEqual(obj.bind_log(path), hashlib.sha256(b"").hexdigest())
        with self.assertRaises(gate.GateBlocked):
            obj.bind(path)

    def test_cli_accepts_explicit_infrastructure_descendant_pin(self):
        args = gate.arguments(["--external", "a", "--integration", "b", "--lake", "c",
                              "--exporter", "d", "--comparison-helper", "e",
                              "--external-head", "f" * 40])
        self.assertEqual(args.external_head, "f" * 40)


class SourceDescendantControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Local gate fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "src").mkdir()
        (self.root / "src/Main.lean").write_text("theorem fixture : True := True.intro\n")
        self.git("add", "src")
        self.git("commit", "-qm", "source checkpoint")
        self.base = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD:src")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL,
                                       text=True).strip()

    def test_infrastructure_descendant_with_identical_source_is_accepted(self):
        (self.root / "workflow.yml").write_text("fixture: infrastructure\n")
        self.git("add", "workflow.yml")
        self.git("commit", "-qm", "infrastructure only")
        row = gate.verify_supplier_checkpoint(self.root, self.base, self.tree)
        self.assertEqual(row["head"], self.git("rev-parse", "HEAD"))
        self.assertNotEqual(row["head"], self.base)

    def test_descendant_with_modified_proof_source_is_rejected(self):
        (self.root / "src/Main.lean").write_text("axiom fixture : False\n")
        self.git("add", "src")
        self.git("commit", "-qm", "changed mathematical source")
        with self.assertRaisesRegex(gate.GateFailure, "src tree differs"):
            gate.verify_supplier_checkpoint(self.root, self.base, self.tree)

    def test_unrelated_commit_with_identical_source_is_rejected(self):
        orphan = self.git("commit-tree", self.git("rev-parse", "HEAD^{tree}"), "-m", "unrelated source")
        self.git("checkout", "--detach", orphan)
        with self.assertRaises(gate.GateBlocked):
            gate.verify_supplier_checkpoint(self.root, self.base, self.tree)


if __name__ == "__main__":
    unittest.main()
