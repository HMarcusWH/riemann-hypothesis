#!/usr/bin/env python3
"""Read-only fork PR identity boundary. Never fetches, executes or merges PR code."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

FORK = "HMarcusWH/riemann-hypothesis"
HEX = re.compile(r"[0-9a-f]{40}\Z")
class Refused(ValueError): pass

def require(ok, why):
    if not ok: raise Refused(why)

def validate(event: dict, *, expected_head: str, expected_base: str, require_internal=True) -> dict:
    require(isinstance(event, dict), "Event object required")
    require(event.get("repository",{}).get("full_name")==FORK, "Not this fork repository")
    pr=event.get("pull_request")
    require(isinstance(pr,dict), "PR payload required")
    head=pr.get("head",{});base=pr.get("base",{})
    number=pr.get("number") or event.get("number")
    require(type(number)==int and 1<=number<=10000000, "Invalid PR number")
    require(head.get("repo",{}).get("full_name") == FORK if require_internal else
            bool(head.get("repo",{}).get("full_name")), "Unreviewed cross-repository PR source")
    require(base.get("repo",{}).get("full_name")==FORK, "PR base is not fork")
    require(isinstance(expected_head,str) and HEX.fullmatch(expected_head), "Exact head SHA required")
    require(isinstance(expected_base,str) and HEX.fullmatch(expected_base), "Exact base SHA required")
    require(head.get("sha")==expected_head, "Stale/changed PR head")
    require(base.get("sha")==expected_base, "Stale/changed PR base")
    require(pr.get("state")=="open" and not pr.get("merged",False), "Not an open PR")
    require(pr.get("base",{}).get("ref") in {"main","research/opica-community-first-contact-20261122"},
            "Unreviewed base ref")
    return {
      "schema":"OPICA_FORK_PR_IDENTITY_V1",
      "repository":FORK,"pr_number":number,
      "head":expected_head,"base":expected_base,
      "origin":head.get("repo",{}).get("full_name"),
      "status":"SOURCE_IDENTITY_OBSERVED_ONLY",
      "candidate_merge_sha":None,
      "trusted_merge_verified":False,
      "proof_acceptance":False,"rh":"OPEN"
    }

def validate_merge_record(item, *, expected_head, expected_base):
    """Only a typed *read-only* parent assertion, never a trusted Git merge."""
    require(isinstance(item,dict),"Git commit record required")
    require(HEX.fullmatch(item.get("sha","")) is not None,"Merge commit SHA missing")
    parents=item.get("parents")
    require(isinstance(parents,list) and len(parents)==2,"Two explicit parents required")
    require([x.get("sha") for x in parents]==[expected_base,expected_head],
            "Git merge parents not exact expected base/head order")
    return {"merge":item["sha"],"parent_observed":True,"proof_acceptance":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--event",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--base",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): p.error("Output must not exist")
    outcome=validate(json.loads(args.event.read_text()),expected_head=args.head,expected_base=args.base)
    args.output.write_text(json.dumps(outcome,indent=2)+"\n")
    print(json.dumps({"status":outcome["status"],"proof_acceptance":False}))
if __name__=="__main__":
    main()
