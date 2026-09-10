from unittest.mock import patch
from datetime import date as RealDate

class FixedDate(RealDate):
    @classmethod
    def today(cls):return cls(2026,9,9)

import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import sys
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]/"skill"
sys.path.insert(0, str(ROOT/"scripts"))
import subagent_router as router


def request(**changes):
    q = {"task_type":"routine", "difficulty":"routine", "risk":"low", "verifiable":True, "bounded":True, "independent":True, "tool_sufficient":False, "failed_attempts":0, "failure_type":"none", "escalation_evidence":[], "current_children":0, "children_started":0, "delegation_depth":0}
    q.update(changes)
    return q


class RoutingTests(unittest.TestCase):
    def setUp(self):
        clock=patch("subagent_router.date",FixedDate);clock.start();self.addCleanup(clock.stop)
        self.registry = json.loads((ROOT/"policies/model-registry.json").read_text(encoding="utf8"))
        self.policy = json.loads((ROOT/"policies/subagent-policy.json").read_text(encoding="utf8"))

    def run_route(self, **kw):
        return router.route(request(**kw), self.registry, self.policy)

    def test_worker_xhigh(self):
        r = self.run_route()
        self.assertEqual((r["binding"],r["reasoning_effort"]), ("economy","xhigh"))
        self.assertEqual(r["spawn_parameters"]["fork_turns"], "none")

    def test_worker_max_after_located_execution_failure(self):
        r = self.run_route(failed_attempts=1, failure_type="execution", escalation_evidence=["test A fails at assertion B"])
        self.assertEqual(r["role"], "acr_worker_max")

    def test_strong_daily_roles(self):
        for task,role,effort in [("development","acr_developer","medium"),("review","acr_reviewer","high"),("architecture","acr_architect","high")]:
            r = self.run_route(task_type=task)
            self.assertEqual((r["role"], r["reasoning_effort"]),(role,effort))

    def test_high_risk_and_unverifiable_never_worker(self):
        for kw in ({"risk":"high"},{"verifiable":False},{"bounded":False}):
            self.assertNotEqual(self.run_route(**kw)["binding"], "economy")

    def test_hard_and_exceptional_need_evidence(self):
        for difficulty,effort in [("hard","xhigh"),("exceptional","max")]:
            with self.assertRaises(ValueError):
                self.run_route(difficulty=difficulty)
            r = self.run_route(difficulty=difficulty, escalation_evidence=["two incompatible invariants; reproduction referenced"])
            self.assertEqual(r["reasoning_effort"], effort)

    def test_two_failures_escalate_to_strong_review_first(self):
        kw = {"failed_attempts":2,"failure_type":"execution","escalation_evidence":["acceptance still fails after repair"]}
        self.assertEqual(self.run_route(**kw)["role"], "acr_reviewer")
        self.assertEqual(self.run_route(**kw,prior_role="acr_reviewer")["role"], "acr_solver")

    def test_sticky_upgrade(self):
        self.assertEqual(self.run_route(prior_role="acr_architect")["role"], "acr_architect")

    def test_environment_failure_not_model_failure(self):
        r = self.run_route(failed_attempts=2,failure_type="environment",escalation_evidence=["service timeout"])
        self.assertEqual(r["mode"], "repair_environment")
        self.assertNotIn("spawn_parameters", r)

    def test_tool_first_and_sequential_work(self):
        self.assertEqual(self.run_route(tool_sufficient=True)["mode"], "direct_tool")
        self.assertEqual(self.run_route(independent=False)["mode"], "keep_with_coordinator")

    def test_low_capability_parent_cannot_self_upgrade(self):
        model = self.registry["models"]["economy"]["model_id"]
        self.assertEqual(self.run_route(task_type="architecture",independent=False,current_model=model)["mode"], "strong_coordinator_required")

    def test_limits(self):
        for kw,mode in [({"current_children":3},"wait_for_capacity"),({"children_started":4},"delegation_budget_exhausted"),({"delegation_depth":1},"return_to_parent")]:
            r = self.run_route(**kw)
            self.assertEqual(r["mode"], mode)
            self.assertNotIn("spawn_parameters", r)

    def test_lower_effort_rejected_in_config_and_request(self):
        for effort in ["none","low","medium","high"]:
            p = copy.deepcopy(self.policy)
            p["roles"]["acr_worker"]["effort"] = effort
            with self.assertRaises(ValueError):
                router.validate(self.registry,p)
        with self.assertRaises(ValueError):
            self.run_route(reasoning_effort="medium")

    def test_unknown_inactive_unsupported_binding(self):
        for change in [{"status":"deprecated"},{"supported_efforts":["medium"]},{"adapter":"new-provider"},{"capabilities":[]}]:
            r = copy.deepcopy(self.registry)
            r["models"]["economy"].update(change)
            with self.assertRaises(ValueError):
                router.validate(r,self.policy)

    def test_refresh_required_and_versioned_trace(self):
        with self.assertRaises(ValueError):
            router.validate(self.registry,self.policy,today=date(2099,1,1))
        result = self.run_route()
        self.assertEqual(len(result["registry_hash"]),64)
        self.assertEqual(result["input_features"],request())

    def test_future_model_replacement_does_not_change_role_policy(self):
        before = router.hash_object(self.policy)
        self.registry["models"]["economy"]["model_id"] = "synthetic-future-economy-model"
        r = self.run_route()
        self.assertEqual(r["model"], "synthetic-future-economy-model")
        self.assertEqual(r["reasoning_effort"], "xhigh")
        self.assertEqual(router.hash_object(self.policy),before)

    def test_deterministic_and_profiles_parse(self):
        expected = self.run_route()
        for _ in range(100):
            self.assertEqual(self.run_route(),expected)
        profiles = router.render(self.registry,self.policy)
        for filename, content in profiles.items():
            data = tomllib.loads(content)
            self.assertEqual(filename,data["name"]+".toml")
            self.assertFalse(data["agents"]["enabled"])
            self.assertEqual(data["model_reasoning_effort"],self.policy["roles"][data["name"]]["effort"])

    def test_handoff_checks_and_no_private_extra_fields(self):
        q = {"task_id":"fixture","parent_task_id":"fixture-parent","goal":"inspect fixture","inputs":["fixture file"],"allowed_tools":["read"],"write_paths":[],"external_effects":[],"acceptance":["report exact count"],"budget":{"max_repairs":1,"max_tool_calls":3,"max_seconds":60,"max_usd":None},"stop_conditions":["input unavailable"],"result_contract":"artifact_evidence_v1"}
        self.assertTrue(router.handoff(q,self.policy)["valid"])
        with self.assertRaises(ValueError):
            router.handoff(dict(q,private_chain_of_thought="forbidden field"),self.policy)
        q["acceptance"] = []
        with self.assertRaises(ValueError):
            router.handoff(q,self.policy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
