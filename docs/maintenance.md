# 供维护 Agent 使用的更新流程

明确改动范围。行为变化核对 VERSION、README 与 [实现状态](implementation-status.md)，单处文案只读相关材料。当前用户授权优先，历史设计不产生额外权限。

新模型、论文、语料或执行示例使用 [资料迭代入口](material-evolution.md)；规则精简参考 [规则演进](instruction-evolution.md)。保留 README 论文依据及来源 ID，纠正解释或标注撤回，不删除证据。

| 变更 | 定位与验证 |
|---|---|
| 指令或文档 | 差异、引用、Skill 格式与必要边界；不重查无关价格或运行能力评测 |
| 模型与角色 | registry/policy、官方与宿主支持、角色生成和实际调用；新协议需适配器 |
| 路由或记忆代码 | 受影响测试及仓库必需检查，存储变化覆盖隔离、遗忘和冲突 |
| 质量或成本结论 | 冻结输入、模型/effort、预算、环境与独立验收后配对评测；无数据标未校准 |

模型复核日期查证后更新，新模型不继承旧质量与规则收益。无需变化的预算和用户档位保持原样。检查通过后，仅在新改动、失败或未解决问题出现时扩大验证。

代码或配置发布运行完整单元测试与仓库检查；纯文档发布运行仓库检查，Skill 入口另做格式校验。CI 保留全套检查。

```sh
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/check_repository.py
python -X utf8 scripts/manage.py install
```

最后一条只预览。比较仓库、已安装文件和回执，本地改动先合并，保留较新资料入口。勿用 `--adopt-existing` 掩盖未知差异。用户已授权安装维护时直接完成合并、安装和诊断；仓库发布本身不表示更新了真实用户安装。

更新实现状态与 CHANGELOG，记录提交、验证和回滚路径。安装用 `--apply`，按用途选择 `--activate`/`--with-roles`，不改主模型或权限。`scripts/manage.py rollback` 默认预览；后续修改保留，数据库和遗忘不回滚。候选经验不是用户维护授权。
