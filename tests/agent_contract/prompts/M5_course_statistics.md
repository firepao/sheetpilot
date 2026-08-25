# M5: 在线课程学习统计

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 教育场景 + 数值范围过滤 + 双指标汇总

## 数据文件
- **路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\M5_course_statistics.xlsx`
- **工作表**: `学员数据`
- **数据量**: 约576行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 学员ID | 文本 | 学员编号 |
| 姓名 | 文本 | 学员姓名 |
| 课程名称 | 文本 | Python基础/数据分析实战/机器学习入门/前端开发/产品经理/UI设计 |
| 课程类型 | 文本 | 编程/数据/AI/产品/设计 |
| 学习时长(小时) | 数值 | 累计学习时长 |
| 完成度(%) | 数值 | 0-100 |
| 考试成绩 | 数值 | 0-100 |
| 付费金额 | 数值 | 实际支付金额（0表示未付费）|

## 用户需求（Prompt）

```
请统计完成度大于80%的学员，按课程名称汇总学员数量和平均学习时长。

输入文件：D:\bitexcel\SheetPilot\tests\agent_contract\data\M5_course_statistics.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 完成度 > 80（注意是>不是≥）

**分组维度**: 课程名称

**指标**（2个）:
1. 学员数量 (count.rows)
2. 平均学习时长 (average)

**业务含义**:
- 完成度>80%: 高完成度学员，学习效果较好
- 平均学习时长: 反映课程难度和学员投入程度

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\M5_course_statistics.xlsx
```

**预期返回**:
- `available_fields`: ["学员ID", "姓名", "课程名称", "课程类型", "学习时长(小时)", "完成度(%)", "考试成绩", "付费金额"]

### Step 2: 构造Task Request

**关键点**: 过滤运算符是 `gt`（>），不是 `gte`（≥）

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\bitexcel\\SheetPilot\\tests\\agent_contract\\data\\M5_course_statistics.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/课程完成情况.xlsx",
  "user_request": "请统计完成度大于80%的学员，按课程名称汇总学员数量和平均学习时长。",
  "source": {"sheet": "学员数据", "header_row": 1},
  "filters": [
    {"id": "high_completion", "field": "完成度(%)", "operator": "gt", "value": 80}
  ],
  "dimensions": [
    {"id": "course", "field": "课程名称", "output_name": "课程名称"}
  ],
  "metrics": [
    {"id": "student_count", "function": "count", "mode": "rows", "output_name": "学员数量"},
    {"id": "avg_hours", "function": "average", "field": "学习时长(小时)", "output_name": "平均学习时长"}
  ],
  "output": {"sheet": "课程完成统计", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["high_completion"],
    "required_dimensions": ["course"],
    "required_metrics": ["student_count", "avg_hours"],
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
| 课程名称 | 学员数量 | 平均学习时长 |
|---------|---------|-------------|
| Python基础 | 68 | 95.5 |
| 数据分析实战 | 72 | 112.3 |
| 机器学习入门 | 58 | 128.7 |
| 前端开发 | 65 | 102.8 |
| 产品经理 | 55 | 88.2 |
| UI设计 | 62 | 96.4 |

### 验证点
1. **行数**: 7行（表头 + 6门课程）
2. **过滤后学员数**: 380人（完成度>80%）
3. **原始学员数**: 约576人（完成度>80%占约66%）
4. **平均学习时长范围**: 88-129小时（合理范围）

### 业务逻辑验证
- **机器学习入门**学习时长最长（128.7小时），课程难度最高
- **产品经理**学习时长最短（88.2小时），相对轻量
- 完成度>80%的学员约占2/3，说明课程质量较好

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤运算符 | 30% | **使用gt（>），不是gte（≥）** |
| 过滤字段 | 20% | 字段名正确（"完成度(%)"） |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 6门课程数据精确匹配 |
| 指标配置 | 10% | count.rows + average |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 过滤运算符错误

❌ **错误1**: 使用 `gte`（≥）
```json
{"operator": "gte", "value": 80}
```
**后果**: 会统计完成度≥80的学员（包括80%），多统计约15人

❌ **错误2**: 使用 `eq`（=）
```json
{"operator": "eq", "value": 80}
```
**后果**: 只统计完成度=80的学员（极少数）

✅ **正确**:
```json
{"operator": "gt", "value": 80}
```

**用户说"大于80%"，不是"大于等于80%"**

### 陷阱2: 字段名包含特殊字符

**问题**: 字段名是"完成度(%)"，包含括号

❌ **错误**: 遗漏括号
```json
{"field": "完成度", ...}
```

✅ **正确**:
```json
{"field": "完成度(%)", ...}
```

**字段名必须精确匹配**，包括括号、空格等特殊字符

### 陷阱3: 遗漏过滤条件
❌ 错误：`filters: []`
- 会统计所有学员（包括完成度低的），学员数约576人

✅ 正确：只统计完成度>80%的学员

### 陷阱4: 统计错误的字段
❌ 错误：统计考试成绩平均值
```json
{"function": "average", "field": "考试成绩", ...}
```

✅ 正确：统计学习时长平均值
```json
{"function": "average", "field": "学习时长(小时)", ...}
```

## 扩展场景

### 变体1: 统计付费学员
用户需求改为："统计已付费且完成度>80%的学员"
```json
"filters": [
  {"id": "high_comp", "field": "完成度(%)", "operator": "gt", "value": 80},
  {"id": "paid", "field": "付费金额", "operator": "gt", "value": 0}
]
```

### 变体2: 按课程类型分组
用户需求改为："按课程类型（编程/数据/AI等）汇总"
```json
"dimensions": [
  {"id": "type", "field": "课程类型", "output_name": "课程类型"}
]
```
预期结果：5行（5种课程类型）

### 变体3: 添加平均考试成绩
```json
"metrics": [
  {"id": "count", "function": "count", "mode": "rows", "output_name": "学员数量"},
  {"id": "avg_hours", "function": "average", "field": "学习时长(小时)", "output_name": "平均学习时长"},
  {"id": "avg_score", "function": "average", "field": "考试成绩", "output_name": "平均考试成绩"}
]
```

### 变体4: 按学习时长降序排序
```json
"sort": [{"by": "avg_hours", "direction": "desc"}]
```
预期第一行：机器学习入门（128.7小时）

### 变体5: 完成度区间统计
用户需求改为："统计完成度在60%-80%之间的学员"
```json
"filters": [
  {"id": "min", "field": "完成度(%)", "operator": "gt", "value": 60},
  {"id": "max", "field": "完成度(%)", "operator": "lte", "value": 80}
]
```

## 数据生成逻辑

```python
courses = [
    ("Python基础", "编程", 399, 100),     # (课程名, 类型, 价格, 难度系数)
    ("数据分析实战", "数据", 599, 120),
    ("机器学习入门", "AI", 899, 140),
    ("前端开发", "编程", 499, 110),
    ("产品经理", "产品", 699, 90),
    ("UI设计", "设计", 799, 100),
]

for course_name, course_type, price, difficulty in courses:
    student_count = random.randint(80, 150)
    
    for i in range(student_count):
        # 学习时长根据难度系数生成
        study_hours = random.randint(difficulty - 30, difficulty + 50)
        
        # 完成度：66%的学员>80%，34%的学员≤80%
        if random.random() < 0.66:
            completion = random.randint(81, 100)  # 高完成度
        else:
            completion = random.randint(30, 80)   # 低完成度
        
        # 考试成绩与完成度正相关
        score = random.randint(
            max(0, completion - 20),
            min(100, completion + 10)
        )
        
        # 付费率85%
        paid = price if random.random() < 0.85 else 0
```

**关键**: 66%学员完成度>80%，34%学员≤80%

## 数值比较运算符速查

| 运算符 | 含义 | 示例 | 本场景 |
|--------|------|------|--------|
| **gt** | > 大于 | `{"operator": "gt", "value": 80}` | ✅ |
| **gte** | ≥ 大于等于 | `{"operator": "gte", "value": 80}` | ❌ |
| **lt** | < 小于 | `{"operator": "lt", "value": 60}` | ❌ |
| **lte** | ≤ 小于等于 | `{"operator": "lte", "value": 60}` | ❌ |
| **eq** | = 等于 | `{"operator": "eq", "value": 80}` | ❌ |

**关键**: "大于"用gt，"大于等于"用gte，不要混淆

## 业务场景说明

### 完成度分层

| 完成度 | 学员类型 | 占比 | 特征 |
|--------|---------|------|------|
| >80% | 优秀学员 | 66% | **本场景统计对象** |
| 60%-80% | 中等学员 | 20% | 需要督促 |
| <60% | 低完成度学员 | 14% | 流失风险高 |

### 实际应用场景
- **课程运营**: 关注高完成度学员，分析课程吸引力
- **教学优化**: 学习时长反映课程难度，帮助优化内容
- **学员画像**: 高完成度学员更可能续费或推荐

## 与其他场景对比

| 场景 | 业务领域 | 过滤运算符 | 指标复杂度 |
|------|---------|-----------|-----------|
| M5 | 在线教育 | gt（数值比较） | count + average |
| M2 | HR绩效 | in（多值OR） | count + average |
| H4 | 电商 | gt + eq组合 | 多条件AND |

**M5是典型的教育数据分析场景**，测试Agent对数值比较运算符的理解

## 场景来源
改编自在线教育平台学习数据，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. "大于"和"大于等于"的区别很重要（gt vs gte）
2. 字段名包含特殊字符（括号）时，必须精确匹配
3. 数值过滤的阈值判断要准确（80%是临界值，不在统计范围内）

**对于业务用户**:
- 完成度>80%是优秀学员的标准（行业惯例）
- 学习时长反映课程难度和学员投入
- 高完成度学员是运营关注的核心人群

**M5是典型的在线教育场景**，测试Agent对数值范围过滤（gt运算符）的准确理解。
