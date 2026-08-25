# S1: 部门销售汇总（简单场景）

## 场景描述
基础的单维度分组汇总任务，用于测试Agent的基本能力。

## 测试目标
- 验证简单场景的端到端执行
- 验证基础的过滤、分组、聚合能力
- 作为S系列的最简路径基准

## 输入文件
- **文件路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\\01_simple_department_sales.xlsx`
- **工作表**: `销售明细`
- **表头行**: 1
- **数据特征**: 37行，字段清晰，无脏数据

## 用户需求（Prompt）

```
请分析销售明细表，按部门汇总销售总额，按销售总额降序排列。

输入文件: D:\bitexcel\SheetPilot\tests\agent_contract\data\\01_simple_department_sales.xlsx
输出文件: <由Agent决定>
```

## 预期执行流程

1. **查询字段清单**（可选）
   ```bash
   sheetpilot task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\\01_simple_department_sales.xlsx --sheet 销售明细 --header-row 1
   ```

2. **构造Task Request**
   - 维度: `部门`
   - 指标: `sum(销售额)` → `销售总额`
   - 排序: `销售总额 DESC`
   - 过滤: 无

3. **提交任务**
   ```bash
   sheetpilot task-run --request request.json --auto-result-dir <result-dir>
   ```

4. **复核状态**
   ```bash
   sheetpilot task-status --task-id <task-id>
   ```

## 预期结果

### Runtime验收（Oracle）
- **状态**: `RUNTIME_PASS`
- **artifact_integrity**: `MATCHED`
- **delivery_valid**: `true`

### 输出数据验证
- 输出工作表: 包含2列（部门、销售总额）
- 排序: 销售总额降序
- 行数: 3行（研发、市场、销售）

### 交互效率
- **理想轮次**: 1-2轮（含clarification）
- **CLI调用次数**: 2-3次（task-types可选 + task-run + task-status）

## 评分权重
- Evidence Gate: 10分
- Contract Gate: 20分
- Blackbox Gate: 30分
- Runtime Gate: 20分
- Oracle Gate: 20分

**通过标准**: ≥90分，无Critical Violations

## 变体场景
- S2: 加入简单过滤（状态='已完成'）
- S3: 两个维度（部门+季度）
