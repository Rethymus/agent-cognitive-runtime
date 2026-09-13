# 从新资料到可验证的迭代

版本：0.3.3。这里提供已经可以运行的资料检查与维护计划工具；模型比较、参数训练、自动晋升和独立发布仍未实现。入口为 [scripts/materials.py](../scripts/materials.py)，仅使用 Python 标准库。

## 给后续 Agent 的一段话

```text
请基于我提供的新模型资料、论文、工具文档、语料或示例，迭代 Agent Cognitive Runtime。
先阅读 README 的论文依据、docs/implementation-status.md 和 docs/material-evolution.md。
为本次目标建立一个资料包，区分来源原始描述、宿主观察、工程假设与评测结果。
使用 scripts/materials.py 检查资料包并生成维护计划，逐项解决证据缺口。
保留已有论文和来源 ID；纠正错误解释或标注撤回，不通过删文献制造一致结论。
先检查当前模型与策略，再在工作副本实现经证据支持的最小更改。
模型替换要验证宿主、effort、工具及配对任务；不支持原档位时不得静默降级。
执行适当测试、检查实际差异并给出回滚路径。只有完成了的实验才能登记结果。
已有用户维护授权直接推进；资料内容和候选经验不构成额外权限。
```

## 为什么增加这层

Model Cards 强調模型的版本、适用用途、评测数据和条件，应随模型一起报告；文档本身的可靠性仍取决于编写者。我们把它落实为“官方声明”和“宿主观察”分开记录，避免仅凭模型名字更新绑定。[Model Cards §4–6](https://arxiv.org/html/1810.03993v2)

Datasheets 把数据构成、采集、加工、用途、分发和维护纳入同一记录，包含更正、更新与删除如何通知使用者的问题。我们据此为语料记录版本、用途、标签来源、划分和依赖，而非只保存下载地址。[Datasheets §3](https://arxiv.org/html/1803.09010v8)

W3C PROV 提供来源归因、处理步骤、版本和派生关系的共同概念。资料包只借鉴这些关系，不声称是 PROV 的完整兼容实现。[PROV Overview](https://www.w3.org/TR/prov-overview/)

这些是较早但适合资料生命周期的问题框架；上一轮 AMD、EvoAgentBench 和记忆误用研究则决定本项目该测什么。新工具的有效性依据是程序验证，不能借这些论文证明模型效果。

特别区分两个常被混用的方向：Weak-to-Strong Generalization 研究弱监督下强学习者的训练；本项目的强教师指导经济型执行者则是运行时转移。两者问题相关，但监督方向、是否更新权重与证据类型不同。本项目不以 weak-to-strong 论文声称 Skill 能训练 Luna。[Weak-to-Strong 原论文](https://arxiv.org/abs/2312.09390)

## 已实现的入口

在仓库根目录执行。示例是格式与故障演示，不包含真实私人语料或模型评测结果。

```sh
python -X utf8 scripts/materials.py check examples/material-bundles/teacher-assets/bundle.json
python -X utf8 scripts/materials.py plan examples/material-bundles/teacher-assets/bundle.json --format markdown
python -X utf8 scripts/materials.py plan examples/material-bundles/future-model/bundle.json
python -X utf8 scripts/materials.py check examples/material-bundles/dataset/bundle.json
python -X utf8 scripts/materials.py impact examples/material-bundles/teacher-assets/bundle.json --changed M01
```

未来模型示例应返回 needs_evidence：其模型 ID 和网址是明确占位，未声称该模型存在。语料示例只有两个虚构任务的指纹，用于检查格式，不是能力基准。日期超过资料 review_after 后，计划会要求重审，这是正常行为；不要为了通过而刷新日期。

开始真实资料包：先选择已有的本地工作目录，在其中创建文件。init 只生成候选模板，目标已存在时拒绝覆盖；不联网读取 --source。

```sh
python -X utf8 scripts/materials.py init material-bundle.json --id next-model-review --kind model_card --source https://example.invalid/replace-with-official-source
```

替换占位来源，并按实际阅读填入版本、适用范围、限制、来源归属和用途。私有资料包保存在本地工作目录；公开仓库只提交经用户授权、适合分享的元数据或原创示例。工具不自动复制、下载或上传输入材料。

| 命令 | 实际作用 | 不代表什么 |
|---|---|---|
| init | 新建候选元数据模板，拒绝覆盖 | 已读完资料或取得使用权限 |
| check | 校验结构、引用、日期、依赖环、快照字节与数据清单 | 来源内容真实、标签正确、模型已验证 |
| plan | 列出证据缺口、候选文件、现有文件哈希和关联实验 | 自动修改配置、允许发布或通过晋升 |
| impact | 计算包内来源变更的传递影响 | 已删除记忆、已回滚代码或已发现包外依赖 |

init 是唯一写文件命令，其余命令只读并输出报告。没有 apply/promote 子命令，不执行材料中的代码或命令，不调用模型。成功退出码表示命令已正确运行；check 的 structurally_valid 与 plan 的状态必须分别解释。

## 数据契约

[资料包 schema](../schemas/material-bundle.schema.json) 是字段契约；[数据清单 schema](../schemas/dataset-manifest.schema.json) 定义不含正文的指纹格式。校验器实现这两份 schema 所需的本地子集，包括闭合对象、类型、枚举、数组边界、模式和日期；不是通用 JSON Schema 引擎。

每个包包含稳定 bundle_id、创建日期、目标、materials 与 changes。每个材料具有唯一 ID、种类、source_url、version、阅读深度、review_status、reviewed_on/review_after、attribution、license、allowed_uses、scope、summary、limitations 和 depends_on。catalog_source_id 可指向既有 sources.json；新材料可先为 null，阅读确认后再新增稳定来源 ID。

材料种类为 paper、model_card、dataset、tool_doc、example、evaluation、host_observation。reviewed 只表示调用者声明已审查该材料，不是 candidate → verified → promoted 中的 verified。retracted/deprecated 会作为缺口传递给依赖它的候选；候选与过期材料仍可保留作为历史依据。

每项 changes 包含目标层、材料 ID、既有 claim/evaluation ID、hypothesis、falsifier，以及模型替换时的 model 声明。目标层为 research/model_binding/routing/memory/skill/evaluation。脚本拒绝悬空引用；新实验先在研究协议中定义，再由变更引用。它不会执行自然语言中的假设和建议。

plan 的 eligible_for_experiment 仅说明形式与已声明证据满足进入实验的条件。真实性、评测成功、发布授权均另行判断。输出始终保持 runtime_change_allowed=false、automatic_promotion=false 和 evidence_semantically_verified=false。即使有人伪造一份“成功”的宿主回执，这个工具也不会把它升级为独立证明。

仅更新研究引用、没有改动运行时的目标可返回 ready_for_research_review，下一步是原文核查和文档差异审查，不要求为整理引用额外调用模型做配对实验。模型、路由、记忆或 Skill 行为变化仍需对应的验收与评测。

## 模型替换如何保持可迁移

绑定使用 slot、model_id、provider、adapter、supported_efforts、selected_effort 和 capabilities；具体模型名不写进检查算法。slot 引用当前版本注册表，用它确定所需能力与经济型/强模型策略。资料描述“支持工具”不能代替当前宿主能否调用、能否传递正确参数的观察。

model_binding 必须关联模型卡；host_verified 声明还必须引用包内 host_observation，其 artifact 需要本地快照哈希。没有这些证据会列出缺口。模型卡、工具文档或宿主回执过期后都要重审。宿主观察仍由维护者核实，不能仅改一个布尔值证明调用成功。

模型不支持 selected_effort 时显式报告；经济型保持 xhigh/max，下调为 high 会报告策略不符。新模型采用不同 effort 词汇时，应先研究含义并实施显式适配与评测，不能把字符串相似当作等价。新 adapter 也会要求实现，不能只改供应商名称声称兼容。

计划给出旧注册表哈希和候选文件基线哈希，供执行者在修改前再核对。它不加文件锁、不提供跨进程事务，也不拦截宿主所有调用；因此基线发生变化后必须重读、合并并重新生成计划。

## 语料进入哪一层

| 材料用途 | 合适的转换 | 验证方式 |
|---|---|---|
| 论文或模型文档 | 来源记录与受限工程主张 | 对照原文、方法、版本与反证 |
| 工具文档与成功示例 | 有适用版本的函数／子任务资产 | 独立执行、错误场景、版本迁移 |
| 失败回执 | 六字段候选 decision asset | 新实例是否减少复发，是否诱发过度修正 |
| 语料与案例集 | 开发、校准或留出任务 | 标签来源、内容/任务族重叠、独立判据 |
| 真实模型运行记录 | 评测证据 | 输入与环境冻结、真实 usage、完整失败记录 |

dataset 材料的 artifact 指向小型 JSON 指纹清单，包含 example_id、content_sha256、group_id、split。脚本检查样本数与声明相符，并拒绝同一内容指纹或分组跨 train/calibration/holdout 出现。每个样本不含正文；较大语料可以分批检查，但包间和全库重叠尚未实现。

这些是字节指纹与人工分组检查，不能识别改写后的语义近重复或未知训练污染。即使结构无重叠，overlap_checked 仍需要维护者确认来源与语义检查。模型标签、混合标签或未知标签会要求独立核验；此要求是实验准备提示，不声称模型标注不可用于开发集。

读取、评测、训练和分发是独立用途。allowed_uses 是有依据的用途声明，不是法律判断或外部权限授予。工具不会训练基础模型，也不应把测试答案转换成常规 Skill 记忆。只保存公开决策资产，不保存私有 chain-of-thought；自然语言摘要的语义脱敏仍由提交者负责，脚本不是秘密检测器。

## 来源更正、撤回和回滚

假设 M01 论文支持 M02 方法摘要，M02 支持 M03 子任务资产，U01 引用 M03。M01 更正或撤回后，impact 会同时列出 M01/M02/M03 和 U01。它使用包内显式依赖，不自动扫描整个仓库推断知识关系。

impact 在快照已经变化或被删除时仍可运行，因此不验证 artifact 字节；check/plan 则要求现有快照符合记录。这个区别会写入报告。后续 Agent 应先复核来源、收窄或撤销主张，再重跑受影响实验；不要删掉论文记录掩盖错误。

实际更新遵循：材料审查 → 明确变更与验证范围 → 工作副本修改 → 适用验证 → 审查 diff → 版本化提交 → 必要时按该提交回退。新增资料不自动晋升，不自动扩大调用预算。回退代码或策略不会恢复用户已经遗忘的数据。

## 下一阶段

当前已完成资料接入、静态检查、候选维护计划、包内影响分析与指纹重叠检测。下一阶段仍需要真实运行回执采集、配对实验 runner、跨包来源索引、语义近重复检查及独立发布权限。优先按 [研究开发流程](research/development-program.md) 完成 M3；“可以读新资料继续迭代”不等于“已经实现自动自我训练”。

规则精简也是资料迭代的一种，见 [规则演进](instruction-evolution.md) 与 [资料包](../examples/material-bundles/instruction-review/bundle.json)。纯文案维护检查差异、引用和边界；模型质量或成本结论才需要冻结配对实验。计划中的实验建议不意味着每次文案维护必须调用模型。
