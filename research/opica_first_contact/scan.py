#!/usr/bin/env python3
"""OPICA first-contact SOURCE search over exact community RH Lean 4.36 tree.

Finds lexical occurrences and approximates source-level module import closure.
Not the governed native OPICA prover, not a Lean kernel/axiom/definition check.
No proof result can arise from this source scan.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TARGET = HERE / "TARGET.json"
MAX_SOURCE_FILES = 220_000
MAX_FILE_BYTES = 16 << 20
MAX_MATCHES_PER_TERM = 24
IMPORT_LINE = re.compile(
    r"^\s*(?:(?:public|private|protected)\s+)?(?:meta\s+)?import\s+([A-Za-z0-9_.']+)(?:\s|$)"
)

class SourceSearchError(ValueError):
    pass

def require(ok: bool, why: str) -> None:
    if not ok:
        raise SourceSearchError(why)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git(*args: str) -> str:
    process = subprocess.run(["git", "-C", str(REPO), *args],
                             capture_output=True, text=True, check=True, timeout=90)
    return process.stdout.strip()

def read_target() -> dict:
    require(TARGET.is_file() and not TARGET.is_symlink(), "Missing or linked target")
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            require(k not in obj, "Duplicate target key: " + k)
            obj[k] = v
        return obj
    obj = json.loads(TARGET.read_text(), object_pairs_hook=unique)
    require(obj["schema"] == "OPICA_COMMUNITY_SUPPLIER_FIRST_CONTACT_V1", "Wrong schema")
    require(obj["upstream_commit"] == "1b894f7511841e6607bc0398cf2657526bbb29d9", "Original upstream commit drift")
    require(obj["upstream_source_tree"] == "69b331ce0e429c7632dac6aa642e5875a50b1218", "Original source tree drift")
    require(obj["toolchain"] == "leanprover/lean4:v4.36.0", "Lean source toolchain changed")
    require(obj["mathlib_commit"] == "fc4f59e577feb1a4956671bc04ac18aaaf8cd842", "Mathlib pin changed")
    require(obj["native_target"]["formal_type_name"] ==
            "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds",
            "Native C1 target changed")
    require(obj["proof_acceptance"] is False and obj["rh_status"] == "OPEN",
            "Search target cannot authorize a theorem")
    terms = obj.get("source_terms")
    require(type(terms) is list and 0 < len(terms) <= 32 and
            len(terms) == len(set(terms)) and all(type(t) is str and 3 <= len(t) <= 100 for t in terms),
            "Source search terms invalid")
    return obj

def verify_source_state(t: dict) -> dict:
    # The search branch is deliberately off the synchronized upstream main and
    # may contain only its own research driver; no supplier source may drift.
    require(git("rev-parse", "HEAD:src") == t["upstream_source_tree"],
            "The scanned supplier source tree differs from the reviewed upstream head")
    upstream = t["upstream_commit"]
    require(git("rev-parse", upstream + ":src") == t["upstream_source_tree"],
            "Pinned upstream commit no longer resolves to expected source tree")
    for path, expected in t["exact_proof_source_blobs"].items():
        require(git("rev-parse", "HEAD:" + path) == expected,
                "Pinned Lean file blob differs: " + path)
        require(git("rev-parse", upstream + ":" + path) == expected,
                "The baseline Lean source file differs: " + path)
    for path in ("lean-toolchain", "lakefile.toml", "comparator.json"):
        require(git("rev-parse", "HEAD:" + path) ==
                git("rev-parse", upstream + ":" + path),
                "Original supplier runtime or comparator config changed: " + path)
    require((REPO/"lean-toolchain").read_text().strip() == t["toolchain"],
            "Worktree Lean toolchain mismatches pinned source")
    require(t["mathlib_commit"] in (REPO/"lakefile.toml").read_text(),
            "Worktree Mathlib revision mismatches pinned source")
    require(git("status", "--porcelain", "--untracked-files=no") == "",
            "Tracked worktree changed during read-only scan")
    return {
        "actual_head": git("rev-parse", "HEAD"),
        "actual_tree": git("rev-parse", "HEAD^{tree}"),
        "upstream_commit": upstream,
        "supplier_source_tree": t["upstream_source_tree"],
        "target_sha256": sha256(TARGET.read_bytes()),
        "proof_source_preserved": True,
    }

def module_name(path: str) -> str:
    require(path.endswith(".lean") and not path.startswith("/") and ".." not in Path(path).parts,
            "Unsafe source module path")
    return path[:-5].replace("/", ".")

def imports_of(source: str) -> list[str]:
    # Source-level approximation; no elaboration or preprocessor expansion.
    found = []
    for line in source.splitlines():
        match = IMPORT_LINE.match(line)
        if match:
            found.append(match.group(1))
    return found

def source_closure(roots: list[str], edges: dict[str, list[str]]) -> dict:
    seen, unresolved = set(), set()
    queue = deque(roots)
    while queue:
        mod = queue.popleft()
        if mod in seen:
            continue
        if mod not in edges:
            unresolved.add(mod)
            continue
        seen.add(mod)
        for imported in edges[mod]:
            if imported not in seen:
                queue.append(imported)
    return {"source_module_count": len(seen),
            "external_or_missing_import_count": len(unresolved),
            "unresolved_import_examples": sorted(unresolved)[:30],
            "module_examples": sorted(seen)[:24]}

def source_scan(src: Path, terms: list[str]) -> dict:
    require(src.is_dir() and not src.is_symlink(), "Supplier source root missing or linked")
    counts = dict.fromkeys(terms, 0)
    rows = {term: [] for term in terms}
    imports = {}
    count = total_bytes = 0
    started = time.monotonic()
    for directory, subdirs, filenames in os.walk(src, topdown=True, followlinks=False):
        subdirs.sort()
        filenames.sort()
        directory_path = Path(directory)
        for name in subdirs:
            require(not (directory_path / name).is_symlink(), "Supplier contains directory link")
        for name in filenames:
            if not name.endswith(".lean"):
                continue
            file = directory_path / name
            mode = file.lstat().st_mode
            require(stat.S_ISREG(mode), "Not a regular supplier Lean file")
            size = file.stat().st_size
            require(size <= MAX_FILE_BYTES, "Supplier Lean file too large for bounded search")
            rel = file.relative_to(src).as_posix()
            count += 1
            require(count <= MAX_SOURCE_FILES, "Source-file search limit exceeded")
            total_bytes += size
            data = file.read_bytes()
            require(len(data) == size, "Supplier file changed during scan")
            contents = data.decode("utf-8", errors="strict")
            module = module_name(rel)
            require(module not in imports, "Duplicate normalized module path")
            imports[module] = imports_of(contents)
            for line_no, line in enumerate(contents.splitlines(), start=1):
                for term in terms:
                    if term in line:
                        counts[term] += line.count(term)
                        if len(rows[term]) < MAX_MATCHES_PER_TERM:
                            rows[term].append({"module": module,
                                               "source_path": "src/" + rel,
                                               "line": line_no,
                                               "excerpt": line.strip()[:260]})
    return {
        "schema": "OPICA_SOURCE_SCAN_V1",
        "status": "SOURCE_ONLY_COMPLETED_NOT_A_PROOF",
        "lean_source_files": count,
        "source_bytes_read": total_bytes,
        "source_terms_counts": counts,
        "bounded_term_occurrences": rows,
        "import_edges": imports,
        "elapsed_seconds_observed": round(time.monotonic() - started, 3),
        "source_level_only": True,
        "proof_acceptance": False,
    }

def analyze(t: dict, observation: dict) -> dict:
    edges = observation.pop("import_edges")
    roots = t["frontier_roots"]
    full = source_closure(["Main"], edges)
    minimal_candidate = source_closure([
        "Statements",
        "Development.AutomorphicArithmetic.CharacterBoxes.ClaimStrip",
        "Development.AutomorphicArithmetic.CharacterBoxes.MainConclusion",
    ], edges)
    independent = source_closure([
        "Development.AutomorphicArithmetic.CharacterBoxes.ClaimStrip",
    ], edges)
    observation["source_import_frontier"] = {
        "Main": full,
        "candidate_Statements_plus_ClaimStrip_plus_MainConclusion": minimal_candidate,
        "ClaimStrip_only_no_analytic_supplier": independent,
        "main_minus_candidate_modules": full["source_module_count"] -
            minimal_candidate["source_module_count"],
        "scope": "Lexically reconstructed project import DAG; does NOT prove correct Lean visibility, cache reuse, equivalent theorem or faster runtime",
    }
    observation["native_C1_symbol_in_supplier_source"] = observation["source_terms_counts"].get(
        "CofinalMomentSliceVanishingErrorBounds", 0)
    observation["independent_C1_certificate_found"] = False
    observation["native_compiler_compatible_without_rebuild"] = False
    observation["search_target"] = t["search_target"]
    observation["target_conclusion"] = "CANDIDATES_ONLY_TYPED_KERNEL_QUALIFICATION_REQUIRED"
    observation["rh_status"] = "OPEN"
    return observation

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    require(not a.output.exists() and a.output.is_absolute(), "Fresh absolute evidence path required")
    t = read_target()
    state = verify_source_state(t)
    result = analyze(t, source_scan(REPO / "src", t["source_terms"]))
    result.update(source_identity=state)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    summary = a.output.with_suffix(".md")
    with summary.open("x", encoding="utf-8") as stream:
        stream.write("# OPICA first-contact supplier scan (source-only)\n\n")
        stream.write(f"Exact checked head: \`{state['actual_head']}\`.\n\n")
        stream.write(f"Scanned {result['lean_source_files']:,} Lean source files with an unmodified pinned source tree.\n\n")
        for name, count in result["source_terms_counts"].items():
            stream.write(f"- \`{name}\`: {count} lexical occurrences\n")
        stream.write("\n## Source-only import closure\n\n")
        for label, value in result["source_import_frontier"].items():
            if isinstance(value, dict) and "source_module_count" in value:
                stream.write(f"- {label}: {value['source_module_count']:,} source modules\n")
        stream.write("\n**Not compiled and not kernel checked.** OPICA C1 and RH remain OPEN.\n")
    print(json.dumps({"status": result["status"], "head": state["actual_head"],
                      "lean_source_files": result["lean_source_files"],
                      "frontier": {k:v["source_module_count"] for k,v in
                          result["source_import_frontier"].items()
                          if isinstance(v,dict) and "source_module_count" in v},
                      "proof_acceptance": False, "rh_status": "OPEN"}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
