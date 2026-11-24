"""Bounded real stock-kernel/Comparator execution test. Never touches supplier proof."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from types import SimpleNamespace
from source import roots, need, json_file, accepted, ALLOWED, KERNELS
from verify import Campaign, write, digest
def run(output, head):
    c=Campaign(SimpleNamespace(output=output,head=head,include_native="false"))
    c.report["schema"]="OPICA_V437_REAL_SMOKE_V1"
    c.report["scope"]="TINY_NON_SUPPLIER_FIXTURES_ONLY"
    c.save()
    try:
        c.install_runtime()
        from verify import inventory_digest
        c.report["runtime_library_inventory"]=inventory_digest(c.rt/"lib/lean")
        c.save()
        c.deps=c.out/"empty-dependencies";c.deps.mkdir()
        rr,mr,_=roots()
        base=[x for x in rr[:38] if x not in mr]
        selected=[*base,"OPICAV437Smoke.claim"]
        need(len(selected)==34,"fixture inventory")
        def fixture(name,body):
            p=c.out/name;p.mkdir();(p/".lake/packages").mkdir(parents=True)
            (p/"lean-toolchain").write_text("leanprover/lean4:v4.37.0-rc1\n")
            (p/"lakefile.toml").write_text('name = "Smoke"\n[[lean_lib]]\nname = "Fixture"\n')
            write(p/"lake-manifest.json",{"version":"1.3.0","packagesDir":".lake/packages","packages":[],"name":"Smoke","lakeDir":".lake","fixedToolchain":False})
            (p/"Fixture.lean").write_text("import Lean\nnamespace OPICAV437Smoke\n"+body+"\nend OPICAV437Smoke\n")
            c.inside(name+"_build",p,["/opt/lean/bin/lake","--no-cache","build","Fixture"],timeout=180)
            lp=c.path(name+"_path",p)
            return p,lp
        ch,cp=fixture("challenge","theorem claim : True := by sorry")
        good,gp=fixture("good","theorem claim : True := True.intro")
        bad,bp=fixture("bad_axiom","theorem claim : True := by sorry")
        wrong,wp=fixture("wrong_type","theorem claim : True ∧ True := ⟨True.intro, True.intro⟩")
        # Verify namespaces are different and source and dependencies are mounted read-only.
        host_net=os.readlink("/proc/self/ns/net")
        namespace=c.inside("sandbox_net",good,["/usr/bin/readlink","/proc/self/ns/net"],timeout=30).read_text().strip()
        need(namespace!=host_net,"network namespace not isolated")
        c.inside("readonly_controls",good,["/bin/sh","-c","if (printf x >> /work/Fixture.lean) 2>/dev/null; then exit 1; fi; if (touch /work/.lake/packages/forbidden) 2>/dev/null; then exit 1; fi"],timeout=30)
        c.inside("tiny_stock_replay",good,["/opt/lean/bin/leanchecker","--fresh","--verbose","Fixture"],lean_path=gp,writable=False,timeout=180)
        ce=c.export("tiny_challenge",ch,"Fixture",selected,lean_path=cp)
        se=c.export("tiny_good",good,"Fixture",selected,lean_path=gp)
        be=c.export("tiny_sorry",bad,"Fixture",selected,lean_path=bp)
        we=c.export("tiny_wrong",wrong,"Fixture",selected,lean_path=wp)
        cfg={"challenge_module":"Fixture","solution_module":"Fixture","theorem_names":["OPICAV437Smoke.claim"],"permitted_axioms":["propext","Quot.sound","Classical.choice"],"external_kernels":{"Lean paranoid":["leanchecker-paranoid","--silent","--from-export"],"nanoda":["nanoda_bin"]}}
        c.judge("tiny_real_three_kernels",cfg,ce,se)
        def negative(name,sol,step):
            config=c.ev/(name+".config.json");write(config,cfg)
            path=c.run(name,[c.rt/"bin/lake","comparator","--json","--config",config,"--challenge-from-export",ce,"--solution-from-export",sol],c.out/"judge",timeout=180,expected=1)
            d=json_file(path);q=d["report"]
            need(d["sandboxed"] is True and d["judgement"]=="failure" and q[step]["judgement"]=="failure","negative control did not fail the intended gate")
            need(set(q["kernel_reports"])==KERNELS and all(x["judgement"]=="skipped" for x in q["kernel_reports"].values()),"negative control reached kernels")
            if step=="check_axioms":
                need(q["compare_statements"]["judgement"]=="success" and "sorryAx" in json.dumps(q["check_axioms"]),"forbidden axiom not identified")
            c.report["stages"][name]["actual_negative_control"]="PASS_EXPECTED_REJECTION";c.save()
        negative("reject_sorry",be,"check_axioms")
        negative("reject_wrong_type",we,"compare_statements")
        c.report["status"]="PASS_REAL_EXECUTION_SMOKE_ONLY";code=0
    except BaseException as exc:
        c.report.update(status="INCOMPLETE_OR_REJECTED",failure=str(exc)[:2000],exception_type=type(exc).__name__);code=2
    finally:c.save()
    print(json.dumps({"status":c.report["status"],"scope":c.report["scope"],"proof_acceptance":False,"supplier_38":"NOT_RUN","combined_50":"NOT_RUN"}),flush=True)
    return code
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--head",required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.output,a.head))
