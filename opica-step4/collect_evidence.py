#!/usr/bin/env python3
"""Collect small audit products, never the large proof or swap files."""
import argparse,hashlib,json,pathlib,zipfile,os
p=argparse.ArgumentParser();p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--head',required=True);a=p.parse_args()
a.work.mkdir(parents=True,exist_ok=True)
selected=[]
for n in ['RUNNER_RESOURCES.json','mounted-store-verified.json','proof-store.sqfs.receipt.json']:
 f=a.work/n
 if f.is_file():selected.append(f)
for folder in ['native/bootstrap-logs','verification']:
 root=a.work/folder
 if root.exists():
  for f in root.rglob('*'):
   if not f.is_file() or f.is_symlink():continue
   if f.suffix in ['.ndjson','.sqfs','.ir','.c','.o','.a','.so']:continue
   if f.stat().st_size>150*1024**2:continue
   selected.append(f)
f=a.work/'native/integration/NATIVE_COMMON_PIN_BUILD.json'
if f.is_file():selected.append(f)
selected=sorted(set(selected));rows=[]
with zipfile.ZipFile(a.work/'evidence.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in selected:
  data=f.read_bytes();name=str(f.relative_to(a.work));z.writestr(name,data)
  rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 receipt={'head':a.head,'files':rows,'scope':'Only the terminal modular gate receipt, when present and PASS, determines exact theorem validation. Resource/bootstrap passes alone do not close C1.'}
 z.writestr('EVIDENCE_MANIFEST.json',json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'evidence_files':len(rows),'archive_bytes':(a.work/'evidence.zip').stat().st_size,'archive_sha256':hashlib.sha256((a.work/'evidence.zip').read_bytes()).hexdigest()}))
