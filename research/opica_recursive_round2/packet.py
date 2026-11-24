"""Consolidate observed receipts into the ten-file R2 research packet."""
import argparse,os
from pathlib import Path
from r2_common import *

def packet(inputs,out,controller):
    out.mkdir(parents=True,exist_ok=False);errors=[];artifacts={}
    def load(rel,default):
        p=inputs/rel
        try:
            r=read(p);artifacts[rel]=filehash(p);return r
        except Exception as ex:errors.append({"input":rel,"reason":str(ex)[:500]});return default
    harvest=load("harvest/harvest.json",{})
    epoch=load("native/epoch.json",{})
    inventory=load("native/search/inventory.json",{})
    if inventory:
        for row in inventory.get("native_rows",[])+inventory.get("external_research_rows",[]):
            try:
                verify_dependency_row(row,inputs/"native/search")
                artifacts["native/search/"+row["dependency_file"]]=row["dependency_archive_sha256"]
            except Exception as ex:errors.append({"input":row.get("declaration"),"reason":"Dependency evidence: "+str(ex)[:500]})
    graph=load("native/search/graph.json",{"nodes":[],"edges":[],"queries":[],"roots":[]})
    compiler=load("native/search/compiler.json",{})
    math_cut=load("native-math-cut/receipt.json",{}) if (inputs/"native-math-cut/receipt.json").is_file() else {}
    evidence_sync=load("evidence-sync/EVIDENCE_LEDGER.json",{}) if (inputs/"evidence-sync/EVIDENCE_LEDGER.json").is_file() else {}
    original_focus={}
    if (inputs/"original-focus/original-focus-receipt.json").is_file():
        original_focus=load("original-focus/original-focus-receipt.json",{})
        try:
            need(original_focus["schema"]=="OPICA_R2_ORIGINAL_FOCUS_V1" and original_focus["proof_acceptance"] is False and original_focus["controller"]==controller and original_focus["native"]==LOCK["native"],"Original-only focus scope differs")
            if original_focus["status"]=="ORIGINAL_FOCUS_RESEARCH_EXECUTED_NOT_PROOF":
                for leaf,key in (("original-focus-graph.json","graph_sha256"),("original-focus-candidates.json","candidates_sha256")):
                    rel="original-focus/"+leaf
                    need(filehash(inputs/rel)==original_focus[key],"Original-only focus bytes differ")
                    artifacts[rel]=original_focus[key]
                # Focus proposals are separate research contacts, never
                # silently merged into the native proof-validation ledger.
        except Exception as ex:errors.append({"input":"original-focus","reason":str(ex)[:500]})
    feedback={}
    if (inputs/"native/recursive-feedback/index.json").is_file():
        feedback=load("native/recursive-feedback/index.json",{})
        try:
            need(feedback["schema"]=="OPICA_R2_RECURSIVE_FEEDBACK_V1" and feedback["native"]==epoch.get("native") and feedback["proof_acceptance"] is False,"Feedback index scope differs")
            for item in feedback["registered"]:
                row=item["row"]
                verify_dependency_row(row,inputs/"native/recursive-feedback")
                artifacts["native/recursive-feedback/"+row["dependency_file"]]=row["dependency_archive_sha256"]
        except Exception as ex:errors.append({"input":"recursive-feedback","reason":str(ex)[:500]})
    validations=[]
    for rel in ("native/validation/review.json","native/feedback-validation/review.json","mixed/review.json","native/alternate/review.json","native/feedback-alternate/review.json","mixed/alternate/review.json"):
        p=inputs/rel
        if p.is_file():validations.append({"path":rel,"receipt":load(rel,{})})
    canonical=[]
    for key in ("canonical","registration"):
        p=inputs/"canonical"/(key+".json")
        if p.is_file():canonical.append({"key":key,"receipt":load("canonical/"+key+".json",{})})
    goals={n["id"]:n for n in graph["nodes"]}
    need(len(goals)==len(graph["nodes"]),"Duplicate graph goal")
    manifests={};coverage=[]
    pairs=(("native/search/native-candidates.json","native/validation/review.json","native"),
           ("native/search/mixed-candidates.json","mixed/review.json","mixed"),
           ("native/feedback-candidates.json","native/feedback-validation/review.json","native"))
    for rel,review_path,mode in pairs:
        if (inputs/rel).is_file():
            m=load(rel,{})
            try:
                need(m["schema"]=="OPICA_R2_CANDIDATE_MANIFEST_V1" and m["proof_acceptance"] is False and m["mode"]==mode and m["native"]==epoch.get("native"),"Candidate manifest scope differs")
                ids=[c["id"] for c in m["selected"]]
                need(len(ids)==len(set(ids)),"Duplicate selected candidate")
                records=[v["receipt"] for v in validations if v["path"]==review_path]
                need(len(records)<=1,"Duplicate validation receipt")
                observed=[]
                if records:
                    v=records[0]
                    need(v["schema"]=="OPICA_R2_VALIDATION_V1" and v["mode"]==mode and v["native"]==m["native"] and v["proof_acceptance"] is False,"Validation receipt scope differs")
                    observed=[r["id"] for r in v["results"]]
                    need(len(observed)==len(set(observed)) and set(observed)<=set(ids),"Unselected or duplicate result")
                coverage.append({"manifest":rel,"selected":len(ids),"observed":len(observed),"missing":sorted(set(ids)-set(observed)),"receipt_present":bool(records),"omitted_budget":m.get("omitted_budget",0)})
            except Exception as ex:
                errors.append({"input":rel,"reason":str(ex)[:500]})
            for cand in m.get("selected",[]):
                old=manifests.get(cand["id"])
                need(old is None or old==cand,"Conflicting candidate identity")
                manifests[cand["id"]]=cand
    allresults=[r for v in validations for r in v["receipt"].get("results",[])]
    local=[];alternate=[]
    def identity(r):
        return (r["id"],r["goal_id"],r["target"]["declaration"],r["expected_type_sha256"],r["candidate_plan_sha256"],r["target"].get("world","NATIVE_QUERY"))
    for v in validations:
        receipt=v["receipt"]
        for r in receipt.get("results",[]):
            if not (r.get("actual_local_kernel_proof") and r.get("status")=="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"):continue
            try:
                cand=manifests[r["id"]];goal=goals[cand["goal_id"]]
                need(r["goal_id"]==cand["goal_id"] and goal["declaration"]==cand["target"]["declaration"] and goal["type_sha256"]==cand["expected_type_sha256"] and goal.get("world","NATIVE_QUERY")==cand["target"].get("world","NATIVE_QUERY"),"Candidate not bound to exact graph goal")
                need(receipt.get("schema")=="OPICA_R2_VALIDATION_V1" and receipt.get("proof_acceptance") is False and receipt.get("native")==epoch.get("native") and r["target"]==cand["target"] and r["expected_type_sha256"]==cand["expected_type_sha256"] and r["candidate_plan_sha256"]==digest(cand["plan"]),"Candidate type/plan/epoch drift")
                need(r.get("actual_local_kernel_proof") is True and set(r["axioms"])<=ALLOWED and all(r["stages"][k]["status"]=="PASS" for k in ("actual_types","kernel","independent_type","fresh_stock_kernel")),"Incomplete local proof gates")
                if receipt["mode"]=="native":need(r["actual_type_sha256"]==cand["expected_type_sha256"] and r["cross_pin_definition_equivalence"]=="SAME_NATIVE_PIN","Native actual target differs")
                else:need(receipt["mode"]=="mixed" and r["cross_pin_definition_equivalence"]=="REVIEW_REQUIRED","Mixed semantic disposition differs")
                local.append({**r,"validation_mode":receipt["mode"]})
            except Exception as ex:errors.append({"input":r.get("id"),"reason":str(ex)[:500]})
    local_keys={(identity(r),r["validation_mode"]) for r in local}
    for v in validations:
        receipt=v["receipt"]
        for r in receipt.get("results",[]):
            if r.get("status")!="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY":continue
            try:
                need(receipt.get("schema")=="OPICA_R2_ALTERNATE_KERNEL_V2" and receipt.get("proof_acceptance") is False and receipt.get("status")=="CHECKED_SELECTED_CLOSURES" and receipt.get("negative_controls")=="PASS" and receipt.get("native")==epoch.get("native") and (identity(r),receipt.get("mode")) in local_keys,"Alternate receipt not bound to complete checker/epoch/local candidate")
                alternate.append({**r,"validation_mode":receipt["mode"]})
            except Exception as ex:errors.append({"input":r.get("id"),"reason":str(ex)[:500]})
    alt_ids={identity(r) for r in alternate}
    terminal=[r for r in alternate if r["validation_mode"]=="native" and r.get("terminal_candidate",{}).get("status")=="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY"]
    roots=set(graph["roots"])
    def goal_key(n):return (n["id"],n["declaration"],n["type_sha256"],n.get("world","NATIVE_QUERY"))
    verified_targets={(r["goal_id"],r["target"]["declaration"],r["expected_type_sha256"],r["target"].get("world","NATIVE_QUERY")) for r in local if r["validation_mode"]=="native"}
    frontier=[n for n in graph["nodes"] if n["id"] not in roots and goal_key(n) not in verified_targets]
    qs=graph["queries"]
    missing=[]
    if not harvest.get("artifact_receipts",{}).get("original"):missing.append("AUTHENTICATED_EXTERNAL_GRAPH_NOT_AVAILABLE")
    if not harvest.get("artifact_receipts",{}).get("historical"):missing.append("HISTORICAL_INDEPENDENT_COMPARISON_NOT_AVAILABLE")
    if epoch.get("historical_status")!="HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH":missing.append("HISTORICAL_NATIVE_INTEGRATION_PENDING")
    if graph.get("truncation") or graph.get("failures") or any(not q.get("bounded_complete") for q in qs):missing.append("BOUNDED_SEARCH_OR_FRONTIER_INCOMPLETE")
    if not validations:missing.append("NO_KERNEL_VALIDATION_RECEIPT")
    if any(x["missing"] or (x["selected"] and not x["receipt_present"]) or x["omitted_budget"] for x in coverage):missing.append("CANDIDATE_POPULATION_INCOMPLETE_OR_BUDGETED")
    # Deliberately excluded endpoints/non-proof rows are part of the admissible
    # inventory boundary, not failed compilation. Every other failure is blocking.
    intentional={"EXCLUDED_ENDPOINT","NON_PROOF_OR_CONTAMINATED"}
    inventory_incomplete=compiler.get("status")!="COMPILER_RESEARCH_INVENTORY_EXPORTED" or any(f.get("status") not in intentional for f in compiler.get("failures",[]))
    if inventory_incomplete:missing.append("COMPILER_INVENTORY_INCOMPLETE")
    if any(r.get("status") in ("RESOURCE_EXHAUSTED","INDEPENDENT_REPLAY_FAILED","INDEPENDENT_CHECKER_UNAVAILABLE","ADAPTER_REQUIRED","UNRESOLVED","INCOMPLETE","REJECTED_OR_INCOMPLETE") for r in allresults):missing.append("CANDIDATE_EXECUTION_INCOMPLETE")
    readiness=harvest.get("expanded_search_readiness",{})
    if readiness.get("status")=="WAITING_FOR_UPSTREAM_EVIDENCE":missing.append("WAITING_FOR_UPSTREAM_EVIDENCE")
    if not feedback and (inputs/"native/feedback-candidates.json").is_file():missing.append("LEGACY_OR_INCOMPLETE_RECURSIVE_FEEDBACK")
    if feedback and (feedback.get("errors") or feedback.get("status") in ("FEEDBACK_INCOMPLETE","FEEDBACK_RESOURCE_LIMIT","FEEDBACK_ROUND_CAP_REACHED")):missing.append("RECURSIVE_FEEDBACK_INCOMPLETE_OR_BOUNDED")
    research_missing=list(missing)
    production_missing=[]
    if not any(x.get("key")=="canonical" for x in canonical):production_missing.append("CANONICAL_PATCH_REVIEW_PENDING")
    if not any(x.get("key")=="registration" for x in canonical):production_missing.append("DISPATCH_REGISTRATION_PATCH_REVIEW_PENDING")
    production_missing+=["CANONICAL_PRODUCTION_11_LANE_AND_3_GROUP_ACCEPTANCE_NOT_ESTABLISHED","MANUAL_DISPATCH_AND_SIGNED_SCALAR_GOVERNED_TARGET_RESULTS_PENDING_OR_UNADMITTED","EXTERNAL_TO_NATIVE_SEMANTIC_ADAPTER_REVIEW_REQUIRED"]
    missing+=production_missing
    outcome="INCOMPLETE_EXECUTION" if errors else "STEP4_CLOSURE_CANDIDATE" if terminal else "NEW_SUPPORTING_THEOREM" if any(identity(r) in alt_ids for r in local) else "INCOMPLETE_EXECUTION" if research_missing or not qs else "CANDIDATES_IN_ENUMERATED_SCOPE" if any(q.get("plans") for q in qs) else "NO_MATCH_IN_ENUMERATED_SCOPE"
    bounded="INCOMPLETE_SEARCH_SCOPE" if inventory_incomplete or not qs or graph.get("truncation") or graph.get("failures") or any(not q.get("bounded_complete") for q in qs) else "CANDIDATES_IN_ENUMERATED_SCOPE" if any(q.get("plans") for q in qs) else "NO_MATCH_IN_ENUMERATED_SCOPE"
    # All statuses stay scoped to the isolated research epoch. The release gate
    # is intentionally not callable from this hosted R2 workflow.
    write(out/"RUN_MANIFEST.json",{"schema":"OPICA_R2_RUN_MANIFEST_V1","controller":controller,"lock_sha256":filehash(HERE/"LOCK.json"),"epoch":epoch,"input_sha256":artifacts,"workflow_results":os.environ.get("R2_WORKFLOW_RESULTS","UNAVAILABLE"),**CLAIMS})
    write(out/"WORKFLOW_HARVEST.json",{"prior_campaigns":harvest,"canonical_patch_reviews":canonical,"compiler":compiler,"recursive_feedback":feedback,"candidate_coverage":coverage,"native_math_cut":math_cut,"original_focus":original_focus,"cross_repository_evidence":evidence_sync,"errors":errors,**CLAIMS})
    write(out/"QUALIFIED_THEOREM_INVENTORY.json",{"scope":"FRESH_RESEARCH_INVENTORY_ONLY","native_rows":inventory.get("native_rows",[]),"external_research_rows":inventory.get("external_research_rows",[]),"requested_native_roots":inventory.get("requested_native_roots"),"production_admission":"NOT_ESTABLISHED",**CLAIMS})
    write(out/"PROOF_OBLIGATION_GRAPH.json",{"nodes":graph["nodes"],"edges":graph["edges"],"roots":graph["roots"],"queries":[{k:v for k,v in q.items() if k!="plans"}|{"candidate_ids":[p["id"] for p in q.get("plans",[])]} for q in qs],"truncation":graph.get("truncation",[]),"authority":"RESEARCH_CONTACTS_NOT_PROOFS",**CLAIMS})
    candidate_rows=[]
    for q in qs:
        candidate_rows+=q.get("plans",[])
    candidate_rows+=list(manifests.values())
    seen=set();unique=[]
    for c in candidate_rows:
        if c["id"] not in seen:seen.add(c["id"]);unique.append(c)
    write(out/"CANDIDATE_COMPOSITIONS.json",{"candidates":unique,"scope":"BOUNDED_TYPED_PLANS_NOT_PROOF","validation_coverage":coverage,"validation_attempts":len([r for r in allresults if "expected_type_sha256" in r and r.get("status")!="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY"]),"local_successes":len(local),**CLAIMS})
    write(out/"KERNEL_VALIDATION.json",{"receipts":validations,"local_exact_proof_count":len(local),"alternate_root_count":len(alternate),"terminal_candidates":terminal,**CLAIMS})
    write(out/"CIRCULARITY_AND_FALSIFICATION.json",{"inventory_exclusions":inventory.get("exclusions",[]),"query_failures":graph.get("failures",[]),"rejected_candidates":[r for r in allresults if r.get("status") not in ("PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED","PASS_ALTERNATE_SELECTED_CLOSURE_ONLY")],"claim":"No claim of mathematical falsification follows from a failed or incomplete search.",**CLAIMS})
    nextgoals=[n for n in graph["nodes"] if goal_key(n) not in verified_targets]
    nextgoals.sort(key=lambda n:(n["id"] in roots,n.get("depth",0),n["declaration"]))
    write(out/"NEXT_ROUND_TARGETS.json",{"targets":nextgoals[:64],"unvisited":graph.get("truncation",[]),"requires_reviewed_epoch_update":True,"not_an_automatic_registry_promotion":True,**CLAIMS})
    lines=["# R2 remaining mathematical obligations","","Exact local proofs: "+str(len(local))+". Alternate checker passes: "+str(len(alternate))+".","", "## Open terminal targets"]
    for n in graph["nodes"]:
        if n["id"] in roots:lines.append("- "+n["declaration"]+": "+("local proof candidate; admission pending" if goal_key(n) in verified_targets else "OPEN"))
    lines+=["","## Exposed frontier (research contacts only; full types in NEXT_ROUND_TARGETS.json)"]
    for n in frontier[:40]:lines.append("- "+n["label"]+" ("+n["type_sha256"]+")")
    lines+=["","## Missing execution/admission gates"]+["- "+m for m in missing]+["","RH, C1 and Step4 remain OPEN."]
    (out/"REMAINING_MATHEMATICS.md").write_text("\n".join(lines)+"\n")
    write(out/"STEP4_VERDICT.json",{"schema":"OPICA_R2_STEP4_VERDICT_V1","outcome":outcome,"bounded_search_outcome":bounded,"expanded_search_readiness":readiness,"research_missing_gates":research_missing,"production_missing_gates":production_missing,"missing_gates":missing,"input_errors":errors,"local_exact_proof_count":len(local),"alternate_kernel_count":len(alternate),"terminal_candidates":terminal,"reduced_frontier_certified":False,"scope":"ISOLATED_RESEARCH_NOT_RELEASE",**CLAIMS})
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--repo",type=Path,required=True)
    a=p.parse_args();packet(a.inputs,a.out,controller_scope(a.repo))
if __name__=="__main__":main()
