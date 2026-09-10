"""Evidence-vector routing and transactional per-task call admission. No model/network calls.

plan/ reserve: JSON with task_id, request_id, features, evidence_refs and coordinator info.
finish: task_id, request_id, status, usage_tokens, evidence_ref.
status: task_id. Reservations count permanently, including cancelled attempts.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import subagent_router as base

ROOT=Path(__file__).resolve().parents[1]


def load(root=ROOT):
    registry,roles=base.load(root)
    policy=json.loads((Path(root)/"policies/adaptive-routing.json").read_text(encoding="utf8"))
    base.require(policy["schema_version"]=="1.0","unsupported adaptive policy")
    for role in policy["roles"].values():
        base.require(role in roles["roles"],"adaptive role missing")
    for v in policy["budgets"].values():
        base.require(type(v) is int and v>0,"invalid admission budget")
    return registry,roles,policy


def plan(q,registry,roles,policy):
    base.validate(registry,roles)
    base.fields(q,{"task_id","request_id","features","evidence_refs","coordinator_binding","is_child","independent_work","probe_completed","failures","strong_review_failed","exceptional","prior_role","checkpoint_verified","decision_ref"})
    for k in ("task_id","request_id"):
        base.text(q[k],200)
    base.require(q["coordinator_binding"] in registry["models"],"unknown coordinator binding")
    for k in ("is_child","independent_work","probe_completed","strong_review_failed","exceptional","checkpoint_verified"):
        base.require(type(q[k]) is bool,"flags must be boolean")
    base.require(type(q["failures"]) is int and 0<=q["failures"]<=100,"invalid failures")
    base.require(q["prior_role"] is None or q["prior_role"] in roles["roles"],"unknown prior role")
    base.require(q["decision_ref"] is None or isinstance(q["decision_ref"],str),"invalid decision reference")
    f=q["features"]
    base.fields(f,set(policy["feature_values"]))
    for name,values in policy["feature_values"].items():
        base.require(f[name] in values,"invalid feature: "+name)
    refs=q["evidence_refs"]
    base.require(isinstance(refs,list) and len(refs)<=12,"invalid evidence refs")
    for ref in refs:
        base.text(ref,1500)
    base.require(len(base.canonical(q))<=16000,"route input exceeds bound")
    if q["failures"] or q["strong_review_failed"] or q["exceptional"] or q["checkpoint_verified"]:
        base.require(refs,"failure/escalation/checkpoint claims require evidence references")
    if q["failures"]:
        base.require(f["failure_type"]!="none","failure requires classification")
    current_tier=registry["models"][q["coordinator_binding"]]["tier"]
    result={"policy_hash":base.hash_object(policy),"registry_hash":base.hash_object(registry),"features":f,"evidence_refs":refs,"calibration":"not_calibrated","dispatch_performed":False}
    def terminal(mode,reason):
        return dict(result,mode=mode,reason_codes=[reason])
    if f["failure_type"]=="environment":
        return terminal("repair_environment","ENVIRONMENT_FAILURE_IS_NOT_REASONING_DIFFICULTY")
    unknown=any(value=="unknown" for value in f.values())
    if unknown and not q["probe_completed"]:
        return terminal("collect_evidence","UNKNOWN_REQUIRES_BOUNDED_READ_OR_TEST_PROBE")
    if not refs:
        return terminal("collect_evidence","TASK_FEATURES_NEED_SOURCE_OR_OBSERVATION")
    easy=(f["ambiguity"]=="clear" and f["dependency"]=="local" and f["constraints"]=="single" and f["novelty"]=="known" and f["verification"]=="deterministic" and f["reversibility"]=="reversible" and f["risk"]=="low" and f["phase"]=="execution" and f["failure_type"]!="reasoning" and q["failures"]<2)
    if q["exceptional"]:
        base.require(q["strong_review_failed"],"max frontier requires failed bounded strong review, not just difficulty wording")
        role,reason=policy["roles"]["exceptional"],"EXCEPTIONAL_WITH_FAILED_STRONG_REVIEW"
    elif q["strong_review_failed"]:
        role,reason=policy["roles"]["frontier"],"BOUNDED_STRONG_REVIEW_FAILED"
    elif easy:
        role=policy["roles"]["repair"] if q["failures"] else policy["roles"]["worker"]
        reason="ALL_ECONOMY_ELIGIBILITY_GATES_MET"
    else:
        role,reason=policy["roles"]["decision"],"NEEDS_BOUNDED_STRONG_DECISION_NOT_FULL_TASK_TAKEOVER"
    prior=q["prior_role"]
    if prior and roles["roles"][prior]["band"]!="economy" and roles["roles"][role]["band"]=="economy":
        if not (q["checkpoint_verified"] and q["decision_ref"]):
            return terminal("verify_checkpoint","DOWNGRADE_REQUIRES_VERIFIED_DECISION_AND_EXECUTION_CONTRACT")
        reason="VERIFIED_CHECKPOINT_RETURNS_EXECUTION_TO_ECONOMY"
    result.update(base.resolve(role,registry,roles))
    result["adaptive_policy_hash"]=base.hash_object(policy)
    result["reason_codes"]=[reason]
    strong=roles["roles"][role]["band"]!="economy"
    result["verification_contract"]=policy["verification_contract"]
    result["return_contract"]="decision_packet_v1" if strong else "artifact_evidence_v1"
    if q["is_child"]:
        return dict(result,mode="return_escalation_to_parent",instruction="禁止嵌套派生；父代理使用同一task_id预算派发同级决策代理")
    selected_tier=registry['models'][result['binding']]['tier']
    if strong and (current_tier=="frontier" or current_tier=="reasoner" and selected_tier!="frontier"):
        return dict(result,mode="coordinator_decides",instruction="当前强主代理完成有界决策，避免重复创建同级强代理；主代理用量另行记录")
    if not strong and current_tier=="economy":
        return dict(result,mode="execute_locally",instruction="当前经济型主代理执行；子代理effort约束不意味着能改变主代理档位")
    if not q["independent_work"]:
        return dict(result,mode="needs_independent_work_or_host_handoff" if strong else "execute_locally",instruction="当前宿主子代理委派需有可并行的其他有用工作；没有时不要制造空转，也不要声称已升级主模型")
    result.update(mode="delegate",spawn_parameters={"model":result["model"],"reasoning_effort":result["reasoning_effort"],"fork_turns":"none"},delegation_kind="decision_only" if strong else "execution_only")
    return result


class Ledger:
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY,budget TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS grants(task_id TEXT NOT NULL,request_id TEXT NOT NULL,digest TEXT NOT NULL,role TEXT NOT NULL,tier TEXT NOT NULL,effort TEXT NOT NULL,plan TEXT NOT NULL,status TEXT NOT NULL,usage_tokens INTEGER,evidence_ref TEXT,created REAL NOT NULL,PRIMARY KEY(task_id,request_id));
        ''')

    def close(self):
        self.db.close()

    def status(self,task_id):
        row=self.db.execute('SELECT budget FROM tasks WHERE task_id=?',(task_id,)).fetchone()
        records=list(self.db.execute('SELECT tier,effort,status,usage_tokens FROM grants WHERE task_id=?',(task_id,)))
        return {"task_id":task_id,"budget":json.loads(row[0]) if row else None,"total_reserved":len(records),"strong_reserved":sum(r['tier']!='economy' for r in records),"frontier_reserved":sum(r['tier']=='frontier' for r in records),"max_reserved":sum(r['effort']=='max' for r in records),"in_flight":sum(r['status']=='reserved' for r in records),"observed_tokens":sum(r['usage_tokens'] for r in records if r['usage_tokens'] is not None),"token_receipts_missing":sum(r['usage_tokens'] is None for r in records),"token_total_complete":bool(records) and all(r['usage_tokens'] is not None for r in records),"global_codex_token_cap_enforced":False}

    def reserve(self,q,registry,roles,policy):
        resolved=plan(q,registry,roles,policy)
        base.require(resolved['mode']=='delegate','route does not permit delegation: '+resolved['mode'])
        digest=base.hash_object(q)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT * FROM grants WHERE task_id=? AND request_id=?',(q['task_id'],q['request_id'])).fetchone()
            if old:
                base.require(old['digest']==digest,'idempotency conflict')
                self.db.commit()
                return {"admitted":False,"already_reserved":True,"instruction":"已有预约；先确认是否已启动，禁止重复spawn","plan":json.loads(old['plan']),"status":old['status']}
            self.db.execute('INSERT OR IGNORE INTO tasks VALUES(?,?,?)',(q['task_id'],base.canonical(policy['budgets']),time.time()))
            state=self.status(q['task_id']);caps=state['budget']
            # A later policy may tighten a live task, never silently increase its budget.
            caps={k:min(v,policy['budgets'][k]) for k,v in caps.items()}
            tier=registry['models'][resolved['binding']]['tier']
            checks=[(state['total_reserved']<caps['max_total_calls'],'total call budget'),(state['in_flight']<caps['max_concurrent_calls'],'concurrency budget')]
            if tier!='economy': checks.append((state['strong_reserved']<caps['max_strong_calls'],'strong call budget'))
            if tier=='frontier': checks.append((state['frontier_reserved']<caps['max_frontier_calls'],'frontier call budget'))
            if resolved['reasoning_effort']=='max': checks.append((state['max_reserved']<caps['max_max_effort_calls'],'max effort budget'))
            for allowed,reason in checks: base.require(allowed,'budget exhausted: '+reason)
            self.db.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?,?,?,?,?)',(q['task_id'],q['request_id'],digest,resolved['role'],tier,resolved['reasoning_effort'],base.canonical(resolved),'reserved',None,None,time.time()))
            self.db.commit()
            return {"admitted":True,"plan":resolved,"budget_state":self.status(q['task_id']),"enforcement":"reservations through this API only; host dispatch still performed by parent"}
        except Exception:
            self.db.rollback();raise

    def finish(self,q):
        base.fields(q,{'task_id','request_id','status','usage_tokens','evidence_ref'})
        base.require(q['status'] in {'completed','failed','cancelled'},'invalid final status')
        base.require(q['usage_tokens'] is None or type(q['usage_tokens']) is int and q['usage_tokens']>=0,'invalid observed token count')
        base.text(q['evidence_ref'],1500)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT status,usage_tokens,evidence_ref FROM grants WHERE task_id=? AND request_id=?',(q['task_id'],q['request_id'])).fetchone()
            base.require(row is not None,'grant unavailable')
            if row['status']!='reserved':
                base.require((row['status'],row['usage_tokens'],row['evidence_ref'])==(q['status'],q['usage_tokens'],q['evidence_ref']),'finished grant is immutable')
            else:
                self.db.execute('UPDATE grants SET status=?,usage_tokens=?,evidence_ref=? WHERE task_id=? AND request_id=?',(q['status'],q['usage_tokens'],q['evidence_ref'],q['task_id'],q['request_id']))
        return self.status(q['task_id'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','reserve','finish','status'])
    p.add_argument('--request');p.add_argument('--root',default=str(ROOT))
    h=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
    p.add_argument('--ledger',default=str(h/'cognitive-runtime/state/routing.sqlite3'))
    args=p.parse_args();ledger=None
    try:
        raw=Path(args.request).read_text(encoding='utf-8-sig') if args.request else sys.stdin.read(24000)
        q=json.loads(raw)
        if args.action in {'plan','reserve'}:
            r,roles,policy=load(args.root)
            if args.action=='plan': value=plan(q,r,roles,policy)
            else:
                ledger=Ledger(args.ledger);value=ledger.reserve(q,r,roles,policy)
        else:
            ledger=Ledger(args.ledger)
            if args.action=='finish':value=ledger.finish(q)
            else:
                base.fields(q,{'task_id'});base.text(q['task_id'],200);value=ledger.status(q['task_id'])
        print(base.canonical({'ok':True,'result':value}));return 0
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as exc:
        print(base.canonical({'ok':False,'error':str(exc)}));return 2
    finally:
        if ledger:ledger.close()


if __name__=='__main__':sys.exit(main())
