"""Fresh native compiler inventory and bounded R2 research execution."""
import argparse,sys,shutil
from pathlib import Path
from r2_common import *
from search import explore,select,api
from external_inventory import load_external, principal_goals, external_frontier

NS="Zeta23.OPICARound6.NextSearch."
DEF="Zeta23.OPICARound6.PrimeDeficit."
C1="Zeta23.OPICARound4.ArithmeticFrontier."
MAIN_GOALS=[(C1+"CofinalMomentSliceVanishingErrorBounds","Zeta23.OPICARound4.ArithmeticFrontier.MomentSlices"),
(NS+"PositiveRawSubpower",NS+"SourceEnergies"),(NS+"NegativeRawSubpower",NS+"SourceEnergies"),(NS+"OnePolarityRawSubpower",NS+"SourceEnergies"),
(DEF+"LargePrimeDeficitSubpower",DEF+"Source"),(DEF+"MissingPrimeDeficitToLiteralGBridge",DEF+"Source")]
NAMED=["C1Named","PositiveNamed","NegativeNamed","OnePolarityNamed","DeficitNamed","DeficitBridgeNamed","UniformRemainder","SamePolicyOpposedSupply","JointCofinalOpposedSupply"]
BASE_MODULES=[NS+"BipolarTransfer",DEF+"Source","Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure","Zeta23.RHRC.OpicaComposition.Audit","Zeta23.RHRC.OpicaRound3AtlasExport"]
class Campaign:
    def __init__(self,repo,epoch,harvest,out):
        self.repo=repo.resolve();self.epoch=read(epoch);self.harvest=harvest.resolve();self.out=out.resolve()
        check_pin(self.repo,self.epoch["native"]);need(self.epoch["proof_acceptance"] is False,"Invalid research epoch")
        self.out.mkdir(parents=True,exist_ok=False);self.work=self.out/"work";self.work.mkdir()
        self.env=compiler_env();self.failures=[];self.compiles=[];self.rows=[];self.goals=[];self.idx=0
        sys.path.insert(0,str(self.repo))
        self.eh=api()[0]
    def run(self,args,label,seconds=1800):
        r=command(args,self.repo,self.env,self.work/(label+".log"),seconds=seconds)
        self.compiles.append({"label":label,**r})
        return r["status"]=="PASS"
    def build(self,modules,label,seconds=5400):
        return self.run(["lake","build",*sorted(set(modules))],label,seconds)
    def compile(self,path,label=None,seconds=600):
        return self.run([self.lean,"--root="+str(self.work),"-DwarningAsError=true","-o",path.with_suffix(".olean"),path],label or path.stem,seconds)
    def driver(self,label,imports,body,seconds=600):
        path=self.work/(label+".lean")
        path.write_text("\n".join("import "+source_name(x) for x in sorted(set(imports)))+"\n"+body+"\n")
        return self.compile(path,label,seconds),self.work/(label+".log"),path
    def setup(self):
        need(self.build(BASE_MODULES,"base-build"),"Mandatory native build failed")
        self.lean=subprocess.check_output(["lake","env","which","lean"],cwd=self.repo,env=self.env,text=True).strip()
        lp=subprocess.check_output(["lake","env","printenv","LEAN_PATH"],cwd=self.repo,env=self.env,text=True).strip()
        self.env["LEAN_PATH"]=str(self.work)+os.pathsep+lp
        for src,stem in [(HERE/"Export.lean","OPICAR2Export"),(HERE/"NativeTargets.lean","OPICAR2Targets")]:
            target=self.work/(stem+".lean");shutil.copyfile(src,target)
            need(self.compile(target),"R2 compiler driver failed: "+stem)
        self.adapter_modules=[]
        for stem in ("Common","Native","Energy"):
            p=self.work/("OPICAExtraction"+stem+".lean");shutil.copyfile(R1/(stem+".lean"),p)
            if not self.compile(p):
                self.failures.append({"stage":"R1_ADAPTER_RECOMPILE","module":p.stem});break
            self.adapter_modules.append(p.stem)
    def inventory(self):
        from research.RHRC.integration.opica_composition.qualification import frozen_atlas
        atlas=frozen_atlas(self.repo)
        requests={r["declaration"]:{ "module":r["module"],"expected_type_sha256":r["type_sha256"],"cohort":"FROZEN_462_ATLAS"} for r in atlas}
        policy=read(self.repo/"research/RHRC/integration/opica_round6/bipolar_transfer/POLICY.json")
        for n in policy["roots"]:requests[n]={"module":NS+"BipolarTransfer","cohort":"BIPOLAR_16"}
        for n,m in [(NS+"rawPositiveEnergy_le_full_components",NS+"SourceEnergies"),(NS+"rawPositiveEnergy_le_of_component_budgets",NS+"SourceEnergies"),(DEF+"positiveDeficitEnergy_nonneg",DEF+"Source"),("OPICAR2.onePolarity_of_samePolicyOpposedSupply","OPICAR2Targets"),("OPICAR2.onePolarity_of_jointCofinalOpposedSupply","OPICAR2Targets")]:
            requests.setdefault(n,{"module":m,"cohort":"ARITHMETIC_SUPPORT"})
        for n in ("even","odd","tendsto"):
            requests.setdefault(C1+"cofinal_moment_slice_bounds_of_"+n,{"module":"Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure","cohort":"C1_CONSUMER_SUPPORT"})
        if "OPICAExtractionNative" in self.adapter_modules:
            requests["OPICAExtractionR1.native_windows_of_ramp_windows"]={"module":"OPICAExtractionNative","cohort":"REBUILT_R1_ADAPTER"}
        if "OPICAExtractionEnergy" in self.adapter_modules:
            for n in ("native_energy_of_ramp_windows","native_energy_of_literal_windows","native_c1_of_ramp_windows_of_direct_bridge"):
                requests["OPICAExtractionR1."+n]={"module":"OPICAExtractionEnergy","cohort":"REBUILT_R1_ADAPTER"}
        historical=self.epoch["historical_roots"]
        modules=self.epoch["historical_modules"]
        if historical:
            if self.build(modules,"historical-overlay-build"):
                for n in historical:requests.setdefault(n,{"module":None,"cohort":"HISTORICAL_PORT_CANDIDATE"})
            else:self.failures.append({"stage":"HISTORICAL_OVERLAY_BUILD","roots":historical})
        need(len(requests)<=BUDGET["atlas_roots"],"Reviewed inventory budget exceeded")
        # Build frozen source modules, not every repository workflow/target.
        modules_to_build=sorted({r["module"] for r in requests.values() if r["module"] and r["module"].startswith("Zeta23.")})
        missing=set()
        def build_chunk(chunk,label):
            if self.build(chunk,label,3600):return
            if len(chunk)==1:missing.update(chunk);return
            mid=len(chunk)//2
            build_chunk(chunk[:mid],label+"-a");build_chunk(chunk[mid:],label+"-b")
        for i in range(0,len(modules_to_build),24):build_chunk(modules_to_build[i:i+24],"atlas-build-"+str(i))
        pending=[]
        for n,r in sorted(requests.items()):
            if forbidden(n):self.failures.append({"declaration":n,"status":"EXCLUDED_ENDPOINT"});continue
            if r["module"] in missing:self.failures.append({"declaration":n,"status":"MODULE_BUILD_FAILED"});continue
            pending.append((n,r))
        def export(batch):
            self.idx+=1;label="Atlas"+str(self.idx)
            imports={"OPICAR2Export"}
            for _,r in batch:
                if r["module"]:imports.add(r["module"])
                else:imports.update(modules)
            body="\n".join("run_cmd OPICAR2Export.emitRow "+chr(96)+source_name(n) for n,_ in batch)
            ok,log,_=self.driver(label,imports,body,seconds=1200)
            if not ok:
                if len(batch)>1:
                    middle=len(batch)//2;export(batch[:middle]);export(batch[middle:])
                else:self.failures.append({"declaration":batch[0][0],"status":"COMPILER_EXPORT_FAILED","log":log.name})
                return
            rows=marker_rows(log,"OPICA3_ATLAS");closures=marker_rows(log,"OPICA_R2_CLOSURE");proofs=marker_rows(log,"OPICA_RETRIEVAL_PROOFS")
            need(len(rows)==len(closures)==len(proofs)==len(batch),"Compiler inventory marker population")
            for (name,spec),row,c,ps in zip(batch,rows,closures,proofs):
                need(row["declaration"]==c["name"]==name,"Compiler root identity drift")
                need(not spec["module"] or spec["module"]==row["module"],"Compiler source module drift")
                h=self.eh(row["type_expression"])
                if (not c["is_prop"] or not set(row["axioms"])<=ALLOWED or any(forbidden(n) for n in c["dependencies"]) or any(forbidden(n) for n in row["type_constants"])):
                    self.failures.append({"declaration":name,"status":"NON_PROOF_OR_CONTAMINATED"});continue
                if spec.get("expected_type_sha256") and h!=spec["expected_type_sha256"]:
                    self.failures.append({"declaration":name,"status":"FROZEN_TYPE_DRIFT","observed":h});continue
                self.rows.append(compact_dependency_row({**row,"world":"NATIVE_COMPILER","source_module":row["module"],"type_sha256":h,"proof_constants":ps,"dependencies":c["dependencies"],"cohort":spec["cohort"],"admission":"FRESH_NATIVE_COMPILER_RESEARCH_NOT_PRODUCTION"},self.out))
        for start in range(0,len(pending),BUDGET["atlas_batch"]):export(pending[start:start+BUDGET["atlas_batch"]])
        return len(requests)
    def goal(self,label,declaration,module):
        self.idx+=1;stem="Target"+str(self.idx)
        ok,log,_=self.driver(stem,[module,"OPICAR2Export"],"run_cmd Zeta23.RHRC.OpicaComposition.exportTarget "+chr(96)+source_name(declaration)+' "value"\nrun_cmd Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants '+chr(96)+declaration+' "value"')
        need(ok,"Target export failed: "+declaration)
        e=marker_rows(log,"OPICA_TARGET");p=marker_rows(log,"OPICA_RETRIEVAL_PROOFS")
        need(len(e)==len(p)==1,"Target marker mismatch")
        h=self.eh(e[0]);return {"id":digest([declaration,h]),"label":label,"declaration":declaration,"module":module,"expression":e[0],"type_sha256":h,"proof_constants":p[0]}
    def register(self,row,slot):
        if row["world"]!="NATIVE_COMPILER":return external_frontier(row,slot)
        # Stable identity uses the exact supplier type and original binder slot.
        key=digest([row["declaration"],row["type_sha256"],slot]);stem="OPICAR2Frontier"+key[:24];name=stem+".goal"
        path=self.work/(stem+".lean")
        if not path.exists():
            ok,log,_=self.driver(stem,[row["module"],"OPICAR2Export"],"run_cmd OPICAR2Export.registerPremise "+chr(96)+source_name(row["declaration"])+" "+str(slot)+" "+chr(96)+name)
            need(ok,"Compiler premise registration rejected")
        else:log=self.work/(stem+".log")
        e=marker_rows(log,"OPICA_TARGET");p=marker_rows(log,"OPICA_RETRIEVAL_PROOFS");meta=marker_rows(log,"OPICA_R2_PREMISE")
        need(len(e)==len(p)==len(meta)==1 and meta[0]["owner"]==row["declaration"] and meta[0]["slot"]==slot and meta[0]["name"]==name,"Premise registration identity drift")
        return {"id":key,"label":row["declaration"]+" premise "+str(slot),"declaration":name,"module":stem,"expression":e[0],"type_sha256":self.eh(e[0]),"proof_constants":p[0],"origin":{**meta[0],"source_module":row["module"],"world":"NATIVE_COMPILER"}}
    def campaign(self):
        self.setup();requested=self.inventory()
        roots=[]
        for n,m in MAIN_GOALS+[("OPICAR2."+n,"OPICAR2Targets") for n in NAMED]:
            roots.append(self.goal(n,n,m))
        if "OPICAExtractionNative" in self.adapter_modules:
            roots.append(self.goal("NativeLiteralWindows","OPICAExtractionR1.NativeLiteralWindows","OPICAExtractionNative"))
        if "OPICAExtractionEnergy" in self.adapter_modules:
            for n in ("NativeEnergySubpower","DirectEnergyToC1"):
                roots.append(self.goal(n,"OPICAExtractionR1."+n,"OPICAExtractionEnergy"))
        ext,rejected=load_external(self.harvest)
        roots.extend(principal_goals(ext))
        inventory={"schema":"OPICA_R2_QUALIFIED_RESEARCH_INVENTORY_V2","epoch":self.epoch,"requested_native_roots":requested,"native_rows":self.rows,"external_research_rows":ext,"exclusions":self.failures+rejected,"production_admission":"NOT_ESTABLISHED",**CLAIMS}
        write(self.out/"inventory.json",inventory)
        graph=explore(roots,self.rows+ext,self.register)
        write(self.out/"graph.json",graph)
        for mode,cap in (("native",BUDGET["attempts_native"]),("mixed",BUDGET["attempts_mixed"])):
            selected,omitted=select(graph,mode,cap)
            write(self.out/(mode+"-candidates.json"),{"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":mode,"native":self.epoch["native"],"original_head":R1_PIN["original"]["head"],"selected":selected,"omitted_budget":omitted,**CLAIMS})
        write(self.out/"compiler.json",{"status":"COMPILER_RESEARCH_INVENTORY_EXPORTED","compiles":self.compiles,"failures":self.failures,**CLAIMS})
        print(json.dumps({"native_rows":len(self.rows),"external_research_rows":len(ext),"goals":len(graph["nodes"]),"queries":len(graph["queries"]),**CLAIMS}))
def main():
    p=argparse.ArgumentParser()
    for k in ("repo","epoch","harvest","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    c=Campaign(a.repo,a.epoch,a.harvest,a.out)
    try:c.campaign()
    except BaseException as ex:
        if not (c.out/"compiler.json").exists():write(c.out/"compiler.json",{"status":"INCOMPLETE_EXECUTION","error":str(ex)[:1800],"compiles":c.compiles,"failures":c.failures,**CLAIMS})
        raise
if __name__=="__main__":main()
