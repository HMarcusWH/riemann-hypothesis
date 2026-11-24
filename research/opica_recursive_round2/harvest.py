"""Collect exact Actions job/receipt evidence. Missing access/CI is OPEN, never PASS."""
import argparse,json,os,re,stat,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
from r2_common import *

def api(endpoint):
    p=subprocess.run(["gh","api",endpoint],capture_output=True,timeout=90,check=True)
    return json.loads(p.stdout)
def pages(endpoint,key):
    result=[]
    for page in range(1,21):
        d=api(endpoint+("&" if "?" in endpoint else "?")+"per_page=100&page="+str(page))
        rows=d[key];result+=rows
        if len(rows)<100:
            need(len(result)==d["total_count"],"Incomplete or changing Actions population")
            return result
    raise RuntimeError("Actions pagination budget exhausted")
def run_identity(run,spec):
    need(run["id"]==spec["run"] and run["head_sha"]==spec["head"],"Wrong run/head")
    need(run["repository"]["full_name"]==spec["repository"] and run["head_repository"]["full_name"]==spec["repository"],"Wrong run repository")
    need(run["path"].split("@")[0]==spec["workflow"],"Wrong workflow")
    need(type(run["run_attempt"]) is int and run["run_attempt"]>0,"Missing attempt")
    if "attempt" in spec:need(run["run_attempt"]==spec["attempt"],"Pinned producer attempt differs")
def successful_job(record,name):
    return sum(j["name"]==name and j["status"]=="completed" and j["conclusion"]=="success" for j in record["jobs"])==1
def safe_members(z):
    names=set();total=0
    for i in z.infolist():
        n=i.filename;p=PurePosixPath(n)
        need(n not in names and not p.is_absolute() and ".." not in p.parts and "\\" not in n,"Unsafe artifact member")
        need(not stat.S_ISLNK(i.external_attr>>16),"Artifact symlink refused")
        names.add(n);total+=i.file_size
        need(total<=768<<20 and len(names)<=20000,"Expanded artifact budget")
    return names
def artifact(record,prefix,wanted,out,expected_id=None,expected_digest=None,expected_name=None):
    spec=record["spec"];run=record["run"];attempt=run["run_attempt"]
    endpoint="repos/"+spec["repository"]+"/actions/runs/"+str(spec["run"])+"/artifacts"
    rows=pages(endpoint,"artifacts")
    matches=[a for a in rows if a["name"].startswith(prefix) and not a["expired"]]
    if expected_name is not None:matches=[a for a in matches if a["name"]==expected_name]
    if expected_id is not None:matches=[a for a in matches if a["id"]==expected_id]
    else:
        suffixed=[a for a in matches if a["name"].endswith("-"+str(spec["run"])+"-"+str(attempt))]
        if suffixed:matches=suffixed
        else:need(attempt==1,"Unsuffixed retry artifact requires explicit pinned identity")
    need(len(matches)==1,"Missing/ambiguous artifact "+prefix)
    a=matches[0];expected=a.get("digest","")
    need(a["workflow_run"]["id"]==spec["run"],"Artifact producer run differs")
    if expected_digest is not None:need(expected=="sha256:"+expected_digest,"Pinned artifact digest differs")
    need(re.fullmatch(r"sha256:[0-9a-f]{64}",expected) is not None,"Artifact digest unavailable")
    need(0<a["size_in_bytes"]<=256<<20,"Artifact compressed budget")
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"artifact.zip"
        with p.open("xb") as f:subprocess.run(["gh","api","repos/"+spec["repository"]+"/actions/artifacts/"+str(a["id"])+"/zip"],stdout=f,stderr=subprocess.PIPE,check=True,timeout=300)
        need(p.stat().st_size<=256<<20 and filehash(p)==expected.split(":")[1],"Artifact ZIP digest differs")
        entries={}
        with zipfile.ZipFile(p) as z:
            names=safe_members(z)
            for leaf in wanted:
                hits=[n for n in names if PurePosixPath(n).name==leaf]
                need(len(hits)==1,"Missing/ambiguous artifact member "+leaf)
                dest=out/leaf
                with z.open(hits[0]) as f,dest.open("xb") as d:
                    while b:=f.read(1<<20):d.write(b)
                entries[leaf]={"sha256":filehash(dest),"bytes":dest.stat().st_size}
    return {"artifact_id":a["id"],"artifact_name":a["name"],"zip_sha256":expected[7:],"run":spec["run"],"attempt":attempt,"head":spec["head"],"entries":entries}
def saved_window_disposition(folder,receipt,*,historical):
    # A green research job is not a successful proof attempt.
    spec=LOCK["evidence"]["saved_window"]
    files=("mixed-candidate-manifest.json","validation.json","ActualTypes.log")
    for leaf in files:
        need(filehash(folder/leaf)==receipt["entries"][leaf]["sha256"],"Saved-window member differs")
    manifest=read(folder/files[0]);validation=read(folder/files[1])
    need(manifest["proof_acceptance"] is False and manifest["mode"]=="mixed" and len(manifest["selected"])==1,"Saved candidate scope")
    c=manifest["selected"][0]
    need(c["id"]==spec["candidate"] and c["target"]["declaration"]=="OPICAExtractionR1.Combined.ConditionalNativeWindows","Saved candidate identity")
    need(validation["schema"]=="OPICA_R1_CANDIDATE_VALIDATION_V1" and validation["mode"]=="mixed" and validation["proof_acceptance"] is False and validation["native"]==manifest["native"] and validation["original"]==manifest["original_head"],"Saved validation scope")
    need(len(validation["results"])==1 and validation["results"][0]["id"]==c["id"],"Saved result population")
    row=validation["results"][0]
    need(row["stages"]["actual_types"]["status"]=="PASS" and row["stages"]["actual_types"]["log_sha256"]==filehash(folder/files[2]),"Saved actual-types log binding")
    actual=marker_rows(folder/files[2],"OPICA_TARGET")
    expected=[c["expected_expression"]]+[s["type_expression"] for s in c["sources"]]
    need(len(actual)==len(expected),"Saved type population")
    if str(R1) not in sys.path:sys.path.insert(0,str(R1))
    from candidate_validate import fingerprint
    comparisons=[{"declaration":n,"actual_nodes":len(a["nodes"]),"expected_nodes":len(e["nodes"]),
                  "raw_equal":a==e,"fingerprint_equal":fingerprint(a)==fingerprint(e)}
                 for n,a,e in zip([c["target"]["declaration"]]+[s["declaration"] for s in c["sources"]],actual,expected)]
    if historical:
        need(receipt["artifact_id"]==spec["artifact"] and receipt["zip_sha256"]==spec["archive_sha256"],"Pinned saved diagnostic differs")
        need(row["status"]=="ADAPTER_REQUIRED" and not comparisons[0]["fingerprint_equal"] and all(x["raw_equal"] for x in comparisons[1:]),"Frozen saved-window disposition changed")
    return {"status":row["status"],"candidate":c["id"],"type_comparisons":comparisons,"historical_diagnostic":historical,"stages":row["stages"],"local_pin_proof_only":row["status"]=="PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED","cross_pin_definition_equivalence":"NOT_ESTABLISHED","proof_acceptance":False}

def expanded_readiness(receipts):
    required=LOCK["expanded_readiness"]["required"]
    need(required==["historical","original","principal"],"Expanded campaign readiness contract differs")
    missing=[k for k in required if k not in receipts]
    return {"status":"WAITING_FOR_UPSTREAM_EVIDENCE" if missing else "READY_FOR_FRESH_EXPANDED_RESEARCH","required":required,"missing":missing,"production_acceptance":False}

def collect(out):
    out.mkdir(parents=True,exist_ok=False)
    reports={};receipts={};errors=[]
    for spec in LOCK["runs"]:
        key=spec["key"];rec={"spec":spec,"run":None,"jobs":[],"all_workflows":[],"status":"INCOMPLETE"}
        reports[key]=rec
        try:
            prefix="repos/"+spec["repository"]+"/actions/runs/"
            run=api(prefix+str(spec["run"]));run_identity(run,spec)
            rec["run"]={k:run[k] for k in ("id","head_sha","path","status","conclusion","event","run_attempt")}
            rec["jobs"]=pages(prefix+str(spec["run"])+"/attempts/"+str(run["run_attempt"])+"/jobs","jobs")
            allruns=pages("repos/"+spec["repository"]+"/actions/runs?head_sha="+spec["head"],"workflow_runs")
            need(all(w["head_sha"]==spec["head"] for w in allruns),"Unexpected head in run listing")
            for w in allruns:
                row={k:w.get(k) for k in ("id","name","head_sha","status","conclusion","event","run_attempt","path")}
                try:
                    jobs=pages(prefix+str(w["id"])+"/attempts/"+str(w["run_attempt"])+"/jobs","jobs")
                    row["jobs"]=[{k:j.get(k) for k in ("id","name","status","conclusion","steps")} for j in jobs]
                except Exception as ex:row["job_inventory_error"]=str(ex)[:500]
                rec["all_workflows"].append(row)
            pr=api("repos/"+spec["repository"]+"/pulls/"+str(spec["pr"]))
            rec["live_pr_head"]=pr["head"]["sha"];rec["merged"]=pr.get("merged",False)
            rec["status"]="EXACT_RUN_OBSERVED"
        except Exception as ex:
            rec["error"]=str(ex)[:1200];errors.append({"lane":key,"reason":rec["error"]})
    def take(key,job,prefix,wanted,label,pinned=None):
        try:
            rec=reports[key]
            need(rec["status"]=="EXACT_RUN_OBSERVED" and successful_job(rec,job),"Producer job not verified successful")
            producer=next(j for j in rec["jobs"] if j["name"]==job and j["status"]=="completed" and j["conclusion"]=="success")
            if pinned and "job" in pinned:need(producer["id"]==pinned["job"],"Pinned producer job differs")
            receipts[label]=artifact(rec,prefix,wanted,out/"inputs"/label,
                                     expected_id=pinned.get("artifact") if pinned else None,
                                     expected_digest=pinned.get("archive_sha256") if pinned else None,
                                     expected_name=pinned.get("artifact_name") if pinned else None)
            receipts[label]["producer_job"]=producer["id"]
        except Exception as ex:errors.append({"lane":label,"reason":str(ex)[:1000]})
    take("external-repaired","verified-export-mining","extraction-original-proof-graph-",["original-dependencies.json"],"original",LOCK["evidence"]["mining"])
    take("external","principal-arithmetic-cut","extraction-principal-",["principal-receipt.json"],"principal",LOCK["evidence"]["old_principal"])
    take("external-repaired","saved-window-validation","extraction-saved-window-validation-",["mixed-candidate-manifest.json","validation.json","ActualTypes.log"],"saved-window-diagnostic",LOCK["evidence"]["saved_window"])
    take("saved-window-repaired","saved-window-validation","extraction-saved-window-validation-",["mixed-candidate-manifest.json","validation.json","ActualTypes.log"],"saved-window-repaired")
    take("external-repaired","research-join","extraction-research-join-",["extraction-research-join.json","research-feedback.json"],"r1-predecessor-join")
    take("energy-repaired","native-typed-search","extraction-native-",["energy-receipt.json","native-retrieval.json","energy-independent-type.log"],"energy")
    take("energy-repaired","research-join","extraction-research-join-",["extraction-research-join.json","research-feedback.json"],"r1-join")
    take("historical-review","review-old-receipts","opica-support-reviewed-old-comparison-",["reviewed-old-cross-pin-type-comparison.json"],"historical")
    take("canonical","canonical-candidate","opica-successor-canonical-review-",["receipt.json","generated-state.patch"],"canonical",LOCK["evidence"]["canonical"])
    take("registration","canonical-candidate","registration-canonical-",["receipt.json","generated-state.patch"],"registration",LOCK["evidence"]["registration"])
    window_results={}
    for label in ("saved-window-diagnostic","saved-window-repaired"):
        if label in receipts:
            try:window_results[label]=saved_window_disposition(out/"inputs"/label,receipts[label],historical=label.endswith("diagnostic"))
            except Exception as ex:errors.append({"lane":label+"-disposition","reason":str(ex)[:1000]})
    report={"schema":"OPICA_R2_AUTHENTICATED_HARVEST_V1","saved_window_dispositions":window_results,"runs":reports,"artifact_receipts":receipts,"unavailable":errors,"expanded_search_readiness":expanded_readiness(receipts),**CLAIMS}
    write(out/"harvest.json",report)
    print(json.dumps({"runs_observed":sum(r["status"]=="EXACT_RUN_OBSERVED" for r in reports.values()),"artifacts":sorted(receipts),"unavailable":len(errors),"expanded_search_readiness":report["expanded_search_readiness"],**CLAIMS}))
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--require-expanded",action="store_true");a=p.parse_args()
    report=collect(a.out)
    if a.require_expanded:need(not report["expanded_search_readiness"]["missing"],"WAITING_FOR_UPSTREAM_EVIDENCE: "+",".join(report["expanded_search_readiness"]["missing"]))
if __name__=="__main__":main()
