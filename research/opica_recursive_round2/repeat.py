"""One bounded feedback pass: inline verified closed frontier proof plans.
A virtual fact is never passed to Lean as a declaration or axiom. Only
binder-free closed plans are reused; all other dependent plans remain explicit
research frontiers for a later compiler-backed context-preserving composition.
"""
import argparse
from pathlib import Path
from r2_common import *
from search import api,query,row_id

def closed_plan(p):
    if isinstance(p,dict):
        if p.get("tag") in ("local","lambda","let","cases"):return False
        return all(closed_plan(v) for v in p.values())
    if isinstance(p,list):return all(closed_plan(x) for x in p)
    return True
def substitute(p,virtual,used):
    if isinstance(p,dict):
        if p.get("tag")=="const" and p.get("constant_id") in virtual:
            k=p["constant_id"];used.add(k);return virtual[k]["plan"]
        return {k:substitute(v,virtual,used) for k,v in p.items()}
    if isinstance(p,list):return [substitute(x,virtual,used) for x in p]
    return p
def feedback(inventory,graph,manifest,review,out):
    from verify_candidates import SUCCESS
    rows=inventory["native_rows"];actual={c["id"]:c for c in manifest["selected"]}
    need(len(actual)==len(manifest["selected"]) and len({r["id"] for r in review["results"]})==len(review["results"]) and set(actual)=={r["id"] for r in review["results"]},"Feedback receipt/manifest bijection")
    need(review["native"]==manifest["native"],"Feedback source epoch differs")
    virtual={};extra=[];held=[]
    for r in review["results"]:
        if r["status"]!=SUCCESS:continue
        c=actual[r["id"]]
        need(r["actual_local_kernel_proof"] and r["candidate_plan_sha256"]==digest(c["plan"]),"Feedback proof receipt mismatch")
        if not c["target"]["module"].startswith("OPICAR2Frontier") or not closed_plan(c["plan"]):
            held.append({"candidate":c["id"],"reason":"NOT_A_BINDER_FREE_FRONTIER_PLAN"});continue
        x={"declaration":"OPICAR2Virtual."+c["id"][:24],"module":"OPICAR2Virtual","world":"NATIVE_COMPILER","type_expression":c["expected_expression"],"type_sha256":c["expected_type_sha256"],"proof_constants":[],"dependencies":[]}
        virtual[row_id(x)]=c;extra.append(x)
    selected=[];queries=[]
    if extra:
        for g in graph["nodes"]:
            if g["id"] not in graph["roots"] or g.get("world")=="ORIGINAL_QUERY":continue
            q=query(g,rows+extra,"native")
            queries.append({"goal":g["id"],"status":q["status"],"plans":len(q["plans"])})
            for c in q["plans"]:
                used=set();plan=substitute(c["plan"],virtual,used)
                if not used:continue
                sources={s["id"]:s for s in c["sources"] if s["id"] not in virtual}
                for k in used:
                    for s in virtual[k]["sources"]:
                        need(s["id"] not in sources or sources[s["id"]]==s,"Conflicting inlined source")
                        sources[s["id"]]=s
                eh,_,_,_,used_ids,check=api()
                check(plan);need(set(used_ids(plan))==set(sources),"Unresolved virtual constant or source")
                candidate={**c,"id":digest([c["target"],c["expected_type_sha256"],plan]),"plan":plan,"sources":list(sources.values()),"inlined_frontier_receipts":[virtual[k]["id"] for k in sorted(used)]}
                selected.append(candidate)
                if len(selected)>=BUDGET["attempts_native"]:break
            if len(selected)>=BUDGET["attempts_native"]:break
    write(out,{"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"native","native":manifest["native"],"original_head":manifest["original_head"],"selected":selected,"omitted_budget":0,"feedback":{"eligible_verified_frontier_plans":len(virtual),"held":held,"queries":queries},**CLAIMS})
def main():
    p=argparse.ArgumentParser()
    for k in ("repo","inventory","graph","manifest","review","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();import sys;sys.path.insert(0,str(a.repo.resolve()))
    feedback(read(a.inventory),read(a.graph),read(a.manifest),read(a.review),a.out)
if __name__=="__main__":main()
