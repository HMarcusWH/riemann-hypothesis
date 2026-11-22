#!/usr/bin/env python3
"""Actual native OPICA typed C1 search. No RH-derived theorem is admissible."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path


def run(controller: Path, native: Path, output: Path):
    plan = json.loads((controller / "research/opica_governed/PLAN.json").read_text())
    goal = plan["target_c1"]
    if plan["schema"] != "OPICA_GOVERNED_RESEARCH_CAMPAIGN_V1" or output.exists():
        raise RuntimeError("wrong target scope or existing result")
    from run_frozen_native_retrieval import enforce_source
    source = enforce_source(controller, native, plan)
    sys.path.insert(0, str(native))
    from research.RHRC.integration.opica_composition.canonical import digest, load_bytes, require
    from research.RHRC.integration.opica_composition.contracts import (
        StatementContract, StatementInventory, TargetSpec, GrammarProfile,
        SearchBudget, CompositionProposal, PER_ATTEMPT_GATES)
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.qualification import atlas_driver
    from research.RHRC.integration.opica_composition.proposals import enumerate_candidates, used_constant_ids
    from research.RHRC.integration.opica_composition.executor import run_worker, execute_attempt, lean_name
    from research.RHRC.integration.opica_composition.tests.test_executor import (
        native_context, fresh, independently_verify)
    from research.RHRC.integration.opica_composition.snapshot import file_hash

    worker, snapshot, _ = native_context()
    require((snapshot.commit, snapshot.tree) == (plan["native_commit"], plan["native_tree"]),
            "current native compiler source/checkout differs")
    require(snapshot.source_policy == "DRAFT", "unexpected native authority elevation")
    expected_declaration = "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"
    required_names = {"cofinal_moment_slice_bounds_of_even",
                      "cofinal_moment_slice_bounds_of_odd",
                      "cofinal_moment_slice_bounds_of_tendsto"}
    allowed = goal["allowed_lemmas"]
    require(goal["declaration"] == expected_declaration
            and goal["module"] == "Zeta23.OPICARound4.ArithmeticFrontier.MomentSlices"
            and goal["type_kind"] == "value", "original C1 target drift")
    require(len(allowed) == 3
            and {r["declaration"].split(".")[-1] for r in allowed} == required_names,
            "independent non-RH arithmetic source menu changed")
    for row in allowed:
        require(row["module"] == "Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure",
                "unexpected source theorem")
        require("riemannHypothesis" not in row["declaration"],
                "RH-derived theorem may not enter C1 menu")
        require(file_hash(native / (row["module"].replace(".", "/") + ".lean")),
                "approved theorem's original source unavailable")

    # Generate the SAME kind of native compiler type-DAG audit used by the
    # original governed deduction tests, never a source string supplied by a
    # proposer. All names are pinned in the reviewed PLAN.json.
    tick = chr(96)
    driver = ("import Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure\n"
              "import Zeta23.RHRC.OpicaComposition.Export\n" + atlas_driver(allowed))
    for item in allowed:
        driver += ("\nrun_cmd Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants "
                   + tick + lean_name(item["declaration"]) + ' "type"\n')
    driver += ("\nrun_cmd Zeta23.RHRC.OpicaComposition.exportTarget "
               + tick + lean_name(expected_declaration) + ' "value"\n')
    driver += ("run_cmd Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants "
               + tick + lean_name(expected_declaration) + ' "value"\n')
    folder = fresh("c1-direct-arithmetic")
    folder.mkdir()
    (folder / "C1Audit.lean").write_text(driver, encoding="utf-8")
    measured = run_worker(worker, folder, "C1Audit.lean", "C1Audit.olean",
                          SearchBudget(**(worker.budget or {})))
    require(measured["exit_code"] == 0 and measured["resource_status"] is None,
            "fresh native Lean compiler type-DAG extraction failed")
    logbytes = (folder / "C1Audit.lean.log").read_bytes()
    statements, targets, proofs = {}, [], []
    for line in logbytes.splitlines():
        if line.startswith(b"OPICA3_ATLAS\t"):
            row = load_bytes(line.split(b"\t", 1)[1])
            require(row["declaration"] not in statements, "duplicated Lean declaration")
            statements[row["declaration"]] = row
        elif line.startswith(b"OPICA_TARGET\t"):
            targets.append(load_bytes(line.split(b"\t", 1)[1]))
        elif line.startswith(b"OPICA_RETRIEVAL_PROOFS\t"):
            proofs.append(load_bytes(line.split(b"\t", 1)[1]))
    require(set(statements) == {x["declaration"] for x in allowed}
            and len(targets) == 1 and len(proofs) == 4,
            "native compiler did not export all bound C1 contracts")
    rows = []
    for i, item in enumerate(allowed):
        row = statements[item["declaration"]]
        require(row["module"] == item["module"], "theorem origin differs")
        require(set(row["axioms"]) <= set(plan["allowed_axioms"]),
                "not allowed native project axioms")
        require(not any(bad in row["value_constants"] for bad in goal["forbidden_lemmas"]),
                "approved source depends on an RH-derived shortcut")
        c = StatementContract(
            declaration=row["declaration"], module=row["module"],
            type_expression=row["type_expression"],
            type_sha256=expression_hash(row["type_expression"]),
            universe_parameters=row["universe_parameters"],
            outer_telescope=row["outer_telescope"],
            conclusion_text=row["conclusion_text"],
            type_constants=row["type_constants"],
            value_constants=row["value_constants"], axioms=row["axioms"])
        require(type(proofs[i]) is list, "compiler proof-erasure inventory missing")
        rows.append({**c.to_dict(), "proof_constants": proofs[i]})
    target_expression = targets[0]
    target_hash = expression_hash(target_expression)
    require(type(proofs[-1]) is list, "target proof-erasure inventory missing")
    constants, table = {}, []
    for item in allowed:
        cid = digest({"source_generation": snapshot.generation,
                      "declaration": item["declaration"], "module": item["module"]},
                     domain="OPICA_APPROVED_CONSTANT_V1")
        constants[cid] = item["declaration"]
        table.append({"id": cid, "declaration": item["declaration"],
                      "module": item["module"], "role": "constant"})
    forbidden = sorted(set(goal["forbidden_lemmas"] + [
        "Zeta23.OPICAComposition.cofinal_newborn_packet_calibration",
        "Zeta23.OPICAComposition.cofinal_schur_packet_calibration"]))
    target = TargetSpec(goal["target_id"], expected_declaration, goal["module"],
                        target_hash, constants, plan["allowed_axioms"],
                        [goal["module"], allowed[0]["module"]],
                        list(PER_ATTEMPT_GATES), "value", forbidden)
    inventory = StatementInventory(
        snapshot.generation, rows, hashlib.sha256(logbytes).hexdigest())
    budget = SearchBudget(candidates=8, term_nodes=384, term_depth=16,
                          wall_seconds=90, heartbeats=800000)
    batch = enumerate_candidates(
        inventory, target, GrammarProfile(forbidden, []), budget,
        search_contract={"expected_expression": target_expression,
                         "statements": rows, "proof_constants": proofs[-1]})
    retrieved = [x for x in batch.candidates if x.get("scientific_scope") ==
                 "BOUNDED_TARGET_DIRECTED_RETRIEVAL_NOT_PROOF"]
    attempted = []
    for cand in retrieved:
        used = used_constant_ids(cand["term_plan"])
        require(set(used) <= set(constants), "unapproved source in C1 plan")
        proposal = CompositionProposal(
            cand["action_id"], target.target_id, snapshot.generation, cand["term_plan"])
        raw = execute_attempt(proposal, target, snapshot,
                              fresh("c1-kernel-attempt"), worker=worker, constant_table=table)
        row = {"action_id": cand["action_id"], "producer_status": raw.status,
               "producer_reason": raw.reason, "independent_status": "NOT_RUN",
               "approved_constants": sorted(constants[x] for x in used)}
        if raw.status == "PROVED_CONDITIONAL":
            checked = independently_verify(raw, target)
            row["independent_status"] = checked.status
        attempted.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "OPICA_NATIVE_C1_RESTRICTED_SEARCH_V1",
        "status": "NATIVE_TYPED_SEARCH_COMPLETED_UNDER_REVIEWED_MENU",
        "source": source, "native_generation": snapshot.generation,
        "native_type_export_sha256": hashlib.sha256(logbytes).hexdigest(),
        "c1_compiler_type_sha256": target_hash,
        "native_statements": {r["declaration"]: r["type_sha256"] for r in rows},
        "reviewed_target": target.to_dict(), "approved_sources": allowed,
        "candidate_count": len(retrieved), "candidate_attempts": attempted,
        "bounded_menu_disposition": batch.disposition,
        "bounded_menu_complete": batch.complete,
        "original_native_11_lanes": "NOT_RUN_BY_THIS_SEARCH",
        "community_v4_36_supplier_import": "NOT_RUN_CROSS_VERSION_BOUNDARY",
        "no_unqualified_rh_claim": True,
        "proof_acceptance": False, "RH": "OPEN", "Step4": "OPEN",
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")
    print(json.dumps({"status": result["status"], "candidate_count": len(retrieved),
                      "bounded_menu": batch.disposition, "RH": "OPEN"}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.controller.resolve(), args.native.resolve(), args.output.resolve())
