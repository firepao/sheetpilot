# S1: 部门销售汇总（简单场景基准）

## 场景描述
最基础的分组汇总场景，无过滤条件，无脏数据，用于验证基本功能。

## 测试目标
- 验证基础分组聚合能力
- 验证降序排序
- 验证Agent基本工作流（task-types → task-run → task-status）
- 作为最简单场景的基准

## 输入文件
- **文件路径**: `tests/agent_contract/data/01_simple_department_sales.xlsx`
- **工作表**: `销售明细`
- **表头行**: 1
- **数据特征**: 
  - 37行记录
  - 4个部门（研发、销售、市场、运营）
  - 无空值、无异常数据
  - 干净的测试数据

## 用户需求（Prompt）

```
请统计各部门的销售总额。

要求：
- 按部门分组
- 计算销售额合计
- 按销售额降序排列

输入文件: tests/agent_contract/data/01_simple_department_sales.xlsx
输出文件: <由Agent决定>
```

## 预期执行流程

1. **查询字段清单（可选）**
   ```bash
   sheetpilot task-types --input tests/agent_contract/data/01_simple_department_sales.xlsx --sheet 销售明细 --header-row 1
   ```

2. **构造Task Request**
   - 过滤条件: 无
   - 维度: `部门`
   - 指标: `sum(销售额)` → `销售总额`
   - 排序: `销售总额 DESC`

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

### 输出数据验证（Oracle值）

预期输出4行（4个部门），数据已验证：

| 部门 | 销售总额 |
|------|---------|
| 销售 | 21500 |
| 研发 | 13500 |
| 市场 | 13000 |
| 运营 | 12000 |

**验证要点**：
- 按销售总额降序排列：销售 > 研发 > 市场 > 运营
- 总计 = 60000（4个部门之和）
- 无空值、无异常

### 交互效率
- **理想轮次**: 1轮
- **CLI调用次数**: 2次（task-run + task-status）或3次（task-types + task-run + task-status）

### 基准意义
- 作为最简单场景，应达到接近100%成功率
- 用于验证基础工作流正确性
- 用于对比其他复杂场景的性能基准

## 评分权重
- Evidence Gate: 10分
- Contract Gate: 15分
- Blackbox Gate: 25分
- Runtime Gate: 20分
- Oracle Gate: 30分（简单场景Oracle权重更高）

**通过标准**: ≥90分（S系列高标准）

## 真实性体现
虽然是简单场景，但数据结构符合真实业务：
- 销售明细表：企业常见的基础报表
- 部门维度：最常用的组织维度
- 销售额求和：最基本的财务分析需求

## 扩展场景
- S1-v2: 增加简单过滤（仅统计"审核通过"订单）
- S1-v3: 增加第二指标（订单数量）
- S2: 两维度分组（部门 × 月份）
- S3: 三个指标（销售额、订单数、平均订单金额）

## 注意事项
- 这是入门级场景，不应有任何失败
- 如果Agent在此场景失败，说明基础工作流有问题
- 用于快速验证SheetPilot环境配置是否正确
