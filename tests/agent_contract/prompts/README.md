# SheetPilot Agent Contract 三类业务提示词

本目录参考上一版 Excel 能力评测中“新建复杂报表、编辑已有工作簿、导入清洗数据”三类提示词的组织方式，为当前 `$sheetpilot-excel-agent` 生成可直接用于 Fresh Agent 会话的测试提示词。

| 文件 | 对应类别 | 当前能力下的测试重点 |
|---|---|---|
| `N1_CREATE_COMPLEX_OPERATING_SUMMARY.md` | 新建复杂报表 | `07_complex_retail_operations.xlsx`，多门店零售经营汇总 |
| `E2_EDIT_EXISTING_WORKBOOK_SUMMARY.md` | 编辑已有工作簿 | `08_complex_saas_renewals.xlsx`，SaaS 续费增量汇总 |
| `I3_DIRTY_DATA_CLEAN_ANALYSIS.md` | 脏数据清洗分析 | `09_complex_dirty_logistics.xlsx`，物流有效数据经营分析 |

## 与旧提示词的差异

当前 Agent-facing Task API 主要支持对已有 `.xlsx/.xlsm` 的筛选、分组、聚合、排序和新建汇总 Sheet。因此：

- N1 不要求从零生成数百行模拟明细，而是从现有明细生成复杂经营汇总。
- E2 不要求修改原表公式或图表，而是验证保留原内容并增量新增汇总 Sheet。
- I3 不要求读取 CSV 或逐单元格修复脏值，而是按已有“清洗状态”执行明确、可冻结的过滤口径。
- 三个提示词都不要求当前 Task API 尚未承诺的图表、PNG、任意公式列或检查页能力。

## 执行规则

1. 每份提示词使用一个全新的 Agent 会话。
2. 将对应 Markdown 正文完整发送给 Agent。
3. 保留 Replay、Task Request、Task ID、最终 Task Status、回复和输出文件。
4. 执行完成后使用 `sheetpilot-run-review` 准备 run bundle，再使用 `sheetpilot-run-scorer` 独立评分。
5. `<AUTO-RESULT-DIR>` 由 `$sheetpilot-excel-agent` 按 Skill 规则替换为新的用户交付目录。
