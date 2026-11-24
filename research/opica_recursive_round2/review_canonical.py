"""Review an authenticated generated-state candidate without committing it."""
import argparse,subprocess,tempfile
from pathlib import Path
from r2_common import *

def review(repo,folder,output):
    repo=repo.resolve();folder=folder.resolve();r=read(folder/"receipt.json")
    head,tree=r["source_head"],r["source_tree"]
    need(git(repo,"rev-parse",head+"^{tree}")==tree,"Candidate tree differs")
    need(r["status"]=="REVIEW_ONLY_GENERATED_STATE" and r["proof_acceptance"] is False,"Not a completed review-only artifact")
    patch=folder/"generated-state.patch";need(filehash(patch)==r["patch_sha256"],"Patch digest differs")
    before,after=r["before_sha256"],r["after_write_sha256"]
    need(len(before)==81 and set(before)==set(after) and after==r["after_check_sha256"],"81-product write/check identity differs")
    frozen=set(r["frozen_git_oids"]);changed=set(r["changed_paths"])
    need(len(frozen)==4 and len(changed)==r["changed_count"] and not frozen&changed,"Protected product changed")
    need(changed=={p for p in before if before[p]!=after[p]},"Declared changed list differs")
    manifest_path="research/RHRC/integration/opica_round4/BUILD_MANIFEST.json"
    manifest=json.loads(git(repo,"show",head+":"+manifest_path))
    need(set(before)=={x["path"] for x in manifest["generated"]},"Original generated inventory differs")
    for p,v in r["frozen_git_oids"].items():need(git(repo,"rev-parse",head+":"+p)==v,"Frozen Git object differs")
    with tempfile.TemporaryDirectory() as td:
        work=Path(td)/"checkout"
        subprocess.run(["git","-C",str(repo),"worktree","add","--detach",str(work),head],check=True,timeout=300)
        try:
            need({p:filehash(work/p) for p in before}==before,"Before hashes differ")
            subprocess.run(["git","-C",str(work),"apply","--check",str(patch)],check=True,timeout=300)
            subprocess.run(["git","-C",str(work),"apply",str(patch)],check=True,timeout=300)
            names=git(work,"diff","--name-status","--no-renames","HEAD").splitlines()
            need(all(n.startswith("M\t") for n in names) and {n[2:] for n in names}==changed,"Patch changed non-authorized paths")
            need(not git(work,"ls-files","--others","--exclude-standard"),"Patch added untracked paths")
            need({p:filehash(work/p) for p in after}==after,"After hashes differ")
        finally:subprocess.run(["git","-C",str(repo),"worktree","remove","--force",str(work)],check=True,timeout=300)
    write(output,{"status":"PATCH_BYTES_AND_PATHS_VERIFIED_REVIEW_REQUIRED","head":head,"tree":tree,"changed_paths":sorted(changed),"patch_sha256":r["patch_sha256"],**CLAIMS})
def main():
    p=argparse.ArgumentParser()
    for k in ("repo","candidate","output"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();review(a.repo,a.candidate,a.output)
if __name__=="__main__":main()
