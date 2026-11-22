#!/usr/bin/env python3
"""Nonaccepting, exact-prefix stock import observation. No production gate executes."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE_HEAD = "51a2aab2566ed9736f6c4fcddbcfeea74d90e09d"
BASE_TREE = "412fec33b3869f438d1c71928cce32be72b636d0"
BASE_MANIFEST_SHA = "09b5ab945355ffd891b8786978fff43fc64b85eb586f03dfc75bb129cb825aee"
PROFILE = "ROUND26_MATCHED_PREFIX_SPLIT1800_DIO1_SINGLE_V1"
RESOURCE_PROFILE = "LOOP_RO_DIO1_ORIGINAL64K_V1"
PROCESS_NAME = "matched_stock_import_split"
PREFIX = (
    "source_identity", "external_validation_evidence", "external_endpoint_presence",
    "immutable_supplier_store", "canonical_environment", "verification_tools",
    "native_build_receipt", "native_source_policy", "canonical_dependency_snapshot",
    "canonical_modules_compile", "canonical_type_and_axiom_audit",
    "canonical_fingerprint_export", "canonical_native_proof_export",
    "complete_native_fresh_kernel_replay", "comparison_controls", "compatible_environment",
    "shared_dependency_comparison", "complete_object_snapshot", "canonical_objects_promotion",
)
OVERRIDES = ("LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
             "DYLD_LIBRARY_PATH", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
             "LAKE_CONFIG", "ELAN_TOOLCHAIN", "LEAN_PLUGIN_PATH")
RESOURCE_KEYS = ("PATH", "LD_LIBRARY_PATH", "LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
                 "LEAN_NUM_THREADS", "LEAN_ABORT_ON_PANIC")
FORBIDDEN_RECEIPTS = ("MODULAR_GATE_RECEIPT.json", "COMBINED_GATE_RECEIPT.json")
SOURCE_HASHES = {
    "opica-step4/modular/verify_modular.py": "7953a9d18c63c6567595533b9028a6f176599fe1fbca65c0f84773e1211267b9",
    "opica-step4/modular/monitored_process.py": "37cc7e705d660745bc0a6b2dc556a38761c1460c6e7e30fd9597ccae40ca0709",
    "opica-step4/portable_gate/verify_combined.py": "a01ac482dd59444b2313dc525b63d22036de892a3076a23a06c80514d7df78ca",
    "opica-step4/portable_gate/GATE_SPEC.json": "771b194e8330a6844705178a5bc4cfc09ece629c9a2c88031e1bb74615640862",
    "opica-step4/native_bootstrap/bootstrap_native.py": "1a9e8c7643bf122c7b855433f47460462501ac1ecefaefe54c6b459ea7443b66",
    "opica-step4/native_bootstrap/runtime_files.json": "550bbf7a1fc8e2549ecf2d122ff5bfa2007f71d78e3ce1dba42d02fb1ae72793",
    "opica-step4/independent/verify_independent.py": "cceb0b3467675dd87e761ec668f0ffc54f89adf2ca2360cc57d6c41e4319687a",
}


class Refusal(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def regular(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Missing/symlink file: " + str(path))
    require(path.absolute() == path.resolve(), "Symlink ancestor or noncanonical path: " + str(path))
    return path


def read_json(path):
    data = json.loads(regular(path).read_text())
    require(isinstance(data, dict), "JSON object required: " + str(path))
    return data


def check_file(path, expected, size=None):
    path = regular(path)
    require(digest(path) == expected and (size is None or path.stat().st_size == size),
            "Required byte identity differs: " + str(path))


def write_json(path, value):
    path = Path(path)
    require(path.parent.is_dir() and path.parent.absolute() == path.parent.resolve(),
            "Unsafe diagnostic output directory")
    require(not path.is_symlink(), "Refuse symlink output")
    pending = path.with_suffix(path.suffix + ".tmp")
    with pending.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    pending.replace(path)


def inspect(argv, cwd):
    row = subprocess.run(list(map(str, argv)), cwd=cwd, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    require(row.returncode == 0, "Inspection failed: " + repr(argv) + "\n" + row.stderr[-2000:])
    return row.stdout.strip()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_selection(selection):
    require(selection == PROFILE, "DIAGNOSTIC_NOT_SELECTED: refuse before preparation")


def reject_overrides(env):
    require(not [key for key in OVERRIDES if env.get(key)], "Inherited loader/import override is forbidden")


def authenticate(supplier, head):
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "Exact full head is required")
    git = lambda *args: inspect(["git", "-C", supplier, *args], supplier)
    require(git("rev-parse", "HEAD") == head, "Checkout differs from exact requested head")
    require(git("rev-parse", BASE_HEAD + "^{tree}") == BASE_TREE, "Round25 base tree differs")
    git("merge-base", "--is-ancestor", BASE_HEAD, "HEAD")
    require(not git("status", "--porcelain", "--untracked-files=no"), "Tracked checkout changed")
    manifest = read_json(HERE / "SOURCE_MANIFEST.json")
    require(manifest["base_head"] == BASE_HEAD and manifest["base_tree"] == BASE_TREE,
            "Diagnostic manifest base differs")
    paths = [row["path"] for row in manifest["files"]]
    self_path = "diagnostics/opica-matched-phase/SOURCE_MANIFEST.json"
    require(len(paths) == len(set(paths)) and self_path not in paths, "Invalid diagnostic inventory")
    allowed = set(paths) | {self_path}
    changes = [line.split("\t") for line in git("diff", "--name-status", BASE_HEAD, "HEAD").splitlines()]
    require(all(len(row) == 2 and row[0] == "A" for row in changes), "Existing source changed")
    require({row[1] for row in changes} == allowed, "Added-file scope differs from diagnostic inventory")
    require(all(p.startswith("diagnostics/opica-matched-phase/") or
                p == ".github/workflows/opica-matched-phase-diagnostic.yml" for p in allowed),
            "Diagnostic files must remain outside original bundle")
    bound = {}
    for row in manifest["files"]:
        check_file(supplier / row["path"], row["sha256"], row["bytes"])
        bound[row["path"]] = row["sha256"]
    source_manifest = regular(supplier / "opica-step4/SOURCE_MANIFEST.json")
    require(digest(source_manifest) == BASE_MANIFEST_SHA, "Original source manifest changed")
    original = read_json(source_manifest)
    for row in original["files"]:
        check_file(supplier / "opica-step4" / row["path"], row["sha256"], row["bytes"])
        bound["opica-step4/" + row["path"]] = row["sha256"]
    workflow = regular(supplier / ".github/workflows/opica-combined-modular.yml")
    require(digest(workflow) == original["workflow_sha256"], "Original full workflow changed")
    for relative, expected in SOURCE_HASHES.items():
        check_file(supplier / relative, expected)
    bound.update({"opica-step4/SOURCE_MANIFEST.json": BASE_MANIFEST_SHA,
                  ".github/workflows/opica-combined-modular.yml": digest(workflow),
                  self_path: digest(HERE / "SOURCE_MANIFEST.json")})
    return {"head": head, "tree": git("rev-parse", "HEAD^{tree}"), "base_head": BASE_HEAD,
            "base_tree": BASE_TREE, "sources": bound, "tracked_source_clean": True}


def production_argv(supplier, head, work):
    return ["--external", str(supplier), "--external-head", head,
            "--external-lib", str(work / "proof-store"), "--native", str(work / "native/native-source"),
            "--integration", str(work / "native/integration"),
            "--lake", str(work / "native/lean-4.33.1-linux/bin/lake"),
            "--exporter", str(work / "exporter/.lake/build/bin/lean4export"),
            "--comparison-helper", str(supplier / "opica-step4/portable_gate/comparison_control/.lake/build/bin/compare_exports"),
            "--external-evidence", str(supplier / "opica-step4/modular/external-evidence"),
            "--output", str(work / "verification"), "--jobs", "2", "--compile-timeout", "1800",
            "--fresh-timeout", "7200", "--export-timeout", "7200", "--replay-timeout", "3600"]


def diagnostic_class(mod):
    require(tuple(mod.STAGES[:19]) == PREFIX and len(mod.STAGES) == 30, "Original stage route changed")

    class DiagnosticPrelude(mod.ModularGate):
        def __init__(self, args):
            self.diagnostic_state = "INITIALIZING"
            self.diagnostic_calls = []
            self.diagnostic_failure = None
            super().__init__(args)
            self.diagnostic_state = "RUNNING_PRELUDE"
            self.save()

        def save(self):
            # The base constructor dynamically calls save before modular initialization.
            if not getattr(self, "_modular_ready", False):
                return
            state = copy.deepcopy(self.receipt)
            state["original_context_schema"] = state.pop("schema")
            state["original_context_status"] = state.pop("status")
            state["unexecuted_original_stage_states"] = state["stages"][19:]
            state["stages"] = state["stages"][:19]
            state.update(schema="OPICA_DIAGNOSTIC_PRELUDE_STATE_V1", status=self.diagnostic_state,
                         proof_acceptance=False, diagnostic_only=True,
                         production_gate="NOT_RUN; no stage20 or subsequent proof/claim stage",
                         diagnostic_calls=list(self.diagnostic_calls), diagnostic_failure=self.diagnostic_failure)
            write_json(self.output / "DIAGNOSTIC_PRELUDE_STATE.json", state)

        def stage(self, name, action):
            index = len(self.diagnostic_calls)
            require(index < len(PREFIX) and name == PREFIX[index], "Only exact first19 order is permitted")
            require(getattr(action, "__self__", None) is self and
                    getattr(action, "__func__", None) is getattr(mod.ModularGate, name),
                    "Stage action must be the unchanged original method")
            self.diagnostic_calls.append(name)
            return super().stage(name, action)

        def execute(self):
            raise Refusal("Production execute() is forbidden in a diagnostic")

    return DiagnosticPrelude


def run_prefix(gate):
    try:
        for name in PREFIX:
            gate.stage(name, getattr(gate, name))
        require(all(row["status"] == "PASS" for row in gate.receipt["stages"][:19]), "Prefix is incomplete")
        require(all(row["status"] == "NOT_RUN" for row in gate.receipt["stages"][19:]), "A proof stage ran")
        gate.diagnostic_state = "PREFIX_COMPLETED_NO_PROOF_ACCEPTANCE"
    except BaseException as exc:
        gate.diagnostic_state = "PREFIX_INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "PREFIX_FAILED_OR_INCOMPLETE"
        gate.diagnostic_failure = {"error_type": type(exc).__name__, "error": str(exc)}
        raise
    finally:
        gate.save()


def identity_projection(receipt):
    details = {row["name"]: row.get("details", {}) for row in receipt["stages"]}
    source = receipt["source_binding"]
    exports = {}
    for name in ("canonical_fingerprint_export", "canonical_native_proof_export"):
        row = details[name]
        exports[name] = {key: row[key] for key in
                        ("status", "module", "stdout_bytes", "stdout_sha256", "explicit_export_targets", "exporter_sha256")}
    tools = receipt["verification_tools"]
    return {
        "source": {key: source[key] for key in
                   ("external_src_tree", "external_source_inventory_sha256_without_challenge",
                    "external_source_inventory_entries_without_challenge", "native_head", "native_tree", "pins")},
        "canonical_environment": receipt["canonical_environment"], "environment": receipt["environment"],
        "stock_runtime_files": receipt["stock_runtime_files"],
        "tools": {key: tools[key]["sha256"] for key in
                  ("exporter", "statement_comparison_helper", "raw_object_inspector_source", "lake", "kernel_producer")},
        "native_validated_inputs_sha256": details["native_build_receipt"]["validated_inventory_sha256"],
        "canonical_type_and_axiom_audit_sha256": details["canonical_type_and_axiom_audit"]["sha256"],
        "complete_snapshot": {key: details["complete_object_snapshot"][key] for key in
                              ("inventory_sha256", "root_count", "object_count")},
        "promoted_canonical_artifacts": details["canonical_objects_promotion"]["exact_canonical_artifacts_promoted"],
        "exports": exports,
    }


def compare_identity(actual, expected):
    mismatches = [key for key in sorted(set(actual) | set(expected)) if actual.get(key) != expected.get(key)]
    return {"status": "MATCHED_RECORDED_INPUT_IDENTITIES" if not mismatches else "DIAGNOSTIC_COMPARISON_MISMATCH",
            "mismatched_fields": mismatches, "actual": actual, "expected": expected,
            "proof_rejection": False, "proof_acceptance": False,
            "scope": "Exact source/object/export/import-path identities; no equality of cache residency, host scheduling or progress"}


def resource_before(work, head, baseline):
    root = work / "loop-dio-resource"
    initial = read_json(root / "INITIAL.json")
    setup = read_json(root / "SETUP_RESULT.json")
    require(initial["status"] == "INITIAL_RESOURCE_IDENTITY_BOUND" and
            setup["status"] == "READY_FOR_ORIGINAL_FILE_VERIFICATION_NOT_BOUND", "Resource setup/binding incomplete")
    require(all(row["requested_head"] == head and row["selected_profile"] == RESOURCE_PROFILE
                for row in (initial, setup)), "Resource source/profile identity differs")
    require(initial["setup_sha256"] == digest(root / "SETUP_RESULT.json"), "Resource receipt chain differs")
    require(initial["identity"] == setup["mounted"] and initial["source_hashes"] == setup["source_hashes"],
            "Resource binding differs from setup")
    require(initial["identity"]["loop"] == baseline["resource"]["loop"], "Effective DIO/RO/geometry differs")
    require(initial["identity"]["decompressor_mode"]["value"] == "single", "Effective single mode missing")
    image = setup["image_authentication"]
    require(image["sha256"] == baseline["resource"]["image_sha256"] and
            image["bytes_read"] == baseline["resource"]["image_bytes"], "Original image bytes differ")
    mounted = read_json(work / "mounted-store-verified.json")
    manifest = work / "proof-store.sqfs.files.sha256"
    require(mounted["status"] == "PASS" and mounted["files"] == 350374 and
            mounted["manifest_sha256"] == digest(manifest) == baseline["resource"]["mounted_manifest_sha256"],
            "Original full mounted-file sweep receipt is missing or differs")
    return {"initial_sha256": digest(root / "INITIAL.json"), "setup_sha256": digest(root / "SETUP_RESULT.json"),
            "mounted_verification_sha256": digest(work / "mounted-store-verified.json"),
            "identity": initial["identity"], "context": initial["context"],
            "scope": "Authenticated same-run setup and full-sweep receipts, not a repeated sweep or continuous DIO measurement"}


def phase_markers(text):
    rows = []
    for line in text.splitlines():
        match = re.fullmatch(r"IMPORT_DIAGNOSTIC mono_ms=(\d+) (.+)", line)
        require(match is not None, "Unexpected diagnostic log line")
        rows.append({"mono_ms": int(match[1]), "message": match[2]})
    expected = ["DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[Init, Init, Main, OPICAStep4.NativeValidated, Lean]",
                "NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit", "CORE_BEGIN", "CORE_END",
                "FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0", "FINALIZE_END"]
    for index, row in enumerate(rows):
        if index < len(expected):
            require(row["message"] == expected[index], "Phase marker order/settings/import-array mismatch")
        elif index == 6:
            require(re.fullmatch(r"HEADER_MATCH modules=\d+", row["message"]) is not None, "Missing exact header check")
        elif index == 7:
            require(row["message"] == "DIAGNOSTIC_COMPLETE no_proof_validity_established", "Unexpected completion marker")
        else:
            raise Refusal("Extra diagnostic marker")
        if index:
            require(row["mono_ms"] >= rows[index - 1]["mono_ms"], "Nonmonotone diagnostic marker time")
    values = {row["message"].split()[0]: row["mono_ms"] for row in rows}
    return {"markers": rows, "header_and_completion_observed": len(rows) == 8,
            "core_seconds": ((values["CORE_END"] - values["CORE_BEGIN"]) / 1000 if "CORE_END" in values else None),
            "finalize_seconds": ((values["FINALIZE_END"] - values["FINALIZE_BEGIN"]) / 1000 if "FINALIZE_END" in values else None),
            "scope": "Only literal completed marker intervals; missing intervals are unknown, never inferred from RSS"}


def monitored(monitor, name, command, cwd, env, output, timeout):
    # Frozen monitored_process.run has keyword-only cwd/env and returns (receipt, text).
    row, text = monitor.run(name, command, cwd=cwd, env=env, output=output,
                            timeout=timeout, memory_mib=50000, expected=0, log_limit=64 << 20)
    return row, text


def retain_probe_products(build, output):
    """Retain only the two generated observer products; never confer proof authority."""
    require(not output.exists() and not output.is_symlink(), "Probe custody directory must be fresh")
    require(output.parent.absolute() == output.parent.resolve(), "Symlink custody ancestor refused")
    output.mkdir()
    result = {"schema": "OPICA_GENERATED_PROBE_CUSTODY_V1", "started_utc": utc(),
              "status": "INCOMPLETE_GENERATED_PROBE_CUSTODY", "proof_acceptance": False,
              "member_limit_bytes": 150 << 20, "total_limit_bytes": 300 << 20,
              "bounds_are_not_future_measured_sufficiency": True, "files": []}
    total = 0
    try:
        prepared = read_json(build / "PROBE_BUILD.json")
        result["probe_build_receipt_sha256"] = digest(build / "PROBE_BUILD.json")
        require(prepared["status"] == "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY", "Probe preparation was not complete")
        for name in ("import_phase_probe", "ImportPhaseProbe.olean"):
            row = {"name": name, "status": "NOT_RETAINED"}
            result["files"].append(row)
            try:
                src, dst = regular(build / name), output / name
                before = src.stat()
                expected = prepared["files"][name]
                require(before.st_size <= result["member_limit_bytes"] and
                        total + before.st_size <= result["total_limit_bytes"], "Generated probe custody size bound exceeded")
                check_file(src, expected["sha256"], expected["bytes"])
                with src.open("rb") as inp, dst.open("xb") as out:
                    copied = 0
                    while block := inp.read(min(8 << 20, expected["bytes"] - copied + 1)):
                        require(copied + len(block) <= expected["bytes"], "Generated probe grew beyond its exact recorded byte bound")
                        out.write(block)
                        copied += len(block)
                check_file(dst, expected["sha256"], expected["bytes"])
                after = src.stat()
                require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                        "Generated probe changed during custody copy")
                check_file(src, expected["sha256"], expected["bytes"])
                total += before.st_size
                row.update(status="RETAINED_GENERATED_DIAGNOSTIC_EVIDENCE_ONLY", bytes=before.st_size,
                           sha256=expected["sha256"], source=str(src), retained=str(dst))
            except (OSError, ValueError, KeyError, Refusal) as exc:
                row.update(status="MISSING_OVERSIZE_DRIFTED_OR_UNREADABLE", error_type=type(exc).__name__, error=str(exc))
        if len(result["files"]) == 2 and all(row["status"] == "RETAINED_GENERATED_DIAGNOSTIC_EVIDENCE_ONLY" for row in result["files"]):
            result["status"] = "COMPLETE_GENERATED_PROBE_CUSTODY_ONLY"
    except (OSError, ValueError, KeyError, Refusal) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    result.update(ended_utc=utc(), retained_bytes=total)
    write_json(output / "PROBE_PRODUCT_CUSTODY.json", result)
    return result


def prepare(args, source):
    build = args.work / "phase-probe-build"
    require(not build.exists() and not build.is_symlink(), "Probe build path must be fresh")
    build.mkdir()
    result = {"schema": "OPICA_DIAGNOSTIC_PROBE_BUILD_V1", "started_utc": utc(), "status": "RUNNING",
              "source_binding": source, "proof_acceptance": False, "commands": []}
    try:
        boot = load("matched_bootstrap", args.supplier / "opica-step4/native_bootstrap/bootstrap_native.py")
        monitor = load("matched_monitor", args.supplier / "opica-step4/modular/monitored_process.py")
        rt = args.work / "native/lean-4.33.1-linux/bin"
        result["runtime"] = boot.verify_runtime(rt)
        probe = HERE / "ImportPhaseProbe.lean"
        dest = build / "ImportPhaseProbe.lean"
        shutil.copyfile(probe, dest)
        env = dict(os.environ, LEAN_SYSROOT=str(rt.parent), LEAN_PATH=str(rt.parent / "lib/lean"))
        commands = [("compile_phase_probe", [str(rt / "lean"), "-c", str(build / "ImportPhaseProbe.c"),
                     "-o", str(build / "ImportPhaseProbe.olean"), str(dest)]),
                    ("link_phase_probe", [str(rt / "leanc"), "-O3", "-o", str(build / "import_phase_probe"),
                     str(build / "ImportPhaseProbe.c")])]
        for name, command in commands:
            row, _ = monitored(monitor, name, command, build, env, build, 600)
            result["commands"].append(row)
            require(row["status"] == "PASS" and row["exit_code"] == 0, "Probe compilation/linking did not complete")
        result["files"] = {name: {"sha256": digest(regular(build / name)), "bytes": (build / name).stat().st_size}
                           for name in ("ImportPhaseProbe.lean", "ImportPhaseProbe.c", "ImportPhaseProbe.olean", "import_phase_probe")}
        require(result["files"]["ImportPhaseProbe.lean"]["sha256"] == digest(probe), "Copied probe source differs")
        result["status"] = "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY"
    except BaseException as exc:
        result.update(status="PREPARATION_FAILED_OR_INCOMPLETE", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        result["ended_utc"] = utc()
        write_json(build / "PROBE_BUILD.json", result)
    return 0


def run(args, source):
    build = args.work / "phase-probe-build"
    prepared = read_json(build / "PROBE_BUILD.json")
    require(prepared["status"] == "PREPARED_DIAGNOSTIC_EXECUTABLE_ONLY" and
            prepared["source_binding"] == source, "Probe preparation source identity differs")
    for name, row in prepared["files"].items():
        check_file(build / name, row["sha256"], row["bytes"])
    require(not (args.work / "verification").exists(), "Prefix output must be entirely fresh")
    mod = load("matched_original_modular", args.supplier / "opica-step4/modular/verify_modular.py")
    monitor = load("matched_original_monitor", args.supplier / "opica-step4/modular/monitored_process.py")
    observations = load("matched_observations", HERE / "observations.py")
    gate = diagnostic_class(mod)(mod.arguments(production_argv(args.supplier, args.head, args.work)))
    result = {"schema": "OPICA_MATCHED_PREFIX_PHASE_RESULT_V1", "status": "RUNNING_PRELUDE", "started_utc": utc(),
              "proof_acceptance": False, "proof_rejection": False, "step4_status": "OPEN", "rh_status": "OPEN",
              "production_modular_gate": "NOT_RUN", "independent_proof_gate": "NOT_RUN",
              "source_binding": source, "production_arguments": production_argv(args.supplier, args.head, args.work),
              "probe_build_receipt_sha256": digest(build / "PROBE_BUILD.json"), "prefix_order": list(PREFIX),
              "comparison": "NOT_RUN", "observation": "NOT_RUN", "post_integrity": "NOT_RUN"}
    baseline = read_json(HERE / "ROUND25_BASELINE.json")
    code, prefix_complete, sampler = 2, False, None
    try:
        result["resource_before"] = resource_before(args.work, args.head, baseline)
        write_json(gate.output / "PROBE_BUILD.json", prepared)
        write_json(gate.output / "MATCHED_PHASE_RESULT.json", result)
        run_prefix(gate)
        prefix_complete = True
        actual = identity_projection(gate.receipt)
        result["comparison"] = compare_identity(actual, baseline["identity_projection"])
        write_json(gate.output / "ROUND25_INPUT_COMPARISON.json", result["comparison"])
        require(not result["comparison"]["mismatched_fields"], "Fresh prefix differs from Round25; diagnostic comparison refused")
        # Use the actual combined environment and promoted original objects, not an abbreviated reconstruction.
        require(gate.env["LEAN_PATH"].split(os.pathsep) == gate.receipt["environment"]["import_roots"], "Actual import roots differ")
        require(gate.receipt["environment"]["import_roots"][0] == str(gate.lib.resolve()), "Promoted root is not first")
        result["launch"] = {"command": [str(build / "import_phase_probe"), "exact-guard", "split"],
                            "cwd": str(gate.sources), "environment": {key: gate.env.get(key) for key in RESOURCE_KEYS},
                            "timeout_seconds": 1800, "rss_plus_swap_limit_mib": 50000, "log_limit_bytes": 64 << 20,
                            "probe_sha256": prepared["files"]["import_phase_probe"]["sha256"]}
        write_json(gate.output / "HOST_BEFORE.json", observations.host_details())
        result["status"] = "OBSERVING_NONACCEPTING_IMPORT"
        write_json(gate.output / "MATCHED_PHASE_RESULT.json", result)
        sampler = observations.SupplementalSampler(gate.output, PROCESS_NAME)
        sampler.thread.start()
        row, text = monitored(monitor, PROCESS_NAME, result["launch"]["command"], gate.sources, gate.env,
                              gate.output, 1800)
        result["observation"] = row
        result["phases"] = phase_markers(text)
        if row["status"] == "PASS" and row["exit_code"] == 0:
            require(result["phases"]["header_and_completion_observed"], "Observer exit zero lacks exact completion/header markers")
            result["status"] = "DIAGNOSTIC_IMPORT_COMPLETED_NO_PROOF_ACCEPTANCE"
            code = 0
        else:
            result["status"] = "DIAGNOSTIC_PROCESS_" + row["status"]
    except BaseException as exc:
        result.update(status="DIAGNOSTIC_INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "DIAGNOSTIC_FAILED_OR_INCOMPLETE",
                      error_type=type(exc).__name__, error=str(exc))
        if isinstance(result["comparison"], dict) and result["comparison"]["mismatched_fields"]:
            result["status"] = "DIAGNOSTIC_COMPARISON_MISMATCH"
    finally:
        if sampler is not None:
            result["optional_observer"] = sampler.finish()
        write_json(gate.output / "HOST_AFTER.json", observations.host_details())
        if prefix_complete:
            # This is an independently labelled rehash, not execution or acceptance of production stage30.
            try:
                result["post_integrity"] = {"status": "DIAGNOSTIC_INPUT_REHASH_PASSED", "production_stage30": "NOT_RUN",
                                            "details": gate.final_integrity()}
                require(digest(build / "import_phase_probe") == prepared["files"]["import_phase_probe"]["sha256"],
                        "Probe executable drifted")
                require(authenticate(args.supplier, args.head) == source, "Diagnostic source drifted")
                require(digest(args.work / "loop-dio-resource/INITIAL.json") == result["resource_before"]["initial_sha256"],
                        "Initial resource receipt drifted")
            except BaseException as exc:
                result["post_integrity"] = {"status": "DIAGNOSTIC_REHASH_FAILED_OR_UNAVAILABLE",
                                            "error_type": type(exc).__name__, "error": str(exc)}
                result["observation_disposition_before_integrity_failure"] = result["status"]
                result["status"] = "DIAGNOSTIC_COMPARISON_INVALID_AFTER_OBSERVATION"
                code = 2
        forbidden = [name for name in FORBIDDEN_RECEIPTS if (gate.output / name).exists()]
        theorem_objects = [str(path) for root in (gate.lib, gate.canonical_lib) for name in ("ImportGuard", "MainClosedBridge")
                           for path in (root / "OPICAStep4").glob(name + ".*")]
        result["acceptance_firewall"] = {"production_receipts_present": forbidden, "guard_or_closed_products": theorem_objects,
                                         "all_production_stages20_to30_not_run": all(r["status"] == "NOT_RUN" for r in gate.receipt["stages"][19:])}
        if forbidden or theorem_objects or not result["acceptance_firewall"]["all_production_stages20_to30_not_run"]:
            result["status"], code = "DIAGNOSTIC_AUTHORITY_BOUNDARY_FAILURE", 2
        result.update(ended_utc=utc(), exit_code=code)
        gate.diagnostic_state = "DIAGNOSTIC_TERMINATED_NO_PROOF_ACCEPTANCE"
        gate.save()
        write_json(gate.output / "MATCHED_PHASE_RESULT.json", result)
    print(json.dumps({key: result[key] for key in ("status", "proof_acceptance", "exit_code")}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("selection", "prepare", "run"))
    parser.add_argument("--selection", required=True)
    parser.add_argument("--supplier", type=Path)
    parser.add_argument("--head")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    try:
        check_selection(args.selection)
        if args.operation == "selection":
            print(json.dumps({"status": "EXPLICIT_DIAGNOSTIC_SELECTION", "proof_acceptance": False}))
            return 0
        reject_overrides(os.environ)
        require(args.supplier is not None and args.head is not None and args.work is not None, "Missing source/work inputs")
        args.supplier, args.work = args.supplier.absolute(), args.work.absolute()
        require(args.supplier == args.supplier.resolve() and args.work == args.work.resolve(), "Canonical source/work paths required")
        baseline = read_json(HERE / "ROUND25_BASELINE.json")
        require(str(args.work) == baseline["work_path"], "Comparison requires the recorded production work path")
        require(args.work.is_dir() and not args.work.is_relative_to(args.supplier), "Existing external work directory required")
        source = authenticate(args.supplier, args.head)
        return prepare(args, source) if args.operation == "prepare" else run(args, source)
    except BaseException as exc:
        print(json.dumps({"status": "DIAGNOSTIC_REFUSED_OR_UNAVAILABLE", "error_type": type(exc).__name__,
                          "error": str(exc), "proof_acceptance": False, "proof_rejection": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
