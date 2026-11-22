import hashlib
import tempfile
from pathlib import Path
import unittest
from reparse_saved_log import reparse, DEFAULT_EXPECTED

EXACT = ("\n".join([
    "IMPORT_DIAGNOSTIC mono_ms=5830318 DIAGNOSTIC_ONLY selection=exact-guard mode=split imports=#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]",
    "IMPORT_DIAGNOSTIC mono_ms=5830318 NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit",
    "IMPORT_DIAGNOSTIC mono_ms=5830318 CORE_BEGIN",
    "IMPORT_DIAGNOSTIC mono_ms=6630460 CORE_END",
    "IMPORT_DIAGNOSTIC mono_ms=6630460 FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0",
]) + "\n").encode()


class HistoricalReparseTests(unittest.TestCase):
    def test_exact_historical_log(self):
        self.assertEqual(hashlib.sha256(EXACT).hexdigest(), DEFAULT_EXPECTED)
        result = reparse(EXACT)
        self.assertEqual(result["core_seconds"], 800.142)
        self.assertIsNone(result["finalize_seconds"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["old_workflow_disposition"], "FAILURE_UNCHANGED")
        self.assertFalse(result["proof_acceptance"])

    def test_tampered_log_rejected(self):
        with self.assertRaises(ValueError):
            reparse(EXACT + b"tampered")


if __name__ == "__main__":
    unittest.main()
