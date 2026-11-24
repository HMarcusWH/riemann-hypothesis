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
    def test_dependency_identity_swap_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r={"world":"NATIVE_COMPILER","declaration":"A","type_sha256":"a"*64,"dependencies":["Nat.add"]}
            row=compact_dependency_row(r,p)
            with self.assertRaises(RuntimeError):verify_dependency_row({**row,"declaration":"B"},p)
    def test_external_compact_dependency_count(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r={"world":"ORIGINAL_EXPORT","declaration":"A","type_sha256":"a"*64,"dependencies":[],"closure_count":120000}
            row=compact_dependency_row(r,p)
            self.assertEqual(row["closure_count"],120000);self.assertEqual(row["dependency_count"],0)
            self.assertTrue(verify_dependency_row(row,p))
    def test_compiler_incomplete_is_not_no_match(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);i=x/"inputs"
            write(i/"harvest/harvest.json",{"artifact_receipts":{"original":{"id":1},"historical":{"id":2}}})
            pin=LOCK["native"]
            write(i/"native/epoch.json",{"native":pin,"historical_status":"HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH"})
            write(i/"native/search/inventory.json",{"native_rows":[]})
            write(i/"native/search/compiler.json",{"status":"COMPILER_RESEARCH_INVENTORY_EXPORTED","failures":[{"status":"MODULE_BUILD_FAILED"}]})
            node={"id":"g","declaration":"A","type_sha256":"a"*64,"label":"A"}
            write(i/"native/search/graph.json",{"nodes":[node],"roots":["g"],"edges":[],"queries":[{"goal":"g","bounded_complete":True,"plans":[]}]})
            write(i/"native/validation/review.json",{"mode":"native","native":pin,"results":[]})
            packet(i,x/"out",{"head":"f"*40})
            r=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(r["outcome"],"INCOMPLETE_EXECUTION")
            self.assertIn("COMPILER_INVENTORY_INCOMPLETE",r["research_missing_gates"])
            self.assertEqual(r["bounded_search_outcome"],"INCOMPLETE_SEARCH_SCOPE")
    def test_feedback_contextual_receipt_and_wrong_epoch(self):
        from recursive_feedback import candidate_binding,feedback_name
        pin=LOCK["native"];target={"declaration":"A.context","module":"A","world":"NATIVE_QUERY"}
        g={"id":"g","declaration":"A.context","type_sha256":"a"*64}
        plan={"tag":"local","binder_slot":1}
        c={"id":"b"*64,"goal_id":"g","target":target,"expected_type_sha256":"a"*64,"plan":plan}
        r={"id":c["id"],"goal_id":"g","target":target,"status":"PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED","actual_local_kernel_proof":True,"expected_type_sha256":"a"*64,"actual_type_sha256":"a"*64,"candidate_plan_sha256":digest(plan),"cross_pin_definition_equivalence":"SAME_NATIVE_PIN","axioms":[],"stages":{k:{"status":"PASS"} for k in ("actual_types","kernel","independent_type","fresh_stock_kernel")}}
        receipt={"schema":"OPICA_R2_VALIDATION_V1","mode":"native","proof_acceptance":False,"native":pin}
        candidate_binding(c,r,g,pin,receipt)
        self.assertEqual(feedback_name(c["id"]),"OPICAR2Feedback"+"b"*32)
        with self.assertRaises(RuntimeError):candidate_binding(c,{**r,"actual_type_sha256":"c"*64},g,pin,receipt)
        with self.assertRaises(RuntimeError):candidate_binding(c,r,g,pin,{**receipt,"mode":"mixed"})
        with self.assertRaises(RuntimeError):feedback_name("../bad")
    def test_no_mixed_candidates_no_source_required(self):
        from mixed_campaign import run
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m={"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"mixed","native":LOCK["native"],"original_head":R1_PIN["original"]["head"],"selected":[],"proof_acceptance":False}
            run(p/"missing-original",p/"missing-native",m,p/"out")
            self.assertEqual(read(p/"out/review.json")["status"],"NO_SHORTLISTED_MIXED_CANDIDATES")
    def test_completed_bounded_negative_separate_from_production(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);i=x/"inputs"
            # Nonempty receipt placeholders are isolated unit-test data only.
            write(i/"harvest/harvest.json",{"artifact_receipts":{"original":{"id":1},"historical":{"id":2}}})
            pin=LOCK["native"]
            write(i/"native/epoch.json",{"native":pin,"historical_status":"HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH"})
            write(i/"native/search/inventory.json",{"native_rows":[]})
            write(i/"native/search/compiler.json",{"status":"COMPILER_RESEARCH_INVENTORY_EXPORTED","failures":[{"status":"EXCLUDED_ENDPOINT"},{"status":"NON_PROOF_OR_CONTAMINATED"}]})
            node={"id":"g","declaration":"A","type_sha256":"a"*64,"label":"A"}
            write(i/"native/search/graph.json",{"nodes":[node],"roots":["g"],"edges":[],"queries":[{"goal":"g","bounded_complete":True,"plans":[]}]})
            write(i/"native/validation/review.json",{"mode":"native","native":pin,"results":[]})
            packet(i,x/"out",{"head":"f"*40})
            r=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(r["outcome"],"NO_MATCH_IN_ENUMERATED_SCOPE")
            self.assertEqual(r["bounded_search_outcome"],"NO_MATCH_IN_ENUMERATED_SCOPE")
            self.assertTrue(r["production_missing_gates"]);self.assertFalse(r["proof_acceptance"])

    def test_wrong_goal_receipt_cannot_discharge(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);i=x/"inputs";pin=LOCK["native"]
            write(i/"harvest/harvest.json",{})
            write(i/"native/epoch.json",{"native":pin})
            write(i/"native/search/inventory.json",{"native_rows":[]})
            write(i/"native/search/compiler.json",{})
            node={"id":"g","declaration":"A","type_sha256":"a"*64,"label":"A"}
            target={"declaration":"A","world":"NATIVE_QUERY"}
            cand={"id":"c","goal_id":"g","target":target,"expected_type_sha256":"a"*64,"plan":{"tag":"const","constant_id":"x"}}
            write(i/"native/search/graph.json",{"nodes":[node],"roots":["g"],"edges":[],"queries":[{"goal":"g","bounded_complete":True,"plans":[cand]}]})
            write(i/"native/search/native-candidates.json",{"selected":[cand],"native":pin})
            write(i/"native/validation/review.json",{"mode":"native","native":pin,"results":[{"id":"c","goal_id":"wrong","target":target,"expected_type_sha256":"a"*64,"candidate_plan_sha256":digest(cand["plan"]),"actual_local_kernel_proof":True,"status":"PROVED_CONDITIONAL_LOCAL_PIN_REVIEW_REQUIRED"}]})
            packet(i,x/"out",{"head":"f"*40})
            r=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(r["local_exact_proof_count"],0);self.assertTrue(r["input_errors"]);self.assertFalse(r["proof_acceptance"])

    def test_expanded_readiness_and_pinned_mining_attempt(self):
        from harvest import expanded_readiness,run_identity
        self.assertEqual(expanded_readiness({"principal":{}})["missing"],["historical","original"])
        self.assertEqual(expanded_readiness({k:{} for k in ("historical","original","principal")})["status"],"READY_FOR_FRESH_EXPANDED_RESEARCH")
        spec=next(x for x in LOCK["runs"] if x["key"]=="external-repaired")
        run={"id":spec["run"],"head_sha":spec["head"],"repository":{"full_name":spec["repository"]},"head_repository":{"full_name":spec["repository"]},"path":spec["workflow"],"run_attempt":1}
        run_identity(run,spec)
        with self.assertRaises(RuntimeError):run_identity({**run,"run_attempt":2},spec)
    def test_empty_packet_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);(x/"inputs").mkdir()
            packet(x/"inputs",x/"out",{"head":"f"*40})
            v=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(v["outcome"],"INCOMPLETE_EXECUTION");self.assertFalse(v["proof_acceptance"]);self.assertEqual(v["RH"],"OPEN")
            self.assertEqual(len(list((x/"out").iterdir())),10)
    def test_evidence_ledger_never_promotes_metadata(self):
        from sync_evidence import classify,disposition
        self.assertEqual(classify("native-search"),"RESEARCH_PRODUCING_CHECK")
        self.assertEqual(classify("unknown"),"UNCLASSIFIED_REQUIRES_REVIEW")
        self.assertEqual(disposition({"status":"completed","conclusion":"success"},[{"status":"completed","conclusion":"success"}]),"METADATA_GREEN_RECEIPTS_REQUIRE_REVIEW")
        self.assertEqual(disposition({"status":"in_progress","conclusion":None},[]),"RUNNING_OR_QUEUED")
        self.assertEqual(disposition({"status":"completed","conclusion":"failure"},[]),"TERMINAL_NON_SUCCESS")
        self.assertEqual(disposition({"status":"completed","conclusion":"success"},[]),"INCOMPLETE_OR_NON_SUCCESS_JOB")
    def test_principal_source_cut_firewall(self):
        from principal_suppliers import safe_dependency,MODULES
        self.assertFalse(safe_dependency("UpperTheory.FinalTheorems.riemannHypothesis"))
        self.assertFalse(safe_dependency("UpperTheory.Top.plugWin"))
        self.assertFalse(safe_dependency("UpperTheory.Lit.everyE₂"))
        self.assertTrue(safe_dependency("UpperTheory.One.vwin_of_row"))
        self.assertEqual(sum(len(x[2]) for x in MODULES.values()),7)
    def test_missing_candidate_result_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            x=Path(d);i=x/"inputs";pin=LOCK["native"]
            write(i/"harvest/harvest.json",{"artifact_receipts":{"original":{"id":1},"historical":{"id":2}}})
            write(i/"native/epoch.json",{"native":pin,"historical_status":"HISTORICAL_PORT_CANDIDATE_SOURCE_ADMITTED_FOR_FRESH_NATIVE_RESEARCH"})
            write(i/"native/search/inventory.json",{"native_rows":[]})
            write(i/"native/search/compiler.json",{"status":"COMPILER_RESEARCH_INVENTORY_EXPORTED","failures":[]})
            node={"id":"g","declaration":"A","type_sha256":"a"*64,"label":"A"}
            cand={"id":"c","goal_id":"g","target":{"declaration":"A","world":"NATIVE_QUERY"},"expected_type_sha256":"a"*64,"plan":{"tag":"const","constant_id":"x"}}
            write(i/"native/search/graph.json",{"nodes":[node],"roots":["g"],"edges":[],"queries":[{"goal":"g","bounded_complete":True,"plans":[cand]}]})
            write(i/"native/search/native-candidates.json",{"schema":"OPICA_R2_CANDIDATE_MANIFEST_V1","mode":"native","proof_acceptance":False,"selected":[cand],"native":pin})
            write(i/"native/validation/review.json",{"schema":"OPICA_R2_VALIDATION_V1","mode":"native","proof_acceptance":False,"native":pin,"results":[]})
            packet(i,x/"out",{"head":"f"*40})
            v=read(x/"out/STEP4_VERDICT.json")
            self.assertEqual(v["outcome"],"INCOMPLETE_EXECUTION")
            self.assertIn("CANDIDATE_POPULATION_INCOMPLETE_OR_BUDGETED",v["research_missing_gates"])
    def test_complete_cost_finite_cells(self):
        from removal_controls import run
        result=run()
        self.assertEqual(result["signed_cell_cases"],414050)
        self.assertEqual(result["violations"],0)
        self.assertFalse(result["proof_acceptance"])
if __name__=="__main__":unittest.main()
