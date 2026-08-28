# M4: 营销渠道ROI分析

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 营销分析场景 + 多指标计算 + 时间序列数据

## 数据文件
- **路径**: `tests/agent_contract/data/M4_marketing_roi.xlsx`
- **工作表**: `渠道数据`
- **数据量**: 约151行（30天 × 5渠道）
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 渠道名称 | 文本 | 百度搜索/抖音信息流/微信朋友圈/知乎广告/小红书 |
| 投放日期 | 日期 | 2024-07-01 到 2024-07-30 |
| 投放金额 | 数值 | 每日投放成本（元）|
| 曝光量 | 数值 | 广告曝光次数 |
| 点击量 | 数值 | 广告点击次数 |
| 转化量 | 数值 | 转化订单数 |
| 销售额 | 数值 | 转化带来的销售金额（元）|

## 数据特殊性

**时间序列特征**:
- 每个渠道每天一条记录
- 连续30天数据（2024年7月）
- 可分析单日表现或汇总表现

**营销指标关系**:
- 点击率 (CTR) = 点击量 / 曝光量
- 转化率 (CVR) = 转化量 / 点击量
- ROI = 销售额 / 投放金额
- CPC = 投放金额 / 点击量

## 用户需求（Prompt）

```
请统计每个营销渠道30天的投放效果，包括总投放金额、总销售额和平均ROI。

输入文件：tests/agent_contract/data/M4_marketing_roi.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 无（统计全部30天）

**分组维度**: 渠道名称

**指标**（3个）:
1. 总投放金额 (sum)
2. 总销售额 (sum)
3. 平均ROI (average)

**注意**: 平均ROI是对每日ROI求平均，不是总销售额/总投放金额

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/M4_marketing_roi.xlsx
```

**预期返回**:
- `available_fields`: ["渠道名称", "投放日期", "投放金额", "曝光量", "点击量", "转化量", "销售额"]

### Step 2: 构造Task Request

**关键点**: 需要计算ROI字段吗？

**分析**: 
- 如果数据中有"ROI"字段 → 直接average
- 如果没有"ROI"字段 → **SheetPilot暂不支持派生字段**

**假设**: 数据中已包含"ROI"列（销售额/投放金额）

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/M4_marketing_roi.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/渠道投放效果.xlsx",
  "user_request": "请统计每个营销渠道30天的投放效果，包括总投放金额、总销售额和平均ROI。",
  "source": {"sheet": "渠道数据", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "channel", "field": "渠道名称", "output_name": "渠道名称"}
  ],
  "metrics": [
    {"id": "total_cost", "function": "sum", "field": "投放金额", "output_name": "总投放金额"},
    {"id": "total_revenue", "function": "sum", "field": "销售额", "output_name": "总销售额"},
    {"id": "avg_roi", "function": "average", "field": "ROI", "output_name": "平均ROI"}
  ],
  "output": {"sheet": "渠道效果", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["channel"],
    "required_metrics": ["total_cost", "total_revenue", "avg_roi"],
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
| 渠道名称 | 总投放金额 | 总销售额 | 平均ROI |
|---------|-----------|---------|---------|
| 百度搜索 | 300000 | 510000 | 1.72 |
| 抖音信息流 | 420000 | 672000 | 1.61 |
| 微信朋友圈 | 360000 | 612000 | 1.68 |
| 知乎广告 | 240000 | 456000 | 1.88 |
| 小红书 | 320000 | 544000 | 1.69 |

### 验证点
1. **行数**: 6行（表头 + 5个渠道）
2. **总投放**: 1,640,000元（5个渠道30天累计）
3. **总销售**: 2,794,000元
4. **整体ROI**: 2794000 / 1640000 ≈ 1.70
5. **平均ROI范围**: 1.6-1.9（合理营销ROI）

### 业务逻辑验证
- **知乎广告**平均ROI最高（1.88），性价比最好
- **抖音信息流**投放金额最大（420000），但ROI相对较低
- **百度搜索**投放金额较低，ROI中等

**注意**: 平均ROI ≠ 总销售额 / 总投放金额
- 平均ROI = 每日ROI的算术平均
- 整体ROI = 总销售额 / 总投放金额

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 指标配置 | 30% | sum + sum + average组合正确 |
| 字段选择 | 25% | 正确识别"投放金额"、"销售额"、"ROI" |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 5个渠道数据精确匹配 |
| 业务理解 | 5% | 理解ROI指标含义 |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: ROI字段不存在

**问题**: 如果数据中没有预计算的"ROI"列，Agent应该怎么办？

❌ **错误做法**: 尝试构造派生字段
```json
{"function": "custom", "expression": "销售额 / 投放金额"}
```
**SheetPilot不支持自定义表达式**

✅ **正确做法1**: 
- 如果数据中有ROI列 → 直接average
- 如果没有ROI列 → 只统计投放金额和销售额，在输出Excel中手动计算

✅ **正确做法2**: 要求数据预处理时添加ROI列

### 陷阱2: 平均ROI vs 整体ROI

❌ **错误理解**: 
```
平均ROI = 总销售额 / 总投放金额
```

✅ **正确理解**:
```
平均ROI = average(每日ROI)
整体ROI = sum(销售额) / sum(投放金额)
```

**示例**:
- 第1天: 投放1000元，销售2000元，ROI=2.0
- 第2天: 投放2000元，销售3000元，ROI=1.5
- 平均ROI = (2.0 + 1.5) / 2 = **1.75**
- 整体ROI = (2000 + 3000) / (1000 + 2000) = **1.67**

**两者不相等**，本场景要求"平均ROI"

### 陷阱3: 字段名混淆

❌ 错误：
- `{"field": "投放成本", ...}`（字段名是"投放金额"）
- `{"field": "收入", ...}`（字段名是"销售额"）

✅ 正确：精确匹配字段名

### 陷阱4: average配置错误
❌ 错误：`{"function": "average"}`（缺少field）
✅ 正确：`{"function": "average", "field": "ROI"}`

## 扩展场景

### 变体1: 只统计某个渠道
用户需求改为："只统计百度搜索的投放效果"
```json
"filters": [
  {"id": "baidu", "field": "渠道名称", "operator": "eq", "value": "百度搜索"}
]
```

### 变体2: 按日期+渠道双维度
用户需求改为："统计每天每个渠道的投放效果"
```json
"dimensions": [
  {"id": "date", "field": "投放日期", "output_name": "投放日期"},
  {"id": "channel", "field": "渠道名称", "output_name": "渠道名称"}
]
```
预期结果：150行（30天 × 5渠道）

### 变体3: 添加点击率指标
**注意**: 如果数据中有预计算的"点击率"列
```json
"metrics": [
  ...,
  {"id": "ctr", "function": "average", "field": "点击率", "output_name": "平均点击率"}
]
```

### 变体4: 按ROI降序排序
```json
"sort": [{"by": "avg_roi", "direction": "desc"}]
```
预期第一行：知乎广告（ROI=1.88）

## 数据生成逻辑

```python
channels = ["百度搜索", "抖音信息流", "微信朋友圈", "知乎广告", "小红书"]

# 每个渠道有不同的ROI特征
channel_profiles = {
    "百度搜索": {"cost_range": (8000, 15000), "roi_range": (1.5, 2.0)},
    "抖音信息流": {"cost_range": (12000, 20000), "roi_range": (1.4, 1.8)},
    "微信朋友圈": {"cost_range": (10000, 18000), "roi_range": (1.5, 1.9)},
    "知乎广告": {"cost_range": (6000, 12000), "roi_range": (1.6, 2.2)},
    "小红书": {"cost_range": (8000, 16000), "roi_range": (1.5, 1.9)},
}

# 生成30天数据
for day in range(1, 31):
    for channel, profile in channel_profiles.items():
        cost = random.randint(*profile["cost_range"])
        roi = random.uniform(*profile["roi_range"])
        revenue = int(cost * roi)
        
        # 曝光/点击/转化根据cost规模生成
        impressions = random.randint(cost * 15, cost * 30)
        clicks = random.randint(cost // 5, cost // 3)
        conversions = revenue // random.randint(280, 450)
        
        # 添加记录（包含ROI列）
```

**关键**: 数据中包含预计算的"ROI"列，方便average统计

## 营销指标说明

### 核心指标

| 指标 | 公式 | 含义 | 本场景是否统计 |
|------|------|------|--------------|
| **ROI** | 销售额 / 投放金额 | 投资回报率 | ✅ average(ROI) |
| **CTR** | 点击量 / 曝光量 | 点击率 | ❌（可扩展） |
| **CVR** | 转化量 / 点击量 | 转化率 | ❌（可扩展） |
| **CPC** | 投放金额 / 点击量 | 单次点击成本 | ❌（可扩展） |

### ROI解读
- ROI > 1: 盈利（销售额 > 成本）
- ROI = 1: 盈亏平衡
- ROI < 1: 亏损（销售额 < 成本）

**本场景**: 所有渠道ROI都在1.6-1.9，说明投放效果良好

## 与其他场景对比

| 场景 | 业务领域 | 指标复杂度 | 时间维度 |
|------|---------|-----------|---------|
| M4 | 营销ROI | sum + average | 30天时间序列 |
| R5 | 广告ROI | 包含负ROI | 6个月 + 浮点过滤 |
| M1 | 电商订单 | sum + count | 单时间点 |

**M4是基础的营销分析场景**，为R5（复杂广告ROI）打基础

## 场景来源
改编自数字营销投放数据，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. 平均ROI ≠ 总销售额/总投放金额（是对每日ROI求平均）
2. 数据中需要有预计算的ROI列，SheetPilot不做派生计算
3. 时间序列数据汇总时，维度选择很重要（按渠道 vs 按日期）

**对于业务用户**:
- ROI是营销核心指标，反映投放效率
- 不同渠道有不同的ROI特征（知乎高质量、抖音大流量）
- 30天汇总数据适合评估渠道整体表现

**M4是典型的营销分析场景**，测试Agent对多指标组合（sum+average）的理解。
