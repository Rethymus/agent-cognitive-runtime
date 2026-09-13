# 架构与实现分层

Skill 负责按需指导，确定性脚本负责可执行约束，Codex 宿主负责模型和工具调用。调用者提供的来源、风险分类与验收结果仍需核验；字段通过校验不等于事实正确。

| 层 | 实现入口 | 责任 |
|---|---|---|
| 工作方式 | `skill/SKILL.md` | 任务约定、相关记忆、交接与验收 |
| 记忆 | `skill/scripts/runtime.py` | SQLite、CAS、幂等、TTL、依赖与遗忘 |
| 模型与职责 | `model-registry.json` / `subagent-policy.json` | 能力槽位、effort、角色生成 |
| 自适应路由 | `adaptive_router.py` / `adaptive-routing.json` | 证据门控、检查点、调用预约 |
| 宿主适配 | Codex subagent 工具 | 执行实际推理，返回公开结果 |
| 安装维护 | `scripts/manage.py` | 预览、备份、激活、诊断、回滚 |

本地持久化状态位于 CODEX_HOME/cognitive-runtime/state：memory.sqlite3 存记忆，routing.sqlite3 存调用预约。代码更新不迁移或恢复数据库。公开项目不包含真实用户记忆、机器安装回执或原附件全文。

目标状态机是 Classify → Retrieve → Contract → Plan → Act → Verify → Reflect → Evaluate → Promote。这些是按需选择的环节，当前 Skill 不要求依次执行；脚本验证 Task 检查点；末端只允许候选保存，独立 Evaluate/Promote 服务尚未实现。不能将概念图描述成后台调度器。

完整目标设计见 [历史技术方案](research/foundations.md)，其 schema 和目标发布协议存放在 design；这些文件用于后续实现，不安装到每次模型上下文，也不等于本地 CLI。
