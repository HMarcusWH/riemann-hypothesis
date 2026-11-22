import copy
import unittest
from fork_ci_identity import Refused, validate, validate_merge_record

FORK="HMarcusWH/riemann-hypothesis"; A="a"*40; B="b"*40; C="c"*40
def payload():
    return {"repository":{"full_name":FORK},"number":5,
            "pull_request":{"number":5,"state":"open","merged":False,
              "head":{"sha":A,"repo":{"full_name":FORK}},
              "base":{"sha":B,"ref":"main","repo":{"full_name":FORK}}}}

class ForkBoundaryTests(unittest.TestCase):
    def test_exact_fork_pr(self):
        x=validate(payload(),expected_head=A,expected_base=B)
        self.assertEqual(x["repository"],FORK);self.assertFalse(x["proof_acceptance"])
        self.assertIsNone(x["candidate_merge_sha"])
    def test_upstream_pr_same_number_refused(self):
        x=payload();x["repository"]["full_name"]="leanprover-community/riemann-hypothesis"
        with self.assertRaises(Refused): validate(x,expected_head=A,expected_base=B)
    def test_external_pr_no_privileged_execution(self):
        x=payload();x["pull_request"]["head"]["repo"]["full_name"]="somebody/untrusted"
        with self.assertRaises(Refused):validate(x,expected_head=A,expected_base=B)
    def test_stale_head_and_base(self):
        for field in ("head","base"):
            x=payload();x["pull_request"][field]["sha"]=C
            with self.assertRaises(Refused):validate(x,expected_head=A,expected_base=B)
    def test_unreviewed_base_branch(self):
        x=payload();x["pull_request"]["base"]["ref"]="attacker"
        with self.assertRaises(Refused):validate(x,expected_head=A,expected_base=B)
    def test_repo_substitution(self):
        x=payload();x["pull_request"]["base"]["repo"]["full_name"]="leanprover-community/riemann-hypothesis"
        with self.assertRaises(Refused):validate(x,expected_head=A,expected_base=B)
    def test_bad_sha(self):
        with self.assertRaises(Refused):validate(payload(),expected_head="main",expected_base=B)
    def test_stale_merge_parents(self):
        for parents in ([{"sha":A},{"sha":B}],[{"sha":B},{"sha":C}],[]):
            with self.assertRaises(Refused):
                validate_merge_record({"sha":C,"parents":parents},expected_head=A,expected_base=B)
    def test_correct_parent_order_not_proof_acceptance(self):
        result=validate_merge_record({"sha":C,"parents":[{"sha":B},{"sha":A}]},
                                     expected_head=A,expected_base=B)
        self.assertFalse(result["proof_acceptance"])
    def test_absent_pr_and_closed(self):
        for x in ({"repository":{"full_name":FORK}}, {**payload(),"pull_request":{**payload()["pull_request"],"state":"closed"}}):
            with self.assertRaises(Refused):validate(x,expected_head=A,expected_base=B)
if __name__=="__main__":unittest.main()
