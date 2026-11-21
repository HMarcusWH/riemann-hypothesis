#!/usr/bin/env python3
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from export_stream_store import build_export
from test_verified_squashfs_store import MKSQUASHFS, UNSQUASHFS

class ExportTransportTests(unittest.TestCase):
    def build(self,tmp,script,**kwargs):
        opts={'min_free_bytes':0,'image_max_bytes':1024**2,'max_bytes':1024**2,
              'processors':1,'memory_mb':16,'timeout_seconds':20}
        opts.update(kwargs)
        return build_export([sys.executable,'-c',script],Path(tmp),Path(tmp)/'export.sqfs',
                 mksquashfs=MKSQUASHFS,unsquashfs=UNSQUASHFS,**opts)

    def reject(self,script,**kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception): self.build(tmp,script,**kwargs)
            self.assertFalse((Path(tmp)/'export.sqfs').exists())
            self.assertFalse((Path(tmp)/'export.sqfs.receipt.json').exists())

    def test_exact_stdout_hash_and_readback(self):
        data=b'{"lean":"example"}\n'*1000
        with tempfile.TemporaryDirectory() as tmp:
            report=self.build(tmp,'import sys;sys.stdout.buffer.write('+repr(data)+')',
                       expected_sha256=hashlib.sha256(data).hexdigest(),expected_bytes=len(data))
            self.assertEqual(report['stdout_sha256'],report['readback_sha256'])
            self.assertEqual(report['stdout_bytes'],len(data))
            self.assertFalse(report['proof_validity_established'])

    def test_nonzero_producer_exit_cannot_publish(self):
        self.reject("import sys;sys.stdout.write('partial');sys.exit(7)")

    def test_wrong_expected_hash(self): self.reject("print('data')",expected_sha256='0'*64)
    def test_wrong_expected_size(self): self.reject("print('data')",expected_bytes=1)
    def test_empty_export(self): self.reject('pass')
    def test_oversized_output(self): self.reject("print('a'*4096)",max_bytes=1024)
    def test_timeout(self): self.reject('import time;time.sleep(10)',timeout_seconds=0.1)

if __name__=='__main__': unittest.main(verbosity=2)
