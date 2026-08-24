# S2: 单维度单指标分组汇总

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: 最简单的分组汇总场景

## 数据文件
- **路径**: `tests/agent_contract/data/S2_single_dim_metric.xlsx`
- **工作表**: `销售数据`
- **数据量**: 约60行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 区域 | 文本 | 华东/华南/华北/华中 |
| 销售额 | 数值 | 订单金额 |

## 用户需求（Prompt）

```
请帮我统计每个区域的总销售额，按区域分组汇总。

输入文件：tests/agent_contract/data/S2_single_dim_metric.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input tests/agent_contract/data/S2_single_dim_metric.xlsx
```

**预期返回**:
- `available_fields`: ["区域", "销售额"]
- 表头位置：第1行

### Step 2: 构造Task Request
```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "tests/agent_contract/data/S2_single_dim_metric.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/区域销售汇总.xlsx",
  "user_request": "请帮我统计每个区域的总销售额，按区域分组汇总。",
  "source": {"sheet": "销售数据", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "region", "field": "区域", "output_name": "区域"}
  ],
  "metrics": [
    {"id": "total_sales", "function": "sum", "field": "销售额", "output_name": "总销售额"}
  ],
  "output": {"sheet": "区域汇总", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["region"],
    "required_metrics": ["total_sales"],
    "required_sort": []
  }
}
```

### Step 3: 提交任务
```bash
task-run --request request.json --auto-result-dir D:/results
```

**预期返回**: `RUNTIME_PASS`（字段精确匹配，无需绑定）

### Step 4: 复核状态
```bash
task-status --task-id <task-id>
```

**预期结果**:
- `artifact_integrity`: `MATCHED`
- `delivery_valid`: `true`

## Oracle验证标准

### 输出工作表结构
| 区域 | 总销售额 |
|------|----------|
| 华东 | 115000 |
| 华南 | 98000 |
| 华北 | 82000 |
| 华中 | 65000 |

### 验证点
1. **行数**: 5行（表头 + 4个区域）
2. **列数**: 2列（区域 + 总销售额）
3. **求和精度**: 华东=115000, 华南=98000, 华北=82000, 华中=65000
4. **总计**: 360000

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 20% | filters=[], dimensions包含region, metrics包含sum |
| 字段绑定 | 15% | 精确匹配"区域"和"销售额" |
| Runtime验收 | 25% | state=RUNTIME_PASS, integrity=MATCHED |
| 输出正确性 | 30% | 4个区域金额精确匹配 |
| 格式规范 | 10% | 表头在A1，无多余列 |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 遗漏维度
❌ 错误：只写metrics，不写dimensions
✅ 正确：dimensions必须包含"区域"

### 陷阱2: 错误的聚合函数
❌ 错误：使用average或count
✅ 正确：使用sum统计"总销售额"

### 陷阱3: 添加不必要的过滤
❌ 错误：添加filters过滤某些区域
✅ 正确：无过滤条件，汇总全部数据

## 扩展场景

### 变体1: 添加排序
用户需求改为："按销售额从高到低排序"
- `sort`: [{"by": "total_sales", "direction": "desc"}]

### 变体2: 过滤特定区域
用户需求改为："只统计华东和华南的销售额"
- `filters`: [{"id": "f1", "field": "区域", "operator": "in", "value": ["华东", "华南"]}]

## 数据生成逻辑

```python
regions_target = {
    "华东": 115000,
    "华南": 98000,
    "华北": 82000,
    "华中": 65000,
}

# 每个区域拆分为12-18笔订单
# 确保总和精确等于target
```

## 与其他场景对比

| 场景 | S1 | S2 | S7 |
|------|----|----|-----|
| 维度数 | 1 | 1 | 2 |
| 指标数 | 4 | 1 | 1 |
| 复杂度 | 中 | **最简** | 中 |

**S2是最基础的场景**，适合验证Agent对summarize_table的基本理解。
