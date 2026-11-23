#!/usr/bin/env python3
"""Independently check the complete 50-root closure after an exact modular PASS.

This is an additional direct-object checker execution. It never reports the
original 25-stage gate or a full NDJSON kernel execution as having passed.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from common import *

HERE = Path(__file__).resolve().parent
MODULAR_PATH = HERE.parent / "modular/verify_modular.py"
require(sha(MODULAR_PATH) == MODULAR_RUNNER_SHA, "Frozen modular runner changed")
_spec = importlib.util.spec_from_file_location("opica20_modular_frozen", MODULAR_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)
old = mod.old
ROOTS = (*mod.SUPPLIER_TARGETS, *mod.AUDIT_NAMES, *mod.CLOSED_TYPES)
require(len(ROOTS) == len(set(ROOTS)) == 50, "Independent ordered root inventory is not exactly 50")
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
STAGES = ("modular_receipt_identity", "checker_build_identity", "inherited_input_identity",
          "read_only_object_views", "cross_version_controls", "combined_proof_closure",
          "final_input_integrity")


def assert_modular_claim(data):
    require(data.get("schema") == mod.GATE_VERSION and data.get("gate_version") == mod.GATE_VERSION,
            "Wrong modular receipt schema")
    require(data.get("status") == "PASS" and data.get("exit_code") == 0, "A completed modular PASS is required")
    require(data.get("runner_sha256") == MODULAR_RUNNER_SHA and
            data.get("frozen_runner_sha256") == mod.FROZEN_RUNNER_SHA and
            data.get("frozen_spec_sha256") == mod.FROZEN_SPEC_SHA, "Modular runner/spec identity changed")
    stages = data.get("stages")
    require(isinstance(stages, list) and [x.get("name") for x in stages] == list(mod.STAGES) and
            all(x.get("status") == "PASS" and isinstance(x.get("details"), dict) for x in stages),
            "All exact 30 modular stages must have passed once in order")
    expected = {"supplier_certificate_identity": "MATCHES_PUBLISHED_FULL_CERTIFICATE",
        "supplier_kernel_execution": "EXTERNAL_PUBLISHED_RECEIPT", "native_full_kernel_execution": "LOCAL_PASS",
        "new_closed_declarations_kernel_execution": "LOCAL_PASS",
        "full_combined_export_kernel_execution": "NOT_RUN_BY_THIS_GATE",
        "prior_round19_25_stage_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
        "fresh_closed_object_production": "STOCK_KERNEL_CHECKED_ACTUAL_THREE_THEOREMS",
        "closed_source_elaborator_compilation": "NOT_RUN_BY_THIS_GATE",
        "closure_claim": "EXACT_NATIVE_C1_AT_COMMON_PIN_UNDER_EXPLICIT_EXTERNAL_SUPPLIER_CERTIFICATE_MODEL"}
    require(all(data.get(k) == v for k, v in expected.items()), "Modular claim/scope mismatch")
    return {row["name"]: row["details"] for row in stages}


def acceptance(text, root_count, *, minimum=1, exact=None, complete_prelude=False):
    verdicts = re.findall(r"(?m)^con-leche: accepted ([0-9]+) declarations \(--verified\)\s*$", text)
    require(len(verdicts) == 1, "Missing or duplicated exact verified acceptance verdict")
    count = int(verdicts[0])
    require(count >= minimum and (exact is None or count == exact), "Unexpected accepted declaration count")
    emits = re.findall(r"con-leche: read: emitting records from ([0-9]+) constants\b", text)
    require(emits == [str(root_count)], "Checker did not select the exact requested root count")
    parses = re.findall(r"con-leche: parse done: ([0-9]+) fold records — the file's ([0-9]+), ([0-9]+) built-in prelude records synthesised", text)
    checks = re.findall(r"con-leche: check done: ([0-9]+) declarations\b", text)
    require(len(parses) == 1 and checks == [parses[0][0]] and int(parses[0][1]) == count,
            "Accepted count does not match the complete emitted-and-checked records")
    if complete_prelude:
        require(parses[0][0] == parses[0][1] and parses[0][2] == "0", "Required explicit primitive roots were not emitted")
    require(not re.search(r"not implemented yet:|internal error:|check failed|PANIC|uncaught exception", text),
            "Independent checker emitted a contradictory failure diagnostic")
    return count


def mount_identity(path):
    target = Path(path).resolve()
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
    require(matches, "Object mount is missing: " + str(path))
    row = max(matches, key=lambda p: p[0])[1]
    require("ro" in row["mount_options"].split(","), "Object reader must use a read-only mount: " + str(path))
    return row


class Independent:
    def __init__(self, args):
        self.args = args
        self.gate = args.modular_output.resolve()
        self.tools = args.checker_work.resolve()
        self.output = args.output.resolve()
        require(not self.output.exists() or not any(self.output.iterdir()), "Independent output must be fresh")
        require(not self.output.is_relative_to(self.gate) and not self.output.is_relative_to(self.tools),
                "Independent output must not alter inherited gate/tools")
        self.output.mkdir(parents=True, exist_ok=True)
        self.bound, self.input_files, self.object_inventories = {}, {}, {}
        self.mounts, self.view_map, self.view_ids, self.view_links = [], {}, {}, {}
        self.workers = min(4, len(os.sched_getaffinity(0))) if args.jobs is None else args.jobs
        require(1 <= self.workers <= min(4, len(os.sched_getaffinity(0))), "Requested workers exceed available bounded CPU count")
        self.receipt = {"schema": SCHEMA, "status": "RUNNING", "started_utc": utc(),
            "scope": "Additional independent direct-object verification of every selected proof/type dependency",
            "prior_round19_25_stage_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
            "full_combined_ndjson_kernel_execution": "NOT_RUN_BY_THIS_GATE",
            "metatheory_fresh_compilation": "NOT_CLAIMED",
            "rh_project_claim_gate": "NOT_EVALUATED_BY_THIS_CHECKER_RECEIPT",
            "ordered_roots": list(ROOTS), "selected_root_count": 50, "workers": self.workers,
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "runner_sha256": sha(Path(__file__)),
            "common_sha256": sha(HERE / "common.py"), "modular_runner_sha256": MODULAR_RUNNER_SHA,
            "stages": [{"name": name, "status": "NOT_RUN"} for name in STAGES]}
        self.save()

    def save(self):
        write_json(self.output / "INDEPENDENT_RECEIPT.json", self.receipt)

    def bind(self, path, expected=None):
        path = Path(path).absolute()
        require(path.is_file(), "Required bound file missing: " + str(path))
        value = sha(path)
        if expected is not None:
            require(value == expected, "File digest mismatch: " + str(path))
        require(str(path) not in self.bound or self.bound[str(path)] == value, "Bound input changed: " + str(path))
        self.bound[str(path)] = value
        return value

    def stage(self, name, action):
        row = next(r for r in self.receipt["stages"] if r["name"] == name)
        row.update(status="RUNNING", started_utc=utc()); self.save()
        print("Running independent stage: " + name, flush=True)
        started = time.monotonic()
        try:
            row.update(details=action(), status="PASS")
        except BaseException as exc:
            row.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAIL", failure=str(exc))
            raise
        finally:
            row.update(ended_utc=utc(), elapsed_seconds=round(time.monotonic()-started,3))
            write_json(self.output / (name + ".stage.json"), row); self.save()

    def modular_receipt_identity(self):
        path = self.gate / "MODULAR_GATE_RECEIPT.json"
        self.data = read_json(path)
        self.details = assert_modular_claim(self.data)
        self.bind(path)
        require(self.data["output"] == str(self.gate), "Modular output path substituted")
        require(re.fullmatch(r"[0-9a-f]{40}", self.args.external_head) and
                self.data["source_binding"]["external_head"] == self.args.external_head, "Exact expected external HEAD mismatch")
        self.external = Path(self.data["external"])
        self.integration = Path(self.data["integration"])
        self.native = Path(self.data["native"])
        require(not self.output.is_relative_to(self.external) and not self.output.is_relative_to(self.native),
                "Independent outputs must stay outside governed sources")
        for row in self.data["stages"]:
            stage_path = self.gate / (row["name"] + ".json")
            require(read_json(stage_path) == row, "Modular stage receipt differs: " + row["name"])
            self.bind(stage_path)
        spec_path = self.gate / "MODULAR_SPEC.json"
        self.bind(spec_path, self.data["modular_spec_sha256"])
        self.spec = read_json(spec_path)
        require(self.spec == mod.modular_spec(read_json(mod.FROZEN / "GATE_SPEC.json")), "Modular mathematical specification changed")
        require(set(self.spec["allowed_axioms"]) == ALLOWED_AXIOMS, "Three-axiom policy changed")
        for stage, filename in (("final_input_integrity", "ALL_BOUND_INPUTS_AND_PRODUCTS.json"),
                                ("complete_object_snapshot", "ALL_OBJECT_INPUT_SNAPSHOTS.json"),
                                ("canonical_dependency_snapshot", "CANONICAL_OBJECT_SNAPSHOT.json")):
            d = self.details[stage]
            target = self.gate / filename
            require(d["inventory"] == str(target), "Inventory path substituted: " + stage)
            self.bind(target, d["inventory_sha256"])
        self.input_files = read_json(self.gate / "ALL_BOUND_INPUTS_AND_PRODUCTS.json")
        require(len(self.input_files) == self.details["final_input_integrity"]["bound_file_count"], "Bound inventory count changed")
        for name, value in self.input_files.items():
            require(Path(name).is_absolute() and re.fullmatch(r"[0-9a-f]{64}", value), "Malformed inherited input entry")
        self.object_inventories = read_json(self.gate / "ALL_OBJECT_INPUT_SNAPSHOTS.json")
        require(sum(len(x) for x in self.object_inventories.values()) == self.details["complete_object_snapshot"]["object_count"],
                "Inherited object count changed")
        for root, inventory in self.object_inventories.items():
            require(Path(root).is_absolute(), "Object root is not absolute")
            for relative, expected in inventory.items():
                safe_relative(relative)
                require(self.input_files.get(str(Path(root)/relative)) == expected, "Object was not bound by modular final integrity")
        for root in (self.gate / "lib", self.gate / "canonical-lib"):
            inventory = {str(Path(name).relative_to(root)): value for name, value in self.input_files.items()
                         if Path(name).is_relative_to(root) and name.endswith((".olean", ".olean.private", ".olean.server", ".ir"))}
            require(inventory, "Fresh authored object inventory absent")
            self.object_inventories[str(root)] = inventory
        self.canonical_roots = self.data["canonical_environment"]["import_roots"]
        self.combined_roots = self.data["environment"]["import_roots"]
        require(self.canonical_roots[0] == str(self.gate/"canonical-lib") and self.combined_roots[0] == str(self.gate/"lib"),
                "Fresh authored namespace precedence changed")
        require(set(self.canonical_roots + self.combined_roots) <= set(self.object_inventories), "Uninventoried import root")
        self.original_mount = self.details["immutable_supplier_store"]
        self.supplier_root = self.original_mount["mountpoint"]
        require(mount_identity(self.supplier_root) == self.original_mount, "Original immutable supplier mount changed")
        for name in ("verify_independent.py", "common.py", "bootstrap_checker.py", "SPEC.md"):
            self.bind(HERE / name)
        self.bind(MODULAR_PATH, MODULAR_RUNNER_SHA)
        self.bind(mod.FROZEN/"verify_combined.py", mod.FROZEN_RUNNER_SHA)
        self.bind(mod.FROZEN/"GATE_SPEC.json", mod.FROZEN_SPEC_SHA)
        self.receipt.update(external_head=self.args.external_head, modular_receipt=str(path), modular_receipt_sha256=self.bound[str(path)],
            mathematical_claim_source="Exact previously passed modular types, safe-theorem and three-axiom audits")
        return {"modular_receipt_sha256": self.bound[str(path)], "stage_count": 30, "bound_file_count": len(self.input_files),
                "supplier_mount": self.original_mount}

    def checker_build_identity(self):
        path = self.tools/"BOOTSTRAP_RECEIPT.json"
        self.build = read_json(path)
        self.bind(path)
        b = self.build
        require(b.get("schema") == "OPICA20_PINNED_INDEPENDENT_CHECKER_BUILD_V1" and b.get("status") == "PASS" and b.get("exit_code") == 0,
                "Fresh successful independent checker bootstrap required")
        require(b.get("source_head") == CHECKER_HEAD and b.get("runtime_archive_sha256") == RUNTIME_SHA and
                b.get("runtime_archive_bytes") == RUNTIME_BYTES and b.get("runtime_url") == RUNTIME_URL, "Independent tool pin mismatch")
        self.bind(HERE/"bootstrap_checker.py", b["bootstrap_sha256"])
        self.bind(HERE/"common.py", b["common_sha256"])
        self.runtime = self.tools/RUNTIME_NAME
        self.checker_source = self.tools/"con-leche"
        require(b["runtime"] == str(self.runtime) and b["source"] == str(self.checker_source), "Tool location substituted")
        clean_checkout(self.checker_source, CHECKER_HEAD)
        require(git(self.checker_source,"rev-parse","HEAD^{tree}") == b["source_tree"], "Checker tree mismatch")
        for name, key in (("RUNTIME_FILES.json", "runtime_inventory"), ("CHECKER_SOURCE_FILES.json", "source_inventory")):
            target = self.tools/name
            require(b[key] == str(target), "Tool inventory location substituted")
            self.bind(target, b[key + "_sha256"])
        self.runtime_inventory = read_json(self.tools/"RUNTIME_FILES.json")
        self.checker_sources = read_json(self.tools/"CHECKER_SOURCE_FILES.json")
        require(len(self.runtime_inventory) > 1000 and "lib/lean/libleanshared.so" in self.runtime_inventory, "Missing runtime library identity")
        verify_file_inventory(self.runtime, self.runtime_inventory)
        require(set(self.checker_sources) == set(git(self.checker_source,"ls-files").splitlines()), "Checker source inventory changed")
        for name, expected in self.checker_sources.items():
            safe_relative(name); self.bind(self.checker_source/name, expected)
        self.binaries = {}
        for name in ("con-leche", "olean-compare"):
            p = self.checker_source/".lake/build/bin"/name
            row = b["tools"][name]
            require(row["path"] == str(p) and row["bytes"] == p.stat().st_size, "Checker executable location/size changed")
            self.bind(p, row["sha256"]); self.binaries[name] = p
        build = b["build"]
        require(build["status"] == "PASS" and build["exit_code"] == 0 and build["command"] ==
                list(map(str,[self.runtime/"bin/lake", "--no-cache", "--wfail", "build", "con-leche", "olean-compare"])),
                "Checker was not built by the exact authenticated command")
        require(Path(build["log"]) == self.tools/"build_checker.log", "Build log path changed")
        self.bind(build["log"], build["log_sha256"])
        require("Build completed successfully" in Path(build["log"]).read_text(), "Fresh checker build success absent")
        self.tool_env = clean_env(self.runtime, self.workers)
        self.receipt["checker"] = {"head": CHECKER_HEAD, "runtime_archive_sha256": RUNTIME_SHA,
            "runtime_inventory_sha256": b["runtime_inventory_sha256"], "executables": b["tools"],
            "host_system_libraries_and_hardware_trusted": True}
        return self.receipt["checker"]

    def current_sources(self):
        require(git(self.external,"rev-parse","HEAD") == self.args.external_head, "External HEAD changed")
        require(git(self.external,"rev-parse","HEAD^{tree}") == self.data["source_binding"]["external_tree"], "External tree changed")
        mod.verify_supplier_checkpoint(self.external, mod.EXTERNAL_HEAD, mod.EXTERNAL_SRC_TREE)
        old.no_tracked_changes(self.external,["src","lean-toolchain","lake-manifest.json","lakefile.toml","opica-step4"])
        require(git(self.native,"rev-parse","HEAD") == self.spec["native_head"] and
                git(self.native,"rev-parse","HEAD^{tree}") == self.spec["native_tree"], "Native HEAD/tree changed")
        old.no_tracked_changes(self.native,["Zeta23","lean-toolchain","lake-manifest.json"])
        for root in (self.external,self.integration):
            manifest = read_json(root/"lake-manifest.json")
            for p in manifest["packages"]:
                repo = (root/manifest.get("packagesDir",".lake/packages")/p["name"]).resolve()
                clean_checkout(repo,p["rev"])
        exporter = self.data["verification_tools"]["exporter_source"]
        require(git(exporter["path"],"rev-parse","HEAD") == mod.EXPORTER_COMMIT, "Exporter HEAD changed")
        old.no_tracked_changes(Path(exporter["path"]),list(exporter["sources"]))

    def check_object_sets(self):
        for root, inventory in self.object_inventories.items():
            require(old.Gate.object_files(Path(root)) == sorted(inventory), "An object appeared/disappeared: " + root)

    def rehash_inputs(self):
        self.check_object_sets()
        started = time.monotonic()
        for index,(name,expected) in enumerate(self.input_files.items(),1):
            require(Path(name).is_file() and sha(name) == expected, "Modular bound input changed: " + name)
            if time.monotonic()-started >= 30:
                print(f"Verified inherited bytes {index}/{len(self.input_files)}", flush=True); started=time.monotonic()
        for name, expected in list(self.bound.items()):
            require(Path(name).is_file() and sha(name) == expected, "Independent bound input changed: " + name)

    def inherited_input_identity(self):
        self.current_sources()
        self.rehash_inputs()
        runtime_manifest = HERE.parent/"native_bootstrap/runtime_files.json"
        self.bind(runtime_manifest,mod.RUNTIME_MANIFEST_SHA)
        expected_runtime = read_json(runtime_manifest)
        require(len(expected_runtime["files"]) == 26, "Original runtime manifest incomplete")
        for prefix, files in self.data["stock_runtime_files"].items():
            require(files == {r["path"]:r["sha256"] for r in expected_runtime["files"]}, "Original runtime scope changed")
            for row in expected_runtime["files"]:
                path = Path(prefix)/row["path"]
                require(self.input_files.get(str(path)) == row["sha256"] and path.stat().st_size == row["bytes"],
                        "Original runtime file not bound")
        for environment in (self.data["canonical_environment"],self.data["environment"]):
            require(str(Path(environment["compiler"]).parent.parent) in self.data["stock_runtime_files"], "Actual original runtime is not pinned")
        actual = self.details["actual_closed_object_audit"]
        closed_object = self.gate/"lib"/old.module_path(mod.CLOSED_MODULE,".olean")
        require(self.input_files.get(str(closed_object)) == actual["object_sha256"] and
                actual["inspector_sha256"] == mod.INSPECTOR_SHA and actual["closed_types"] == mod.CLOSED_TYPES,
                "Actual safe closed theorem object identity changed")
        rawlog = Path(actual["log"])
        require(self.input_files.get(str(rawlog)) == actual["log_sha256"], "Raw audit log not bound")
        text = rawlog.read_text()
        names = re.findall(r"(?m)^OPICA20_ACTUAL_THEOREM (\S+)\s*$",text)
        require(len(names) == 3 and set(names) == set(mod.CLOSED_TYPES) and text.count("OPICA20_CLOSED_OBJECT_AUDIT_PASS") == 1,
                "Raw safe-theorem/root-presence audit incomplete")
        self.bind(HERE.parent/"modular/InspectClosedObject.lean",mod.INSPECTOR_SHA)
        closed_compile = self.details["fresh_closed_kernel_construction"]
        require(closed_compile["production"] == "STOCK_KERNEL_CHECKED_DECLARATIONS_AND_STOCK_MODULE_DATA_WRITER"
                and closed_compile["source_elaborator_compilation"] == "NOT_RUN"
                and closed_compile["new_elaborator_extension_entries"] == "EMPTY",
                "Closed object production method or metadata scope changed")
        closed_log = Path(closed_compile["log"])
        require(self.input_files.get(str(closed_log)) == closed_compile["log_sha256"],
                "Actual selected-root/type/axiom audit log is not bound")
        closed_text = closed_log.read_text()
        safe_roots = mod.parse_selected_root_audit(closed_text)
        require(safe_roots == list(ROOTS) == closed_compile["ordered_safe_roots"] and
                closed_compile["mathematical_theorem_roots"] == list(mod.MATHEMATICAL_ROOTS),
                "Actual root-presence/safety/theorem-kind coverage changed")
        parsed = old.parse_audit(closed_text,["riemannHypothesis",*mod.CLOSED_TYPES],ALLOWED_AXIOMS)
        for name,typ in {"riemannHypothesis":"RiemannHypothesis",**mod.CLOSED_TYPES}.items():
            require(" ".join(parsed[name]["type"].split()) in (name+" : "+typ,"@"+name+" : "+typ), "Closed root type has changed")
        closed_report = self.gate/"CLOSED_TYPES_AND_TRANSITIVE_AXIOMS.json"
        require(parsed == read_json(closed_report), "Closed type/axiom report differs from actual kernel-object audit")
        native = self.details["canonical_type_and_axiom_audit"]
        require(native["targets"] == list(mod.AUDIT_NAMES) and set(native["allowed_axioms"]) == ALLOWED_AXIOMS, "Native axiom coverage changed")
        native_data = read_json(native["report"])
        native_parsed = old.parse_audit((self.gate/"canonical_native_type_commands.log").read_text(),list(mod.AUDIT_NAMES),ALLOWED_AXIOMS)
        require(native_data == native_parsed, "Native type/axiom report differs from actual compiler audit")
        require(self.details["final_supplier_certificate_identity"]["stdout_sha256"] == mod.SUPPLIER_SHA and
                self.details["final_supplier_certificate_identity"]["explicit_export_targets"] == list(mod.SUPPLIER_TARGETS),
                "Actual final supplier proof identity differs")
        require(self.details["final_native_proof_export_identity"]["stdout_sha256"] ==
                self.details["canonical_native_proof_export"]["stdout_sha256"], "Final native proof identity differs")
        return {"safe_closed_roots":dict(mod.CLOSED_TYPES),"allowed_axioms":sorted(ALLOWED_AXIOMS),
                "bound_files_rehashed":len(self.input_files),"current_object_roots":len(self.object_inventories)}

    def command(self,name,argv,*,env=None,timeout=None,memory=None,expected=0):
        row,text = run(name,argv,cwd=self.output,env=env or self.tool_env,output=self.output,
            timeout=timeout or self.args.control_timeout,memory_mib=memory or self.args.control_memory_mib,expected=expected)
        self.bind(row["log"],row["log_sha256"]); self.bind(self.output/(name+".json"))
        return row,text

    def readonly_mount(self, source, target, tag):
        target.mkdir()
        self.command("mount_bind_"+tag,["sudo","-n","mount","--bind",source,target],timeout=60,memory=512)
        self.mounts.append(target)
        self.command("mount_ro_"+tag,["sudo","-n","mount","-o","remount,bind,ro",target],timeout=60,memory=512)
        identity=mount_identity(target)
        require(identity["mountpoint"] == str(target),"Read-only bind mount at wrong location")
        self.view_ids[str(target)]=identity
        return target

    def read_only_object_views(self):
        storage = self.output/"view-data"; storage.mkdir()
        mounts = self.output/"mounts"; mounts.mkdir()
        native_root = str((self.integration/".lake/build/lib/lean").resolve())
        excluded=[]
        for index,name in enumerate(dict.fromkeys(self.canonical_roots+self.combined_roots)):
            root=Path(name)
            source=root
            if not root.exists():
                require(not self.object_inventories[name],"Missing nonempty object root")
                source=storage/("empty-"+str(index));source.mkdir()
            view=self.readonly_mount(source,mounts/str(index),str(index))
            if name == native_root and (view/"OPICAStep4").exists():
                filtered=storage/"native-filtered";filtered.mkdir()
                links={}
                for child in view.iterdir():
                    if child.name != "OPICAStep4":
                        (filtered/child.name).symlink_to(child,target_is_directory=child.is_dir())
                        links[child.name]=str(child)
                self.view_links[str(filtered)]=links
                view=self.readonly_mount(filtered,mounts/"native-filtered","native_filtered")
                excluded=[p for p in self.object_inventories[name] if p.startswith("OPICAStep4/")]
            self.view_map[name]=str(view)
            for relative in self.object_inventories[name]:
                if name == native_root and relative in excluded:
                    continue
                original,read_path=root/relative,view/relative
                a,b=original.stat(),read_path.stat()
                require((a.st_dev,a.st_ino,a.st_size)==(b.st_dev,b.st_ino,b.st_size),"Read-only view changed original file identity")
        # The only filter removes an already masked authored namespace. The
        # actual final/canonical imports continue to use their bound fresh copies.
        for module in mod.CANONICAL_MODULES:
            relative=old.module_path(module,".olean")
            canonical,combined=self.gate/"canonical-lib"/relative,self.gate/"lib"/relative
            require(self.input_files.get(str(canonical)) == self.input_files.get(str(combined)) and
                    self.input_files.get(str(canonical)) is not None,"Promoted authored object identity differs")
        for name in ("OPICAStep4.ImportGuard",mod.CLOSED_MODULE,*mod.CANONICAL_MODULES):
            target=Path(self.view_map[str(self.gate/"lib")])/old.module_path(name,".olean")
            require(target.is_file(),"Required actual authored module absent from sole namespace")
        self.canonical_search=os.pathsep.join(self.view_map[x] for x in self.canonical_roots)
        self.combined_search=os.pathsep.join(self.view_map[x] for x in self.combined_roots)
        mapping={"original_roots":self.combined_roots,"canonical_original_roots":self.canonical_roots,
            "read_only_view_map":self.view_map,"mount_identities":self.view_ids,
            "excluded_already_masked_native_namespace_files":excluded,"filtered_symlinks":self.view_links,
            "scope":"Exact original inodes/bytes; only obsolete native OPICAStep4 namespace copies are hidden"}
        write_json(self.output/"READ_ONLY_OBJECT_VIEWS.json",mapping);self.bind(self.output/"READ_ONLY_OBJECT_VIEWS.json")
        return mapping

    def cross_version_controls(self):
        fixture=self.output/"negative-fixture";fixture.mkdir()
        source=fixture/"ClosureControl.lean"
        source.write_text("-- Adversarial fixture only; never part of a proof gate.\nnamespace ClosureControl\n"
            "axiom uncheckedLeaf : False\ntheorem selectedRoot : False := uncheckedLeaf\n"
            "theorem unrelatedRoot : True := True.intro\nend ClosureControl\n")
        original_lean=Path(self.data["canonical_environment"]["compiler"])
        old_prefix=original_lean.parent.parent
        self.command("fixture_compile",[original_lean,"--root="+str(fixture),"-DwarningAsError=true","-o",fixture/"ClosureControl.olean",source],
            env=clean_env(old_prefix,1))
        self.bind(source);self.bind(fixture/"ClosureControl.olean")
        core=str(old_prefix/"lib/lean")
        require(core in self.view_map,"Original core objects missing from read-only views")
        search=str(fixture)+os.pathsep+self.view_map[core]
        base=[self.binaries["con-leche"],"--verified","--jobs=1","--progress=30s","--olean","--search-path="+search]
        _,text=self.command("control_unrelated_axiom",[*base,"--constant=ClosureControl.unrelatedRoot","ClosureControl"])
        acceptance(text,1,exact=2)
        _,text=self.command("control_transitive_axiom",[*base,"--constant=ClosureControl.selectedRoot","ClosureControl"],expected=2)
        require("not implemented yet: non-standard axiom (ClosureControl.uncheckedLeaf)" in text and "con-leche: accepted " not in text,
                "Transitive proof axiom did not receive its exact fail-closed disposition")
        _,text=self.command("control_missing_root",[*base,"--constant=ClosureControl.absentRoot","ClosureControl"],expected=3)
        require("the constant ClosureControl.absentRoot is not in the import closure" in text and "con-leche: accepted " not in text,
                "Missing-root control did not fail closed")
        names=[*mod.AUX_TARGETS,*mod.AUDIT_NAMES]
        _,text=self.command("control_native_proof",[self.binaries["con-leche"],"--verified","--jobs=1","--progress=30s","--olean",
            "--search-path="+self.canonical_search,*["--constant="+n for n in names],"OPICAStep4.NativeValidated"])
        native_count=acceptance(text,42,exact=65507,complete_prelude=True)
        names=[*mod.AUX_TARGETS,*self.spec["fingerprint_theorems"]]
        _,text=self.command("control_reader_comparison",[self.binaries["olean-compare"],*["--constant="+n for n in names],
            self.gate/"canonical-fingerprint.ndjson",self.canonical_search,"OPICAStep4.ClaimFingerprint"])
        counts=re.findall(r"(?m)^([0-9]+) stream keys, ([0-9]+) olean keys, 0 differences, 0 duplicate keys, ([0-9]+) / ([0-9]+) records\s*$",text)
        require(counts == [("51634",)*4],"Actual stock-export/direct-reader comparison differs from its exact control")
        return {"positive_unused_axiom":"ACCEPTED_2_RECORDS","transitive_custom_axiom":"EXPECTED_EXIT_2_WITH_EXACT_AXIOM_NAME",
            "missing_root":"EXPECTED_EXIT_3_WITH_EXACT_MISSING_NAME","native_proof_records":native_count,
            "reader_comparison_records":51634,"reader_differences":0,"duplicate_keys":0,
            "comparison_scope":"Complete canonical fingerprint declaration fields including proof/value fields; not full supplier comparison"}

    def check_views(self):
        require(mount_identity(self.supplier_root) == self.original_mount,"Original supplier read-only mount changed")
        for target,identity in self.view_ids.items():
            require(mount_identity(target) == identity,"Lazy-reader view mount changed: "+target)
        for name,expected in self.view_links.items():
            path=Path(name)
            require({p.name:os.readlink(p) for p in path.iterdir()} == expected,"Filtered namespace view changed")

    def combined_proof_closure(self):
        self.check_views()
        row,text=self.command("combined_50_root_proof",[self.binaries["con-leche"],"--verified","--jobs="+str(self.workers),"--progress=30s",
            "--olean","--search-path="+self.combined_search,*["--constant="+n for n in ROOTS],mod.CLOSED_MODULE],
            timeout=self.args.timeout,memory=self.args.memory_mib)
        count=acceptance(text,50,minimum=1468418+3,complete_prelude=True)
        self.receipt.update(accepted_declaration_records=count,independent_combined_proof_execution="LOCAL_PASS",
            selected_root_presence="ALL_50_PRESENT_SAFE_AND_NONPARTIAL; ALL_17_MATHEMATICAL_ROOTS_AUDITED_AS_THEOREMS",
            proof_scope="Complete transitive statement and proof dependency closure of all 50 exact roots")
        return {"process":row,"accepted_declaration_records":count,"ordered_roots":list(ROOTS),
            "direct_object_module":mod.CLOSED_MODULE,"root_count":50,"mode":"--verified --olean",
            "root_identity_basis":"Exact immutable authored objects plus inherited raw safe-theorem/type/axiom audit and missing-root control"}

    def final_input_integrity(self):
        self.check_views()
        self.current_sources()
        clean_checkout(self.checker_source,CHECKER_HEAD)
        self.rehash_inputs()
        verify_file_inventory(self.runtime,self.runtime_inventory)
        require(set(self.checker_sources) == set(git(self.checker_source,"ls-files").splitlines()),"Checker source set changed")
        write_json(self.output/"INDEPENDENT_BOUND_FILES.json",self.bound)
        return {"all_inherited_files_rehashed":len(self.input_files),"additional_bound_files_rehashed":len(self.bound),
                "all_object_sets_unchanged":True,"all_read_only_mounts_unchanged":True,
                "runtime_files_rehashed":len(self.runtime_inventory),
                "inventory":str(self.output/"INDEPENDENT_BOUND_FILES.json"),
                "inventory_sha256":sha(self.output/"INDEPENDENT_BOUND_FILES.json"),
                "host_trust":"Host administrator, kernel/filesystem, system libraries and hardware remain trusted; no concurrent writer is authorized"}

    def execute(self):
        code=1
        try:
            for name in STAGES:
                self.stage(name,getattr(self,name))
            require(all(r["status"] == "PASS" for r in self.receipt["stages"]),"Independent stage incomplete")
            self.receipt.update(status="PASS",claim="Exact combined 50-root proof/type closure independently accepted from the authenticated original objects")
            code=0
        except BaseException as exc:
            self.receipt.update(status="INTERRUPTED" if isinstance(exc,KeyboardInterrupt) else "FAIL",failure=str(exc),exception_type=type(exc).__name__)
            print(str(exc),file=sys.stderr,flush=True)
            if isinstance(exc,KeyboardInterrupt):code=130
        finally:
            cleanup=[]
            for target in reversed(self.mounts):
                try:
                    row,_=run("unmount_"+target.name,["sudo","-n","umount",target],cwd=self.output,env=clean_env(),
                              output=self.output,timeout=60,memory_mib=512)
                    cleanup.append({"target":str(target),"status":"PASS"})
                except BaseException as exc:
                    cleanup.append({"target":str(target),"status":"FAIL","failure":str(exc)})
                    self.receipt.update(status="FAIL",failure="Read-only view cleanup failed: "+str(exc));code=1
            self.receipt.update(ended_utc=utc(),exit_code=code,owned_mount_cleanup=cleanup)
            self.save()
            print(self.receipt["status"]+": "+SCHEMA,flush=True)
        return code


def arguments(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("modular-output","checker-work","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--external-head",required=True)
    p.add_argument("--jobs",type=int)
    for name,default in (("timeout",9000),("memory-mib",50000),("control-timeout",900),("control-memory-mib",7000)):
        p.add_argument("--"+name,type=int,default=default)
    args=p.parse_args(argv)
    require(all(v>0 for v in (args.timeout,args.memory_mib,args.control_timeout,args.control_memory_mib)),"Invalid process budget")
    return args

def main():
    try:
        return Independent(arguments()).execute()
    except Exception as exc:
        print("BLOCKED before independent verification: "+str(exc),file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
