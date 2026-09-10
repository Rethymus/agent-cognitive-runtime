# 故障排查

先运行 `python -X utf8 scripts/manage.py doctor`，区分文件安装问题、注册表问题和宿主模型调用问题。

| 现象 | 处理 |
|---|---|
| Skill 未发现 | 核对 CODEX_HOME 和 skills 路径，在新会话显式调用 Skill |
| Python 命令不存在 | 使用 python3、py -3.12 或实际解释器路径；要求 3.11+ |
| registry review required | 核对当前宿主/官方模型能力后更新注册表；不能只延长日期 |
| 模型 ID 不支持 | 选已核实绑定并重新验证角色，不猜测别名或静默降低 effort |
| unmanaged or locally modified target | 查看本地差异；完成明确合并后才用 --adopt-existing |
| .lock 已存在 | 核对是否还有安装进程；崩溃后检查回执再清理，不抢占锁 |
| budget exhausted | 收束已验证成果，保留阻碍；不换 task_id 规避限制 |
| already_reserved | 核对真实派发状态；不要重复启动，预约不等于模型已执行 |
| needs_independent_work_or_host_handoff | 当前宿主无法在此顺序场景自动升级主模型，保存公开交接点 |
| 记忆过期／依赖变化 | 核对当前事实后重写，不盲目续期或跳过来源 |
| 回滚报告保留文件 | 用户后续修改被保留；先审查差异，不能直接覆盖 |

Token 统计为 null 表示未知，不能解释为免费。安装诊断不验证模型账户或读取记忆内容；宿主错误应提供最小化的错误摘要。
