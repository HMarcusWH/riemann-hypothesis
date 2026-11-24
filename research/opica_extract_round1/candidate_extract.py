"""Select real typed retrieval plans; source locations are never authority."""
import argparse,hashlib,json,pathlib,sys
from scan import PIN,need,textgit,write
NS="OPICAExtractionR1."
def digest(x):
    return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def extract(repo,report,mode,limit=6):
    need(textgit(repo,"rev-parse","HEAD")==PIN["native"]["head"],"native engine pin")
    sys.path.insert(0,str(repo))
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.proposals import validate_plan,used_constant_ids
    need(report.get("proof_acceptance") is False,"unexpected research authority")
    if mode=="native":
        need(report["native"]==PIN["native"],"native report epoch")
        contracts={x["declaration"]:{**x,"world":"NATIVE_COMPILER","source_module":x["module"]} for x in report["actual_source_theorems"]}
        queries=[{"label":x["target"],"registered_target":{"declaration":x["target"],"module":x["module"],"kind":"value"},"query_expression":x["compiler_expression"],"query_type_sha256":x["type_sha256"],"plans":x["plans"]} for x in report["targets"]]
    else:
        contracts={x["declaration"]:x for x in report.get("research_contracts",[])}
        queries=report.get("queries",[])
    candidates=[];rejected=[];seen=set()
    for q in queries:
        target=q.get("registered_target")
        if not target or not target.get("module") or not q.get("query_expression"):continue
        e=q["query_expression"];eh=expression_hash(e)
        need(eh==q["query_type_sha256"],"query type drift")
        # Fair cap: first actual nontrivial candidate for each target, then
        # continue with alternatives up to the overall budget.
        eligible=[]
        for p in q.get("plans",[]):
            plan=p["term_plan"]
            validate_plan(plan)
            ids=p.get("constant_ids",{})
            need(set(ids)==set(used_constant_ids(plan)) and set(ids.values())==set(p["used"]),"candidate constant identity")
            need(all(n in contracts for n in ids.values()),"candidate source contract missing")
            if p.get("kind")=="BARE_SEED":continue
            used=[{**contracts[name],"id":cid} for cid,name in sorted(ids.items())]
            if any(expression_hash(x["type_expression"])!=x["type_sha256"] for x in used):raise RuntimeError("source type digest")
            worlds={x["world"] for x in used}
            if mode=="mixed" and (not worlds-{"NATIVE_COMPILER"} and target["module"]!="OPICAExtractionCombinedTargets"):continue
            if mode=="native" and worlds-{"NATIVE_COMPILER"}:continue
            key=digest([target,eh,plan,ids])
            if key in seen:continue
            seen.add(key)
            eligible.append({"id":key,"label":q["label"],"target":target,"expected_expression":e,"expected_type_sha256":eh,"plan":plan,"sources":used,"worlds":sorted(worlds),"proof_acceptance":False})
        if eligible:candidates.append(eligible)
    ordered=[]
    while candidates and len(ordered)<limit:
        remaining=[]
        for row in candidates:
            if len(ordered)<limit:ordered.append(row.pop(0))
            if row:remaining.append(row)
        candidates=remaining
    return {"schema":"OPICA_R1_CANDIDATE_MANIFEST_V1","mode":mode,"input_sha256":digest(report),"native":PIN["native"],"original_head":PIN["original"]["head"],"selected":ordered,"omitted_budget":sum(map(len,candidates)),"proof_acceptance":False,"C1":"OPEN"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--report",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True);p.add_argument("--mode",choices=("native","mixed"),required=True);p.add_argument("--limit",type=int,default=6)
    a=p.parse_args();need(1<=a.limit<=16,"candidate cap")
    manifest=extract(a.repo.resolve(),json.loads(a.report.read_text()),a.mode,a.limit);write(a.output,manifest)
    print(json.dumps({"status":"CANDIDATES_SELECTED_NOT_PROVED","mode":a.mode,"selected":len(manifest["selected"]),"omitted_budget":manifest["omitted_budget"],"proof_acceptance":False}))
if __name__=="__main__":main()
