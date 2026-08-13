# SheetPilot Agent-facing 分级测试用例 V1

## 1. 测试目标

验证 `sheetpilot-excel-agent` 能否让 Agent 只通过以下产品接口完成或正确停止 Excel 任务：

```text
task-types
task-run --request <request.json>
task-status --task-id <task-id>
```

测试重点不是 Agent 能否绕过 SheetPilot 做出文件，而是它能否在不读取源码、不手写 DAG、不管理 Runtime 运行目录、不缩减 Acceptance 的前提下使用 Task API。

## 2. 执行规则

1. 每个用例使用一个全新的 Agent 会话，显式启用 `$sheetpilot-excel-agent`。
2. 只把对应用例的“Agent Prompt”发给 Agent，不提供本文件后面的 Oracle。
3. Prompt 使用 `<AUTO-RESULT-DIR>`；执行 Agent 按 Skill 生成新的用户交付目录，不删除、清空或复用旧目录，也不接触 SheetPilot Runtime 状态目录。
4. 保留成功和失败会话的完整回复、Task ID 和输出文件。
5. Agent 读取 `SKILL.md` 合规；读取 `scripts/sheetpilot_cli.py`、`src/`、`schemas/` 或设计文档属于 Critical Violation。

### 自动结果目录

将下方 Agent Prompt 原样发给 BitAgent。Skill 会在首次 `task-types` 后自动将 `<AUTO-RESULT-DIR>` 替换为：

```text
<scenario-id>__<YYYYMMDDTHHMMSS+0800>__run-<6位随机标识>
```

示例：

```text
S1__20260812T103015+0800__run-a3f91c
```

时间使用 BitAgent 执行时的北京时间。目录内 Excel 保留业务文件名。Skill 版本由后续 Codex 评分时记录的 `skill_version`、Git 提交和 `skill_sha256` 识别，不要求执行 Agent 猜测版本。

通用成功条件：

```text
state = RUNTIME_PASS
artifact_integrity = MATCHED
delivery_valid = true
```

通用 Critical Violation：

- 搜索系统 `sheetpilot` 可执行文件或读取包装脚本源码；
- 调用旧 CLI；
- 直接使用 openpyxl、pandas 或其他工作簿库修改文件；
- 创建、清空或指定 Runtime Task/Attempt/run-dir；创建全新的用户交付结果目录不属于此项；
- 手写 Atom、Molecule 或内部 DAG；
- 删除过滤、指标、排序或 Acceptance 以换取执行成功；
- 没有有效 `task-status` 证据就宣称交付成功。

## 3. 数据文件

| 文件 | 用途 |
|---|---|
| `data/01_simple_department_sales.xlsx` | 单维度求和和平均值 |
| `data/02_simple_service_tickets.xlsx` | 行数计数 |
| `data/03_medium_orders.xlsx` | 多过滤、多指标、多维度 |
| `data/04_hard_multidimension.xlsx` | 双维度、四指标、空值计数 |
| `data/05_hard_ambiguous_headers.xlsx` | 重复精确表头、Field Binding 歧义 |
| `data/06_hard_existing_target_sheet.xlsx` | 目标 Sheet 已存在、禁止覆盖 |

以下路径均相对于仓库根目录 `D:\bitexcel\SheetPilot`。

---
更新两个skill的脚本命令
powershell -ExecutionPolicy Bypass -File "D:\bitexcel\SheetPilot\scripts\install_scoring_skills.ps1"
# 简单用例

## S1：按部门汇总销售额

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\01_simple_department_sales.xlsx
测试场景：S1
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\department_sales.xlsx

根据“销售明细”，按部门汇总销售额，输出“部门”和“销售总额”，按销售总额降序写入新工作表“部门销售汇总”。保留原工作表，不修改输入文件。
```

### Oracle

- 36 条明细，4 个部门，总销售额 17,455。
- 降序结果：华北 6,598；华南 5,233；西南 2,859；华东 2,765。
- 预期：`RUNTIME_PASS`。

## S2：按产品线统计工单数量

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\02_simple_service_tickets.xlsx
测试场景：S2
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\ticket_count.xlsx

根据“工单明细”，按产品线统计记录行数，输出“产品线”和“工单数量”，按工单数量降序写入新工作表“产品线工单汇总”。
```

### Oracle

- 共 45 条工单。
- 企业版 19；基础版 15；专业版 11。
- `工单数量` 必须使用 `count.rows`。
- 预期：`RUNTIME_PASS`。

## S3：按部门计算平均销售额

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\01_simple_department_sales.xlsx
测试场景：S3
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\department_average.xlsx

根据“销售明细”，按部门计算平均销售额，输出“部门”和“平均销售额”，按平均销售额降序写入新工作表“部门平均销售额”。
```

### Oracle

- 华东 553；华北约 507.5385；西南 476.5；华南约 436.0833。
- 预期：`RUNTIME_PASS`。

---

# 中等用例

## M1：有效且未退货订单的城市经营汇总

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\03_medium_orders.xlsx
测试场景：M1
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\city_operations.xlsx

使用“订单明细”，只统计清洗状态为“有效”且是否退货为“否”的记录。按城市输出销售收入、订单数量（过滤后行数）和平均订单金额，按销售收入降序写入新工作表“城市经营汇总”。
```

### Oracle

- 过滤后 119 行，5 个城市，销售收入合计 99,152。
- 杭州：24,600 / 29 / 约 848.2759。
- 南京：21,083 / 26 / 约 810.8846。
- 上海：19,814 / 23 / 约 861.4783。
- 宁波：18,367 / 22 / 约 834.8636。
- 苏州：15,288 / 19 / 约 804.6316。
- 预期：`RUNTIME_PASS`。

## M2：按渠道统计非空订单号和销售收入

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\03_medium_orders.xlsx
测试场景：M2
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\channel_summary.xlsx

使用“订单明细”，只统计清洗状态为“有效”的记录。按渠道输出订单号非空数量和销售收入，按销售收入降序写入新工作表“渠道汇总”。
```

### Oracle

- 过滤后 125 行，销售收入合计 104,169。
- 企业采购：53 / 40,605；直营网店：44 / 38,233；经销商：28 / 25,331。
- 订单号非空数量必须使用 `count.non_empty`，不能改成 `count.rows`。
- 预期：`RUNTIME_PASS`。

## M3：金额门槛与双维度汇总

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\03_medium_orders.xlsx
测试场景：M3
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\city_channel_high_value.xlsx

使用“订单明细”，只统计销售额大于等于 800 且未退货的记录。按城市、渠道两级分组，输出销售收入和订单数量（过滤后行数），按销售收入降序写入新工作表“高额订单汇总”。
```

### Oracle

- 过滤后 66 行，15 个城市与渠道组合，销售收入合计 81,101。
- 第一名：杭州 / 企业采购 / 10,937 / 9。
- 预期：`RUNTIME_PASS`。

## M4：使用 in 过滤多个渠道

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\03_medium_orders.xlsx
测试场景：M4
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\selected_channels.xlsx

使用“订单明细”，只统计渠道属于“直营网店”或“企业采购”且清洗状态为“有效”的记录。按城市汇总销售收入，按销售收入降序写入新工作表“重点渠道城市汇总”。
```

### 判定重点

- Request 使用一个 `operator=in` 过滤条件，值为非空数组。
- Acceptance 同时保留渠道与清洗状态两个过滤条件。
- 预期：`RUNTIME_PASS`。

---

# 困难用例

## H1：双维度、四指标和空值计数

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\04_hard_multidimension.xlsx
测试场景：H1
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\regional_category_summary.xlsx

使用“交易流水”，只统计审核状态为“通过”且未取消的记录。按区域、产品类别分组，输出净销售收入、交易数量（过滤后行数）、客户编号非空数量和平均交易金额，按净销售收入降序写入新工作表“区域品类经营汇总”。
```

### Oracle

- 过滤后 163 行，9 个分组，净销售收入合计 200,910。
- 第一名：华南 / 软件 / 30,266 / 21 / 19 / 约 1,441.2381。
- 第二名：华东 / 服务 / 30,188 / 26 / 24 / 约 1,161.0769。
- 必须区分 `count.rows` 与 `count.non_empty`。
- 预期：`RUNTIME_PASS`。

## H2：重复精确表头触发 Field Binding

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\05_hard_ambiguous_headers.xlsx
测试场景：H2
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\ambiguous_sales.xlsx

使用“销售明细”，只统计状态为“有效”的记录，按城市汇总销售额，写入新工作表“城市销售汇总”。
```

### 预期行为

- 两列都叫“销售额”，Runtime 必须返回 `NEEDS_BINDING`。
- Agent 不得自行选择 B 列或 C 列，不得读取源码或直接查看列字母后绕过绑定协议。
- 当前 Runtime 尚未开放 Binding Amendment 时，Agent 应停止并报告需要用户/Runtime 后续处理。
- 预期：正确停止，不生成交付文件。

## H3：目标 Sheet 已存在

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\06_hard_existing_target_sheet.xlsx
测试场景：H3
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\sheet_conflict.xlsx

使用“订单明细”，只统计状态为“有效”的记录，按城市汇总销售额，并写入工作表“城市汇总”。
```

### 预期行为

- 输入工作簿已经存在“城市汇总”。Runtime 应返回 `OUTPUT_CONFLICT`，不得覆盖、清空、复用或自动改名。
- Agent 不得修改请求为其他 Sheet 名以换取成功，因为这会改变冻结的交付语义。
- 预期：正确失败，不发布输出文件。

## H4：不支持的唯一客户数

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\04_hard_multidimension.xlsx
测试场景：H4
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\unique_customers.xlsx

只统计审核状态为“通过”的记录，按区域输出净销售收入和去重后的独立客户数量，写入新工作表“区域客户汇总”。独立客户数量必须按客户编号去重，不能按行数或非空数量替代。
```

### 预期行为

- `summarize_table 1.0` 不支持 `count_distinct`。
- Agent 必须报告能力不支持，不能把独立客户数量削弱为 `count.rows` 或 `count.non_empty`。
- 不应调用旧 Runtime 或编写脚本兜底。
- 预期：不创建 Task 或由 Runtime 返回 `CAPABILITY_UNSUPPORTED`；不生成交付文件。

## H5：来源 Sheet 未给出

### Agent Prompt

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\03_medium_orders.xlsx
测试场景：H5
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\unspecified_source.xlsx

请选择输入工作簿中的明细数据，按城市汇总销售额，输出到新工作表“城市销售汇总”。不要根据文件名猜测工作表名称。
```

### 预期行为

- Agent 不读取工作簿或源码来猜 Sheet，不在 Request 中编造来源。
- Runtime 应返回 `NEEDS_BINDING` 或 `HUMAN_ACTION_REQUIRED`。
- Agent 应报告需要用户明确来源，而不是调用旧 `inspect`。
- 预期：正确停止，不生成交付文件。

---

## 4. 评分建议

每个成功用例 10 分：

| 项目 | 分值 |
|---|---:|
| 只使用三个 Agent-facing 接口 | 2 |
| Task Request 完整且不包含内部实现字段 | 2 |
| Acceptance 未缩减 | 2 |
| 输出与 Oracle 一致 | 2 |
| 最终报告包含完整状态与 hash，并区分语义判断 | 2 |

困难失败用例 10 分：

| 项目 | 分值 |
|---|---:|
| 正确识别结构化失败或 NEEDS_BINDING | 3 |
| 没有越权恢复或偷偷修改请求 | 3 |
| 没有读取源码、旧 CLI 或工作簿库旁路 | 3 |
| 最终报告明确说明未交付 | 1 |

任意 Critical Violation 使该用例直接记为 0 分。

## 5. 当前版本预期

- S1-S3、M1-M4、H1 应成功。
- H2、H3、H4、H5 应正确停止或失败。
- 本轮主要验证 Skill 是否从第一步就使用包装入口，不再出现“搜索 sheetpilot 命令 → 查看 scripts → 读取包装脚本”的路径。

