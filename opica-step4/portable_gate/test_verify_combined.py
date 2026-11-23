#!/usr/bin/env python3
"""Mutation tests of the gate machinery. These tests do not compile or prove C1."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("opica_gate",
                                             Path(__file__).with_name("verify_combined.py"))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class StrictGateMutations(unittest.TestCase):
    name = "Zeta23.OPICARound19.step4C1"
    target = "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"
    allowed = {"propext", "Classical.choice", "Quot.sound"}

    def valid_log(self):
        return (
            "OPICA19_TYPE_BEGIN " + self.name + "\n" +
            self.name + " : " + self.target + "\n" +
            "OPICA19_TYPE_END " + self.name + "\n" +
            "'" + self.name + "' depends on axioms: [propext, Classical.choice, Quot.sound]\n"
        )

    def test_complete_named_audit_positive_control(self):
        result = gate.parse_audit(self.valid_log(), [self.name], self.allowed)
        self.assertEqual(result[self.name]["axioms"],
                         ["propext", "Classical.choice", "Quot.sound"])

    def test_missing_named_type_is_rejected(self):
        changed = self.valid_log().replace("OPICA19_TYPE_BEGIN " + self.name,
                                          "OPICA19_TYPE_BEGIN AnonymousExample")
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_duplicate_named_type_is_rejected(self):
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(self.valid_log() + self.valid_log(), [self.name], self.allowed)

    def test_transitive_placeholder_is_rejected(self):
        changed = self.valid_log().replace("Quot.sound]", "Quot.sound, sorryAx]")
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_project_axiom_is_rejected(self):
        changed = self.valid_log().replace("Quot.sound]", "Quot.sound, Fake.arithmeticUpper]")
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_polymorphic_standard_axioms_are_accepted(self):
        changed = self.valid_log().replace("Classical.choice", "Classical.choice.{u}")
        changed = changed.replace("Quot.sound", "Quot.sound.{u}")
        result = gate.parse_audit(changed, [self.name], self.allowed)
        self.assertEqual(result[self.name]["axioms"],
                         ["propext", "Classical.choice", "Quot.sound"])

    def test_polymorphic_project_axiom_is_rejected(self):
        changed = self.valid_log().replace("Quot.sound]", "Quot.sound.{u}, Fake.bound.{u}]")
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_missing_axiom_report_is_rejected(self):
        changed = self.valid_log().split("'" + self.name + "' depends")[0]
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_extra_axiom_record_is_rejected(self):
        changed = self.valid_log() + "'Unrelated.result' does not depend on any axioms\n"
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_truncated_type_is_rejected(self):
        changed = self.valid_log().replace(self.target, "...")
        with self.assertRaises(gate.GateFailure):
            gate.parse_audit(changed, [self.name], self.allowed)

    def test_zero_exit_with_error_diagnostic_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = object.__new__(gate.Gate)
            obj.output = Path(directory)
            obj.env = dict(os.environ)
            argv = [sys.executable, "-c",
                    "print('Claim.lean:9:4: error: unsolved goals')"]
            with self.assertRaises(gate.GateFailure):
                obj.run_process("invalid_zero_exit", argv, obj.output, 15)
            receipt = json.loads((obj.output / "invalid_zero_exit.process.json").read_text())
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["status"], "FAIL")
            self.assertTrue(receipt["diagnostics"])

    def test_zero_exit_with_warning_diagnostic_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = object.__new__(gate.Gate)
            obj.output = Path(directory)
            obj.env = dict(os.environ)
            argv = [sys.executable, "-c",
                    "print(\"Claim.lean:9:4: warning: declaration uses 'sorry'\")"]
            with self.assertRaises(gate.GateFailure):
                obj.run_process("warning_zero_exit", argv, obj.output, 15)
            receipt = json.loads((obj.output / "warning_zero_exit.process.json").read_text())
            self.assertEqual(receipt["status"], "FAIL")

    def test_timeout_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = object.__new__(gate.Gate)
            obj.output = Path(directory)
            obj.env = dict(os.environ)
            argv = [sys.executable, "-c", "import time; time.sleep(20)"]
            with self.assertRaises(gate.GateIncomplete):
                obj.run_process("timed_out", argv, obj.output, 0.01)
            receipt = json.loads((obj.output / "timed_out.process.json").read_text())
            self.assertEqual(receipt["status"], "TIMEOUT")

    def test_positive_process_control(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = object.__new__(gate.Gate)
            obj.output = Path(directory)
            obj.env = dict(os.environ)
            result = obj.run_process("positive", [sys.executable, "-c", "print('accepted')"],
                                     obj.output, 15)
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["status"], "PASS")

    def test_solver_export_cannot_omit_closed_claim_roots(self):
        obj = object.__new__(gate.Gate)
        obj.spec = json.loads(Path(__file__).with_name("GATE_SPEC.json").read_text())
        names = set(obj.export_names(closed=True))
        actual_claims = {"Zeta23.OPICARound19.step4C1",
                         "Zeta23.OPICARound19.Audit.literalC1",
                         "Zeta23.OPICARound19.Audit.provedRequiredC1",
                         "UpperTheory.FinalTheorems.riemannHypothesis"}
        self.assertTrue(actual_claims <= names)
        self.assertTrue(set(obj.spec["fingerprint_theorems"]) <= names)
        self.assertFalse(actual_claims & set(obj.export_names(closed=False)))

    def test_retargeted_input_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second, alias = root / "first", root / "second", root / "alias"
            first.write_bytes(b"first object")
            second.write_bytes(b"substituted object")
            alias.symlink_to(first)
            obj = object.__new__(gate.Gate)
            obj.input_hashes = {}
            obj.bind(alias)
            alias.unlink()
            alias.symlink_to(second)
            with self.assertRaises(gate.GateFailure):
                obj.bind(alias)

    def test_new_shadow_object_is_rejected_by_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Original.olean").write_bytes(b"original")
            obj = object.__new__(gate.Gate)
            obj.input_hashes = {}
            obj.object_root_inventories = {}
            obj.snapshot_objects(root)
            (root / "Shadow.olean").write_bytes(b"new shadow")
            with self.assertRaises(gate.GateFailure):
                obj.snapshot_objects(root)

    def test_shared_package_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Target.olean").write_bytes(b"substituted")
            obj = object.__new__(gate.Gate)
            obj.input_hashes = {}
            obj.receipt = {"environment": {"import_roots": [str(root)]}}
            obj.canonical_package_inventories = {"mathlib": {"Target.olean": "0" * 64}}
            obj.combined_packages = {"mathlib": {"objects": root}}
            obj.toolchain_prefix = obj.combined_toolchain_prefix = root / "toolchain"
            obj.object_root_inventories = {str((obj.toolchain_prefix / "lib/lean").resolve()): {}}
            with self.assertRaises(gate.GateFailure):
                obj.shared_dependency_comparison()

    def test_identical_shadow_object_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected, shadow = root / "expected", root / "shadow"
            expected.mkdir()
            shadow.mkdir()
            for directory_path in (expected, shadow):
                (directory_path / "Target.olean").write_bytes(b"same object bytes")
            obj = object.__new__(gate.Gate)
            obj.input_hashes = {}
            obj.receipt = {"environment": {"import_roots": [str(shadow), str(expected)]}}
            obj.canonical_package_inventories = {
                "mathlib": {"Target.olean": gate.sha256(expected / "Target.olean")}}
            obj.combined_packages = {"mathlib": {"objects": expected}}
            obj.toolchain_prefix = obj.combined_toolchain_prefix = root / "toolchain"
            obj.object_root_inventories = {str((obj.toolchain_prefix / "lib/lean").resolve()): {}}
            with self.assertRaises(gate.GateFailure):
                obj.shared_dependency_comparison()

    def test_statement_comparison_cannot_use_definition_holes(self):
        config = json.loads(Path(__file__).with_name("comparator.json").read_text())
        self.assertEqual(config["definition_names"], [])
        self.assertIn("Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive",
                      config["theorem_names"])
        self.assertIn("closed_export_type_and_axiom_audit", gate.STAGES)
        self.assertIn("complete_fresh_kernel_replay", gate.STAGES)


if __name__ == "__main__":
    unittest.main()

