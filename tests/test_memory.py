import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/"skill/scripts/runtime.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("runtime", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root/"project"
        self.project.mkdir()
        self.other = self.root/"other"
        self.other.mkdir()
        self.rt = mod.Runtime(self.root/"state")
        self.counter = 0

    def tearDown(self):
        self.rt.close()
        self.temp.cleanup()

    def put(self, **kw):
        self.counter += 1
        q = {"action":"put", "kind":"project", "project":str(self.project), "title":"环境 Python", "content":"该测试项目使用 Python。", "provenance":{"source_type":"user_stated","source_ref":"synthetic fixture"}, "idempotency_key":str(self.counter)}
        q.update(kw)
        return q

    def get(self, rid):
        return self.rt.request({"action":"get", "project":str(self.project), "id":rid})

    def search(self, **kw):
        q = {"action":"retrieve", "project":str(self.project), "query":"Python"}
        q.update(kw)
        return self.rt.request(q)["entries"]

    def test_persistence_across_reopen(self):
        r = self.rt.request(self.put())
        self.rt.close()
        self.rt = mod.Runtime(self.root/"state")
        self.assertEqual(self.get(r["id"])["body"]["confidence"], "source_attribution_only")
        self.assertEqual(len(self.search()), 1)

    def test_project_scope_and_explicit_user_retrieval(self):
        self.rt.request(self.put())
        self.assertEqual(self.search(project=str(self.other)), [])
        q = self.put(kind="user")
        del q["project"]
        self.rt.request(q)
        self.assertEqual(len(self.search()), 1)
        self.assertEqual(len(self.search(include_user=True)), 2)

    def test_candidate_cannot_pollute_active_retrieval(self):
        q = self.put(kind="procedural", content={key:"Python synthetic proposal" for key in mod.ASSET})
        r = self.rt.request(q)
        self.assertEqual(r["status"], "candidate")
        self.assertEqual(self.search(), [])
        self.assertEqual(len(self.search(include_candidates=True)), 1)
        for action in ("promote", "verify_candidate"):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                self.rt.request({"action":action, "id":r["id"]})

    def test_cas_and_idempotency(self):
        q = self.put()
        first = self.rt.request(q)
        self.assertTrue(self.rt.request(q)["replayed"])
        changed = dict(q, content="different")
        with self.assertRaisesRegex(ValueError, "idempotency"):
            self.rt.request(changed)
        update = self.put(id=first["id"], expected_revision=1, content="Python updated")
        self.assertEqual(self.rt.request(update)["revision"], 2)
        with self.assertRaisesRegex(ValueError, "revision conflict"):
            self.rt.request(self.put(id=first["id"], expected_revision=1))
        self.assertEqual(self.rt.request(q)["current_revision"], 2)

    def test_second_connection_cannot_overwrite_stale_version(self):
        r = self.rt.request(self.put())
        other = mod.Runtime(self.root/"state")
        try:
            self.rt.request(self.put(id=r["id"], expected_revision=1))
            with self.assertRaisesRegex(ValueError, "revision conflict"):
                other.request(self.put(id=r["id"], expected_revision=1))
        finally:
            other.close()

    def test_forget_cascades_scrubs_and_cannot_replay(self):
        q = self.put(content="UNIQUE_PRIVATE_FIXTURE")
        parent = self.rt.request(q)
        child = self.rt.request(self.put(derived_from=[parent["id"]], content="UNIQUE_DERIVED_FIXTURE"))
        self.rt.request({"action":"forget", "project":str(self.project), "id":parent["id"], "expected_revision":1})
        for rid in (parent["id"], child["id"]):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                self.get(rid)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.rt.request(q)
        bodies = [r[0] for r in self.rt.db.execute("SELECT body FROM records")]
        self.assertEqual(bodies, ["{}", "{}"])
        self.assertNotIn(b"UNIQUE_PRIVATE_FIXTURE", (self.root/"state/memory.sqlite3").read_bytes())

    def test_expiry_scrubs_on_access(self):
        r = self.rt.request(self.put())
        with self.rt.db:
            self.rt.db.execute("UPDATE records SET expires=0 WHERE id=?", (r["id"],))
        self.assertEqual(self.search(), [])
        self.assertEqual(self.rt.db.execute("SELECT body FROM records").fetchone()[0], "{}")

    def test_review_due_retains_for_explicit_maintenance_only(self):
        r = self.rt.request(self.put())
        with self.rt.db:
            self.rt.db.execute("UPDATE records SET review=0 WHERE id=?", (r["id"],))
        self.assertEqual(self.search(), [])
        self.assertTrue(self.get(r["id"])["review_due"])

    def test_file_changes_invalidate_retrieval(self):
        p = self.project/"evidence.txt"
        p.write_text("version 1", encoding="utf8")
        check = self.rt.request({"action":"check_file", "path":str(p)})
        self.assertEqual(check["business_result"], "unknown")
        r = self.rt.request(self.put(files=[{"path":str(p),"sha256":check["sha256"]}]))
        p.write_text("version 2", encoding="utf8")
        self.assertEqual(self.search(), [])
        self.assertTrue(self.get(r["id"])["dependency_stale"])

    def test_parent_update_invalidates_children(self):
        parent = self.rt.request(self.put())
        child = self.rt.request(self.put(derived_from=[parent["id"]]))
        self.rt.request(self.put(id=parent["id"], expected_revision=1))
        self.assertTrue(self.get(child["id"])["dependency_stale"])
        self.assertEqual(len(self.search()), 1)

    def test_deprecation_is_not_forget(self):
        r = self.rt.request(self.put())
        self.rt.request({"action":"deprecate", "project":str(self.project),"id":r["id"],"expected_revision":1})
        self.assertEqual(self.search(), [])
        self.assertEqual(self.get(r["id"])["status"], "deprecated")

    def test_sensitive_consent_and_user_attribution(self):
        with self.assertRaises(ValueError):
            self.rt.request(self.put(sensitivity="sensitive"))
        self.rt.request(self.put(sensitivity="sensitive", consent_ref="explicit synthetic user request"))
        q = self.put(kind="user", provenance={"source_type":"agent_inferred","source_ref":"guess"})
        del q["project"]
        with self.assertRaises(ValueError):
            self.rt.request(q)

    def test_unknown_fields_and_bounded_recall(self):
        with self.assertRaises(ValueError):
            self.rt.request(self.put(chain_of_thought="private"))
        for _ in range(8):
            self.rt.request(self.put())
        self.assertLessEqual(len(self.search()), 6)
        self.assertEqual(self.search(max_chars=100), [])
        with self.assertRaises(ValueError):
            self.search(limit=7)

    def test_task_contract_and_route_are_honest_about_capabilities(self):
        content = {"goal":"test", "deliverables":["test"], "success_criteria":["test passes"], "constraints":"local synthetic test only", "phase":"act", "next_action":"run test", "budget":{"max_retries":2,"max_teacher_rounds":1,"max_usd":None}}
        self.rt.request(self.put(kind="task", content=content))
        bad = copy.deepcopy(content)
        bad["budget"]["max_retries"] = 100
        with self.assertRaises(ValueError):
            self.rt.request(self.put(kind="task", content=bad))
        result = self.rt.request({"action":"recommend_route", "task_type":"routine", "verifiable":True, "failed_attempts":0})
        self.assertEqual(result["recommended_model"], "gpt-5.6-luna")
        self.assertFalse(result["dispatch_performed"])

    def test_cli_real_process_unicode_and_exit_code(self):
        args = [sys.executable,"-X","utf8",str(SCRIPT),"--state-dir",str(self.root/"cli")]
        ok = subprocess.run(args, input=json.dumps(self.put(), ensure_ascii=False), text=True, encoding="utf8", capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["ok"])
        bad = subprocess.run(args, input='{"action":"promote"}', text=True, encoding="utf8", capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stdout)["ok"])




if __name__ == "__main__":
    unittest.main(verbosity=2)
