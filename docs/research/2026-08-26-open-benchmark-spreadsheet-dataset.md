# 开源 Excel/表格 Agent Benchmark 调研

## 范围与证据原则

本报告优先使用项目官方仓库、论文和数据说明；不引用二手博客或排行榜。重点回答四个问题：任务如何构造、数据质量如何保证、用户 prompt 如何呈现、结果如何评估。

## 1. SpreadsheetBench（NeurIPS 2024 D&B）

一手来源：

- 官方仓库与数据说明：[RUCKBReasoning/SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench)
- 官方论文：[SpreadsheetBench: Towards Challenging Real World Spreadsheet Manipulation](https://arxiv.org/abs/2406.14991)
- 官方主页：[spreadsheetbench.github.io](https://spreadsheetbench.github.io/)

### 任务设计

官方 README 说明，基准包含 912 个来自真实 Excel 论坛的问题，而不是合成指令；问题覆盖 find、extract、sum、highlight、remove、modify、count、delete、calculate、display 等操作。工作簿允许多 sheet、同一 sheet 多表、非标准关系表以及丰富的非文本元素，因而更接近用户实际文件，而不是干净的二维 CSV。

每条数据包含 `id`、`instruction`、`spreadsheet_path`、`instruction_type`（Cell-Level 或 Sheet-Level）和 `answer_position`。每个任务目录有输入与答案工作簿，答案指定应写入的位置。完整集为 912 instructions、2,729 test cases，平均每条指令约 3 个测试例；官方还发布了 400 条专家标注的 Verified 子集。

官方论文进一步报告：题目来自 ExcelForum、Chandoo、MrExcel、ExcelGuru 四个论坛；35.7% 的文件含多个表，42.7% 含非标准关系表（嵌套、不完整或缺失表头），文件规模可超过 100 列和 20,000 行，并包含自由文本和颜色等非文本元素。数据流程是“采集 -> 筛选已解决且可测试的纯表格操作 -> GPT-4 重写指令并人工核验 -> 标注答案位置 -> 构造多测试例”。这说明 prompt 清晰化可以使用模型辅助，但必须保留人工核验环节。

### 数据质量与鲁棒性

同一 instruction 配多个输入/答案测试例，使评测不仅检查一个固定数值，而是检查解决方案对不同单元格值的泛化。官方把测试例组织方式类比 online judge，并要求执行生成的代码后再比较结果工作簿。该设计能暴露“只记住样例值”或只对某一布局有效的程序。

官方数据描述强调真实文件中的额外解释、多个表和非规则布局；因此任务难点同时来自语言理解、表格定位、格式保留和计算，而非仅来自算术。

### Prompt 与推理设置

官方实验区分 single-round 和 multi-round。single-round 向模型提供输入工作簿的前几行并要求一次生成代码；multi-round 增加 ReAct 过程和代码执行反馈，也有“5 行预览 + 执行反馈”等变体。生成的 Python 代码在隔离执行环境中运行，再产生输出工作簿。

这提供了一个清晰的 prompt 对照实验：只改变上下文量（前几行/更多行）、交互次数和执行反馈，不改变任务本身。

### 评估标准

官方评估脚本会先用 LibreOffice 或 Windows Excel/win32com 强制重算公式，再比较模型输出和答案文件；这避免 `openpyxl` 读到过期缓存值。核心结果是测试例级正确率及 instruction 级通过情况，且要求所有测试例都正确才算稳定解决。官方论文还报告了 Excel 专家的人类表现，用于显示模型与人工之间的差距。

### 对 SheetPilot 的可借鉴点

1. 每个自然语言任务至少配一个 gold 工作簿；高风险任务配多个“值不同但结构相同”的测试例。
2. 输入应保留真实布局、多个 sheet、说明文字和格式，而不是预先压平成干净表格。
3. prompt 评测拆成单轮、执行反馈、多轮修订三个条件，以区分规划能力和调试能力。
4. 评测前统一重算公式，并同时比较值、公式、单元格位置和必要的格式/结构属性。
5. 数据记录应保留任务类型、答案位置、输入/答案文件对，便于按能力切片。

## 2. SpreadsheetBench 的局限与数据治理建议

官方 README 没有声称每个论坛问题都具有唯一解释；真实问题可能含隐含业务口径。因此 SheetPilot 若复用其思路，应为每题补充：目标区域、允许修改范围、公式/值的预期语义、格式是否纳入验收、以及歧义是否需要澄清。Verified 子集说明专家复核是有价值的质量层，应把“原始题”和“专家确认题”分开报告，避免混淆数据清洁度与模型能力。

还应固定数据版本和哈希。SpreadsheetBench 官方明确表示数据会持续修正并版本化；SheetPilot 的回归测试也应把 benchmark 版本、工作簿哈希和评估器版本写入运行证据。

## 3. 可补充采用的公开基准模式

本次检索未找到具有同等公开、稳定一手规范且专注 Excel Agent 执行的另一套成熟 benchmark。对于 SheetBench、ToolBench/OpenAssistant 等名称，若没有官方任务文件、答案工作簿和评估脚本，不应把搜索摘要当作可复现实验依据。可借鉴的通用模式只有在获得其官方仓库/论文后再纳入：工具调用轨迹、结构化 action schema、执行后状态检查和可重放日志。

## 4. 建议的 SheetPilot Benchmark 规范

### 任务记录

```json
{
  "task_id": "...",
  "version": "...",
  "prompt": "用户原始请求",
  "input_workbook_sha256": "...",
  "gold_workbook_sha256": "...",
  "task_type": "cell|sheet|workbook",
  "answer_region": "Sheet1!D5:D20",
  "allowed_mutations": ["values", "formulas", "styles"],
  "clarification_policy": "..."
}
```

### 评估分层

- **文件级通过率**：输出能否打开、公式是否已重算、是否产生预期 sheet/区域。
- **单元格值/公式正确率**：逐格比较，分别统计值和公式。
- **结构与格式正确率**：合并单元格、表格边界、样式等仅在任务声明要求时纳入。
- **任务级成功率**：一个任务的所有测试例都通过才记为通过；同时报告测试例平均分，避免单一汇总掩盖失败。
- **交互效率**：轮数、执行次数、澄清次数和运行时间，作为质量之外的成本指标。

### 最小数据质量门槛

- gold 文件由独立脚本生成并可重复；输入/答案文件一一对应。
- 每个任务至少有一条人工验收说明，注明允许修改区域和业务口径。
- 对公式任务用 Excel/LibreOffice 重算后再取值；评估器记录重算后状态。
- 对结构变化任务提供反例或多测试例，防止硬编码位置/常数。
- 运行产物保存 prompt、代码/工具轨迹、输出文件哈希和逐项差异，支持审计与复现。

## 结论

SpreadsheetBench 最值得直接借鉴的不是题目数量，而是“真实用户 prompt + 原始复杂工作簿 + 每题多个测试例 + 执行后 OJ 风格比较”的组合。对 SheetPilot，推荐先建立小规模高质量版本：每项能力 20--50 个真实任务，复杂任务配 3 个结构保持而数值变化的测试例；同时把文件可打开、值/公式、结构/格式和任务级通过率分开报告。这样能明确区分 Agent 规划错误、执行错误、公式缓存问题与评估器问题。
