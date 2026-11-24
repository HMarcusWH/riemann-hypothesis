from pathlib import Path
import hashlib
import tempfile
import unittest
import storage_benchmark as s

class StorageControls(unittest.TestCase):
    def fixture(self,base):
        root=Path(base)
        a,b=root/"a",root/"b"
        for p in [a,b]:
            p.mkdir();(p/"x").write_bytes(b"hello")
        digest=hashlib.sha256(b"hello").hexdigest()
        m=root/"files.sha256"
        m.write_text(digest+"  x\n")
        return a,b,m

    def test_equal_valid_file_bytes_only(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b,m=self.fixture(temp)
            r=s.compare(m,a,b,1)
            self.assertFalse(r["proof_acceptance"])
            self.assertFalse(r["complete_supplier_store_verified"])
            self.assertTrue(r["same_files_and_expected_digests"])

    def test_changed_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b,m=self.fixture(temp)
            (b/"x").write_bytes(b"wrong")
            with self.assertRaises(s.StorageError):
                s.compare(m,a,b,1)

    def test_duplicate_and_traversal_rejected(self):
        h="a"*64
        for text in [h+"  ../outside\n",h+"  x\n"+h+"  x\n",h+" *x\n"]:
            with self.assertRaises(s.StorageError):
                s.parse_manifest(text)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b,m=self.fixture(temp)
            (b/"x").unlink()
            (b/"x").symlink_to(a/"x")
            with self.assertRaises(s.StorageError):
                s.compare(m,a,b,1)

if __name__=="__main__":
    unittest.main()
