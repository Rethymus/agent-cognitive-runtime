# codex-with-chatgpt 参考范式分析

研究日期：2026-09-09。参考仓库：[XiaoDuoYa/codex-with-chatgpt](https://github.com/XiaoDuoYa/codex-with-chatgpt)。固定提交：[`a9f91cd98df1bc82686f57d5bc2b2993394c93be`](https://github.com/XiaoDuoYa/codex-with-chatgpt/tree/a9f91cd98df1bc82686f57d5bc2b2993394c93be)。

本次阅读双语 README、架构、协议、安全与故障排查文档，并检查 execution/records.ts、session/state.ts、mcp/server.ts 的相关实现及测试目录。没有运行其浏览器、OAuth、隧道或端到端安装，因此不认证它的运行或安全承诺。

## 对外表达

README 用简短定位句引入，依次回答问题、产品身份、安装、使用、原理、边界和开发。它给非技术用户可交给 Agent 的完整安装请求，并让详细文档承担维护信息。借鉴的是这条用户路径，本项目重新撰写了中文首页与英文入口。

## 工程组织与迁移

| 参考项目的机制 | 本项目采用方式 | 差异 |
|---|---|---|
| Skill 是用户操作入口，运行代码独立 | skill 安装内容与 scripts、docs、tests 分离 | 本地 Python 内核，无 Node/浏览器桥 |
| 控制消息与按需取证分开 | 短交接合约引用产物、范围及验收 | 当前共享本地文件，无远程 MCP 数据通道 |
| 执行记录供审查读取 | 回执、文件与测试证据独立于结论 | 调用者提供的回执仍需父代理核验 |
| 工作区绑定与会话检查点分离 | 项目作用域记忆与 Task 检查点分离 | 不能继承其 OAuth 工作区隔离保证 |
| doctor、恢复与维护入口 | 通用 install/doctor/rollback | doctor 不自动联网修复或更换模型 |

## 不迁移的产品假设

该项目通过网页 ChatGPT 承担思考，其额度、浏览器与公网连接属于特定产品方案。本项目使用宿主子代理，不承诺使用网页版额度，也不引入隧道、OAuth、远程凭据或浏览器控制。

参考 README 描述自动更新和端到端状态；本项目只写当前真实能力，不沿用未经实现的自动更新、无需操作或完全隔离保证。采用前需把文字主张与服务代码、测试和实际运行分开核对。

本仓库没有复制参考项目的实现代码或长段 README，仅借鉴结构与通用设计思想；参考项目保持其 MIT 许可证和原作者归属。
