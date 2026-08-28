# S8: 单维度多指标

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: 多指标组合（sum + count.rows + average）

## 数据文件
- **路径**: `tests/agent_contract/data/S8_multi_metrics.xlsx`
- **工作表**: `订单数据`
- **数据量**: 约165行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 订单号 | 文本 | 订单编号 |
| 城市 | 文本 | 北京/上海/深圳/广州/杭州 |
| 订单金额 | 数值 | 金额 |
| 客户ID | 文本 | 客户编号 |

## 用户需求（Prompt）

```
请统计每个城市的总订单金额、订单数量、平均订单金额。

输入文件：tests/agent_contract/data/S8_multi_metrics.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/S8_multi_metrics.xlsx
```

**预期返回**:
- `available_fields`: ["订单号", "城市", "订单金额", "客户ID"]

### Step 2: 构造Task Request

**关键点**: metrics包含3个不同函数

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/S8_multi_metrics.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/城市订单统计.xlsx",
  "user_request": "请统计每个城市的总订单金额、订单数量、平均订单金额。",
  "source": {"sheet": "订单数据", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "city", "field": "城市", "output_name": "城市"}
  ],
  "metrics": [
    {"id": "total", "function": "sum", "field": "订单金额", "output_name": "总订单金额"},
    {"id": "count", "function": "count", "mode": "rows", "output_name": "订单数量"},
    {"id": "avg", "function": "average", "field": "订单金额", "output_name": "平均订单金额"}
  ],
  "output": {"sheet": "城市统计", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["city"],
    "required_metrics": ["total", "count", "avg"],
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
| 城市 | 总订单金额 | 订单数量 | 平均订单金额 |
|------|-----------|---------|-------------|
| 北京 | 120000 | 45 | 2666.67 |
| 上海 | 98000 | 38 | 2578.95 |
| 深圳 | 85000 | 32 | 2656.25 |
| 广州 | 72000 | 28 | 2571.43 |
| 杭州 | 58000 | 22 | 2636.36 |

### 验证点
1. **行数**: 6行（表头 + 5个城市）
2. **列数**: 4列（城市 + 3个指标）
3. **数值验证**:
   - 总金额: sum(订单金额)
   - 订单数量: count(记录数)
   - 平均金额: 总金额 / 订单数量
4. **一致性**: 平均金额 = 总订单金额 / 订单数量（允许±1误差）

### 交叉验证
以北京为例：
- 总订单金额: 120000
- 订单数量: 45
- 平均订单金额: 120000 / 45 = 2666.67 ✓

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | metrics包含3个指标（sum/count.rows/average） |
| 字段绑定 | 15% | 正确绑定"城市"和"订单金额" |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 5个城市×3个指标精确匹配 |
| 一致性验证 | 10% | 平均值=总额/数量 |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: metrics配置错误

❌ **错误1**: count.rows包含field
```json
{"function": "count", "mode": "rows", "field": "订单号"}  // 多余的field
```

❌ **错误2**: sum缺少field
```json
{"function": "sum", "output_name": "总订单金额"}  // 缺少field
```

❌ **错误3**: average缺少field
```json
{"function": "average", "output_name": "平均金额"}  // 缺少field
```

✅ **正确配置**:
```json
[
  {"id": "total", "function": "sum", "field": "订单金额", ...},
  {"id": "count", "function": "count", "mode": "rows"},  // 无field
  {"id": "avg", "function": "average", "field": "订单金额", ...}
]
```

### 陷阱2: 指标ID重复
❌ 错误：
```json
[
  {"id": "m1", "function": "sum", ...},
  {"id": "m1", "function": "count", ...}  // ID重复
]
```

### 陷阱3: 遗漏acceptance
❌ 错误：
```json
"acceptance": {"required_metrics": ["total"]}  // 只写了1个
```

✅ 正确：
```json
"acceptance": {"required_metrics": ["total", "count", "avg"]}
```

### 陷阱4: 使用count.non_empty代替count.rows
- 如果数据全部非空，结果相同，**但写法不同**
- 本场景应使用count.rows（统计订单数）

## 扩展场景

### 变体1: 添加更多指标
用户需求改为："再加上客户数量（去重）"
```json
"metrics": [
  ...,
  {"id": "customers", "function": "count", "mode": "non_empty", "field": "客户ID", "output_name": "客户数"}
]
```

### 变体2: 过滤大额订单
用户需求改为："只统计订单金额≥3000的订单"
```json
"filters": [
  {"id": "large", "field": "订单金额", "operator": "gte", "value": 3000}
]
```

### 变体3: 按总金额降序排序
```json
"sort": [{"by": "total", "direction": "desc"}]
```

## 数据生成逻辑

```python
cities_data = [
    ("北京", 120000, 45),   # (城市, 总金额, 订单数)
    ("上海", 98000, 38),
    ("深圳", 85000, 32),
    ("广州", 72000, 28),
    ("杭州", 58000, 22),
]

# 为每个城市生成精确数量的订单
# 确保订单金额总和=target_amount
# 算法：前n-1笔随机，最后1笔=总额-前n-1笔总和
```

## 指标函数配置速查

| 指标 | 函数 | field | mode | 示例 |
|------|------|-------|------|------|
| 总金额 | sum | ✅ 必须 | ❌ 无 | `{"function": "sum", "field": "金额"}` |
| 平均金额 | average | ✅ 必须 | ❌ 无 | `{"function": "average", "field": "金额"}` |
| 订单数 | count | ❌ 无 | ✅ rows | `{"function": "count", "mode": "rows"}` |
| 客户数 | count | ✅ 必须 | ✅ non_empty | `{"function": "count", "mode": "non_empty", "field": "客户ID"}` |

## 常见用户需求关键词

识别以下组合时应使用多指标：
- "总...、数量、平均..."（明确列举多个指标）
- "汇总统计"、"综合分析"
- "总额和订单数"
- "销售额、客户数、平均单价"

## 与其他场景对比

| 场景 | 维度数 | 指标数 | 复杂度 |
|------|-------|-------|--------|
| S2 | 1 | 1 | 最简单 |
| S8 | 1 | **3** | 中等 |
| S1 | 1 | 4 | 中等 |
| S7 | 2 | 1 | 中等 |

**S8验证Agent对多指标的理解**，特别是不同函数的field/mode配置规则。
