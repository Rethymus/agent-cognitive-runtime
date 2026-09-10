> 目标协议设计，不是当前本地接口的实现声明。实际调用见 [当前协议](../protocol.md)。

# 接口与发布协议

## 实现范围

本文保留 v0.1 的目标工程契约。当前本地版已有 SQLite 记忆与调用预约，但未实现本文完整服务接口、常驻模型客户端或独立发布器。接口名为模型无关的逻辑名称，不假设当前宿主已支持这些工具。

| 接口 | 请求 | 响应 | 服务端不变量 |
|---|---|---|---|
| memory.retrieve | principal、scope、query、purpose、token_budget、as_of | entries、revision/hash、context_manifest | 授权与失效过滤先于排序；candidate 不注入执行流程 |
| memory.observe | run_id、record、expected_revision、idempotency_key | receipt_id、new_revision、content_hash | 来源由运行时校验；更新/事件在同一事务 |
| memory.forget | principal、target_ids、scope、request_ref | deletion_epoch、purge_report | 传播到派生、索引、缓存、导出；备份恢复服从删除日志 |
| runtime.checkpoint | run_id、sequence、contract_revision、state、artifact_refs | checkpoint_ref | sequence 单调；不写私有推理 |
| tools.execute | capability_id、arguments、authorization_ref、idempotency_key | observed_result、receipt、usage | actor 无权自行增权；副作用超时可核对 |
| lesson.propose | lesson、base_hash、candidate_hash、evidence_refs | candidate_id、status=candidate | 不能写 active Skill；明确反例和 scope |
| evaluation.run | candidate_id、artifact_hash、protocol_id、baseline_hash | signed_eval_receipt | 独立工作区；固定输入和 grader；保留集不可向 actor 暴露 |
| review.critique | contract、public_artifact、observations、budget | critique | 无隐藏推理要求；评审身份由 adapter 确认 |
| release.publish | candidate_id、eval_receipt_ids、review_id、expected_active | release_id、active_hash、audit_receipt | 只有 publisher 身份；哈希和配置完全匹配；门禁全通过 |
| release.rollback | target_release、expected_active、reason、principal | new_active、audit_receipt | 不得指向撤销或依赖失效版本；应用当前删除 epoch |

## SQLite 建议

tables: memory_records、memory_revisions、provenance、dependencies、tombstones、runs、events、tool_receipts、lesson_candidates、evaluation_receipts、releases、active_releases。

唯一键：(tenant_id,id)、(run_id,sequence)、(principal,idempotency_key)。索引至少覆盖 scope/status/expiry、depends_on 的反向查询与实体别名。全文检索只是候选排序入口，不替代访问控制。只有 publisher 可写 active_releases；只有 evaluator 可写 trusted evaluation receipt。

数据库文件如果 actor 可以直接读写，则这些角色限制不成立。生产实现应以单独服务进程/操作系统身份隔离数据库和密钥；不把几个目录名视为安全隔离。评测工作区不挂载 gold labels、release signing keys 或生产数据。

## 发布事务

1. 对候选资源作规范化内容哈希，递归列举依赖。拒绝路径穿越、外部符号链接和未声明可执行依赖。
2. 核验 verifier/publisher 信任根，禁止信任 JSON 中自称 verifier 的字段。签名服务密钥不在 actor 环境。
3. 验证所有回执的 candidate_hash、baseline_hash、protocol_hash、dataset_hash、grader_hash、scope 和 model 配置；任一变更使旧回执失效。
4. 运行 promotion policy；quality 与efficiency 两路径分别验证，critical regression 一票阻断。缺失值一律不通过。
5. 创建不可变 release manifest，列资源 hash、policy hash、回执和依赖；写临时目录并完整校验。
6. 事务中 CAS 切换 active 指针、添加 release event。若 active 被并发更新，重评依赖，不覆盖。
7. 通过 shadow/canary 后标为稳定；发现撤销条件时 CAS 回滚到仍有效的 release。

版本回滚是行为资产回滚。与用户事实更新、删除日志分离，不能整个数据库倒回旧快照让已忘记的数据重现。

## 错误枚举

SCHEMA_INVALID、SCOPE_DENIED、STALE_REVISION、DEPENDENCY_CHANGED、MEMORY_EXPIRED、SEMANTIC_CONFLICT、BUDGET_EXCEEDED、TOOL_UNKNOWN_OUTCOME、VERIFIER_UNAVAILABLE、INSUFFICIENT_EVIDENCE、RECEIPT_INVALID、EVAL_CONTAMINATED、RELEASE_REVOKED。

只有明确可恢复的机械故障自动重试。SEMANTIC_CONFLICT 保留证据并寻求事实澄清；VERIFIER_UNAVAILABLE 不得降格为通过；TOOL_UNKNOWN_OUTCOME 先核对；INSUFFICIENT_EVIDENCE 保持未发布状态。
