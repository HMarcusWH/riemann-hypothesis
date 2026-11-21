#!/usr/bin/env python3
"""OPICA23 kernel-object composition with bounded memory-counter reconciliation.

The supplier certificate is authenticated against an external published kernel
receipt.  Native imports are replayed locally with --fresh; the actual newly
kernel-constructed theorem values are inspected and replayed locally. The stock
kernel checks every fresh declaration. This avoids loading elaborator extensions;
it does not claim that the original Main-importing Lean source compilation passed.
The original 25-stage and Round20, Round21 and Round22 gates retain their recorded dispositions.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import ExitStack
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "portable_gate"
FROZEN_RUNNER_SHA = "a01ac482dd59444b2313dc525b63d22036de892a3076a23a06c80514d7df78ca"
FROZEN_SPEC_SHA = "771b194e8330a6844705178a5bc4cfc09ece629c9a2c88031e1bb74615640862"
GATE_VERSION = "OPICA23_KERNEL_OBJECT_COMPOSITION_V1"
KERNEL_PRODUCER_FILES = {
    "KernelBridge.lean": "bce55684b2e0ca99a46fc79e259573ae801523799d2c01cc5922c6233e49b977",
    "lakefile.toml": "689bac7c7427b93750318c305b40cdf8c67264e1752c987e11989b93f0cc6fcc",
    "lean-toolchain": "3aac669c7a910ec2389f4e4f921b605adf6ebf2d1e0c9b9cd0be4d33f3f5db71",
    "SELECTED_ROOT_INVENTORY.json": "5170df5090528ad6bb7edf8a2537dd2aa039284f8a358b4ee7dbeb84a52b48ff",
    "PRODUCER_SPEC.md": "8f9a590976a3e994eb11bfb4e47c5ef7ecfb6bf8a3155eda7b514e51b7b6fad1"
}
MONITOR_SHA = "37cc7e705d660745bc0a6b2dc556a38761c1460c6e7e30fd9597ccae40ca0709"
PRIOR_ROUND22_MODULAR_RUNNER_SHA = "cf300d15b9aa01d1a18094e669b89d7b375117df4cc03643990058d38d397639"
PRIOR_ROUND21_MODULAR_RUNNER_SHA = "32d19e6c9e89aefe74cdbfde6aace6a4eb28e1c80ebe88fcd8ca02def0ed8299"
PRIOR_MODULAR_RUNNER_SHA = "e73facc3098f023ca1a0c89a4320b7974f0afc6e842d0e82784d2426da0ac726"
EXTERNAL_HEAD = "bdb1810a06c78f246da285c9bcbe7db2cd992888"
EXTERNAL_SRC_TREE = "24df20b62d9976ccd20da819bc20b16f808f0fdd"
COMPILER_COMMIT = "819816b2e0a3bf405af45ae5c7af2491d8f5bee6"
EXPORTER_COMMIT = "15f6055e299ad5b89345e533cc2192f4cc00f659"
SUPPLIER_SHA = "5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e"
SUPPLIER_COMPRESSED_SHA = "61a8938ad5f5e57397c1c0e3b954916af546d9004ade01c3555744a681b05381"
SUPPLIER_PUBLISHED_BYTES = 61_570_595_788
TARGET_FILE_SHA = "9eeb2e5e55be4a78f6e4983fc950dba915b45ad8aeb7a02a32341927a89e05e8"
INSPECTOR_SHA = "9d54c1c2fd25ade5d1aaa558c9c5d5fdbd156973a20f246b5caf661872fd262c"
LOG_HASHES = {
    "audit.log": "0a1473fce6eed840011f4a76b1c51558fc6f03edd1e6bd1ee542e6c738d87a62",
    "con-leche-master.log": "23e27eacb9e8378569474cc185c0e98f6b995b4db0f8df88fd48a921084fed02",
    "con-leche-compare.log": "5a068bf55f24904eea9f05eda947c63d43bdee3c6ab0490e43943a3bd9af1f6e",
    "nanoda.log": "d4c5360b02d8dd885150c1cc28b616cb6fb5bf5b20d142558d79a7b15ae9d9df",
}
PAGE_SHA = "e46488825acc7e4fbf3c0c744edcfaa5219f773571a9267b06df26b11f18a1a3"
MANIFEST_SHA = "a26d92ed4c11c8503e9f09a52fa874fa9175c13b2c7bb29213af21ac12c1ede3"
RUNTIME_MANIFEST_SHA = "550bbf7a1fc8e2549ecf2d122ff5bfa2007f71d78e3ce1dba42d02fb1ae72793"
HEADLINE_TARGETS = (
    "riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re",
    "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive",
)
PRIMITIVE_TARGETS = (
    "Nat.add", "Nat.sub", "Nat.mul", "Nat.pow", "Nat.gcd", "Nat.div", "Nat.mod",
    "Nat.beq", "Nat.ble", "Nat.land", "Nat.lor", "Nat.xor", "Nat.shiftLeft",
    "Nat.shiftRight", "String.ofList", "Char.ofNat", "List", "eagerReduce", "Nat",
    "String", "String.mk", "Char", "optParam", "autoParam", "semiOutParam", "outParam",
)
AUX_TARGETS = ("Quot", "Quot.mk", "Quot.lift", "Quot.ind", "propext", "Quot.sound",
               "Classical.choice", *PRIMITIVE_TARGETS)
SUPPLIER_TARGETS = ("Quot", "Quot.mk", "Quot.lift", "Quot.ind", *HEADLINE_TARGETS,
                    "propext", "Quot.sound", "Classical.choice", *PRIMITIVE_TARGETS)
AUDIT_NAMES = (
    "Zeta23.OPICARound19.ReceiverAudit.exactReceiver",
    "Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_reflexive",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredC1_is_native",
    "Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive",
    "Zeta23.OPICARound20.even_zero_bound_of_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.riemannHypothesis_iff_all_boundary_flat_nonnegative",
    "Zeta23.OPICARound20.finite_negative_boundary_flat_witness_refutes_c1",
)
CANONICAL_MODULES = ("OPICAStep4.ReceiverAudit", "OPICAStep4.ClaimFingerprint",
                     "OPICAStep4.BoundaryFlatCharacterization", "OPICAStep4.NativeValidated")
CLOSED_MODULE = "OPICAStep4.MainClosedBridge"
CLOSED_TYPES = {
    "Zeta23.OPICARound20.Closed.step4C1":
        "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds",
    "Zeta23.OPICARound20.Closed.literalC1": "Zeta23.OPICARound19.ClaimFingerprint.requiredC1",
    "Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity":
        "Zeta23.OPICARound20.AllBoundaryFlatNonnegative",
}
SELECTED_ROOTS = (*SUPPLIER_TARGETS, *AUDIT_NAMES, *CLOSED_TYPES)
MATHEMATICAL_ROOTS = (*HEADLINE_TARGETS, *AUDIT_NAMES, *CLOSED_TYPES)
SOURCE_HASHES = {
    "OPICAStep4/ReceiverAudit.lean": "99810c3fd20182630ec6b0fcaf6e67c6be3ec0b04171371ba5d723b2dcc4745b",
    "OPICAStep4/ClaimFingerprint.lean": "255a46d2926e713ad5d41083ef9f818b7e415d89c8a96d63540486d73a56fd56",
    "OPICAStep4/BoundaryFlatCharacterization.lean": "e19bfb13fcb523930617aae99c9d1190cccb1ec3915feae610f7195c68bbef61",
    "OPICAStep4/NativeValidated.lean": "490d4dedfbf28088dbb85f3567c9acc93401b15a19d23e5399eea79bd32e03cf",
    "OPICAStep4/ImportGuard.lean": "549a0c43ced7253fc6c1672e3ab548e6576a88f1d5e42f770592dc570f6c6c27",
    "OPICAStep4/MainClosedBridge.lean": "a4243a995e778677094035e9f212f504c208b9f7d35dc4e0ee92de80512ec86e",
}
STAGES = (
    "source_identity", "external_validation_evidence", "external_endpoint_presence",
    "immutable_supplier_store", "canonical_environment", "verification_tools",
    "native_build_receipt", "native_source_policy", "canonical_dependency_snapshot",
    "canonical_modules_compile", "canonical_type_and_axiom_audit",
    "canonical_fingerprint_export", "canonical_native_proof_export",
    "complete_native_fresh_kernel_replay", "comparison_controls", "compatible_environment",
    "shared_dependency_comparison", "complete_object_snapshot", "canonical_objects_promotion",
    "guarded_kernel_import", "fresh_closed_kernel_construction", "actual_closed_object_audit",
    "closed_type_and_axiom_audit", "import_guard_kernel_replay", "closed_module_kernel_replay",
    "final_native_proof_export_identity", "final_fingerprint_export",
    "canonical_statement_definition_comparison", "final_supplier_certificate_identity",
    "final_input_integrity",
)


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


# Validate before importing executable frozen helpers.
if digest_file(FROZEN / "verify_combined.py") != FROZEN_RUNNER_SHA:
    raise RuntimeError("Frozen Round19 helper changed")
if digest_file(FROZEN / "GATE_SPEC.json") != FROZEN_SPEC_SHA:
    raise RuntimeError("Frozen Round19 specification changed")
_module_spec = importlib.util.spec_from_file_location("opica19_frozen_gate", FROZEN / "verify_combined.py")
old = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(old)
GateFailure, GateBlocked, GateIncomplete = old.GateFailure, old.GateBlocked, old.GateIncomplete
require, require_file, sha256, json_write = old.require, old.require_file, old.sha256, old.json_write


def modular_spec(frozen: dict) -> dict:
    spec = copy.deepcopy(frozen)
    spec.update(schema=GATE_VERSION, name="OPICA23 stock-kernel object composition with bounded counter reconciliation",
                external_endpoint="Main", external_theorem="riemannHypothesis",
                recognized_external_heads={EXTERNAL_HEAD: "Frozen supplier fork checkpoint"},
                closed_comparison_module=CLOSED_MODULE,
                module_types={CLOSED_MODULE: ["riemannHypothesis", *CLOSED_TYPES]},
                source_sha256=dict(SOURCE_HASHES), native_proof_targets=list(AUDIT_NAMES),
                supplier_export_targets=list(SUPPLIER_TARGETS), supplier_export_sha256=SUPPLIER_SHA,
                supplier_published_bytes=SUPPLIER_PUBLISHED_BYTES,
                actual_closed_types=dict(CLOSED_TYPES), inspector_sha256=INSPECTOR_SHA,
                kernel_producer_files=dict(KERNEL_PRODUCER_FILES), monitor_sha256=MONITOR_SHA,
                object_production=("Pinned stock Lean kernel addDeclCore with checking enabled, followed "
                    "by the stock ordinary-module writer. No Main-importing elaborator compilation is claimed."),
                original_closed_source_role="PINNED_EXACT_MATHEMATICAL_SPECIFICATION_NOT_REELABORATED",
                claim_boundary=("Exact native C1 at the common integration pin using the identified "
                    "externally kernel-checked supplier certificate; native environment and new "
                    "closed declaration values checked locally. No full combined export kernel "
                    "rerun, original 25-stage gate pass, original-pin rebuild, or production acceptance."))
    require(tuple(spec["export_auxiliary_targets"]) == AUX_TARGETS, "Frozen auxiliary targets changed")
    require(len(SUPPLIER_TARGETS) == 38 and len(set(SUPPLIER_TARGETS)) == 38,
            "Supplier target list must have 38 distinct ordered names")
    return spec


def terminate_group(process: subprocess.Popen | None):
    if process is None:
        return
    try:
        # The leader may have exited while a descendant still holds stdout.
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def stream_command(argv, *, cwd: Path, env: dict, log: Path, record: Path,
                   timeout: float, max_bytes: int, expected_sha: str | None = None,
                   stdout_path: Path | None = None, progress_seconds: float = 30) -> dict:
    """Hash every stdout byte once, without decoding, normalization or buffering it all.

    EOF, exit zero, no diagnostics, a nonempty bounded stream and the requested
    hash are all required. A timeout or error kills the whole producer group.
    """
    require(timeout > 0 and max_bytes > 0, "Stream limits must be positive")
    require(not log.exists() and not record.exists(), "Stream evidence paths must be fresh")
    if stdout_path:
        require(not stdout_path.exists(), "Stream artifact path must be fresh")
    row = {"status": "RUNNING", "command": list(map(str, argv)), "cwd": str(cwd),
           "log": str(log), "started_utc": old.utc_now(), "max_bytes": max_bytes,
           "timeout_seconds": timeout, "stdout_storage": "FILE" if stdout_path else "HASH_AND_COUNT_ONLY",
           "environment": {k: env[k] for k in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT",
               "PATH", "LD_LIBRARY_PATH", "LEAN_NUM_THREADS", "LEAN_ABORT_ON_PANIC") if k in env}}
    h, count, process = hashlib.sha256(), 0, None
    started = progress = time.monotonic()
    json_write(record, row)
    try:
        with ExitStack() as stack:
            err = stack.enter_context(log.open("xb"))
            out = stack.enter_context(stdout_path.open("xb")) if stdout_path else None
            process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                                       stdout=subprocess.PIPE, stderr=err, start_new_session=True)
            stack.callback(process.stdout.close)
            selector = stack.enter_context(selectors.DefaultSelector())
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            eof = False
            while not eof or process.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > timeout:
                    row["status"] = "INCOMPLETE"
                    raise GateIncomplete("Stream exceeded its time budget; no pass is inferred")
                require(log.stat().st_size <= 64 << 20, "Exporter stderr exceeded the diagnostic size limit")
                for key, _ in selector.select(timeout=0.2):
                    block = os.read(key.fd, 1 << 20)
                    if not block:
                        eof = True
                        selector.unregister(key.fileobj)
                        continue
                    count += len(block)
                    require(count <= max_bytes, "Export exceeded its configured byte limit")
                    h.update(block)
                    if out:
                        out.write(block)
                if time.monotonic() - progress >= progress_seconds:
                    print(f"Streamed {count:,} exact bytes in {elapsed:.1f}s: {record.stem}", flush=True)
                    progress = time.monotonic()
                if eof and process.poll() is None:
                    time.sleep(0.05)
            row["exit_code"] = process.wait()
        require(log.stat().st_size <= 64 << 20, "Exporter stderr exceeded the diagnostic size limit")
        row["diagnostics"] = old.compiler_diagnostics(log.read_text(encoding="utf-8", errors="replace"))
        require(row["exit_code"] == 0, "Exporter exited with " + str(row["exit_code"]))
        require(not row["diagnostics"], "Exporter emitted an invalid-proof/error/warning diagnostic")
        require(count > 0, "Exporter returned an empty stream")
        if expected_sha:
            require(h.hexdigest() == expected_sha, "Exact export SHA256 differs from required certificate")
        if stdout_path:
            require(sha256(stdout_path) == h.hexdigest(), "Stored export differs from observed stdout")
            row["stdout_artifact"] = str(stdout_path)
        row["status"] = "PASS"
        return row
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            row["status"] = "INTERRUPTED"
        elif row["status"] == "RUNNING":
            row["status"] = "FAIL"
        row.update(failure=str(exc), exception_type=type(exc).__name__)
        raise
    finally:
        terminate_group(process)
        row.update(exit_code=process.returncode if process else None, stdout_bytes=count,
                   stdout_sha256=h.hexdigest(), expected_sha256=expected_sha,
                   ended_utc=old.utc_now(), elapsed_seconds=round(time.monotonic() - started, 3))
        if log.exists():
            row["log_sha256"] = sha256(log)
        json_write(record, row)


def parse_sha_manifest(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([^\r\n]+)", line)
        require(match is not None, "Malformed publisher SHA256SUMS entry")
        value, name = match.groups()
        require(name not in result and not name.startswith("/") and
                all(part not in ("", ".", "..") for part in name.split("/")),
                "Duplicate or unsafe publisher manifest entry")
        result[name] = value
    return result


def verify_supplier_checkpoint(repo, checkpoint, source_tree):
    require(old.git_text(repo, "rev-parse", "HEAD:src") == source_tree,
            "Supplier src tree differs from the original published source")
    old.command_bytes(["git", "merge-base", "--is-ancestor", checkpoint, "HEAD"], repo)
    return {"head": old.git_text(repo, "rev-parse", "HEAD"),
            "source_tree": source_tree, "checkpoint_ancestor": checkpoint}


def parse_selected_root_audit(text):
    roots = re.findall(r"(?m)^OPICA21_SAFE_SELECTED_ROOT (\S+)\s*$", text)
    require(len(SELECTED_ROOTS) == len(set(SELECTED_ROOTS)) == 50,
            "Expected selected-root inventory is not exactly fifty distinct names")
    require(roots == list(SELECTED_ROOTS),
            "Actual safe selected-root audit is missing, duplicated, substituted or reordered")
    return roots


class ModularGate(old.Gate):
    def __init__(self, args):
        require(not any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_AUDIT", "DYLD_INSERT_LIBRARIES")),
                "Inherited dynamic-loader injection variables are forbidden")
        self._modular_ready = False
        super().__init__(args)
        self.spec = modular_spec(self.spec)
        self.inspector = HERE / "InspectClosedObject.lean"
        self.evidence_dir = (args.external_evidence or HERE / "external-evidence").resolve()
        self.runtime_prefixes = {}
        self.receipt.update(schema=GATE_VERSION, gate_version=GATE_VERSION,
            runner_sha256=sha256(Path(__file__)), frozen_runner_sha256=FROZEN_RUNNER_SHA,
            frozen_spec_sha256=FROZEN_SPEC_SHA,
            supplier_certificate_identity="NOT_ESTABLISHED",
            supplier_kernel_execution="NOT_ESTABLISHED",
            native_full_kernel_execution="NOT_RUN",
            new_closed_declarations_kernel_execution="NOT_RUN",
            full_combined_export_kernel_execution="NOT_RUN_BY_THIS_GATE",
            prior_round19_25_stage_gate="NOT_RUN_OR_BLOCKED_UNCHANGED",
            prior_round20_modular_v1_gate="INCOMPLETE_IMPORT_GUARD_TIMEOUT_AT_56869094",
            prior_round20_modular_runner_sha256=PRIOR_MODULAR_RUNNER_SHA,
            prior_round21_kernel_object_gate="FAIL_OPTIONAL_PROC_IO_AT_56b129cc",
            prior_round21_modular_runner_sha256=PRIOR_ROUND21_MODULAR_RUNNER_SHA,
            prior_round22_kernel_object_gate="FAIL_MANDATORY_PROC_COUNTERS_AT_70bfbd66",
            prior_round22_modular_runner_sha256=PRIOR_ROUND22_MODULAR_RUNNER_SHA,
            closed_source_elaborator_compilation="NOT_RUN_BY_THIS_GATE",
            fresh_closed_object_production="NOT_RUN",
            source_to_object_provenance={"native": "PENDING_FRESH_BUILD_RECEIPT_VALIDATION",
                "supplier": "NOT_ESTABLISHED_BY_OBJECT_SNAPSHOTS_OR_EXPORT_HASH"},
            claim="NOT_ESTABLISHED", stages=[{"name": n, "status": "NOT_RUN"} for n in STAGES])
        self._modular_ready = True
        json_write(self.output / "MODULAR_SPEC.json", self.spec)
        self.receipt["modular_spec_sha256"] = self.bind(self.output / "MODULAR_SPEC.json")
        self.save()

    def save(self):
        # The inherited initializer must never emit an old-gate receipt.
        if self._modular_ready:
            json_write(self.output / "MODULAR_GATE_RECEIPT.json", self.receipt)

    def bind_log(self, path):
        # Quiet successful tools have empty logs; proof/source artifacts continue
        # to use the frozen nonempty-file requirement in bind().
        require(path.is_file(), "Required process log is absent: " + str(path))
        key, value = str(path.absolute()), sha256(path)
        require(key not in self.input_hashes or self.input_hashes[key] == value,
                "Process log changed while binding: " + key)
        self.input_hashes[key] = value
        return value

    def run_process(self, name, argv, cwd, timeout, *, env=None, stdout_path=None):
        """Bound execution and preserve resource evidence; these records prove no theorem."""
        monitor_path = HERE / "monitored_process.py"
        require(sha256(monitor_path) == MONITOR_SHA, "Execution monitor source changed")
        monitor_spec = importlib.util.spec_from_file_location("opica21_monitored_process", monitor_path)
        monitor = importlib.util.module_from_spec(monitor_spec)
        monitor_spec.loader.exec_module(monitor)
        row, text = monitor.run(name, argv, cwd=cwd, env=env or self.env,
            output=self.output, timeout=timeout, memory_mib=50000,
            expected=0, log_limit=64 << 20, stdout_path=stdout_path)
        if row.get("status") == "INCOMPLETE":
            raise GateIncomplete(row.get("failure", name + " did not complete within its execution limits"))
        require(row.get("status") == "PASS" and row.get("exit_code") == 0,
                row.get("failure", name + " did not return a successful process result"))
        diagnostics = old.compiler_diagnostics(text)
        row["diagnostics"] = diagnostics
        if diagnostics:
            row.update(status="FAIL", failure=name + " emitted an error, warning or invalid-proof diagnostic")
            json_write(self.output / (name + ".process.json"), row)
            raise GateFailure(row["failure"])
        json_write(self.output / (name + ".process.json"), row)
        telemetry = self.output / (name + ".telemetry.jsonl")
        self.bind_log(telemetry)
        return row

    def source_identity(self):
        require(self.bind(self.package / "verify_combined.py") == FROZEN_RUNNER_SHA and
                self.bind(self.spec_file) == FROZEN_SPEC_SHA, "Frozen helper/specification changed")
        # Infrastructure-only descendants are accepted only at an explicit full
        # head pin. The frozen helper verifies that pin and protected source tree.
        verify_supplier_checkpoint(self.external, EXTERNAL_HEAD, EXTERNAL_SRC_TREE)
        result = super().source_identity()
        require(self.bind(self.inspector) == INSPECTOR_SHA, "Raw object inspector source changed")
        self.bind(Path(__file__))
        require(bool(KERNEL_PRODUCER_FILES), "Reviewed kernel producer inventory is missing")
        for relative, expected in KERNEL_PRODUCER_FILES.items():
            require(self.bind(HERE / "kernel_producer" / relative) == expected,
                    "Kernel producer source changed: " + relative)
        root_inventory = json.loads((HERE / "kernel_producer/SELECTED_ROOT_INVENTORY.json").read_text())
        require(root_inventory["ordered_roots"] == list(SELECTED_ROOTS) and
                root_inventory["mathematical_roots"] == list(MATHEMATICAL_ROOTS),
                "Generated producer root inventory differs from the exact gate roots")
        require(self.bind(HERE / "monitored_process.py") == MONITOR_SHA,
                "Execution monitor source changed")
        require(self.bind(self.external / "export-targets.txt") == TARGET_FILE_SHA,
                "Original ordered supplier target file changed")
        require(tuple((self.external / "export-targets.txt").read_text().split()) == SUPPLIER_TARGETS,
                "Original target file does not contain all 38 targets in required order")
        self.bind(HERE / "SPEC.md")
        result.update(external_src_tree=EXTERNAL_SRC_TREE, supplier_source_checkpoint_ancestor=EXTERNAL_HEAD,
                      gate_version=GATE_VERSION,
                      actual_closed_module=CLOSED_MODULE)
        return result

    def external_validation_evidence(self):
        manifest_path = self.evidence_dir / "SHA256SUMS"
        require(self.bind(manifest_path) == MANIFEST_SHA, "Frozen publisher manifest changed")
        manifest = parse_sha_manifest(manifest_path.read_text())
        required = {**LOG_HASHES, "solution.ndjson": SUPPLIER_SHA,
                    "solution.ndjson.zst": SUPPLIER_COMPRESSED_SHA}
        for name, expected in required.items():
            require(manifest.get(name) == expected, "Publisher manifest binding differs: " + name)
        files = {"SHA256SUMS": {"sha256": self.bind(manifest_path)}}
        logs = {}
        for name, expected in LOG_HASHES.items():
            path = self.evidence_dir / name
            require(self.bind(path) == expected, "Published external verification log changed: " + name)
            logs[name] = path.read_text()
            files[name] = {"path": str(path), "sha256": expected}
        for name in ("con-leche-master.log", "con-leche-compare.log", "nanoda.log"):
            require(bool(re.search(r"(?m)^\s*Exit status:\s*0\s*$", logs[name])),
                    "External completed-success exit marker is absent: " + name)
        require("accepted 1468418 declarations (--verified)" in logs["con-leche-master.log"],
                "External complete supplier acceptance marker is absent")
        for name in HEADLINE_TARGETS:
            require("con-leche: theorem " + name + " justified by the solution" in
                    logs["con-leche-compare.log"], "External comparison did not accept target: " + name)
            matches = re.findall(r"'" + re.escape(name) + r"' depends on axioms:\s*\[([^]]*)\]",
                                 logs["audit.log"])
            require(len(matches) == 1 and {x.strip() for x in matches[0].split(",") if x.strip()}
                    <= set(self.spec["allowed_axioms"]), "External target axiom audit failed: " + name)
        page = self.evidence_dir / "index.html"
        require(self.bind(page) == PAGE_SHA, "Frozen verification page changed; a new report requires review")
        files["index.html"] = {"path": str(page), "sha256": self.bind(page)}
        text = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", page.read_text())).split())
        require(SUPPLIER_SHA in text and SUPPLIER_COMPRESSED_SHA in text,
                "Frozen verification page does not identify the required supplier artifact")
        require("accept the full exported proof" in text and "confirms all five theorems" in text,
                "Frozen verification page lacks the completed external kernel/comparison report")
        fetched = self.evidence_dir / "FETCH_RECEIPT.json"
        if fetched.exists():
            files[fetched.name] = {"path": str(fetched), "sha256": self.bind(fetched)}
        self.receipt["supplier_kernel_execution"] = "EXTERNAL_PUBLISHED_RECEIPT"
        result = {"publisher": "https://math.mit.edu/~drew/grh/", "files": files,
            "accepted_supplier_declarations": 1468418, "accepted_headline_targets": list(HEADLINE_TARGETS),
            "scope": "Pinned completed published con-leche/nanoda receipts, not a local execution",
            "trust_boundary": "Relies on the publisher's report that the identified computation happened",
            "pending_full_export_lean_and_comparator_runs": "NOT_COUNTED_AS_PASSED"}
        self.receipt["external_validation_evidence"] = result
        return result

    def supplier_mount(self):
        target = self.external_lib.resolve()
        matches = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            fields, extra = left.split(), right.split()
            decode = lambda s: re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), s)
            point = Path(decode(fields[4]))
            if target.is_relative_to(point):
                matches.append((len(point.parts), {"mount_id": fields[0], "device": fields[2],
                    "root": decode(fields[3]), "mountpoint": str(point), "mount_options": fields[5],
                    "filesystem": extra[0], "source": decode(extra[1]), "super_options": extra[2]}))
        require(matches, "Cannot identify supplier object mount")
        row = max(matches, key=lambda item: item[0])[1]
        require("ro" in row["mount_options"].split(","), "Supplier objects must stay on a read-only mount")
        return row

    def immutable_supplier_store(self):
        self.supplier_mount_identity = self.supplier_mount()
        return self.supplier_mount_identity

    def verify_runtime_prefix(self, prefix):
        manifest_path = HERE.parent / "native_bootstrap/runtime_files.json"
        require(self.bind(manifest_path) == RUNTIME_MANIFEST_SHA, "Stock runtime manifest changed")
        manifest = json.loads(manifest_path.read_text())
        require(len(manifest["files"]) == 26, "Stock runtime manifest is incomplete")
        rows = {}
        for row in manifest["files"]:
            path = prefix / row["path"]
            require(self.bind(path) == row["sha256"] and path.stat().st_size == row["bytes"],
                    "Stock runtime file differs: " + str(path))
            rows[row["path"]] = row["sha256"]
        self.runtime_prefixes[str(prefix)] = rows
        self.receipt["stock_runtime_files"] = self.runtime_prefixes
        self.receipt["runtime_trust_boundary"] = (
            "Pinned Lean runtime executables and shared libraries; host OS, system loader/libc and hardware remain trusted")

    def canonical_environment(self):
        self.verify_runtime_prefix(self.args.lake.resolve().parent.parent)
        return super().canonical_environment()

    def identify_compiler(self, root, env):
        lean, checker, prefix, version = super().identify_compiler(root, env)
        self.verify_runtime_prefix(prefix)
        require(COMPILER_COMMIT in version and "Release" in version,
                "Compiler does not identify the required stock Release commit")
        return lean, checker, prefix, version

    def verification_tools(self):
        require(self.args.exporter is not None and self.args.comparison_helper is not None,
                "Supply --exporter and --comparison-helper")
        self.exporter = self.args.exporter.resolve()
        self.comparison_helper = self.args.comparison_helper.resolve()
        records = {name: {"path": str(path), "sha256": self.bind(path)} for name, path in
                   (("exporter", self.exporter), ("statement_comparison_helper", self.comparison_helper),
                    ("raw_object_inspector_source", self.inspector), ("lake", self.args.lake.resolve()))}
        source = self.args.exporter_source.resolve() if self.args.exporter_source else self.exporter.parents[3]
        require(old.git_text(source, "rev-parse", "HEAD") == EXPORTER_COMMIT,
                "Exporter source is not the reviewed commit")
        protected = [p for p in old.git_text(source, "ls-files").splitlines()
                     if p.endswith(".lean") or p in ("lakefile.toml", "lake-manifest.json")]
        require("Main.lean" in protected and "Export.lean" in protected,
                "Exporter entry point or implementation is missing from its source inventory")
        old.no_tracked_changes(source, protected)
        self.exporter_protected_paths = protected
        records["exporter_source"] = {"path": str(source), "head": EXPORTER_COMMIT,
            "tree": old.git_text(source, "rev-parse", "HEAD^{tree}"),
            "sources": {p: self.bind(source / p) for p in protected},
            "lean_toolchain_file_sha256": self.bind(source / "lean-toolchain")}
        self.exporter_source = source
        records["scope"] = "Trusted stock tools; executable hashes record bytes, not independent build provenance"
        records["official_comparator"] = "OPTIONAL_SMALL_CONTROLS_ONLY" if self.args.comparator_lake else "NOT_RUN"
        if self.args.comparator_lake:
            # Frozen validation also authenticates the optional judge toolchain.
            records["optional_official_tools"] = super().verification_tools()
        producer_root = self.output / "kernel-producer"
        require(not producer_root.exists(), "Kernel producer build directory must be fresh")
        producer_root.mkdir()
        for relative, expected in KERNEL_PRODUCER_FILES.items():
            source = HERE / "kernel_producer" / relative
            require(self.bind(source) == expected, "Kernel producer source changed")
            destination = producer_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            require(self.bind(destination) == expected, "Kernel producer copied source changed")
        build = self.run_process("build_kernel_producer", [str(self.args.lake.resolve()),
            "build", "kernel_bridge"], producer_root, 600, env=self.canonical_env)
        self.kernel_producer = producer_root / ".lake/build/bin/kernel_bridge"
        producer_sha = self.bind(self.kernel_producer)
        controls = self.run_process("kernel_producer_adversarial_controls",
            [str(self.kernel_producer), "controls"], producer_root, 120, env=self.canonical_env)
        control_text = Path(controls["log"]).read_text()
        for marker in ("OPICA21_KERNEL_CONTROLS_PASS", "EMPTY_GUARD_AND_THREE_THEOREM_OBJECTS_REPLAYED",
                       "INVALID_PROOF_REJECTED", "EXISTING_NAME_REJECTED",
                       "OPAQUE_TRANSITIVE_NONSTANDARD_AXIOM_REJECTED", "UNRESOLVED_DEPENDENCY_REJECTED",
                       "NON_THEOREM_MATHEMATICAL_ROOT_REJECTED", "MISSING_SELECTED_ROOT_REJECTED",
                       "DUPLICATE_SELECTED_ROOT_REJECTED", "UNSAFE_SELECTED_ROOT_REJECTED",
                       "PARTIAL_SELECTED_ROOT_REJECTED"):
            require(control_text.splitlines().count(marker) == 1,
                    "Kernel producer control marker missing or duplicated: " + marker)
        self.bind_log(Path(build["log"]))
        self.bind_log(Path(controls["log"]))
        records["kernel_producer"] = {
            "path": str(self.kernel_producer), "sha256": producer_sha,
            "sources": dict(KERNEL_PRODUCER_FILES), "build": build, "controls": controls,
            "role": "Untrusted producer; stock kernel checking and subsequent proof/claim gates establish acceptance",
            "new_elaborator_extension_entries": "EMPTY; no logical constant, type, proof or dependency omitted",
        }
        self.receipt["verification_tools"] = records
        return records

    def native_build_receipt(self):
        result = super().native_build_receipt()
        data = json.loads(Path(result["receipt"]).read_text())
        for field, actual in (("compiler_sha256", self.bind(self.lean)),
                              ("kernel_checker_sha256", self.bind(self.checker))):
            require(data.get(field) == actual, "Native receipt tool identity differs: " + field)
        self.receipt["source_to_object_provenance"]["native"] = "FRESH_572_MODULE_RECEIPT_AND_CURRENT_BYTES_VALIDATED"
        return result

    def native_source_policy(self):
        modules = old.native_import_closure(self.native, self.spec["native_endpoint"])
        for module in sorted(modules):
            path = self.native / old.module_path(module, ".lean")
            text = old.strip_lean_comments(path.read_text())
            require(not re.search(r"\b(?:sorry|sorryAx|admit|axiom)\b", text),
                    "Placeholder or project axiom in native closure: " + module)
            self.bind(path)
        return {"native_source_modules_scanned": len(modules),
                "authored_modules_already_pinned_and_scanned": len(SOURCE_HASHES)}

    def canonical_modules_compile(self):
        rows = []
        for module in CANONICAL_MODULES:
            row = self.compile_module(module, "compile_canonical_" + module.replace(".", "_"), canonical=True)
            row["scope"] = "Native receiver, definition fingerprints and structural consequences; no closed RH supplier"
            rows.append(row)
            self.bind_log(Path(row["log"]))
        return {"modules": rows}

    def compile_module(self, module, stage_name, *, canonical=False):
        row = super().compile_module(module, stage_name, canonical=canonical)
        if canonical:
            self.receipt.pop("canonical_fingerprint_compile", None)
            row["scope"] = "Fresh canonical native-only authored module; no closed supplier theorem"
        return row

    def canonical_type_and_axiom_audit(self):
        module = "OPICAStep4.NativeTypesAudit"
        source = self.sources / old.module_path(module, ".lean")
        lines = ["import OPICAStep4.NativeValidated", "set_option pp.fullNames true",
                 "set_option pp.universes true", "set_option pp.maxSteps 100000"]
        for name in AUDIT_NAMES:
            lines += ['#eval IO.println "OPICA19_TYPE_BEGIN ' + name + '"', "#check @" + name,
                      '#eval IO.println "OPICA19_TYPE_END ' + name + '"', "#print axioms " + name]
        source.write_text("\n".join(lines) + "\n")
        self.bind(source)
        row = self.compile_module(module, "canonical_native_type_commands", canonical=True)
        data = old.parse_audit(Path(row["log"]).read_text(), list(AUDIT_NAMES), set(self.spec["allowed_axioms"]))
        self.bind_log(Path(row["log"]))
        target = self.output / "CANONICAL_NATIVE_TYPES_AND_AXIOMS.json"
        json_write(target, data)
        return {"targets": list(AUDIT_NAMES), "report": str(target), "sha256": self.bind(target),
                "allowed_axioms": self.spec["allowed_axioms"]}

    def streamed_export(self, name, module, names, *, canonical=False, expected_sha=None, artifact=None,
                        max_bytes=8 << 30):
        result = stream_command([self.exporter, module, "--", *names], cwd=self.sources,
            env=self.canonical_env if canonical else self.env, log=self.output / (name + ".log"),
            record=self.output / (name + ".process.json"), timeout=self.args.export_timeout,
            max_bytes=max_bytes, expected_sha=expected_sha, stdout_path=artifact)
        result.update(module=module, explicit_export_targets=list(names), exporter_sha256=self.bind(self.exporter))
        self.bind_log(Path(result["log"]))
        self.bind(self.output / (name + ".process.json"))
        if artifact:
            result.update(export=str(artifact), export_sha256=self.bind(artifact))
        return result

    def canonical_fingerprint_export(self):
        return self.streamed_export("canonical_fingerprint_export", self.spec["fingerprint_module"],
            [*AUX_TARGETS, *self.spec["fingerprint_theorems"]], canonical=True,
            artifact=self.output / "canonical-fingerprint.ndjson", max_bytes=2 << 30)

    def canonical_native_proof_export(self):
        result = self.streamed_export("canonical_native_proof_export", "OPICAStep4.NativeValidated",
                                     [*AUX_TARGETS, *AUDIT_NAMES], canonical=True)
        self.canonical_native_proof_sha = result["stdout_sha256"]
        self.canonical_native_proof_bytes = result["stdout_bytes"]
        result["scope"] = "Full proof values and transitive dependencies for every native target used by the delta"
        return result

    def complete_native_fresh_kernel_replay(self):
        result = self.run_process("complete_native_fresh_kernel_replay",
            [str(self.checker), "--fresh", "--verbose", "OPICAStep4.NativeValidated"], self.sources,
            self.args.fresh_timeout, env=self.canonical_env)
        self.bind_log(Path(result["log"]))
        self.receipt["native_full_kernel_execution"] = "LOCAL_PASS"
        result.update(scope="Complete imported native-only environment and all aggregate declarations",
                      independent_kernel_implementation=False)
        return result

    def comparison_controls(self):
        if self.args.comparator_lake:
            return super().comparison_controls()
        control = self.package / "comparison_control/test_statement_definitions.py"
        out = self.output / "definition-controls"
        row = self.run_process("comparison_helper_controls", [sys.executable, str(control),
            "--lean", str(self.lean), "--exporter", str(self.exporter),
            "--comparison-helper", str(self.comparison_helper), "--output", str(out)],
            self.output, self.args.comparison_timeout, env=self.canonical_env)
        path = out / "DEFINITION_COMPARISON_CONTROL.json"
        data = json.loads(path.read_text())
        require(data.get("status") == "PASS" and data.get("matching_definition") == "ACCEPTED" and
                data.get("changed_definition") == "REJECTED_AT_REQUIRED_C1_BODY",
                "Comparison helper did not pass both exact semantic controls")
        for file in out.rglob("*"):
            if file.is_file() and file.stat().st_size:
                self.bind(file)
        self.bind_log(Path(row["log"]))
        return {"helper_control": str(path), "sha256": self.bind(path),
                "same_definition": "ACCEPTED", "changed_definition": "REJECTED_AT_REQUIRED_C1_BODY",
                "official_comparator": "NOT_RUN_OPTIONAL", "c1_or_rh_proved_by_controls": False}

    def canonical_objects_promotion(self):
        rows = []
        for module in CANONICAL_MODULES:
            for suffix in (".olean", ".olean.private", ".olean.server", ".ir", ".ilean"):
                relative = old.module_path(module, suffix)
                src, dst = self.canonical_lib / relative, self.lib / relative
                if not src.exists():
                    continue
                expected = self.bind(src)
                require(not dst.exists(), "Combined authored object path is not fresh")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                require(self.bind(dst) == expected, "Promoted canonical object changed")
                rows.append({"path": str(dst), "sha256": expected})
        return {"exact_canonical_artifacts_promoted": rows,
                "scope": "Same namespace root contains every authored OPICAStep4 import"}

    def kernel_construct(self, module, mode, stage_name):
        obj = self.lib / old.module_path(module, ".olean")
        obj.parent.mkdir(parents=True, exist_ok=True)
        artifact_pattern = module.rsplit(".", 1)[-1] + ".*"
        require(not list(obj.parent.glob(artifact_pattern)), "Kernel construction output and sidecars must be fresh")
        row = self.run_process(stage_name, [str(self.kernel_producer), mode, str(obj)],
            self.sources, self.args.compile_timeout, env=self.env)
        require_file(obj, "Kernel producer returned without the required ordinary object")
        require(set(obj.parent.glob(artifact_pattern)) == {obj},
                "Kernel producer created an unexpected module sidecar")
        row.update(module=module, products={".olean": {"path": str(obj), "sha256": self.bind(obj)}},
            original_lean_specification_sha256=self.bind(self.sources / old.module_path(module, ".lean")),
            producer_sha256=self.bind(self.kernel_producer),
            production="STOCK_KERNEL_CHECKED_DECLARATIONS_AND_STOCK_MODULE_DATA_WRITER",
            source_elaborator_compilation="NOT_RUN", new_elaborator_extension_entries="EMPTY")
        self.compiled[module] = row
        self.bind_log(Path(row["log"]))
        return row

    def guarded_kernel_import(self):
        row = self.kernel_construct("OPICAStep4.ImportGuard", "guard", "guarded_kernel_import")
        text = Path(row["log"]).read_text()
        require(text.count("OPICA20_NEW_NAMES_ABSENT") == 1, "Preexisting-name guard success marker missing or duplicated")
        self.bind_log(Path(row["log"]))
        obj = self.lib / old.module_path("OPICAStep4.ImportGuard", ".olean")
        audit = self.run_process("actual_guard_object_audit", [str(self.lean),
            "-DwarningAsError=true", "-DrelaxedAutoImplicit=false", "--run", str(self.inspector),
            str(obj), "--guard"], self.sources, 120, env=self.canonical_env)
        audit_text = Path(audit["log"]).read_text()
        require(audit_text.splitlines().count("OPICA21_GUARD_OBJECT_AUDIT_PASS") == 1,
                "Actual guard object audit marker missing or duplicated")
        self.bind_log(Path(audit["log"]))
        row["raw_object_audit"] = audit
        return row

    def fresh_closed_kernel_construction(self):
        row = self.kernel_construct(CLOSED_MODULE, "closed", "fresh_closed_kernel_construction")
        text = Path(row["log"]).read_text()
        row["ordered_safe_roots"] = parse_selected_root_audit(text)
        row["mathematical_theorem_roots"] = list(MATHEMATICAL_ROOTS)
        require(text.splitlines().count("OPICA21_KERNEL_CLOSED_OBJECT_PASS") == 1,
                "Kernel construction did not complete its actual object and axiom audits")
        self.receipt["fresh_closed_object_production"] = "STOCK_KERNEL_CHECKED_ACTUAL_THREE_THEOREMS"
        return row

    def actual_closed_object_audit(self):
        obj = self.lib / old.module_path(CLOSED_MODULE, ".olean")
        row = self.run_process("actual_closed_object_audit", [str(self.lean),
            "-DwarningAsError=true", "-DrelaxedAutoImplicit=false", "--run", str(self.inspector), str(obj)],
            self.sources, self.args.compile_timeout, env=self.canonical_env)
        text = Path(row["log"]).read_text()
        names = re.findall(r"(?m)^OPICA20_ACTUAL_THEOREM (\S+)\s*$", text)
        require(len(names) == len(CLOSED_TYPES) and set(names) == set(CLOSED_TYPES),
                "Actual object audit did not cover exactly the three required theorem declarations")
        require(text.count("OPICA20_CLOSED_OBJECT_AUDIT_PASS") == 1,
                "Actual raw object audit lacks its unique success marker")
        self.bind_log(Path(row["log"]))
        row.update(object_sha256=self.bind(obj), inspector_sha256=self.bind(self.inspector),
            closed_types=dict(CLOSED_TYPES),
            checked="Raw theorem kind, closed type, proof value, constant ownership and direct dependency coverage")
        return row

    def closed_type_and_axiom_audit(self):
        log = Path(self.compiled[CLOSED_MODULE]["log"])
        data = old.parse_audit(log.read_text(), ["riemannHypothesis", *CLOSED_TYPES],
                               set(self.spec["allowed_axioms"]))
        for name, target in {"riemannHypothesis": "RiemannHypothesis", **CLOSED_TYPES}.items():
            compact = " ".join(data[name]["type"].split())
            require(compact in (name + " : " + target, "@" + name + " : " + target),
                    "Closed theorem has a substituted type or hidden parameter: " + name)
        self.bind_log(log)
        path = self.output / "CLOSED_TYPES_AND_TRANSITIVE_AXIOMS.json"
        json_write(path, data)
        return {"report": str(path), "sha256": self.bind(path), "declarations": len(data),
                "allowed_axioms": self.spec["allowed_axioms"]}

    def new_module_replay(self, module, name):
        row = self.replay(module, name)
        self.bind_log(Path(row["log"]))
        if module == CLOSED_MODULE:
            self.receipt["new_closed_declarations_kernel_execution"] = "LOCAL_PASS"
        return row

    def final_native_proof_export_identity(self):
        row = self.streamed_export("final_native_proof_export_identity", CLOSED_MODULE,
                                  [*AUX_TARGETS, *AUDIT_NAMES], expected_sha=self.canonical_native_proof_sha)
        require(row["stdout_bytes"] == self.canonical_native_proof_bytes,
                "Native proof export byte count differs despite matching digest")
        row["scope"] = "Exact native proof values and complete dependencies in the actual final environment"
        return row

    def final_fingerprint_export(self):
        return self.streamed_export("final_fingerprint_export", CLOSED_MODULE,
            [*AUX_TARGETS, *self.spec["fingerprint_theorems"]],
            artifact=self.output / "final-fingerprint.ndjson", max_bytes=2 << 30)

    def canonical_statement_definition_comparison(self):
        row = self.run_process("canonical_statement_definition_comparison", [str(self.comparison_helper),
            str(self.output / "canonical-fingerprint.ndjson"), str(self.output / "final-fingerprint.ndjson"),
            *self.spec["fingerprint_theorems"]], self.output, self.args.comparison_timeout,
            env=self.canonical_env)
        require(Path(row["log"]).read_text().count("OPICA19_DEFINITION_COMPARISON_PASS") == 1,
                "Definition comparison lacks its unique success marker")
        self.bind_log(Path(row["log"]))
        row.update(scope="All canonical statement definitions with no open definition holes; no proof authority",
                   definition_names=[], targets=self.spec["fingerprint_theorems"])
        return row

    def final_supplier_certificate_identity(self):
        row = self.streamed_export("final_supplier_certificate_identity", CLOSED_MODULE,
            SUPPLIER_TARGETS, expected_sha=SUPPLIER_SHA, max_bytes=128 << 30)
        row.update(published_bytes=SUPPLIER_PUBLISHED_BYTES,
                   published_byte_count_matches=row["stdout_bytes"] == SUPPLIER_PUBLISHED_BYTES,
                   byte_count_discrepancy=(None if row["stdout_bytes"] == SUPPLIER_PUBLISHED_BYTES else
                       "Published prose count differs; exact required SHA256 still matches"),
                   kernel_execution="EXTERNAL_PUBLISHED_RECEIPT",
                   scope="Complete original supplier certificate exported from the actual final combined importer")
        self.receipt["supplier_certificate_identity"] = "MATCHES_PUBLISHED_FULL_CERTIFICATE"
        return row

    def final_integrity(self):
        require(self.supplier_mount() == self.supplier_mount_identity,
                "Supplier object mount identity or read-only property changed")
        require(old.git_text(self.exporter_source, "rev-parse", "HEAD") == EXPORTER_COMMIT,
                "Exporter source checkout changed")
        old.no_tracked_changes(self.exporter_source, self.exporter_protected_paths)
        result = super().final_integrity()
        result.update(supplier_store_still_read_only=True,
                      scope="All registered object inventories and every bound input/product rehashed")
        return result

    def execute(self):
        actions = {name: getattr(self, name) for name in STAGES if hasattr(self, name)}
        actions.update(
            import_guard_kernel_replay=lambda: self.new_module_replay("OPICAStep4.ImportGuard", "import_guard_kernel_replay"),
            closed_module_kernel_replay=lambda: self.new_module_replay(CLOSED_MODULE, "closed_module_kernel_replay"),
            final_input_integrity=self.final_integrity)
        code = 1
        try:
            for name in STAGES:
                self.stage(name, actions[name])
            require(all(row["status"] == "PASS" for row in self.receipt["stages"]), "A modular stage did not pass")
            required_scope = {
                "supplier_certificate_identity": "MATCHES_PUBLISHED_FULL_CERTIFICATE",
                "supplier_kernel_execution": "EXTERNAL_PUBLISHED_RECEIPT",
                "native_full_kernel_execution": "LOCAL_PASS",
                "new_closed_declarations_kernel_execution": "LOCAL_PASS",
                "full_combined_export_kernel_execution": "NOT_RUN_BY_THIS_GATE",
                "prior_round19_25_stage_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
                "fresh_closed_object_production": "STOCK_KERNEL_CHECKED_ACTUAL_THREE_THEOREMS",
                "closed_source_elaborator_compilation": "NOT_RUN_BY_THIS_GATE",
            }
            require(all(self.receipt.get(k) == v for k, v in required_scope.items()),
                    "Completed stage scope does not support the required modular claim")
            self.receipt.update(status="PASS",
                closure_claim="EXACT_NATIVE_C1_AT_COMMON_PIN_UNDER_EXPLICIT_EXTERNAL_SUPPLIER_CERTIFICATE_MODEL",
                claim=("Exact native C1 was constructed as an ordinary checked theorem object by the stock kernel "
                       "and passed modular kernel/definition/axiom checks at the "
                       "recorded common pin, using a supplier certificate byte-identical to the independently "
                       "verified published artifact."))
            code = 0
        except (GateBlocked, GateIncomplete) as exc:
            self.receipt.update(status="BLOCKED" if isinstance(exc, GateBlocked) else "INCOMPLETE", failure=str(exc))
            code = 2
        except KeyboardInterrupt:
            self.receipt.update(status="INTERRUPTED", failure="Interrupted by operator")
            code = 130
        except Exception as exc:
            self.receipt.update(status="FAIL", failure=str(exc), exception_type=type(exc).__name__)
        finally:
            self.receipt.update(ended_utc=old.utc_now(), exit_code=code)
            self.save()
            print(self.receipt["status"] + ": " + self.receipt["closure_claim"], flush=True)
            print("Receipt: " + str(self.output / "MODULAR_GATE_RECEIPT.json"), flush=True)
            if self.receipt.get("failure"):
                print(self.receipt["failure"], file=sys.stderr, flush=True)
        return code


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("external", "integration", "lake", "exporter", "comparison-helper"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("native", "external-lib", "native-receipt", "comparator-lake", "output",
                 "external-evidence", "exporter-source"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--external-head", help="Explicit full infrastructure descendant commit; source tree remains frozen")
    for name, default in (("jobs", 2), ("max-heartbeats", 1600000), ("compile-timeout", 7200),
                          ("replay-timeout", 14400), ("fresh-timeout", 86400),
                          ("export-timeout", 86400), ("comparison-timeout", 7200)):
        parser.add_argument("--" + name, type=int, default=default)
    args = parser.parse_args(argv)
    for key, value in vars(args).items():
        if isinstance(value, int) and value <= 0:
            parser.error(key.replace("_", "-") + " must be positive")
    return args


def main():
    try:
        gate = ModularGate(arguments())
    except Exception as exc:
        print("BLOCKED before modular gate initialization: " + str(exc), file=sys.stderr)
        return 2
    return gate.execute()


if __name__ == "__main__":
    raise SystemExit(main())
