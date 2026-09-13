# 安装、诊断与回滚

需要 Python 3.11+；Git 用于获取及更新仓库。标准库足以安装和运行。先确认实际 Codex 宿主支持 Skill；跨模型子代理依赖宿主能力，安装 Python 文件不能补出缺少的工具。

## 默认安装

```sh
git clone https://github.com/Rethymus/agent-cognitive-runtime.git
cd agent-cognitive-runtime
python -X utf8 scripts/manage.py install
python -X utf8 scripts/manage.py install --apply
python -X utf8 scripts/manage.py doctor
```

Windows 如果 `python` 不可用，可将上述命令的 `python` 换成 `py -3.12` 或已安装解释器的绝对路径；macOS/Linux 通常也可使用 `python3`。不要把命令中的示例路径当成本机真实路径。

安装位置取 `CODEX_HOME`，未设置时使用用户主目录下 `.codex`。默认仅复制到 `skills/agent-cognitive-runtime`；不会修改主模型、模型默认值、权限或数据库。

## 可选全局入口与原生角色

先让当前 Agent 核对 `skill/policies/model-registry.json` 的 model ID、effort 和宿主原生角色格式。注册表过期时先核对官方/宿主资料后更新日期，不能只延长日期绕过检查。

```sh
python -X utf8 scripts/manage.py install --activate --with-roles
python -X utf8 scripts/manage.py install --activate --with-roles --apply
```

`--activate` 仅新增或替换全局 AGENTS.md 内的 ACR 标记块；块外用户文字保留。本地修改或删除受管块时会拒绝覆盖；审查合并后才能显式采用 `--adopt-existing`。新回执单独记录块哈希；旧回执只有整文件哈希时无法区分块内外修改，保守要求审查采用。`--with-roles` 生成八个角色文件，但不启用未知宿主的功能开关，不修改 config.toml。宿主只接受显式 model/effort 时，按路由结果传参；不能声称命名角色已被加载。

默认子代理角色为 economy/xhigh，修复角色 economy/max。角色示例仅来自 2026-09-09 研究环境。其他账号、模型供应商或宿主版本需要更新绑定/适配器，不能把示例 ID 当通用 API 标识。

## 已有安装

相同文件重复安装不产生新备份。安装器管理的未修改文件可更新；遇到陌生或本地修改文件会拒绝覆盖。先比较 diff，完成用户授权的合并后才考虑 `--adopt-existing`；此选项会备份并替换待安装的冲突文件，不能拿它掩盖不理解的改动。

此前的本机 v0.3 安装包没有本仓库的安装元数据，迁移时属于已有安装。先预览差异与备份，不要直接把旧的机器回执复制进仓库。

## 隔离验证

可用 `--home` 指定空的试验目录：

```sh
python -X utf8 scripts/manage.py install --home work/demo-home --activate --with-roles --apply
python -X utf8 scripts/manage.py doctor --home work/demo-home
python -X utf8 scripts/manage.py rollback --home work/demo-home
python -X utf8 scripts/manage.py rollback --home work/demo-home --apply
```

该 home 是测试状态根目录，不会改变真实 CODEX_HOME。工作目录 `work/` 已被 git 忽略。

## 诊断与回滚

doctor 检查 Python、安装文件与当前 checkout 是否匹配、注册表日期和格式；不读取数据库正文、不调用模型、不验证账户额度。退出码：0 通过，1 存在诊断缺口，2 输入/文件操作错误。

安装回执和原文件备份在 `CODEX_HOME/cognitive-runtime/packages/`。`rollback` 默认预览最近一次安装，`--apply` 恢复仍匹配安装后哈希的文件；后续修改保留并报告。部分回滚应先处理差异，不要反复强制覆盖。回滚不修改 state 下的记忆与路由账本，也不撤销遗忘。

安装器有协作锁、写入前哈希核对、单文件原子替换与失败恢复；它不是对任意外部进程的完整文件系统事务。进程崩溃留下 `.lock` 时，先核对已无安装进程与回执，再由维护者清理锁，不能盲目并行重试。
