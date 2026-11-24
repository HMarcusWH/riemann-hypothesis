import hashlib,pathlib,tempfile,unittest,zipfile
from unittest.mock import patch
from reuse_mining import PIN,HEAD,TREE,RUN,JOB,REPO,WORKFLOW,ARTIFACT,identity,verify_graph,select_artifact,extract_graph

class MiningReuseTests(unittest.TestCase):
    def graph(self):
        s=PIN["original"]["solution"]
        return {"schema":"OPICA_AUTHENTICATED_EXPORT_DEPENDENCIES_V1","mode":"solution","proof_acceptance":False,"C1":"OPEN","independent_step4":"OPEN","raw_sha256":s["raw_sha256"],"raw_bytes":s["raw_bytes"],"roots":[{"name":"fixture","closure":{"status":"BUDGET_EXHAUSTED"}}],"expressions":1,"declarations":1,"download":{"url":s["url"],"compressed_sha256":s["compressed_sha256"],"compressed_bytes":s["compressed_bytes"],"observed_raw_sha256":s["raw_sha256"],"observed_raw_bytes":s["raw_bytes"],"zstd_exit":0,"feed_errors":[],"feed_thread_alive":False,"http_status":200,"resources":{"format":"OPICA_EXPR_COMPACT_V2"}}}
    def test_authentication_preserves_root_limits(self):
        g=self.graph();verify_graph(g)
        self.assertEqual(g["roots"][0]["closure"]["status"],"BUDGET_EXHAUSTED")
    def test_transport_rejections(self):
        for k,v in (("compressed_sha256","0"*64),("feed_errors",["Broken pipe"]),("zstd_exit",-13),("feed_thread_alive",True),("observed_raw_bytes",0),("index_failure",True)):
            g=self.graph();g["download"][k]=v
            with self.assertRaises(RuntimeError):verify_graph(g)
    def test_claim_and_raw_digest(self):
        for k,v in (("proof_acceptance",True),("raw_sha256","0"*64),("roots",[])):
            g=self.graph();g[k]=v
            with self.assertRaises(RuntimeError):verify_graph(g)
    def test_exact_successful_job(self):
        r={"id":RUN,"head_sha":HEAD,"run_attempt":1,"event":"pull_request","repository":{"full_name":REPO},"head_repository":{"full_name":REPO},"path":WORKFLOW,"pull_requests":[{"number":13,"head":{"sha":HEAD}}],"conclusion":"failure"}
        j={"id":JOB,"run_id":RUN,"name":"verified-export-mining","status":"completed","conclusion":"success"}
        def git(repo,*args):
            return TREE if args[-1]==HEAD+"^{tree}" else "a"*40
        with patch("reuse_mining.textgit",side_effect=git):
            self.assertEqual(len(identity(None,r,j)),4)
            with self.assertRaises(RuntimeError):identity(None,r,{**j,"conclusion":"failure"})
            with self.assertRaises(RuntimeError):identity(None,{**r,"run_attempt":2},j)
    def test_artifact_inventory_and_zip_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"a.zip"
            with zipfile.ZipFile(p,"w") as z:z.writestr("original-dependencies.json",b'{}')
            a={"id":1,"name":ARTIFACT,"expired":False,"workflow_run":{"id":RUN},"size_in_bytes":p.stat().st_size,"digest":"sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()}
            self.assertEqual(select_artifact({"total_count":1,"artifacts":[a]}),a)
            self.assertEqual(extract_graph(p,a)[0],b"{}")
            with self.assertRaises(RuntimeError):select_artifact({"total_count":2,"artifacts":[a]})
            with self.assertRaises(RuntimeError):select_artifact({"total_count":2,"artifacts":[a,a]})
            with self.assertRaises(RuntimeError):extract_graph(p,{**a,"digest":"sha256:"+"0"*64})
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"a.zip"
            with zipfile.ZipFile(p,"w") as z:z.writestr("../original-dependencies.json",b"{}")
            with self.assertRaises(RuntimeError):extract_graph(p,{"digest":"sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()})
if __name__=="__main__":unittest.main()
