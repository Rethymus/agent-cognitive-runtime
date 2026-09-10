# 自适应委派 v0.3

## 分类依据

读取 `policies/adaptive-routing.json` 的 feature_guidance 和 feature_values。以可定位的任务要求、代码依赖、工具观察和测试失败支持判断；模型输出的分数不代表校准概率。

简单执行须同时满足：需求明确、依赖局部、约束单一、方法已知、有确定性验收、操作可逆、风险低、处于执行阶段，且没有推理失败或两次失败。任一不满足并不证明模型能力不足；它意味着不能通过低成本执行门槛。信息 unknown 先做有界只读查证，探测后仍不明确再请求有界决策。环境故障先修环境，不能借此升级推理模型。

分类对象是一个可交接子任务及其当前阶段。复杂项目中的确定性执行仍可交给经济型；简单命令如果后果不可逆仍需风险核验。任务难度与风险是不同维度。

## 双向路径

- 强主代理：明确执行委派给 economy/xhigh，自身推进独立的架构、研究或验收工作。已有强主代理承担适合自己的决策，不重复创建同级强代理。
- 经济型主代理：复杂点交给 reasoner/high，只返回 decision_packet_v1；如有证据表明强审查仍失败，才考虑 frontier/xhigh，例外攻坚才 max。主代理仍保留任务所有权。
- 经济型子代理遇难题：向父代理返回阻碍、失败证据和所需决策。父代理从同一预算派发同级决策代理；子代理禁止再派生。
- 降级必须有已核验的 decision_ref、执行边界和验收条件；`checkpoint_verified` 是调用者声明，脚本不能判断引用内容的真伪。父代理承担实质核验。

当前宿主只允许在另有有用工作可并行时派生子代理。经济型主代理若完全被一个顺序难题阻塞，路由返回 needs_independent_work_or_host_handoff：保留检查点并明确宿主需要的交接，不能伪称当前主模型已切换或制造空转以绕过约束。当前模型的 effort 也不能由此脚本修改。

## 操作接口

使用 `scripts/adaptive_router.py plan|reserve|finish|status --request JSON文件`；JSON 也可从 stdin 传入。默认账本在 `$CODEX_HOME/cognitive-runtime/state/routing.sqlite3`，未设置 CODEX_HOME 时采用用户 .codex 目录。接口只产生决策和预留，不直接调用模型。

1. 建立稳定 task_id（当前任务 ID + 用户目标标识）；同一目标的全部子任务共享它。每次模型执行轮次使用唯一 request_id。
2. 参照 `examples/adaptive-request.json` 构造请求，plan 检查路径；信息不够先补齐证据。尽量用现有输入或确定性工具查证，不额外创建分类模型。
3. 只有 mode=delegate 才 reserve。只有 admitted=true 才启动该轮；显式使用返回的 model、reasoning_effort 和 fork_turns，并加上有界交接说明。admitted=false/already_reserved 不得重复派发，先核对真实运行状态。
4. 主代理继续独立工作；每个子任务限制工具、路径、外部副作用、时间、修复次数和输出。经济型子代理保持 xhigh/max，不得静默降档。
5. 对返回结果检查 scope_and_diff、acceptance_outcomes、evidence_freshness、declared_side_effects、remaining_unknowns。强主代理要核验关键断言及验收，不能把子代理的“全部通过”当证据；也不必无差别重做整个任务。返回决策要查约束、反例、依据，不能仅做措辞评价。
6. 用 finish 写 completed/failed/cancelled、实际可观察 usage_tokens（没有则 null）与 evidence_ref；随后查看 status。终态回执不可覆盖，允许完全相同的幂等重放。

预算按新子代理推理轮次计数：spawn、followup_task 和任何会触发新模型工作的一轮消息均须独立 reserve。已在执行轮次内的纯状态查询不新增推理预算；不要通过发消息让子代理继续工作来绕过计数。新轮次沿用适用角色，调用对应的宿主工具，而不是机械地每次创建新代理。

## 初始预算与边界

每个任务最多 4 次子代理推理轮次，其中强模型最多 2 次、frontier 最多 1 次、max effort 最多 1 次，同时在途最多 3 次。frontier 属于强模型子集。它们是可修改的保守起始值，不是经评测得到的最优阈值。

预约使用 SQLite BEGIN IMMEDIATE，避免并发抢占超过上限；取消或失败也保留调用额度，因为当前宿主不能证明该轮未消耗推理。修改策略只能收紧正在执行任务的预算，不能悄悄放大最初上限。预算耗尽则收束已验证成果、保留阻碍，不能自动将高风险工作强压给廉价模型。

这些上限只约束经过此接口的预约。它不是 Codex 全局调用拦截器：主模型思考、绕开接口的调用、真实输出长度及账户共享额度不受数据库硬性控制。未知 token 回执不能记作 0；status 的 observed_tokens 只是已知部分，须同时查看 token_total_complete。需要绝对 token/费用上限时，应接入宿主计费回执及可中止的统一派发层，当前版本没有实现。

派发与预约分属两个系统，不能保证崩溃场景端到端 exactly-once；已有预约先人工/工具核对，不能盲目重放。路由输入和证据引用也不是防篡改证明。当前环境可写文件，并不提供子代理的强沙箱。

## 维护与校准

模型 ID/支持的 effort 放 model-registry.json；职责与档位放 subagent-policy.json；门槛、预算和维度放 adaptive-routing.json。旧模型经验不自动迁移成新模型能力保证。变更运行回归测试、生成角色并验证宿主，再做任务族配对评测。calibration 当前关闭，禁止用历史成功几次自行改阈值。
学习闭环仍只保存候选；没有独立留出评测与发布器，不能把 critique 升格为 Skill 修改。细节见 [maintaining-subagents.md](maintaining-subagents.md)。
