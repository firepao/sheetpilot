# SheetPilot Agent Contract 测试集 - Prompt索引

## 概述

本目录包含所有测试场景的Prompt文档，用于指导Agent执行测试和人工评估。

## 测试场景分级

| 级别 | 描述 | 通过标准 | 场景数 |
|------|------|---------|-------|
| **S** (Simple) | 简单场景，单一维度/指标，无脏数据 | ≥90分 | 1 |
| **M** (Medium) | 中等场景，多维度/指标，轻度脏数据 | ≥80分 | 0 |
| **H** (Hard) | 困难场景，歧义字段，需语义判断 | ≥70分 | 1 |
| **R** (Real) | 真实场景，复杂业务逻辑，重度脏数据 | ≥60分 | 6 |

**当前总场景数**: 8个

## 场景列表

### S系列（简单场景）

| ID | 名称 | 数据文件 | 数据量 | 关键测试点 |
|----|------|---------|--------|-----------|
| S1 | 部门销售汇总 | `01_simple_department_sales.xlsx` | 37行 | 基础分组、排序 |

### H系列（困难场景）

| ID | 名称 | 数据文件 | 数据量 | 关键测试点 |
|----|------|---------|--------|-----------|
| H3 | 模糊字段选择 | `H3_sales_multi_amount.xlsx` | 200行 | 3列金额歧义、样本值判断、字段绑定 |

### R系列（真实场景）

| ID | 名称 | 数据文件 | 数据量 | 关键测试点 |
|----|------|---------|--------|-----------|
| R1 | 财务科目余额表 | `R1_finance_ledger.xlsx` | 600行 | 12%空值、借贷不平衡、财务术语 |
| R2 | 电商库存预警 | `R2_inventory_sku.xlsx` | 1500行 | 15%空值、IS NOT NULL过滤、比较运算 |
| R3 | 人力薪资成本 | `R3_hr_payroll.xlsx` | 804行 | 空值语义（无迟到）、多指标聚合 |
| R4 | 客户RFM价值 | `R4_customer_rfm.xlsx` | 6000行 | 二阶段聚合、能力边界识别 |
| R5 | 广告渠道ROI | `R5_ad_roi.xlsx` | 400行 | 负ROI、浮点数过滤、派生指标验证 |
| R6 | 物流配送时效 | `R6_logistics_timeout.xlsx` | 3000行 | 跨过滤聚合、能力边界识别 |

## Prompt文档结构

每个Prompt文档包含以下章节：

1. **场景描述** - 业务背景和测试目标
2. **输入文件** - 数据文件路径和特征
3. **用户需求（Prompt）** - 给Agent的原始需求描述
4. **预期执行流程** - Agent应该执行的步骤
5. **预期结果** - Oracle验证标准
6. **评分权重** - 各Gate的分数配比
7. **真实性体现** - 与真实业务的对应关系
8. **关键陷阱/扩展场景** - 常见错误和变体

## 使用方法

### 手工测试

1. 选择一个场景，如`R1_finance_reconciliation.md`
2. 复制"用户需求（Prompt）"章节的文本
3. 提交给Agent执行
4. 对照"预期执行流程"检查Agent行为
5. 使用"预期结果"中的Oracle值验证输出

### 自动化测试

```bash
# 运行单个场景
python -m tests.agent_contract.runner --scenario R1

# 运行整个测试套件
python -m tests.agent_contract.runner --all

# 运行特定级别
python -m tests.agent_contract.runner --level R
```

## 评估维度

### 基础Gate（100分制）

| Gate | 权重 | 验证内容 |
|------|------|---------|
| Evidence Gate | 10-15分 | 命令记录、文件交付完整性 |
| Contract Gate | 15-20分 | Task Request契约正确性 |
| Blackbox Gate | 20-30分 | 黑盒纪律遵守（不读源码/不直接操作工作簿） |
| Runtime Gate | 15-20分 | Runtime验收通过（RUNTIME_PASS + MATCHED） |
| Oracle Gate | 15-20分 | 输出数据与Oracle一致 |

### 扩展维度（观察指标，不计入总分）

| 维度 | 适用场景 | 验证内容 |
|------|---------|---------|
| Interaction Efficiency | 所有 | 交互轮次、CLI调用次数 |
| Field Binding Quality | H/R系列 | 字段绑定准确率 |
| Clarification Coverage | R4/R6 | 能力边界识别、简化方案质量 |

## 数据文件位置

- **测试数据**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\\`
- **场景定义**: `tests/agent_contract/scenarios/`
- **Prompt文档**: `tests/agent_contract/prompts/`（本目录）

## 下一步扩展（P1阶段）

计划新增16个场景，达到24个场景的MVP目标：

- **S系列**: 新增S2-S3（加入简单过滤、两维度分组）
- **M系列**: 新增M1-M8（中等复杂度，从Kaggle改造）
- **H系列**: 新增H1-H2, H4-H5（日期歧义、多条件组合）
- **R系列**: 当前6个场景完成

## 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-08-24 | v1.0 | 初始版本，包含8个场景（S1 + H3 + R1-R6） |
