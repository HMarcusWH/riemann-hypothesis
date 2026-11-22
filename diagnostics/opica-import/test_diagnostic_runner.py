#!/usr/bin/env python3
"""Small input-policy controls; no compiler, supplier import, or proof claim."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest

import diagnostic_runner as runner


class DiagnosticInputControls(unittest.TestCase):
    def test_wrong_hash_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"changed")
            with self.assertRaises(runner.InputFailure):
                runner.Bindings().add(path, hashlib.sha256(b"expected").hexdigest())

    def test_missing_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(runner.InputFailure):
                runner.Bindings().add(Path(directory) / "missing")

    def test_valid_identity_then_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"good")
            bindings = runner.Bindings()
            bindings.add(path, hashlib.sha256(b"good").hexdigest(), 4)
            self.assertEqual(bindings.verify()["status"], "PASS")
            path.write_bytes(b"evil")
            self.assertEqual(bindings.verify()["status"], "FAIL")

    def test_symlink_retarget_same_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a", "b"):
                (root / name).write_bytes(b"same")
            link = root / "link"
            link.symlink_to(root / "a")
            bindings = runner.Bindings(); bindings.add(link)
            link.unlink(); link.symlink_to(root / "b")
            self.assertEqual(bindings.verify()["status"], "FAIL")

    def test_ld_preload_rejected(self):
        with self.assertRaises(runner.InputFailure):
            runner.reject_overrides({"LD_PRELOAD": "/tmp/substitute.so"})

    def test_unreviewed_import_override_rejected(self):
        with self.assertRaises(runner.InputFailure):
            runner.reject_overrides({"LEAN_PATH": "/tmp/substituted"})

    def test_resource_variables_allowed(self):
        runner.reject_overrides({"LEAN_NUM_THREADS": "2", "LEAN_ABORT_ON_PANIC": "1"})

    def test_native_nonpass_receipt_rejected(self):
        boot = types.SimpleNamespace(NATIVE_HEAD="a", NATIVE_TREE="b", MATHLIB="c")
        with self.assertRaises(runner.InputFailure):
            runner.validate_native_receipt({"status": "INCOMPLETE"}, boot, {}, {"modules": {}},
                                           Path("/unused"), Path("/unused"), runner.Bindings())

    def test_earlier_root_shadow_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roots = [root / "first", root / "expected"]
            for path in roots:
                path.mkdir(); (path / "Main.olean").write_bytes(b"same")
            boot = types.SimpleNamespace(module_path=lambda name, suffix: Path(name + suffix))
            with self.assertRaises(runner.InputFailure):
                runner.require_resolution("Main", roots, roots[1] / "Main.olean", boot)
            runner.require_resolution("Main", [roots[1]], roots[1] / "Main.olean", boot)

    def test_missing_optional_counter_is_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = runner.optional_read(Path(directory) / "missing")
            self.assertEqual(result["coverage"], "UNAVAILABLE")
            self.assertNotIn("text", result)

    def test_unsafe_cgroup_membership_not_followed(self):
        result = runner.cgroup_observations({"coverage": "AVAILABLE", "text": "0::/../../outside\n"})
        self.assertEqual(result["coverage"], "UNAVAILABLE")

    def test_partial_startup_record_then_valid_is_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "fixture.process.json"
            record.write_text('{"pid":')
            sampler = runner.SupplementalSampler(root, "fixture")
            sampler.thread.start()
            try:
                deadline = time.monotonic() + 3
                while sampler.result["initial_record_retries"] == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertGreater(sampler.result["initial_record_retries"], 0)
                record.write_text(json.dumps({"pid": os.getpid()}))
                while sampler.result["snapshots"] == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertGreater(sampler.result["snapshots"], 0)
            finally:
                result = sampler.finish()
            self.assertEqual(result["status"], "COLLECTION_COMPLETED_WITH_PER_FIELD_COVERAGE")
            self.assertEqual(result["initial_record_last_error_type"], "JSONDecodeError")


if __name__ == "__main__":
    unittest.main(verbosity=2)
