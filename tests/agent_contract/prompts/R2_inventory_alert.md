# R2: 电商库存预警分析（真实场景）

## 场景描述
电商库存管理场景，分析各类目的低库存SKU数量。包含真实数据质量问题：安全库存字段15%空值。

## 测试目标
- 验证空值感知的过滤条件（安全库存 IS NOT NULL）
- 验证比较运算符在过滤中的应用（库存 < 安全库存）
- 验证中等数据量场景（1500行）
- 验证电商领域业务逻辑

## 输入文件
- **文件路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\\R2_inventory_sku.xlsx`
- **工作表**: `SKU库存`
- **表头行**: 1
- **数据特征**: 
  - 1500行SKU记录
  - 8个商品类目
  - 安全库存空值率15%（表示未设置安全库存）
  - 销售状态：在售/下架/清仓

## 用户需求（Prompt）

```
请分析SKU库存表，统计各类目低于安全库存的SKU数量。

要求：
- 只统计已设置安全库存的SKU（安全库存非空）
- 只统计库存数量低于安全库存的SKU
- 按类目分组
- 统计每个类目的预警SKU数量
- 按预警数量降序排列

输入文件: D:\bitexcel\SheetPilot\tests\agent_contract\data\\R2_inventory_sku.xlsx
输出文件: <由Agent决定>
```

## 预期执行流程

1. **查询字段清单**
   ```bash
   sheetpilot task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\\R2_inventory_sku.xlsx --sheet SKU库存 --header-row 1
   ```

2. **构造Task Request**
   - 过滤条件:
     - `安全库存 IS NOT NULL`（排除空值）
     - `库存数量 < 安全库存`（低库存判断）
   - 维度: `类目`
   - 指标: `count.rows` → `预警SKU数量`
   - 排序: `预警SKU数量 DESC`

3. **提交任务**
   ```bash
   sheetpilot task-run --request request.json --auto-result-dir <result-dir>
   ```

4. **复核状态**
   ```bash
   sheetpilot task-status --task-id <task-id>
   ```

## 预期结果

### Runtime验收（Oracle）
- **状态**: `RUNTIME_PASS`
- **artifact_integrity**: `MATCHED`
- **delivery_valid**: `true`

### 输出数据验证（部分Oracle值）

基于生成的测试数据，预期输出8行（8个类目），示例：

| 类目 | 预警SKU数量 |
|------|-----------|
| 图书 | 23 |
| 运动 | 22 |
| 美妆 | 20 |
| 家居 | 15 |
| 食品 | 14 |
| 电子产品 | 13 |
| 玩具 | 13 |
| 服装 | 10 |

**验证要点**：
- 总预警数量 = 130（约占1500行的8.6%，合理比例）
- 安全库存为空的SKU已被正确排除（不计入预警）
- 按预警数量降序排列

### 交互效率
- **理想轮次**: 1-2轮
- **CLI调用次数**: 2-3次（task-types可选 + task-run + task-status）

### 数据质量处理
- **空值过滤**: ✓（IS NOT NULL条件生效）
- **业务逻辑**: ✓（库存 < 安全库存判断正确）

## 评分权重
- Evidence Gate: 10分
- Contract Gate: 15分
- Blackbox Gate: 25分
- Runtime Gate: 20分
- Oracle Gate: 20分
- **Null-Aware Filter Quality**: 10分（新增维度，空值感知能力）

**通过标准**: ≥60分（R系列通过标准）

## 真实性体现
1. **数据量**: 1500行（中小电商SKU量级）
2. **空值语义**: 安全库存空值 = 未设置，而非0（真实业务逻辑）
3. **业务规则**: 库存 < 安全库存 = 预警（标准库存管理逻辑）
4. **销售状态**: 在售/下架/清仓（真实电商状态机）

## 关键陷阱
- ❌ **错误1**: 未过滤安全库存空值 → 统计错误（空值参与比较）
- ❌ **错误2**: 过滤条件写成`安全库存 > 0` → 排除了安全库存=0的合法场景
- ✅ **正确**: 使用`IS NOT NULL` + `库存数量 < 安全库存`双重过滤

## 扩展场景
- R2-v2: 增加销售状态过滤（仅统计"在售"SKU）
- R2-v3: 多级预警（严重预警：库存<安全库存*0.5，一般预警：库存<安全库存）
- R2-v4: 增加金额维度（预警SKU的库存金额合计）
