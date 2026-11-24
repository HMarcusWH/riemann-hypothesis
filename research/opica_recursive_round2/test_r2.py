import io,tempfile,unittest,zipfile
from pathlib import Path
from r2_common import *
from harvest import safe_members,run_identity
from repeat import closed_plan,substitute
from search import select
from packet import packet
class Controls(unittest.TestCase):
    def test_unsafe_zip(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:z.writestr("../escape","x")
        with zipfile.ZipFile(b) as z:
            with self.assertRaises(RuntimeError):safe_members(z)
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x";p.write_text('{"a":1,"a":2}')
            with self.assertRaises(RuntimeError):read(p)
    def test_run_pin(self):
        s=LOCK["runs"][0];r={"id":s["run"],"head_sha":s["head"],"repository":{"full_name":s["repository"]},"head_repository":{"full_name":s["repository"]},"path":s["workflow"],"run_attempt":1}
        run_identity(r,s)
        with self.assertRaises(RuntimeError):run_identity({**r,"head_sha":"0"*40},s)
    def test_circular_exclusions(self):
        self.assertTrue(forbidden("UpperTheory.FinalTheorems.riemannHypothesis"))
        self.assertTrue(forbidden("Zeta23.OPICARound4.ArithmeticFrontier.riemannHypothesis_of_cofinal_moment_slice_bounds"))
        self.assertTrue(forbidden("Foo.Validation.secret"))
        self.assertFalse(forbidden("OPICAExtractionR1.principal_ramp_windows_of_connected"))
    def test_feedback_no_local_capture(self):
        p={"tag":"const","constant_id":"a"};q={"tag":"const","constant_id":"b"};v={"a":{"plan":q}};seen=set()
        self.assertTrue(closed_plan(p));self.assertFalse(closed_plan({"tag":"local","index":0}))
        self.assertFalse(closed_plan({"tag":"lambda","body":q}))
        self.assertEqual(substitute(p,v,seen),q);self.assertEqual(seen,{"a"})
    def test_dependency_shard_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r={"world":"NATIVE_COMPILER","declaration":"A","type_sha256":"a"*64,"dependencies":["Nat.add","propext"]}
            c=compact_dependency_row(r,p)
            self.assertNotIn("dependencies",c);self.assertEqual(c["closure_count"],2)
            self.assertTrue(verify_dependency_row(c,p))
            with (p/c["dependency_file"]).open("ab") as f:f.write(b"x")
            with self.assertRaises(RuntimeError):verify_dependency_row(c,p)
    def test_no_mixed_candidates_no_source_required(self):
        from mixed_campaign import run
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m={"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"mixed","native":LOCK["native"],"original_head":R1_PIN["original"]["head"],"selected":[],"proof_acceptance":False}
            run(p/"missing-original",p/"missing-native",m,p/"out")
            self.assertEqual(read(p/"out/review.json")["status"],"NO_SHORTLISTED_MIXED_CANDIDATES")
    def test_empty_packet_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);(x/"inputs").mkdir()
            packet(x/"inputs",x/"out",{"head":"f"*40})
            v=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(v["outcome"],"INCOMPLETE_EXECUTION");self.assertFalse(v["proof_acceptance"]);self.assertEqual(v["RH"],"OPEN")
            self.assertEqual(len(list((x/"out").iterdir())),10)
if __name__=="__main__":unittest.main()
