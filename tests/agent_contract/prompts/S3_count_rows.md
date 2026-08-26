# S3: count.rows 行数统计

## 场景分类
- **难度**: Simple
- **系列**: S (Simple) - 基础功能验证
- **测试重点**: count.rows（统计记录数）的正确使用

## 数据文件
- **路径**: `D:/bitexcel/SheetPilot/tests/agent_contract/data/S3_count_rows.xlsx`
- **工作表**: `订单数据`
- **数据量**: 约320行
- **表头行**: 第1行

## 表头结构
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 城市 | 文本 | 北京/上海/广州/深圳 |
| 订单号 | 文本 | 订单编号 |

## 用户需求（Prompt）

```
请统计每个城市的订单数量。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/S3_count_rows.xlsx
输出文件：<自动生成>
```

## 预期执行流程

### Step 1: 查询字段清单
```bash
task-types --input D:/bitexcel/SheetPilot/tests/agent_contract/data/S3_count_rows.xlsx
```

**预期返回**:
- `available_fields`: ["城市", "订单号"]

### Step 2: 构造Task Request

**关键点**: count.rows **不需要指定field**

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/bitexcel/SheetPilot/tests/agent_contract/data/S3_count_rows.xlsx",
  "output_file": "<AUTO-RESULT-DIR>/城市订单数量.xlsx",
  "user_request": "请统计每个城市的订单数量。",
  "source": {"sheet": "订单数据", "header_row": 1},
  "filters": [],
  "dimensions": [
    {"id": "city", "field": "城市", "output_name": "城市"}
  ],
  "metrics": [
    {"id": "order_count", "function": "count", "mode": "rows", "output_name": "订单数量"}
  ],
  "output": {"sheet": "城市订单统计", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["city"],
    "required_metrics": ["order_count"],
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
| 城市 | 订单数量 |
|------|----------|
| 北京 | 100 |
| 上海 | 80 |
| 广州 | 70 |
| 深圳 | 70 |

### 验证点
1. **行数**: 5行（表头 + 4个城市）
2. **订单总数**: 320
3. **数值类型**: 整数（不是浮点数）
4. **count逻辑**: 统计行数，与字段内容无关

## 评分标准

| Gate | 权重 | 判定条件 |
|------|------|---------|
| 契约正确性 | 25% | metrics使用count + mode=rows，**不包含field** |
| 字段绑定 | 15% | 只绑定"城市"维度 |
| Runtime验收 | 25% | state=RUNTIME_PASS |
| 输出正确性 | 25% | 4个城市计数精确匹配 |
| 格式规范 | 10% | 输出名称="订单数量" |

**通过标准**: ≥ 90分

## 关键陷阱

### 陷阱1: 错误添加field字段
❌ **错误**:
```json
{"function": "count", "mode": "rows", "field": "订单号"}
```
这会导致 `INVALID_COMBINATION` 错误！

✅ **正确**:
```json
{"function": "count", "mode": "rows"}
```

### 陷阱2: 与count.non_empty混淆
- `count.rows`: 统计**记录行数**（不关心字段内容）
- `count.non_empty`: 统计**某字段的非空值数量**（需要指定field）

**本场景应使用count.rows**

### 陷阱3: 使用sum代替count
❌ 错误：`{"function": "sum", "field": "订单号"}`（订单号是文本，无法求和）
✅ 正确：`{"function": "count", "mode": "rows"}`

## 扩展场景

### 变体1: 过滤后计数
用户需求改为："统计北京和上海的订单数量"
- 添加 `filters`: [{"id": "f1", "field": "城市", "operator": "in", "value": ["北京", "上海"]}]
- 预期结果：北京=100, 上海=80

### 变体2: 排序
用户需求改为："按订单数量从多到少排序"
- 添加 `sort`: [{"by": "order_count", "direction": "desc"}]
- 预期顺序：北京(100) → 上海(80) → 广州(70) = 深圳(70)

## 与S4对比

| 场景 | S3 | S4 |
|------|----|----|
| 统计方式 | count.rows | count.non_empty |
| 是否需要field | ❌ 不需要 | ✅ 需要 |
| 语义 | 统计记录数 | 统计非空值数 |
| 空值影响 | 无影响 | 排除空值 |

## 数据生成逻辑

```python
cities_count = {
    "北京": 100,
    "上海": 80,
    "广州": 70,
    "深圳": 70,
}

# 每个城市生成精确数量的订单记录
# 订单号从O10001递增
```

**关键**: 数据中无空值，count.rows和count.non_empty结果相同，但**写法不同**！
