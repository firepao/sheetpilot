# summarize_table Task Request 契约原型 V1

## 1. 决策目标

本原型定义 Agent 提交 `summarize_table` 任务时唯一需要理解的业务契约。Agent 不提交 Atom DAG、Molecule 名称、运行目录、临时文件、执行顺序或 Validator 实现。

契约使用稳定组件 ID 连接过滤、维度、指标、排序和验收。显示名称只用于输出，不能充当内部引用。

## 2. 顶层结构

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/data/orders.xlsx",
  "output_file": "D:/result/city-summary.xlsx",
  "user_request": "仅统计有效且未退货订单，按城市汇总销售收入、订单数量和平均订单金额，并按销售收入降序。",
  "source": {},
  "filters": [],
  "dimensions": [],
  "metrics": [],
  "output": {},
  "acceptance": {}
}
```

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | string | 第一阶段固定为 `1.0` |
| `task_type` | string | 固定为 `summarize_table` |
| `input_file` | string | 必填；Runtime 规范化并验证，不能与输出相同 |
| `output_file` | string | 必填；表示用户交付位置，不是运行目录 |
| `user_request` | string | 必填；仅用于审计，不参与 Runtime 推断 |
| `source` | object | 必填；提供已知来源提示，不能包含列字母映射 |
| `filters` | array | 可为空；元素 ID 必须唯一 |
| `dimensions` | array | 至少一个；元素 ID 必须唯一 |
| `metrics` | array | 至少一个；元素 ID 必须唯一 |
| `output` | object | 必填；声明目标 Sheet、起始单元格和排序 |
| `acceptance` | object | 必填；独立验收范围，详细协议由 Acceptance Contract Ticket 决定 |

所有对象拒绝未知字段。Runtime 返回的 `task_id`、`request_revision`、`attempt_id` 和状态不属于首次 Task Request。

## 3. Source

```json
{
  "sheet": "清洗明细",
  "header_row": 1
}
```

- `sheet` 可省略。省略或无法唯一匹配时，Runtime 返回 `NEEDS_BINDING`。
- `header_row` 可省略，必须是大于等于 1 的整数。
- Agent 使用业务字段名称引用来源列，不提交 `A`、`D`、`G` 等物理列字母。
- 字段如何绑定到实际工作簿由 Field Binding Ticket 定义。

## 4. Filters

```json
{
  "id": "valid_rows",
  "field": "清洗状态",
  "operator": "eq",
  "value": "有效"
}
```

第一阶段支持 `eq`、`ne`、`gt`、`gte`、`lt`、`lte`、`in`。多个过滤条件固定使用 `all` 语义；第一阶段不公开任意嵌套布尔表达式。

`in` 的 `value` 必须是非空数组，其他 operator 的 `value` 必须是单值。每个过滤条件必须有稳定 `id`，供 Acceptance Contract 引用。

## 5. Dimensions

```json
{
  "id": "city",
  "field": "城市",
  "output_name": "城市"
}
```

- `field` 是待绑定的业务字段名称。
- `output_name` 是输出表头。
- 第一阶段支持一个或多个维度，顺序决定输出列顺序和分组键顺序。

## 6. Metrics

求和：

```json
{
  "id": "sales_revenue",
  "function": "sum",
  "field": "销售额",
  "output_name": "销售收入"
}
```

按过滤后行数计数：

```json
{
  "id": "order_count",
  "function": "count",
  "mode": "rows",
  "output_name": "订单数量"
}
```

非空字段计数：

```json
{
  "id": "order_count",
  "function": "count",
  "mode": "non_empty",
  "field": "订单号",
  "output_name": "订单数量"
}
```

平均值：

```json
{
  "id": "average_order_amount",
  "function": "average",
  "field": "销售额",
  "output_name": "平均订单金额"
}
```

字段约束：

| function | `field` | `mode` |
|---|---|---|
| `sum` | 必填 | 禁止 |
| `average` | 必填 | 禁止 |
| `count` + `rows` | 禁止 | 必填，值为 `rows` |
| `count` + `non_empty` | 必填 | 必填，值为 `non_empty` |

第一阶段不支持其他聚合函数。Runtime 必须在创建 Attempt 前拒绝不合法组合。

## 7. Output

```json
{
  "sheet": "城市经营汇总",
  "anchor": "A1",
  "sort": [
    {
      "by": "sales_revenue",
      "direction": "desc"
    }
  ]
}
```

- `sheet` 必填，表示交付工作表名称。
- `anchor` 可省略，默认 `A1`。
- `sort[].by` 必须引用 Dimension ID 或 Metric ID，不能引用显示名称。
- `direction` 只能是 `asc` 或 `desc`。
- 第一阶段只允许写入 Runtime 新建的 Sheet；目标 Sheet 已存在时返回可恢复错误，不静默覆盖。

## 8. Acceptance 引用边界

本 Ticket 只确定 Acceptance Contract 如何引用 Task Request，不决定其 hash、证据或系统检查结构。

```json
{
  "required_filters": ["valid_rows", "not_returned"],
  "required_dimensions": ["city"],
  "required_metrics": [
    "sales_revenue",
    "order_count",
    "average_order_amount"
  ],
  "required_sort": [
    {
      "by": "sales_revenue",
      "direction": "desc"
    }
  ]
}
```

Acceptance 只引用稳定组件 ID，因此 Agent 修正工作簿 Field Binding 时不需要重写验收范围。Acceptance 中引用不存在的 ID 必须在接收 Task 时失败。

## 9. 最小完整示例

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/data/U3_builtin_dirty_orders_report.xlsx",
  "output_file": "D:/result/city-operating-summary.xlsx",
  "user_request": "仅统计清洗状态为有效且未退货的记录，按城市汇总销售收入、订单数量和平均订单金额，并按销售收入降序。",
  "source": {
    "sheet": "清洗明细",
    "header_row": 1
  },
  "filters": [
    {
      "id": "valid_rows",
      "field": "清洗状态",
      "operator": "eq",
      "value": "有效"
    },
    {
      "id": "not_returned",
      "field": "是否退货",
      "operator": "eq",
      "value": "否"
    }
  ],
  "dimensions": [
    {
      "id": "city",
      "field": "城市",
      "output_name": "城市"
    }
  ],
  "metrics": [
    {
      "id": "sales_revenue",
      "function": "sum",
      "field": "销售额",
      "output_name": "销售收入"
    },
    {
      "id": "order_count",
      "function": "count",
      "mode": "rows",
      "output_name": "订单数量"
    },
    {
      "id": "average_order_amount",
      "function": "average",
      "field": "销售额",
      "output_name": "平均订单金额"
    }
  ],
  "output": {
    "sheet": "城市经营汇总",
    "anchor": "A1",
    "sort": [
      {
        "by": "sales_revenue",
        "direction": "desc"
      }
    ]
  },
  "acceptance": {
    "required_filters": ["valid_rows", "not_returned"],
    "required_dimensions": ["city"],
    "required_metrics": [
      "sales_revenue",
      "order_count",
      "average_order_amount"
    ],
    "required_sort": [
      {
        "by": "sales_revenue",
        "direction": "desc"
      }
    ]
  }
}
```

## 10. 版本策略

- `schema_version` 使用 `major.minor`。
- 同一 major 内只允许增加可选字段或枚举能力，既有请求含义不能改变。
- 删除字段、改变默认值、改变过滤或聚合语义必须提升 major。
- Runtime 必须明确拒绝未知 major；不能按最接近版本猜测执行。
- `task-types` 返回当前支持版本和该版本的完整公开 Schema、约束说明及最小示例。

## 11. Agent 认知负担

使用本契约时，Agent 只需要完成：

1. 把用户要求翻译为过滤、维度、指标、排序和验收 ID。
2. 提交 `task-run --request <request.json>`。
3. 若返回 `NEEDS_BINDING`，仅补充 Runtime 明确允许的字段绑定。
4. 根据 Runtime Evidence 给出独立业务语义判断。

Agent 不需要查询 Atom/Molecule 能力、构造执行步骤、创建运行目录、调用独立 Validator 或阅读 SheetPilot 源码。
