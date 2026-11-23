#!/usr/bin/env python3
"""Read-only preflight of a dedicated, explicitly provisioned original-proof host.

Unlike prepare_runner.py this never deletes SDKs, changes sysctls, or allocates
swap. The maintainer must provision a disposable long-run image independently.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

REPO = "HMarcusWH/riemann-hypothesis"
MARKER = Path("/etc/opica/original-433-longrun.json")
GIB = 1024**3

def need(ok, message):
    if not ok:
        raise RuntimeError(message)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--work",required=True,type=Path)
    p.add_argument("--head",required=True)
    a=p.parse_args()
    output=a.work/"RUNNER_RESOURCES.json"
    report={"schema":"OPICA_ORIGINAL_LONGRUN_PREFLIGHT_V1","status":"INCOMPLETE",
            "requested_head":a.head,"profile":"LONGRUN_ORIGINAL","proof_acceptance":False,
            "RH":"OPEN","C1":"OPEN","Step4":"OPEN"}
    code=2
    try:
        need(os.environ.get("GITHUB_ACTIONS")=="true" and
             os.environ.get("RUNNER_ENVIRONMENT")=="self-hosted" and
             os.environ.get("GITHUB_REPOSITORY")==REPO and
             os.environ.get("GITHUB_REF")=="refs/heads/research/opica-step4-combined-gate-20261121" and
             os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch",
             "Manual selected self-hosted original-proof workflow required")
        need(re.fullmatch(r"[0-9a-f]{40}",a.head) and os.environ.get("GITHUB_SHA")==a.head,
             "Exact reviewed head required")
        supplier=Path(__file__).resolve().parents[2]
        got=subprocess.check_output(["git","-C",str(supplier),"rev-parse","HEAD"],text=True).strip()
        need(got==a.head,"Exact checkout differs")
        need(a.work.resolve().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()) and
             a.work.is_dir() and not a.work.is_symlink() and not output.exists(),
             "Fresh bounded output on runner temp required")
        runner=os.environ["RUNNER_NAME"]
        need(re.fullmatch(r"opica-original-433-[A-Za-z0-9_-]+",runner),"Wrong dedicated runner name")
        info=MARKER.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not (stat.S_IMODE(info.st_mode)&0o022)
             and info.st_size<=4096,"Root-owned non-writable ephemeral runner marker required")
        marker=json.loads(MARKER.read_text())
        need(marker=={"schema":"OPICA_ORIGINAL_433_EPHEMERAL_V1","runner_name":runner,"ephemeral":True},
             "Invalid runner provisioning marker")
        cpu=len(os.sched_getaffinity(0))
        ram=int(next(l.split()[1] for l in Path("/proc/meminfo").read_text().splitlines()
                     if l.startswith("MemTotal:")))//1024
        fs=os.statvfs(a.work)
        free=fs.f_bavail*fs.f_frsize
        maps=int(Path("/proc/sys/vm/max_map_count").read_text())
        tools=("git","python3","mksquashfs","zstd","losetup","mount","sudo")
        need(all(shutil.which(t) for t in tools),"Provisioned tools absent")
        need(cpu>=8 and ram>=120000 and free>=250*GIB and fs.f_favail>=400000 and maps>=1048576,
             "Provisioned CPU/RAM/disk/inodes/map limits insufficient")
        need(subprocess.run(["sudo","-n","true"],check=False,timeout=10).returncode==0,
             "Required bounded mount privileges unavailable")
        report.update(status="PASS_RESOURCE_PREFLIGHT_ONLY",cpu_count=cpu,ram_mib=ram,
                      free_bytes=free,free_inodes=fs.f_favail,max_map_count=maps,
                      compile_timeout_seconds=14400,workflow_timeout_minutes=1200,
                      checked_head=got)
        code=0
    except Exception as exc:
        report.update(status="BLOCKED_RESOURCE_PREFLIGHT",reason=str(exc)[:1000])
    finally:
        if output.exists():
            raise SystemExit("Refusing to overwrite resource receipt")
        output.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(report,sort_keys=True),flush=True)
    return code

if __name__=="__main__":
    sys.exit(main())
