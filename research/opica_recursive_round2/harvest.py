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
def artifact(record,prefix,wanted,out):
    spec=record["spec"];run=record["run"];attempt=run["run_attempt"]
    endpoint="repos/"+spec["repository"]+"/actions/runs/"+str(spec["run"])+"/artifacts"
    rows=pages(endpoint,"artifacts")
    matches=[a for a in rows if a["name"].startswith(prefix) and not a["expired"]]
    # R1 artifacts predate attempt-suffixed naming. Refuse ambiguity, do not guess.
    need(len(matches)==1,"Missing/ambiguous artifact "+prefix)
    a=matches[0];expected=a.get("digest","")
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
    def take(key,job,prefix,wanted,label):
        try:
            rec=reports[key]
            need(rec["status"]=="EXACT_RUN_OBSERVED" and successful_job(rec,job),"Producer job not verified successful")
            receipts[label]=artifact(rec,prefix,wanted,out/"inputs"/label)
        except Exception as ex:errors.append({"lane":label,"reason":str(ex)[:1000]})
    take("external","verified-export-mining","extraction-original-proof-graph-",["original-dependencies.json"],"original")
    take("external","principal-arithmetic-cut","extraction-principal-",["principal-receipt.json"],"principal")
    take("external","research-join","extraction-research-join-",["extraction-research-join.json","research-feedback.json"],"r1-join")
    take("historical","cross-pin-type-comparison","opica-support-cross-pin-comparison-",["cross-pin-type-comparison.json"],"historical")
    take("canonical","canonical-candidate","opica-successor-canonical-review-",["receipt.json","generated-state.patch"],"canonical")
    take("registration","canonical-candidate","registration-canonical-",["receipt.json","generated-state.patch"],"registration")
    report={"schema":"OPICA_R2_AUTHENTICATED_HARVEST_V1","runs":reports,"artifact_receipts":receipts,"unavailable":errors,**CLAIMS}
    write(out/"harvest.json",report)
    print(json.dumps({"runs_observed":sum(r["status"]=="EXACT_RUN_OBSERVED" for r in reports.values()),"artifacts":sorted(receipts),"unavailable":len(errors),**CLAIMS}))
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);a=p.parse_args();collect(a.out)
if __name__=="__main__":main()
