"""Compiler-independent typed research on the authenticated original graph.
No native build or new proof acceptance. Dynamic target types must subsequently
be reconstructed and checked by the pinned common-pin compiler.
"""
import argparse
from pathlib import Path
from r2_common import *
from external_inventory import load_external,principal_goals,external_frontier,complete_original_leads
import search

def run(native,harvest,out):
    native=native.resolve();harvest=harvest.resolve();out=out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    doc={"schema":"OPICA_R2_ORIGINAL_FOCUS_V1","status":"INCOMPLETE_EXECUTION",
         "controller":controller_scope(HERE.parent.parent),"native":LOCK["native"],
         "source_scope":"ORIGINAL_AUTHENTICATED_GRAPH_AND_COMPILER_INTERFACES_ONLY",**CLAIMS}
    try:
        check_pin(native,LOCK["native"])
        sys.path.insert(0,str(native))
        sys.path.insert(0,str(R1))
        evidence=read(harvest/"harvest.json")
        rows,rejected=load_external(harvest)
        roots=principal_goals(rows)
        doc["input_receipts"]={k:v for k,v in evidence["artifact_receipts"].items() if k in ("original","principal")}
        doc["row_count"]=len(rows);doc["rejected"]=rejected
        doc["root_labels"]=[g["label"] for g in roots]
        if not rows or not roots:
            doc["status"]="WAITING_FOR_AUTHENTICATED_ORIGINAL_INTERFACES"
            return
        # Explicit isolated budget, not a change to the governed native menu.
        search.BUDGET={**BUDGET,**LOCK["original_focus_budget"]}
        graph=search.explore(roots,rows,external_frontier)
        selected,omitted=search.select(graph,"mixed",search.BUDGET["attempts_mixed"])
        # The original memberships stay in the separately authenticated
        # harvest; graph/candidates contain only the typed research objects.
        write(out/"original-focus-graph.json",graph)
        write(out/"original-focus-candidates.json",{"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"mixed","native":LOCK["native"],
          "original_head":R1_PIN["original"]["head"],"selected":selected,"omitted_budget":omitted,**CLAIMS})
        doc.update(status="ORIGINAL_FOCUS_RESEARCH_EXECUTED_NOT_PROOF",budget=search.BUDGET,
            goals=len(graph["nodes"]),queries=len(graph["queries"]),plans=sum(len(q["plans"]) for q in graph["queries"]),
            selected=len(selected),omitted_budget=omitted,query_failures=graph["failures"],truncation=graph["truncation"],
            unregistered_premises=sum(len(e["unregistered_premises"]) for e in graph["edges"]),
            graph_sha256=filehash(out/"original-focus-graph.json"),
            candidates_sha256=filehash(out/"original-focus-candidates.json"),
            expanded_inputs_available=not evidence["expanded_search_readiness"]["missing"])
    except BaseException as ex:
        doc["error"]=str(ex)[:1500];raise
    finally:
        write(out/"original-focus-receipt.json",doc)
        print(json.dumps({k:doc[k] for k in ("status","proof_acceptance")}))
def main():
    p=argparse.ArgumentParser()
    for k in ("native","harvest","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.native,a.harvest,a.out)
if __name__=="__main__":main()
