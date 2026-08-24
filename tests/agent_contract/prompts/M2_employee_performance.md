# M2: 员工绩效分析

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: HR场景 + 平均值计算 + 过滤

## 数据文件
- **路径**: `tests/agent_contract/data/M2_employee_performance.xlsx`
- **工作表**: `员工绩效`
- **数据量**: 约74行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 员工ID | 文本 | 员工编号 |
| 姓名 | 文本 | 员工姓名 |
| 部门 | 文本 | 销售部/研发部/财务部/人力资源部 |
| 绩效分数 | 数值 | 60-100分 |
| 等级 | 文本 | 优秀/良好/合格/待改进 |

## 用户需求（Prompt）

```
请统计绩效等级为"优秀"和"良好"的员工，按部门汇总人数和平均绩效分数。

输入文件：tests/agent_contract/data/M2_employee_performance.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 等级 in ["优秀", "良好"]

**分组维度**: 部门

**指标**（2个）:
1. 人数 (count.rows)
2. 平均绩效分数 (average)

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/M2_employee_performance.xlsx
```

### Step 2: 构造Task Request

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/M2_employee_performance.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/部门绩效汇总.xlsx",
  "user_request": "请统计绩效等级为"优秀"和"良好"的员工，按部门汇总人数和平均绩效分数。",
  "source": {"sheet": "员工绩效", "header_row": 1},
  "filters": [
    {"id": "high_perf", "field": "等级", "operator": "in", "value": ["优秀", "良好"]}
  ],
  "dimensions": [
    {"id": "dept", "field": "部门", "output_name": "部门"}
  ],
  "metrics": [
    {"id": "count", "function": "count", "mode": "rows", "output_name": "人数"},
    {"id": "avg_score", "function": "average", "field": "绩效分数", "output_name": "平均绩效分数"}
  ],
  "output": {"sheet": "部门绩效", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["high_perf"],
    "required_dimensions": ["dept"],
    "required_metrics": ["count", "avg_score"],
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
| 部门 | 人数 | 平均绩效分数 |
|------|-----|-------------|
| 销售部 | 15 | 88.5 |
| 研发部 | 18 | 90.2 |
| 财务部 | 10 | 86.8 |
| 人力资源部 | 8 | 87.3 |

### 验证点
1. **行数**: 5行（表头 + 4个部门）
2. **过滤后总人数**: 51（只统计"优秀"+"良好"）
3. **平均分数范围**: 85-92（合理范围）
4. **全体平均**: 约88.5

### 业务逻辑验证
- 原始数据: 74人（包括"合格"、"待改进"）
- 过滤后: 51人（69%）
- 研发部平均分最高（90.2）

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤运算符 | 25% | 使用in运算符，value为数组 |
| 平均值计算 | 25% | metrics使用average + field="绩效分数" |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 4个部门人数和平均分精确匹配 |
| 语义理解 | 10% | 理解"优秀和良好"=OR逻辑 |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 错误的过滤运算符

❌ **错误1**: 使用两个eq过滤条件
```json
"filters": [
  {"id": "f1", "field": "等级", "operator": "eq", "value": "优秀"},
  {"id": "f2", "field": "等级", "operator": "eq", "value": "良好"}
]
```
**后果**: filters是AND关系，等级不能同时="优秀"AND="良好"，结果为空！

❌ **错误2**: value不是数组
```json
{"operator": "in", "value": "优秀"}  // 应该是数组
```

✅ **正确**:
```json
{"operator": "in", "value": ["优秀", "良好"]}
```

### 陷阱2: average配置错误
❌ 错误：`{"function": "average"}`（缺少field）
✅ 正确：`{"function": "average", "field": "绩效分数"}`

### 陷阱3: 遗漏过滤条件
❌ 错误：`filters: []`
- 会统计所有等级的员工，平均分更低（约75分）

## 扩展场景

### 变体1: 只统计研发部
```json
"filters": [
  {"id": "high_perf", "field": "等级", "operator": "in", "value": ["优秀", "良好"]},
  {"id": "rd", "field": "部门", "operator": "eq", "value": "研发部"}
]
```

### 变体2: 按平均分降序排序
```json
"sort": [{"by": "avg_score", "direction": "desc"}]
```

### 变体3: 添加最高分和最低分
**注意**: SheetPilot暂不支持max/min函数，只能用average/sum/count

## 数据生成逻辑

```python
departments = {
    "销售部": {"total": 22, "high_perf": 15, "avg_high": 88.5},
    "研发部": {"total": 25, "high_perf": 18, "avg_high": 90.2},
    "财务部": {"total": 15, "high_perf": 10, "avg_high": 86.8},
    "人力资源部": {"total": 12, "high_perf": 8, "avg_high": 87.3},
}

# 为每个部门生成：
# 1. high_perf个"优秀"或"良好"员工（平均分=avg_high）
# 2. (total - high_perf)个"合格"或"待改进"员工（平均分=70）

# 等级划分规则：
# - 优秀: 90-100分
# - 良好: 80-89分
# - 合格: 70-79分
# - 待改进: 60-69分
```

## in运算符使用场景

| 需求 | 运算符 | value类型 | 示例 |
|------|--------|----------|------|
| 单个值 | eq | 字符串 | `{"operator": "eq", "value": "优秀"}` |
| 多个值（OR） | in | **数组** | `{"operator": "in", "value": ["优秀", "良好"]}` |
| 排除某些值 | ne | 字符串 | `{"operator": "ne", "value": "待改进"}` |

**关键**: "优秀和良好" = OR逻辑 → 使用in运算符

## 场景来源
改编自HR绩效管理场景，测试Agent对in运算符（OR逻辑）的理解。

## 学习要点

**对于Agent开发者**:
1. "A和B"在过滤中通常是OR逻辑（使用in），不是AND
2. in运算符的value**必须是数组**，不是字符串
3. average函数必须指定field

**对于用户**:
- "优秀和良好" = 优秀OR良好（包含两者之一即可）
- "优秀且良好" = 优秀AND良好（必须同时满足，通常不合理）

**M2是典型的HR分析场景**，测试Agent对in运算符和average函数的理解。
