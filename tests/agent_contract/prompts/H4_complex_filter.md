# H4: 多条件复杂过滤

## 场景分类
- **难度**: Hard
- **系列**: H (Hard) - 复杂场景验证
- **测试重点**: 3个过滤条件的组合（AND逻辑）+ 字段选择

## 数据文件
- **路径**: `tests/agent_contract/data/H4_complex_filter.xlsx`
- **工作表**: `客户订单`
- **数据量**: 约386行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 订单号 | 文本 | 订单编号 |
| 客户类型 | 文本 | 企业/个人 |
| 区域 | 文本 | 华东/华南/华北/华中 |
| 订单金额 | 数值 | 订单金额 |
| 支付状态 | 文本 | 已支付/未支付/已退款 |
| 订单状态 | 文本 | 已完成/进行中/已取消 |

## 用户需求（Prompt）

```
请统计已支付、已完成、订单金额大于5000元的企业客户订单，按区域分组汇总总金额和订单数量。

输入文件：tests/agent_contract/data/H4_complex_filter.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件提取**（3个AND组合）:
1. 支付状态 = "已支付"
2. 订单状态 = "已完成"
3. 订单金额 > 5000
4. 客户类型 = "企业" ⚠️ **易遗漏**

**分组维度**: 区域

**指标**:
1. 总金额 (sum)
2. 订单数量 (count.rows)

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/H4_complex_filter.xlsx
```

**预期返回**:
- `available_fields`: ["订单号", "客户类型", "区域", "订单金额", "支付状态", "订单状态"]

### Step 2: 构造Task Request

**关键点**: 4个过滤条件的正确识别与表达

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/H4_complex_filter.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/企业大额订单汇总.xlsx",
  "user_request": "请统计已支付、已完成、订单金额大于5000元的企业客户订单，按区域分组汇总总金额和订单数量。",
  "source": {"sheet": "客户订单", "header_row": 1},
  "filters": [
    {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"},
    {"id": "completed", "field": "订单状态", "operator": "eq", "value": "已完成"},
    {"id": "large", "field": "订单金额", "operator": "gt", "value": 5000},
    {"id": "enterprise", "field": "客户类型", "operator": "eq", "value": "企业"}
  ],
  "dimensions": [
    {"id": "region", "field": "区域", "output_name": "区域"}
  ],
  "metrics": [
    {"id": "total", "function": "sum", "field": "订单金额", "output_name": "总金额"},
    {"id": "count", "function": "count", "mode": "rows", "output_name": "订单数量"}
  ],
  "output": {"sheet": "企业大额订单", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["paid", "completed", "large", "enterprise"],
    "required_dimensions": ["region"],
    "required_metrics": ["total", "count"],
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
| 区域 | 总金额 | 订单数量 |
|------|--------|---------|
| 华东 | 185000 | 28 |
| 华南 | 152000 | 22 |
| 华北 | 138000 | 20 |
| 华中 | 95000 | 14 |

### 验证点
1. **行数**: 5行（表头 + 4个区域）
2. **过滤后总额**: 570000（仅符合全部4个条件的订单）
3. **过滤后订单数**: 84
4. **平均订单金额**: 570000 / 84 ≈ 6786（>5000 ✓）

### 过滤逻辑验证

**原始数据分布**（约386行）:
- 已支付 + 已完成 + >5000 + 企业: 84行 ✅ **符合**
- 已支付 + 已完成 + >5000 + 个人: 38行 ❌（客户类型不符）
- 已支付 + 已完成 + ≤5000 + 企业: 62行 ❌（金额不符）
- 已支付 + 进行中 + >5000 + 企业: 28行 ❌（状态不符）
- 未支付 + ...: 更多不符合条件的记录

**只有同时满足4个条件的84行被统计**

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤条件完整性 | 35% | filters包含全部4个条件 |
| 过滤条件正确性 | 20% | 每个条件的operator和value正确 |
| Acceptance完整性 | 15% | required_filters包含4个ID |
| Runtime验收 | 15% | state=RUNTIME_PASS |
| 输出正确性 | 15% | 4个区域×2个指标精确匹配 |

**通过标准**: ≥ 70分

**关键**: 遗漏任何一个过滤条件直接导致输出错误

## 关键陷阱

### 陷阱1: 遗漏"客户类型=企业"条件

❌ **高频错误**: 只写3个过滤条件
```json
"filters": [
  {"id": "paid", "field": "支付状态", "operator": "eq", "value": "已支付"},
  {"id": "completed", "field": "订单状态", "operator": "eq", "value": "已完成"},
  {"id": "large", "field": "订单金额", "operator": "gt", "value": 5000}
  // 遗漏了"企业客户"
]
```

**后果**: 会统计个人客户的大额订单，总额变为约760000

✅ **正确**: 必须包含4个过滤条件

### 陷阱2: 金额过滤运算符错误

❌ 错误：
```json
{"field": "订单金额", "operator": "gte", "value": 5000}  // >=5000
```
用户说"大于5000"，应该是 `gt`（>），不是 `gte`（≥）

✅ 正确：
```json
{"operator": "gt", "value": 5000}
```

### 陷阱3: 状态字段名混淆

用户需求中有"已支付"和"已完成"两个状态，对应不同字段：
- "已支付" → `支付状态`
- "已完成" → `订单状态`

❌ 错误：
```json
{"field": "状态", "value": "已支付"}  // 没有"状态"字段
```

✅ 正确：分别使用两个字段

### 陷阱4: Acceptance不完整

❌ 错误：
```json
"filters": [
  {"id": "paid", ...},
  {"id": "completed", ...},
  {"id": "large", ...},
  {"id": "enterprise", ...}
],
"acceptance": {
  "required_filters": ["paid", "completed"]  // 只写了2个
}
```

✅ 正确：
```json
"acceptance": {
  "required_filters": ["paid", "completed", "large", "enterprise"]
}
```

## 扩展场景

### 变体1: 更宽松的条件（OR组合模拟）
用户需求改为："统计已支付或已完成的订单"
- SheetPilot不支持真正的OR
- 可以用 `in` 模拟单字段的OR：
  ```json
  {"field": "订单状态", "operator": "in", "value": ["已完成", "进行中"]}
  ```
- 但无法表达"已支付 OR 已完成"（跨字段OR）

### 变体2: 金额区间过滤
用户需求改为："5000-10000元之间的订单"
```json
"filters": [
  {"id": "min", "field": "订单金额", "operator": "gt", "value": 5000},
  {"id": "max", "field": "订单金额", "operator": "lte", "value": 10000}
]
```

### 变体3: 添加排序
用户需求改为："按总金额从高到低排序"
```json
"sort": [{"by": "total", "direction": "desc"}]
```

## 数据生成逻辑

```python
# 区域目标（已支付+已完成+>5000+企业）
regions_target = {
    "华东": (185000, 28),  # (总金额, 订单数)
    "华南": (152000, 22),
    "华北": (138000, 20),
    "华中": (95000, 14),
}

# 为每个区域生成：
# 1. 符合条件的订单（总和=target）
# 2. 个人客户的大额订单（噪声）
# 3. 企业客户的小额订单（噪声）
# 4. 未支付/未完成的订单（噪声）

# 噪声订单约占70%，符合条件的仅30%
```

## 过滤条件复杂度对比

| 场景 | 过滤条件数 | 字段数 | 运算符种类 |
|------|-----------|-------|-----------|
| S6 | 1 | 1 | eq |
| S9 | 2 | 2 | eq |
| H4 | **4** | **4** | eq, gt |
| M1 | 2 | 2 | eq |

**H4是过滤条件最多的简单场景**（M/R系列有更复杂的业务逻辑）

## 常见用户需求关键词

识别以下关键词时应使用多条件过滤：
- "且"、"并且"、"同时满足"
- 多个限定条件并列（用顿号、逗号分隔）
- "大于...的...客户"（嵌套条件）
- "已...、已...、...以上"（3个以上条件）

## 学习要点

**对于Agent开发者**:
1. 仔细分析用户需求，提取**所有**限定条件
2. "企业客户"、"大客户"等词也是过滤条件，不只是"已支付"
3. 数值比较注意 `gt` vs `gte` 的区别
4. 所有过滤条件的ID都要加入acceptance

**对于Oracle设计者**:
1. 验证点应包括"过滤后总额"和"过滤后订单数"
2. 提供"如果遗漏某条件的预期结果"作为对比
3. 噪声数据应占大部分，符合条件的是少数

**对于Runtime**:
- filters数组中的条件是AND关系（全部满足）
- 不支持OR关系（需要在数据层面预处理）
