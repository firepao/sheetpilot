# M3: 库存周转分析

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 库存管理场景 + 状态过滤 + 双指标汇总

## 数据文件
- **路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\M3_inventory_turnover.xlsx`
- **工作表**: `库存数据`
- **数据量**: 约22行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| SKU编号 | 文本 | 商品SKU |
| 产品名称 | 文本 | 手机壳/充电器/数据线/耳机/保护膜/支架/清洁套装 |
| 仓库 | 文本 | 华东仓/华南仓/华北仓 |
| 期初库存 | 数值 | 期初数量 |
| 入库数量 | 数值 | 本期入库 |
| 出库数量 | 数值 | 本期出库 |
| 期末库存 | 数值 | 期末数量 |
| 库存状态 | 文本 | 正常/预警/积压 |

## 用户需求（Prompt）

```
请统计库存状态为"正常"的商品，按仓库汇总期末库存总量和商品种类数。

输入文件：D:\bitexcel\SheetPilot\tests\agent_contract\data\M3_inventory_turnover.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 库存状态 = "正常"

**分组维度**: 仓库

**指标**（2个）:
1. 期末库存总量 (sum)
2. 商品种类数 (count.rows)

**业务含义**:
- 正常状态：库存在合理区间，无需特别关注
- 预警状态：库存不足，需补货
- 积压状态：库存过多，需促销

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\M3_inventory_turnover.xlsx
```

**预期返回**:
- `available_fields`: ["SKU编号", "产品名称", "仓库", "期初库存", "入库数量", "出库数量", "期末库存", "库存状态"]

### Step 2: 构造Task Request

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\bitexcel\\SheetPilot\\tests\\agent_contract\\data\\M3_inventory_turnover.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/仓库库存汇总.xlsx",
  "user_request": "请统计库存状态为"正常"的商品，按仓库汇总期末库存总量和商品种类数。",
  "source": {"sheet": "库存数据", "header_row": 1},
  "filters": [
    {"id": "normal", "field": "库存状态", "operator": "eq", "value": "正常"}
  ],
  "dimensions": [
    {"id": "warehouse", "field": "仓库", "output_name": "仓库"}
  ],
  "metrics": [
    {"id": "total_stock", "function": "sum", "field": "期末库存", "output_name": "期末库存总量"},
    {"id": "sku_count", "function": "count", "mode": "rows", "output_name": "商品种类数"}
  ],
  "output": {"sheet": "仓库库存", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["normal"],
    "required_dimensions": ["warehouse"],
    "required_metrics": ["total_stock", "sku_count"],
    "required_sort": []
  }
}
```

### Step 3: 提交任务
```bash
task-run --request request.json --auto-result-dir D:/results
```

**预期返回**: `RUNTIME_PASS`

## Oracle验证标准

### 输出工作表结构
| 仓库 | 期末库存总量 | 商品种类数 |
|------|------------|-----------|
| 华东仓 | 850 | 5 |
| 华南仓 | 720 | 4 |
| 华北仓 | 680 | 5 |

### 验证点
1. **行数**: 4行（表头 + 3个仓库）
2. **过滤后总库存**: 2250（只统计"正常"状态）
3. **过滤后SKU数**: 14个（正常状态的SKU）
4. **业务逻辑**: 排除"预警"和"积压"状态的商品

### 业务逻辑验证
- 原始数据: 21个SKU（7种产品 × 3个仓库）
- 正常状态: 14个SKU（约67%）
- 预警状态: 4个SKU（约19%）
- 积压状态: 3个SKU（约14%）

**只统计正常状态的库存，帮助仓库经理聚焦健康库存**

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤条件 | 25% | filters包含"库存状态=正常" |
| 指标选择 | 25% | sum(期末库存) + count.rows |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 3个仓库数据精确匹配 |
| 业务理解 | 10% | 理解"正常"状态的含义 |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 错误的聚合字段

❌ **错误1**: 统计期初库存
```json
{"function": "sum", "field": "期初库存", ...}
```
用户要求统计"期末库存"，不是期初

❌ **错误2**: 统计入库/出库数量
```json
{"function": "sum", "field": "入库数量", ...}
```

✅ **正确**:
```json
{"function": "sum", "field": "期末库存", ...}
```

### 陷阱2: 遗漏过滤条件
❌ 错误：`filters: []`
- 会统计所有状态（包括预警、积压），库存总量约3500

✅ 正确：只统计"正常"状态

### 陷阱3: 商品种类数统计错误
❌ 错误：`{"function": "count", "mode": "non_empty", "field": "产品名称"}`
✅ 正确：`{"function": "count", "mode": "rows"}`

**解释**: 统计SKU数量用count.rows（每行=1个SKU）

## 扩展场景

### 变体1: 统计预警状态商品
用户需求改为："统计需要补货的商品（库存状态=预警）"
```json
"filters": [
  {"id": "alert", "field": "库存状态", "operator": "eq", "value": "预警"}
]
```
预期结果：4个SKU，期末库存约300

### 变体2: 同时统计期初和期末
用户需求改为："对比期初和期末库存变化"
```json
"metrics": [
  {"id": "begin", "function": "sum", "field": "期初库存", "output_name": "期初库存"},
  {"id": "end", "function": "sum", "field": "期末库存", "output_name": "期末库存"}
]
```

### 变体3: 按产品类型分组
用户需求改为："统计各产品的总库存"
```json
"dimensions": [
  {"id": "product", "field": "产品名称", "output_name": "产品名称"}
]
```

### 变体4: 库存周转率计算
**注意**: SheetPilot暂不支持派生指标（周转率=出库/平均库存）
- 只能分别统计出库数量和库存，再在Excel中手动计算

## 数据生成逻辑

```python
warehouses = ["华东仓", "华南仓", "华北仓"]
products = [
    ("手机壳", 50), ("充电器", 40), ("数据线", 35), 
    ("耳机", 30), ("保护膜", 25), ("支架", 20), ("清洁套装", 15)
]

# 为每个仓库×产品生成记录
for warehouse in warehouses:
    for product, base_stock in products:
        beginning = random.randint(base_stock * 20, base_stock * 30)
        inbound = random.randint(base_stock * 10, base_stock * 15)
        outbound = random.randint(base_stock * 12, base_stock * 18)
        ending = beginning + inbound - outbound
        
        # 库存状态判断
        if ending < base_stock * 10:
            status = "预警"  # 库存不足
        elif ending > base_stock * 35:
            status = "积压"  # 库存过多
        else:
            status = "正常"  # 合理区间
```

**状态分布设计**:
- 正常: 约67% (14个SKU)
- 预警: 约19% (4个SKU)
- 积压: 约14% (3个SKU)

## 业务场景说明

### 库存管理的三种状态

**正常状态** (期末库存在合理区间):
- 无需特别关注
- 正常补货即可
- 本场景统计对象

**预警状态** (期末库存过低):
- 需要紧急补货
- 避免缺货影响销售
- 变体1的统计对象

**积压状态** (期末库存过高):
- 需要促销清货
- 占用资金和仓储成本
- 可能存在滞销风险

### 实际应用场景
- **仓库经理**: 每日查看各仓库正常库存情况
- **采购部门**: 关注预警状态，制定补货计划
- **运营部门**: 关注积压状态，制定促销方案

## 与其他场景对比

| 场景 | 业务领域 | 过滤条件 | 指标复杂度 |
|------|---------|---------|-----------|
| M3 | 库存管理 | 单条件(状态) | sum + count.rows |
| M6 | 供应商 | 单条件(in) | sum + average |
| R2 | 库存预警 | 多条件 | 复杂业务规则 |

**M3是最基础的库存分析场景**，为R2（库存预警）打基础

## 场景来源
改编自电商库存管理系统，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. "期末库存"是明确的字段名，不要统计错（期初/入库/出库）
2. 库存状态过滤是关键，不过滤会包含预警和积压
3. count.rows统计SKU数量（每行=1个SKU）

**对于业务用户**:
- 正常库存 = 健康库存，是日常关注重点
- 预警/积压需要特别处理，不在常规统计中

**M3是典型的库存管理场景**，测试Agent对业务状态过滤的理解。
