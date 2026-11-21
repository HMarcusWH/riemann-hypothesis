#!/usr/bin/env python3
"""Collect small audit products, never the large proof or swap files."""
import argparse,hashlib,json,pathlib,zipfile,os
p=argparse.ArgumentParser();p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--head',required=True);a=p.parse_args()
a.work.mkdir(parents=True,exist_ok=True)
selected=[]
for n in ['RUNNER_RESOURCES.json','mounted-store-verified.json','proof-store.sqfs.receipt.json']:
 f=a.work/n
 if f.is_file():selected.append(f)
for folder in ['native/bootstrap-logs','verification','independent-verification']:
 root=a.work/folder
 if root.exists():
  for f in root.rglob('*'):
   if not f.is_file() or f.is_symlink():continue
   if f.suffix in ['.ndjson','.sqfs','.ir','.c','.o','.a','.so']:continue
   if f.stat().st_size>150*1024**2:continue
   selected.append(f)
f=a.work/'native/integration/NATIVE_COMMON_PIN_BUILD.json'
if f.is_file():selected.append(f)
checker=a.work/'independent-checker'
if checker.exists():
 for f in checker.iterdir():
  if f.is_file() and f.suffix in ['.json','.log'] and f.stat().st_size<=150*1024**2:
   selected.append(f)
selected=sorted(set(selected));rows=[]
with zipfile.ZipFile(a.work/'evidence.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in selected:
  data=f.read_bytes();name=str(f.relative_to(a.work));z.writestr(name,data)
  rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 dispositions={}
 for label,relative in [('modular','verification/MODULAR_GATE_RECEIPT.json'),('independent','independent-verification/INDEPENDENT_RECEIPT.json')]:
  f=a.work/relative
  if f.is_file():
   data=json.loads(f.read_text());dispositions[label]={'status':data.get('status','UNKNOWN'),'path':relative,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
  else:dispositions[label]={'status':'NOT_RUN_OR_NO_RECEIPT','path':relative}
 receipt={'head':a.head,'files':rows,'dispositions':dispositions,'scope':'The exact common-pin theorem requires the modular proof and claim gate plus the independent complete selected-proof-closure check to PASS. Resource/bootstrap/control passes alone do not close C1. The original Round19 25-stage procedure retains its separate unexecuted status.'}
 z.writestr('EVIDENCE_MANIFEST.json',json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'evidence_files':len(rows),'archive_bytes':(a.work/'evidence.zip').stat().st_size,'archive_sha256':hashlib.sha256((a.work/'evidence.zip').read_bytes()).hexdigest()}))
