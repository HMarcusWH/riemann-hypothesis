"""Source identity, exact selected roots and fail-closed Comparator receipts."""
from __future__ import annotations
import json, pathlib, subprocess, sys, re
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PIN = json.loads((HERE / "SOURCE_PIN.json").read_text())
ALLOWED = {"propext", "Quot.sound", "Classical.choice"}
KERNELS = {"Lean paranoid", "nanoda", "Lean default"}
PUBLIC = ["riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re", "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive"]
FC = ["RiemannHypothesis.riemannHypothesis", "GRH.generalized_riemann_hypothesis"]
class Refused(RuntimeError): pass
def need(ok, why):
    if not ok: raise Refused(why)
def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=120).strip()
def json_file(path): return json.loads(path.read_text())
def roots():
    inv = json_file(HERE/"native_bridge/SELECTED_ROOT_INVENTORY.json")
    rr, mr = inv["ordered_roots"], inv["mathematical_roots"]
    need(len(rr) == len(set(rr)) == 50 and len(mr) == len(set(mr)) == 17, "root inventory count")
    need(rr[:38] == (REPO/"export-targets.txt").read_text().split() and mr[:5] == PUBLIC, "supplier root drift")
    need(rr[38:] == mr[5:] and [x for x in rr[:38] if x in mr] == PUBLIC, "combined root drift")
    ff = (REPO/"comparator/formal-conjectures-export-targets.txt").read_text().split()
    need(len(ff)==len(set(ff))==35 and [x for x in ff if x not in FC]==[x for x in rr[:38] if x not in PUBLIC], "FC root drift")
    return rr, mr, ff
def scope(head):
    need(re.fullmatch("[0-9a-f]{40}",head) is not None and git(REPO,"rev-parse","HEAD")==head,"wrong head")
    need(PIN["schema"]=="OPICA_V437_QUALIFICATION_CANDIDATE_V1" and PIN["proof_acceptance"] is False and PIN["independent_native_step4"]=="OPEN", "claim firewall")
    need(git(REPO,"rev-parse",PIN["base_commit"]+"^{tree}")==PIN["base_tree"],"wrong base")
    need(not git(REPO,"diff","--name-only","HEAD"),"modified tracked source")
    need(not git(REPO,"ls-files","--others","--exclude-standard","--","src","comparator","verification/opica-v437"),"untracked proof source")
    need(not git(REPO,"ls-files","--others","--ignored","--exclude-standard","--","src","comparator","verification/opica-v437"),"ignored proof source")
    allowed = {".github/workflows/opica-v437-qualification.yml"} | {"verification/opica-v437/"+n for n in ("SOURCE_PIN.json","README.md","source.py","test_source.py","verify.py","Ingress.lean","CombinedChallenge.lean","smoke.py","RUNNER.md")}
    bridge = git(REPO,"ls-tree","-r","--name-only",head,"verification/opica-v437/native_bridge").splitlines()
    allowed |= set(bridge)
    changed = [x.split("\t") for x in git(REPO,"diff","--name-status","--no-renames",PIN["base_commit"],head).splitlines()]
    need(all(len(x)==2 and x[0]=="A" for x in changed) and {x[1] for x in changed}==allowed, "non-additive or unexpected source delta")
    need(git(REPO,"rev-parse",head+":src")==PIN["src_tree"] and git(REPO,"rev-parse",head+":comparator")==PIN["comparator_tree"],"supplier source drift")
    need(git(REPO,"rev-parse",head+":verification/opica-v437/native_bridge")==PIN["bridge_tree"],"historical bridge changed")
    need((REPO/"lean-toolchain").read_text().strip()==PIN["toolchain"],"compiler drift")
    packages=json_file(REPO/"lake-manifest.json")["packages"]
    need(len(packages)==9 and [p["rev"] for p in packages if p["name"]=="mathlib"]==[PIN["mathlib"]],"dependency drift")
    rr,mr,ff=roots()
    for path, names in ((REPO/"comparator.json",PUBLIC),(REPO/"comparator/formal-conjectures.json",FC)):
        config=json_file(path)
        need(config["theorem_names"]==names and set(config["permitted_axioms"])==ALLOWED and not config.get("definition_names"),"Comparator config drift")
        need(set(config["external_kernels"])==KERNELS-{"Lean default"},"kernel scope changed")
    return {"status":"SOURCE_ONLY_PASS","head":head,"tree":git(REPO,"rev-parse","HEAD^{tree}"),"roots":[len(rr[:38]),len(rr),len(ff)],"proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN"}
def accepted(d, config):
    need(d.get("sandboxed") is True and d.get("judgement")=="accepted","unsandboxed or rejected Comparator")
    q=d["report"]
    for k in ("compare_statements","check_axioms"):
        need(q[k]["judgement"]=="success","missing "+k)
    need(set(q["kernel_reports"])==KERNELS and all(x["judgement"]=="success" for x in q["kernel_reports"].values()),"missing or rejected kernel")
    cfg=q["config"]
    for k in ("challenge_module","solution_module","theorem_names","permitted_axioms","external_kernels"):
        need(cfg.get(k)==config[k],"reported config differs: "+k)
    need(set(cfg["permitted_axioms"])==ALLOWED and not cfg.get("definition_names"),"axiom/definition policy drift")
    return True
def axiom_report(text, names):
    need(not re.search(r"\bsorryAx\b|\berror:",text),"compiler error or forbidden axiom")
    matches=re.findall(r"(?m)^'([^'\n]+)' (?:depends on axioms:\s*\[([^\]]*)\]|does not depend on any axioms)[ \t]*(?=\n|$)",text)
    got={}
    for name,raw in matches:
        a=[x.strip() for x in raw.split(",") if x.strip()]
        need(name in names and name not in got and len(a)==len(set(a)) and set(a)<=ALLOWED,"bad axiom report: "+name)
        got[name]=a
    need(set(got)==set(names),"missing axiom reports")
    return got
if __name__=="__main__":
    print(json.dumps(scope(sys.argv[1]),sort_keys=True))
