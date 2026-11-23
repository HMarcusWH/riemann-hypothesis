#!/usr/bin/env python3
"""Strict OPICA C1 integration gate. Python 3.11+; no third-party modules.

This runner never builds or updates either dependency repository. It consumes an
existing complete original proof build and the separately recorded common-pin
native rebuild. It separately exports canonical statement definitions, then
freshly compiles the closed bridge, named consumers and comparison binding.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import uuid


class GateFailure(RuntimeError):
    pass


class GateBlocked(GateFailure):
    pass


class GateIncomplete(GateFailure):
    pass


STAGES = (
    "source_identity",
    "external_endpoint_presence",
    "canonical_environment",
    "verification_tools",
    "native_build_receipt",
    "canonical_dependency_snapshot",
    "canonical_fingerprint_compile",
    "canonical_fingerprint_export",
    "compatible_environment",
    "shared_dependency_comparison",
    "complete_object_snapshot",
    "comparison_controls",
    "combined_fingerprint_compile",
    "fresh_bridge_compile",
    "fresh_named_consumer_compile",
    "closed_fingerprint_consumer_compile",
    "complete_type_and_axiom_audit",
    "closed_solution_export",
    "closed_export_type_and_axiom_audit",
    "canonical_statement_comparison",
    "bridge_kernel_replay",
    "named_consumer_kernel_replay",
    "closed_fingerprint_consumer_kernel_replay",
    "complete_fresh_kernel_replay",
    "final_input_integrity",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def require_file(path: Path, message: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise GateBlocked(message + ": " + str(path))


def module_path(module: str, suffix: str) -> Path:
    require(bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*",
                              module)), "Invalid module name: " + module)
    return Path(*module.split(".")).with_suffix(suffix)


def command_bytes(argv: list[str], cwd: Path, env=None, timeout=180) -> bytes:
    try:
        completed = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateBlocked("Cannot inspect required environment: " + str(exc)) from exc
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace")[-3000:]
        raise GateBlocked("Inspection command failed: " + repr(argv) + "\n" + detail)
    return completed.stdout


def git_text(repo: Path, *args: str) -> str:
    return command_bytes(["git", "-C", str(repo), *args], repo).decode("utf-8").strip()


def tree_inventory_without_challenge(repo: Path, excluded_path: str) -> tuple[str, int]:
    raw = command_bytes(["git", "-C", str(repo), "ls-tree", "-rz", "--full-tree",
                         "HEAD", "--", "src"], repo)
    records = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        header, path = record.split(b"\t", 1)
        if path.decode("utf-8") == excluded_path:
            continue
        mode, kind, digest = header.split()
        require(kind == b"blob" and mode in (b"100644", b"100755"),
                "Unexpected external source tree entry: " + repr(record[:160]))
        require(bool(re.fullmatch(rb"[0-9a-f]{40}", digest)),
                "Invalid external Git blob identity")
        records.append(record)
    canonical = b"\0".join(sorted(records)) + b"\0"
    return hashlib.sha256(canonical).hexdigest(), len(records)


def no_tracked_changes(repo: Path, paths: list[str]) -> None:
    result = subprocess.run(["git", "-C", str(repo), "diff", "--quiet", "HEAD", "--", *paths],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "Protected source or pin differs from HEAD: " + str(repo))
    others = git_text(repo, "ls-files", "--others", "--exclude-standard", "--", *paths)
    unexpected = [line for line in others.splitlines() if line.endswith(".lean")]
    require(not unexpected, "Untracked Lean source in a protected source tree: " +
            repr(unexpected[:10]))


def mathlib_revision(manifest: Path) -> str:
    require_file(manifest, "Missing package manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    packages = [p for p in data.get("packages", []) if p.get("name") == "mathlib"]
    require(len(packages) == 1, "Manifest must contain exactly one mathlib package")
    require(packages[0].get("type") == "git", "Mathlib must retain a pinned Git identity")
    revision = packages[0].get("rev")
    require(isinstance(revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", revision)),
            "Mathlib revision is not a full commit hash")
    return revision


def strip_lean_comments(text: str) -> str:
    # Needed only for the controlled native import closure, not as a proof parser.
    result = []
    depth = 0
    index = 0
    in_string = False
    while index < len(text):
        pair = text[index:index + 2]
        char = text[index]
        if depth:
            if pair == "/-":
                depth += 1
                index += 2
            elif pair == "-/":
                depth -= 1
                index += 2
            else:
                result.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if in_string:
            result.append(char)
            if char == "\\" and index + 1 < len(text):
                result.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if pair == "/-":
            depth = 1
            result.append("  ")
            index += 2
        elif pair == "--":
            newline = text.find("\n", index)
            if newline < 0:
                break
            result.append("\n")
            index = newline + 1
        else:
            result.append(char)
            if char == '"':
                in_string = True
            index += 1
    require(depth == 0, "Unclosed Lean comment while inspecting imports")
    return "".join(result)


def native_import_closure(repo: Path, endpoint: str) -> set[str]:
    pending = [endpoint]
    found = set()
    while pending:
        module = pending.pop()
        if module in found:
            continue
        source = repo / module_path(module, ".lean")
        require_file(source, "Missing native dependency source")
        text = strip_lean_comments(source.read_text(encoding="utf-8"))
        found.add(module)
        for line in text.splitlines():
            match = re.match(r"^\s*(?:public\s+)?import\s+(.+?)\s*$", line)
            if match:
                for imported in match.group(1).split():
                    if imported.startswith("Zeta23."):
                        pending.append(imported)
    return found


def compiler_diagnostics(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        if (re.search(r"(?:^|\s)(?:error|warning)(?:\[[^\]]*\])?\s*(?::|\()", line,
                      flags=re.IGNORECASE)
                or re.search(r"uncaught exception|PANIC|sorryAx|unsolved goals", line)):
            found.append(line[:1200])
    return found


def parse_audit(text: str, names: list[str], allowed_axioms: set[str]) -> dict:
    types = {}
    for name in names:
        begin = "OPICA19_TYPE_BEGIN " + name
        end = "OPICA19_TYPE_END " + name
        require(text.splitlines().count(begin) == 1 and text.splitlines().count(end) == 1,
                "Missing or duplicate complete-type marker for " + name)
        match = re.search(r"(?m)^" + re.escape(begin) + r"\n(.*?)\n" +
                          re.escape(end) + r"$", text, re.DOTALL)
        require(match is not None, "Malformed complete-type record for " + name)
        declared = match.group(1).strip()
        require(bool(re.match(r"^@?" + re.escape(name) + r"(?:\.\{[^}]*\})?\s*:",
                              declared)),
                "Unexpected declaration in complete-type record for " + name)
        require("..." not in declared and "⋯" not in declared,
                "Truncated type output for " + name)
        types[name] = {"type": declared}
    axioms = {}
    for name, raw in re.findall(r"'([^']+)' depends on axioms:\s*\[([^\]]*)\]",
                                text, flags=re.DOTALL):
        require(name not in axioms, "Duplicate axiom report for " + name)
        # Full universe printing decorates polymorphic standard axioms, e.g.
        # Classical.choice.{u}. Strip only complete trailing level annotations,
        # never namespace components or a non-standard constant's name.
        normalized = re.sub(r"([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)"
                            r"\.\{[^{}]*\}", r"\1", raw)
        atoms = [word.strip() for word in normalized.replace("\n", " ").split(",") if word.strip()]
        require(set(atoms) <= allowed_axioms,
                "Forbidden transitive axiom for " + name + ": " + repr(atoms))
        axioms[name] = atoms
    for name in re.findall(r"'([^']+)' does not depend on any axioms", text):
        require(name not in axioms, "Duplicate axiom report for " + name)
        axioms[name] = []
    require(set(axioms) == set(names), "Missing, extra or substituted theorem axiom reports")
    for name in names:
        types[name]["axioms"] = axioms[name]
    return types


class Gate:
    def __init__(self, args):
        self.args = args
        self.package = Path(__file__).resolve().parent
        self.spec_file = self.package / "GATE_SPEC.json"
        self.spec = json.loads(self.spec_file.read_text(encoding="utf-8"))
        self.external = args.external.resolve()
        self.integration = args.integration.resolve()
        require(self.external.is_dir() and self.integration.is_dir(),
                "Both --external and --integration must be existing directories")
        self.native = args.native.resolve() if args.native else self.find_native()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.output = (args.output.resolve() if args.output else
                       self.integration.parent / "opica-step4-verification" /
                       (stamp + "-" + uuid.uuid4().hex[:8]))
        require(not self.output.is_relative_to(self.external) and
                not self.output.is_relative_to(self.native),
                "Gate output must stay outside both governed source checkouts")
        require(not self.output.exists() or not any(self.output.iterdir()),
                "Output directory must be fresh and empty")
        self.output.mkdir(parents=True, exist_ok=True)
        self.sources = self.output / "sources"
        self.lib = self.output / "lib"
        self.canonical_lib = self.output / "canonical-lib"
        self.sources.mkdir()
        self.lib.mkdir()
        self.canonical_lib.mkdir()
        self.native_lib = self.integration / ".lake/build/lib/lean"
        self.external_lib = (args.external_lib.resolve() if args.external_lib else
                             self.external / ".lake/build/lib/lean")
        self.env = dict(os.environ)
        self.env["LEAN_ABORT_ON_PANIC"] = "1"
        self.canonical_env = None
        self.canonical_packages = {}
        self.combined_packages = {}
        self.object_root_inventories = {}
        self.canonical_package_inventories = {}
        self.exporter = None
        self.comparator_lake = None
        self.comparator_env = None
        self.lean = None
        self.checker = None
        self.input_hashes = {}
        self.compiled = {}
        self.receipt = {
            "schema": "OPICA_STEP4_COMBINED_STRICT_GATE_V2",
            "status": "RUNNING",
            "closure_claim": "NOT_ESTABLISHED",
            "native_round4_production_acceptance": "NOT_RUN_NOT_CLAIMED",
            "native_original_pin_rebuild": "NOT_RUN_NOT_CLAIMED",
            "external_source_to_object_provenance": "NOT_ESTABLISHED_BY_OBJECT_HASH_SNAPSHOTS",
            "fingerprints_prove_c1_or_rh": False,
            "started_utc": utc_now(),
            "external": str(self.external),
            "integration": str(self.integration),
            "native": str(self.native),
            "output": str(self.output),
            "runner_sha256": sha256(Path(__file__)),
            "spec_sha256": sha256(self.spec_file),
            "stages": [{"name": name, "status": "NOT_RUN"} for name in STAGES],
        }
        self.save()

    def find_native(self) -> Path:
        config = self.integration / "lakefile.toml"
        require_file(config, "Missing integration Lake configuration")
        data = tomllib.loads(config.read_text(encoding="utf-8"))
        choices = [item for item in data.get("lean_lib", [])
                   if item.get("name") == "Zeta23"]
        require(len(choices) == 1, "Cannot infer exactly one Zeta23 source library; use --native")
        src = choices[0].get("srcDir", ".")
        require(isinstance(src, str), "Invalid Zeta23 srcDir")
        return (self.integration / src).resolve()

    def save(self):
        json_write(self.output / "COMBINED_GATE_RECEIPT.json", self.receipt)

    def bind(self, path: Path) -> str:
        require_file(path, "Required input missing")
        # Keep the path by which the input will be opened. Resolving its last
        # symlink here would miss a later retargeting of that symlink.
        key = str(path.absolute())
        value = sha256(path)
        if key in self.input_hashes:
            require(self.input_hashes[key] == value, "Input changed while binding: " + key)
        self.input_hashes[key] = value
        return value

    def stage(self, name, action):
        row = next(row for row in self.receipt["stages"] if row["name"] == name)
        row.update(status="RUNNING", started_utc=utc_now())
        self.save()
        print("Running " + name.replace("_", " ") + ".", flush=True)
        started = time.monotonic()
        try:
            details = action()
            row.update(status="PASS", details=details)
        except KeyboardInterrupt:
            row.update(status="INTERRUPTED", failure="Interrupted by operator")
            raise
        except GateBlocked as exc:
            row.update(status="BLOCKED", failure=str(exc))
            raise
        except GateIncomplete as exc:
            row.update(status="INCOMPLETE", failure=str(exc))
            raise
        except Exception as exc:
            row.update(status="FAIL", failure=str(exc), exception_type=type(exc).__name__)
            raise
        finally:
            row.update(ended_utc=utc_now(), elapsed_seconds=round(time.monotonic() - started, 3))
            json_write(self.output / (name + ".json"), row)
            self.save()

    def run_process(self, name, argv, cwd, timeout, *, env=None, stdout_path=None):
        log = self.output / (name + ".log")
        row = {"command": [str(x) for x in argv], "cwd": str(cwd),
               "log": str(log), "started_utc": utc_now(), "status": "RUNNING"}
        json_write(self.output / (name + ".process.json"), row)
        process = None
        started = time.monotonic()
        try:
            with ExitStack() as stack:
                stream = stack.enter_context(log.open("wb"))
                out_stream = stream
                if stdout_path is not None:
                    require(not stdout_path.exists(), "Export output was not fresh")
                    stdout_path.parent.mkdir(parents=True, exist_ok=True)
                    out_stream = stack.enter_context(stdout_path.open("wb"))
                    row["stdout_artifact"] = str(stdout_path)
                process = subprocess.Popen(argv, cwd=cwd, env=env or self.env, stdout=out_stream,
                                           stderr=stream, start_new_session=True)
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                        row["status"] = "TIMEOUT"
                        raise GateIncomplete(name + " exceeded its time budget; no pass is inferred")
                    time.sleep(0.5)
            row["exit_code"] = process.returncode
            row["status"] = "PASS" if process.returncode == 0 else "FAIL"
            text = log.read_text(encoding="utf-8", errors="replace")
            diagnostics = compiler_diagnostics(text)
            row["diagnostics"] = diagnostics
            require(process.returncode == 0, name + " exited with " + str(process.returncode))
            require(not diagnostics, name + " emitted an error, warning or invalid-proof diagnostic")
            return row
        except KeyboardInterrupt:
            row["status"] = "INTERRUPTED"
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise
        except Exception:
            if row["status"] in ("RUNNING", "PASS"):
                row["status"] = "FAIL"
            raise
        finally:
            if process is not None:
                row["exit_code"] = process.returncode
            row["ended_utc"] = utc_now()
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            if log.exists():
                row["log_sha256"] = sha256(log)
            if stdout_path is not None and stdout_path.exists():
                row["stdout_artifact_sha256"] = sha256(stdout_path)
            json_write(self.output / (name + ".process.json"), row)

    def source_identity(self):
        s = self.spec
        external_head = git_text(self.external, "rev-parse", "HEAD")
        if self.args.external_head:
            require(bool(re.fullmatch(r"[0-9a-f]{40}", self.args.external_head)),
                    "--external-head must be a full lowercase commit hash")
            require(external_head == self.args.external_head, "External HEAD differs from explicit pin")
        else:
            require(external_head in s["recognized_external_heads"],
                    "Unrecognized external HEAD; supply an explicit --external-head")
        external_tree = git_text(self.external, "rev-parse", "HEAD^{tree}")
        native_head = git_text(self.native, "rev-parse", "HEAD")
        native_tree = git_text(self.native, "rev-parse", "HEAD^{tree}")
        require(native_head == s["native_head"] and native_tree == s["native_tree"],
                "Native source head/tree differs from the reviewed C1 source")
        no_tracked_changes(self.external, ["src", "lean-toolchain", "lake-manifest.json",
                                          "lakefile.toml"])
        no_tracked_changes(self.native, ["Zeta23", "lean-toolchain", "lake-manifest.json"])
        digest, count = tree_inventory_without_challenge(self.external, s["external_excluded_path"])
        require(digest == s["external_source_inventory_sha256_without_challenge"] and
                count == s["external_source_inventory_entries_without_challenge"],
                "External proof source differs from the complete reviewed source inventory")
        pins = {}
        for label, root, expected in [
                ("external", self.external, s["integration_toolchain"]),
                ("integration", self.integration, s["integration_toolchain"]),
                ("native", self.native, s["native_toolchain"])]:
            path = root / "lean-toolchain"
            require_file(path, "Missing " + label + " toolchain pin")
            actual = path.read_text(encoding="utf-8").strip()
            require(actual == expected, label + " toolchain pin changed")
            pins[label] = {"toolchain": actual, "toolchain_sha256": self.bind(path)}
            manifest = root / "lake-manifest.json"
            pins[label]["manifest_sha256"] = self.bind(manifest)
            if label != "native":
                require(mathlib_revision(manifest) == s["mathlib_rev"],
                        label + " Mathlib pin differs from the common pin")
        self.bind(self.integration / "lakefile.toml")
        self.bind(self.spec_file)
        self.bind(Path(__file__))
        require(self.bind(self.package / "comparator.json") == s["comparator_config_sha256"],
                "Comparator configuration differs from its reviewed version")
        comparison = json.loads((self.package / "comparator.json").read_text())
        require(comparison.get("definition_names") == [] and
                comparison.get("theorem_names") == s["fingerprint_theorems"],
                "Statement fingerprints must be ordinary theorem targets, without definition holes")
        for relative, expected in s["comparison_control_sha256"].items():
            require(self.bind(self.package / "comparison_control" / relative) == expected,
                    "Comparison helper or control source changed: " + relative)
        for relative, expected in s["source_sha256"].items():
            source = self.package / relative
            require(self.bind(source) == expected, "Portable proof source changed: " + relative)
            text = strip_lean_comments(source.read_text(encoding="utf-8"))
            require(not re.search(r"\b(?:sorry|sorryAx|admit|axiom)\b", text),
                    "Placeholder or new axiom in portable proof source")
            require(not re.search(r"(?m)^\s*example\b", text),
                    "Anonymous examples are forbidden in the claim-validation modules")
            destination = self.sources / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            require(self.bind(destination) == expected, "Copied portable source changed")
        self.receipt["source_binding"] = {
            "external_head": external_head, "external_tree": external_tree,
            "external_head_label": s["recognized_external_heads"].get(external_head,
                                                                      "Explicitly pinned by operator"),
            "external_source_inventory_sha256_without_challenge": digest,
            "external_source_inventory_entries_without_challenge": count,
            "only_excluded_source": s["external_excluded_path"],
            "native_head": native_head, "native_tree": native_tree, "pins": pins,
        }
        return self.receipt["source_binding"]

    def external_endpoint_presence(self):
        obj = self.external_lib / module_path(self.spec["external_endpoint"], ".olean")
        require_file(obj, "Complete external proof object is missing; source files alone cannot close C1")
        result = {"endpoint_object": str(obj), "endpoint_object_sha256": self.bind(obj)}
        for suffix in (".olean.private", ".olean.server"):
            extra = self.external_lib / module_path(self.spec["external_endpoint"], suffix)
            if extra.exists():
                result[suffix] = {"path": str(extra), "sha256": self.bind(extra)}
        return result

    def lake_environment(self, root):
        lake = str(self.args.lake.resolve()) if self.args.lake else shutil.which("lake")
        if not lake:
            raise GateBlocked("Lake is not on PATH; supply --lake from Lean 4.33.1")
        keys = ("LEAN_PATH", "LEAN_SRC_PATH", "PATH", "LD_LIBRARY_PATH",
                "DYLD_LIBRARY_PATH", "LEAN_SYSROOT")
        expression = ("import json,os; print(json.dumps({k:os.environ[k] for k in " +
                      repr(keys) + " if k in os.environ}))")
        base = dict(os.environ)
        for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LAKE_CONFIG"):
            base.pop(key, None)
        base["LEAN_ABORT_ON_PANIC"] = "1"
        raw = command_bytes([lake, "env", sys.executable, "-c", expression], root,
                            base, timeout=300)
        try:
            selected = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GateBlocked("lake env did not produce a clean environment record") from exc
        require(isinstance(selected, dict) and all(isinstance(x, str) for x in selected.values()),
                "Invalid Lake environment")
        base.update(selected)
        roots = []
        for item in selected.get("LEAN_PATH", "").split(os.pathsep):
            if item:
                path = Path(item)
                roots.append((path if path.is_absolute() else root / path).resolve())
        require(roots, "Lake environment exposed no import roots")
        return base, list(dict.fromkeys(roots))

    def identify_compiler(self, root, env):
        launcher = shutil.which("lean", path=env.get("PATH"))
        if not launcher:
            raise GateBlocked("Lean is absent from the selected Lake environment")
        prefix = Path(command_bytes([launcher, "--print-prefix"], root, env)
                      .decode("utf-8").strip()).resolve()
        lean = prefix / "bin/lean"
        checker = prefix / "bin/leanchecker"
        require_file(lean, "Resolved Lean binary is absent")
        require_file(checker, "Resolved kernel checker is absent")
        version = command_bytes([str(lean), "--version"], root, env).decode("utf-8").strip()
        require(bool(re.search(r"\bversion 4\.33\.1(?:,|\s|$)", version)),
                "Actual compiler is not Lean 4.33.1")
        env["PATH"] = str(prefix / "bin") + os.pathsep + env.get("PATH", "")
        env["LEAN_NUM_THREADS"] = str(self.args.jobs)
        env["LEAN_ABORT_ON_PANIC"] = "1"
        return lean, checker, prefix, version

    def verified_packages(self, root):
        manifest = json.loads((root / "lake-manifest.json").read_text())
        package_dir = manifest.get("packagesDir", ".lake/packages")
        require(isinstance(package_dir, str), "Invalid package directory in manifest")
        packages = {}
        for row in manifest.get("packages", []):
            name = row.get("name")
            rev = row.get("rev")
            require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]+", name),
                    "Unsupported package name")
            require(name not in packages and row.get("type") == "git" and
                    isinstance(rev, str) and re.fullmatch(r"[0-9a-f]{40}", rev),
                    "Each dependency must have one exact Git pin")
            repo = (root / package_dir / name).resolve()
            require(repo.is_dir(), "Missing pinned package: " + name)
            require(git_text(repo, "rev-parse", "HEAD") == rev,
                    "Package checkout differs from its manifest pin: " + name)
            no_tracked_changes(repo, ["."])
            packages[name] = {"root": repo, "revision": rev,
                              "objects": (repo / ".lake/build/lib/lean").resolve()}
        require(packages.get("mathlib", {}).get("revision") == self.spec["mathlib_rev"],
                "Pinned common Mathlib package is absent")
        return packages

    def canonical_environment(self):
        env, roots = self.lake_environment(self.integration)
        lean, checker, prefix, version = self.identify_compiler(self.integration, env)
        self.lean, self.checker, self.toolchain_prefix = lean, checker, prefix
        packages = self.verified_packages(self.integration)
        self.canonical_packages = packages
        allowed = {self.native_lib.resolve(), prefix / "lib/lean"}
        allowed.update(row["objects"] for row in packages.values())
        require(set(roots) <= allowed,
                "Canonical environment contains an unregistered import root")
        require(self.native_lib.resolve() in roots, "Canonical native import root is absent")
        require(all(not path.is_relative_to(self.external) for path in roots),
                "Canonical environment must not resolve external proof objects")
        ordered = list(dict.fromkeys([self.canonical_lib.resolve(), *roots, prefix / "lib/lean"]))
        env["LEAN_PATH"] = os.pathsep.join(str(path) for path in ordered)
        self.canonical_env = dict(env)
        self.env = dict(env)
        self.canonical_roots = ordered
        information = {
            "compiler": str(lean), "compiler_version": version,
            "compiler_sha256": self.bind(lean),
            "kernel_checker": str(checker), "kernel_checker_sha256": self.bind(checker),
            "mathlib_commit": self.spec["mathlib_rev"],
            "import_roots": [str(path) for path in ordered],
            "scope": "Native-only canonical environment before external module loading",
            "jobs": self.args.jobs,
        }
        # The native receipt validator uses this environment before it is replaced
        # by the combined one. The canonical record is retained separately.
        self.receipt["canonical_environment"] = information
        self.receipt["environment"] = dict(information)
        return information

    def compatible_environment(self):
        require_file(self.output / "canonical-fingerprint.ndjson",
                     "Canonical export must be completed before external module loading")
        env, roots = self.lake_environment(self.external)
        lean, checker, prefix, version = self.identify_compiler(self.external, env)
        canonical = self.receipt["canonical_environment"]
        require(self.bind(lean) == canonical["compiler_sha256"] and
                self.bind(checker) == canonical["kernel_checker_sha256"] and
                version == canonical["compiler_version"],
                "Combined and canonical environments use different compiler tools")
        packages = self.verified_packages(self.external)
        self.combined_toolchain_prefix = prefix
        require({name: row["revision"] for name, row in packages.items()} ==
                {name: row["revision"] for name, row in self.canonical_packages.items()},
                "Combined and canonical dependency pins differ")
        self.combined_packages = packages
        allowed = {self.external_lib.resolve(), prefix / "lib/lean"}
        allowed.update(row["objects"] for row in packages.values())
        require(set(roots) <= allowed, "External environment contains an unregistered import root")
        require(self.external_lib.resolve() in roots, "External build root is absent from LEAN_PATH")
        ordered = list(dict.fromkeys([self.lib.resolve(), *roots, self.native_lib.resolve(),
                                      prefix / "lib/lean"]))
        env["LEAN_PATH"] = os.pathsep.join(str(path) for path in ordered)
        self.env = env
        for module, wanted in [(self.spec["external_endpoint"], self.external_lib),
                               (self.spec["native_endpoint"], self.native_lib),
                               ("Mathlib", packages["mathlib"]["objects"])]:
            relative = module_path(module, ".olean")
            found = next((root / relative for root in ordered if (root / relative).is_file()), None)
            require(found is not None and found.resolve() == (wanted / relative).resolve(),
                    "An import root shadows a required object: " + module)
        information = {
            "compiler": str(lean), "compiler_version": version,
            "compiler_sha256": canonical["compiler_sha256"],
            "kernel_checker": str(checker), "kernel_checker_sha256": canonical["kernel_checker_sha256"],
            "mathlib_commit": self.spec["mathlib_rev"],
            "import_roots": [str(path) for path in ordered], "jobs": self.args.jobs,
        }
        self.receipt["environment"] = information
        return information

    def native_build_receipt(self):
        path = (self.args.native_receipt.resolve() if self.args.native_receipt else
                self.integration / "NATIVE_COMMON_PIN_BUILD.json")
        require_file(path, "Missing common-pin native rebuild receipt")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "PASS":
            raise GateBlocked("Native common-pin build is not PASS: " + str(data.get("status")))
        require(data.get("schema") == 1 and data.get("exit_code") == 0,
                "Native build schema or exit code is invalid")
        require(data.get("native_head") == self.spec["native_head"] and
                data.get("native_tree") == self.spec["native_tree"],
                "Native build receipt belongs to a different source")
        require(data.get("common_mathlib_rev") == self.spec["mathlib_rev"],
                "Native build used a different Mathlib revision")
        require(data.get("compiler_version") == self.receipt["environment"]["compiler_version"],
                "Native rebuild compiler identity differs")
        closure = native_import_closure(self.native, self.spec["native_endpoint"])
        require(len(closure) == self.spec["native_module_count"],
                "Native source import closure differs from the reviewed 572 modules")
        rows = data.get("modules")
        require(isinstance(rows, list) and len(rows) == len(closure),
                "Native receipt has missing or extra module records")
        names = [row.get("module") for row in rows]
        require(len(set(names)) == len(names) and set(names) == closure,
                "Native build receipt does not exactly cover the source import closure")
        records = []
        for row in rows:
            module = row["module"]
            require(row.get("preexisting_object") is False,
                    "Native receipt reused a preexisting module object: " + module)
            require(row.get("source_unchanged") is True,
                    "Native source was not unchanged through its build: " + module)
            source_relative = module_path(module, ".lean")
            object_relative = module_path(module, ".olean")
            require(str(row.get("source_path", "")).replace("\\", "/").endswith(
                    "/" + source_relative.as_posix()), "Native receipt source path is substituted")
            require(str(row.get("object_path", "")).replace("\\", "/").endswith(
                    "/" + object_relative.as_posix()), "Native receipt object path is substituted")
            source = self.native / source_relative
            obj = self.native_lib / object_relative
            import_roots = [Path(root) for root in self.receipt["environment"]["import_roots"]]
            resolved = next((root / object_relative for root in import_roots
                             if (root / object_relative).is_file()), None)
            require(resolved is not None and resolved.resolve() == obj.resolve(),
                    "An import root shadows the recorded native dependency: " + module)
            source_hash = self.bind(source)
            object_hash = self.bind(obj)
            require(row.get("source_sha256") == source_hash and
                    row.get("object_sha256") == object_hash,
                    "Native source/object hashes do not match receipt: " + module)
            record = {"module": module, "source": str(source), "source_sha256": source_hash,
                      "object": str(obj), "object_sha256": object_hash}
            for suffix in (".olean.private", ".olean.server"):
                extra = self.native_lib / module_path(module, suffix)
                if extra.exists():
                    record[suffix] = self.bind(extra)
            records.append(record)
        self.bind(path)
        inventory = self.output / "NATIVE_VALIDATED_INPUTS.json"
        json_write(inventory, {"modules": records, "count": len(records)})
        return {"receipt": str(path), "receipt_sha256": sha256(path), "module_count": len(records),
                "validated_inventory": str(inventory), "validated_inventory_sha256": sha256(inventory),
                "scope": "Conditional native receiver rebuild; not the closed C1 claim"}

    @staticmethod
    def object_files(root):
        # Lake can list an unused package's not-yet-created object directory.
        # An actual missing import will fail compilation; recording its empty
        # inventory still detects later shadow objects appearing there.
        if not root.exists():
            return []
        require(root.is_dir(), "Object root is not a directory: " + str(root))
        files = []
        for directory, directories, names in os.walk(root):
            for name in directories:
                require(not (Path(directory) / name).is_symlink(),
                        "Nested symlink object directories are unsupported: " + str(root))
            for name in names:
                if name.endswith((".olean", ".olean.private", ".olean.server", ".ir")):
                    files.append((Path(directory) / name).relative_to(root).as_posix())
        return sorted(files)

    def snapshot_objects(self, root):
        root = root.resolve()
        key = str(root)
        names = self.object_files(root)
        existing = self.object_root_inventories.get(key)
        if existing is not None:
            require(set(existing) == set(names), "Object inventory changed during verification: " + key)
        inventory = {}
        started = time.monotonic()
        for index, relative in enumerate(names, 1):
            inventory[relative] = self.bind(root / relative)
            if time.monotonic() - started >= 30:
                print("Bound " + str(index) + " of " + str(len(names)) +
                      " objects in " + key + ".", flush=True)
                started = time.monotonic()
        if existing is not None:
            require(inventory == existing, "Object bytes changed during verification: " + key)
        self.object_root_inventories[key] = inventory
        return inventory

    def canonical_dependency_snapshot(self):
        for name, row in self.canonical_packages.items():
            self.canonical_package_inventories[name] = self.snapshot_objects(row["objects"])
        self.snapshot_objects(self.native_lib)
        self.snapshot_objects(self.toolchain_prefix / "lib/lean")
        report = self.output / "CANONICAL_OBJECT_SNAPSHOT.json"
        json_write(report, self.object_root_inventories)
        return {"inventory": str(report), "inventory_sha256": sha256(report),
                "scope": "Current canonical inputs and later integrity, not retrospective build provenance",
                "root_count": len(self.object_root_inventories),
                "object_count": sum(len(row) for row in self.object_root_inventories.values())}

    def shared_dependency_comparison(self):
        checked = 0
        roots = [Path(path) for path in self.receipt["environment"]["import_roots"]]
        comparisons = [(name, self.combined_packages[name]["objects"], inventory)
                       for name, inventory in self.canonical_package_inventories.items()]
        # Core objects are dependencies too. Matching compiler executable bytes
        # alone does not prevent a different or shadowed Init/Lean object root.
        require(hasattr(self, "toolchain_prefix") and hasattr(self, "combined_toolchain_prefix"),
                "Both canonical and combined toolchain roots must be initialized")
        core = str((self.toolchain_prefix / "lib/lean").resolve())
        require(core in self.object_root_inventories, "Canonical core object inventory is absent")
        comparisons.append(("Lean toolchain", self.combined_toolchain_prefix / "lib/lean",
                            self.object_root_inventories[core]))
        for name, root, original in comparisons:
            for relative, expected in original.items():
                actual = root / relative
                require_file(actual, "Combined environment lacks a canonical package artifact")
                require(self.bind(actual) == expected,
                        "Shared dependency differs from the canonical environment: " + name + "/" + relative)
                if relative.endswith(".olean"):
                    resolved = next((candidate / relative for candidate in roots
                                     if (candidate / relative).is_file()), None)
                    require(resolved is not None and resolved.resolve() == actual.resolve(),
                            "An import root shadows a canonical package dependency: " + relative)
                checked += 1
        # Every native input remains the exact freshly built object, even if an
        # external root happens to contain a same-named Zeta23 module.
        for module in native_import_closure(self.native, self.spec["native_endpoint"]):
            relative = module_path(module, ".olean")
            resolved = next((candidate / relative for candidate in roots
                             if (candidate / relative).is_file()), None)
            require(resolved is not None and resolved.resolve() == (self.native_lib / relative).resolve(),
                    "An import root shadows a fresh native dependency: " + module)
        return {"shared_package_artifacts_compared": checked,
                "native_objects_resolution_checked": self.spec["native_module_count"],
                "scope": "Exact current artifact identity, not a claim about prior cache origin"}

    def complete_object_snapshot(self):
        for path in self.receipt["environment"]["import_roots"]:
            root = Path(path)
            if root.resolve() != self.lib.resolve():
                self.snapshot_objects(root)
        report = self.output / "ALL_OBJECT_INPUT_SNAPSHOTS.json"
        json_write(report, self.object_root_inventories)
        return {"inventory": str(report), "inventory_sha256": sha256(report),
                "root_count": len(self.object_root_inventories),
                "object_count": sum(len(row) for row in self.object_root_inventories.values()),
                "external_source_to_object_provenance": "NOT_ESTABLISHED_BY_THIS_SNAPSHOT"}

    def compile_module(self, module: str, stage_name: str, *, canonical=False):
        require(self.lean is not None, "Compiler not initialized")
        relative = module_path(module, ".lean")
        library = self.canonical_lib if canonical else self.lib
        obj = library / module_path(module, ".olean")
        interface = library / module_path(module, ".ilean")
        obj.parent.mkdir(parents=True, exist_ok=True)
        require(not obj.exists() and not interface.exists(), "Fresh output path was not empty")
        argv = [str(self.lean), "-j" + str(self.args.jobs),
                "-DwarningAsError=true", "-DrelaxedAutoImplicit=false",
                "-DmaxHeartbeats=" + str(self.args.max_heartbeats),
                str(relative), "-o", str(obj), "-i", str(interface)]
        result = self.run_process(stage_name, argv, self.sources, self.args.compile_timeout,
                                  env=self.canonical_env if canonical else self.env)
        require_file(obj, "Compiler returned without the required fresh object")
        require_file(interface, "Compiler returned without the required fresh interface")
        result["products"] = {}
        for suffix in (".olean", ".olean.private", ".olean.server", ".ir", ".ilean"):
            artifact = library / module_path(module, suffix)
            if artifact.exists():
                result["products"][suffix] = {"path": str(artifact), "sha256": self.bind(artifact)}
        result["source_sha256"] = self.bind(self.sources / relative)
        result["module"] = module
        if canonical:
            result["scope"] = "Canonical statement definitions and reflexivity only; no C1 or RH proof"
            self.receipt["canonical_fingerprint_compile"] = result
        else:
            self.compiled[module] = result
        return result

    def verification_tools(self):
        if self.args.exporter is None:
            raise GateBlocked("Supply --exporter from lean4export v4.33.0 built with Lean 4.33.1")
        if self.args.comparator_lake is None:
            raise GateBlocked("Supply --comparator-lake from the official Lean 4.36.0 toolchain")
        self.exporter = self.args.exporter.resolve()
        self.comparator_lake = self.args.comparator_lake.resolve()
        self.comparison_helper = (self.args.comparison_helper.resolve() if self.args.comparison_helper else
                                  self.package / "comparison_control/.lake/build/bin/compare_exports")
        for path in (self.exporter, self.comparator_lake, self.comparison_helper):
            require_file(path, "Required verification tool is absent")
        judge_bin = self.comparator_lake.parent
        judge_lean = judge_bin / "lean"
        require_file(judge_lean, "Comparator toolchain Lean binary is absent")
        env = dict(os.environ)
        for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LAKE_CONFIG",
                    "COMPARATOR_LEAN4EXPORT", "COMPARATOR_NANODA", "COMPARATOR_LANDRUN",
                    "COMPARATOR_BWRAP"):
            env.pop(key, None)
        env["PATH"] = str(judge_bin) + os.pathsep + env.get("PATH", "")
        env["LEAN_ABORT_ON_PANIC"] = "1"
        version = command_bytes([str(judge_lean), "--version"], self.output, env).decode().strip()
        expected = re.escape(self.spec["comparator_toolchain_version"])
        require(bool(re.search(r"\bversion " + expected + r"(?:,|\s|$)", version)),
                "Comparator must use the reviewed Lean 4.36.0 toolchain")
        self.comparator_env = env
        tools = {"exporter": self.exporter, "statement_comparison_helper": self.comparison_helper,
                 "comparator_lake": self.comparator_lake, "comparator_lean": judge_lean,
                 "paranoid_kernel": judge_bin / "leanchecker-paranoid",
                 "independent_nanoda_kernel": judge_bin / "nanoda_bin"}
        records = {name: {"path": str(path), "sha256": self.bind(path)} for name, path in tools.items()}
        records["comparator_version"] = version
        records["scope"] = "Trusted verification-tool inputs; hashes record bytes, not a new provenance claim"
        self.receipt["verification_tools"] = records
        return records

    def export_names(self, closed=False):
        names = list(self.spec["export_auxiliary_targets"])
        names.extend(self.spec["fingerprint_theorems"])
        if closed:
            for group in self.spec["module_types"].values():
                names.extend(group)
        return list(dict.fromkeys(names))

    def export_module(self, *, canonical):
        require(self.exporter is not None, "Exporter is not initialized")
        name = "canonical_fingerprint_export" if canonical else "closed_solution_export"
        module = self.spec["fingerprint_module"] if canonical else self.spec["closed_comparison_module"]
        target = self.output / ("canonical-fingerprint.ndjson" if canonical else "closed-solution.ndjson")
        names = self.export_names(closed=not canonical)
        result = self.run_process(name, [str(self.exporter), module, "--", *names], self.sources,
                                  self.args.export_timeout,
                                  env=self.canonical_env if canonical else self.env,
                                  stdout_path=target)
        require_file(target, "Exporter returned no export")
        result.update(export=str(target), export_sha256=self.bind(target), explicit_export_targets=names,
                      scope=("Canonical statement definitions only; no closed C1 proof" if canonical else
                             "Fingerprints plus every closed proof target and its transitive proof dependencies"))
        return result

    def comparison_controls(self):
        control_dir = self.output / "definition-controls"
        source = self.package / "comparison_control/test_statement_definitions.py"
        self.bind(source)
        self.run_process("comparison_helper_controls", [sys.executable, str(source),
                         "--lean", str(self.lean), "--exporter", str(self.exporter),
                         "--comparison-helper", str(self.comparison_helper), "--output", str(control_dir)],
                         self.output, self.args.compile_timeout, env=self.canonical_env)
        control_receipt = control_dir / "DEFINITION_COMPARISON_CONTROL.json"
        data = json.loads(control_receipt.read_text())
        require(data.get("status") == "PASS" and
                data.get("changed_definition") == "REJECTED_AT_REQUIRED_C1_BODY",
                "The upstream comparison helper did not pass its semantic mutation control")
        self.bind(control_receipt)
        config = json.loads((self.package / "comparator.json").read_text())
        config.update(challenge_module="Control", solution_module="Control",
                      theorem_names=["OPICA19Control.statementFingerprint"])
        control_config = control_dir / "comparator-control.json"
        json_write(control_config, config)
        self.bind(control_config)
        work = self.output / "comparator-work"
        work.mkdir(exist_ok=True)
        common = [str(self.comparator_lake), "comparator", "--config", str(control_config),
                  "--challenge-from-export", str(control_dir / "challenge.ndjson"),
                  "--solution-from-export"]
        positive = self.run_process("official_comparator_positive_control",
                                     [*common, str(control_dir / "matching.ndjson")], work,
                                     self.args.comparison_timeout, env=self.comparator_env)
        positive_text = Path(positive["log"]).read_text()
        require("Your solution is okay!" in positive_text, "Comparator positive control has no success marker")
        try:
            self.run_process("official_comparator_negative_control",
                             [*common, str(control_dir / "substituted.ndjson")], work,
                             self.args.comparison_timeout, env=self.comparator_env)
        except GateFailure as exc:
            if isinstance(exc, (GateBlocked, GateIncomplete)):
                raise
            process = json.loads((self.output / "official_comparator_negative_control.process.json").read_text())
            negative_text = Path(process["log"]).read_text()
            require(process.get("exit_code") == 1 and
                    "OPICA19Control.requiredC1" in negative_text and
                    ("does not match" in negative_text or "mismatch" in negative_text.lower()),
                    "Comparator negative control failed for an unrelated reason")
        else:
            raise GateFailure("Comparator accepted the substituted proposition definition")
        for name in ("challenge.ndjson", "matching.ndjson", "substituted.ndjson"):
            self.bind(control_dir / name)
        return {"helper_control": str(control_receipt),
                "same_definition": "ACCEPTED_BY_HELPER_AND_OFFICIAL_COMPARATOR",
                "changed_definition": "REJECTED_AT_REQUIRED_C1_BY_BOTH",
                "c1_or_rh_proved_by_controls": False}

    def closed_export_audit(self):
        names = [name for group in self.spec["module_types"].values() for name in group]
        require(len(names) == len(set(names)), "Duplicate closed export target")
        result = self.run_process("closed_export_type_and_axiom_audit",
                                  [str(self.comparison_helper),
                                   str(self.output / "canonical-fingerprint.ndjson"),
                                   str(self.output / "closed-solution.ndjson"),
                                   *self.spec["fingerprint_theorems"], "--closed", *names],
                                  self.output, self.args.comparison_timeout, env=self.canonical_env)
        text = Path(result["log"]).read_text()
        require("OPICA19_DEFINITION_COMPARISON_PASS" in text and
                ("OPICA19_CLOSED_EXPORT_AXIOMS_PASS " + str(len(names))) in text,
                "Same-export closed type/axiom audit lacks its complete success markers")
        result.update(closed_targets=names,
                      solution_export_sha256=self.bind(self.output / "closed-solution.ndjson"))
        return result

    def canonical_statement_comparison(self):
        config = self.package / "comparator.json"
        require(self.bind(config) == self.spec["comparator_config_sha256"],
                "Comparator configuration changed")
        work = self.output / "comparator-work"
        work.mkdir(exist_ok=True)
        result = self.run_process("canonical_statement_comparison",
                                  [str(self.comparator_lake), "comparator", "--config", str(config),
                                   "--challenge-from-export", str(self.output / "canonical-fingerprint.ndjson"),
                                   "--solution-from-export", str(self.output / "closed-solution.ndjson")],
                                  work, self.args.comparison_timeout, env=self.comparator_env)
        text = Path(result["log"]).read_text()
        require("Your solution is okay!" in text, "Official Comparator produced no success marker")
        require(not re.search(r"(?im)^.*(?:Building|Exporting|Resolving dependencies).*$", text),
                "Comparator unexpectedly rebuilt or re-exported instead of using the bound exports")
        result.update(canonical_export_sha256=self.bind(self.output / "canonical-fingerprint.ndjson"),
                      closed_solution_export_sha256=self.bind(self.output / "closed-solution.ndjson"),
                      scope="Canonical definition identity and kernels on the same augmented closed-proof export",
                      separate_closed_target_axiom_audit="closed_export_type_and_axiom_audit")
        return result

    def type_and_axiom_audit(self):
        results = {}
        allowed = set(self.spec["allowed_axioms"])
        for module, names in self.spec["module_types"].items():
            log = Path(self.compiled[module]["log"])
            results.update(parse_audit(log.read_text(encoding="utf-8"), names, allowed))
        # These are closed types, not implications whose premise was hidden by a wrapper.
        source_name = self.spec["external_theorem"]
        compact = " ".join(results[source_name]["type"].split())
        require(compact in (source_name + " : RiemannHypothesis",
                            "@" + source_name + " : RiemannHypothesis"),
                "External endpoint has an unexpected parameter or target")
        step_name = "Zeta23.OPICARound19.step4C1"
        compact = " ".join(results[step_name]["type"].split())
        target = "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"
        require(compact in (step_name + " : " + target, "@" + step_name + " : " + target),
                "C1 theorem has an unexpected parameter or target")
        report = self.output / "TYPES_AND_TRANSITIVE_AXIOMS.json"
        json_write(report, results)
        return {"declarations": len(results), "report": str(report),
                "report_sha256": sha256(report), "allowed_axioms": sorted(allowed)}

    def replay(self, module: str, name: str, fresh=False):
        require(self.checker is not None, "Kernel checker not initialized")
        argv = [str(self.checker)]
        if fresh:
            argv.append("--fresh")
        argv.extend(["--verbose", module])
        result = self.run_process(name, argv, self.sources,
                                  self.args.fresh_timeout if fresh else self.args.replay_timeout)
        result["scope"] = ("Complete imported and new constant environment" if fresh else
                           "New declarations of the exact module against its imports")
        result["independent_kernel_implementation"] = False
        return result

    def final_integrity(self):
        no_tracked_changes(self.external, ["src", "lean-toolchain", "lake-manifest.json",
                                          "lakefile.toml"])
        no_tracked_changes(self.native, ["Zeta23", "lean-toolchain", "lake-manifest.json"])
        require(git_text(self.external, "rev-parse", "HEAD") ==
                self.receipt["source_binding"]["external_head"], "External HEAD changed during gate")
        require(git_text(self.native, "rev-parse", "HEAD") == self.spec["native_head"],
                "Native HEAD changed during gate")
        for packages in (self.canonical_packages, self.combined_packages):
            for name, row in packages.items():
                require(git_text(row["root"], "rev-parse", "HEAD") == row["revision"],
                        "Dependency HEAD changed: " + name)
                no_tracked_changes(row["root"], ["."])
        for root, inventory in self.object_root_inventories.items():
            require(set(self.object_files(Path(root))) == set(inventory),
                    "An object appeared, disappeared or changed import resolution: " + root)
        for name, expected in self.input_hashes.items():
            path = Path(name)
            require(path.is_file() and sha256(path) == expected,
                    "Bound input or product changed during gate: " + name)
        inventory = self.output / "ALL_BOUND_INPUTS_AND_PRODUCTS.json"
        json_write(inventory, self.input_hashes)
        return {"bound_file_count": len(self.input_hashes), "inventory": str(inventory),
                "inventory_sha256": sha256(inventory)}

    def execute(self) -> int:
        exit_code = 1
        try:
            self.stage("source_identity", self.source_identity)
            self.stage("external_endpoint_presence", self.external_endpoint_presence)
            self.stage("canonical_environment", self.canonical_environment)
            self.stage("verification_tools", self.verification_tools)
            self.stage("native_build_receipt", self.native_build_receipt)
            self.stage("canonical_dependency_snapshot", self.canonical_dependency_snapshot)
            self.stage("canonical_fingerprint_compile",
                       lambda: self.compile_module(self.spec["fingerprint_module"],
                                                   "canonical_fingerprint_compile", canonical=True))
            self.stage("canonical_fingerprint_export", lambda: self.export_module(canonical=True))
            self.stage("compatible_environment", self.compatible_environment)
            self.stage("shared_dependency_comparison", self.shared_dependency_comparison)
            self.stage("complete_object_snapshot", self.complete_object_snapshot)
            self.stage("comparison_controls", self.comparison_controls)
            self.stage("combined_fingerprint_compile",
                       lambda: self.compile_module(self.spec["fingerprint_module"],
                                                   "combined_fingerprint_compile"))
            self.stage("fresh_bridge_compile",
                       lambda: self.compile_module("OPICAStep4.ClosedBridge", "fresh_bridge_compile"))
            self.stage("fresh_named_consumer_compile",
                       lambda: self.compile_module("OPICAStep4.IndependentConsumer",
                                                   "fresh_named_consumer_compile"))
            self.stage("closed_fingerprint_consumer_compile",
                       lambda: self.compile_module(self.spec["closed_comparison_module"],
                                                   "closed_fingerprint_consumer_compile"))
            self.stage("complete_type_and_axiom_audit", self.type_and_axiom_audit)
            self.stage("closed_solution_export", lambda: self.export_module(canonical=False))
            self.stage("closed_export_type_and_axiom_audit", self.closed_export_audit)
            self.stage("canonical_statement_comparison", self.canonical_statement_comparison)
            self.stage("bridge_kernel_replay",
                       lambda: self.replay("OPICAStep4.ClosedBridge", "bridge_kernel_replay"))
            self.stage("named_consumer_kernel_replay",
                       lambda: self.replay("OPICAStep4.IndependentConsumer",
                                           "named_consumer_kernel_replay"))
            self.stage("closed_fingerprint_consumer_kernel_replay",
                       lambda: self.replay(self.spec["closed_comparison_module"],
                                           "closed_fingerprint_consumer_kernel_replay"))
            self.stage("complete_fresh_kernel_replay",
                       lambda: self.replay(self.spec["closed_comparison_module"],
                                           "complete_fresh_kernel_replay", fresh=True))
            self.stage("final_input_integrity", self.final_integrity)
            require(all(row["status"] == "PASS" for row in self.receipt["stages"]),
                    "At least one required stage did not pass")
            self.receipt.update(status="PASS",
                                closure_claim="EXACT_CANONICAL_NATIVE_C1_PROVED_AT_RECORDED_INTEGRATION_PIN")
            exit_code = 0
        except GateBlocked as exc:
            self.receipt.update(status="BLOCKED", failure=str(exc))
            exit_code = 2
        except GateIncomplete as exc:
            self.receipt.update(status="INCOMPLETE", failure=str(exc))
            exit_code = 2
        except KeyboardInterrupt:
            self.receipt.update(status="INTERRUPTED", failure="Interrupted by operator")
            exit_code = 130
        except Exception as exc:
            self.receipt.update(status="FAIL", failure=str(exc), exception_type=type(exc).__name__)
            exit_code = 1
        finally:
            self.receipt.update(ended_utc=utc_now(), exit_code=exit_code)
            self.save()
            print(self.receipt["status"] + ": " + self.receipt["closure_claim"], flush=True)
            print("Receipt: " + str(self.output / "COMBINED_GATE_RECEIPT.json"), flush=True)
            if self.receipt.get("failure"):
                print(self.receipt["failure"], file=sys.stderr, flush=True)
        return exit_code


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", type=Path, required=True,
                        help="Existing complete, verified original-proof checkout/build")
    parser.add_argument("--integration", type=Path, required=True,
                        help="Existing Lean 4.33.1 common-pin native integration workspace")
    parser.add_argument("--native", type=Path,
                        help="Optional native checkout; otherwise inferred from integration lakefile.toml")
    parser.add_argument("--external-head",
                        help="Explicit full external commit pin; canonical proof source identity is still required")
    parser.add_argument("--external-lib", type=Path,
                        help="Optional existing external object root; must occur in external lake env")
    parser.add_argument("--native-receipt", type=Path,
                        help="Defaults to integration/NATIVE_COMMON_PIN_BUILD.json")
    parser.add_argument("--lake", type=Path,
                        help="Compatible Lake binary if it is not already on PATH")
    parser.add_argument("--exporter", type=Path,
                        help="lean4export v4.33.0 binary built with Lean 4.33.1")
    parser.add_argument("--comparator-lake", type=Path,
                        help="Official Lean 4.36.0 bin/lake with bundled comparator and kernels")
    parser.add_argument("--comparison-helper", type=Path,
                        help="Defaults to comparison_control/.lake/build/bin/compare_exports in this package")
    parser.add_argument("--output", type=Path, help="Fresh empty evidence directory")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--max-heartbeats", type=int, default=1600000)
    parser.add_argument("--compile-timeout", type=int, default=7200,
                        help="Seconds allowed for each fresh integration module")
    parser.add_argument("--replay-timeout", type=int, default=14400,
                        help="Seconds allowed for each module kernel replay")
    parser.add_argument("--fresh-timeout", type=int, default=86400,
                        help="Seconds allowed for the mandatory complete fresh kernel replay")
    parser.add_argument("--export-timeout", type=int, default=86400,
                        help="Seconds allowed for each complete Lean export")
    parser.add_argument("--comparison-timeout", type=int, default=86400,
                        help="Seconds allowed for each export comparison or kernel adjudication")
    args = parser.parse_args()
    for name in ("jobs", "max_heartbeats", "compile_timeout", "replay_timeout", "fresh_timeout",
                 "export_timeout", "comparison_timeout"):
        parser.error(name.replace("_", "-") + " must be positive") if getattr(args, name) <= 0 else None
    return args


def main() -> int:
    args = arguments()
    try:
        gate = Gate(args)
    except Exception as exc:
        print("BLOCKED before initialization: " + str(exc), file=sys.stderr)
        return 2
    return gate.execute()


if __name__ == "__main__":
    raise SystemExit(main())

