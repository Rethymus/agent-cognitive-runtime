"""Deterministic role resolver and Codex profile compiler; never calls a model.

Edit policies/model-registry.json to replace models, policy to replace roles.
CLI: validate | route --request FILE | render --output DIR | handoff --request FILE
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_object(value):
    return hashlib.sha256(canonical(value).encode("utf8")).hexdigest()


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), "expected object")
    require(set(required) <= obj.keys(), "missing fields: " + ",".join(sorted(set(required)-obj.keys())))
    require(obj.keys() <= set(required)|set(optional), "unsupported fields")


def text(value, limit=2000):
    require(isinstance(value, str) and 0 < len(value) <= limit, "invalid bounded text")


def load(root=ROOT):
    root = Path(root)
    registry = json.loads((root/"policies/model-registry.json").read_text(encoding="utf8"))
    policy = json.loads((root/"policies/subagent-policy.json").read_text(encoding="utf8"))
    validate(registry, policy)
    return registry, policy


def validate(registry, policy, today=None):
    require(registry["schema_version"] == policy["schema_version"] == "1.0", "unsupported schema version")
    today = today or date.today()
    require(date.fromisoformat(registry["verified_on"]) <= today < date.fromisoformat(registry["review_after"]), "registry review required; refresh official capabilities, do not silently guess a successor")
    require(set(policy["economy_allowed_efforts"]) == {"xhigh", "max"}, "economy effort floor must remain xhigh/max")
    require(set(policy["strong_daily_allowed_efforts"]) <= {"medium", "high"}, "daily strong profiles must use medium/high")
    require(set(policy["strong_hard_allowed_efforts"]) <= {"xhigh", "max"}, "hard profiles must use xhigh/max")
    require(policy["default_role"] in policy["roles"], "unknown default role")
    require(len(policy["escalation_order"]) == len(policy["roles"]) and set(policy["escalation_order"]) == set(policy["roles"]), "invalid escalation order")
    for name, role in policy["roles"].items():
        require(re.fullmatch(r"acr_[a-z0-9_]+", name) is not None, "invalid role name")
        model = registry["models"].get(role["binding"])
        require(model is not None and model["status"] == "active", "role points to unavailable/inactive model")
        require(model["adapter"] == "codex", "provider requires a new adapter; cannot emit a Codex profile")
        text(model["model_id"], 150)
        require(role["capability"] in model["capabilities"], "binding lacks required capability")
        require(role["effort"] in model["supported_efforts"], "model does not support requested effort")
        allowed = policy[{"economy":"economy_allowed_efforts", "daily":"strong_daily_allowed_efforts", "hard":"strong_hard_allowed_efforts"}[role["band"]]]
        require(role["effort"] in allowed, "profile effort outside its policy band")
        if model["tier"] == "economy":
            require(role["band"] == "economy" and role["effort"] in policy["economy_allowed_efforts"], "economy model cannot acquire a decision role or lower effort")
        elif role["band"] == "economy":
            raise ValueError("economy roles require an economy binding; plan an explicit stronger-role fallback")
    default = policy["roles"][policy["default_role"]]
    require(default["band"] == "economy", "default subagent must be an economy execution profile")
    for value in policy["limits"].values():
        require(type(value) is int and value > 0, "invalid limits")
    return {"valid":True, "registry_hash":hash_object(registry), "policy_hash":hash_object(policy), "roles":len(policy["roles"])}


def resolve(name, registry, policy):
    role = policy["roles"][name]
    model = registry["models"][role["binding"]]
    return {"role":name, "binding":role["binding"], "model":model["model_id"], "reasoning_effort":role["effort"], "registry_hash":hash_object(registry), "policy_hash":hash_object(policy)}


def route(q, registry, policy):
    validate(registry, policy)
    fields(q, {"task_type", "difficulty", "risk", "verifiable", "bounded", "independent", "tool_sufficient", "failed_attempts", "failure_type", "escalation_evidence", "current_children", "children_started", "delegation_depth"}, {"current_model", "prior_role"})
    require(q["task_type"] in {"routine", "development", "review", "architecture", "research"}, "invalid task type")
    require(q["difficulty"] in {"routine", "hard", "exceptional"}, "invalid difficulty")
    require(q["risk"] in {"low", "medium", "high"}, "invalid risk")
    require(q["failure_type"] in {"none", "execution", "reasoning", "environment"}, "invalid failure type")
    for key in ("verifiable", "bounded", "independent", "tool_sufficient"):
        require(type(q[key]) is bool, "flags must be boolean")
    for key in ("failed_attempts", "current_children", "children_started", "delegation_depth"):
        require(type(q[key]) is int and 0 <= q[key] <= 100, "invalid counts")
    require(isinstance(q["escalation_evidence"], list) and len(q["escalation_evidence"]) <= 6, "invalid evidence list")
    for evidence in q["escalation_evidence"]:
        text(evidence)
    evidence = bool(q["escalation_evidence"])
    if q["failed_attempts"] > 0:
        require(evidence and q["failure_type"] != "none", "failed attempts require located evidence and failure type")
    if q["failure_type"] == "environment":
        return {"mode":"repair_environment", "reason":"先修复缺少工具/文件/权限/服务的问题；更多推理不能替代输入", "dispatch_performed":False}
    if q["tool_sufficient"] and q["failed_attempts"] == 0 and q["risk"] != "high":
        return {"mode":"direct_tool", "reason":"确定性工具可以完成，无需新模型调用", "dispatch_performed":False}
    prior = q.get("prior_role")
    require(prior is None or prior in policy["roles"], "unknown prior role")
    if q["difficulty"] == "exceptional":
        require(evidence, "max requires an explicit escalation rationale")
        role, reason = "acr_solver_max", "有证据支持的例外难题"
    elif q["difficulty"] == "hard":
        require(evidence, "hard-problem escalation requires concrete difficulty/failure evidence")
        role, reason = "acr_solver", "难题或连续两次失败，升级攻坚"
    elif q["failed_attempts"] >= 2:
        role = "acr_reviewer" if prior is None or policy["roles"][prior]["band"] == "economy" else "acr_solver"
        reason = "经济型执行失败先强模型审查；强模型仍失败再前沿攻坚"
    elif q["risk"] == "high" or q["task_type"] == "architecture" or not q["bounded"]:
        role, reason = "acr_architect", "架构、关键决策或边界不清"
    elif q["task_type"] == "review" or not q["verifiable"] or q["failure_type"] == "reasoning":
        role, reason = "acr_reviewer", "审查、不可直接验证或推理缺陷"
    elif q["task_type"] == "routine" and q["risk"] == "low":
        role = "acr_worker_max" if q["failed_attempts"] == 1 else "acr_worker"
        reason = "边界清楚的执行任务，经济型模型保持高 effort 下限"
    else:
        role, reason = "acr_developer", "日常开发或有界综合工作"
    order = policy["escalation_order"]
    if prior is not None and order.index(prior) > order.index(role):
        role, reason = prior, "同一逻辑子任务保持已升级档位；新任务或明确检查点才能重置"
    result = dict(resolve(role, registry, policy), reason=reason, input_features=q, dispatch_performed=False, quality_calibration="not_run")
    limits = policy["limits"]
    if q["delegation_depth"] >= limits["max_delegation_depth"]:
        mode = "return_to_parent"
    elif q["children_started"] >= limits["max_children_per_task"]:
        mode = "delegation_budget_exhausted"
    elif q["current_children"] >= limits["max_concurrent_children"]:
        mode = "wait_for_capacity"
    elif not q["independent"]:
        mode = "keep_with_coordinator"
    elif not q["bounded"]:
        mode = "define_bounded_decision_contract"
    else:
        mode = "delegate"
    # A low-capability parent must not pretend that a local path upgrades its model.
    current = q.get("current_model")
    economy_ids = {m["model_id"] for m in registry["models"].values() if m["tier"] == "economy"}
    if mode == "keep_with_coordinator" and current in economy_ids and policy["roles"][role]["band"] != "economy":
        mode = "strong_coordinator_required"
    result["mode"] = mode
    if mode == "delegate":
        result["spawn_parameters"] = {"model":result["model"], "reasoning_effort":result["reasoning_effort"], "fork_turns":"none"}
    return result


def handoff(q, policy):
    fields(q, {"task_id", "parent_task_id", "goal", "inputs", "allowed_tools", "write_paths", "external_effects", "acceptance", "budget", "stop_conditions", "result_contract"})
    for k in ("task_id", "parent_task_id", "goal"):
        text(q[k])
    for key in ("inputs", "allowed_tools", "write_paths", "external_effects", "acceptance", "stop_conditions"):
        require(isinstance(q[key], list) and len(q[key]) <= 20, "invalid handoff list")
        for item in q[key]:
            text(item)
    require(q["acceptance"] and q["stop_conditions"], "acceptance and stop conditions required")
    for path in q["write_paths"]:
        require(Path(path).is_absolute(), "write paths must be absolute")
    fields(q["budget"], {"max_repairs", "max_tool_calls", "max_seconds", "max_usd"})
    for key in ("max_repairs", "max_tool_calls", "max_seconds"):
        require(type(q["budget"][key]) is int and q["budget"][key] >= 0, "invalid budget")
    require(q["budget"]["max_repairs"] <= policy["limits"]["max_repairs_per_subtask"], "repair limit exceeded")
    require(q["budget"]["max_tool_calls"] > 0 and q["budget"]["max_seconds"] > 0, "bounded tool/time budgets required")
    usd = q["budget"]["max_usd"]
    require(usd is None or (type(usd) in (int, float) and 0 < usd < 10000), "invalid money budget; null means unknown")
    require(q["result_contract"] in {"artifact_evidence_v1", "decision_packet_v1"}, "unsupported result contract")
    require(len(canonical(q)) <= policy["limits"]["max_handoff_chars"], "handoff too large; curate context")
    return {"valid":True, "contract_hash":hash_object(q), "enforcement":"field_validation_only; parent enforces tool/side-effect/time permissions"}


def render(registry, policy):
    validate(registry, policy)
    output = {}
    shared = "你是有界子代理。严格依据交接任务执行；不得再派生子代理。只操作获准的工具、路径和副作用。遇到未知先报告，不扩大授权。按交接指定的 artifact_evidence_v1 或 decision_packet_v1 返回任务ID、公开结论、证据、通过/失败/未知的检查、阻碍及实际可观察用量；不保存私有思维链。不要自行晋升经验或修改路由、Skill、评测器。默认不写长期记忆，向主代理提出候选。"
    for name, role in policy["roles"].items():
        binding = resolve(name, registry, policy)
        # JSON quoted strings are valid TOML basic strings for these bounded values.
        values = {"name":name, "description":role["description"], "model":binding["model"], "model_reasoning_effort":binding["reasoning_effort"], "developer_instructions":shared + role["instructions"]}
        rendered = "# GENERATED: edit model-registry.json / subagent-policy.json, then regenerate.\n"
        rendered += "# registry_sha256=" + binding["registry_hash"] + "\n"
        rendered += "# policy_sha256=" + binding["policy_hash"] + "\n"
        rendered += "\n".join(k+" = "+json.dumps(v, ensure_ascii=False) for k,v in values.items())
        rendered += "\n\n[agents]\nenabled = false\n"
        tomllib.loads(rendered)
        output[name+".toml"] = rendered
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "route", "render", "handoff"])
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--request")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        registry, policy = load(args.root)
        if args.action == "validate":
            result = validate(registry, policy)
        elif args.action == "render":
            require(args.output, "output directory required")
            target = Path(args.output)
            target.mkdir(parents=True, exist_ok=True)
            profiles = render(registry, policy)
            for name, body in profiles.items():
                (target/name).write_text(body, encoding="utf8")
            result = {"profiles":list(profiles), "output":str(target.resolve())}
        else:
            raw = Path(args.request).read_text(encoding="utf-8-sig") if args.request else sys.stdin.read(32000)
            q = json.loads(raw)
            result = route(q, registry, policy) if args.action == "route" else handoff(q, policy)
        print(canonical({"ok":True, "result":result}))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(canonical({"ok":False, "error":str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
