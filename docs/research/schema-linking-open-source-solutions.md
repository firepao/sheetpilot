# 自然语言业务词绑定真实字段：开源方案调研

## 1. 问题与范围

SheetPilot 当前问题是：Agent 在制定计划前已经获得工作表、表头、类型和有限样例值，但仍不能稳定地把用户业务词（如“区域”“产品类别”“销售额”）绑定到真实字段（如“所属片区”“商品大类”“实收金额”）。

本报告只考察 GitHub 官方仓库、论文官方代码和项目官方文档，重点覆盖：

- Text-to-SQL schema linking 与字段消歧；
- 表格问答中的语言到表格 grounding；
- semantic layer / metrics layer；
- Agent 规划中的结构化中间表示；
- 可迁移到 SheetPilot 现有 Field Binding 协议的机制。

调研结论不是“再强化一次总 Prompt”。主流开源系统普遍把问题拆成独立环节：

```text
schema/value grounding
-> 候选字段检索或排序
-> 显式 schema links / binding IR
-> 查询或计划生成
-> 执行与验证
```

## 2. 一手来源方案

### 2.1 RAT-SQL：关系感知的 schema linking

来源：

- 官方仓库：[microsoft/rat-sql](https://github.com/microsoft/rat-sql)
- 论文：[RAT-SQL: Relation-Aware Schema Encoding and Linking for Text-to-SQL Parsers](https://arxiv.org/abs/1911.04942)

RAT-SQL 不把 schema linking 简化为字段名字符串匹配。它将问题 token、表、列以及主外键关系组织成图，并显式编码 question-column、question-table、column-table、外键、名称匹配和值匹配等关系，再由 relation-aware Transformer 联合建模。

可迁移机制：

- 字段判断应联合使用用户词、列名、值和表结构，而非只看表头；
- “用户词与字段”“样例值与字段”“字段与工作表”应作为不同类型的证据；
- 规划器可以接收显式关系，而不是一段未经组织的工作簿文本。

局限：这是训练型 Text-to-SQL 模型，官方实现依赖 Python、Stanford CoreNLP/JVM 和训练数据；BERT 配置的硬件成本较高。Excel 通常又缺少可靠的主外键元数据，因此完整移植不合适，主要适合作为关系建模原则。

### 2.2 RESDSQL：将 schema item ranking 与生成解耦

来源：

- 官方仓库：[RUCKBReasoning/RESDSQL](https://github.com/RUCKBReasoning/RESDSQL)
- 核心源码：[schema_item_classifier.py](https://github.com/RUCKBReasoning/RESDSQL/blob/main/schema_item_classifier.py)
- 论文：[RESDSQL: Decoupling Schema Linking and Skeleton Parsing for Text-to-SQL](https://arxiv.org/abs/2302.05965)

RESDSQL 的核心架构决策是把 schema linking 与 SQL skeleton parsing 解耦。第一阶段使用 cross-encoder 同时读取问题和表/列信息，对每个表、每列输出 relevance probability，再保留 top-k schema 供后续生成器使用。

官方实现中的 `use_contents` 可将数据库内容加入列信息，`add_fk_info` 可加入外键信息。官方鲁棒性结果还单独报告 DB schema synonym、NLQ-column synonym 和 NLQ-column attribute 等测试，说明同义词和模糊字段匹配被视为一项独立能力，而不是生成器的附带行为。

可迁移机制：

- 将“字段候选排序”从“最终计划生成”中拆为独立、可观测阶段；
- 对每个 Binding Slot 返回 top-k 候选及独立分数；
- 排序输入联合列名、类型、样例内容、字段说明和任务角色；
- 单独评测 candidate recall@k 与最终 binding accuracy。

局限：完整 RESDSQL 训练和推理较重，不适合直接嵌入轻量桌面 Runtime。

### 2.3 Text2SQL Schema Filter：可独立部署的中英文字段过滤器

来源：

- 官方仓库：[RUCKBReasoning/text2sql-schema-filter](https://github.com/RUCKBReasoning/text2sql-schema-filter)

该项目将 RESDSQL/CodeS 的 schema classifier 独立为组件。输入包含自然语言问题、表名、列名、`table_comment` 和 `column_comments`，输出表和列的相关性排名，并支持 top-k table/column 过滤以及中英文输入。

其输入契约有一个重要启示：Agent 看到了表头，不代表它拥有足够的业务语义。列名难以理解时，项目明确允许提供字段说明。这与企业 Excel 中大量缩写、内部简称和模糊列名高度相关。

可迁移机制：

- 可作为 SheetPilot 字段候选排序的离线基准或教师模型；
- Workbook Profile 可增加可选字段说明、已治理别名，而不只返回原始表头；
- 候选排序组件应只排序，不替代 Agent 对业务口径的最终选择。

局限：官方强模型基于 XLM-RoBERTa-XL，约 3.5B 参数，至少需要约 15GB CPU/GPU 内存；并且训练分布来自 Text-to-SQL 数据，迁移到中文 Excel 前必须进行实测。

### 2.4 DIN-SQL：显式 Schema_links 与 Intermediate Representation

来源：

- 官方代码：[MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting](https://github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting)
- 核心实现：[DIN-SQL.py](https://github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting/blob/main/DIN-SQL.py)
- 论文：[DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction](https://arxiv.org/abs/2304.11015)

DIN-SQL 将流程拆为 schema linking、难度分类、SQL 生成和 self-correction。源码中的 `schema_linking_prompt_maker` 先要求模型独立输出 `Schema_links`；复杂问题还会产生子问题和 `Intermediate_representation`，最后才生成 SQL。

Schema links 不仅可以包含列，还包含表连接以及问题中出现的值与字段的关联。

可迁移机制：

- 在计划生成前，要求 Agent 提交显式 Binding IR；
- Binding IR 使用现有 `binding-xxx` 和 `candidate-xxx` ID，而非自由文本字段名；
- 绑定阶段与计划阶段分别记录结果、错误和评测指标；
- 复杂任务可以先拆业务子目标，再分别绑定字段。

局限：官方原型依赖较长的 few-shot prompt、旧式 LLM API 和字符串切片解析。SheetPilot 不宜照搬其文本协议，应使用严格 JSON Schema 和 Candidate ID 枚举。

### 2.5 CHESS：值检索、schema 剪枝、候选生成与测试

来源：

- 官方仓库：[ShayanTalaei/CHESS](https://github.com/ShayanTalaei/CHESS)
- 论文：[CHESS: Contextual Harnessing for Efficient SQL Synthesis](https://arxiv.org/abs/2405.16755)

CHESS 的 Information Retriever 会检索相关数据库目录与真实值，Schema Selector 随后裁剪 schema，Candidate Generator 迭代产生候选，Unit Tester 再用自然语言测试验证。其预处理使用 MinHash、LSH 和向量数据库建立值级索引。

可迁移机制：

- 当问题中出现“华北”“已退款”“苹果手机”等值时，可通过单元格值反推出更可能的列；
- 大字段集先召回、再重排，避免一次把所有列交给模型；
- 绑定和计划生成后，使用面向用户需求的测试做反向验证。

局限：完整 CHESS 是包含索引、多组件和多次 LLM 调用的重型流水线。对单工作簿或字段较少的任务，完整照搬会增加延迟和工程复杂度；值检索应按工作簿规模按需启用。

### 2.6 OmniTab：问题文本与表格内容的显式对齐

来源：

- 官方仓库：[jzbjyb/OmniTab](https://github.com/jzbjyb/OmniTab)
- 论文：[OmniTab: Pretraining with Natural and Synthetic Data for Few-shot Table-based Question Answering](https://arxiv.org/abs/2207.03637)

OmniTab 直接联合编码自然语言问题和二维表。其自然数据包含 `mentions`，即问题文本字符区间与表格内容之间的显式对齐，再结合自然、合成和 SQL 数据训练语言到表格的 grounding 与推理能力。

可迁移机制：

- 样例值不是附属展示信息，而是字段 grounding 的直接证据；
- SheetPilot 的字段绑定测试集应标注“业务词/值 -> 真实列”的 mention 或 link；
- 对比实验应测“只给表头”和“表头 + 类型 + 样例值”两种输入。

局限：OmniTab 输出问题答案，不提供可审计的字段绑定和执行计划；训练与推理成本也较高，不适合作为现有 Runtime 的直接替代。

### 2.7 MetricFlow 与 Cube：稳定业务语义的治理层

来源：

- 官方仓库：[dbt-labs/metricflow](https://github.com/dbt-labs/metricflow)
- 官方仓库：[cube-js/cube](https://github.com/cube-js/cube)

MetricFlow 和 Cube 采用 semantic/metrics layer：预先定义 metric、dimension、join 和业务逻辑。MetricFlow 将指标请求编译成 dataflow query plan，再优化并渲染 SQL；Cube 将统一语义定义暴露给 BI 工具和 AI Agent。

可迁移机制：

- 对已知模板和反复出现的企业词汇，持久化“销售额”“净利润”“客户数”等定义和别名；
- 语义层命中应成为候选排序的高优先级证据；
- 指标口径包含聚合方式、维度、时间粒度和适用模板，而不只是词语到列名的简单字典。

局限：语义层解决的是已治理、重复出现的业务概念，不能独立解决首次上传的陌生工作簿。它应与通用字段 grounding 并存，而非替代后者。

## 3. 方案比较

| 方案 | 核心机制 | 是否需要训练/重模型 | 对模糊字段的直接价值 | 适合 SheetPilot 的角色 |
|---|---|---:|---|---|
| RAT-SQL | 关系图 + name/value linking | 是 | 高，强调多种关系证据 | 架构原则，不直接移植 |
| RESDSQL | 独立 schema relevance classifier + top-k | 是 | 很高 | 候选排序阶段的主要参考 |
| Schema Filter | 中英文表列相关性排序，支持 comments | 是，约 3.5B | 很高 | 离线基准/教师模型 |
| DIN-SQL | 显式 schema links + IR + self-correction | 否，依赖 LLM | 很高 | Agent 绑定协议的主要参考 |
| CHESS | 值检索 + schema 剪枝 + 候选 + 单测 | 可轻可重 | 高，尤其是值线索 | 大表召回与结果验证参考 |
| OmniTab | 问题 span 与表格内容对齐 | 是 | 中高 | 数据集和 grounding 评测参考 |
| MetricFlow/Cube | 持久化 metric/dimension 语义 | 配置治理为主 | 对已知模板很高 | 企业模板语义层 |

## 4. 与 SheetPilot 现有协议的关系

SheetPilot 已在 `docs/current/16-field-binding-and-request-revision-prototype-v1.md` 定义：

- Binding Slot；
- Runtime 生成的 Binding Candidate；
- Candidate ID；
- `NEEDS_BINDING`；
- Agent 只能从允许候选中选择；
- Binding revision 与 hash。

因此不需要重建绑定对象模型。开源方案主要补足以下空白：

### 4.1 候选召回

现有协议规定 Candidate 必须来自 Workbook Profile，但尚未给出语义候选如何稳定召回。可借鉴 CHESS 与 RAT-SQL：

- 表头精确/规范化匹配；
- 用户词与表头的语义相关性；
- 问题中的值与列样例/受控值的匹配；
- 字段类型与 Slot 用途的兼容性；
- 字段所在表、相邻字段和已绑定字段的结构关系；
- 已治理字段说明与别名。

### 4.2 候选重排

借鉴 RESDSQL，把每个 Slot 的候选重排作为独立阶段，输出 top-k，而不是让最终 Planner 同时阅读全部列并生成完整 Request。

建议先用当前 LLM 在严格结构化输入上完成重排，以便验证架构；不要一开始就部署 3.5B Schema Filter。待积累标注数据后，再比较：

- 现有 Agent 直接选择；
- LLM 独立重排；
- embedding/轻量 cross-encoder；
- 官方 Schema Filter 作为离线基准。

### 4.3 结构化 Binding IR

借鉴 DIN-SQL，计划前增加机器可检查的中间结果，但直接复用现有 ID：

```json
{
  "binding_decisions": [
    {
      "slot_id": "binding-003",
      "selected_candidate_id": "candidate-8f1472c1",
      "alternative_candidate_ids": ["candidate-a07f0614"],
      "evidence_used": ["header_semantics", "type_compatible", "sample_values"],
      "decision": "SELECT",
      "ambiguity": "MATERIAL"
    }
  ]
}
```

其中 confidence 可以用于评测和解释，但不能越过现有 Runtime 的自动绑定边界。若多个候选代表不同业务口径，应保持 `NEEDS_BINDING` 或进入人工确认，而不是因模型分数高就静默执行。

### 4.4 持久化语义层

借鉴 MetricFlow/Cube，对已知企业模板建立可版本化的语义资产：

```text
业务概念
-> 别名/说明
-> 模板与来源字段
-> 聚合方式与单位
-> 有效版本
-> 适用条件
```

语义层命中只能增加候选证据或在明确模板版本下形成确定映射；陌生文件仍走通用候选召回和 Agent 消歧。

## 5. 建议的验证顺序

这些建议来自上述开源系统的共同机制，目的是先验证问题结构，不是直接选定最终实现。

### 阶段 1：把绑定从规划结果中独立出来

- 保持现有 Runtime Candidate ID 和 amendment 协议；
- Agent 在制定计划前单独输出 Binding IR；
- 计划只能消费已经选定的 Candidate ID；
- 分别记录候选召回、绑定选择和计划生成错误。

对应来源：DIN-SQL、RESDSQL。

### 阶段 2：建立候选排序基线

- 输入使用业务词、任务角色、表头、类型、最多三个样例值和可选字段说明；
- 每个 Slot 输出 top-3 候选；
- 首先使用现有 LLM 作为重排器；
- 用 H1 等题集测 candidate recall@1、recall@3 和最终 binding accuracy。

对应来源：RESDSQL、Schema Filter、OmniTab。

### 阶段 3：增加值 grounding

- 仅在用户问题含明显实体/枚举值，或字段数较多时启动；
- 在受限样例或索引中检索值属于哪些列；
- 将值命中作为候选证据，不直接决定字段。

对应来源：CHESS、RAT-SQL、OmniTab。

### 阶段 4：引入已治理语义资产

- 对稳定模板维护指标、维度、别名和业务口径；
- 对新文件不强行套用旧模板；
- 所有语义定义版本化并进入 Evidence。

对应来源：MetricFlow、Cube。

### 阶段 5：数据充足后再评估专用模型

- 使用真实失败轨迹形成字段绑定标注集；
- 将开源 Schema Filter 作为离线强基准；
- 只有轻量方法明显不足时，才训练或蒸馏专用 reranker。

对应来源：RESDSQL、Schema Filter。

## 6. 评测应拆分的指标

开源方案把 schema linking 独立出来后，SheetPilot 也应避免只看最终 Excel：

| 指标 | 含义 |
|---|---|
| candidate recall@k | 正确字段是否进入前 k 个候选 |
| binding accuracy | Agent 是否从候选中选对字段 |
| material ambiguity detection | 是否识别会改变业务口径的歧义 |
| unnecessary clarification rate | 是否对本可自主判断的高置信映射频繁询问 |
| plan accuracy given gold bindings | 已提供正确绑定时，计划是否仍正确 |
| end-to-end task success | 最终工作簿是否满足用户需求 |

这些指标能区分：Runtime 候选没召回、Agent 候选选错、Agent 已选对但计划生成错，以及执行层错误。

## 7. 结论

开源社区较成熟的答案不是把所有责任继续压在一个 Agent Prompt 上，也不是让 Runtime 直接替用户决定业务口径，而是组合三类机制：

1. schema/value grounding：用表头、类型、值、说明和结构关系建立证据；
2. 独立 schema linking：为每个业务词召回并重排 top-k 真实字段；
3. structured IR：在生成计划前形成显式、可审计、可评测的绑定结果。

对 SheetPilot，最接近现有架构且成本最低的验证路线是：

```text
现有 Runtime 生成 Candidate ID
-> 参考 RESDSQL 独立做 top-k 重排
-> 参考 DIN-SQL 产出结构化 Binding IR
-> Agent 基于已绑定字段制定计划
-> 参考 CHESS 做需求级反向验证
```

RAT-SQL 和 OmniTab 更适合作为 grounding 原理与数据构造参考；Schema Filter 可作为离线强基准；MetricFlow/Cube 适合处理已知模板和重复业务口径。现阶段没有证据支持直接引入一个大型专用模型会优于先把候选、绑定和规划三个错误面拆开测试。
