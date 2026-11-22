#!/usr/bin/env python3
"""Preserve bounded diagnostic evidence; never turn it into proof acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.head):
        raise ValueError('A complete lowercase commit SHA is required')
    if args.work.is_symlink():
        raise ValueError('The diagnostic work directory cannot be a symlink')
    args.work.mkdir(parents=True, exist_ok=True)
    work = args.work.resolve()
    selected = set()
    excluded = []

    def select(path):
        relative = path.relative_to(work)
        current = work
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise ValueError('Symlink in diagnostic evidence path: ' + str(relative))
        if not path.exists():
            return
        if not path.resolve().is_relative_to(work):
            raise ValueError('Diagnostic evidence escaped the work directory')
        if not path.is_file():
            return
        if path.stat().st_size > 150 * 1024 ** 2:
            excluded.append({'path': str(relative), 'bytes': path.stat().st_size,
                             'reason': 'member size limit'})
            return
        selected.add(path)

    for relative in (
        'RUNNER_RESOURCES.json', 'mounted-store-verified.json',
        'proof-store.sqfs.receipt.json',
        'native/integration/NATIVE_COMMON_PIN_BUILD.json',
    ):
        path = work / relative
        select(path)
    for relative in ('native/bootstrap-logs', 'import-diagnostic'):
        root = work / relative
        if not root.exists():
            continue
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                excluded.append({'path': str(path.relative_to(work)), 'reason': 'symlink'})
                continue
            if not path.is_file():
                continue
            retain = path.suffix in {'.json', '.jsonl', '.log', '.txt', '.lean', '.olean', '.ilean'}
            retain = retain or path.name.endswith(('.olean.private', '.olean.server'))
            if not retain:
                excluded.append({'path': str(path.relative_to(work)),
                                 'bytes': path.stat().st_size,
                                 'reason': 'unselected binary'})
                continue
            select(path)
    rows = []
    archive = work / 'import-diagnostic-evidence.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for path in sorted(selected):
            content = path.read_bytes()
            relative = str(path.relative_to(work))
            target.writestr(relative, content)
            rows.append({'path': relative, 'bytes': len(content),
                         'sha256': hashlib.sha256(content).hexdigest()})
        manifest = {
            'schema': 'OPICA_IMPORT_PHASE_DIAGNOSTIC_EVIDENCE_V1',
            'head': args.head, 'files': rows, 'excluded': excluded,
            'scope': 'Stock import resource and phase observations only',
            'proof_acceptance': False, 'step4': 'OPEN', 'c1': 'OPEN', 'rh': 'OPEN',
            'modular_30_stage_gate': 'NOT_RUN_BY_THIS_WORKFLOW',
            'independent_7_stage_gate': 'NOT_RUN_BY_THIS_WORKFLOW',
            'retention_limits': [
                'Original supplier store and all native dependency object bytes are not archived.',
                'Compiled diagnostic executable is omitted; its build/source identities are retained.',
                'No guard or closed theorem is constructed by the diagnostic.',
            ],
        }
        target.writestr('EVIDENCE_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(archive) as check:
        for row in rows:
            content = check.read(row['path'])
            if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                raise ValueError('Evidence archive readback mismatch')
    print(json.dumps({'archive': str(archive), 'files': len(rows),
                      'bytes': archive.stat().st_size,
                      'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'proof_acceptance': False}))


if __name__ == '__main__':
    main()
