#!/usr/bin/env python3
"""Bound the disposable standard GitHub VM; never touches a persistent host."""
import argparse,json,os,pathlib,shutil,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--work',type=pathlib.Path,required=True);a=p.parse_args()
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
 raise SystemExit('This preparation is restricted to the disposable GitHub-hosted runner')
a.work.mkdir(parents=True,exist_ok=True)
def run(args):
 r=subprocess.run(args,check=True,capture_output=True,text=True)
 return {'argv':args,'stdout':r.stdout,'stderr':r.stderr,'exit_code':r.returncode}
report={'status':'RUNNING','scope':'Resource preparation only; no mathematical claim','before':{'disk':shutil.disk_usage(a.work)._asdict(),'memory':pathlib.Path('/proc/meminfo').read_text()}}
try:
 # Only unrelated preinstalled SDKs in this explicitly disposable job image.
 report['reclaimed_preinstalled_sdks']=run(['sudo','rm','-rf','--','/usr/local/lib/android','/usr/share/dotnet'])
 report['map_limit']=run(['sudo','sysctl','-w','vm.max_map_count=1048576'])
 free=shutil.disk_usage(a.work).free
 reserve=(40+15+5)*1024**3
 swap_gib=min(40,int(free/1024**3)-60)
 if swap_gib<32:raise RuntimeError(f'Need at least92GiB before swap; have{free/1024**3:.2f}GiB')
 swap_bytes=swap_gib*1024**3
 report['swap_gib']=swap_gib
 swap=a.work/'opica.swap'
 if swap.exists():raise RuntimeError('Swap output already exists')
 report['allocate_swap']=run(['sudo','fallocate','-l',str(swap_bytes),str(swap)])
 report['swap_permissions']=run(['sudo','chmod','600',str(swap)])
 report['format_swap']=run(['sudo','mkswap',str(swap)])
 report['enable_swap']=run(['sudo','swapon',str(swap)])
 report['after']={'disk':shutil.disk_usage(a.work)._asdict(),'memory':pathlib.Path('/proc/meminfo').read_text(),'swap':run(['swapon','--show','--bytes'])}
 report['status']='PASS'
finally:
 (a.work/'RUNNER_RESOURCES.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
