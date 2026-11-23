#!/usr/bin/env python3
"""Executable semantic control for the upstream definition comparison only.

Build compare_exports first with Lean 4.33.1. This test never imports the RH
solution or native C1 and makes no theorem-closure or kernel-replay claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

TARGET = "OPICA19Control.statementFingerprint"
DEFINITION = "OPICA19Control.requiredC1"
EXPORT_TARGETS = [
    "Quot", "Quot.mk", "Quot.lift", "Quot.ind", TARGET,
    "propext", "Quot.sound", "Classical.choice", "Nat.add", "Nat.sub", "Nat.mul",
    "Nat.pow", "Nat.gcd", "Nat.div", "Nat.mod", "Nat.beq", "Nat.ble", "Nat.land",
    "Nat.lor", "Nat.xor", "Nat.shiftLeft", "Nat.shiftRight", "String.ofList",
    "Char.ofNat", "List", "eagerReduce", "Nat", "String", "String.mk", "Char",
    "optParam", "autoParam", "semiOutParam", "outParam",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--exporter", type=Path, required=True)
    parser.add_argument("--comparison-helper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise SystemExit("Output directory must be fresh and empty")
    root.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": 1, "status": "RUNNING", "scope": "Statement comparison controls only",
               "c1_or_rh_proved": False, "kernel_replay": "NOT_RUN", "processes": []}

    def save():
        (root / "DEFINITION_COMPARISON_CONTROL.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def run(label, argv, cwd, env, expected=0, stdout=None):
        out_file = stdout or root / (label + ".log")
        err_file = root / (label + ".stderr.log")
        with out_file.open("wb") as out, err_file.open("wb") as err:
            completed = subprocess.run([str(item) for item in argv], cwd=cwd, env=env,
                                       stdout=out, stderr=err, timeout=300, check=False)
        row = {"name": label, "command": [str(item) for item in argv],
               "cwd": str(cwd), "exit_code": completed.returncode,
               "expected_exit_code": expected, "stdout": str(out_file),
               "stdout_sha256": digest(out_file), "stderr": str(err_file),
               "stderr_sha256": digest(err_file)}
        receipt["processes"].append(row)
        save()
        if completed.returncode != expected:
            raise RuntimeError(label + " returned an unexpected exit code: " + str(completed.returncode))
        return out_file.read_text() + err_file.read_text()

    try:
        lean = args.lean.resolve()
        exporter = args.exporter.resolve()
        helper = args.comparison_helper.resolve()
        base_env = dict(os.environ)
        base_env["PATH"] = str(lean.parent) + os.pathsep + base_env.get("PATH", "")
        base_env["LEAN_ABORT_ON_PANIC"] = "1"
        for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LAKE_CONFIG"):
            base_env.pop(key, None)
        version = run("compiler_version", [lean, "--version"], root, base_env)
        if "version 4.33.1," not in version:
            raise RuntimeError("Control requires the same Lean 4.33.1 exporter/compiler pair")
        receipt["tools"] = {name: {"path": str(path), "sha256": digest(path)}
                            for name, path in [("lean", lean), ("exporter", exporter), ("helper", helper)]}
        exports = {}
        for variant, value in [("challenge", "True"), ("matching", "True"), ("substituted", "False")]:
            work = root / variant
            work.mkdir()
            source = work / "Control.lean"
            source.write_text("namespace OPICA19Control\n" +
                              "def requiredC1 : Prop := " + value + "\n" +
                              "theorem statementFingerprint : requiredC1 ↔ requiredC1 := Iff.rfl\n" +
                              "end OPICA19Control\n")
            env = dict(base_env)
            env["LEAN_PATH"] = str(work)
            run(variant + "_compile", [lean, "-DwarningAsError=true", "-o", work / "Control.olean",
                                      "Control.lean"], work, env)
            export = root / (variant + ".ndjson")
            run(variant + "_export", [exporter, "Control", "--", *EXPORT_TARGETS], work, env,
                stdout=export)
            exports[variant] = export
        positive = run("matching_comparison", [helper, exports["challenge"], exports["matching"], TARGET],
                       root, base_env)
        if "OPICA19_DEFINITION_COMPARISON_PASS" not in positive:
            raise RuntimeError("Positive control produced no exact success marker")
        negative = run("substituted_comparison", [helper, exports["challenge"], exports["substituted"], TARGET],
                       root, base_env, expected=1)
        if "Const does not match between challenge and target" not in negative or DEFINITION not in negative:
            raise RuntimeError("Negative control failed for a different reason than the changed definition")
        receipt.update(status="PASS", matching_definition="ACCEPTED",
                       changed_definition="REJECTED_AT_REQUIRED_C1_BODY")
        print("PASS: ordinary theorem fingerprints detect a changed proposition definition.")
        print("This is a comparator control, not C1 or RH proof validation.")
        return 0
    except Exception as exc:
        receipt.update(status="FAIL", failure=str(exc), exception_type=type(exc).__name__)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        save()


if __name__ == "__main__":
    raise SystemExit(main())
