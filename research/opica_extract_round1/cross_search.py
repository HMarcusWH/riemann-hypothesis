"""Cross-world research retrieval using the ORIGINAL OPICA DAG search.

No proof constants from another compiler epoch are admitted to native execution.
Synthetic queries are explicitly assembled from actual typed binder domains and
conclusions; their hashes identify a research question, NOT a theorem contract.
"""
import argparse, array, base64, hashlib, json, pathlib, sys, zlib
from types import SimpleNamespace
from scan import PIN, need, textgit, write
NS="OPICAExtractionR1."
FORBIDDEN={"riemannHypothesis","_root_.riemannHypothesis","UpperTheory.FinalTheorems.riemannHypothesis","UpperTheory.FinalTheorems.everyCharacter","LFunction_ne_zero_of_half_lt_re","Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis","Zeta23.OPICARound4.ArithmeticFrontier.riemannHypothesis_iff_cofinal_moment_slice_bounds"}
def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def name(n):
    if n[0]=="anonymous":return ""
    p=name(n[1]);return (p+"." if p else "")+n[2]
def root(e):return int(e["root"])
def children(row):
    k=row[0]
    return [1,2] if k=="app" else [3,4] if k in ("forall","lam") else [2,3,4] if k=="let" else [2] if k=="mdata" else [3] if k=="proj" else []
class Builder:
    def __init__(self):self.nodes=[];self.cache={};self.intern={}
    def add(self,row):
        key=json.dumps(row,ensure_ascii=False,separators=(",",":"))
        if key not in self.intern:self.intern[key]=len(self.nodes);self.nodes.append(row)
        return self.intern[key]
    def clone(self,e,i):
        key=id(e),i
        if key in self.cache:return self.cache[key]
        row=list(e["nodes"][i])
        for k in children(row):row[k]=str(self.clone(e,int(row[k])))
        j=self.add(row);self.cache[key]=j;return j
    def finish(self,i):
        need(i==len(self.nodes)-1,"noncanonical query root")
        return {"format":"LEAN_EXPR_DAG_V1","nodes":self.nodes,"root":str(i)}
def subdag(e,i):
    b=Builder();return b.finish(b.clone(e,i))
def peel(e):
    i=root(e);bind=[]
    while True:
        row=e["nodes"][i]
        if row[0]=="mdata":i=int(row[2]);continue
        if row[0]!="forall":return bind,i
        bind.append((e,i));i=int(row[4])
def head(e,i=None):
    i=root(e) if i is None else i
    for _ in range(512):
        row=e["nodes"][i]
        if row[0]=="mdata":i=int(row[2])
        elif row[0]=="app":i=int(row[1])
        elif row[0]=="const":return name(row[1])
        else:return None
    return None
def conditional(domains,conclusion,idx):
    b=Builder()
    def add(k):
        if k==len(domains):return b.clone(conclusion,idx)
        e,i=domains[k];r=e["nodes"][i]
        # Binder domains must be independently closed before caller uses them.
        domain=b.clone(e,int(r[3]));body=add(k+1)
        return b.add(["forall",r[1],r[2],str(domain),str(body)])
    return b.finish(add(0))
def membership(rec):
    need(rec["encoding"]=="LE_U32_SORTED_ZLIB_BASE64_V1" and type(rec["count"]) is int and 0<=rec["count"]<=3000000,"closure membership shape")
    size=4*rec["count"];z=zlib.decompressobj()
    b=z.decompress(base64.b64decode(rec["data"],validate=True),size+1)
    need(z.eof and not z.unused_data and not z.unconsumed_tail and len(b)==size and hashlib.sha256(b).hexdigest()==rec["sha256"],"closure membership digest")
    a=array.array("I");a.frombytes(b)
    if sys.byteorder!="little":a.byteswap()
    need(len(a)==rec["count"] and all(x<y for x,y in zip(a,a[1:])),"closure membership order")
    return set(a)
def union_report(rows,baseline):
    original=[];compiler=[];native=[];unavailable=[]
    sets=[]
    for row in rows:
        w=row["world"]
        if w=="ORIGINAL_EXPORT":
            m=row.get("membership")
            if not m:unavailable.append(row["declaration"]);continue
            sets.append(membership(m));original.append(row["declaration"])
        elif w=="ORIGINAL_COMPILER_ADAPTER":compiler.append(row["declaration"])
        else:native.append(row["declaration"])
    total=set().union(*sets) if sets else set()
    return {"original_export_roots":original,"original_export_union_declarations":None if unavailable else len(total),
            "original_export_sum_declarations":sum(map(len,sets)),"original_export_overlap_saved":sum(map(len,sets))-len(total),
            "original_headline_baseline_declarations":len(baseline) if baseline is not None else None,
            "original_union_fraction_of_headline":len(total)/len(baseline) if baseline and not unavailable and original else None,
            "separate_original_compiler_adapters":compiler,"separate_native_consumers":native,"unavailable":unavailable,
            "full_closed_route_compression":"NOT_ESTABLISHED_OTHER_EPOCHS_AND_OPEN_PREMISES"}
def find(inputs,filename,part):
    rows=[p for p in inputs.rglob(filename) if part in str(p)]
    need(len(rows)<=1,"ambiguous input "+filename)
    return json.loads(rows[0].read_text()) if rows else None
def run(repo,inputs,out):
    need(textgit(repo,"rev-parse","HEAD")==PIN["native"]["head"] and textgit(repo,"rev-parse","HEAD^{tree}")==PIN["native"]["tree"],"native OPICA engine pin")
    sys.path.insert(0,str(repo))
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.composition_search import retrieve
    from research.RHRC.integration.opica_composition.contracts import SearchBudget,GrammarProfile
    from research.RHRC.integration.opica_composition.proposals import used_constant_ids
    nr=find(inputs,"native-retrieval.json","extraction-native")
    if nr is None:nr=find(inputs,"native-retrieval-base.json","extraction-native")
    er=find(inputs,"principal-receipt.json","extraction-principal")
    gr=find(inputs,"original-dependencies.json","original-proof-graph")
    adapter=find(inputs,"adapter-receipt.json","extraction-native")
    report={"schema":"OPICA_R1_CROSS_WORLD_TYPED_RETRIEVAL_V2","status":"PARTIAL","proof_acceptance":False,"external_approved_proof_constants":[],"C1":"OPEN","independent_step4":"OPEN","queries":[],"premise_frontier":[]}
    table={};rejected=[];baseline=None
    def add(n,e,w,proofs,**meta):
        try:h=expression_hash(e)
        except Exception as exc:rejected.append({"name":n,"world":w,"reason":"DAG_VALIDATION:"+str(exc)[:300]});return
        if n in FORBIDDEN or n in table:
            rejected.append({"name":n,"world":w,"reason":"FORBIDDEN_OR_DUPLICATE"});return
        table[n]={"declaration":n,"module":w,"world":w,"type_expression":e,"type_sha256":h,"proof_constants":proofs,**meta}
    if gr and gr.get("raw_sha256")==PIN["original"]["solution"]["raw_sha256"] and gr.get("raw_bytes")==PIN["original"]["solution"]["raw_bytes"]:
        for x in gr["roots"]:
            cl=x.get("closure",{})
            if x["name"]=="riemannHypothesis" and cl.get("membership"):baseline=membership(cl["membership"])
            if x.get("kind")!="thm" or not x["role"].startswith(("CONDITIONAL_","PRODUCER_","DISCOVERED_")):continue
            if cl.get("status")!="COMPLETE" or not cl.get("membership") or x.get("excluded_dependencies") or not set(cl.get("axioms",[]))<=set(PIN["allowed_axioms"]) or x.get("type_status")!="ORIGINAL_EXPORT_EXPR_CONVERTED":
                rejected.append({"name":x["name"],"world":"ORIGINAL_EXPORT","reason":"INCOMPLETE_OR_EXCLUDED_OR_AXIOM"});continue
            add(x["name"],x["type_expression"],"ORIGINAL_EXPORT",[],membership=cl["membership"])
    if nr and nr.get("native")==PIN["native"] and nr.get("proof_acceptance") is False:
        for x in nr["actual_source_theorems"]:
            need(set(x["axioms"])<=set(PIN["allowed_axioms"]),"native unapproved axiom")
            need(expression_hash(x["type_expression"])==x["type_sha256"],"native actual type hash")
            add(x["declaration"],x["type_expression"],"NATIVE_COMPILER",x.get("proof_constants",[]),closure_count=x["closure_count"])
    if er and er.get("head")==PIN["original"]["head"] and er.get("status")=="PASS_CONDITIONAL_PRINCIPAL_CUT_ONLY" and adapter and er["shared_source_sha256"]==adapter.get("shared_source_sha256"):
        for x in er["rows"]:
            need(set(x["axioms"])<=set(PIN["allowed_axioms"]),"principal adapter axiom")
            add(x["name"],x["type_expression"],"ORIGINAL_COMPILER_ADAPTER",x["proof_constants"],closure_count=len(x["dependency_names"]))
    report["sources"]={"original_export_authenticated":bool(gr and gr.get("raw_sha256")==PIN["original"]["solution"]["raw_sha256"]),"principal_adapter_available":NS+"principal_ramp_windows_of_topG_vwin" in table,"native_receiving_types_available":bool(nr),"native_common_source_match":bool(er and adapter and er.get("shared_source_sha256")==adapter.get("shared_source_sha256"))}
    report["research_menu"]=[{"name":n,"world":x["world"],"type_sha256":x["type_sha256"]} for n,x in sorted(table.items())]
    report["rejected_menu_rows"]=rejected
    report["status"]="RESEARCH_QUERIES_EXECUTED_NOT_PROOF"
    def query(label,e,menu):
        try:target_hash=expression_hash(e)
        except Exception as exc:return {"label":label,"status":"DEPENDENT_OR_UNSUPPORTED_QUERY","reason":str(exc)[:300],"proof_acceptance":False}
        ids={sha([x["world"],x["declaration"],x["type_sha256"]]):x["declaration"] for x in menu}
        byname={x["declaration"]:x for x in menu}
        spec=SimpleNamespace(allowed_constants=ids,expected_type_hash=target_hash,declaration="RESEARCH_QUERY."+label,forbidden_constants=sorted(FORBIDDEN))
        rows,complete,provenance=retrieve(SimpleNamespace(statements=menu),spec,GrammarProfile(sorted(FORBIDDEN),[]),SearchBudget(candidates=8,term_nodes=2048,term_depth=16,wall_seconds=45,heartbeats=800000),e)
        plans=[]
        for x in rows:
            used=used_constant_ids(x["term_plan"]);need(set(used)<=set(ids),"research plan names not in menu")
            names=sorted(ids[i] for i in used)
            plans.append({"term_plan":x["term_plan"],"used":names,"worlds":sorted({byname[n]["world"] for n in names}),"union":union_report([byname[n] for n in names],baseline),"kernel_acceptance":False,"required":"SAME_PIN_PORT_AND_INDEPENDENT_REPLAY"})
        return {"label":label,"status":provenance["stopping_reason"],"query_type_sha256":target_hash,"query_expression":e,"plans":plans,"bounded_complete":complete,"proof_acceptance":False}
    menu=list(table.values())
    principal=table.get(NS+"principal_ramp_windows_of_topG_vwin")
    if principal:
        pe=principal["type_expression"];pb,pt=peel(pe)
        need(len(pb)==2 and head(pe,pt)==NS+"RampWindows","principal typed interface changed")
        # Verify each binder domain really is a closed type, without inventing
        # a claim about whether a general upstream binder is a proof or datum.
        premises=[]
        for e,i in pb:
            domain=subdag(e,int(e["nodes"][i][3]));expression_hash(domain);premises.append(domain)
        report["queries"].append(query("principal_windows_closed",subdag(pe,pt),menu))
        for i,domain in enumerate(premises):
            report["queries"].append(query("principal_premise_"+str(i),domain,menu))
        for target in (NS+"native_windows_of_ramp_windows",NS+"native_energy_of_ramp_windows",NS+"native_c1_of_ramp_windows_of_direct_bridge"):
            row=table.get(target)
            if row is None:continue
            e=row["type_expression"];bs,end=peel(e)
            need(len(bs) in (1,2),"receiving adapter binder count")
            need(head(e,int(e["nodes"][bs[-1][1]][3]))==NS+"RampWindows","receiving adapter changed window premise")
            # Include the exact OPEN detector bridge as a local premise for C1,
            # never pretend that the energy bound already proves it.
            extra=bs[:-1]
            for q,i in extra:expression_hash(subdag(q,int(q["nodes"][i][3])))
            conditional_goal=conditional(pb+extra,e,end)
            report["queries"].append(query("conditional_"+target.split(".")[-1],conditional_goal,menu))
            report["queries"].append(query("closed_"+target.split(".")[-1],subdag(e,end),menu))
        # Backward research frontier: actual terminal-head matches trigger
        # recursive typed searches of independently closed binder domains.
        # Dependent binders remain explicit, not silently discharged.
        visited=set();queue=[(p,0,"principal") for p in premises]
        while queue and len(visited)<12:
            goal,depth,parent=queue.pop(0);gh=expression_hash(goal)
            if gh in visited:continue
            visited.add(gh);q=query("frontier_"+str(len(visited)),goal,menu);q["parent"]=parent;q["depth"]=depth
            alternatives=[]
            if not q.get("plans") and depth<2:
                goalhead=head(goal)
                for row in menu:
                    e=row["type_expression"];bs,last=peel(e)
                    if goalhead is None or head(e,last)!=goalhead:continue
                    bindings=[]
                    for qdag,i in bs:
                        b=subdag(qdag,int(qdag["nodes"][i][3]))
                        try:
                            h=expression_hash(b);bindings.append({"type_sha256":h,"status":"OPEN_CLOSED_BINDER_DOMAIN","head":head(b)})
                            if len(queue)<48:queue.append((b,depth+1,row["declaration"]))
                        except Exception:bindings.append({"status":"DEPENDENT_BINDER_REQUIRES_INSTANTIATION"})
                    alternatives.append({"name":row["declaration"],"role":"HEAD_MATCH_NOT_UNIFIER","bindings":bindings})
                    if len(alternatives)>=8:break
            q["head_matched_alternatives"]=alternatives
            report["premise_frontier"].append(q)
        report["frontier_unvisited_count"]=len(queue)
    else:
        report["status"]="PARTIAL_NO_COMPILER_QUALIFIED_PRINCIPAL_INTERFACE"
    report["next_math"]=["Discharge exact principal TopG and VWinAt from upstream producers or simplify their hypotheses.","Port selected upstream proof source, not .olean files, and verify shared mathematical definitions.","Prove DirectEnergyToC1 or another actual native signed-source transfer; no RH-equivalent endpoint shortcut."]
    write(out,report)
    print(json.dumps({"status":report["status"],"menu":len(table),"queries":len(report["queries"]),"plans":sum(len(q.get("plans",[])) for q in report["queries"]),"frontier":len(report["premise_frontier"]),"proof_acceptance":False}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--inputs",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();run(a.repo.resolve(),a.inputs,a.output)
