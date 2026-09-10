# 供维护 Agent 使用的更新流程

先读 VERSION、README、[实现状态](implementation-status.md)和目标变更。不要把历史设计或测试数当成当前产品承诺。

1. 读取当前注册表、角色与自适应配置，核对宿主官方信息与实际模型目录。
2. 模型替换主要修改 skill/policies/model-registry.json；职责和 effort 修改 subagent-policy.json；预算/特征修改 adaptive-routing.json。新供应商需要新的宿主适配器，不能只改字符串。
3. 模型复核日期只能在事实核验后更新。模型替换不自动继承旧模型的能力假设和路由阈值。
4. 运行单元与安装测试、仓库检查；涉及模型效果时运行有限配对任务并记录真实用量。tests 的固定日期是为了复现程序行为，不绕过真实运行日期检查。
5. 查看安装预览，保留冲突文件和用户改动；用户明确维护授权覆盖时完成合并、安装和诊断。每次文件变更保留回执。
6. 更新 README、实现状态、CHANGELOG，删除过时说明。代码变化与文档承诺对应，未实现功能仍标未实现。

```sh
git pull --ff-only
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/check_repository.py
python -X utf8 scripts/manage.py install
```

上面不执行安装写入。确认任务已授权且 diff 清楚后使用 --apply，必要时保留原有 --activate/--with-roles 选项。不强制覆盖用户提交，不自动修改预算以让失败测试通过。

回滚安装用 scripts/manage.py rollback，默认预览。数据库不回滚；不要从旧备份复活已遗忘的数据。自主生成的候选经验不能当作用户维护授权。
