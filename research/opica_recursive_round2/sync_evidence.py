"""Read-only exact-head ledger for all tracked repair branches and pinned evidence.
Actions metadata is not a mathematical proof; missing data is never success.
"""
import argparse
from r2_common import *
from harvest import api,pages,run_identity
NATIVE="HMarcusWH/zeta-23-lean"
EXTERNAL="HMarcusWH/riemann-hypothesis"
TRACKED={NATIVE:[311,312,313,314,315,316],EXTERNAL:[9,12,13,14]}
EXACT_JOB_CLASS={
 "source-contract":"FORMAL_VALIDITY_GATE","source-admission":"FORMAL_VALIDITY_GATE",
 "source-controls":"FORMAL_VALIDITY_GATE","source-and-finite-controls":"REGRESSION_GATE",
 "native-compiler":"FORMAL_VALIDITY_GATE","native-candidate":"FORMAL_VALIDITY_GATE",
 "independent-candidate":"FORMAL_VALIDITY_GATE","historical-type-export":"RESEARCH_PRODUCING_CHECK",
 "cross-pin-type-comparison":"FORMAL_VALIDITY_GATE","review-old-receipts":"REGRESSION_GATE",
 "scope":"FORMAL_VALIDITY_GATE","dual-review":"FORMAL_VALIDITY_GATE",
 "canonical-candidate":"RESEARCH_PRODUCING_CHECK","canonical-review":"REGRESSION_GATE",
 "verified-export-mining":"RESEARCH_PRODUCING_CHECK","principal-arithmetic-cut":"RESEARCH_PRODUCING_CHECK",
 "native-typed-search":"RESEARCH_PRODUCING_CHECK","research-join":"RESEARCH_PRODUCING_CHECK",
 "native-math-cut":"FORMAL_VALIDITY_GATE","native-search":"RESEARCH_PRODUCING_CHECK",
 "mixed-validation":"FORMAL_VALIDITY_GATE","harvest":"REGRESSION_GATE",
 "packet":"RESEARCH_PRODUCING_CHECK","evidence-sync":"REGRESSION_GATE","final-evidence-sync":"REGRESSION_GATE"}
def classify(name):
    if name in EXACT_JOB_CLASS:return EXACT_JOB_CLASS[name]
    if name.startswith("principal-supplier ("):return "RESEARCH_PRODUCING_CHECK"
    if name.startswith("Round4 / "):return "FORMAL_VALIDITY_GATE"
    return "UNCLASSIFIED_REQUIRES_REVIEW"
def disposition(run,jobs):
    if run["status"]!="completed" or any(j["status"]!="completed" for j in jobs):return "RUNNING_OR_QUEUED"
    if run["conclusion"]!="success":return "TERMINAL_NON_SUCCESS"
    if not jobs or any(j["conclusion"] not in ("success","skipped") for j in jobs):return "INCOMPLETE_OR_NON_SUCCESS_JOB"
    return "METADATA_GREEN_RECEIPTS_REQUIRE_REVIEW"
def one_run(repository,head,run):
    spec={"repository":repository,"run":run["id"],"head":head,"workflow":run["path"].split("@")[0]}
    run_identity(run,spec)
    ep="repos/"+repository+"/actions/runs/"+str(run["id"])
    attempts=[]
    for attempt in range(1,run["run_attempt"]+1):
        need(attempt<=20,"Run-attempt budget exhausted")
        jobs=pages(ep+"/attempts/"+str(attempt)+"/jobs","jobs")
        need(all(j["run_id"]==run["id"] and j.get("run_attempt",attempt)==attempt for j in jobs),"Job identity differs")
        rows=[]
        for j in jobs:
            rows.append({**{k:j.get(k) for k in ("id","name","status","conclusion","html_url","started_at","completed_at")},"classification":classify(j["name"]),"steps":[{k:s.get(k) for k in ("name","number","status","conclusion")} for s in j.get("steps",[])],"content_disposition":"JOB_METADATA_ONLY_REVIEW_NAMED_RECEIPTS"})
        attempts.append({"attempt":attempt,"jobs":rows})
    artifacts=pages(ep+"/artifacts","artifacts")
    need(all(a["workflow_run"]["id"]==run["id"] for a in artifacts),"Artifact producer differs")
    return {**{k:run.get(k) for k in ("id","name","path","event","head_sha","status","conclusion","run_attempt","html_url")},"attempts":attempts,"disposition":disposition(run,attempts[-1]["jobs"]),"artifacts":[{**{k:a.get(k) for k in ("id","name","size_in_bytes","digest","expired")},"authority":"PUBLISHED_ARTIFACT_METADATA_NOT_REHASHED"} for a in artifacts]}
def collect(out,repo):
    out.mkdir(parents=True,exist_ok=False)
    records=[];historical=[];errors=[]
    for repository,numbers in TRACKED.items():
        for n in numbers:
            key=repository+"#"+str(n)
            try:
                pr=api("repos/"+repository+"/pulls/"+str(n))
                head=pr["head"]["sha"]
                need(pr["head"]["repo"]["full_name"]==repository and pr["number"]==n and re.fullmatch(r"[0-9a-f]{40}",head),"Unexpected PR identity")
                commit=api("repos/"+repository+"/git/commits/"+head);need(commit["sha"]==head,"Commit identity")
                row={"key":key,"repository":repository,"pr":n,"head":head,"tree":commit["tree"]["sha"],"state":pr["state"],"merged":pr["merged"],"draft":pr["draft"],"branch":pr["head"]["ref"],"url":pr["html_url"],"runs":[]}
                records.append(row)
                for run in pages("repos/"+repository+"/actions/runs?head_sha="+head,"workflow_runs"):
                    try:row["runs"].append(one_run(repository,head,run))
                    except Exception as ex:errors.append({"key":key,"run":run["id"],"reason":str(ex)[:1000]})
                row["disposition"]="NO_RUN_OBSERVED" if not row["runs"] else "LIVE_HEAD_WORKFLOWS_RECORDED"
            except Exception as ex:errors.append({"key":key,"reason":str(ex)[:1000]})
    for spec in LOCK["runs"]:
        try:
            run=api("repos/"+spec["repository"]+"/actions/runs/"+str(spec["run"]))
            run_identity(run,spec)
            historical.append({"key":spec["key"],"repository":spec["repository"],"pr":spec["pr"],"pinned_head":spec["head"],"run":one_run(spec["repository"],spec["head"],run)})
        except Exception as ex:errors.append({"key":spec["key"],"run":spec["run"],"reason":str(ex)[:1000]})
    doc={"schema":"OPICA_CROSS_REPOSITORY_EVIDENCE_LEDGER_V1","controller":controller_scope(repo),"tracked_prs":records,"frozen_producers":historical,"unavailable":errors,"status":"METADATA_HARVEST_COMPLETE" if not errors else "METADATA_HARVEST_PARTIAL","authority":"JOB_AND_ARTIFACT_METADATA_ONLY; EXACT RECEIPTS AND HUMAN POST_GREEN REVIEW STILL REQUIRED",**CLAIMS}
    write(out/"EVIDENCE_LEDGER.json",doc)
    lines=["# Cross-repository evidence ledger","","No theorem promotion. Every live head is kept separate from prior successful receipts.","","| Repository / PR | Exact head | Tree | Run dispositions |","|---|---|---|---|"]
    for p in records:
        runs="; ".join(str(x["id"])+": "+x["disposition"] for x in p["runs"]) or "NO_RUN_OBSERVED"
        lines.append("| "+p["key"]+" | "+p["head"]+" | "+p["tree"]+" | "+runs+" |")
    lines+=["","## Frozen producer runs"]
    for h in historical:lines.append("- "+h["key"]+": "+str(h["run"]["id"])+" — "+h["run"]["disposition"])
    lines+=["","## Unavailable / incomplete observations"]
    for x in errors:lines.append("- "+json.dumps(x,ensure_ascii=False))
    lines+=["","RH, C1, independent Step 4 remain OPEN. This ledger cannot substitute for a kernel receipt."]
    (out/"EVIDENCE_LEDGER.md").write_text("\n".join(lines)+"\n")
    write(out/"LEDGER_SHA256.json",{p.name:filehash(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(doc["status"],"PRs",len(records),"frozen producers",len(historical),"unavailable",len(errors))

def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();collect(a.out,a.repo)
if __name__=="__main__":main()
