"""Finite controls for the new composition, not a replay of the production97 controls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("matched_runner_controls", HERE / "runner.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
FROZEN = Path(os.environ.get("OPICA_DIAGNOSTIC_TEST_FROZEN_SOURCE", HERE.parents[1]))
for relative in ("opica-step4/modular/verify_modular.py", "opica-step4/portable_gate/verify_combined.py",
                 "opica-step4/portable_gate/GATE_SPEC.json"):
    r.check_file(FROZEN / relative, r.SOURCE_HASHES[relative])
mod = r.load("original_modular_control_only", FROZEN / "opica-step4/modular/verify_modular.py")
observations = r.load("signature_custody_controls", HERE / "observations.py")


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

    def test_committed_profile_refuses_timing_import_schedule_and_authority_drift(self):
        profile = r.read_json(HERE / "PROFILE.json")
        r.check_profile(profile)
        for section, key, value in (("probe", "seconds", 1800),
                                    ("probe", "load_extensions", True),
                                    ("optional_observations", "smaps_snapshot_indices", [0, 2, 16, 100]),
                                    ("trigger", "manual_dispatch", True)):
            changed = copy.deepcopy(profile)
            changed[section][key] = value
            with self.assertRaises(r.Refusal):
                r.check_profile(changed)
        changed = copy.deepcopy(profile)
        changed["proof_acceptance"] = True
        with self.assertRaises(r.Refusal):
            r.check_profile(changed)

    def test_only_selected_successor_push_triggers_diagnostic(self):
        workflow = (HERE.parents[1] / ".github/workflows/opica-matched-phase-diagnostic.yml").read_text()
        trigger = workflow.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
        self.assertEqual(trigger, "  push:\n    branches: [" + r.DIAGNOSTIC_BRANCH + "]\n    paths:\n"
                         "      - .github/workflows/opica-matched-phase-diagnostic.yml\n"
                         "      - diagnostics/opica-matched-phase/**")
        self.assertIn("OPICA_DIAGNOSTIC_PROFILE: '" + r.PROFILE + "'", workflow)
        self.assertIn("LEAN_NUM_THREADS: '2'", workflow)
        self.assertIn("timeout-minutes: 360", workflow)
        for name in ("opica-combined-modular.yml", "opica-import-diagnostic.yml"):
            other = HERE.parents[1] / ".github/workflows" / name
            if other.exists():
                self.assertNotIn(r.DIAGNOSTIC_BRANCH, other.read_text())

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
            "DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]",
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
        for text in (self.log().replace("public import Init, public meta import Init, public import Main", "public import Init, public import Main"),
                     self.log() + "IMPORT_DIAGNOSTIC mono_ms=8000 CORE_END\n",
                     self.log().replace("trustLevel=0", "trustLevel=1")):
            with self.assertRaises(r.Refusal):
                r.phase_markers(text)

    def test_literal_historical_probe_rendering_and_censored_interval(self):
        # Exact retained five-line log from run45022141225, stock_import_split.log,
        # SHA256 41147c8b311b7b2719c55320048083913f8883657aeff626a1684c9fbdda4cb5.
        # This is a historical parser regression, not a new supplier import.
        text = "\n".join([
            "IMPORT_DIAGNOSTIC mono_ms=3981457 DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]",
            "IMPORT_DIAGNOSTIC mono_ms=3981457 NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit",
            "IMPORT_DIAGNOSTIC mono_ms=3981457 CORE_BEGIN",
            "IMPORT_DIAGNOSTIC mono_ms=4534491 CORE_END",
            "IMPORT_DIAGNOSTIC mono_ms=4534492 FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0",
        ]) + "\n"
        result = r.phase_markers(text)
        self.assertEqual(result["core_seconds"], 553.034)
        self.assertIsNone(result["finalize_seconds"])
        self.assertFalse(result["header_and_completion_observed"])
        compact = text.replace(
            "#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]",
            "#[Init, Init, Main, OPICAStep4.NativeValidated, Lean]")
        with self.assertRaises(r.Refusal):
            r.phase_markers(compact)

    def test_literal_round26_probe_timeout_preserves_completed_core_only(self):
        # Exact raw child log from run45043676060; producer parser failed separately.
        text = "\n".join([
            "IMPORT_DIAGNOSTIC mono_ms=5830318 DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]",
            "IMPORT_DIAGNOSTIC mono_ms=5830318 NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit",
            "IMPORT_DIAGNOSTIC mono_ms=5830318 CORE_BEGIN",
            "IMPORT_DIAGNOSTIC mono_ms=6630460 CORE_END",
            "IMPORT_DIAGNOSTIC mono_ms=6630460 FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0",
        ]) + "\n"
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),
                         "0ee6413ccb845c6532fe8efac97fff8cf7138df7e93a0bedec9109de8385f190")
        result = r.phase_markers(text)
        self.assertEqual(result["core_seconds"], 800.142)
        self.assertIsNone(result["finalize_seconds"])
        self.assertFalse(result["header_and_completion_observed"])

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
        row, text = r.observe_import(monitor,
                                     [sys.executable, "-c", "print('TINY_MONITOR_ADAPTER_CONTROL')"],
                                     self.root, dict(os.environ), output)
        self.assertEqual(row["status"], "PASS")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(text.strip(), "TINY_MONITOR_ADAPTER_CONTROL")
        saved = r.read_json(output / (r.PROCESS_NAME + ".process.json"))
        self.assertEqual(saved, row)
        self.assertEqual(saved["timeout_seconds"], 3600)
        args = mod.arguments(r.production_argv(Path("/supplier"), "b" * 40, Path("/work")))
        self.assertEqual(args.compile_timeout, 1800)
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

    def signature_fixture(self, name):
        work = self.root / name
        inputs = work / "inputs"
        inputs.mkdir(parents=True)
        roots = [inputs / ("root" + str(index).zfill(2)) for index in range(13)]
        for index, path in enumerate(roots):
            if index != 1:  # An explicitly empty/missing role remains observable.
                path.mkdir()
        providers = {}
        for module, signature in (("Package/Present", b"tiny-signature"), ("Package/Absent", None)):
            for suffix, value in ((".ir", b"tiny-ir"), (".olean", b"tiny-object")):
                path = roots[2] / (module + suffix)
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(value)
            if signature is not None:
                (roots[2] / (module + ".ir.sig")).write_bytes(signature)
            providers[module] = {key: {"relative": module + suffix,
                                      "sha256": r.digest(roots[2] / (module + suffix))}
                                 for key, suffix in (("ir", ".ir"), ("olean", ".olean"))}
        basis = {"schema": "OPICA_CURRENT_SIGNATURE_PROVIDER_BASIS_V1", "proof_acceptance": False,
                 "limits": dict(observations.SIGNATURE_LIMITS), "actual_import_roots": list(map(str, roots)),
                 "recorded_ir_provider_count": 2,
                 "roots": [{"index": index, "path": str(path), "recorded_inventory_entries": 4 if index == 2 else 0,
                            "providers": providers if index == 2 else {}} for index, path in enumerate(roots)]}
        output = work / "verification/signature-custody"
        output.mkdir(parents=True)
        basis_path = output / "PROVIDER_BASIS.json"
        observations.signature_write_json(basis_path, basis)
        return work, roots, basis_path

    def test_signature_capture_preserves_exact_bytes_absence_and_rejects_drift_or_reuse(self):
        _, roots, basis = self.signature_fixture("capture-positive")
        before = observations.capture_signatures(basis, r.digest(basis), basis.parent / "before", "before")
        after = observations.capture_signatures(basis, r.digest(basis), basis.parent / "after", "after")
        self.assertEqual(before["status"], "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY")
        self.assertEqual(before["roots"][1]["enumeration"], "COMPLETE_ABSENT_ROOT")
        self.assertEqual(before["roots"][2]["providers"]["Package/Absent"]["status"], "ABSENT_SIGNATURE")
        self.assertEqual(observations.compare_signature_captures(before, after)["status"],
                         "CURRENT_SIGNATURE_BYTES_AND_PROVIDER_IDENTITIES_STABLE")
        with zipfile.ZipFile(basis.parent / "before/signatures.zip") as archive:
            self.assertEqual(archive.namelist(), ["signatures/00000.bin"])
            self.assertEqual(archive.read(archive.namelist()[0]), b"tiny-signature")
        with self.assertRaises(observations.InputFailure):
            observations.capture_signatures(basis, r.digest(basis), basis.parent / "before", "before")
        (roots[2] / "Package/Present.ir.sig").write_bytes(b"changed-signature")
        drift = observations.capture_signatures(basis, r.digest(basis), basis.parent / "drift", "after")
        with self.assertRaises(observations.InputFailure):
            observations.compare_signature_captures(before, drift)

    def test_signature_capture_refuses_orphan_symlink_nonregular_and_size_gaps(self):
        for fault in ("orphan", "symlink", "nonregular", "oversize", "enumeration_error"):
            with self.subTest(fault=fault):
                _, roots, basis = self.signature_fixture("capture-" + fault)
                signature = roots[2] / "Package/Present.ir.sig"
                if fault == "orphan":
                    (roots[0] / "Unknown.ir.sig").write_bytes(b"orphan")
                elif fault == "symlink":
                    signature.unlink()
                    signature.symlink_to(roots[2] / "Package/Present.ir")
                elif fault == "nonregular":
                    signature.unlink()
                    os.mkfifo(signature)
                elif fault == "oversize":
                    with signature.open("wb") as stream:
                        stream.truncate(observations.SIGNATURE_LIMITS["signature_bytes"] + 1)
                if fault == "enumeration_error":
                    with mock.patch.object(observations.os, "scandir", side_effect=PermissionError("tiny enumeration denial")):
                        result = observations.capture_signatures(basis, r.digest(basis), basis.parent / "before", "before")
                else:
                    result = observations.capture_signatures(basis, r.digest(basis), basis.parent / "before", "before")
                self.assertEqual(result["status"], "SIGNATURE_CAPTURE_FAILED_OR_INCOMPLETE")
                self.assertFalse(result["proof_acceptance"])
                self.assertFalse((basis.parent / "before/signatures.zip").exists())

    def test_signature_root_ancestor_basis_and_archive_caps_fail_closed(self):
        work, roots, basis = self.signature_fixture("capture-ancestor")
        (work / "alias").symlink_to(work / "inputs", target_is_directory=True)
        changed = observations.signature_read_json(basis)
        changed["roots"][2]["path"] = str(work / "alias/root02")
        changed["actual_import_roots"][2] = changed["roots"][2]["path"]
        observations.signature_write_json(basis, changed)
        bad = observations.capture_signatures(basis, r.digest(basis), basis.parent / "before", "before")
        self.assertEqual(bad["status"], "SIGNATURE_CAPTURE_FAILED_OR_INCOMPLETE")
        changed["roots"] = changed["roots"][:-1]
        with self.assertRaises(observations.InputFailure):
            observations.validate_signature_basis(changed)
        _, _, capped = self.signature_fixture("capture-archive-cap")
        with mock.patch.dict(observations.SIGNATURE_LIMITS, {"archive_bytes": 32}):
            changed = observations.signature_read_json(capped)
            changed["limits"] = dict(observations.SIGNATURE_LIMITS)
            observations.signature_write_json(capped, changed)
            bad = observations.capture_signatures(capped, r.digest(capped), capped.parent / "before", "before")
            self.assertEqual(bad["status"], "SIGNATURE_CAPTURE_FAILED_OR_INCOMPLETE")
            self.assertLessEqual((capped.parent / "before/signatures.partial.zip").stat().st_size, 32)

    def test_real_signature_subprocess_and_original_collector_retain_only_bounded_products(self):
        work, _, basis = self.signature_fixture("capture-real-process")
        monitor = r.load("real_monitor_for_signature_fixture", FROZEN / "opica-step4/modular/monitored_process.py")
        gate = SimpleNamespace(sources=work, env=dict(os.environ))
        before = r.capture_signature_process(monitor, observations, gate, basis, "before")
        self.assertEqual(before["process"]["status"], "PASS")
        self.assertEqual(before["status"], "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY")
        self.assertEqual(before["process"]["timeout_seconds"], 300)
        self.assertEqual(before["process"]["rss_plus_swap_limit_bytes"], 1024 << 20)
        self.assertEqual(before["process"]["log_limit_bytes"], 8 << 20)
        self.assertEqual(before["address_space_limits_bytes"], [1 << 30, 1 << 30])
        self.assertEqual(before["process"]["cleanup"]["status"], "PASS")
        collected = subprocess.run([sys.executable, str(FROZEN / "opica-step4/collect_evidence.py"),
                                    "--work", str(work), "--head", "a" * 40],
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(collected.returncode, 0, collected.stderr)
        with zipfile.ZipFile(work / "evidence.zip") as archive:
            names = set(archive.namelist())
            self.assertIn("verification/signature-custody/PROVIDER_BASIS.json", names)
            self.assertIn("verification/signature-custody/before/CAPTURE.json", names)
            self.assertIn("verification/signature-custody/before/signatures.zip", names)
            self.assertFalse(any(name.endswith(".ir.sig") for name in names))
            self.assertFalse(any("partial.zip" in name for name in names))

    def test_actual_run_finalizes_after_precapture_postcapture_parser_and_optional_failures(self):
        baseline = r.read_json(HERE / "ROUND25_BASELINE.json")
        for fault in ("before", "after", "parser_and_optional", "initial_result_write"):
            with self.subTest(fault=fault):
                work = self.root / ("lifecycle-" + fault)
                build = work / "phase-probe-build"
                build.mkdir(parents=True)
                (build / "import_phase_probe").write_bytes(b"tiny-generated-probe")
                source = {"fixture": "source-identity-only"}
                prepared = {"status": "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY", "source_binding": source,
                            "files": {"import_phase_probe": {"sha256": r.digest(build / "import_phase_probe"),
                                                              "bytes": (build / "import_phase_probe").stat().st_size}}}
                r.write_json(build / "PROBE_BUILD.json", prepared)
                resource = work / "loop-dio-resource"
                resource.mkdir()
                (resource / "INITIAL.json").write_text("{}\n")
                final_calls, capture_calls = [], []
                gate = SimpleNamespace(output=work / "verification", sources=work,
                                       env={"LEAN_PATH": os.pathsep.join(baseline["identity_projection"]["environment"]["import_roots"])},
                                       lib=Path(baseline["identity_projection"]["environment"]["import_roots"][0]),
                                       canonical_lib=work / "no-theorem-output", save=lambda: None)
                gate.receipt = {"environment": copy.deepcopy(baseline["identity_projection"]["environment"]),
                                "stages": [{"name": name, "status": "PASS" if i < 19 else "NOT_RUN"}
                                           for i, name in enumerate(mod.STAGES)]}
                def rehash():
                    final_calls.append("original-final-rehash")
                    return {"fixture": "literal-final-result"}
                gate.final_integrity = rehash
                def construct(_):
                    gate.output.mkdir()
                    return gate
                sampler = SimpleNamespace(thread=SimpleNamespace(start=lambda: None), finish=lambda: {"status": "tiny-finish"})
                host_calls = []
                def host():
                    host_calls.append(1)
                    if fault == "parser_and_optional" and len(host_calls) > 1:
                        raise OSError("tiny HOST_AFTER failure")
                    return {"fixture": "host"}
                if fault == "parser_and_optional":
                    def finish_error():
                        raise RuntimeError("tiny sampler finish failure")
                    sampler.finish = finish_error
                fake_observations = SimpleNamespace(signature_write_json=observations.signature_write_json,
                    host_details=host, SupplementalSampler=lambda *unused: sampler,
                    signature_read_json=lambda *unused: {},
                    compare_signature_captures=lambda *unused: {"status": "CURRENT_SIGNATURE_BYTES_AND_PROVIDER_IDENTITIES_STABLE"})
                child = {"status": "INCOMPLETE", "failure_kind": "TIMEOUT", "exit_code": None,
                         "elapsed_seconds": 3600.01, "cleanup": {"status": "PASS"}, "fixture": "literal-child-row"}
                def capture(_monitor, _observations, _gate, _basis, phase):
                    capture_calls.append(phase)
                    if phase == "after":
                        saved = r.read_json(gate.output / "MATCHED_PHASE_RESULT.json")
                        self.assertEqual(saved["observation"], "NOT_RUN" if fault == "initial_result_write" else child)
                    if fault == phase:
                        raise r.Refusal("tiny " + phase + " capture failure")
                    return {"process": {"status": "PASS"}, "status": "CAPTURED_CURRENT_SIGNATURE_BYTES_ONLY",
                            "receipt_path": str(work / (phase + ".json")), "receipt_sha256": "0" * 64}
                def loaded(name, _path):
                    if name == "matched_observations":
                        return fake_observations
                    return SimpleNamespace(arguments=lambda _argv: None)
                args = SimpleNamespace(work=work, supplier=self.root, head="b" * 40)
                original_write = r.write_json
                write_faults = []
                def save_result(path, value):
                    if fault == "initial_result_write" and Path(path).name == "MATCHED_PHASE_RESULT.json" and \
                            value.get("status") == "OBSERVING_NONACCEPTING_IMPORT" and not write_faults:
                        write_faults.append("before-monitor")
                        raise OSError("tiny initial observing-result write failure")
                    return original_write(path, value)
                with mock.patch.object(r, "load", side_effect=loaded), \
                     mock.patch.object(r, "diagnostic_class", return_value=construct), \
                     mock.patch.object(r, "run_prefix"), \
                     mock.patch.object(r, "identity_projection", return_value=baseline["identity_projection"]), \
                     mock.patch.object(r, "signature_basis", return_value={"fixture": "bounded-provider-basis"}), \
                     mock.patch.object(r, "resource_before", return_value={"initial_sha256": r.digest(resource / "INITIAL.json")}), \
                     mock.patch.object(r, "authenticate", return_value=source), \
                     mock.patch.object(r, "capture_signature_process", side_effect=capture), \
                     mock.patch.object(r, "write_json", side_effect=save_result), \
                     mock.patch.object(r, "observe_import", return_value=(child, "malformed" if fault == "parser_and_optional" else self.log(False))) as launched:
                    self.assertEqual(r.run(args, source), 2)
                result = r.read_json(gate.output / "MATCHED_PHASE_RESULT.json")
                self.assertEqual(final_calls, ["original-final-rehash"])
                self.assertEqual(result["post_integrity"]["status"], "DIAGNOSTIC_INPUT_REHASH_PASSED")
                self.assertFalse(result["proof_acceptance"])
                if fault in ("before", "initial_result_write"):
                    launched.assert_not_called()
                    self.assertEqual(capture_calls, ["before"] if fault == "before" else ["before", "after"])
                    self.assertEqual(result["observation"], "NOT_RUN")
                    self.assertFalse(result["probe_launch_attempted"])
                    if fault == "initial_result_write":
                        self.assertTrue(result["signature_custody"]["after_attempted"])
                        self.assertEqual(write_faults, ["before-monitor"])
                else:
                    launched.assert_called_once()
                    self.assertEqual(capture_calls, ["before", "after"])
                    self.assertTrue(result["signature_custody"]["after_attempted"])
                    self.assertEqual(result["observation"], child)
                if fault == "parser_and_optional":
                    self.assertIn("Unexpected diagnostic log line", result["error"])
                    self.assertEqual({row["context"] for row in result["auxiliary_failures"]},
                                     {"optional_sampler_finish", "host_after_preservation"})


if __name__ == "__main__":
    unittest.main()
