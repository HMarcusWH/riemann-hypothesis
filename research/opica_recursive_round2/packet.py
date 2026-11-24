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
        for row in inventory.get("native_rows",[]):
            try:
                verify_dependency_row(row,inputs/"native/search")
                artifacts["native/search/"+row["dependency_file"]]=row["dependency_archive_sha256"]
            except Exception as ex:errors.append({"input":row.get("declaration"),"reason":"Dependency evidence: "+str(ex)[:500]})
    graph=load("native/search/graph.json",{"nodes":[],"edges":[],"queries":[],"roots":[]})
    compiler=load("native/search/compiler.json",{})
    validations=[]
    for rel in ("native/validation/review.json","native/feedback-validation/review.json","mixed/review.json","native/alternate/review.json","native/feedback-alternate/review.json","mixed/alternate/review.json"):
        p=inputs/rel
        if p.is_file():validations.append({"path":rel,"receipt":load(rel,{})})
    canonical=[]
    for key in ("canonical","registration"):
        p=inputs/"canonical"/(key+".json")
        if p.is_file():canonical.append({"key":key,"receipt":load("canonical/"+key+".json",{})})
    manifests={}
    for rel in ("native/search/native-candidates.json","native/search/mixed-candidates.json","native/feedback-candidates.json"):
        if (inputs/rel).is_file():
            m=load(rel,{})
            for cand in m.get("selected",[]):
                old=manifests.get(cand["id"])
                need(old is None or old==cand,"Conflicting candidate identity")
                manifests[cand["id"]]=cand
    allresults=[r for v in validations for r in v["receipt"].get("results",[])]
    local=[];alternate=[]
    def identity(r):
        return (r["id"],r["target"]["declaration"],r["expected_type_sha256"],r["candidate_plan_sha256"],r["target"].get("world","NATIVE_QUERY"))
    for v in validations:
        receipt=v["receipt"]
        for r in receipt.get("results",[]):
            if not (r.get("actual_local_kernel_proof") and r.get("status")=="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"):continue
            try:
                cand=manifests[r["id"]]
                need(receipt.get("native")==epoch.get("native") and r["target"]==cand["target"] and r["expected_type_sha256"]==cand["expected_type_sha256"] and r["candidate_plan_sha256"]==digest(cand["plan"]),"Candidate type/plan/epoch drift")
                local.append({**r,"validation_mode":receipt["mode"]})
            except Exception as ex:errors.append({"input":r.get("id"),"reason":str(ex)[:500]})
    local_keys={(identity(r),r["validation_mode"]) for r in local}
    for v in validations:
        receipt=v["receipt"]
        for r in receipt.get("results",[]):
            if r.get("status")!="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY":continue
            try:
                need(receipt.get("native")==epoch.get("native") and (identity(r),receipt.get("mode")) in local_keys,"Alternate receipt not bound to local candidate")
                alternate.append({**r,"validation_mode":receipt["mode"]})
            except Exception as ex:errors.append({"input":r.get("id"),"reason":str(ex)[:500]})
    alt_ids={identity(r) for r in alternate}
    terminal=[r for r in alternate if r["validation_mode"]=="native" and r.get("terminal_candidate",{}).get("status")=="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY"]
    roots=set(graph["roots"])
    def goal_key(n):return (n["declaration"],n["type_sha256"],n.get("world","NATIVE_QUERY"))
    verified_targets={(r["target"]["declaration"],r["expected_type_sha256"],r["target"].get("world","NATIVE_QUERY")) for r in local}
    frontier=[n for n in graph["nodes"] if n["id"] not in roots and goal_key(n) not in verified_targets]
    qs=graph["queries"]
    missing=[]
    if not harvest.get("artifact_receipts",{}).get("original"):missing.append("AUTHENTICATED_EXTERNAL_GRAPH_NOT_AVAILABLE")
    if not harvest.get("artifact_receipts",{}).get("historical"):missing.append("HISTORICAL_INDEPENDENT_COMPARISON_NOT_AVAILABLE")
    if epoch.get("historical_status")!="HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH":missing.append("HISTORICAL_NATIVE_INTEGRATION_PENDING")
    if graph.get("truncation") or graph.get("failures") or any(not q.get("bounded_complete") for q in qs):missing.append("BOUNDED_SEARCH_OR_FRONTIER_INCOMPLETE")
    if not validations:missing.append("NO_KERNEL_VALIDATION_RECEIPT")
    research_missing=list(missing)
    production_missing=[]
    if not any(x.get("key")=="canonical" for x in canonical):production_missing.append("CANONICAL_PATCH_REVIEW_PENDING")
    if not any(x.get("key")=="registration" for x in canonical):production_missing.append("DISPATCH_REGISTRATION_PATCH_REVIEW_PENDING")
    production_missing+=["CANONICAL_PRODUCTION_11_LANE_AND_3_GROUP_ACCEPTANCE_NOT_ESTABLISHED","MANUAL_DISPATCH_AND_SIGNED_SCALAR_GOVERNED_TARGET_RESULTS_PENDING_OR_UNADMITTED","EXTERNAL_TO_NATIVE_SEMANTIC_ADAPTER_REVIEW_REQUIRED"]
    missing+=production_missing
    outcome="STEP4_CLOSURE_CANDIDATE" if terminal else "NEW_SUPPORTING_THEOREM" if any(identity(r) in alt_ids for r in local) else "INCOMPLETE_EXECUTION" if research_missing or errors or not qs else "NO_MATCH_IN_ENUMERATED_SCOPE"
    bounded="INCOMPLETE_SEARCH_SCOPE" if not qs or graph.get("truncation") or graph.get("failures") or any(not q.get("bounded_complete") for q in qs) else "CANDIDATES_IN_ENUMERATED_SCOPE" if any(q.get("plans") for q in qs) else "NO_MATCH_IN_ENUMERATED_SCOPE"
    # All statuses stay scoped to the isolated research epoch. The release gate
    # is intentionally not callable from this hosted R2 workflow.
    write(out/"RUN_MANIFEST.json",{"schema":"OPICA_R2_RUN_MANIFEST_V1","controller":controller,"lock_sha256":filehash(HERE/"LOCK.json"),"epoch":epoch,"input_sha256":artifacts,"workflow_results":os.environ.get("R2_WORKFLOW_RESULTS","UNAVAILABLE"),**CLAIMS})
    write(out/"WORKFLOW_HARVEST.json",{"prior_campaigns":harvest,"canonical_patch_reviews":canonical,"compiler":compiler,"errors":errors,**CLAIMS})
    write(out/"QUALIFIED_THEOREM_INVENTORY.json",{"scope":"FRESH_RESEARCH_INVENTORY_ONLY","native_rows":inventory.get("native_rows",[]),"external_research_rows":inventory.get("external_research_rows",[]),"requested_native_roots":inventory.get("requested_native_roots"),"production_admission":"NOT_ESTABLISHED",**CLAIMS})
    write(out/"PROOF_OBLIGATION_GRAPH.json",{"nodes":graph["nodes"],"edges":graph["edges"],"roots":graph["roots"],"queries":[{k:v for k,v in q.items() if k!="plans"}|{"candidate_ids":[p["id"] for p in q.get("plans",[])]} for q in qs],"truncation":graph.get("truncation",[]),"authority":"RESEARCH_CONTACTS_NOT_PROOFS",**CLAIMS})
    candidate_rows=[]
    for q in qs:
        candidate_rows+=q.get("plans",[])
    seen=set();unique=[]
    for c in candidate_rows:
        if c["id"] not in seen:seen.add(c["id"]);unique.append(c)
    write(out/"CANDIDATE_COMPOSITIONS.json",{"candidates":unique,"scope":"BOUNDED_TYPED_PLANS_NOT_PROOF","validation_attempts":len([r for r in allresults if "expected_type_sha256" in r and r.get("status")!="PASS_ALTERNATE_SELECTED_CLOSURE_ONLY"]),"local_successes":len(local),**CLAIMS})
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
    write(out/"STEP4_VERDICT.json",{"schema":"OPICA_R2_STEP4_VERDICT_V1","outcome":outcome,"bounded_search_outcome":bounded,"research_missing_gates":research_missing,"production_missing_gates":production_missing,"missing_gates":missing,"input_errors":errors,"local_exact_proof_count":len(local),"alternate_kernel_count":len(alternate),"terminal_candidates":terminal,"reduced_frontier_certified":False,"scope":"ISOLATED_RESEARCH_NOT_RELEASE",**CLAIMS})
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--repo",type=Path,required=True)
    a=p.parse_args();packet(a.inputs,a.out,controller_scope(a.repo))
if __name__=="__main__":main()
