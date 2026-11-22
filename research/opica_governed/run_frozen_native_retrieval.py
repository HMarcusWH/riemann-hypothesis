#!/usr/bin/env python3
"""Use the ORIGINAL native OPICA typed-DAG proposer on frozen non-calibration targets.

NO Lean compilation happens in this fast lane. It is NOT a proof-validity gate.
Proof search on the exact native kernel is a separately required runner lane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, timeout=60).stdout.strip()


def enforce_source(fork: Path, native: Path, spec: dict) -> dict:
    if git(native, "rev-parse", "HEAD") != spec["native_commit"]:
        raise RuntimeError("native OPICA source HEAD differs")
    if git(native, "rev-parse", "HEAD^{tree}") != spec["native_tree"]:
        raise RuntimeError("native OPICA source tree differs")
    if git(fork, "rev-parse", "HEAD:src") != spec["supplier_source_tree"]:
        raise RuntimeError("synced proof supplier source was modified")
    if git(fork, "rev-parse", spec["supplier_commit"] + ":src") != spec["supplier_source_tree"]:
        raise RuntimeError("published supplier source tree differs")
    for rel, blob in spec["native_search_source"].items():
        if git(native, "rev-parse", "HEAD:" + rel) != blob:
            raise RuntimeError("native governed search source differs: " + rel)
    if git(native, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("native checked source has tracked modifications")
    if git(fork, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("fork tracked source is modified")
    return {"fork_head": git(fork, "rev-parse", "HEAD"),
            "supplier_source_tree": spec["supplier_source_tree"],
            "native_head": spec["native_commit"], "native_tree": spec["native_tree"]}


def run(fork: Path, native: Path, output: Path) -> dict:
    if output.exists():
        raise RuntimeError("replayed output must be a new file")
    spec = json.loads((fork / "research/opica_governed/PLAN.json").read_text())
    if spec["schema"] != "OPICA_GOVERNED_RESEARCH_CAMPAIGN_V1":
        raise RuntimeError("reviewed target schema differs")
    state = enforce_source(fork, native, spec)
    sys.path.insert(0, str(native))
    # Exact native engine: real source-bound TARGETS, typed DAGs and typed search.
    from research.RHRC.integration.opica_composition.canonical import digest, load_bytes, require
    from research.RHRC.integration.opica_composition.contracts import (
        GrammarProfile, SearchBudget, StatementInventory)
    from research.RHRC.integration.opica_composition.proposals import enumerate_candidates, used_constant_ids
    from research.RHRC.integration.opica_composition.service import _target, _search_contract

    root = native / "research/RHRC/integration/opica_composition"
    doc = load_bytes((root / "SEARCH_CONTRACTS.json").read_bytes())
    public = load_bytes((root / "PUBLIC_TARGETS.json").read_bytes())
    ids = spec["frozen_native_typed_targets"]
    require(doc["schema"] == "OPICA4_SEARCH_CONTRACTS_V1"
            and doc["kernel_acceptance"] is False
            and [x["target_id"] for x in doc["targets"]] == ids,
            "frozen compiler typed target registry differs")
    require(len(doc["statements"]) == 6 and len({r["declaration"] for r in doc["statements"]}) == 6,
            "native typed retrieval statement inventory differs")
    require([x["id"] for x in public["intermediate"]] == ids,
            "public target registration order differs")
    generation = digest({
        "controller_tree": git(fork, "rev-parse", "HEAD^{tree}"),
        "native_tree": spec["native_tree"],
        "native_registered_targets": hashlib.sha256((root / "PUBLIC_TARGETS.json").read_bytes()).hexdigest(),
        "supplier_tree": spec["supplier_source_tree"]
    }, domain="OPICA_CROSSREPO_PREVIEW_SOURCE_GENERATION_V1")
    identity = SimpleNamespace(generation=generation)
    search_budget = SearchBudget(candidates=8, term_nodes=2048, term_depth=32,
                                 wall_seconds=90, heartbeats=800000)
    # Explicit sentinel: the fast lane has not freshly exported a compiler object.
    inventory = StatementInventory(generation, [], "0" * 64)
    rows = []
    for name in ids:
        target, table = _target(native, identity, name)
        contract = _search_contract(native, target)
        require(contract is not None, "reviewed typed retrieval contract missing")
        batch = enumerate_candidates(inventory, target, GrammarProfile([], []),
                                     search_budget, search_contract=contract)
        retrieved = [r for r in batch.candidates if r.get("scientific_scope") ==
                     "BOUNDED_TARGET_DIRECTED_RETRIEVAL_NOT_PROOF"]
        candidates = []
        for item in retrieved:
            names = sorted(target.allowed_constants[cid] for cid in used_constant_ids(item["term_plan"]))
            require(len(names) == 2, "expected two independently approved native links")
            candidates.append({"action_id": item["action_id"],
                               "term_plan": item["term_plan"],
                               "used_native_declarations": names,
                               "provenance": item["search_provenance"],
                               "kernel_acceptance": False})
        rows.append({
            "target_id": name, "declaration": target.declaration,
            "expected_type_sha256": target.expected_type_hash,
            "constant_table": table, "reviewed_source_dag": True,
            "proposer_candidate_count": len(candidates), "candidates": candidates,
            "bounded_search_complete": batch.complete,
            "disposition": batch.disposition,
            "native_qualified_proof": "NOT_RUN_FAST_TYPED_LANE",
        })
    result = {
        "schema": "OPICA_NATIVE_GOVERNED_FIRST_CONTACT_TYPED_PREVIEW_V1",
        "status": "TYPED_DAG_RETRIEVAL_COMPLETE_NOT_PROOF",
        "checked": state, "native_generation_preview": generation,
        "source_contract_sha256": hashlib.sha256((root / "SEARCH_CONTRACTS.json").read_bytes()).hexdigest(),
        "targets": rows, "expected_native_targets": ids,
        "supplier_typed_import": "NOT_RUN_SEPARATE_LEAN_4_36_WORLD",
        "independent_c1_search": "PENDING_FRESH_NATIVE_COMPILER_LANE",
        "source_status": "PREVIEW_NO_PRODUCTION_SNAPSHOT",
        "kernel_acceptance": False, "original_11_lanes": "NOT_RUN_BY_THIS_JOB",
        "proof_acceptance": False, "RH": "OPEN", "Step4": "OPEN",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "targets": {r["target_id"]: r["proposer_candidate_count"] for r in rows},
                      "proof_acceptance": False, "RH": "OPEN"}), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fork", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.fork.resolve(), args.native.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
