"""Build original-source arithmetic cuts; emit only fully audited source-pin rows."""
import argparse,shutil
from r2_common import *
from harvest import api,pages,artifact,successful_job,run_identity

ORIGINAL_TREE="e517b335d21898fd2506ad538a1e1775c0aaa4e4"
CODEC_HEAD="4f81c784d3b330395507f6dcd1c8b0010b3835cc"
CODEC_PATH="Zeta23/RHRC/OpicaTypeExprExport.lean"
MODULES={
    "joint":("OPICAR2PrincipalJoint","PrincipalJoint.lean",["principal_vwin_of_joint","principal_host_of_joint","principal_windows_of_joint_topG"]),
    "host":("OPICAR2PrincipalHost","PrincipalHost.lean",["principal_vwin_from_source","principal_host_from_source","principal_connected_of_topG","principal_windows_of_topG"]),
    "shape":("OPICAR2PrincipalShape","PrincipalShape.lean",["topG_of_green_hyps","principal_connected_of_green_hyps_host"]),
    "literature":("OPICAR2PrincipalLiterature","PrincipalLiterature.lean",["topG_of_literature_components"])}
EXCLUDED={"plugAll","plugWin","everyE₂","every_character_of_theta_integrals_local_matching","every_character_of_literature_of_vWin","zeroFreeAll_of_topG"}
def safe_dependency(n):
    return not forbidden(n) and n.split(".")[-1] not in EXCLUDED

def expected_sources(cut):
    mods={"OPICAExtractionCommon":R1/"Common.lean","OPICAExtractionPrincipal":R1/"Principal.lean"}
    if cut=="literature":mods[MODULES["shape"][0]]=HERE/MODULES["shape"][1]
    module,filename,_=MODULES[cut];mods[module]=HERE/filename
    return mods

def source_manifest(cut):
    return {str(p.relative_to(HERE.parent)):filehash(p) for p in expected_sources(cut).values()}

def compile_cut(repo,codec,cut,out):
    repo=repo.resolve();codec=codec.resolve();out=out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    stages=[]
    result={"schema":"OPICA_R2_PRINCIPAL_SUPPLIER_V1","cut":cut,"status":"INCOMPLETE_EXECUTION","rows":[],"stages":stages,
            "controller":controller_scope(HERE.parent.parent),"original":{"head":R1_PIN["original"]["head"],"tree":ORIGINAL_TREE,"toolchain":R1_PIN["original"]["toolchain"],"mathlib":R1_PIN["original"]["mathlib"]},
            "source_sha256":source_manifest(cut),**CLAIMS}
    try:
        check_pin(repo,result["original"])
        need(git(codec,"rev-parse","HEAD")==CODEC_HEAD,"Wrong native type codec source")
        result["codec"]={"head":CODEC_HEAD,"blob":git(codec,"rev-parse",CODEC_HEAD+":"+CODEC_PATH),"sha256":filehash(codec/CODEC_PATH)}
        env=compiler_env();mods=expected_sources(cut)
        external=set()
        for p in mods.values():
            for line in p.read_text().splitlines():
                if line.startswith("import "):
                    name=line[7:].strip()
                    if name not in mods and name.startswith(("Development.","Formalism.","CompanionTheory.","GroundTheory.")):
                        need(safe_dependency(name),"Excluded import")
                        external.add(name)
        def run(args,label,seconds):
            s=command(args,repo,env,out/(label+".log"),seconds=seconds);stages.append({"stage":label,**s});need(s["status"]=="PASS",label+" did not pass")
        run(["lake","build",*["+"+n for n in sorted(external)]],"source-dependency-build",7800)
        lean=subprocess.check_output(["lake","env","which","lean"],cwd=repo,env=env,text=True).strip()
        lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=repo,env=env,text=True).strip()
        env["LEAN_PATH"]=str(out)+os.pathsep+lp
        for name,p in mods.items():
            dst=out/(name+".lean");shutil.copyfile(p,dst)
            run([lean,"--root="+str(out),"-DwarningAsError=true","-o",dst.with_suffix(".olean"),dst],name,1200)
        target=out/CODEC_PATH;target.parent.mkdir(parents=True);shutil.copyfile(codec/CODEC_PATH,target)
        run([lean,"--root="+str(out),"-DwarningAsError=true","-o",target.with_suffix(".olean"),target],"codec",600)
        original=(R1/"PrincipalAudit.lean").read_text()
        library=original.split("\nrun_cmd ",1)[0]+"\n"
        lib=out/"PrincipalAuditLibrary.lean";lib.write_text(library)
        result["audit_library_sha256"]=filehash(lib)
        run([lean,"--root="+str(out),"-DwarningAsError=true","-o",lib.with_suffix(".olean"),lib],"audit-library",600)
        module,_,names=MODULES[cut]
        roots=["OPICAR2Original."+n for n in names]
        audit=out/"SupplierAudit.lean"
        audit.write_text("import "+module+"\nimport PrincipalAuditLibrary\n"+"\n".join("run_cmd OPICAExtractionR1.Audit.emit "+chr(96)+n for n in roots)+"\n")
        run([lean,"--root="+str(out),"-DwarningAsError=true",audit],"supplier-audit",1800)
        rows=marker_rows(out/"supplier-audit.log","OPICA_R1_PRINCIPAL")
        need(len(rows)==len(roots) and {r["name"] for r in rows}==set(roots),"Supplier root census")
        for row in rows:
            deps=row["dependency_names"]
            need(row["name"] in deps and len(deps)==len(set(deps)) and all(safe_dependency(n) for n in deps),"Forbidden or incomplete supplier dependency closure")
            need(set(row["axioms"])<=ALLOWED,"Supplier unapproved axiom")
        prefix=Path(subprocess.check_output([lean,"--print-prefix"],cwd=repo,env=env,text=True).strip())
        run([prefix/"bin/leanchecker","--fresh","--verbose",module],"fresh-stock-kernel",1200)
        result.update(status="PASS_ORIGINAL_PIN_CUT_ONLY",rows=rows,source_module=module)
        return result
    except BaseException as ex:
        result["error"]=str(ex)[:1500];raise
    finally:
        write(out/"principal-supplier-receipt.json",result)

def collect(out,repo):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    scope=controller_scope(repo)
    repository=LOCK["controller"]["repository"]
    runid=int(os.environ["GITHUB_RUN_ID"]);attempt=int(os.environ["GITHUB_RUN_ATTEMPT"])
    spec={"repository":repository,"run":runid,"head":scope["head"],"workflow":".github/workflows/opica-recursive-r2.yml","attempt":attempt}
    run=api("repos/"+repository+"/actions/runs/"+str(runid));run_identity(run,spec)
    jobs=pages("repos/"+repository+"/actions/runs/"+str(runid)+"/attempts/"+str(attempt)+"/jobs","jobs")
    record={"spec":spec,"run":run,"jobs":jobs}
    receipts={};unavailable=[]
    for cut in MODULES:
        try:
            name="principal-supplier ("+cut+")"
            need(successful_job(record,name),"Supplier job not successful")
            a="opica-r2-principal-"+cut+"-"+str(runid)+"-"+str(attempt)
            rec=artifact(record,a,["principal-supplier-receipt.json"],out/cut,expected_name=a)
            rec["producer_job"]=next(j["id"] for j in jobs if j["name"]==name and j["conclusion"]=="success")
            receipts[cut]=rec
        except Exception as ex:unavailable.append({"cut":cut,"reason":str(ex)[:1000]})
    write(out/"index.json",{"schema":"OPICA_R2_PRINCIPAL_HARVEST_V1","controller":scope,"receipts":receipts,"unavailable":unavailable,**CLAIMS})

def read_suppliers(folder):
    if not (folder/"index.json").is_file():return []
    index=read(folder/"index.json");scope=controller_scope(HERE.parent.parent)
    need(index["schema"]=="OPICA_R2_PRINCIPAL_HARVEST_V1" and index["controller"]==scope and index["proof_acceptance"] is False,"Supplier harvest identity")
    out=[]
    for cut,rec in index["receipts"].items():
        module,_,roots=MODULES[cut];p=folder/cut/"principal-supplier-receipt.json"
        need(filehash(p)==rec["entries"][p.name]["sha256"] and rec["head"]==scope["head"],"Supplier artifact binding")
        d=read(p);need(d["schema"]=="OPICA_R2_PRINCIPAL_SUPPLIER_V1" and d["status"]=="PASS_ORIGINAL_PIN_CUT_ONLY" and d["controller"]==scope and d["cut"]==cut and d["source_module"]==module and d["proof_acceptance"] is False,"Supplier receipt scope")
        need(d["original"]=={"head":R1_PIN["original"]["head"],"tree":ORIGINAL_TREE,"toolchain":R1_PIN["original"]["toolchain"],"mathlib":R1_PIN["original"]["mathlib"]} and d["source_sha256"]==source_manifest(cut),"Supplier source epoch")
        need({r["name"] for r in d["rows"]}=={"OPICAR2Original."+n for n in roots} and len(d["rows"])==len(roots),"Supplier census")
        need(d["stages"] and all(s["status"]=="PASS" for s in d["stages"]) and any(s["stage"]=="fresh-stock-kernel" for s in d["stages"]),"Supplier replay missing")
        for row in d["rows"]:
            need(set(row["axioms"])<=ALLOWED and all(safe_dependency(n) for n in row["dependency_names"]),"Supplier closure rejected")
            out.append((module,row))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cut",choices=MODULES);p.add_argument("--codec",type=Path);p.add_argument("--collect",action="store_true")
    a=p.parse_args()
    if a.collect:collect(a.out,a.repo)
    else:need(a.cut and a.codec,"Cut and codec required");compile_cut(a.repo,a.codec,a.cut,a.out)
if __name__=="__main__":main()
