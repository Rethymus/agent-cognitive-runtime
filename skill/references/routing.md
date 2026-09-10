# 路由入口

当前默认使用 [adaptive-routing.md](adaptive-routing.md)：证据门控、双向交接与事务预算。
`scripts/subagent_router.py` 保留模型绑定解析、角色生成、交接结构验证；其 `route` 是 v0.2 兼容接口，不能用它绕过 v0.3 调用预算。
`scripts/runtime.py route` 也是旧接口，不能作为当前子代理派发准入。
角色交接细节见 [subagents.md](subagents.md)；冲突时以当前 adaptive 路由和已解析模型注册表为准。
