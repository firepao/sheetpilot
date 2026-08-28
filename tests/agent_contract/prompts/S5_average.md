# S5: average 平均值计算

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: average（平均值）的正确使用

## 数据文件
- **路径**: `tests/agent_contract/data/S5_average.xlsx`
- **工作表**: `成绩单`
- **数据量**: 约180行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 班级 | 文本 | 一班/二班/三班/四班/五班/六班 |
| 学生姓名 | 文本 | 学生名 |
| 数学成绩 | 数值 | 60-100分 |

## 用户需求（Prompt）

```
请统计每个班级的数学平均分。

输入文件：tests/agent_contract/data/S5_average.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/S5_average.xlsx
```

**预期返回**:
- `available_fields`: ["班级", "学生姓名", "数学成绩"]

### Step 2: 构造Task Request

**关键点**: average **必须指定field**

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/S5_average.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/班级平均分.xlsx",
  "user_request": "请统计每个班级的数学平均分。",
  "source": {"sheet": "成绩单", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "class", "field": "班级", "output_name": "班级"}
  ],
  "metrics": [
    {"id": "avg_score", "function": "average", "field": "数学成绩", "output_name": "数学平均分"}
  ],
  "output": {"sheet": "班级平均分", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["class"],
    "required_metrics": ["avg_score"],
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
| 班级 | 数学平均分 |
|------|-----------|
| 一班 | 85.0 |
| 二班 | 82.0 |
| 三班 | 78.0 |
| 四班 | 75.0 |
| 五班 | 72.0 |
| 六班 | 68.0 |

### 验证点
1. **行数**: 7行（表头 + 6个班级）
2. **数值类型**: 浮点数（保留1位小数）
3. **平均值精度**: 允许±0.1的误差（浮点运算）
4. **全校平均**: (85+82+78+75+72+68)/6 ≈ 76.67

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | metrics使用average + field="数学成绩" |
| 字段绑定 | 15% | 绑定"班级"和"数学成绩" |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 6个班级平均分精确匹配（误差≤0.1） |
| 格式规范 | 10% | 输出名称="数学平均分" |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 忘记指定field
❌ **错误**:
```json
{"function": "average"}
```
这会导致 `INVALID_COMBINATION` 错误！

✅ **正确**:
```json
{"function": "average", "field": "数学成绩"}
```

### 陷阱2: 使用sum代替average
❌ 错误：`{"function": "sum", "field": "数学成绩"}`
- 结果会是总分（如一班=2550），而非平均分（85.0）

✅ 正确：`{"function": "average", "field": "数学成绩"}`

### 陷阱3: 错误添加mode字段
❌ 错误：`{"function": "average", "field": "数学成绩", "mode": "rows"}`
- mode只用于count函数，average不需要mode

✅ 正确：`{"function": "average", "field": "数学成绩"}`

### 陷阱4: 字段名混淆
❌ 错误：`{"field": "成绩"}`（表头是"数学成绩"）
✅ 正确：`{"field": "数学成绩"}`

## 扩展场景

### 变体1: 同时统计人数和平均分
用户需求改为："统计每个班级的人数和数学平均分"
```json
"metrics": [
  {"id": "count", "function": "count", "mode": "rows", "output_name": "人数"},
  {"id": "avg", "function": "average", "field": "数学成绩", "output_name": "平均分"}
]
```

### 变体2: 过滤优秀学生
用户需求改为："统计每个班级80分以上学生的平均分"
```json
"filters": [
  {"id": "f1", "field": "数学成绩", "operator": "gte", "value": 80}
]
```
预期结果：
- 一班: 90.0（优秀学生平均分）
- 二班: 88.0

### 变体3: 按平均分排序
用户需求改为："按平均分从高到低排序"
```json
"sort": [{"by": "avg_score", "direction": "desc"}]
```

## 数据生成逻辑

```python
classes_target = {
    "一班": 85.0,
    "二班": 82.0,
    "三班": 78.0,
    "四班": 75.0,
    "五班": 72.0,
    "六班": 68.0,
}

# 每个班级30人
# 生成成绩时确保平均值精确等于target
# 算法：前29人随机，最后1人=target*30 - sum(前29人)
```

## 与其他聚合函数对比

| 函数 | 是否需要field | 返回类型 | 用途 |
|------|--------------|---------|------|
| sum | ✅ 必须 | 数值 | 求总和 |
| average | ✅ 必须 | 浮点数 | 求平均 |
| count.rows | ❌ 禁止 | 整数 | 统计行数 |
| count.non_empty | ✅ 必须 | 整数 | 统计非空值数 |

## 常见用户需求关键词

识别以下关键词时应使用average：
- "平均"、"均值"、"平均数"
- "人均"（如"人均销售额"）
- "单均"（如"单均订单金额"）
- "平均分"、"平均成绩"

**不要混淆**：
- "总分" → sum
- "人数" → count.rows
- "平均分" → average
