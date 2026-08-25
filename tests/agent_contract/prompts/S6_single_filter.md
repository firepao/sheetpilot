# S6: 单条件过滤

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: 单个过滤条件的正确使用

## 数据文件
- **路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\\S6_single_filter.xlsx`
- **工作表**: `订单数据`
- **数据量**: 约136行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 订单号 | 文本 | 订单编号 |
| 产品名称 | 文本 | 产品A/B/C/D/E |
| 订单金额 | 数值 | 金额 |
| 支付状态 | 文本 | 已支付/未支付 |

## 用户需求（Prompt）

```
请统计已支付订单的总金额，按产品分组。

输入文件：D:\bitexcel\SheetPilot\tests\agent_contract\data\\S6_single_filter.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\\S6_single_filter.xlsx
```

**预期返回**:
- `available_fields`: ["订单号", "产品名称", "订单金额", "支付状态"]

### Step 2: 构造Task Request

**关键点**: 过滤条件 `支付状态 = 已支付`

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\bitexcel\SheetPilot\tests\agent_contract\data\\S6_single_filter.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/已支付订单汇总.xlsx",
  "user_request": "请统计已支付订单的总金额，按产品分组。",
  "source": {"sheet": "订单数据", "header_row": 1},
  "filters": [
    {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"}
  ],
  "dimensions": [
    {"id": "product", "field": "产品名称", "output_name": "产品名称"}
  ],
  "metrics": [
    {"id": "total_amount", "function": "sum", "field": "订单金额", "output_name": "已支付总额"}
  ],
  "output": {"sheet": "已支付汇总", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["paid"],
    "required_dimensions": ["product"],
    "required_metrics": ["total_amount"],
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
| 产品名称 | 已支付总额 |
|---------|-----------|
| 产品A | 72000 |
| 产品B | 65000 |
| 产品C | 58000 |
| 产品D | 48000 |
| 产品E | 37000 |

### 验证点
1. **行数**: 6行（表头 + 5个产品）
2. **过滤后总额**: 280000（只统计"已支付"）
3. **过滤前总额**: 约420000（包含"未支付"）
4. **过滤准确性**: 必须排除所有"未支付"订单

### 对比验证
如果**不加过滤条件**，结果应该是：
- 产品A: 108000（72000已支付 + 36000未支付）
- 产品B: 97500
- ...

**本场景必须得到280000，而非420000**

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | filters包含"支付状态=已支付" |
| 字段绑定 | 15% | 绑定"支付状态"、"产品名称"、"订单金额" |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 5个产品金额精确匹配，**总额=280000** |
| Acceptance验收 | 10% | required_filters包含过滤条件 |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 遗漏过滤条件
❌ **致命错误**: `filters: []`
- 会统计所有订单（包括未支付），得到错误结果

✅ **正确**:
```json
"filters": [
  {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"}
]
```

### 陷阱2: 过滤条件不在acceptance中
❌ 错误：
```json
"filters": [{"id": "paid", ...}],
"acceptance": {"required_filters": []}  // 空数组！
```

✅ 正确：
```json
"acceptance": {"required_filters": ["paid"]}
```

### 陷阱3: 错误的字段名
❌ 错误：`{"field": "状态", ...}`（表头是"支付状态"）
✅ 正确：`{"field": "支付状态", ...}`

### 陷阱4: 错误的值
❌ 错误：`{"value": "已付款"}`（数据中是"已支付"）
✅ 正确：`{"value": "已支付"}`

### 陷阱5: 错误的运算符
❌ 错误：`{"operator": "in", "value": ["已支付"]}`（单值用eq）
✅ 正确：`{"operator": "eq", "value": "已支付"}`

## 扩展场景

### 变体1: 多值过滤（使用in）
用户需求改为："统计产品A和产品B的已支付总额"
```json
"filters": [
  {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"},
  {"id": "products", "field": "产品名称", "operator": "in", "value": ["产品A", "产品B"]}
]
```
预期结果：
- 产品A: 72000
- 产品B: 65000
- 总计: 137000

### 变体2: 数值过滤
用户需求改为："统计已支付且金额大于5000的订单"
```json
"filters": [
  {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"},
  {"id": "large", "field": "订单金额", "operator": "gt", "value": 5000}
]
```

### 变体3: 不过滤直接汇总
用户需求改为："统计所有订单的总金额"（包括未支付）
```json
"filters": []
```
预期总额: 420000

## 数据生成逻辑

```python
products_paid = {
    "产品A": 72000,
    "产品B": 65000,
    "产品C": 58000,
    "产品D": 48000,
    "产品E": 37000,
}

# 每个产品生成：
# 1. 已支付订单（金额总和=target）
# 2. 未支付订单（金额总和≈target*0.5）
```

## 过滤运算符速查

| 运算符 | 含义 | value类型 | 示例 |
|--------|------|----------|------|
| eq | 等于 | 单值 | `{"operator": "eq", "value": "已支付"}` |
| ne | 不等于 | 单值 | `{"operator": "ne", "value": "已取消"}` |
| gt | 大于 | 数值 | `{"operator": "gt", "value": 5000}` |
| gte | 大于等于 | 数值 | `{"operator": "gte", "value": 5000}` |
| lt | 小于 | 数值 | `{"operator": "lt", "value": 1000}` |
| lte | 小于等于 | 数值 | `{"operator": "lte", "value": 1000}` |
| in | 包含于 | **数组** | `{"operator": "in", "value": ["A", "B"]}` |

## 常见用户需求关键词

识别以下关键词时应添加过滤条件：
- "已支付"、"已完成"、"有效"、"正常"
- "排除"、"不包括"、"去掉"
- "只统计"、"仅统计"、"限定"
- "大于"、"小于"、"超过"、"不足"

**S6是最简单的过滤场景**，为S9（多条件过滤）和R系列（复杂业务过滤）打基础。
