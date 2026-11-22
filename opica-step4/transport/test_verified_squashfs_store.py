#!/usr/bin/env python3
"""Byte transport and rejection controls; these tests do not validate Lean proofs."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import zstandard as zstd

from verified_squashfs_store import PREFIX, Pin, build_store, read_manifest

TOOLS = Path(__file__).parent / 'squashfs-tools-4.6.1' / 'squashfs-tools'
MKSQUASHFS = os.environ.get('MKSQUASHFS') or shutil.which('mksquashfs') or str(TOOLS / 'mksquashfs')
UNSQUASHFS = os.environ.get('UNSQUASHFS') or shutil.which('unsquashfs') or str(TOOLS / 'unsquashfs')


def fixture(entries=None, *, manifest_entries=None, suffix=b''):
    import tarfile
    if entries is None:
        entries=[('A.olean',b'proof bytes\0'*8192,'file'),('A.ilean',b'interface','file')]
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w',format=tarfile.GNU_FORMAT) as t:
        for name,data,kind in entries:
            info=tarfile.TarInfo(PREFIX+name)
            if kind=='symlink':
                info.type=tarfile.SYMTYPE; info.linkname='/etc/passwd'
            elif kind=='dir': info.type=tarfile.DIRTYPE
            else: info.size=len(data)
            t.addfile(info,io.BytesIO(data) if kind=='file' else None)
    archive=zstd.ZstdCompressor().compress(raw.getvalue()+suffix)
    if manifest_entries is None: manifest_entries=entries
    manifest=''.join(hashlib.sha256(data).hexdigest()+'  '+PREFIX+name+'\n'
                     for name,data,kind in manifest_entries if kind=='file').encode()
    pin=Pin('TRANSPORT_FIXTURE',len(archive),hashlib.sha256(archive).hexdigest(),
            len(manifest),hashlib.sha256(manifest).hexdigest(),
            sum(kind=='file' for _,_,kind in manifest_entries),
            sum(len(data) for _,data,kind in manifest_entries if kind=='file'))
    return archive,manifest,pin


class TransportTests(unittest.TestCase):
    def build(self, fixture_value, directory, **kwargs):
        archive,manifest,pin=fixture_value
        return build_store(io.BytesIO(archive),manifest,pin,Path(directory)/'proof.sqfs',
            mksquashfs=MKSQUASHFS,processors=1,memory_mb=16,min_free_bytes=0,
            image_max_bytes=1024**2,**kwargs)

    def rejected(self, value, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception): self.build(value,tmp,**kwargs)
            self.assertFalse((Path(tmp)/'proof.sqfs').exists())
            self.assertFalse((Path(tmp)/'proof.sqfs.receipt.json').exists())

    def test_actual_roundtrip_and_nonproof_receipt(self):
        names=['A.olean','A.ilean','Long.'+'a'*170+'.olean']
        entries=[(n,(n.encode()+b'\0')*1000,'file') for n in names]
        value=fixture(entries)
        with tempfile.TemporaryDirectory() as tmp:
            receipt=self.build(value,tmp)
            self.assertFalse(receipt['proof_validity_established'])
            self.assertFalse(receipt['production_supplier'])
            output=Path(tmp)/'unpacked'
            p=subprocess.run([UNSQUASHFS,'-no-progress','-processors','1','-d',str(output),str(Path(tmp)/'proof.sqfs')],capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual({str(p.relative_to(output)):p.read_bytes() for p in output.rglob('*') if p.is_file()},
                             {n:d for n,d,k in entries})

    def test_actual_64k_multiblock_tail_and_fragment_roundtrip(self):
        block_size = 65536
        first = bytes(range(256)) * 256
        second = hashlib.shake_256(b'OPICA64K second block').digest(4096) * 16
        large = first + second + first[::-1] + hashlib.shake_256(b'OPICA64K tail').digest(731)
        small = b'small fragment\0' + hashlib.shake_256(b'OPICA64K fragment').digest(997)
        self.assertEqual(len(large), 3 * block_size + 731)
        self.assertLess(len(small), block_size)
        entries = [('MultiBlock.olean', large, 'file'), ('Small.ilean', small, 'file')]
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self.build(fixture(entries), tmp)
            self.assertFalse(receipt['proof_validity_established'])
            self.assertFalse(receipt['production_supplier'])
            image = Path(tmp) / 'proof.sqfs'
            info = subprocess.run([UNSQUASHFS, '-s', str(image)], capture_output=True, text=True)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertRegex(info.stdout, r'(?m)^Block size 65536\s*$')
            output = Path(tmp) / 'unpacked'
            unpack = subprocess.run([UNSQUASHFS, '-no-progress', '-processors', '1',
                                     '-d', str(output), str(image)], capture_output=True)
            self.assertEqual(unpack.returncode, 0, unpack.stderr)
            self.assertEqual({str(p.relative_to(output)): p.read_bytes()
                              for p in output.rglob('*') if p.is_file()},
                             {name: data for name, data, _ in entries})
            print(json.dumps({'control': 'OPICA24_64K_MULTIBLOCK_ROUNDTRIP',
                              'status': 'PASS', 'block_size_bytes': block_size,
                              'stock_unsquashfs_summary': info.stdout,
                              'image_sha256': receipt['image_sha256'],
                              'image_bytes': receipt['image_bytes'],
                              'readback_files': [{'path': name, 'bytes': (output / name).stat().st_size,
                                                  'sha256': hashlib.sha256((output / name).read_bytes()).hexdigest()}
                                                 for name, _, _ in entries],
                              'proof_validity_established': False}), flush=True)

    def test_source_archive_hash_mismatch(self):
        a,m,p=fixture(); p=Pin(**{**p.__dict__,'archive_sha256':'0'*64})
        self.rejected((a,m,p))

    def test_manifest_hash_mismatch(self):
        a,m,p=fixture(); self.rejected((a,m+b'junk',p))

    def test_member_content_mismatch(self):
        self.rejected(fixture([('A.olean',b'evil','file')],manifest_entries=[('A.olean',b'good','file')]))

    def test_member_missing(self):
        self.rejected(fixture([('A.olean',b'one','file')],manifest_entries=[('A.olean',b'one','file'),('B.olean',b'two','file')]))

    def test_duplicate_member(self):
        x=('A.olean',b'one','file'); self.rejected(fixture([x,x],manifest_entries=[x]))

    def test_symlink(self):
        self.rejected(fixture([('A.olean',b'','symlink')],manifest_entries=[('A.olean',b'','file')]))

    def test_path_traversal(self):
        self.rejected(fixture([('../escape.olean',b'bad','file')]))

    def test_oversize_member(self): self.rejected(fixture(),member_max_bytes=16)

    def test_explicit_window_bound(self): self.rejected(fixture(),max_window_bytes=1024)

    def test_backend_window_units_are_bytes(self):
        a,_,_=fixture()
        window=zstd.get_frame_parameters(a).window_size
        self.assertGreater(window,1024)
        with self.assertRaises(zstd.ZstdError):
            with zstd.ZstdDecompressor(max_window_size=1024).stream_reader(io.BytesIO(a)) as f:
                f.read(1024)

    def test_wrong_total_size(self):
        a,m,p=fixture(); p=Pin(**{**p.__dict__,'expanded_bytes':p.expanded_bytes+1}); self.rejected((a,m,p))

    def test_truncated_source(self):
        a,m,p=fixture(); self.rejected((a[:-4],m,p))

    def test_nonzero_tar_suffix(self): self.rejected(fixture(suffix=b'not a tar trailer'))

    def test_duplicate_manifest(self):
        x=('A.olean',b'one','file'); self.rejected(fixture([x],manifest_entries=[x,x]))

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'proof.sqfs'; out.write_bytes(b'existing')
            with self.assertRaises(ValueError): self.build(fixture(),tmp)
            self.assertEqual(out.read_bytes(),b'existing')


if __name__=='__main__': unittest.main(verbosity=2)
