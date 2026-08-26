# S9: 多条件AND过滤

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: 多个过滤条件的AND组合

## 数据文件
- **路径**: `D:/bitexcel/SheetPilot/tests/agent_contract/data/S9_multi_filter.xlsx`
- **工作表**: `产品销售`
- **数据量**: 约101行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 产品ID | 文本 | 产品编号 |
| 产品名称 | 文本 | 产品A/B/C/D/E |
| 销售额 | 数值 | 金额 |
| 状态 | 文本 | 正常/停售 |
| 区域 | 文本 | 华东/华南/华北 |

## 用户需求（Prompt）

```
请统计状态为"正常"且区域为"华东"的产品销售额，按产品分组。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/S9_multi_filter.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:/bitexcel/SheetPilot/tests/agent_contract/data/S9_multi_filter.xlsx
```

**预期返回**:
- `available_fields`: ["产品ID", "产品名称", "销售额", "状态", "区域"]

### Step 2: 构造Task Request

**关键点**: 两个过滤条件（AND关系）

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/bitexcel/SheetPilot/tests/agent_contract/data/S9_multi_filter.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/华东正常产品销售.xlsx",
  "user_request": "请统计状态为"正常"且区域为"华东"的产品销售额，按产品分组。",
  "source": {"sheet": "产品销售", "header_row": 1},
  "filters": [
    {"id": "f_status", "field": "状态", "operator": "eq", "value": "正常"},
    {"id": "f_region", "field": "区域", "operator": "eq", "value": "华东"}
  ],
  "dimensions": [
    {"id": "product", "field": "产品名称", "output_name": "产品名称"}
  ],
  "metrics": [
    {"id": "sales", "function": "sum", "field": "销售额", "output_name": "销售额"}
  ],
  "output": {"sheet": "华东正常产品", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": ["f_status", "f_region"],
    "required_dimensions": ["product"],
    "required_metrics": ["sales"],
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
| 产品名称 | 销售额 |
|---------|--------|
| 产品A | 45000 |
| 产品B | 38000 |
| 产品C | 32000 |
| 产品D | 28000 |
| 产品E | 22000 |

### 验证点
1. **行数**: 6行（表头 + 5个产品）
2. **过滤后总额**: 165000（只统计"正常"+"华东"）
3. **过滤准确性**: 必须同时满足两个条件

### 过滤逻辑验证

**原始数据分布**（示例）:
- 产品A-正常-华东: 45000 ✅ **符合**
- 产品A-停售-华东: 8000 ❌（状态不符）
- 产品A-正常-华南: 12000 ❌（区域不符）
- 产品A-停售-华北: 5000 ❌（都不符）

**只有同时满足"正常"AND"华东"的记录被统计**

### 对比验证
- 只过滤"正常"（不限区域）: 约280000
- 只过滤"华东"（不限状态）: 约220000
- 同时过滤"正常"AND"华东": **165000** ✓

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | filters包含2个条件，**都在acceptance中** |
| 字段绑定 | 15% | 绑定"状态"、"区域"、"产品名称"、"销售额" |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 5个产品金额精确匹配，**总额=165000** |
| 过滤逻辑 | 10% | 理解AND关系（非OR） |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 遗漏过滤条件

❌ **错误1**: 只写一个过滤条件
```json
"filters": [
  {"id": "f_status", "field": "状态", "operator": "eq", "value": "正常"}
]
```
会统计所有区域的正常产品，得到280000

❌ **错误2**: filters为空
```json
"filters": []
```
会统计所有数据，得到错误结果

✅ **正确**: 必须包含2个过滤条件

### 陷阱2: 误用OR逻辑
**注意**: SheetPilot的filters是**AND关系**，不是OR

如果用户需求是"华东**或**华南"，应该这样写：
```json
{"id": "f_region", "field": "区域", "operator": "in", "value": ["华东", "华南"]}
```
而不是写两个独立的eq过滤条件！

### 陷阱3: acceptance不完整
❌ 错误：
```json
"filters": [
  {"id": "f_status", ...},
  {"id": "f_region", ...}
],
"acceptance": {
  "required_filters": ["f_status"]  // 只写了1个
}
```

✅ 正确：
```json
"acceptance": {
  "required_filters": ["f_status", "f_region"]  // 2个都要
}
```

### 陷阱4: 字段名或值错误
❌ 错误：
- `{"field": "区域", "value": "东部"}`（值不匹配）
- `{"field": "状态", "value": "在售"}`（值不匹配）

✅ 正确：精确匹配数据中的值

## 扩展场景

### 变体1: 三个过滤条件
用户需求改为："统计正常、华东、销售额>3000的产品"
```json
"filters": [
  {"id": "f1", "field": "状态", "operator": "eq", "value": "正常"},
  {"id": "f2", "field": "区域", "operator": "eq", "value": "华东"},
  {"id": "f3", "field": "销售额", "operator": "gt", "value": 3000}
]
```

### 变体2: 使用in代替多个eq
用户需求改为："统计正常产品在华东和华南的销售额"
```json
"filters": [
  {"id": "f_status", "field": "状态", "operator": "eq", "value": "正常"},
  {"id": "f_region", "field": "区域", "operator": "in", "value": ["华东", "华南"]}
]
```

### 变体3: 不过滤（对比基准）
用户需求改为："统计所有产品的销售额"
```json
"filters": []
```
预期总额: 约500000

## 数据生成逻辑

```python
# 每个产品生成多种状态和区域的组合
products = ["产品A", "产品B", "产品C", "产品D", "产品E"]

target_by_product = {
    "产品A": 45000,  # 正常+华东的目标金额
    "产品B": 38000,
    "产品C": 32000,
    "产品D": 28000,
    "产品E": 22000,
}

# 为每个产品生成：
# 1. 正常+华东的订单（总和=target）
# 2. 其他组合的噪声订单（停售+华东、正常+华南等）
```

## 过滤条件组合理解

### AND逻辑（SheetPilot默认）
```json
"filters": [
  {"field": "状态", "operator": "eq", "value": "正常"},
  {"field": "区域", "operator": "eq", "value": "华东"}
]
```
**含义**: 状态="正常" **且** 区域="华东"

### 模拟OR逻辑（使用in运算符）
```json
"filters": [
  {"field": "区域", "operator": "in", "value": ["华东", "华南"]}
]
```
**含义**: 区域="华东" **或** 区域="华南"

**不支持**: 跨字段的OR（如"状态=正常 OR 区域=华东"）

## 常见用户需求关键词

识别以下关键词时应使用多条件过滤：
- "且"、"并且"、"同时"
- "既...又..."
- "在...的...产品"（如"在华东的正常产品"）
- 多个限定条件并列

## 与其他场景对比

| 场景 | 过滤条件数 | 过滤逻辑 |
|------|-----------|---------|
| S6 | 1 | 单条件 |
| S9 | 2 | AND |
| M1 | 2 | AND |
| H4 | 3 | AND（更复杂） |

**S9是最简单的多条件过滤场景**，为M/H系列的复杂过滤打基础。
