# S4: count.non_empty 非空值统计

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: count.non_empty（统计非空值数量）的正确使用

## 数据文件
- **路径**: `D:/bitexcel/SheetPilot/tests/agent_contract/data/S4_count_non_empty.xlsx`
- **工作表**: `用户数据`
- **数据量**: 约437行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 注册渠道 | 文本 | 官网/APP/小程序 |
| 用户ID | 文本 | 用户编号 |
| 邮箱 | 文本 | 邮箱地址（**部分为空**） |

## 用户需求（Prompt）

```
请统计每个注册渠道有多少用户填写了邮箱（邮箱字段非空的用户数）。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/S4_count_non_empty.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:/bitexcel/SheetPilot/tests/agent_contract/data/S4_count_non_empty.xlsx
```

**预期返回**:
- `available_fields`: ["注册渠道", "用户ID", "邮箱"]
- 注意：`null_ratio` 字段会显示邮箱的空值比例约35%

### Step 2: 构造Task Request

**关键点**: count.non_empty **必须指定field**

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/bitexcel/SheetPilot/tests/agent_contract/data/S4_count_non_empty.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/渠道邮箱统计.xlsx",
  "user_request": "请统计每个注册渠道有多少用户填写了邮箱（邮箱字段非空的用户数）。",
  "source": {"sheet": "用户数据", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "channel", "field": "注册渠道", "output_name": "注册渠道"}
  ],
  "metrics": [
    {"id": "email_count", "function": "count", "mode": "non_empty", "field": "邮箱", "output_name": "填写邮箱用户数"}
  ],
  "output": {"sheet": "渠道邮箱统计", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["channel"],
    "required_metrics": ["email_count"],
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
| 注册渠道 | 填写邮箱用户数 |
|---------|--------------|
| 官网 | 110 |
| APP | 95 |
| 小程序 | 80 |

### 验证点
1. **行数**: 4行（表头 + 3个渠道）
2. **非空总数**: 285（不是437，因为排除了空值）
3. **空值比例**: 约35%（152个空值）
4. **count逻辑**: 只统计"邮箱"字段非空的记录

### 对比验证
如果用count.rows统计，结果应该是：
- 官网: 170（110非空 + 60空）
- APP: 147（95非空 + 52空）
- 小程序: 120（80非空 + 40空）

**本场景必须得到285，而非437**

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | metrics使用count + mode=non_empty + field="邮箱" |
| 字段绑定 | 15% | 绑定"注册渠道"和"邮箱" |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 3个渠道计数精确匹配，**总数=285** |
| 语义理解 | 10% | 理解"填写了邮箱"="非空统计" |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 忘记指定field
❌ **错误**:
```json
{"function": "count", "mode": "non_empty"}
```
这会导致 `INVALID_COMBINATION` 错误！

✅ **正确**:
```json
{"function": "count", "mode": "non_empty", "field": "邮箱"}
```

### 陷阱2: 使用count.rows
❌ 错误：`{"function": "count", "mode": "rows"}`
- 结果会是437（全部记录数），而非285

✅ 正确：`{"function": "count", "mode": "non_empty", "field": "邮箱"}`

### 陷阱3: 统计错误的字段
❌ 错误：`{"field": "用户ID"}`（用户ID全部非空）
✅ 正确：`{"field": "邮箱"}`（邮箱部分为空）

## 扩展场景

### 变体1: 同时统计总数和非空数
用户需求改为："统计每个渠道的总用户数和填写邮箱的用户数"
- metrics添加两个：
  ```json
  [
    {"id": "total", "function": "count", "mode": "rows", "output_name": "总用户数"},
    {"id": "has_email", "function": "count", "mode": "non_empty", "field": "邮箱", "output_name": "填写邮箱数"}
  ]
  ```
- 可计算填写率：has_email / total

### 变体2: 只统计官网渠道
- 添加 `filters`: [{"id": "f1", "field": "注册渠道", "operator": "eq", "value": "官网"}]
- 预期结果：110

## 与S3对比

| 特性 | S3 (count.rows) | S4 (count.non_empty) |
|------|----------------|---------------------|
| 统计对象 | 记录行数 | 某字段非空值数 |
| field字段 | **禁止**提供 | **必须**提供 |
| 空值影响 | 无影响 | 排除空值 |
| 用户需求关键词 | "订单数"、"记录数" | "填写了"、"有效值"、"非空" |

## 数据生成逻辑

```python
channels_data = {
    "官网": (170, 110),    # (总数, 非空数)
    "APP": (147, 95),
    "小程序": (120, 80),
}

# 为每个渠道生成记录
# 前non_empty个记录有邮箱
# 后(total - non_empty)个记录邮箱为空(None)
```

**验证要点**: 
- 总记录数: 170 + 147 + 120 = 437
- 非空邮箱数: 110 + 95 + 80 = 285
- 空值数: 437 - 285 = 152（约35%空值率）
