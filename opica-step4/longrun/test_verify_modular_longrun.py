from __future__ import annotations
import argparse
import ast
import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
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
            post = {"schema": v.PILOT_INTEGRITY_SCHEMA, "status":"PASS",
                    "proof_acceptance":False, "production_stage30_status":"NOT_RUN"}
            pp = root/v.PILOT_INTEGRITY_FILE
            pp.write_text(json.dumps(post))
            gate = argparse.Namespace(receipt={"status":"PILOT_STAGE20_COMPLETE","stages":stages,
                "pilot_post_integrity":post, "pilot_post_integrity_sha256":v.sha256(pp)}, output=root)
            with patch.object(v, "git", return_value="0"*40):
                info = v.controller_receipt(root/"CONTROLLER.json", mode="pilot_stage20",
                                             head="0"*40, p=policy.profile(), result=0, gate=gate,
                                             stage_budgets=[])
            self.assertEqual(info["status"], "PILOT_STAGE20_COMPLETE_NOT_MODULAR_PASS")
            self.assertFalse(info["modular_pass"])
            self.assertFalse(info["proof_acceptance"])
            self.assertFalse(info["independent_pass"])


class PilotLifecycleControls(unittest.TestCase):
    def make_fixture(self, root, *, child_failure=False, integrity_failure=False, mode="pilot_stage20"):
        # Exact ordered names, but deliberately synthetic actions: no Lean/process execution.
        tree = ast.parse(v.ORIGINAL.read_text())
        stages = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "STAGES" for t in node.targets))
        class Incomplete(RuntimeError):
            pass
        class Blocked(RuntimeError):
            pass
        class Frozen:
            def __init__(self, args):
                self.args, self.output = args, args.output
                self.calls = []
                self.receipt = {"status":"RUNNING", "stages":[
                    {"name":name,"status":"NOT_RUN"} for name in stages]}
            def __getattr__(self, name):
                if name not in stages:
                    raise AttributeError(name)
                def action():
                    self.calls.append(name)
                    if name == stages[19] and child_failure:
                        raise Incomplete("literal synthetic child timeout")
                    return {"fixture":name}
                return action
            def stage(self, name, action):
                row = next(row for row in self.receipt["stages"] if row["name"] == name)
                try:
                    row.update(status="PASS", details=action())
                except Incomplete as err:
                    row.update(status="INCOMPLETE", failure=str(err))
                    raise
            def save(self):
                (self.output/"MODULAR_GATE_RECEIPT.json").write_text(json.dumps(self.receipt))
            def final_integrity(self):
                self.calls.append("SEPARATE_POST_INTEGRITY")
                if integrity_failure:
                    raise RuntimeError("literal synthetic input drift")
                return {"scope":"Synthetic lifecycle fixture only", "bound_file_count":2}
            def execute(self):
                self.calls.append("UNCHANGED_FULL_EXECUTE")
                return 17
        mod = SimpleNamespace(ModularGate=Frozen, STAGES=stages,
                              GateIncomplete=Incomplete, GateBlocked=Blocked,
                              old=SimpleNamespace(utc_now=lambda:"fixture-time"))
        gate = v.make_gate_class(mod,policy.profile())(argparse.Namespace(output=Path(root)),mode)
        return gate, stages

    def test_successful_pilot_rehashes_without_stage30_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            gate, stages = self.make_fixture(d)
            self.assertEqual(gate.execute(),0)
            self.assertEqual(gate.calls,list(stages[:20])+["SEPARATE_POST_INTEGRITY"])
            self.assertEqual([r["status"] for r in gate.receipt["stages"]], ["PASS"]*20+["NOT_RUN"]*10)
            self.assertEqual(gate.receipt["pilot_post_integrity"]["status"],"PASS")
            self.assertEqual(gate.receipt["pilot_post_integrity_sha256"],v.sha256(Path(d)/v.PILOT_INTEGRITY_FILE))

    def test_child_failure_still_rehashes_and_retains_literal_failure(self):
        with tempfile.TemporaryDirectory() as d:
            gate, _ = self.make_fixture(d,child_failure=True)
            self.assertEqual(gate.execute(),2)
            self.assertEqual(gate.calls[-1],"SEPARATE_POST_INTEGRITY")
            self.assertEqual(gate.receipt["status"],"INCOMPLETE")
            self.assertEqual(gate.receipt["failure"],"literal synthetic child timeout")
            self.assertEqual(gate.receipt["stages"][19]["status"],"INCOMPLETE")
            self.assertEqual(gate.receipt["pilot_post_integrity"]["status"],"PASS")
            self.assertEqual([r["status"] for r in gate.receipt["stages"][20:]],["NOT_RUN"]*10)

    def test_post_integrity_failure_does_not_erase_successful_stage20(self):
        with tempfile.TemporaryDirectory() as d:
            gate, _ = self.make_fixture(d,integrity_failure=True)
            self.assertEqual(gate.execute(),2)
            self.assertEqual(gate.receipt["status"],"PILOT_POST_INTEGRITY_FAILED")
            self.assertEqual(gate.receipt["pilot_execution_outcome"]["exit_code"],0)
            self.assertEqual(gate.receipt["pilot_post_integrity"]["failure"],"literal synthetic input drift")
            self.assertEqual([r["status"] for r in gate.receipt["stages"]],["PASS"]*20+["NOT_RUN"]*10)

    def test_both_failures_remain_separate(self):
        with tempfile.TemporaryDirectory() as d:
            gate, _ = self.make_fixture(d,child_failure=True,integrity_failure=True)
            self.assertEqual(gate.execute(),2)
            self.assertEqual(gate.receipt["status"],"INCOMPLETE")
            self.assertEqual(gate.receipt["failure"],"literal synthetic child timeout")
            self.assertEqual(gate.receipt["pilot_post_integrity"]["failure"],"literal synthetic input drift")

    def test_full_mode_delegates_without_extra_pilot_operation(self):
        with tempfile.TemporaryDirectory() as d:
            gate, _ = self.make_fixture(d,mode="full")
            self.assertEqual(gate.execute(),17)
            self.assertEqual(gate.calls,["UNCHANGED_FULL_EXECUTE"])
            self.assertFalse((Path(d)/v.PILOT_INTEGRITY_FILE).exists())


class WorkflowBoundaryControls(unittest.TestCase):
    def test_manual_inputs_are_environment_values_and_upload_is_named(self):
        workflow = (policy.REPO/".github/workflows/opica-longrun-verify.yml").read_text()
        self.assertIn('REQUESTED_VERIFY_HEAD: ${{ inputs.verify_head }}',workflow)
        self.assertIn('OPICA_EXECUTION_MODE: ${{ inputs.execution_mode }}',workflow)
        self.assertIn('test "$REQUESTED_VERIFY_HEAD" = "$GITHUB_SHA"',workflow)
        run_indent = None
        for line in workflow.splitlines():
            indent = len(line)-len(line.lstrip())
            if line.strip() == "run: |":
                run_indent = indent
            elif line.strip() and run_indent is not None:
                if indent <= run_indent:
                    run_indent = None
                else:
                    self.assertNotIn("${{ inputs.",line)
        raw = workflow.split("      - name: Preserve the selected long-run receipts even after failure\n",1)[1].split("      - name:",1)[0]
        expected = {"LONGRUN_PREFLIGHT.json","LONGRUN_WORKFLOW_DISPOSITION.json",
                    "verification/MODULAR_GATE_RECEIPT.json","verification/LONGRUN_CONTROLLER_RECEIPT.json",
                    "verification/PILOT_POST_INTEGRITY.json","independent-verification/INDEPENDENT_RECEIPT.json",
                    "LONGRUN_COLLECTION_GUARD.json"}
        actual = {line.strip().removeprefix("${{ env.OPICA_WORK }}/") for line in raw.splitlines()
                  if line.strip().startswith("${{ env.OPICA_WORK }}/")}
        self.assertEqual(actual,expected)
        guard = workflow.index("id: longrun_collection_guard")
        collect = workflow.index("id: original_evidence_collection")
        self.assertLess(guard,collect)
        self.assertIn("steps.longrun_collection_guard.outcome == 'success'",workflow[collect:])


if __name__ == "__main__":
    unittest.main()
