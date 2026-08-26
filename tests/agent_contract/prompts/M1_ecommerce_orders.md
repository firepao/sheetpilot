# M1: 电商订单分析（双维度双指标）

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 电商业务场景 + 双维度 + 双指标 + 过滤

## 数据文件
- **路径**: `D:/bitexcel/SheetPilot/tests/agent_contract/data/M1_ecommerce_orders.xlsx`
- **工作表**: `订单明细`
- **数据量**: 约342行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 订单ID | 文本 | 订单编号 |
| 产品类别 | 文本 | 电子产品/家居用品/服装鞋帽/食品饮料/图书文具 |
| 城市 | 文本 | 北京/上海/广州/深圳 |
| 销售额 | 数值 | 订单金额 |
| 订单状态 | 文本 | 已完成/已取消/退货中 |

## 用户需求（Prompt）

```
请统计已完成订单中，每个城市每个产品类别的销售总额和订单数量。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/M1_ecommerce_orders.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 订单状态 = "已完成"

**分组维度**（2个）:
1. 城市
2. 产品类别

**指标**（2个）:
1. 销售总额 (sum)
2. 订单数量 (count.rows)

**预期输出**: 4个城市 × 5个类别 = 20行（部分组合可能无数据）

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:/bitexcel/SheetPilot/tests/agent_contract/data/M1_ecommerce_orders.xlsx
```

### Step 2: 构造Task Request

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/bitexcel/SheetPilot/tests/agent_contract/data/M1_ecommerce_orders.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/城市产品销售.xlsx",
  "user_request": "请统计已完成订单中，每个城市每个产品类别的销售总额和订单数量。",
  "source": {"sheet": "订单明细", "header_row": 1},
  "filters": [
    {"id": "completed", "field": "订单状态", "operator": "eq", "value": "已完成"}
  ],
  "dimensions": [
    {"id": "city", "field": "城市", "output_name": "城市"},
    {"id": "category", "field": "产品类别", "output_name": "产品类别"}
  ],
  "metrics": [
    {"id": "sales", "function": "sum", "field": "销售额", "output_name": "销售总额"},
    {"id": "orders", "function": "count", "mode": "rows", "output_name": "订单数量"}
  ],
  "output": {"sheet": "城市产品销售", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["completed"],
    "required_dimensions": ["city", "category"],
    "required_metrics": ["sales", "orders"],
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

### 输出工作表结构（部分示例）
| 城市 | 产品类别 | 销售总额 | 订单数量 |
|------|---------|---------|---------|
| 北京 | 电子产品 | 125000 | 18 |
| 北京 | 家居用品 | 88000 | 12 |
| 北京 | 服装鞋帽 | 62000 | 15 |
| 北京 | 食品饮料 | 45000 | 22 |
| 北京 | 图书文具 | 32000 | 10 |
| 上海 | 电子产品 | 115000 | 16 |
| ... | ... | ... | ... |

### 验证点
1. **行数**: 约20行（4城市×5类别，部分组合可能无数据）
2. **列数**: 4列（城市 + 产品类别 + 销售总额 + 订单数量）
3. **过滤准确性**: 只统计"已完成"订单
4. **总销售额**: 约1,280,000
5. **总订单数**: 约240

### 业务逻辑验证
- 北京总销售额 = 125000 + 88000 + 62000 + 45000 + 32000 = 352,000
- 电子产品总销售额 = 125000 + 115000 + ... (跨城市汇总)

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤条件 | 20% | filters包含"已完成" |
| 双维度 | 20% | dimensions包含城市和产品类别 |
| 双指标 | 20% | metrics包含sum和count.rows |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 关键组合（如北京-电子产品）精确匹配 |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 遗漏过滤条件
❌ 错误：`filters: []`
- 会统计所有状态的订单（包括已取消、退货中）

### 陷阱2: 维度顺序影响输出
- `["城市", "产品类别"]` → 先按城市分组（北京的5个类别在一起）
- `["产品类别", "城市"]` → 先按类别分组（电子产品的4个城市在一起）

**推荐**: 按用户自然语序（城市在前）

### 陷阱3: count指标配置错误
❌ 错误：`{"function": "count", "mode": "rows", "field": "订单ID"}`
✅ 正确：`{"function": "count", "mode": "rows"}`（不要field）

## 扩展场景

### 变体1: 只统计北京和上海
```json
"filters": [
  {"id": "completed", "field": "订单状态", "operator": "eq", "value": "已完成"},
  {"id": "cities", "field": "城市", "operator": "in", "value": ["北京", "上海"]}
]
```

### 变体2: 按销售额降序排序
```json
"sort": [{"by": "sales", "direction": "desc"}]
```

### 变体3: 添加平均订单金额
```json
"metrics": [
  {"id": "sales", "function": "sum", "field": "销售额", ...},
  {"id": "orders", "function": "count", "mode": "rows", ...},
  {"id": "avg", "function": "average", "field": "销售额", "output_name": "平均订单额"}
]
```

## 数据生成逻辑

```python
# 10个城市-类别组合的目标值
targets = {
    ("北京", "电子产品"): (125000, 18),
    ("北京", "家居用品"): (88000, 12),
    ...
}

# 每个组合生成：
# 1. 已完成订单（总和=target）
# 2. 已取消/退货中订单（噪声，约30%）
```

## 场景来源
改编自Kaggle电商数据集，简化为SheetPilot可处理的结构。

## 学习要点
M1是典型的电商分析场景，测试Agent对"过滤+双维度+双指标"的综合理解。
