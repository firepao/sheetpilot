# M7: 客户投诉分析

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 客服场景 + 双维度交叉分析 + 单指标统计

## 数据文件
- **路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\M7_complaint_analysis.xlsx`
- **工作表**: `投诉记录`
- **数据量**: 约426行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 投诉单号 | 文本 | 工单编号 |
| 客户姓名 | 文本 | 投诉客户 |
| 投诉类型 | 文本 | 产品质量/物流配送/售后服务/价格问题/虚假宣传 |
| 产品类别 | 文本 | 数码/家电/服装/食品/家居 |
| 严重程度 | 文本 | 低/中/高 |
| 处理状态 | 文本 | 已解决/处理中/已关闭 |
| 响应时长(小时) | 数值 | 从投诉到首次响应的时长 |
| 满意度 | 数值 | 1-5分 |
| 登记日期 | 日期 | 投诉登记时间 |

## 用户需求（Prompt）

```
请统计已处理的客诉单，按投诉类型和处理状态交叉汇总投诉数量。

输入文件：D:\bitexcel\SheetPilot\tests\agent_contract\data\M7_complaint_analysis.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 处理状态 in ["已解决", "处理中"]（排除"已关闭"）

**注意**: "已处理"在业务上指"已解决"或"处理中"，不包括"已关闭"（关闭表示未处理直接关单）

**分组维度**（2个）:
1. 投诉类型
2. 处理状态

**指标**: 投诉数量 (count.rows)

**输出特点**: 双维度交叉表，每种(投诉类型, 处理状态)组合一行

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\M7_complaint_analysis.xlsx
```

**预期返回**:
- `available_fields`: ["投诉单号", "客户姓名", "投诉类型", "产品类别", "严重程度", "处理状态", "响应时长(小时)", "满意度", "登记日期"]

### Step 2: 构造Task Request

**关键点**: 
1. 过滤条件用in运算符（"已解决"或"处理中"）
2. 双维度分组（投诉类型 × 处理状态）

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\bitexcel\\SheetPilot\\tests\\agent_contract\\data\\M7_complaint_analysis.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/投诉分析报告.xlsx",
  "user_request": "请统计已处理的客诉单，按投诉类型和处理状态交叉汇总投诉数量。",
  "source": {"sheet": "投诉记录", "header_row": 1},
  "filters": [
    {"id": "handled", "field": "处理状态", "operator": "in", "value": ["已解决", "处理中"]}
  ],
  "dimensions": [
    {"id": "type", "field": "投诉类型", "output_name": "投诉类型"},
    {"id": "status", "field": "处理状态", "output_name": "处理状态"}
  ],
  "metrics": [
    {"id": "count", "function": "count", "mode": "rows", "output_name": "投诉数量"}
  ],
  "output": {"sheet": "投诉统计", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["handled"],
    "required_dimensions": ["type", "status"],
    "required_metrics": ["count"],
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
| 投诉类型 | 处理状态 | 投诉数量 |
|---------|---------|---------|
| 产品质量 | 已解决 | 58 |
| 产品质量 | 处理中 | 22 |
| 物流配送 | 已解决 | 52 |
| 物流配送 | 处理中 | 18 |
| 售后服务 | 已解决 | 45 |
| 售后服务 | 处理中 | 15 |
| 价格问题 | 已解决 | 38 |
| 价格问题 | 处理中 | 12 |
| 虚假宣传 | 已解决 | 32 |
| 虚假宣传 | 处理中 | 8 |

### 验证点
1. **行数**: 11行（表头 + 5类型×2状态=10行）
2. **过滤后总数**: 300个投诉单（只统计"已解决"+"处理中"）
3. **原始总数**: 约426个（"已关闭"约占30%）
4. **交叉分析**: 每种投诉类型都有"已解决"和"处理中"两行

### 业务逻辑验证
- **产品质量**投诉最多（80个），是客服重点关注领域
- **虚假宣传**投诉最少（40个）
- **已解决占比**: 约75%（225/300），**处理中占比**: 约25%（75/300）

**交叉表用途**: 
- 横向看：某类投诉的处理进度（已解决 vs 处理中）
- 纵向看：不同类型投诉的数量对比

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤运算符 | 25% | 使用in运算符，value为数组["已解决", "处理中"] |
| 双维度配置 | 25% | dimensions包含投诉类型和处理状态 |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 10个组合数据精确匹配 |
| 业务理解 | 10% | 理解"已处理"不包括"已关闭" |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 过滤条件理解错误

❌ **错误1**: 理解为"处理状态=已解决"（遗漏"处理中"）
```json
{"operator": "eq", "value": "已解决"}
```
**后果**: 只统计225个"已解决"，遗漏75个"处理中"

❌ **错误2**: 使用两个eq过滤条件
```json
"filters": [
  {"id": "f1", "field": "处理状态", "operator": "eq", "value": "已解决"},
  {"id": "f2", "field": "处理状态", "operator": "eq", "value": "处理中"}
]
```
**后果**: filters是AND关系，处理状态不能同时="已解决"AND="处理中"，结果为空！

✅ **正确**:
```json
{"operator": "in", "value": ["已解决", "处理中"]}
```

### 陷阱2: 误统计"已关闭"状态

❌ 错误：`filters: []`（无过滤）
- 会统计所有状态（包括"已关闭"），投诉数约426个

✅ 正确：排除"已关闭"

**业务含义**: "已关闭"表示客户投诉后撤诉或无效投诉，直接关单，不算"已处理"

### 陷阱3: 维度数量不足

❌ **错误**: 只用一个维度
```json
"dimensions": [
  {"id": "type", "field": "投诉类型", "output_name": "投诉类型"}
]
```
**后果**: 只统计各投诉类型总数，看不到处理进度（已解决 vs 处理中）

✅ **正确**: 必须包含2个维度

### 陷阱4: 维度顺序影响输出

**注意**: dimensions顺序会影响输出排序

- `["投诉类型", "处理状态"]` → 先按类型分组（产品质量的2个状态在一起）
- `["处理状态", "投诉类型"]` → 先按状态分组（已解决的5个类型在一起）

**推荐**: 按用户自然语序（投诉类型在前）

## 扩展场景

### 变体1: 只统计"已解决"
用户需求改为："统计已彻底解决的投诉"
```json
"filters": [
  {"id": "resolved", "field": "处理状态", "operator": "eq", "value": "已解决"}
]
```
预期结果：5行（5种投诉类型，都是"已解决"）

### 变体2: 三维度交叉分析
用户需求改为："按投诉类型、产品类别、处理状态交叉统计"
```json
"dimensions": [
  {"id": "type", "field": "投诉类型", "output_name": "投诉类型"},
  {"id": "category", "field": "产品类别", "output_name": "产品类别"},
  {"id": "status", "field": "处理状态", "output_name": "处理状态"}
]
```
预期结果：约50行（5类型 × 5产品 × 2状态）

### 变体3: 添加平均响应时长
```json
"metrics": [
  {"id": "count", "function": "count", "mode": "rows", "output_name": "投诉数量"},
  {"id": "avg_response", "function": "average", "field": "响应时长(小时)", "output_name": "平均响应时长"}
]
```

### 变体4: 只统计严重投诉
```json
"filters": [
  {"id": "handled", "field": "处理状态", "operator": "in", "value": ["已解决", "处理中"]},
  {"id": "severe", "field": "严重程度", "operator": "eq", "value": "高"}
]
```

### 变体5: 按投诉数量降序排序
```json
"sort": [{"by": "count", "direction": "desc"}]
```

## 数据生成逻辑

```python
complaint_types = ["产品质量", "物流配送", "售后服务", "价格问题", "虚假宣传"]
product_categories = ["数码", "家电", "服装", "食品", "家居"]
severities = ["低", "中", "高"]
statuses = ["已解决", "处理中", "已关闭"]

# 状态分布：已解决53%、处理中17%、已关闭30%
# 目标：已解决+处理中 = 70%

for month in range(6):
    complaint_count = random.randint(50, 100)
    
    for _ in range(complaint_count):
        complaint_type = random.choice(complaint_types)
        product = random.choice(product_categories)
        severity = random.choice(severities)
        
        # 状态分布
        rand = random.random()
        if rand < 0.53:
            status = "已解决"
            response_hours = random.randint(1, 24)
            satisfaction = random.randint(3, 5)
        elif rand < 0.70:
            status = "处理中"
            response_hours = random.randint(2, 48)
            satisfaction = random.randint(2, 4)
        else:
            status = "已关闭"
            response_hours = random.randint(1, 12)
            satisfaction = random.randint(1, 3)
        
        # 添加记录
```

**关键**: 
- 已解决: 53%（约225个）
- 处理中: 17%（约75个）
- 已关闭: 30%（约126个）
- **已处理（已解决+处理中）: 70%（约300个）**

## 客服业务场景说明

### 投诉处理状态

| 状态 | 含义 | 占比 | 是否统计 |
|------|------|------|---------|
| **已解决** | 问题彻底解决，客户满意 | 53% | ✅ |
| **处理中** | 正在处理，尚未完结 | 17% | ✅ |
| **已关闭** | 客户撤诉/无效投诉/超时关单 | 30% | ❌ |

### 交叉分析的价值

**横向看**（按投诉类型）:
- 产品质量: 已解决58个，处理中22个 → 解决率72.5%
- 物流配送: 已解决52个，处理中18个 → 解决率74.3%

**纵向看**（按处理状态）:
- 已解决: 产品质量58 > 物流配送52 > 售后服务45 > ...
- 处理中: 产品质量22 > 物流配送18 > 售后服务15 > ...

**管理决策**:
- 产品质量投诉最多 → 需要产品改进
- 处理中占比25% → 处理效率需提升
- 各类投诉的解决率相似 → 处理流程标准化良好

## 与其他场景对比

| 场景 | 维度数 | 过滤类型 | 指标数 |
|------|-------|---------|--------|
| M7 | 2 | in（OR逻辑） | 1 |
| M1 | 2 | eq | 2 |
| S7 | 2 | 无 | 1 |
| H5 | 3 | 无 | 1 |

**M7特点**: 双维度交叉分析 + in运算符过滤

## 场景来源
改编自电商客服投诉数据，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. "已处理"在业务上可能指多个状态（已解决+处理中），用in运算符
2. 双维度交叉分析生成笛卡尔积（5类型 × 2状态 = 10行）
3. in运算符的value必须是数组，不是字符串

**对于业务用户**:
- 双维度交叉表适合分析两个分类变量的组合
- "已处理"不包括"已关闭"（关闭≠处理）
- 交叉表可横向看、纵向看，多角度分析

**M7是典型的客服分析场景**，测试Agent对双维度交叉分析和in运算符的理解。
