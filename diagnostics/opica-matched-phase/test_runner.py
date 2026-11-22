"""Finite controls for the new composition, not a replay of the production97 controls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("matched_runner_controls", HERE / "runner.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
FROZEN = Path(os.environ.get("OPICA_DIAGNOSTIC_TEST_FROZEN_SOURCE", HERE.parents[1]))
for relative in ("opica-step4/modular/verify_modular.py", "opica-step4/portable_gate/verify_combined.py",
                 "opica-step4/portable_gate/GATE_SPEC.json"):
    r.check_file(FROZEN / relative, r.SOURCE_HASHES[relative])
mod = r.load("original_modular_control_only", FROZEN / "opica-step4/modular/verify_modular.py")


class TinyOriginal:
    """Only a test double for exercising ordering/delegation without any proof input."""
    def __init__(self, args):
        self.output = args.output
        self.output.mkdir()
        self._modular_ready = False
        self.receipt = {"schema": "TEST_LEGACY_CONTEXT", "status": "RUNNING", "claim": "NOT_ESTABLISHED",
                        "stages": [{"name": name, "status": "NOT_RUN"} for name in mod.STAGES]}
        self.seen = []
        self.save()
        self._modular_ready = True
        self.receipt["schema"] = "TEST_MODULAR_CONTEXT"
        self.save()

    def stage(self, name, action):
        row = next(row for row in self.receipt["stages"] if row["name"] == name)
        row["status"] = "RUNNING"
        self.save()
        row["details"] = action()
        row["status"] = "PASS"
        r.write_json(self.output / (name + ".json"), row)
        self.save()


def tiny_action(name):
    def action(self):
        self.seen.append(name)
        return {"literal_test_action": name}
    return action


for _name in mod.STAGES:
    setattr(TinyOriginal, _name, tiny_action(_name))
tiny_mod = SimpleNamespace(ModularGate=TinyOriginal, STAGES=mod.STAGES)


class MatchedDiagnosticControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def real_gate(self):
        supplier, work = self.root / "supplier", self.root / "work"
        supplier.mkdir()
        (work / "native/integration").mkdir(parents=True)
        (work / "native/native-source").mkdir()
        args = mod.arguments(r.production_argv(supplier, "a" * 40, work))
        return r.diagnostic_class(mod)(args)

    def tiny_gate(self):
        return r.diagnostic_class(tiny_mod)(SimpleNamespace(output=self.root / "tiny"))

    def test_real_initializer_never_writes_production_receipt(self):
        gate = self.real_gate()
        self.assertEqual(gate.receipt["schema"], mod.GATE_VERSION)
        self.assertEqual(gate.receipt["status"], "RUNNING")
        saved = r.read_json(gate.output / "DIAGNOSTIC_PRELUDE_STATE.json")
        self.assertEqual(saved["schema"], "OPICA_DIAGNOSTIC_PRELUDE_STATE_V1")
        self.assertFalse(saved["proof_acceptance"])
        self.assertEqual(len(saved["stages"]), 19)
        self.assertEqual(len(saved["unexecuted_original_stage_states"]), 11)
        self.assertTrue(all(not (gate.output / name).exists() for name in r.FORBIDDEN_RECEIPTS))

    def test_save_does_not_mutate_original_context_or_spec(self):
        gate = self.real_gate()
        receipt, spec = copy.deepcopy(gate.receipt), copy.deepcopy(gate.spec)
        gate.save()
        self.assertEqual(gate.receipt, receipt)
        self.assertEqual(gate.spec, spec)

    def test_real_first_stage_failure_is_literal_and_terminal(self):
        gate = self.real_gate()
        # The empty fixture is intentionally not a repository: the unchanged
        # source_identity action must fail before a compiler or object is touched.
        with self.assertRaises(mod.GateFailure):
            r.run_prefix(gate)
        raw = r.read_json(gate.output / "source_identity.json")
        self.assertEqual(raw, gate.receipt["stages"][0])
        self.assertEqual(raw["status"], "BLOCKED")
        state = r.read_json(gate.output / "DIAGNOSTIC_PRELUDE_STATE.json")
        self.assertEqual(state["status"], "PREFIX_FAILED_OR_INCOMPLETE")
        self.assertTrue(all(row["status"] == "NOT_RUN" for row in gate.receipt["stages"][1:]))
        self.assertFalse((gate.output / "MODULAR_GATE_RECEIPT.json").exists())

    def test_exact19_delegation_has_no_stage20(self):
        gate = self.tiny_gate()
        r.run_prefix(gate)
        self.assertEqual(gate.seen, list(r.PREFIX))
        self.assertEqual(gate.diagnostic_calls, list(r.PREFIX))
        self.assertEqual(gate.receipt["status"], "RUNNING")
        self.assertTrue(all(row["status"] == "NOT_RUN" for row in gate.receipt["stages"][19:]))
        with self.assertRaises(r.Refusal):
            gate.stage("guarded_kernel_import", gate.guarded_kernel_import)
        self.assertEqual(gate.seen, list(r.PREFIX))

    def test_wrong_order_and_substituted_action_refused(self):
        gate = self.tiny_gate()
        with self.assertRaises(r.Refusal):
            gate.stage(r.PREFIX[1], getattr(gate, r.PREFIX[1]))
        with self.assertRaises(r.Refusal):
            gate.stage(r.PREFIX[0], lambda: {"status": "PASS"})
        self.assertEqual(gate.seen, [])
        self.assertEqual(gate.diagnostic_calls, [])

    def test_full_execute_refused_before_any_action(self):
        gate = self.real_gate()
        with self.assertRaises(r.Refusal):
            gate.execute()
        self.assertTrue(all(row["status"] == "NOT_RUN" for row in gate.receipt["stages"]))

    def test_original_parser_defaults_and_production_budgets(self):
        args = mod.arguments(r.production_argv(Path("/supplier"), "b" * 40, Path("/work")))
        self.assertEqual((args.jobs, args.compile_timeout, args.fresh_timeout, args.export_timeout,
                          args.replay_timeout, args.comparison_timeout, args.max_heartbeats),
                         (2, 1800, 7200, 7200, 3600, 7200, 1600000))
        self.assertIsNone(args.comparator_lake)
        self.assertIsNone(args.native_receipt)
        self.assertIsNone(args.exporter_source)

    def test_missing_tampered_and_wrong_size_inputs_refused(self):
        path = self.root / "input"
        with self.assertRaises(r.Refusal):
            r.check_file(path, "0" * 64)
        path.write_bytes(b"exact")
        wanted = r.digest(path)
        r.check_file(path, wanted, 5)
        with self.assertRaises(r.Refusal):
            r.check_file(path, wanted, 6)
        path.write_bytes(b"drift")
        with self.assertRaises(r.Refusal):
            r.check_file(path, wanted, 5)

    def test_symlink_file_and_parent_refused(self):
        actual = self.root / "actual"
        actual.mkdir()
        (actual / "input").write_bytes(b"x")
        (self.root / "link").symlink_to(actual, target_is_directory=True)
        (self.root / "file").symlink_to(actual / "input")
        for path in (self.root / "link/input", self.root / "file"):
            with self.assertRaises(r.Refusal):
                r.regular(path)

    def test_deselection_and_loader_injection_refused(self):
        for selection in ("none", "", "almost-" + r.PROFILE):
            with self.assertRaises(r.Refusal):
                r.check_selection(selection)
        r.check_selection(r.PROFILE)
        for key in ("LD_PRELOAD", "LD_AUDIT", "LEAN_PATH"):
            with self.assertRaises(r.Refusal):
                r.reject_overrides({key: "/unreviewed"})

    def test_recorded_identity_matches_but_object_export_and_root_drift_do_not(self):
        baseline = r.read_json(HERE / "ROUND25_BASELINE.json")["identity_projection"]
        self.assertFalse(r.compare_identity(baseline, baseline)["mismatched_fields"])
        for key in ("complete_snapshot", "native_validated_inputs_sha256", "promoted_canonical_artifacts", "exports", "environment"):
            changed = copy.deepcopy(baseline)
            changed[key] = {"substituted": True}
            result = r.compare_identity(changed, baseline)
            self.assertEqual(result["mismatched_fields"], [key])
            self.assertFalse(result["proof_rejection"])
            self.assertFalse(result["proof_acceptance"])

    def log(self, complete=True):
        messages = [
            "DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[Init, Init, Main, OPICAStep4.NativeValidated, Lean]",
            "NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit",
            "CORE_BEGIN", "CORE_END", "FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0"]
        if complete:
            messages += ["FINALIZE_END", "HEADER_MATCH modules=177508", "DIAGNOSTIC_COMPLETE no_proof_validity_established"]
        return "\n".join("IMPORT_DIAGNOSTIC mono_ms=" + str(1000 * i) + " " + message for i, message in enumerate(messages)) + "\n"

    def test_exact_complete_markers_and_literal_intervals(self):
        result = r.phase_markers(self.log())
        self.assertTrue(result["header_and_completion_observed"])
        self.assertEqual(result["core_seconds"], 1)
        self.assertEqual(result["finalize_seconds"], 1)

    def test_timeout_markers_do_not_invent_finalization(self):
        result = r.phase_markers(self.log(False))
        self.assertFalse(result["header_and_completion_observed"])
        self.assertEqual(result["core_seconds"], 1)
        self.assertIsNone(result["finalize_seconds"])
        empty = r.phase_markers("")
        self.assertIsNone(empty["core_seconds"])
        self.assertIsNone(empty["finalize_seconds"])

    def test_changed_import_order_duplicate_and_unknown_markers_rejected(self):
        for text in (self.log().replace("Init, Init, Main", "Init, Main"),
                     self.log() + "IMPORT_DIAGNOSTIC mono_ms=8000 CORE_END\n",
                     self.log().replace("trustLevel=0", "trustLevel=1")):
            with self.assertRaises(r.Refusal):
                r.phase_markers(text)

    def test_changed_original_route_rejected(self):
        changed = SimpleNamespace(ModularGate=TinyOriginal, STAGES=("different", *mod.STAGES[1:]))
        with self.assertRaises(r.Refusal):
            r.diagnostic_class(changed)

    def test_resource_chain_and_effective_dio_required(self):
        baseline = r.read_json(HERE / "ROUND25_BASELINE.json")
        root = self.root / "loop-dio-resource"
        root.mkdir()
        manifest = self.root / "proof-store.sqfs.files.sha256"
        manifest.write_text("tiny fixture; no real store supplied\n")
        baseline["resource"]["mounted_manifest_sha256"] = r.digest(manifest)
        identity = {"loop": copy.deepcopy(baseline["resource"]["loop"]),
                    "decompressor_mode": {"value": "single"}}
        setup = {"status": "READY_FOR_ORIGINAL_FILE_VERIFICATION_NOT_BOUND", "requested_head": "a" * 40,
                 "selected_profile": r.RESOURCE_PROFILE, "source_hashes": {"fixture": "b" * 64},
                 "mounted": identity, "image_authentication": {"sha256": baseline["resource"]["image_sha256"],
                                                             "bytes_read": baseline["resource"]["image_bytes"]}}
        r.write_json(root / "SETUP_RESULT.json", setup)
        initial = {"status": "INITIAL_RESOURCE_IDENTITY_BOUND", "requested_head": "a" * 40,
                   "selected_profile": r.RESOURCE_PROFILE, "source_hashes": setup["source_hashes"],
                   "identity": identity, "setup_sha256": r.digest(root / "SETUP_RESULT.json"), "context": {}}
        r.write_json(root / "INITIAL.json", initial)
        r.write_json(self.root / "mounted-store-verified.json", {"status": "PASS", "files": 350374,
                                                                "manifest_sha256": r.digest(manifest)})
        r.resource_before(self.root, "a" * 40, baseline)
        initial["setup_sha256"] = "0" * 64
        r.write_json(root / "INITIAL.json", initial)
        with self.assertRaises(r.Refusal):
            r.resource_before(self.root, "a" * 40, baseline)
        identity["loop"]["dio"] = 0
        r.write_json(root / "SETUP_RESULT.json", setup)
        initial["setup_sha256"] = r.digest(root / "SETUP_RESULT.json")
        r.write_json(root / "INITIAL.json", initial)
        with self.assertRaises(r.Refusal):
            r.resource_before(self.root, "a" * 40, baseline)

    def test_real_frozen_monitor_adapter_keyword_and_tuple_contract(self):
        path = FROZEN / "opica-step4/modular/monitored_process.py"
        r.check_file(path, r.SOURCE_HASHES["opica-step4/modular/monitored_process.py"])
        monitor = r.load("actual_monitor_for_tiny_child", path)
        output = self.root / "tiny-monitor"
        output.mkdir()
        row, text = r.monitored(monitor, "tiny_adapter_child",
                                [sys.executable, "-c", "print('TINY_MONITOR_ADAPTER_CONTROL')"],
                                self.root, dict(os.environ), output, 10)
        self.assertEqual(row["status"], "PASS")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(text.strip(), "TINY_MONITOR_ADAPTER_CONTROL")
        saved = r.read_json(output / "tiny_adapter_child.process.json")
        self.assertEqual(saved, row)
        self.assertEqual(saved["timeout_seconds"], 10)
        self.assertEqual(saved["rss_plus_swap_limit_bytes"], 50000 << 20)
        self.assertEqual(saved["log_limit_bytes"], 64 << 20)
        self.assertEqual(saved["cleanup"]["status"], "PASS")

    def test_generated_probe_custody_preserves_bytes_and_rejects_drift(self):
        build = self.root / "build"
        build.mkdir()
        names = ("import_phase_probe", "ImportPhaseProbe.olean")
        for name in names:
            (build / name).write_bytes(("tiny generated fixture " + name).encode())
        prepared = {"status": "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY",
                    "files": {name: {"sha256": r.digest(build / name), "bytes": (build / name).stat().st_size} for name in names}}
        r.write_json(build / "PROBE_BUILD.json", prepared)
        result = r.retain_probe_products(build, self.root / "custody")
        self.assertEqual(result["status"], "COMPLETE_GENERATED_PROBE_CUSTODY_ONLY")
        self.assertFalse(result["proof_acceptance"])
        for name in names:
            self.assertEqual((self.root / "custody" / name).read_bytes(), (build / name).read_bytes())
        with self.assertRaises(r.Refusal):
            r.retain_probe_products(build, self.root / "custody")
        (build / names[0]).write_bytes(b"drifted generated executable")
        result = r.retain_probe_products(build, self.root / "drifted-custody")
        self.assertEqual(result["status"], "INCOMPLETE_GENERATED_PROBE_CUSTODY")
        self.assertEqual(result["files"][0]["status"], "MISSING_OVERSIZE_DRIFTED_OR_UNREADABLE")
        self.assertFalse((self.root / "drifted-custody" / names[0]).exists())

    def test_generated_probe_custody_refuses_missing_and_oversize(self):
        missing = r.retain_probe_products(self.root / "absent", self.root / "missing-custody")
        self.assertEqual(missing["status"], "INCOMPLETE_GENERATED_PROBE_CUSTODY")
        build = self.root / "oversize"
        build.mkdir()
        with (build / "import_phase_probe").open("wb") as stream:
            stream.truncate((150 << 20) + 1)
        (build / "ImportPhaseProbe.olean").write_bytes(b"tiny")
        r.write_json(build / "PROBE_BUILD.json", {"status": "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY", "files": {
            "import_phase_probe": {"sha256": "0" * 64, "bytes": (150 << 20) + 1},
            "ImportPhaseProbe.olean": {"sha256": r.digest(build / "ImportPhaseProbe.olean"), "bytes": 4}}})
        result = r.retain_probe_products(build, self.root / "oversize-custody")
        self.assertEqual(result["status"], "INCOMPLETE_GENERATED_PROBE_CUSTODY")
        self.assertIn("size bound", result["files"][0]["error"])
        self.assertFalse((self.root / "oversize-custody/import_phase_probe").exists())


if __name__ == "__main__":
    unittest.main()
