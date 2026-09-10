from unittest.mock import patch
from datetime import date as RealDate

class FixedDate(RealDate):
    @classmethod
    def today(cls):return cls(2026,9,9)

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/'skill'
sys.path.insert(0,str(ROOT/'scripts'))
import adaptive_router as ar


def query(**changes):
    q={'task_id':'fixture-work-order','request_id':'first','features':{'ambiguity':'clear','dependency':'local','constraints':'single','novelty':'known','verification':'deterministic','reversibility':'reversible','risk':'low','phase':'execution','failure_type':'none'},'evidence_refs':['fixture: closed task contract and acceptance test'],'coordinator_binding':'frontier','is_child':False,'independent_work':True,'probe_completed':False,'failures':0,'strong_review_failed':False,'exceptional':False,'prior_role':None,'checkpoint_verified':False,'decision_ref':None}
    f=changes.pop('features',{})
    q.update(changes);q['features'].update(f)
    return q


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        clock=patch("subagent_router.date",FixedDate);clock.start();self.addCleanup(clock.stop)
        self.r,self.roles,self.policy=ar.load(ROOT)
        self.tmp=tempfile.TemporaryDirectory()
        self.ledger=ar.Ledger(Path(self.tmp.name)/'routing.sqlite3')

    def tearDown(self):
        self.ledger.close();self.tmp.cleanup()

    def plan(self,q):return ar.plan(q,self.r,self.roles,self.policy)
    def reserve(self,q):return self.ledger.reserve(q,self.r,self.roles,self.policy)
    def finish(self,q,status='completed'):
        return self.ledger.finish({'task_id':q['task_id'],'request_id':q['request_id'],'status':status,'usage_tokens':None,'evidence_ref':'fixture runner receipt'})

    def test_strong_to_economy(self):
        p=self.plan(query());self.assertEqual(p['mode'],'delegate');self.assertEqual(p['reasoning_effort'],'xhigh')
        self.assertEqual(p['delegation_kind'],'execution_only')

    def test_luna_to_bounded_sol_decision(self):
        p=self.plan(query(coordinator_binding='economy',features={'constraints':'interacting','phase':'decision'}))
        self.assertEqual(p['binding'],'reasoner');self.assertEqual(p['mode'],'delegate')
        self.assertEqual(p['return_contract'],'decision_packet_v1')

    def test_strong_parent_avoids_duplicate_strong_agent(self):
        p=self.plan(query(features={'constraints':'interacting'}))
        self.assertEqual(p['mode'],'coordinator_decides');self.assertNotIn('spawn_parameters',p)

    def test_unknown_first_probe_then_decision(self):
        q=query(coordinator_binding='economy',features={'novelty':'unknown'})
        self.assertEqual(self.plan(q)['mode'],'collect_evidence')
        q['probe_completed']=True
        self.assertEqual(self.plan(q)['binding'],'reasoner')

    def test_missing_evidence_cannot_claim_easy(self):
        self.assertEqual(self.plan(query(evidence_refs=[]))['mode'],'collect_evidence')

    def test_high_risk_blocks_economy_even_when_trivial(self):
        p=self.plan(query(coordinator_binding='economy',features={'risk':'high'}))
        self.assertEqual(p['binding'],'reasoner')

    def test_each_simple_gate_is_necessary(self):
        for name,value in [('ambiguity','conflicting'),('dependency','coupled'),('constraints','interacting'),('novelty','new'),('verification','partial'),('reversibility','irreversible'),('risk','medium'),('phase','decision')]:
            p=self.plan(query(features={name:value},coordinator_binding='economy'))
            self.assertNotEqual(p.get('binding'),'economy',name)

    def test_execution_repair_max_and_failure_escalation(self):
        q=query(failures=1,features={'failure_type':'execution'})
        self.assertEqual(self.plan(q)['role'],'acr_worker_max')
        q['failures']=2;q['coordinator_binding']='economy'
        self.assertEqual(self.plan(q)['role'],'acr_decision')

    def test_environment_does_not_spend_model_budget(self):
        q=query(failures=2,features={'failure_type':'environment'})
        self.assertEqual(self.plan(q)['mode'],'repair_environment')
        with self.assertRaises(ValueError):self.reserve(q)
        self.assertEqual(self.ledger.status(q['task_id'])['total_reserved'],0)

    def test_child_returns_to_parent_without_recursion(self):
        p=self.plan(query(coordinator_binding='economy',is_child=True,features={'dependency':'coupled'}))
        self.assertEqual(p['mode'],'return_escalation_to_parent');self.assertNotIn('spawn_parameters',p)

    def test_no_fabricated_sequential_model_switch(self):
        p=self.plan(query(coordinator_binding='economy',independent_work=False,features={'dependency':'coupled'}))
        self.assertEqual(p['mode'],'needs_independent_work_or_host_handoff')
        self.assertFalse(p['dispatch_performed'])

    def test_frontier_requires_failed_strong_review(self):
        q=query(coordinator_binding='economy',features={'phase':'decision'},strong_review_failed=True)
        self.assertEqual(self.plan(q)['binding'],'frontier')
        q['coordinator_binding']='reasoner'
        self.assertEqual(self.plan(q)['mode'],'delegate')
        with self.assertRaises(ValueError):self.plan(query(exceptional=True))

    def test_downgrade_requires_verified_checkpoint(self):
        q=query(prior_role='acr_decision')
        self.assertEqual(self.plan(q)['mode'],'verify_checkpoint')
        q.update(checkpoint_verified=True,decision_ref='fixture decision with resolved constraints')
        self.assertEqual(self.plan(q)['role'],'acr_worker')

    def test_reservation_idempotency_prevents_duplicate_spawn(self):
        q=query();self.assertTrue(self.reserve(q)['admitted'])
        repeated=self.reserve(q)
        self.assertFalse(repeated['admitted']);self.assertTrue(repeated['already_reserved'])
        self.assertEqual(self.ledger.status(q['task_id'])['total_reserved'],1)
        q['features']['risk']='medium'
        with self.assertRaises(ValueError):self.reserve(q)

    def test_strong_budget_and_no_cancellation_refund(self):
        for i in range(2):
            q=query(request_id=str(i),coordinator_binding='economy',features={'phase':'decision'})
            self.reserve(q);self.finish(q,status='cancelled')
        q['request_id']='third'
        with self.assertRaisesRegex(ValueError,'strong call budget'):self.reserve(q)
        self.assertEqual(self.ledger.status(q['task_id'])['strong_reserved'],2)

    def test_frontier_and_max_limits(self):
        q=query(coordinator_binding='economy',strong_review_failed=True,exceptional=True)
        self.reserve(q);self.finish(q)
        q['request_id']='second'
        with self.assertRaisesRegex(ValueError,'frontier call budget'):self.reserve(q)

    def test_concurrency_and_total_limits(self):
        for i in range(3):self.reserve(query(request_id=str(i)))
        with self.assertRaisesRegex(ValueError,'concurrency'):self.reserve(query(request_id='four'))
        self.finish(query(request_id='0'))
        self.reserve(query(request_id='four'))
        with self.assertRaisesRegex(ValueError,'total call budget'):self.reserve(query(request_id='five'))

    def test_second_connection_observes_shared_cap(self):
        for i in range(2):
            q=query(request_id=str(i),coordinator_binding='economy',features={'phase':'decision'})
            self.reserve(q);self.finish(q)
        other=ar.Ledger(self.ledger.path)
        try:
            q['request_id']='extra'
            with self.assertRaisesRegex(ValueError,'strong call budget'):other.reserve(q,self.r,self.roles,self.policy)
        finally:other.close()

    def test_tokens_unknown_and_finished_receipts_immutable(self):
        q=query();self.reserve(q);state=self.finish(q)
        self.assertFalse(state['token_total_complete']);self.assertEqual(state['token_receipts_missing'],1)
        with self.assertRaises(ValueError):self.finish(q,status='failed')

    def test_live_budget_cannot_silently_expand(self):
        q=query(coordinator_binding='economy',features={'phase':'decision'})
        self.reserve(q);self.finish(q)
        q['request_id']='second';self.reserve(q);self.finish(q)
        policy=copy.deepcopy(self.policy);policy['budgets']['max_strong_calls']=9
        q['request_id']='extra'
        with self.assertRaises(ValueError):self.ledger.reserve(q,self.r,self.roles,policy)


if __name__=='__main__':unittest.main(verbosity=2)
