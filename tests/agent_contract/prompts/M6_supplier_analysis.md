# M6: 供应商采购分析

## 场景分类
- **难度**: Medium
- **系列**: M (Medium) - 中等复杂度场景
- **测试重点**: 供应链场景 + in运算符 + 多指标分析

## 数据文件
- **路径**: `tests/agent_contract/data/M6_supplier_analysis.xlsx`
- **工作表**: `采购记录`
- **数据量**: 约338行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 采购单号 | 文本 | PO编号 |
| 供应商 | 文本 | 供应商A/B/C/D/E |
| 物料名称 | 文本 | 钢材/铝材/塑料/电子元件/包装材料 |
| 采购数量 | 数值 | 采购数量 |
| 单价 | 数值 | 单位价格（元）|
| 总金额 | 数值 | 采购总额（元）|
| 交货天数 | 数值 | 交货周期（天）|
| 合格率(%) | 数值 | 质检合格率 0-100 |
| 采购日期 | 日期 | 采购下单日期 |

## 用户需求（Prompt）

```
请统计质检合格率大于等于90%的采购记录，按供应商汇总采购总额、采购次数和平均交货天数。

输入文件：tests/agent_contract/data/M6_supplier_analysis.xlsx
输出文件：<自动生成>
```

## 需求分析

**过滤条件**: 合格率 >= 90

**分组维度**: 供应商

**指标**（3个）:
1. 采购总额 (sum)
2. 采购次数 (count.rows)
3. 平均交货天数 (average)

**业务含义**:
- 合格率≥90%: 高质量供应商，产品质量可靠
- 采购总额: 反映供应商规模和合作深度
- 平均交货天数: 反映供应商响应速度

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/M6_supplier_analysis.xlsx
```

**预期返回**:
- `available_fields`: ["采购单号", "供应商", "物料名称", "采购数量", "单价", "总金额", "交货天数", "合格率(%)", "采购日期"]

### Step 2: 构造Task Request

**关键点**: 过滤运算符是 `gte`（≥），不是 `gt`（>）

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/M6_supplier_analysis.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/供应商采购汇总.xlsx",
  "user_request": "请统计质检合格率大于等于90%的采购记录，按供应商汇总采购总额、采购次数和平均交货天数。",
  "source": {"sheet": "采购记录", "header_row": 1},
  "filters": [
    {"id": "high_quality", "field": "合格率(%)", "operator": "gte", "value": 90}
  ],
  "dimensions": [
    {"id": "supplier", "field": "供应商", "output_name": "供应商"}
  ],
  "metrics": [
    {"id": "total_amount", "function": "sum", "field": "总金额", "output_name": "采购总额"},
    {"id": "purchase_count", "function": "count", "mode": "rows", "output_name": "采购次数"},
    {"id": "avg_delivery", "function": "average", "field": "交货天数", "output_name": "平均交货天数"}
  ],
  "output": {"sheet": "供应商汇总", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["high_quality"],
    "required_dimensions": ["supplier"],
    "required_metrics": ["total_amount", "purchase_count", "avg_delivery"],
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
| 供应商 | 采购总额 | 采购次数 | 平均交货天数 |
|--------|---------|---------|-------------|
| 供应商A | 2,850,000 | 52 | 5.2 |
| 供应商B | 2,120,000 | 48 | 7.8 |
| 供应商C | 1,680,000 | 38 | 10.5 |
| 供应商D | 2,980,000 | 58 | 3.5 |
| 供应商E | 1,450,000 | 32 | 15.2 |

### 验证点
1. **行数**: 6行（表头 + 5个供应商）
2. **过滤后总额**: 11,080,000元（只统计合格率≥90%）
3. **过滤后采购数**: 228笔
4. **原始采购数**: 约338笔（合格率≥90%占约67%）
5. **交货天数范围**: 3.5-15.2天（合理范围）

### 业务逻辑验证
- **供应商D**: 采购总额最高（2,980,000），交货最快（3.5天），性价比最优
- **供应商E**: 采购总额最低，交货最慢（15.2天），合作规模较小
- **供应商A**: 采购总额居中，交货快（5.2天），质量稳定

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 过滤运算符 | 25% | **使用gte（≥），不是gt（>）** |
| 指标配置 | 25% | sum + count.rows + average组合 |
| Runtime验收 | 20% | state=RUNTIME_PASS |
| 输出正确性 | 20% | 5个供应商数据精确匹配 |
| 字段选择 | 10% | 正确识别"总金额"、"交货天数" |

**通过标准**: ≥ 80分

## 关键陷阱

### 陷阱1: 过滤运算符错误

❌ **错误1**: 使用 `gt`（>）
```json
{"operator": "gt", "value": 90}
```
**后果**: 只统计合格率>90的记录（排除90%），少统计约20笔

❌ **错误2**: 使用 `eq`（=）
```json
{"operator": "eq", "value": 90}
```
**后果**: 只统计合格率=90的记录（极少数）

✅ **正确**:
```json
{"operator": "gte", "value": 90}
```

**用户说"大于等于90%"，注意是≥，包括90%**

### 陷阱2: 字段名混淆

❌ **错误1**: 字段名错误
```json
{"field": "采购金额", ...}  // 字段名是"总金额"
```

❌ **错误2**: 字段名错误
```json
{"field": "交货周期", ...}  // 字段名是"交货天数"
```

✅ **正确**: 精确匹配字段名

### 陷阱3: 遗漏过滤条件
❌ 错误：`filters: []`
- 会统计所有采购记录（包括低合格率），采购总额约16,500,000元

✅ 正确：只统计合格率≥90%的记录

### 陷阱4: count指标配置错误
❌ 错误：`{"function": "count", "mode": "non_empty", "field": "采购单号"}`
✅ 正确：`{"function": "count", "mode": "rows"}`

**采购次数 = 记录行数，用count.rows**

## 扩展场景

### 变体1: 只统计特定供应商
用户需求改为："只统计供应商A和供应商D的采购情况"
```json
"filters": [
  {"id": "quality", "field": "合格率(%)", "operator": "gte", "value": 90},
  {"id": "suppliers", "field": "供应商", "operator": "in", "value": ["供应商A", "供应商D"]}
]
```
预期结果：2行（供应商A + 供应商D）

### 变体2: 按物料类型分组
用户需求改为："统计各物料类型的采购情况"
```json
"dimensions": [
  {"id": "material", "field": "物料名称", "output_name": "物料名称"}
]
```
预期结果：5行（5种物料）

### 变体3: 添加最低和最高单价
**注意**: SheetPilot暂不支持min/max函数，只能用average

### 变体4: 按采购总额降序排序
```json
"sort": [{"by": "total_amount", "direction": "desc"}]
```
预期第一行：供应商D（2,980,000元）

### 变体5: 双维度分析
用户需求改为："统计各供应商各物料的采购情况"
```json
"dimensions": [
  {"id": "supplier", "field": "供应商", "output_name": "供应商"},
  {"id": "material", "field": "物料名称", "output_name": "物料名称"}
]
```
预期结果：约25行（5供应商 × 5物料）

## 数据生成逻辑

```python
suppliers = ["供应商A", "供应商B", "供应商C", "供应商D", "供应商E"]
materials = ["钢材", "铝材", "塑料", "电子元件", "包装材料"]

# 每个供应商有不同的质量和速度特征
supplier_profiles = {
    "供应商A": {"quality_range": (92, 98), "delivery_range": (3, 7)},
    "供应商B": {"quality_range": (88, 95), "delivery_range": (5, 10)},
    "供应商C": {"quality_range": (85, 93), "delivery_range": (7, 14)},
    "供应商D": {"quality_range": (94, 99), "delivery_range": (2, 5)},
    "供应商E": {"quality_range": (80, 90), "delivery_range": (10, 20)},
}

# 生成6个月采购数据
for month in range(6):
    for supplier in suppliers:
        purchase_count = random.randint(8, 15)
        
        for _ in range(purchase_count):
            material = random.choice(materials)
            quantity = random.randint(100, 1000)
            unit_price = random.randint(80, 120)
            total_amount = quantity * unit_price
            
            profile = supplier_profiles[supplier]
            quality = random.randint(*profile["quality_range"])
            delivery = random.randint(*profile["delivery_range"])
            
            # 添加记录
```

**关键**: 
- 供应商D质量最高（94-99%），交货最快（2-5天）
- 供应商E质量一般（80-90%），交货最慢（10-20天）
- 约67%的采购记录合格率≥90%

## 供应链指标说明

### 供应商评估维度

| 维度 | 指标 | 本场景是否统计 | 说明 |
|------|------|--------------|------|
| **质量** | 合格率(%) | ✅ 过滤条件 | 产品质量水平 |
| **成本** | 采购总额 | ✅ sum | 合作规模 |
| **交付** | 交货天数 | ✅ average | 响应速度 |
| **数量** | 采购次数 | ✅ count.rows | 合作频次 |
| **单价** | 平均单价 | ❌（可扩展） | 价格竞争力 |

### 供应商分级（示例）

| 等级 | 合格率 | 交货天数 | 特征 |
|------|--------|---------|------|
| **A级** | ≥95% | ≤5天 | 优质供应商（如供应商D）|
| **B级** | ≥90% | ≤10天 | 合格供应商（如供应商A/B）|
| **C级** | <90% | >10天 | 需改进（如供应商E部分订单）|

## 与其他场景对比

| 场景 | 业务领域 | 过滤运算符 | 指标数量 |
|------|---------|-----------|---------|
| M6 | 供应链 | gte（数值≥） | 3个（sum+count+avg） |
| M2 | HR绩效 | in（多值OR） | 2个（count+avg） |
| M5 | 在线教育 | gt（数值>） | 2个（count+avg） |

**M6综合考察**: 数值过滤 + 多指标汇总 + 供应链业务理解

## 场景来源
改编自制造业供应链采购数据，简化为SheetPilot可处理的结构。

## 学习要点

**对于Agent开发者**:
1. "大于等于"用gte（≥），包括边界值（90%）
2. 供应链场景的多指标分析：质量（过滤）+ 成本（sum）+ 交付（average）+ 频次（count）
3. 字段名要精确匹配（"总金额"不是"采购金额"）

**对于业务用户**:
- 合格率≥90%是高质量供应商的标准
- 交货天数反映供应商响应能力
- 多维度评估供应商（质量+成本+交付+频次）

**M6是典型的供应链分析场景**，测试Agent对多指标组合（sum+count+average）和数值过滤（gte）的综合理解。
