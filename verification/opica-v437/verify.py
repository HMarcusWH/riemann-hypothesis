#!/usr/bin/env python3
"""New execution candidate. Stock 4.37 Comparator and nanoda, not legacy con-leche receipts."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, re, shutil, stat, subprocess, sys, time
from source import HERE, REPO, PIN, PUBLIC, FC, ALLOWED, roots, scope, git, need, accepted, axiom_report, json_file
P=pathlib.Path
def write(path, data):
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
def digest(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()
def inventory(root):
    need(root.is_dir(),"missing inventory root: "+str(root))
    result={}
    for p in sorted(root.rglob("*")):
        need(not p.is_symlink(),"unexpected symlink: "+str(p))
        if p.is_file():result[str(p.relative_to(root))]={"bytes":p.stat().st_size,"sha256":digest(p)}
    need(bool(result),"empty inventory: "+str(root))
    return result
def inventory_digest(root):
    return hashlib.sha256(json.dumps(inventory(root),sort_keys=True,separators=(",",":")).encode()).hexdigest()
def copy_inputs(dst, with_source=False):
    dst.mkdir()
    for name in ("lakefile.toml","lake-manifest.json","lean-toolchain"):
        shutil.copyfile(REPO/name,dst/name)
    if with_source: shutil.copytree(REPO/"src",dst/"src")
    else:
        (dst/"src").mkdir()
        shutil.copyfile(REPO/"src/Challenge.lean",dst/"src/Challenge.lean")
    shutil.copytree(REPO/"comparator",dst/"comparator")
    (dst/".lake/packages").mkdir(parents=True)
def host_preflight(head):
    e=os.environ
    need(e.get("GITHUB_ACTIONS")=="true" and e.get("GITHUB_REPOSITORY")=="HMarcusWH/riemann-hypothesis" and e.get("RUNNER_ENVIRONMENT")=="self-hosted" and e.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and e.get("GITHUB_REF")=="refs/heads/"+PIN["topic"] and e.get("GITHUB_SHA")==head,"reviewed manual runner only")
    marker=P("/etc/opica/community-v437.json")
    st=marker.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022 and st.st_size<=4096,"invalid root-owned runner marker")
    need(json_file(marker)=={"schema":"OPICA_COMMUNITY_V437_EPHEMERAL_V1","runner_name":e["RUNNER_NAME"],"ephemeral":True,"no_private_data":True},"wrong runner marker")
    need(e["RUNNER_NAME"].startswith("opica-v437-") and os.geteuid()!=0 and os.uname().machine=="x86_64","wrong host")
    need(len(os.sched_getaffinity(0))>=8,"CPU budget")
    ram=int(next(l.split()[1] for l in P("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal:")))//1024
    free=shutil.disk_usage(e["RUNNER_TEMP"]).free
    need(ram>=192000 and free>=500*1024**3 and int(P("/proc/sys/vm/max_map_count").read_text())>=1048576,"resource preflight (192000 MiB RAM, 500 GiB disk, map count)")
    need(shutil.which("bwrap") and shutil.which("zstd"),"sandbox or zstd missing")
    return {"ram_mib":ram,"free_bytes":free,"cpu":len(os.sched_getaffinity(0))}
class Campaign:
    def __init__(self,args):
        self.args=args; self.out=args.output.resolve()
        need(not self.out.exists() and not self.out.is_relative_to(REPO),"fresh external output required")
        self.out.mkdir(parents=True);self.ev=self.out/"evidence";self.ev.mkdir()
        self.exports=self.out/"exports";self.exports.mkdir()
        self.home=self.out/"home";self.home.mkdir()
        self.rt=self.out/"runtime";self.rt.mkdir()
        self.report={"schema":"OPICA_V437_EXECUTION_CANDIDATE_V1","head":args.head,"status":"INCOMPLETE","stages":{},"supplier_38":"NOT_RUN","formal_conjectures_35":"NOT_RUN","combined_50":"NOT_RUN","legacy_con_leche_38_50":"NOT_RUN","original_30_plus_7":"NOT_RUN","native_original_pin_transfer":"NOT_ESTABLISHED","proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN","RH_project_release":"OPEN"}
        self.save()
    def save(self): write(self.ev/"RECEIPT.json",self.report)
    def env(self):
        return {"PATH":str(self.rt/"bin")+":/usr/bin:/bin","HOME":str(self.home),"LANG":"C.UTF-8","LEAN_ABORT_ON_PANIC":"1","LAKE_ARTIFACT_CACHE":"false","LEAN_NUM_THREADS":"2","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_NOSYSTEM":"1"}
    def run(self,name,argv,cwd,*,export=None,timeout=14400,expected=0):
        need(name not in self.report["stages"],"duplicate stage")
        dest=export or self.ev/(name+".stdout")
        err=self.ev/(name+".stderr")
        row={"argv":list(map(str,argv)),"status":"RUNNING","stdout":str(dest.relative_to(self.out)),"stderr":str(err.relative_to(self.out))}
        self.report["stages"][name]=row;self.save();start=time.monotonic()
        print("BEGIN",name,flush=True)
        try:
            with dest.open("xb") as o,err.open("xb") as e:
                rc=subprocess.run(list(map(str,argv)),cwd=cwd,env=self.env(),stdout=o,stderr=e,timeout=timeout,check=False).returncode
            row.update(exit=rc,seconds=time.monotonic()-start,stdout_bytes=dest.stat().st_size,stdout_sha256=digest(dest),stderr_sha256=digest(err))
            need(rc==expected,"unexpected exit in "+name)
            row["status"]="PASS";self.save();print("PASS",name,flush=True)
        except BaseException:
            row.update(status="FAIL_OR_INCOMPLETE",seconds=time.monotonic()-start);self.save();raise
        return dest
    def box(self,project,command,*,extra=(),lean_path=None,writable=True):
        a=["bwrap","--unshare-all","--die-with-parent","--new-session","--clearenv","--ro-bind","/usr","/usr"]
        for p in ("/bin","/lib","/lib64","/etc/ld.so.cache"):
            if P(p).exists(): a+=["--ro-bind",p,p]
        a+=["--proc","/proc","--dev","/dev","--tmpfs","/tmp","--dir","/tmp/home","--ro-bind",str(self.rt),"/opt/lean","--ro-bind",str(project),"/work"]
        if writable: a+=["--bind",str(project/".lake"),"/work/.lake"]
        a+=["--ro-bind",str(self.deps),"/work/.lake/packages"]
        for origin,target in extra: a+=["--ro-bind",str(origin),target]
        for k,v in {"PATH":"/opt/lean/bin:/usr/bin:/bin","HOME":"/tmp/home","LANG":"C.UTF-8","LEAN_ABORT_ON_PANIC":"1","LAKE_ARTIFACT_CACHE":"false","LEAN_NUM_THREADS":"2","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_NOSYSTEM":"1"}.items():a+=["--setenv",k,v]
        if lean_path is not None:a+=["--setenv","LEAN_PATH",lean_path]
        return a+["--chdir","/work","--"]+list(command)
    def inside(self,name,project,command,**kw):
        opts={k:kw.pop(k) for k in ("extra","lean_path","writable") if k in kw}
        return self.run(name,self.box(project,command,**opts),self.out,**kw)
    def path(self,name,project):
        p=self.inside(name,project,["/opt/lean/bin/lake","env","printenv","LEAN_PATH"],timeout=120).read_text().strip()
        need(p and all(x.startswith("/work/.lake/") or x.startswith("/opt/lean/") for x in p.split(":")),"unexpected Lean path")
        return p
    def export(self,name,project,module,selected,*,lean_path=None,extra=()):
        dest=self.exports/(name+".export")
        self.inside(name,project,["/opt/lean/bin/leanexport",module,"--",*selected],export=dest,lean_path=lean_path,extra=extra,writable=False)
        need(dest.stat().st_size>0,"empty proof export")
        return dest
    def judge(self,name,config,ch,sol):
        cfg=self.ev/(name+".config.json");write(cfg,config)
        empty=self.out/"judge";empty.mkdir(exist_ok=True)
        result=self.run(name,[self.rt/"bin/lake","comparator","--json","--config",cfg,"--challenge-from-export",ch,"--solution-from-export",sol],empty)
        try:accepted(json_file(result),config)
        except BaseException:
            self.report["stages"][name]["status"]="FAIL_OR_INCOMPLETE";self.save();raise
        self.report["stages"][name]["actual_comparator_receipt"]="PASS_SANDBOXED_THREE_KERNELS";self.save()
    def prepare(self):
        self.report["source"]=scope(self.args.head);self.report["host"]=host_preflight(self.args.head);self.save()
        archive=self.out/"runtime.tar.zst"
        self.run("download_runtime",["curl","--fail","--silent","--show-error","--location","--retry","3","-o",archive,PIN["runtime_url"]],self.out,timeout=1800)
        need(archive.stat().st_size==PIN["runtime_bytes"] and digest(archive)==PIN["runtime_sha256"],"runtime archive mismatch")
        self.run("extract_runtime",["tar","--zstd","-xf",archive,"--strip-components=1","-C",self.rt],self.out,timeout=1800)
        for binary in ("lean","lake","leanexport","leanchecker","leanchecker-paranoid","nanoda_bin"):
            need((self.rt/"bin"/binary).is_file(),"missing runtime binary "+binary)
        self.report["runtime_binaries"]={n:digest(self.rt/"bin"/n) for n in ("lean","lake","leanexport","leanchecker","leanchecker-paranoid","nanoda_bin")}
        v=self.run("runtime_version",[self.rt/"bin/lean","--version"],self.out,timeout=60).read_text()
        need("version 4.37.0-rc1" in v,"runtime version mismatch")
        # Only the Mathlib dependency preparation has network. It sees no supplier proof source.
        prep=self.out/"dependency-prep";copy_inputs(prep)
        (prep/"src/Challenge.lean").unlink()
        env=self.env();env["MATHLIB_CACHE_GET_URL"]="https://cache.mathlib.org/mathlib4"
        # Cache executable is from the pinned official Mathlib checkout.
        old=self.env;self.env=lambda:env
        try:self.run("mathlib_only_cache",[self.rt/"bin/lake","exe","mathlib/cache","get"],prep,timeout=7200)
        finally:self.env=old
        self.deps=prep/".lake/packages"
        for d in json_file(REPO/"lake-manifest.json")["packages"]:
            need(git(self.deps/d["name"],"rev-parse","HEAD")==d["rev"],"actual dependency pin mismatch")
            need(not git(self.deps/d["name"],"diff","--name-only","HEAD"),"modified dependency source")
        self.report["dependency_pins"]={x["name"]:x["rev"] for x in json_file(REPO/"lake-manifest.json")["packages"]}
        self.dep_roots={n:self.deps/n/".lake/build/lib/lean" for n in self.report["dependency_pins"] if (self.deps/n/".lake/build/lib/lean").is_dir()}
        need("mathlib" in self.dep_roots,"missing Mathlib object root")
        self.report["dependency_object_inventories"]={n:inventory_digest(p) for n,p in self.dep_roots.items()}
        self.report["runtime_library_inventory"]=inventory_digest(self.rt/"lib/lean")
        self.report["source_file_inventory"]=inventory_digest(REPO/"src")
        self.save()
    def supplier(self):
        rr,mr,ff=roots()
        ch=self.out/"challenge";copy_inputs(ch)
        sol=self.out/"supplier";copy_inputs(sol,True)
        shutil.copyfile(HERE/"Ingress.lean",sol/"Ingress.lean")
        need(inventory_digest(sol/"src")==self.report["source_file_inventory"],"supplier copy differs")
        # Same pinned cache mounted read-only; no network or supplier caches during builds.
        self.inside("challenge_build",ch,["/opt/lean/bin/lake","--no-cache","build","Challenge"])
        cp=self.path("challenge_path",ch)
        ce=self.export("challenge_38",ch,"Challenge",rr[:38],lean_path=cp)
        need(digest(ce)==PIN["challenge_hashes"]["original"],"original challenge checksum drift")
        (ch/".lake/comparator").mkdir()
        self.inside("fc_challenge_build",ch,["/opt/lean/bin/lean","--root=comparator","-o",".lake/comparator/FormalConjecturesChallenge.olean","comparator/FormalConjecturesChallenge.lean"],lean_path=cp)
        fce=self.export("fc_challenge_35",ch,"FormalConjecturesChallenge",ff,lean_path="/work/.lake/comparator:"+cp)
        need(digest(fce)==PIN["challenge_hashes"]["formal_conjectures"],"FC challenge checksum drift")
        need(not (sol/".lake/build").exists(),"fresh supplier objects required")
        self.inside("actual_supplier_build",sol,["/opt/lean/bin/lake","--no-cache","build","Main"],timeout=36000)
        sp=self.path("supplier_path",sol)
        need((sol/".lake/build/lib/lean/Main.olean").is_file(),"Main object missing")
        log=self.inside("actual_ingress",sol,["/opt/lean/bin/lean","-DwarningAsError=true","Ingress.lean"],lean_path=sp).read_text()
        self.report["public_axioms"]=axiom_report(log,PUBLIC+["OPICACommunityV437.suppliedRH"]);self.save()
        se=self.export("actual_supplier_38",sol,"Main",rr[:38],lean_path=sp)
        self.judge("original_comparator_38",json_file(REPO/"comparator.json"),ce,se)
        self.report["supplier_38"]="PASS_SANDBOXED_COMPARATOR";self.save()
        (sol/".lake/comparator").mkdir()
        for m in ("FormalConjecturesStatement","FormalConjecturesBridge","FormalConjecturesSolution"):
            self.inside("actual_"+m,sol,["/opt/lean/bin/lean","-DwarningAsError=true","--root=comparator","-o",".lake/comparator/"+m+".olean","comparator/"+m+".lean"],lean_path="/work/.lake/comparator:"+sp)
        fse=self.export("actual_fc_solution_35",sol,"FormalConjecturesSolution",ff,lean_path="/work/.lake/comparator:"+sp)
        self.judge("formal_conjectures_comparator_35",json_file(REPO/"comparator/formal-conjectures.json"),fce,fse)
        self.report["formal_conjectures_35"]="PASS_SANDBOXED_COMPARATOR";self.save()
        self.report["supplier_object_inventory"]=inventory_digest(sol/".lake/build/lib/lean")
        self.save()
        return ch,sol
    def native(self,ch,sol):
        need(self.report["supplier_38"]==self.report["formal_conjectures_35"]=="PASS_SANDBOXED_COMPARATOR","both supplier gates required")
        native=self.out/"native"
        self.run("native_init",["git","init",native],self.out,timeout=60)
        self.run("native_fetch",["git","-C",native,"fetch","--depth=1","--no-tags","https://github.com/HMarcusWH/zeta-23-lean.git",PIN["native_commit"]],self.out,timeout=1800)
        self.run("native_checkout",["git","-C",native,"checkout","--detach","FETCH_HEAD"],self.out,timeout=300)
        need(git(native,"rev-parse","HEAD")==PIN["native_commit"] and git(native,"rev-parse","HEAD^{tree}")==PIN["native_tree"],"native identity mismatch")
        old="51e6992efd06126df61a496bebf8f49482a4e129";lf=native/"lakefile.toml"
        t=lf.read_text();need(t.count(old)==1,"native Mathlib pin changed")
        lf.write_text(t.replace(old,PIN["mathlib"])+'\n[[lean_lib]]\nname = "OPICAStep4"\n')
        (native/"lean-toolchain").write_text(PIN["toolchain"]+"\n")
        lock=json_file(REPO/"lake-manifest.json");lock["name"]="Zeta23";write(native/"lake-manifest.json",lock)
        (native/".lake/packages").mkdir(parents=True)
        bridge=native/"OPICAStep4";bridge.mkdir()
        for p in (HERE/"native_bridge").glob("*.lean"):shutil.copyfile(p,bridge/p.name)
        shutil.copyfile(HERE/"CombinedChallenge.lean",bridge/"CombinedChallenge.lean")
        allowed={"lakefile.toml","lake-manifest.json","lean-toolchain"}|{"OPICAStep4/"+p.name for p in bridge.iterdir()}
        def native_integrity():
            need(git(native,"rev-parse","HEAD")==PIN["native_commit"],"native head changed")
            actual=set(git(native,"diff","--name-only","HEAD").splitlines())|set(git(native,"ls-files","--others","--exclude-standard").splitlines())
            need(actual==allowed,"unexpected native source change")
        native_integrity()
        initial={n:digest(native/n) for n in allowed}
        self.inside("native_only_build",native,["/opt/lean/bin/lake","--no-cache","build","OPICAStep4.NativeValidated"],timeout=21600)
        np=self.path("native_path",native)
        self.inside("native_only_stock_replay",native,["/opt/lean/bin/leanchecker","--fresh","--verbose","OPICAStep4.NativeValidated"],lean_path=np,timeout=14400,writable=False)
        no=native/".lake/build/lib/lean";co=ch/".lake/build/lib/lean";so=sol/".lake/build/lib/lean"
        for other in (co,so):
            need(not ({p.relative_to(no) for p in no.rglob("*.olean")} & {p.relative_to(other) for p in other.rglob("*.olean")}),"native/supplier module collision")
        (native/".lake/combined-challenge/OPICAStep4").mkdir(parents=True)
        cpath="/work/.lake/combined-challenge:"+np+":/supplier-challenge"
        cextra=((co,"/supplier-challenge"),)
        self.inside("combined_expected_types",native,["/opt/lean/bin/lean","--root=/work","-o",".lake/combined-challenge/OPICAStep4/CombinedChallenge.olean","OPICAStep4/CombinedChallenge.lean"],lean_path=cpath,extra=cextra)
        rr,mr,_=roots()
        cexp=self.export("combined_challenge_50",native,"OPICAStep4.CombinedChallenge",rr,lean_path=cpath,extra=cextra)
        (native/".lake/combined-solution/OPICAStep4").mkdir(parents=True)
        spath="/work/.lake/combined-solution:"+np+":/supplier"
        sextra=((so,"/supplier"),)
        for m in ("ImportGuard","MainClosedBridge"):
            p=self.inside("combined_"+m,native,["/opt/lean/bin/lean","-DwarningAsError=true","--root=/work","-o",".lake/combined-solution/OPICAStep4/"+m+".olean","OPICAStep4/"+m+".lean"],lean_path=spath,extra=sextra)
            if m=="ImportGuard":need("OPICA20_NEW_NAMES_ABSENT" in p.read_text(),"missing guard")
        audit=native/".lake/CombinedAudit.lean";audit.write_text("import OPICAStep4.MainClosedBridge\n"+"\n".join("#print axioms "+n for n in mr)+"\n")
        log=self.inside("combined_named_axioms",native,["/opt/lean/bin/lean","-DwarningAsError=true",".lake/CombinedAudit.lean"],lean_path=spath,extra=sextra).read_text()
        self.report["combined_axioms"]=axiom_report(log,mr);self.save()
        self.inside("combined_stock_replay",native,["/opt/lean/bin/leanchecker","--fresh","--verbose","OPICAStep4.MainClosedBridge"],lean_path=spath,extra=sextra,writable=False)
        sexp=self.export("combined_solution_50",native,"OPICAStep4.MainClosedBridge",rr,lean_path=spath,extra=sextra)
        cfg=json_file(REPO/"comparator.json");cfg.update(challenge_module="OPICAStep4.CombinedChallenge",solution_module="OPICAStep4.MainClosedBridge",theorem_names=mr)
        self.judge("combined_comparator_50",cfg,cexp,sexp)
        native_integrity();need(all(digest(native/n)==s for n,s in initial.items()),"native staged bytes drift")
        self.report["combined_50"]="PASS_SAME_V437_PIN_CANDIDATE_ONLY";self.save()
    def execute(self):
        try:
            self.prepare()
            ch,sol=self.supplier()
            if self.args.include_native=="true":self.native(ch,sol)
            need(scope(self.args.head)==self.report["source"],"final source changed")
            need(inventory_digest(REPO/"src")==self.report["source_file_inventory"]==inventory_digest(sol/"src"),"supplier source bytes changed")
            need(inventory_digest(sol/".lake/build/lib/lean")==self.report["supplier_object_inventory"],"supplier object bytes changed")
            need({n:inventory_digest(p) for n,p in self.dep_roots.items()}==self.report["dependency_object_inventories"],"dependency objects changed")
            need(inventory_digest(self.rt/"lib/lean")==self.report["runtime_library_inventory"],"runtime library bytes changed")
            need(all(digest(self.rt/"bin"/n)==h for n,h in self.report["runtime_binaries"].items()),"runtime binary drift")
            for p in self.exports.iterdir():
                stage=self.report["stages"][p.stem]
                need(digest(p)==stage["stdout_sha256"],"export changed: "+p.name)
            self.report["status"]="PASS_NEW_CANDIDATE_SCOPE_ONLY"
            code=0
        except BaseException as e:
            self.report.update(status="INCOMPLETE_OR_REJECTED",failure=str(e)[:2000],exception_type=type(e).__name__)
            code=2
        finally:self.save()
        print(json.dumps({k:self.report[k] for k in ("status","supplier_38","formal_conjectures_35","combined_50","proof_acceptance","C1","independent_step4")}),flush=True)
        return code
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--head",required=True);a.add_argument("--include-native",choices=("true","false"),required=True);a.add_argument("--output",type=P,required=True)
    sys.exit(Campaign(a.parse_args()).execute())
