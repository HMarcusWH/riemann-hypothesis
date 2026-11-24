"""Small native compiler and actual dependent-context control before expanded R2."""
import argparse
from r2_common import *
from native_campaign import Campaign
from recursive_feedback import Feedback

CUTS=[
    ("OPICAR2Targets","OPICAR2.cofinalSubpower_min_iff"),
    ("OPICAR2Targets","OPICAR2.minPolarityRawSubpower_iff"),
    ("OPICAR2Targets","OPICAR2.onePolarity_of_adaptiveMinOpposedSupply"),
    ("OPICAR2Targets","OPICAR2.empty_clippedOpposedEnergy_le"),
    ("OPICAR2Targets","OPICAR2.empty_min_budget_optimal"),
    ("OPICAR2Targets","OPICAR2.adaptiveMin_iff_emptyRemoval"),
    ("OPICAR2Targets","OPICAR2.onePolarity_of_emptyRemovalSupply"),
    ("OPICAR2EnergyDetector","OPICAR2.directEnergyToC1_of_power_comparison"),
    ("OPICAR2EnergyDetector","OPICAR2.directEnergyToC1_of_power_supply")]
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    pin=LOCK["native"];epoch={"native":pin,"proof_acceptance":False}
    write(out/"epoch.json",epoch)
    result={"schema":"OPICA_R2_NATIVE_MATH_CUT_V1","status":"INCOMPLETE_EXECUTION","native":pin,"controller":controller_scope(HERE.parent.parent),"roots":[],"compiles":[],**CLAIMS}
    try:
        c=Campaign(a.repo,out/"epoch.json",out,out/"compiler")
        result["compiles"]=c.compiles
        c.setup()
        need("OPICAR2EnergyDetector" in c.adapter_modules,"Detector adapter not compiled")
        for i,(module,name) in enumerate(CUTS):
            ok,log,_=c.driver("MathCut"+str(i),["OPICAR2Export",module],"run_cmd OPICAR2Export.emitRow "+chr(96)+name,seconds=1200)
            need(ok,"Named conditional root export failed")
            rows=marker_rows(log,"OPICA3_ATLAS");cls=marker_rows(log,"OPICA_R2_CLOSURE")
            need(len(rows)==len(cls)==1 and rows[0]["declaration"]==cls[0]["name"]==name and cls[0]["is_prop"],"Compiler root identity")
            row=rows[0]
            need(set(row["axioms"])<=ALLOWED and not any(forbidden(n) for n in cls[0]["dependencies"]+row["type_constants"]),"Endpoint or axiom contamination")
            result["roots"].append(compact_dependency_row({**row,"world":"NATIVE_COMPILER","type_sha256":c.eh(row["type_expression"]),"dependencies":cls[0]["dependencies"]},out))
        prefix=Path(subprocess.check_output([c.lean,"--print-prefix"],cwd=c.repo,env=c.env,text=True).strip())
        for module in ("OPICAR2Targets","OPICAR2EnergyDetector"):
            need(c.run([prefix/"bin/leanchecker","--fresh","--verbose",module],"fresh-stock-"+module,1800),"Fresh stock replay failed")
        from removal_controls import run as finite_removal_controls
        result["finite_removal_controls"]=finite_removal_controls()
        f=Feedback(c.repo,c.work,{"epoch":epoch},{"nodes":[]},out/"context-controls");f.controls()
        result["context_controls"]=read(out/"context-controls/compiler-controls.json")
        for row in result["roots"]:verify_dependency_row(row,out)
        result["status"]="PASS_CONDITIONAL_CUTS_AND_CONTEXT_CONTROLS_ONLY"
    except BaseException as ex:
        result["error"]=str(ex)[:1500];raise
    finally:write(out/"receipt.json",result)
if __name__=="__main__":main()
