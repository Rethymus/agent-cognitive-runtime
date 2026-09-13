# Runtime 维护

用户已授权本次维护时，直接完成范围内的修改、验证和回滚准备。候选经验不能自行更新 Skill 或路由。

## 修改位置

| 变更 | 位置 |
|---|---|
| 模型绑定、支持的 effort | `policies/model-registry.json` |
| 角色、默认 effort、交接限制 | `policies/subagent-policy.json` |
| 委派门控与调用预算 | `policies/adaptive-routing.json` |
| 路由实现、宿主适配 | `scripts/adaptive_router.py`、`scripts/subagent_router.py` |
| 记忆接口与数据语义 | `scripts/runtime.py`、[local-runtime.md](local-runtime.md) |
| 原生角色 | 用 `subagent_router.py render` 生成 `~/.codex/agents/acr_*.toml`，不手改生成文件 |

保留用户指定的主代理、私有连接及分工偏好：经济型子代理 xhigh/max；强模型日常 medium/high、攻坚 xhigh/max。这是用户配置，不代表各任务的最优档位。仅在修改模型绑定或兼容性时核对当前官方资料和宿主能力；纯文案精简不要求重查模型价格或可用性。未验证的能力不猜测，新的供应商或协议需要适配器实现。

## 按变更验证

- **指令文案**：检查差异、引用、技能元数据，以及授权、隐私、预算和工作流的一致性。无需重跑无关代码测试或模型评测。
- **角色或路由配置**：验证受影响的配置和路由；生成角色并比较差异。改变宿主加载或模型绑定时做有界实际调用，明确本次调用验证的范围。
- **代码或存储语义**：运行受影响的测试及项目必需检查；涉及记忆隔离、更新或遗忘时覆盖相应回归。
- **能力或成本结论**：用相同输入、验收与预算进行任务族配对评测，按要回答的问题确定样本量。没有数据就保留 `not_calibrated`，不把调用成功当成能力或成本优势。

通过相应检查后，仅在新变更、失败或未解决问题出现时追加验证。实际调用只用宿主已提供的工具，不新增外部 API 计费服务。

## 变更与回滚

修改前保存受影响文件的备份和哈希，记录来源、理由、差异与验证结果。替换前检查并发修改，避免覆盖他人工作；失败时撤回本次变更，保留用户后续修改。回滚不恢复或删除记忆、遗忘记录和路由账本，避免被遗忘内容复活。

维护仓库：https://github.com/Rethymus/agent-cognitive-runtime 。安装回执 `packages/latest.json` 的 `source_checkout` 指向来源；源目录不可用时重新获取仓库。仓库 `scripts/manage.py` 提供 install、doctor、rollback；先预览，再按已授权范围应用。`--activate` 更新全局标记块，`--with-roles` 生成角色；本地修改先比较合并，勿盲目使用 `--adopt-existing`。回执与备份存于 `CODEX_HOME/cognitive-runtime/packages`，不伪造旧回执。

## 宿主与评测边界

路由器只控制通过其接口的预约，不切换主模型，也不提供全局 Token/费用上限。以当前宿主工具声明核实角色与显式参数的优先级；按 [adaptive-routing.md](adaptive-routing.md) 核对实际派发的模型/effort。子代理禁止再委派，写入范围靠交接约束，不能声称具有强沙箱隔离。

评测区分已观察结果与未知结果；费用未知不能记作 0。历史路由只观察被选中的模型，有选择偏差，不能据此断言其他模型失败。校准与经验晋升仍关闭；简化旧流程同样需要当前任务的证据，不把一次成功推广成普遍保证。

## 新资料与旧规则复核

根据论文、模型卡、语料、工具文档或执行示例维护时，在源仓库阅读 `docs/material-evolution.md`，用 `scripts/materials.py` 建立资料包并检查来源、缺口和影响。保留 README 的直接论文依据与稳定来源 ID。

模型更新也要复核旧规则的适用范围，见源仓库 `docs/instruction-evolution.md`：硬边界保留，工作流程按任务需要使用；增减规则的质量与成本结论需独立对照。资料工具的实验建议不构成额外审批，也不要求纯文案修改付费运行模型；用户授权维护、程序验证和模型效果证据分别记录。
