"""Reconstruct shortlisted mixed proof terms on the original Lean pin.
Never import compiled native objects. Dynamic frontier sources are regenerated
from named compiler selectors, not executed from arbitrary artifacts.
"""
import argparse,sys,shutil,re
from pathlib import Path
from r2_common import *
sys.path.insert(0,str(R1))
import candidate_port as port
from verify_candidates import validate

def run(original,native,manifest,out):
    original=original.resolve();native=native.resolve();out=out.resolve()
    need(manifest["schema"]=="OPICA_R2_CANDIDATE_MANIFEST_V1" and manifest["mode"]=="mixed" and manifest["proof_acceptance"] is False and manifest["original_head"]==R1_PIN["original"]["head"],"Mixed manifest scope")
    out.mkdir(parents=True,exist_ok=False)
    if not manifest["selected"]:
        write(out/"review.json",{"schema":"OPICA_R2_VALIDATION_V1","mode":"mixed","native":manifest["native"],"status":"NO_SHORTLISTED_MIXED_CANDIDATES","results":[],**CLAIMS});return
    need(git(original,"rev-parse","HEAD")==R1_PIN["original"]["head"] and git(original,"rev-parse","HEAD^{tree}")=="e517b335d21898fd2506ad538a1e1775c0aaa4e4","Original pin differs")
    status=git(original,"status","--porcelain","--untracked-files=all")
    need(not status,"Original source dirty: "+status[:1500])
    need((original/"lean-toolchain").read_text().strip()==R1_PIN["original"]["toolchain"],"Original compiler differs")
    manifest_packages=read(original/"lake-manifest.json")["packages"]
    ml=[x for x in manifest_packages if x["name"]=="mathlib"]
    need(len(ml)==1 and ml[0]["rev"]==R1_PIN["original"]["mathlib"],"Original Mathlib pin differs")
    for p in manifest_packages:need(git(original/".lake/packages"/p["name"],"rev-parse","HEAD")==p["rev"],"Original package checkout differs: "+p["name"])
    check_pin(native,manifest["native"])
    work=out/"work";work.mkdir()
    adapters={"OPICAExtractionCommon":R1/"Common.lean","OPICAExtractionNative":R1/"Native.lean","OPICAExtractionEnergy":R1/"Energy.lean","OPICAExtractionPrincipal":R1/"Principal.lean","OPICAExtractionCombinedTargets":R1/"CombinedTargets.lean","OPICAExtractionEnergyTargets":R1/"EnergyTargets.lean","OPICAR2Targets":HERE/"NativeTargets.lean","OPICAR2PrincipalJoint":HERE/"PrincipalJoint.lean","OPICAR2PrincipalHost":HERE/"PrincipalHost.lean","OPICAR2PrincipalShape":HERE/"PrincipalShape.lean","OPICAR2PrincipalLiterature":HERE/"PrincipalLiterature.lean","OPICAR2EnergyDetector":HERE/"EnergyDetector.lean","OPICAR2Export":HERE/"Export.lean","OPICAR2PrincipalTargets":HERE/"PrincipalTargets.lean"}
    port.PIN={**R1_PIN,"native":manifest["native"]}
    for cand in manifest["selected"]:
        t=cand["target"];origin=t.get("origin")
        if not origin:continue
        mod=source_name(t["module"]);owner=source_name(origin["owner"]);target=source_name(t["declaration"])
        need(re.fullmatch(r"OPICAR2(?:External)?Frontier[0-9a-f]{24}",mod) and target==mod+".goal","Invalid generated frontier identity")
        need(type(origin["slot"]) is int and 0<=origin["slot"]<1024,"Invalid frontier slot")
        if origin["world"]=="ORIGINAL_EXPORT":srcmod,_=port.resolve_original(original,owner)
        elif origin["world"]=="ORIGINAL_COMPILER_ADAPTER":srcmod="OPICAExtractionPrincipal"
        else:srcmod=source_name(origin["source_module"])
        source=work/(mod+".lean")
        source.write_text("import OPICAR2Export\nimport "+srcmod+"\nrun_cmd OPICAR2Export.registerPremise "+chr(96)+owner+" "+str(origin["slot"])+" "+chr(96)+target+"\n")
        adapters[mod]=source
    stage=out/"adapter-sources";stage.mkdir()
    for module,path in adapters.items():shutil.copyfile(path,stage/(module+".lean"))
    port.ADAPTERS={m:m+".lean" for m in adapters}
    # Adapt the manifest envelope only; the selected types and plans are
    # byte-identical and verified by the unchanged R1 source-port machinery.
    adapted={**manifest,"schema":"OPICA_R1_CANDIDATE_MANIFEST_V1"}
    port.stage(original,native,stage,adapted,out/"port.json")
    p=read(out/"port.json")
    if not p["resolved"]:
        write(out/"review.json",{"schema":"OPICA_R2_VALIDATION_V1","mode":"mixed","native":manifest["native"],"status":"NO_PORTABLE_CANDIDATES","results":p["rejected"],**CLAIMS});return
    required=set(p["build_modules"]);needed=[x["module"] for x in p["adapter_order"]]
    need(not (required&port.DENIED),"Endpoint module in common-pin build")
    env=compiler_env();b=command(["lake","build",*["+"+m for m in sorted(required)]],original,env,out/"build.log",seconds=9000)
    write(out/"build.json",b)
    need(b["status"]=="PASS","Common-pin source build failed")
    lean=subprocess.check_output(["lake","env","which","lean"],cwd=original,env=env,text=True).strip()
    lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=original,env=env,text=True).strip()
    env["LEAN_PATH"]=str(work)+os.pathsep+lp
    built=set()
    def compile(m):
        if m not in needed or m in built:return
        for line in (stage/(m+".lean")).read_text().splitlines():
            s=re.match(r"^\s*import\s+([\w.']+)",line)
            if s:compile(s[1])
        path=work/(m+".lean");shutil.copyfile(stage/(m+".lean"),path)
        r=command([lean,"--root="+str(work),"-DwarningAsError=true","-o",path.with_suffix(".olean"),path],original,env,out/(m+".log"),seconds=900)
        need(r["status"]=="PASS","Common-pin adapter compile failed: "+m);built.add(m)
    for m in needed:compile(m)
    validate(original,native,work,p,out/"validation","mixed")
    report=read(out/"validation/review.json")
    # Every selected ID receives an outcome, including source-port rejections.
    report["results"]+=p["rejected"]
    ids=[x["id"] for x in report["results"]]
    need(len(ids)==len(set(ids)) and set(ids)=={x["id"] for x in manifest["selected"]},"Mixed result population differs")
    write(out/"review.json",report)
def main():
    p=argparse.ArgumentParser()
    for k in ("original","native","manifest","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.original,a.native,read(a.manifest),a.out)
if __name__=="__main__":main()
