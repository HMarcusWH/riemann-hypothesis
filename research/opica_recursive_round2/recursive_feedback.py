"""Bounded recursive reuse of actual kernel-validated contextual proofs.

Rebuild named theorems from the fixed native proof grammar. No binder shifting,
untrusted Lean syntax, imported evidence object, virtual axiom or cross-pin
semantic assertion. Every newly composed candidate goes through the existing
compiler, independent expected type and fresh stock replay.
"""
import argparse, os, re, shutil, sys, time
from pathlib import Path
from r2_common import *
from search import api, query, row_id

ROUNDS=3
ATTEMPTS=8
PER_ROUND=3
QUERY_CAP=20
TERMINALS={"OPICAR2.C1Named","Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"}
SUCCESS="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"

def candidate_binding(c,r,goal,native,receipt):
    need(receipt.get("schema")=="OPICA_R2_VALIDATION_V1" and receipt.get("mode")=="native" and receipt.get("proof_acceptance") is False and receipt["native"]==native,"Wrong feedback receipt epoch or scope")
    need(r.get("id")==c["id"] and r.get("goal_id")==c["goal_id"]==goal["id"] and r.get("target")==c["target"] and goal["declaration"]==c["target"]["declaration"],"Feedback target differs")
    need(r.get("status")==SUCCESS and r.get("actual_local_kernel_proof") is True and r.get("expected_type_sha256")==c["expected_type_sha256"]==r.get("actual_type_sha256")==goal["type_sha256"] and r.get("candidate_plan_sha256")==digest(c["plan"]),"Feedback proof binding differs")
    need(r.get("cross_pin_definition_equivalence")=="SAME_NATIVE_PIN" and set(r["axioms"])<=ALLOWED and all(r["stages"][k]["status"]=="PASS" for k in ("actual_types","kernel","independent_type","fresh_stock_kernel")),"Incomplete feedback proof gates")
    need(c["target"].get("world","NATIVE_QUERY")=="NATIVE_QUERY" and goal.get("world","NATIVE_QUERY")=="NATIVE_QUERY","Not a same-pin native goal")

def feedback_name(cid):
    need(re.fullmatch(r"[0-9a-f]{64}",cid) is not None,"Invalid candidate identity")
    return "OPICAR2Feedback"+cid[:32]

def source_bytes(c, name):
    # Generate the same closed protocol as R1, with a reviewed named-declaration
    # evaluator. The only new syntax is a fixed command and validated name.
    from research.RHRC.integration.opica_composition.executor import generate_source
    from research.RHRC.integration.opica_composition.contracts import TargetSpec,CompositionProposal,PER_ATTEMPT_GATES
    from candidate_validate import FORBIDDEN
    target=c["target"]
    rows=c["sources"]
    table=[{"id":r["id"],"declaration":source_name(r["declaration"]),"module":source_name(r.get("source_module") or r["module"]),"role":"constant"} for r in rows]
    need(len({r["id"] for r in table})==len(table) and all(not forbidden(r["declaration"]) for r in table),"Unapproved feedback source")
    imports=sorted({target["module"],*[r["module"] for r in table]})
    spec=TargetSpec("R2F_"+c["id"][:16],target["declaration"],target["module"],c["expected_type_sha256"],{r["id"]:r["declaration"] for r in table},sorted(ALLOWED),imports,list(PER_ATTEMPT_GATES),"value",FORBIDDEN)
    proposal=CompositionProposal(c["id"],spec.target_id,"0"*64,c["plan"])
    source=generate_source(proposal,spec,table)
    anchor="run_cmd Zeta23.RHRC.OpicaComposition.runAttempt "
    need(source.count(anchor)==1,"Fixed evaluator source anchor differs")
    return "import OPICAR2Export\n"+source.replace(anchor,"run_cmd OPICAR2Export.registerFeedback "+chr(96)+source_name(name+".result")+" ",1)

def check_files(folder,r):
    for leaf,h in r["files"].items():
        need(Path(leaf).name==leaf and re.fullmatch(r"[0-9a-f]{64}",h) is not None,"Invalid proof file receipt")
        p=folder/leaf
        need(p.is_file() and not p.is_symlink() and filehash(p)==h,"Prior proof file drift: "+leaf)

class Feedback:
    def __init__(self,repo,work,inventory,graph,root):
        self.repo=repo.resolve();self.work=work.resolve();self.inventory=inventory
        self.native=inventory["epoch"]["native"];check_pin(self.repo,self.native)
        self.graph=graph;self.goals={g["id"]:g for g in graph["nodes"]}
        need(len(self.goals)==len(graph["nodes"]),"Duplicate graph goal")
        self.root=root.resolve();self.root.mkdir(parents=True,exist_ok=False)
        self.env=compiler_env()
        self.lean=subprocess.check_output(["lake","env","which","lean"],cwd=self.repo,env=self.env,text=True).strip()
        lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=self.repo,env=self.env,text=True).strip()
        self.env["LEAN_PATH"]=str(self.work)+os.pathsep+lp
        self.checker=Path(subprocess.check_output([self.lean,"--print-prefix"],cwd=self.repo,env=self.env,text=True).strip())/"bin"/"leanchecker"
        need(self.checker.is_file(),"Missing fresh stock replay checker")
        self.hash=api()[0];self.rows=[];self.receipts=[];self.held=[];self.errors=[];self.proved=set();self.seen=set()
        self.records=[];self.start=time.monotonic()

    def compile(self,source,stem,seconds=600):
        p=self.work/(stem+".lean")
        need(not p.exists(),"Feedback source name collision")
        p.write_text(source,encoding="utf-8")
        log=self.work/(stem+".log")
        r=command([self.lean,"--root="+str(self.work),"-DwarningAsError=true","-o",p.with_suffix(".olean"),p],self.repo,self.env,log,seconds)
        return r,p,log

    def controls(self):
        # A genuinely dependent target: the second local has type p, which
        # depends on the first. Prove and apply the exact named abstraction.
        plan=json.dumps(json.dumps({"tag":"local","binder_slot":1},separators=(",",":")))
        bad=json.dumps(json.dumps({"tag":"local","binder_slot":2},separators=(",",":")))
        def src(stem,term):
            return "import OPICAR2Export\nnamespace "+stem+"\ndef target : Prop := ∀ p : Prop, p → p\nend "+stem+"\nrun_cmd OPICAR2Export.registerFeedback "+chr(96)+stem+".result "+chr(96)+stem+'.target "value" '+term+' "[]" "[]" "[]"\n'
        good="OPICAR2FeedbackControl"
        r,p,l=self.compile(src(good,plan)+"example (p : Prop) (h : p) : p := "+good+".result p h\n",good)
        need(r["status"]=="PASS","Context-preserving compiler control failed")
        rows=marker_rows(l,"OPICA_R2_FEEDBACK")
        need(len(rows)==1 and rows[0]["declaration"]==good+".result" and len(rows[0]["context"])==2 and not rows[0]["axioms"],"Context-preserving control audit differs")
        s,pb,lb=self.compile(src("OPICAR2FeedbackBad",bad),"OPICAR2FeedbackBad")
        need(s["status"]=="REJECTED" and "unauthorized local slot" in lb.read_text(errors="replace"),"Unbound local negative control failed")
        write(self.root/"compiler-controls.json",{"status":"PASS_DEPENDENT_CONTEXT_AND_UNBOUND_LOCAL_CONTROLS","positive":r,"negative":s,**CLAIMS})

    def register(self,c,r,folder):
        from research.RHRC.integration.opica_composition.executor import parse_native
        check_files(folder,r)
        stem=feedback_name(c["id"]);name=stem+".result"
        src=source_bytes(c,stem)
        result,p,log=self.compile(src,stem)
        need(result["status"]=="PASS","Named proof reconstruction failed")
        a=parse_native(log,"OPICA_R2_FEEDBACK")
        need(a["declaration"]==name and self.hash(a["type_expression"])==c["expected_type_sha256"],"Reconstructed exact theorem type differs")
        need(set(a["axioms"])<=ALLOWED and not any(forbidden(n) for n in a["constants"]),"Reconstructed endpoint or axiom dependency")
        replay=command([self.checker,"--fresh","--verbose",stem],self.repo,self.env,self.work/(stem+"-stock.log"),900)
        need(replay["status"]=="PASS","Named feedback stock replay failed")
        q,p2,l2=self.compile("import "+stem+"\nimport OPICAR2Export\nrun_cmd OPICAR2Export.emitRow "+chr(96)+name+"\n",stem+"Inventory")
        need(q["status"]=="PASS","Named feedback compiler inventory failed")
        atlas=marker_rows(l2,"OPICA3_ATLAS");closure=marker_rows(l2,"OPICA_R2_CLOSURE");proofs=marker_rows(l2,"OPICA_RETRIEVAL_PROOFS")
        need(len(atlas)==len(closure)==len(proofs)==1,"Named compiler inventory markers differ")
        row=atlas[0];cl=closure[0]
        need(row["declaration"]==cl["name"]==name and row["module"]==stem and cl["is_prop"] and self.hash(row["type_expression"])==c["expected_type_sha256"],"Feedback compiler origin or type differs")
        need(set(row["axioms"])<=ALLOWED and not any(forbidden(n) for n in cl["dependencies"]+row["type_constants"]),"Feedback compiler closure contaminated")
        row=compact_dependency_row({**row,"world":"NATIVE_COMPILER","source_module":stem,"type_sha256":c["expected_type_sha256"],"proof_constants":proofs[0],"dependencies":cl["dependencies"],"cohort":"VERIFIED_RECONSTRUCTED_FEEDBACK","admission":"FRESH_NATIVE_COMPILER_RESEARCH_NOT_PRODUCTION"},self.root)
        verify_dependency_row(row,self.root)
        self.rows.append(row)
        self.receipts.append({"candidate":c["id"],"goal_id":c["goal_id"],"theorem":name,"type_sha256":c["expected_type_sha256"],"source_sha256":filehash(p),"prior_proof_receipt_sha256":filehash(folder/"receipt.json"),"reconstruction":result,"stock":replay,"inventory":q,"context_binders":len(a["context"]),"claim_scope":"EXACT_ABSTRACTED_TELESCOPE_ONLY","row":row,**CLAIMS})

    def ingest(self,manifest,review,folder):
        need(manifest.get("schema")=="OPICA_R2_CANDIDATE_MANIFEST_V1" and manifest.get("mode")=="native" and manifest.get("proof_acceptance") is False and manifest["native"]==self.native,"Feedback manifest scope")
        candidates={c["id"]:c for c in manifest["selected"]}
        results={r["id"]:r for r in review["results"]}
        need(len(candidates)==len(manifest["selected"]) and len(results)==len(review["results"]) and set(candidates)==set(results),"Feedback result/manifest population differs")
        self.seen.update(candidates)
        count=0
        for cid,c in candidates.items():
            r=results[cid]
            if r["status"]!=SUCCESS:continue
            g=self.goals[c["goal_id"]]
            candidate_binding(c,r,g,self.native,review)
            if c["goal_id"] in self.proved:continue
            if g["declaration"] in TERMINALS or forbidden(g["declaration"]):
                self.held.append({"candidate":cid,"reason":"TERMINAL_OR_ENDPOINT_NOT_A_FEEDBACK_SUPPLIER"})
                self.proved.add(c["goal_id"]);continue
            try:
                self.register(c,r,folder/cid)
                self.proved.add(c["goal_id"]);count+=1
            except Exception as exc:
                self.errors.append({"candidate":cid,"reason":str(exc)[:1800],"status":"NAMED_RECONSTRUCTION_INCOMPLETE"})
        return count

    def propose(self,limit):
        selected=[];queries=[]
        roots=set(self.graph["roots"]);facts={row_id(r) for r in self.rows}
        # Deepest contextual obligations first, then root retry. The exact
        # proof grammar still checks application to the complete telescope.
        goals=sorted((g for g in self.graph["nodes"] if g["id"] not in self.proved and g.get("world","NATIVE_QUERY")=="NATIVE_QUERY"),key=lambda g:(g["id"] in roots,-g.get("depth",0),g["declaration"]))
        for g in goals[:QUERY_CAP]:
            if time.monotonic()-self.start>4500:break
            try:
                q=query(g,self.inventory["native_rows"]+self.rows,"native")
                queries.append({k:v for k,v in q.items() if k!="plans"})
                for c in q["plans"]:
                    if c["id"] in self.seen or not any(r["id"] in facts for r in c["sources"]):continue
                    self.seen.add(c["id"]);selected.append(c)
                    if len(selected)>=limit:return selected,queries
            except Exception as exc:
                self.errors.append({"goal":g["id"],"reason":str(exc)[:1000],"status":"FEEDBACK_QUERY_INCOMPLETE"})
        return selected,queries

    def run(self,manifest,review,validation,out_manifest,out_validation):
        from verify_candidates import validate
        all_candidates=[];all_results=[]
        out_validation.mkdir(parents=True,exist_ok=False)
        status="NO_NEW_VERIFIED_FEEDBACK"
        try:
            self.controls()
            newly=self.ingest(manifest,review,validation)
            for i in range(1,ROUNDS+1):
                if newly==0 or len(all_candidates)>=ATTEMPTS:break
                if time.monotonic()-self.start>4500:
                    status="FEEDBACK_RESOURCE_LIMIT";break
                selected,qs=self.propose(min(PER_ROUND,ATTEMPTS-len(all_candidates)))
                rounddir=self.root/("round-"+str(i).zfill(2));rounddir.mkdir()
                m={"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"native","native":self.native,"original_head":manifest["original_head"],"selected":selected,"omitted_budget":0,**CLAIMS}
                write(rounddir/"manifest.json",m)
                record={"round":i,"new_suppliers":newly,"queries":qs,"selected":[c["id"] for c in selected]}
                self.records.append(record)
                if not selected:
                    status="NO_FRESH_CANDIDATES_IN_BOUNDED_FEEDBACK";break
                rr=validate(self.repo,self.repo,self.work,m,rounddir/"validation","native")
                all_candidates.extend(selected);all_results.extend(rr["results"])
                # Reconstruct before moving directories for the unified
                # independent replay. Each later iteration uses the actual
                # named kernel theorem, never a dangling virtual source.
                newly=self.ingest(m,rr,rounddir/"validation")
                for c in selected:
                    shutil.move(str(rounddir/"validation"/c["id"]),str(out_validation/c["id"]))
                status="FEEDBACK_BOUNDED_ROUNDS_EXECUTED"
                if i==ROUNDS and newly:status="FEEDBACK_ROUND_CAP_REACHED"
            if self.errors:status="FEEDBACK_INCOMPLETE"
        except Exception as exc:
            self.errors.append({"reason":str(exc)[:1800],"status":"FEEDBACK_EXECUTION_INCOMPLETE"})
            status="FEEDBACK_INCOMPLETE"
        finally:
            write(out_manifest,{"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"native","native":self.native,"original_head":manifest["original_head"],"selected":all_candidates,"omitted_budget":0,**CLAIMS})
            write(out_validation/"review.json",{"schema":"OPICA_R2_VALIDATION_V1","mode":"native","native":self.native,"results":all_results,**CLAIMS})
            write(self.root/"index.json",{"schema":"OPICA_R2_RECURSIVE_FEEDBACK_V1","native":self.native,"status":status,"round_cap":ROUNDS,"attempt_cap":ATTEMPTS,"query_cap":QUERY_CAP,"rounds":self.records,"registered":self.receipts,"held":self.held,"errors":self.errors,"selected_count":len(all_candidates),"result_count":len(all_results),"proof_acceptance":False,"RH":"OPEN","C1":"OPEN","Step4":"OPEN"})
        if status=="FEEDBACK_INCOMPLETE":raise RuntimeError("Incomplete recursive feedback; retained index")

def main():
    p=argparse.ArgumentParser()
    for k in ("repo","work","inventory","graph","manifest","validation","out","out-manifest","out-validation"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.repo.resolve()))
    sys.path.insert(0,str(R1))
    inv=read(a.inventory);verify_inventory(inv,a.inventory.parent)
    f=Feedback(a.repo,a.work,inv,read(a.graph),a.out)
    f.run(read(a.manifest),read(a.validation/"review.json"),a.validation,a.out_manifest,a.out_validation)

if __name__=="__main__":main()
