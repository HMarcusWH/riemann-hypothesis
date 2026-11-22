from __future__ import annotations
import argparse
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import policy
import verify_modular_longrun as v


class StageSelectionControls(unittest.TestCase):
    def test_separate_selected_deadlines(self):
        p = policy.profile()
        self.assertEqual(v.LONGRUN_STAGES,
                         frozenset(["guarded_kernel_import", "fresh_closed_kernel_construction"]))
        class Frozen:
            def kernel_construct(self, module, mode, stage_name):
                return {"stage": stage_name, "timeout_during_call": self.args.compile_timeout}
        class Mod:
            ModularGate = Frozen
        Gate = v.make_gate_class(Mod, p)
        instance = Gate.__new__(Gate)
        instance.args = argparse.Namespace(compile_timeout=1800)
        instance.longrun_budgets = []
        observed = instance.kernel_construct("Main", "guard", "guarded_kernel_import")
        self.assertEqual(observed["timeout_during_call"], 14400)
        self.assertEqual(instance.args.compile_timeout, 1800)
        other = instance.kernel_construct("Other", "normal", "canonical_modules_compile")
        self.assertEqual(other["timeout_during_call"], 1800)
        self.assertEqual(len(instance.longrun_budgets), 1)

    def test_budget_restored_on_exception(self):
        p = policy.profile()
        class Frozen:
            def kernel_construct(self, module, mode, stage_name):
                raise RuntimeError("synthetic proof failure")
        class Mod:
            ModularGate = Frozen
        Gate = v.make_gate_class(Mod, p)
        instance = Gate.__new__(Gate)
        instance.args = argparse.Namespace(compile_timeout=1800)
        instance.longrun_budgets = []
        with self.assertRaisesRegex(RuntimeError, "synthetic"):
            instance.kernel_construct("Main", "guard", "guarded_kernel_import")
        self.assertEqual(instance.args.compile_timeout, 1800)

    def test_wrong_previous_budget_fails_closed(self):
        p = policy.profile()
        class Frozen:
            def kernel_construct(self, module, mode, stage_name):
                self.fail("Must not be called")
        class Mod:
            ModularGate = Frozen
        Gate = v.make_gate_class(Mod, p)
        instance = Gate.__new__(Gate)
        instance.args = argparse.Namespace(compile_timeout=900)
        instance.longrun_budgets = []
        with self.assertRaises(policy.PolicyError):
            instance.kernel_construct("Main", "guard", "guarded_kernel_import")

    def test_pilot_receipt_cannot_claim_modular_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            receipt = root / "MODULAR_GATE_RECEIPT.json"
            receipt.write_text('{"status":"PILOT_STAGE20_COMPLETE"}')
            stages = [{"status":"PASS"}] * 20 + [{"status":"NOT_RUN"}] * 10
            gate = argparse.Namespace(receipt={"status":"PILOT_STAGE20_COMPLETE","stages":stages}, output=root)
            with patch.object(v, "git", return_value="0"*40):
                info = v.controller_receipt(root/"CONTROLLER.json", mode="pilot_stage20",
                                             head="0"*40, p=policy.profile(), result=0, gate=gate,
                                             stage_budgets=[])
            self.assertEqual(info["status"], "PILOT_STAGE20_COMPLETE_NOT_MODULAR_PASS")
            self.assertFalse(info["modular_pass"])
            self.assertFalse(info["proof_acceptance"])
            self.assertFalse(info["independent_pass"])


if __name__ == "__main__":
    unittest.main()
