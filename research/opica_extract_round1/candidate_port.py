"""Stage a bounded original-pin source port, never mix compiled objects."""
import argparse,hashlib,json,pathlib,re,shutil,subprocess
from scan import PIN,need,textgit,write
ADAPTERS={"OPICAExtractionCommon":"Common.lean","OPICAExtractionNative":"Native.lean","OPICAExtractionEnergy":"Energy.lean","OPICAExtractionPrincipal":"Principal.lean","OPICAExtractionCombinedTargets":"CombinedTargets.lean","OPICAExtractionEnergyTargets":"EnergyTargets.lean"}
DENIED={"Main","Challenge","Solution","Development.AutomorphicArithmetic.CharacterBoxes.MainConclusion"}
def filehash(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def resolve_original(repo,name):
    rows=[x["original"] for x in PIN["catalog"] if x["name"]==name]
    if not rows:
        leaf=name.rsplit(".",1)[-1]
        need(re.fullmatch(r"[\w']+",leaf) is not None,"unsupported declaration spelling")
        # Exact source candidate anchor, then compiler checks the actual module.
        q=subprocess.run(["git","-C",str(repo),"grep","-l","-E","^[[:space:]]*(private[[:space:]]+)?(theorem|lemma|def|abbrev)[[:space:]]+([[:alnum:]_'.]+\\.)?"+re.escape(leaf)+"([[:space:]:({]|$)",PIN["original"]["head"],"--","src"],capture_output=True,text=True,timeout=120)
        rows=[s.split(":",1)[1] for s in q.stdout.splitlines() if ":" in s and s.endswith(".lean")]
        need(q.returncode==0 and len(set(rows))==1,"unresolved/ambiguous original declaration origin")
    need(len(set(rows))==1,"ambiguous original anchor")
    p=rows[0];need(p.startswith("src/") and p.endswith(".lean"),"source path")
    mod=p[4:-5].replace("/",".")
    need(mod not in DENIED,"endpoint import refused")
    return mod,p
def stage(repo,native,controller,manifest,out,budget=15000):
    need(textgit(repo,"rev-parse","HEAD")==PIN["original"]["head"] and textgit(native,"rev-parse","HEAD")==PIN["native"]["head"] and textgit(native,"rev-parse","HEAD^{tree}")==PIN["native"]["tree"],"port source epoch")
    need(not textgit(repo,"diff","--name-only","HEAD") and not textgit(native,"diff","--name-only","HEAD"),"source dirty")
    need((repo/"lean-toolchain").read_text().strip()==PIN["original"]["toolchain"],"common pin")
    need(manifest.get("schema")=="OPICA_R1_CANDIDATE_MANIFEST_V1" and manifest.get("mode")=="mixed" and manifest.get("native")==PIN["native"] and manifest.get("original_head")==PIN["original"]["head"] and manifest.get("proof_acceptance") is False,"candidate manifest epoch")
    need(not (repo/"src/Zeta23").exists(),"native namespace collision")
    # Copy only authored, Git-tracked Lean files. No native .olean or cache.
    names=textgit(native,"ls-files","--","Zeta23","Zeta23.lean").splitlines()
    files={}
    for rel in names:
        if not rel.endswith(".lean"):continue
        src=native/rel;dst=repo/"src"/rel
        need(src.is_file() and not src.is_symlink() and not dst.exists(),"native staging source")
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);files[rel]=filehash(dst)
    lake=repo/"lakefile.toml"
    with lake.open("a") as f:f.write('\n[[lean_lib]]\nname = "Zeta23"\nleanOptions = {autoImplicit = true, maxHeartbeats = 800000}\n')
    resolved=[];rejected=[];modules={"Zeta23.RHRC.OpicaComposition.Audit"}
    for cand in manifest["selected"]:
        try:
            cc=json.loads(json.dumps(cand));mm=set()
            for row in cc["sources"]:
                w=row["world"]
                if w=="ORIGINAL_EXPORT":
                    module,path=resolve_original(repo,row["declaration"]);row["source_path"]=path;row["source_blob"]=textgit(repo,"rev-parse",PIN["original"]["head"]+":"+path)
                elif w=="ORIGINAL_COMPILER_ADAPTER":module="OPICAExtractionPrincipal"
                else:module=row.get("source_module") or row.get("module")
                need(isinstance(module,str) and module not in DENIED,"source module")
                row["source_module"]=module;mm.add(module)
            mm.add(cc["target"]["module"]);modules|=mm;resolved.append(cc)
        except (RuntimeError,subprocess.SubprocessError,KeyError) as e:
            rejected.append({"id":cand["id"],"status":"ADAPTER_REQUIRED","reason":str(e)[:1000]})
    # Account for imports before build: known repo source modules only.
    # Mathlib deps are separately pinned and intentionally outside this count.
    pending=list(modules);seen=set();required=set(modules)-set(ADAPTERS)
    while pending:
        m=pending.pop()
        if m in seen:continue
        need(m not in DENIED,"endpoint in selected import closure: "+m)
        seen.add(m);need(len(seen)<=budget,"RESOURCE_EXHAUSTED: source import closure")
        if m in ADAPTERS:p=controller/ADAPTERS[m]
        else:p=repo/"src"/(m.replace(".","/")+".lean")
        if not p.is_file():continue
        for line in p.read_text(encoding="utf8").splitlines():
            q=re.match(r"^\s*(?:public\s+)?import\s+([^\s]+)",line)
            if q:
                target=q.group(1)
                if target in ADAPTERS or (repo/"src"/(target.replace(".","/")+".lean")).is_file():
                    pending.append(target)
                    if m in ADAPTERS and target not in ADAPTERS:required.add(target)
    order=[];visiting=set()
    def visit(m):
        if m not in ADAPTERS or m in order:return
        need(m not in visiting,"adapter import cycle")
        visiting.add(m)
        for line in (controller/ADAPTERS[m]).read_text(encoding="utf8").splitlines():
            q=re.match(r"^\s*(?:public\s+)?import\s+([^\s]+)",line)
            if q:visit(q.group(1))
        visiting.remove(m);order.append(m)
    for m in sorted(modules):visit(m)
    write(out,{"schema":"OPICA_R1_COMMON_PIN_PORT_V1","mode":"mixed","original":PIN["original"]["head"],"native":PIN["native"],"compiler":PIN["original"]["toolchain"],"staged_native_files":files,"lakefile_sha256":filehash(lake),"resolved":resolved,"rejected":rejected,"source_import_closure_count":len(seen),"build_modules":sorted(required),"adapter_order":[{"module":m,"file":ADAPTERS[m]} for m in order],"proof_acceptance":False,"C1":"OPEN"})
    print(json.dumps({"status":"PORT_STAGED_NOT_COMPILED","selected":len(resolved),"rejected":len(rejected),"source_modules":len(seen),"proof_acceptance":False}))
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=pathlib.Path,required=True);p.add_argument("--native",type=pathlib.Path,required=True);p.add_argument("--controller",type=pathlib.Path,required=True);p.add_argument("--manifest",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();stage(a.repo.resolve(),a.native.resolve(),a.controller.resolve(),json.loads(a.manifest.read_text()),a.output)
if __name__=="__main__":main()
