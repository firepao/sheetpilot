# Bread 风格能力目录与业务分子能力 V1

本目录以 Bread Excel Agent 的 Action Space 为参考，但只把能够在 SheetPilot 的确定性、可审计 Runtime 中执行的动作标记为 `available`。当前迁移清单共 67 项：第一阶段 52 项，第二阶段 5 项，第三阶段 10 项；`109` 是能力建设版本号，不代表必须一次实现 109 个函数。

## 已落地原子能力

| 类别 | 能力 | 状态 | 典型业务用途 |
|---|---|---|---|
| 表格 | `read_table` | available | 读取表头和数据行 |
| 表格 | `filter_rows` | available | 多条件筛选、日期/数值范围 |
| 表格 | `select_columns` | available | 输出字段投影、字段重命名 |
| 表格 | `sort_rows` | available | 金额、日期、优先级排序 |
| 表格 | `aggregate` | available | 求和、平均、行数、非空数 |
| 表格 | `derive_column` | available | 加减乘、安全除法、兜底值 |
| 表格 | `deduplicate` | available | 按业务键去重，保留首条/末条 |
| 表格 | `fill_missing` | available | 缺失状态、金额、分类的统一填充 |
| 表格 | `value_counts` | available | 状态、渠道、地区频数分布 |
| 表格 | `table.count` | available | 总行数或指定字段非空数 |
| 表格 | `table.unique` | available | 提取确定性排序的唯一值清单 |
| 表格 | `describe_table` | available | 字段非空数、数值和、均值概览 |
| 工作簿 | `create_sheet` | available | 创建结果、异常、对账工作表 |
| 工作簿 | `write_table` | available | 将结果表写入指定锚点 |
| 展示 | `apply_style_preset` | available | 业务表、标题、合计、输入/公式区 |
| 展示 | `freeze_header` | available | 冻结表头 |
| 展示 | `create_chart` | available | 柱状、折线、饼图 |

## 第一批通用分子能力

这些能力必须展开为可审计的原子步骤，不能依赖业务专用脚本：

- `clean_and_profile_table`：读取 → 去重 → 缺失值处理 → 描述性统计 → 输出“清洗明细”和“数据概览”。
- `operating_summary`：筛选 → 派生指标 → 按维度/期间汇总 → 排序 → 写表 → 样式/图表。
- `profitability_report`：读取收入与成本 → 计算利润/利润率 → 按产品、区域或期间汇总 → 写入报告。
- `reconciliation_report`：分别汇总源表和结果表 → 计算差异 → 输出对账表与 PASS/FAIL 状态。
- `distribution_report`：按分类做频数/占比 → 排序 → 写入分布表，可选图表。
- `exception_worklist`：筛选缺失、重复、越界或状态异常 → 保留原始行号 → 输出待处理清单。

## 测试集收敛规则

同一原子语义只保留一个最小代表场景和一个组合场景：

- `S` 层验证单个原子：筛选、排序、聚合、去重、缺失值、频数统计各 1 个。
- `M` 层验证分子：经营汇总、利润报告、清洗概览、异常清单、对账、分布报告各 1 个。
- `H` 层只保留字段歧义、复杂条件、日期/数字脏值、多维输出等边界场景，不重复同构统计。
- `R` 层保留跨行业真实流程；同一统计公式只在不同数据质量或写入要求确实改变时重复。

删除/合并标准：若两个场景的输入字段类型、过滤谓词、指标函数、输出对象和验收条件完全同构，则保留数据质量更高、覆盖行数更大的场景，另一个改为参数变体而不是独立 case。
