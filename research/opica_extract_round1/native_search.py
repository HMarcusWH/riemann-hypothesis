"""Native OPICA: real compiler DAGs and original bounded proposer, no proof promotion."""
import argparse, hashlib, json, os, pathlib, subprocess, sys
from scan import PIN, need, textgit, write
PREFIX="Zeta23.OPICARound6.PrimeDeficit."
SIGNED="Zeta23.OPICARound6.NextSearch."
C1="Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds"
TARGETS=[("OPICAExtractionR1.NativeEnergySubpower","OPICAExtractionEnergy"),("OPICAExtractionR1.DirectEnergyToC1","OPICAExtractionEnergy"),("OPICAExtractionR1.NativeLiteralWindows","OPICAExtractionNative"),(PREFIX+"LargePrimeDeficitSubpower",PREFIX+"Source"),(PREFIX+"MissingPrimeDeficitToLiteralGBridge",PREFIX+"Source"),(SIGNED+"OnePolarityRawSubpower",SIGNED+"SourceEnergies"),(C1,"Zeta23.OPICARound4.ArithmeticFrontier.MomentSlices")]
MENU=[("OPICAExtractionR1.native_energy_of_ramp_windows","OPICAExtractionEnergy"),("OPICAExtractionR1.native_energy_of_literal_windows","OPICAExtractionEnergy"),("OPICAExtractionR1.native_c1_of_ramp_windows_of_direct_bridge","OPICAExtractionEnergy"),("OPICAExtractionR1.native_windows_of_ramp_windows","OPICAExtractionNative"),(PREFIX+"positiveDeficitEnergy_nonneg",PREFIX+"Source"),(SIGNED+"rawPositiveEnergy_le_full_components",SIGNED+"SourceEnergies"),(SIGNED+"rawPositiveEnergy_le_of_component_budgets",SIGNED+"SourceEnergies"),*[(f"Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_{s}","Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure") for s in ("even","odd","tendsto")]]
FORBIDDEN=["riemannHypothesis","_root_.riemannHypothesis","UpperTheory.FinalTheorems.riemannHypothesis","UpperTheory.FinalTheorems.everyCharacter","LFunction_ne_zero_of_half_lt_re","Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis","Zeta23.OPICARound4.ArithmeticFrontier.riemannHypothesis_iff_cofinal_moment_slice_bounds"]
def run(repo,work,out,mode):
    global MENU,TARGETS
    if mode=="base":
        MENU=[x for x in MENU if x[1]!="OPICAExtractionEnergy"]
        TARGETS=[x for x in TARGETS if x[1]!="OPICAExtractionEnergy"]
    n=PIN["native"]
    need(textgit(repo,"rev-parse","HEAD")==n["head"] and textgit(repo,"rev-parse","HEAD^{tree}")==n["tree"],"native pin")
    sys.path.insert(0,str(repo))
    from research.RHRC.integration.opica_composition.qualification import atlas_driver
    from research.RHRC.integration.opica_composition.executor import lean_name
    from research.RHRC.integration.opica_composition.canonical import load_bytes, digest
    from research.RHRC.integration.opica_composition.inventory import expression_hash
    from research.RHRC.integration.opica_composition.contracts import StatementContract,StatementInventory,TargetSpec,GrammarProfile,SearchBudget,PER_ATTEMPT_GATES
    from research.RHRC.integration.opica_composition.proposals import enumerate_candidates,used_constant_ids
    rows=[{"declaration":a,"module":b} for a,b in MENU]
    code="import Zeta23.RHRC.OpicaComposition.Export\n"+atlas_driver(rows)
    for name,_ in MENU:
        code+="\nrun_cmd Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants "+chr(96)+lean_name(name)+' "type"\n'
    for name,_ in TARGETS:
        code+="\nrun_cmd Zeta23.RHRC.OpicaComposition.exportTarget "+chr(96)+lean_name(name)+' "value"\n'
        code+="run_cmd Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants "+chr(96)+lean_name(name)+' "value"\n'
    code+="""
open Lean Elab Command in
run_cmd do
  let banned : List String := """+json.dumps(FORBIDDEN)+"""
  let roots : List Name := ["""+",".join(chr(96)+a for a,_ in MENU)+"""]
  for root in roots do
    let closure : Array Name ← liftTermElabM <| Zeta23.RHRC.OpicaComposition.dependencyClosure root
    for name in closure do
      if banned.contains name.toString || name.toString.endsWith ".riemannHypothesis" then
        throwError "forbidden native proof dependency"
    liftIO <| IO.println ("OPICA_R1_CLOSURE\\t" ++ root.toString ++ "\\t" ++ toString closure.size)
"""
    driver=work/("NativeTargetAtlas-"+mode+".lean");driver.write_text(code)
    env=dict(os.environ);lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=repo,text=True).strip()
    env["LEAN_PATH"]=str(work)+os.pathsep+lp
    lean=subprocess.check_output(["lake","env","which","lean"],cwd=repo,text=True).strip()
    proc=subprocess.run([lean,str(driver)],cwd=repo,env=env,capture_output=True,timeout=1800)
    (work/("native-atlas-"+mode+".log")).write_bytes(proc.stdout+proc.stderr)
    if proc.returncode:print((proc.stdout+proc.stderr).decode(errors="replace")[-12000:])
    need(proc.returncode==0,"native atlas compile failed")
    statements={};targets=[];proofs=[];closure={}
    for line in proc.stdout.splitlines():
        if line.startswith(b"OPICA3_ATLAS\t"):
            a=load_bytes(line.split(b"\t",1)[1]);need(a["declaration"] not in statements,"duplicate atlas");statements[a["declaration"]]=a
        elif line.startswith(b"OPICA_TARGET\t"):targets.append(load_bytes(line.split(b"\t",1)[1]))
        elif line.startswith(b"OPICA_RETRIEVAL_PROOFS\t"):proofs.append(load_bytes(line.split(b"\t",1)[1]))
        elif line.startswith(b"OPICA_R1_CLOSURE\t"):
            _,name,count=line.decode().split("\t");closure[name]=int(count)
    need(set(statements)==set(closure)=={a for a,_ in MENU} and len(targets)==len(TARGETS) and len(proofs)==len(MENU)+len(TARGETS),"incomplete exact types or closure")
    generation=digest({"native_head":n["head"],"native_tree":n["tree"],"compiler_export_sha256":hashlib.sha256(proc.stdout).hexdigest()},domain="OPICA_CROSS_REPO_R1_NATIVE_V1")
    typed=[];constants={}
    for i,(name,module) in enumerate(MENU):
        row=statements[name]
        need(row["module"]==module and set(row["axioms"])<=set(PIN["allowed_axioms"]),"native theorem origin/axioms")
        record=StatementContract(declaration=name,module=module,type_expression=row["type_expression"],type_sha256=expression_hash(row["type_expression"]),universe_parameters=row["universe_parameters"],outer_telescope=row["outer_telescope"],conclusion_text=row["conclusion_text"],type_constants=row["type_constants"],value_constants=row["value_constants"],axioms=row["axioms"])
        typed.append(record)
        constants[digest({"source_generation":generation,"declaration":name,"module":module},domain="OPICA_APPROVED_CONSTANT_V1")]=name
    inv=StatementInventory(generation,[x.to_dict() for x in typed],hashlib.sha256(proc.stdout).hexdigest())
    results=[]
    for i,(name,module) in enumerate(TARGETS):
        e=targets[i]
        spec=TargetSpec("EXTRACT_R1_"+str(i),name,module,expression_hash(e),constants,sorted(PIN["allowed_axioms"]),sorted(set([module]+[b for a,b in MENU])),list(PER_ATTEMPT_GATES),"value",FORBIDDEN)
        batch=enumerate_candidates(inv,spec,GrammarProfile(FORBIDDEN,[]),SearchBudget(candidates=16,term_nodes=512,term_depth=16,wall_seconds=90,heartbeats=800000),search_contract={"expected_expression":e,"statements":[{**x.to_dict(),"proof_constants":proofs[j]} for j,x in enumerate(typed)],"proof_constants":proofs[len(MENU)+i]})
        plans=[]
        for x in batch.candidates:
            ids=used_constant_ids(x["term_plan"]);need(set(ids)<=set(constants),"unapproved source")
            plans.append({"action_id":x["action_id"],"term_plan":x["term_plan"],"constant_ids":{z:constants[z] for z in sorted(ids)},"used":[constants[z] for z in sorted(ids)],"kind":"BARE_SEED" if x["term_plan"].get("tag")=="const" else "UNVERIFIED_COMPOSITION","kernel_acceptance":False})
        results.append({"target":name,"module":module,"target_kind":"value","type_sha256":expression_hash(e),"compiler_expression":e,"proof_constants":proofs[len(MENU)+i],"plans":plans,"disposition":batch.disposition,"bounded_complete":batch.complete})
    write(out,{"schema":"OPICA_CROSS_REPO_R1_NATIVE_TYPES_AND_RETRIEVAL","generation":generation,"native":n,"actual_source_theorems":[{**x.to_dict(),"closure_count":closure[x.declaration],"proof_constants":proofs[j]} for j,x in enumerate(typed)],"targets":results,"external_approved_proof_constants":[],"proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"})
    print(json.dumps({"status":"NATIVE_TYPED_RETRIEVAL_NOT_PROOF","targets":len(results),"nontrivial":[sum(x["kind"]=="UNVERIFIED_COMPOSITION" for x in a["plans"]) for a in results],"proof_acceptance":False}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--work",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    p.add_argument("--mode",choices=("base","expanded"),default="expanded")
    a=p.parse_args();run(a.repo.resolve(),a.work.resolve(),a.output,a.mode)
