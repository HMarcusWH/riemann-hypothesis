#!/usr/bin/env python3
"""Synthetic custody fixtures only: no Lean execution or formal-validity claim."""
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

import collect_native_capsule as capsule


class Fixture:
    def __init__(self, root, bundle):
        self.work = root / "work"; self.work.mkdir()
        self.output = root / "capsule"
        self.bundle = bundle
        sources = json.loads((bundle / "native_sources.json").read_text())["modules"]
        runtime = json.loads((bundle / "runtime_files.json").read_text())
        rt = {row["path"]: row["sha256"] for row in runtime["files"]}
        self.receipt = {"schema": 1, "status": "PASS", "exit_code": 0,
                        "native_head": capsule.NATIVE_HEAD, "native_tree": capsule.NATIVE_TREE,
                        "common_mathlib_rev": capsule.MATHLIB, "compiler_version": capsule.COMPILER,
                        "compiler_sha256": rt["bin/lean"], "lake_sha256": rt["bin/lake"],
                        "kernel_checker_sha256": rt["bin/leanchecker"],
                        "runtime_manifest_sha256": capsule.BUNDLE_HASHES["runtime_files.json"],
                        "source_unchanged": True, "c1_closed": False, "rh_closed": False, "modules": []}
        self.native_bytes = 0
        self.authored_bytes = 0
        self.receipt["audit_modules"] = []
        for name, source_sha in sorted({**sources, **capsule.AUTHORED}.items()):
            product_paths = {}
            suffixes = [".olean", ".ilean"]
            if name == "Zeta23.FromPNTPlus.EulerMaclaurin":
                suffixes += [".olean.private", ".olean.server", ".ir"]
            for suffix in suffixes:
                path = self.work / capsule.NATIVE_LIB / capsule.module_path(name, suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                data = ("SYNTHETIC_CUSTODY_FIXTURE:" + name + suffix).encode()
                path.write_bytes(data)
                if name in sources: self.native_bytes += len(data)
                else: self.authored_bytes += len(data)
                product_paths[suffix] = {"path": str(path), "sha256": capsule.sha_bytes(data)}
            row = {"module": name,
                "source_path": str(self.work / (capsule.NATIVE_SOURCE if name in sources else "native/integration") / capsule.module_path(name, ".lean")),
                "source_sha256": source_sha, "object_path": product_paths[".olean"]["path"],
                "object_sha256": product_paths[".olean"]["sha256"],
                "sidecars": {k: v for k, v in product_paths.items() if k != ".olean"},
                "preexisting_object": False, "source_unchanged": True,
                "process": {"status": "PASS", "exit_code": 0}}
            if name in sources: self.receipt["modules"].append(row)
            elif name == "OPICAStep4.NativeBootstrapAudit": self.receipt["audit_consumer"] = row
            else: self.receipt["audit_modules"].append(row)
        self.write_receipt()

    def write_receipt(self):
        (self.work / capsule.RECEIPT).write_bytes(capsule.json_bytes(self.receipt))

    def run(self, max_member=1 << 20, max_total=8 << 20):
        return capsule.collect(self.work, self.output, self.bundle,
                               {"fixture": True, "scope": "Synthetic bytes, no compiler/proof authority"},
                               max_member, max_total)


class NativeCustodyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = Path(os.environ.get("OPICA_CUSTODY_REFERENCE_BUNDLE",
                          str(Path(__file__).resolve().parents[1] / "native_bootstrap"))).resolve()
        if not cls.bundle.is_dir():
            raise RuntimeError("Frozen native_bootstrap reference metadata is required; no test skip")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = Fixture(self.root, self.bundle)

    def incomplete(self, result):
        self.assertFalse(result["custody_complete"])
        self.assertFalse(result["proof_acceptance"])
        self.assertEqual(result["exit_code"], 2)
        self.assertFalse((self.fixture.output / "native-objects.zip").exists())
        self.assertTrue((self.fixture.output / "CUSTODY_MANIFEST.json").is_file())

    def test_complete_1155_file_roundtrip_without_source_or_supplier_payloads(self):
        result = self.fixture.run()
        self.assertTrue(result["custody_complete"])
        self.assertFalse(result["proof_acceptance"])
        self.assertEqual(result["step4"], "OPEN")
        self.assertEqual(len(result["objects"]), 1155)
        self.assertEqual(result["scope_counts"]["native_files"], 1147)
        self.assertEqual(result["scope_counts"]["authored_audit_files"], 8)
        self.assertEqual(result["measurement"]["required_total_bytes"], self.fixture.native_bytes + self.fixture.authored_bytes)
        self.assertEqual(result["measurement"]["by_role"]["native_dependency"]["required_total_bytes"], self.fixture.native_bytes)
        self.assertTrue(all(row["status"] == "ARCHIVED_AND_VERIFIED" for row in result["objects"]))
        with zipfile.ZipFile(result["archive"]["path"]) as archive:
            names = archive.namelist()
            self.assertEqual(sum(name.startswith("objects/") for name in names), 1155)
            self.assertIn("objects/Zeta23/FromPNTPlus/EulerMaclaurin.ir", names)
            self.assertIn("objects/OPICAStep4/NativeBootstrapAudit.olean", names)
            self.assertIn("objects/OPICAStep4/NativeBootstrapAudit.ilean", names)
            self.assertFalse(any(name.endswith((".lean", ".sqfs", ".so")) for name in names))

    def test_missing_required_private_sidecar_explicit_unknown_size(self):
        row = next(row for row in self.fixture.receipt["modules"] if row["module"].endswith(".EulerMaclaurin"))
        Path(row["sidecars"][".olean.private"]["path"]).unlink()
        result = self.fixture.run(); self.incomplete(result)
        self.assertEqual(sum(row["status"] == "MISSING" for row in result["objects"]), 1)
        self.assertIsNone(result["measurement"]["required_total_bytes"])

    def test_changed_object_hash_rejected(self):
        Path(self.fixture.receipt["modules"][0]["object_path"]).write_bytes(b"wrong exact object")
        result = self.fixture.run(); self.incomplete(result)
        self.assertEqual(sum(row["status"] == "HASH_MISMATCH" for row in result["objects"]), 1)

    def test_member_size_limit_explicit(self):
        result = self.fixture.run(max_member=1)
        self.incomplete(result)
        self.assertTrue(all(row["status"] == "OVERSIZE_MEMBER" for row in result["objects"]))
        self.assertEqual(result["measurement"]["required_total_bytes"], self.fixture.native_bytes + self.fixture.authored_bytes)

    def test_total_size_limit_rejects_even_when_every_member_is_ready(self):
        result = self.fixture.run(max_total=1)
        self.incomplete(result)
        self.assertTrue(all(row["status"] == "READY" for row in result["objects"]))
        self.assertTrue(any(row["status"] == "OVERSIZE_TOTAL" for row in result["measurement"]["problems"]))

    def test_receipt_substituted_path_rejected(self):
        self.fixture.receipt["modules"][0]["object_path"] = str(self.root / "outside.olean")
        self.fixture.write_receipt()
        result = self.fixture.run(); self.incomplete(result)
        self.assertIn("object path is substituted", result["error"])

    def test_ancestor_symlink_rejected_without_copying_external_files(self):
        native_root = self.fixture.work / capsule.NATIVE_LIB / "Zeta23"
        outside = self.root / "outside"; native_root.rename(outside)
        native_root.symlink_to(outside, target_is_directory=True)
        result = self.fixture.run(); self.incomplete(result)
        self.assertTrue(all(row["status"] == "UNSAFE_OR_UNREADABLE" for row in result["objects"] if row["role"] == "native_dependency"))

    def test_undeclared_produced_sidecar_rejected(self):
        name = self.fixture.receipt["modules"][0]["module"]
        (self.fixture.work / capsule.NATIVE_LIB / capsule.module_path(name, ".ir")).write_bytes(b"unrecorded")
        result = self.fixture.run(); self.incomplete(result)
        self.assertTrue(any(row["status"] == "UNDECLARED_PRODUCED_SIDECAR" for row in result["measurement"]["problems"]))

    def test_drift_between_preflight_and_copy_leaves_partial_only(self):
        original = capsule.copy_product
        changed = False
        def mutate_once(target, work, row, max_member):
            nonlocal changed
            if not changed:
                (work / row["path"]).write_bytes(b"changed after preflight")
                changed = True
            return original(target, work, row, max_member)
        with mock.patch.object(capsule, "copy_product", side_effect=mutate_once):
            result = self.fixture.run()
        self.incomplete(result)
        self.assertTrue((self.fixture.output / "native-objects.partial.zip").exists())
        self.assertTrue(any(row["status"] == "DRIFTED_OR_UNREADABLE_DURING_COLLECTION" for row in result["objects"]))

    def test_corrupted_archive_readback_never_promoted(self):
        original = capsule.verify_roundtrip
        def corrupt(archive, plan, embedded):
            with zipfile.ZipFile(archive) as view:
                info = view.getinfo(plan[0]["archive_path"])
                offset = info.header_offset
            with archive.open("r+b") as stream:
                stream.seek(offset + 26)
                name_size, extra_size = struct.unpack("<HH", stream.read(4))
                stream.seek(offset + 30 + name_size + extra_size)
                old = stream.read(1); stream.seek(-1, 1); stream.write(bytes([old[0] ^ 1]))
            return original(archive, plan, embedded)
        with mock.patch.object(capsule, "verify_roundtrip", side_effect=corrupt):
            result = self.fixture.run()
        self.incomplete(result)
        self.assertEqual(result["error_type"], "BadZipFile")

    def test_reference_manifest_drift_rejected(self):
        bundle = self.root / "reference-copy"; bundle.mkdir()
        for name in capsule.BUNDLE_HASHES:
            shutil.copyfile(self.bundle / name, bundle / name)
        (bundle / "runtime_files.json").write_bytes(b"{}")
        self.fixture.bundle = bundle
        result = self.fixture.run(); self.incomplete(result)
        self.assertIn("Reference metadata SHA256 mismatch", result["error"])

    def test_overwrite_refused(self):
        self.fixture.output.mkdir()
        sentinel = self.fixture.output / "existing"; sentinel.write_bytes(b"preserve")
        with self.assertRaises(capsule.CustodyError):
            self.fixture.run()
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_nonpass_build_receipt_cannot_qualify_custody(self):
        self.fixture.receipt["status"] = "INCOMPLETE"
        self.fixture.write_receipt()
        result = self.fixture.run(); self.incomplete(result)
        self.assertIn("receipt identity/status mismatch", result["error"])

    def test_missing_authored_audit_consumer_rejected(self):
        del self.fixture.receipt["audit_consumer"]
        self.fixture.write_receipt()
        result = self.fixture.run(); self.incomplete(result)
        self.assertIn("bootstrap audit consumer", result["error"])

    def test_gate_native_binding_mismatch_rejected(self):
        rows = [{"module": row["module"], "object": row["object_path"],
                 "object_sha256": row["object_sha256"], "source_sha256": row["source_sha256"]}
                for row in self.fixture.receipt["modules"]]
        rows[0]["object_sha256"] = "0" * 64
        path = self.fixture.work / "verification/NATIVE_VALIDATED_INPUTS.json"
        path.parent.mkdir(); path.write_bytes(capsule.json_bytes({"count": 572, "modules": rows}))
        result = self.fixture.run(); self.incomplete(result)
        self.assertIn("Gate-validated native object differs", result["error"])

    def test_output_parent_symlink_rejected_before_creation(self):
        outside = self.root / "outside"; outside.mkdir()
        alias = self.root / "alias"; alias.symlink_to(outside, target_is_directory=True)
        self.fixture.output = alias / "new-capsule"
        with self.assertRaises(capsule.CustodyError):
            self.fixture.run()
        self.assertFalse((outside / "new-capsule").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
