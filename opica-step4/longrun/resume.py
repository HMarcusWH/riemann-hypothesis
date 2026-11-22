#!/usr/bin/env python3
"""Review a sealed checkpoint and fail closed on attempts to skip proof stages.

Cross-job shortcut/resumption is explicitly NOT authorized by this version.
A fresh full kernel proof run must be selected separately after this audit.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from checkpoint import verify


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",type=Path,required=True)
    p.add_argument("--seal",type=Path,required=True)
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--skip-completed",action="store_true")
    args=p.parse_args()
    r=verify(args.work,args.seal,args.expected_sha256,args.head)
    r.update(status="FRESH_ORIGINAL_KERNEL_REPLAY_REQUIRED",
             proof_acceptance=False,resume_authorized=False,
             requested_skip_completed=args.skip_completed,
             execution_action="NOT_RUN")
    print(json.dumps(r,indent=2))
    # This command is never a proof-stage runner or shortcut.
    return 2 if args.skip_completed else 0


if __name__=="__main__":
    raise SystemExit(main())
