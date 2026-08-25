# M8: 项目工时统计

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 项目管理场景 + count.non_empty去重 + 单过滤

## 数据文件
- **路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\M8_project_hours.xlsx`
- **工作表**: `工时记录`
- **数据量**: 约601行（30天 × 20人）
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 工时ID | 文本 | 工时记录编号 |
| 员工姓名 | 文本 | 员工1-员工20 |
| 项目名称 | 文本 | 项目A/B/C/D |
| 任务类型 | 文本 | 需求分析/设计/开发/测试/部署 |
| 工作日期 | 日期 | 2024-07-01 到 2024-07-30 |
| 工时(小时) | 数值 | 当日工时 6-10小时 |
| 是否加班 | 文本 | 是/否 |
| 工作内容 | 文本 | 任务描述 |

## 数据特殊性

**时间序列特征**:
- 每个员工每天提交一条工时记录
- 连续30天数据
- 员工可能在不同项目间切换

**关键挑战**: 统计"参与人数"需要去重
- 同一员工在同一项目可能有多条记录（多天）
- 需要使用 `count.non_empty` 对员工字段去重

## 用户需求（Prompt）

```
请统计各项目的总工时和参与人数（去重）。

输入文件：D:\bitexcel\SheetPilot\tests\agent_contract\data\M8_project_hours.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 无（统计全部30天）

**分组维度**: 项目名称

**指标**（2个）:
1. 总工时 (sum)
2. 参与人数 (count.non_empty) ← **关键：去重统计**

**注意**: 
- 参与人数 ≠ 工时记录数
- 同一员工在项目A工作了15天 → 15条记录，但只算1人

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\M8_project_hours.xlsx
```

**预期返回**:
- `available_fields`: ["工时ID", "员工姓名", "项目名称", "任务类型", "工作日期", "工时(小时)", "是否加班", "工作内容"]

### Step 2: 构造Task Request

**关键点**: 参与人数用 `count.non_empty` + `field="员工姓名"`

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\bitexcel\\SheetPilot\\tests\\agent_contract\\data\\M8_project_hours.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/项目工时统计.xlsx",
  "user_request": "请统计各项目的总工时和参与人数（去重）。",
  "source": {"sheet": "工时记录", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "project", "field": "项目名称", "output_name": "项目名称"}
  ],
  "metrics": [
    {"id": "total_hours", "function": "sum", "field": "工时(小时)", "output_name": "总工时"},
    {"id": "member_count", "function": "count", "mode": "non_empty", "field": "员工姓名", "output_name": "参与人数"}
  ],
  "output": {"sheet": "项目工时", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["project"],
    "required_metrics": ["total_hours", "member_count"],
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
| 项目名称 | 总工时 | 参与人数 |
|---------|--------|---------|
| 项目A | 1250 | 18 |
| 项目B | 1100 | 15 |
| 项目C | 950 | 12 |
| 项目D | 850 | 10 |

### 验证点
1. **行数**: 5行（表头 + 4个项目）
2. **总工时**: 4150小时（30天 × 20人 × 平均7小时 ≈ 4200）
3. **参与人数**: 去重后的唯一员工数
4. **工时记录数**: 约600条（30天 × 20人）

### 关键验证：去重逻辑

**示例数据**:
- 项目A: 员工1工作15天、员工2工作12天、员工3工作10天...（总计18人）
- 工时记录数: 约180条（18人 × 平均10天）
- 参与人数: **18人**（去重后）

**对比**:
- 如果用 `count.rows`: 结果=180（记录数，错误）
- 如果用 `count.non_empty`: 结果=18（去重人数，正确）

### 业务逻辑验证
- **项目A**: 总工时最多（1250），参与人数最多（18），规模最大
- **项目D**: 总工时最少（850），参与人数最少（10），规模最小
- **人均工时**: 项目A = 1250 / 18 ≈ 69小时/人

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| count配置 | 35% | **使用count.non_empty + field="员工姓名"** |
| sum配置 | 20% | 正确统计"工时(小时)" |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 4个项目数据精确匹配 |
| 去重理解 | 5% | 理解"参与人数"需要去重 |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 错误使用count.rows

❌ **致命错误**:
```json
{"function": "count", "mode": "rows", "output_name": "参与人数"}
```

**后果**: 统计的是工时记录数（约180条），不是去重人数（18人）

**示例**:
- 员工1在项目A工作了15天 → 15条记录
- 用count.rows: 计为15人 ❌
- 用count.non_empty: 计为1人 ✅

✅ **正确**:
```json
{"function": "count", "mode": "non_empty", "field": "员工姓名", ...}
```

### 陷阱2: count.non_empty缺少field

❌ **错误**:
```json
{"function": "count", "mode": "non_empty"}
```
**后果**: `INVALID_COMBINATION` 错误（count.non_empty必须指定field）

✅ **正确**: 必须指定field

### 陷阱3: 字段名错误

❌ **错误1**: 字段名不匹配
```json
{"field": "员工", ...}  // 字段名是"员工姓名"
```

❌ **错误2**: 统计错误的字段
```json
{"field": "工时ID", ...}  // 工时ID是唯一的，不需要去重
```

✅ **正确**: `{"field": "员工姓名", ...}`

### 陷阱4: sum字段选择错误

❌ **错误**: 统计工作日期
```json
{"function": "sum", "field": "工作日期", ...}
```

✅ **正确**: `{"function": "sum", "field": "工时(小时)", ...}`

## 扩展场景

### 变体1: 只统计某个项目
用户需求改为："只统计项目A的工时和人数"
```json
"filters": [
  {"id": "proj_a", "field": "项目名称", "operator": "eq", "value": "项目A"}
]
```
预期结果：1行（项目A）

### 变体2: 按任务类型分组
用户需求改为："统计各任务类型的工时和人数"
```json
"dimensions": [
  {"id": "task", "field": "任务类型", "output_name": "任务类型"}
]
```
预期结果：5行（5种任务类型）

### 变体3: 双维度分析
用户需求改为："统计各项目各任务类型的工时"
```json
"dimensions": [
  {"id": "project", "field": "项目名称", "output_name": "项目名称"},
  {"id": "task", "field": "任务类型", "output_name": "任务类型"}
]
```
预期结果：约20行（4项目 × 5任务类型）

### 变体4: 添加加班工时统计
```json
"filters": [
  {"id": "overtime", "field": "是否加班", "operator": "eq", "value": "是"}
]
```

### 变体5: 按总工时降序排序
```json
"sort": [{"by": "total_hours", "direction": "desc"}]
```
预期第一行：项目A（1250小时）

## 数据生成逻辑

```python
projects = ["项目A", "项目B", "项目C", "项目D"]
employees = [f"员工{i}" for i in range(1, 21)]  # 20个员工
task_types = ["需求分析", "设计", "开发", "测试", "部署"]

# 项目人员分配
project_members = {
    "项目A": employees[0:18],   # 18人
    "项目B": employees[2:17],   # 15人
    "项目C": employees[8:20],   # 12人
    "项目D": employees[10:20],  # 10人
}

# 生成30天数据
for day in range(1, 31):
    current_date = datetime(2024, 7, day)
    
    for employee in employees:
        # 每个员工随机选择一个项目工作
        project = random.choice(projects)
        
        # 只有该项目的成员才会记录工时
        if employee in project_members[project]:
            task_type = random.choice(task_types)
            hours = random.choice([6, 7, 8, 9, 10])
            overtime = "是" if hours >= 9 else "否"
            content = f"{task_type}相关工作"
            
            # 添加记录
```

**关键**: 
- 每个员工每天只记录一条工时（对应一个项目）
- 同一员工在项目A可能工作多天 → 多条记录 → 需要去重
- 项目A有18个成员，工时记录约180条（18人 × 平均10天）

## count.rows vs count.non_empty对比

### 场景对比

| 场景 | 数据特征 | 应该用 | 原因 |
|------|---------|--------|------|
| **统计订单数** | 每行=1个订单 | count.rows | 不需要去重 |
| **统计有邮箱的客户数** | 客户ID可能重复 | count.non_empty | 去重+排除空值 |
| **统计项目参与人数** | 员工姓名重复出现 | count.non_empty | **去重统计唯一人数** |

### 本场景示例

**原始数据**（项目A，部分）:
| 工时ID | 员工姓名 | 项目名称 | 工时 |
|--------|---------|---------|------|
| T001 | 员工1 | 项目A | 8 |
| T002 | 员工2 | 项目A | 7 |
| T003 | 员工1 | 项目A | 9 |  ← 员工1再次出现
| T004 | 员工3 | 项目A | 8 |
| T005 | 员工1 | 项目A | 7 |  ← 员工1第三次出现

**统计结果对比**:
- `count.rows`: 5（记录数）❌
- `count.non_empty("员工姓名")`: 3（唯一员工：员工1/2/3）✅

## 项目管理指标说明

### 常见项目统计指标

| 指标 | 计算方式 | 本场景是否统计 |
|------|---------|--------------|
| **总工时** | sum(工时) | ✅ |
| **参与人数** | count.non_empty(员工) | ✅ |
| **人均工时** | 总工时 / 参与人数 | ❌（需手动计算） |
| **加班工时** | sum(工时) where 是否加班=是 | ❌（可扩展） |
| **工作天数** | count(distinct 日期) | ❌（SheetPilot暂不支持） |

### 项目规模评估

| 项目 | 总工时 | 参与人数 | 人均工时 | 规模评估 |
|------|--------|---------|---------|---------|
| 项目A | 1250 | 18 | 69.4 | 大型 |
| 项目B | 1100 | 15 | 73.3 | 中型 |
| 项目C | 950 | 12 | 79.2 | 中型 |
| 项目D | 850 | 10 | 85.0 | 小型 |

## 与其他场景对比

| 场景 | count类型 | 去重需求 | 业务领域 |
|------|-----------|---------|---------|
| S3 | count.rows | 不需要 | 基础统计 |
| S4 | count.non_empty | 排除空值 | 客户数据 |
| M8 | count.non_empty | **去重统计唯一人数** | 项目管理 |

**M8的特殊性**: count.non_empty用于去重，而非排除空值

## 场景来源
改编自软件项目管理系统工时数据，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. **关键**: "参与人数"需要去重 → 用count.non_empty + field="员工姓名"
2. count.rows统计记录数，count.non_empty统计唯一值数
3. count.non_empty必须指定field，不能省略

**对于业务用户**:
- 工时记录数 ≠ 参与人数（同一人多天工作）
- 去重统计是项目管理的常见需求
- 人均工时 = 总工时 / 参与人数（需手动计算）

**M8是典型的项目管理场景**，测试Agent对count.non_empty去重功能的理解，这是count.non_empty的**核心用法之一**（去重统计）。
