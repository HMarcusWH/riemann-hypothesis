"""Actual fixed OPICA evaluator, independent expected-type consumer, fresh stock replay.

Runs on reviewed hosted source checkouts, not a production acceptance worker.
No caller-supplied Lean syntax, no cross-version .olean use, no RH promotion.
"""
import argparse,hashlib,json,os,pathlib,re,signal,subprocess,sys,time
from scan import PIN,need,textgit,write
from candidate_port import filehash
FORBIDDEN=["riemannHypothesis","_root_.riemannHypothesis","UpperTheory.FinalTheorems.riemannHypothesis","UpperTheory.FinalTheorems.everyCharacter","LFunction_ne_zero_of_half_lt_re","riemannZeta_eq_zero_re","LFunction_eq_zero_re","LFunction_eq_zero_re_of_isPrimitive","UpperTheory.Top.zeroFreeAll_of_topG","UpperTheory.Top.zero_free_all_of_green_v_win","Deduction.zeroFree_of_rpow_window","UpperTheory.Comparison₂.formB","Formalism.HC.level_of_tiedWin","Formalism.HC.zeroFreeOn_of_tiedWin_cyc","Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis","Zeta23.OPICARound4.ArithmeticFrontier.riemannHypothesis_iff_cofinal_moment_slice_bounds"]
SUFFIXES={x.split(".")[-1] for x in FORBIDDEN}|{"rhOfAll","allChi","claimAll","critAll","everyCharacter_of_row","every_character_of_literature_of_vWin"}
def fingerprint(e):
    # Alpha/binder-name and metadata normalization ONLY. No name alias,
    # definition unfolding or proof erasure is claimed to be kernel equality.
    rows=[]
    for row in e["nodes"]:
        row=list(row);k=row[0]
        if k=="mdata":rows.append(rows[int(row[2])]);continue
        if k in ("forall","lam"):
            row[1]=["anonymous"];indices=(3,4)
        elif k=="let":row[1]=["anonymous"];indices=(2,3,4)
        elif k=="app":indices=(1,2)
        elif k=="proj":indices=(3,)
        else:indices=()
        for i in indices:row[i]=rows[int(row[i])]
        rows.append(hashlib.sha256(json.dumps(row,ensure_ascii=False,separators=(",",":")).encode()).hexdigest())
    return rows[int(e["root"])]
def command(argv,cwd,env,log,timeout):
    start=time.monotonic()
    with log.open("xb") as f:
        proc=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            rc=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait();return {"status":"RESOURCE_EXHAUSTED","seconds":time.monotonic()-start,"log_sha256":filehash(log)}
    return {"status":"PASS" if rc==0 else "REJECTED","exit":rc,"seconds":time.monotonic()-start,"log_sha256":filehash(log)}
def execute(repo,engine,work,manifest,out,mode,limit):
    need(textgit(engine,"rev-parse","HEAD")==PIN["native"]["head"],"engine source pin")
    need(textgit(repo,"rev-parse","HEAD")==PIN["native" if mode=="native" else "original"]["head"],"candidate world pin")
    sys.path.insert(0,str(engine))
    from research.RHRC.integration.opica_composition.executor import generate_source,generate_consumer,parse_native,lean_name
    from research.RHRC.integration.opica_composition.contracts import TargetSpec,CompositionProposal,PER_ATTEMPT_GATES
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.proposals import validate_plan,used_constant_ids
    from research.RHRC.integration.opica_composition.canonical import load_bytes
    from types import SimpleNamespace
    env=dict(os.environ);lean=pathlib.Path(subprocess.check_output(["lake","env","which","lean"],cwd=repo,text=True).strip())
    prefix=pathlib.Path(subprocess.check_output([lean,"--print-prefix"],cwd=repo,text=True).strip())
    lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=repo,text=True).strip()
    env.update(LEAN_PATH=str(work)+os.pathsep+lp,LEAN_NUM_THREADS="2")
    results=[]
    rows=manifest["selected" if mode=="native" else "resolved"]
    for cand in rows[:limit]:
        folder=out/cand["id"];folder.mkdir(parents=True,exist_ok=False)
        result={"id":cand["id"],"label":cand["label"],"mode":mode,"status":"UNRESOLVED","stages":{},"proof_acceptance":False}
        results.append(result)
        try:
            validate_plan(cand["plan"])
            target=cand["target"];tname=lean_name(target["declaration"]);tmod=lean_name(target["module"])
            table=[];contract={}
            for row in cand["sources"]:
                name=lean_name(row["declaration"])
                module=lean_name(row.get("source_module") or row["module"])
                need(name.split(".")[-1] not in SUFFIXES and name not in FORBIDDEN,"forbidden source")
                table.append({"id":row["id"],"declaration":name,"module":module,"role":"constant"});contract[name]=row
            ids={x["id"]:x["declaration"] for x in table}
            need(set(ids)==set(used_constant_ids(cand["plan"])),"plan source table drift")
            imports=sorted({tmod,*[x["module"] for x in table],"Zeta23.RHRC.OpicaComposition.Export"})
            # Actual compiler checks the selected source types and literal target
            # in this very environment before candidate compilation.
            driver="\n".join("import "+m for m in imports)+"\n"
            driver+="run_cmd Zeta23.RHRC.OpicaComposition.exportTarget "+chr(96)+tname+' "value"\n'
            for row in table:driver+="run_cmd Zeta23.RHRC.OpicaComposition.exportTarget "+chr(96)+row["declaration"]+' "type"\n'
            (folder/"ActualTypes.lean").write_text(driver)
            localenv={**env,"LEAN_PATH":str(folder)+os.pathsep+env["LEAN_PATH"]}
            x=command([lean,"--root="+str(folder),folder/"ActualTypes.lean"],repo,localenv,folder/"ActualTypes.log",240);result["stages"]["actual_types"]=x
            if x["status"]!="PASS":result["status"]="ADAPTER_REQUIRED" if x["status"]=="REJECTED" else x["status"];continue
            types=[load_bytes(l.split(b"\t",1)[1]) for l in (folder/"ActualTypes.log").read_bytes().splitlines() if l.startswith(b"OPICA_TARGET\t")]
            need(len(types)==len(table)+1,"actual type inventory")
            expected=cand["expected_expression"];need(expression_hash(expected)==cand["expected_type_sha256"],"frozen target digest")
            eq=lambda a,b: expression_hash(a)==expression_hash(b) if mode=="native" else fingerprint(a)==fingerprint(b)
            if not eq(types[0],expected) or any(not eq(e,contract[row["declaration"]]["type_expression"]) for row,e in zip(table,types[1:])):
                result["status"]="ADAPTER_REQUIRED";result["reason"]="actual compiler types differ from frozen research types";continue
            spec=TargetSpec("R1_"+cand["id"][:16],tname,tmod,expression_hash(types[0]),ids,sorted(PIN["allowed_axioms"]),sorted({tmod,*[x["module"] for x in table]}),list(PER_ATTEMPT_GATES),"value",FORBIDDEN)
            proposal=CompositionProposal(cand["id"],spec.target_id,"0"*64,cand["plan"])
            (folder/"OpicaAttempt.lean").write_text(generate_source(proposal,spec,table))
            (folder/"OpicaConsumer.lean").write_text(generate_consumer(spec))
            write(folder/"target.json",spec.to_dict());write(folder/"candidate.json",cand)
            x=command([lean,"--root="+str(folder),"-DwarningAsError=true","-o",folder/"OpicaAttempt.olean",folder/"OpicaAttempt.lean"],repo,localenv,folder/"OpicaAttempt.log",300);result["stages"]["kernel"]=x
            if x["status"]!="PASS":result["status"]="TYPE_REJECTED_THIS_APPLICATION" if x["status"]=="REJECTED" else x["status"];continue
            row=parse_native(folder/"OpicaAttempt.log","OPICA_NATIVE")
            need(expression_hash(row["type_expression"])==spec.expected_type_hash,"kernel result differs from actual target")
            need(set(row["axioms"])<=set(PIN["allowed_axioms"]) and not any(n.split(".")[-1] in SUFFIXES or n in FORBIDDEN for n in row["constants"]),"endpoint or axiom violation")
            x=command([lean,"--root="+str(folder),"-DwarningAsError=true","-o",folder/"OpicaConsumer.olean",folder/"OpicaConsumer.lean"],repo,localenv,folder/"OpicaConsumer.log",300);result["stages"]["independent_type"]=x
            if x["status"]!="PASS":result["status"]="INDEPENDENT_REPLAY_FAILED";continue
            independent=parse_native(folder/"OpicaConsumer.log","OPICA_INDEPENDENT")
            need(expression_hash(independent["type_expression"])==spec.expected_type_hash and set(independent["axioms"])<=set(PIN["allowed_axioms"]) and not any(n.split(".")[-1] in SUFFIXES or n in FORBIDDEN for n in independent["constants"]),"independent audit mismatch")
            # Recheck all actual declarations from fresh kernel state, not merely
            # accept the imported .olean. This is stock Lean, not another implementation.
            checker=prefix/"bin/leanchecker"
            if not checker.is_file():result["status"]="INDEPENDENT_CHECKER_UNAVAILABLE";continue
            x=command([checker,"--fresh","--verbose","OpicaConsumer"],repo,localenv,folder/"fresh-kernel.log",600);result["stages"]["fresh_stock_kernel"]=x
            if x["status"]!="PASS":result["status"]="RESOURCE_EXHAUSTED" if x["status"]=="RESOURCE_EXHAUSTED" else "INDEPENDENT_REPLAY_FAILED";continue
            result.update(status="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED",actual_type_sha256=spec.expected_type_hash,axioms=row["axioms"],dependency_count=len(row["constants"]),premises=[x for x in row["context"] if x["is_prop"]],alternate_kernel="NOT_RUN",cross_pin_definition_equivalence="REVIEW_REQUIRED" if mode=="mixed" else "SAME_NATIVE_PIN")
        except Exception as e:
            result.update(status="ADAPTER_REQUIRED",reason=str(e)[:1500])
        finally:
            result["files"]={p.name:filehash(p) for p in folder.iterdir() if p.is_file()}
            write(folder/"receipt.json",result)
            print("CANDIDATE",cand["id"],result["status"],flush=True)
    write(out/"validation.json",{"schema":"OPICA_R1_CANDIDATE_VALIDATION_V1","mode":mode,"native":PIN["native"],"original":PIN["original"]["head"],"results":results,"omitted":max(0,len(rows)-limit),"proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"})
    print(json.dumps({"status":"VALIDATION_CAMPAIGN_COMPLETE_NOT_PROOF_RELEASE","mode":mode,"attempts":len(results),"local_pin_success":sum(x["status"]=="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED" for x in results),"proof_acceptance":False}))
def main():
    p=argparse.ArgumentParser()
    for arg in ("repo","engine","work","manifest","output"):p.add_argument("--"+arg,type=pathlib.Path,required=True)
    p.add_argument("--mode",choices=("native","mixed"),required=True);p.add_argument("--limit",type=int,default=4)
    a=p.parse_args();need(1<=a.limit<=8,"validation cap");a.output.mkdir(parents=True,exist_ok=False)
    execute(a.repo.resolve(),a.engine.resolve(),a.work.resolve(),json.loads(a.manifest.read_text()),a.output.resolve(),a.mode,a.limit)
if __name__=="__main__":main()
