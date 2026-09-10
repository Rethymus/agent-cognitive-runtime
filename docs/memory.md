# 记忆与候选经验

User、Project、Episodic、Failure、Procedural、Skill Library、Evaluation 七层，加 Task 检查点。每条记录有来源、版本、到期与复核时间；可关联文件哈希、父记忆版本。变化导致依赖失效，避免陈旧经验继续进入正常上下文。

默认仅召回当前项目相关、有效的少量记忆；跨项目用户记忆显式选择。Failure、Procedural、Skill Library 及模型推断以 candidate 保存，正常检索默认排除。confidence 表示来源归因，不能变成事实真值概率。

遗忘删除正文并级联清除依赖，保留不含正文的墓碑以防重试复活。代码回滚不恢复记忆库。到期清理在访问/显式 gc 时执行，没有后台定时器。

保存公开的 Problem Pattern → Decision → Evidence → Failure Mode → Heuristic → Validation Result。自我反思和 Teacher critique 不能单独晋升 Skill；当前 verify_candidate/promote 接口拒绝执行。

真实动作、默认 TTL 和精确字段见 [本地接口](../skill/references/local-runtime.md)。目标版更完整的记忆 schema 见 docs/design，不能混用两套格式。
