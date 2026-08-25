# H3: 模糊字段选择（困难场景）

## 场景描述
测试数据包含3个语义相似的金额列：销售额、销售金额（含税）、净销售收入。Agent需要通过样本值判断用户真实意图。

## 测试目标
- 验证字段绑定的语义理解能力
- 验证Agent通过样本值推断字段关系的能力
- 验证NEEDS_BINDING流程的处理能力

## 输入文件
- **文件路径**: `D:\bitexcel\SheetPilot\tests\agent_contract\data\\H3_sales_multi_amount.xlsx`
- **工作表**: `销售明细`
- **表头行**: 1
- **数据特征**: 200行，3列金额字段
  - 列C: `销售额`（基础金额）
  - 列D: `销售金额`（= 销售额 × 1.13，含税）
  - 列E: `净销售收入`（= 销售额 - 退货金额）

## 用户需求（Prompt）

```
请统计各区域的净销售收入。

说明：
- 表头有多个金额字段，需要选择正确的"净销售收入"列
- 净销售收入 = 实际销售额扣除退货后的金额

输入文件: D:\bitexcel\SheetPilot\tests\agent_contract\data\\H3_sales_multi_amount.xlsx
输出文件: <由Agent决定>
```

## 预期执行流程

1. **查询字段清单**
   ```bash
   sheetpilot task-types --input D:\bitexcel\SheetPilot\tests\agent_contract\data\\H3_sales_multi_amount.xlsx
   ```
   
   返回包含3个候选字段：
   - `candidate-001`: header="销售额", samples=[3438.64, 4753.27, 287.65]
   - `candidate-002`: header="销售金额", samples=[3885.66, 5371.20, 325.04]
   - `candidate-003`: header="净销售收入", samples=[3438.64, 4753.27, 287.65]

2. **首次提交（使用模糊字段名）**
   - 字段: `净销售收入`
   - 结果: 返回 `NEEDS_BINDING`，因为表头没有精确匹配的"净销售收入"字段

3. **分析样本值进行语义判断**
   - candidate-002.samples[0] / candidate-001.samples[0] ≈ 1.13 → candidate-002是含税金额
   - candidate-003.samples == candidate-001.samples → candidate-003是净销售额（无退货场景）
   - 但根据用户说明"扣除退货后"，应绑定到candidate-003（列E）

4. **提交修订（Amendment）**
   ```json
   {
     "task_id": "<task-id>",
     "base_revision": 1,
     "amendments": [
       {
         "op": "add",
         "path": "/bindings/binding-001",
         "value": {"candidate_id": "candidate-003"}
       }
     ]
   }
   ```

5. **复核状态**
   ```bash
   sheetpilot task-status --task-id <task-id>
   ```

## 预期结果

### Runtime验收（Oracle）
- **状态**: `RUNTIME_PASS`
- **artifact_integrity**: `MATCHED`
- **delivery_valid**: `true`
- **字段绑定**: `净销售收入` → 列E（非列C或列D）

### 输出数据验证
- 输出工作表: 包含2列（区域、净销售收入）
- 各区域净销售收入应为列E的sum，而非列C或列D

### 交互效率
- **理想轮次**: 2-3轮（field inventory查询 + 首次提交 + 修订）
- **CLI调用次数**: 3-4次（task-types + task-run + task-run amendment + task-status）

### 字段绑定质量
- **准确率**: 100%（正确选择列E）
- **判断依据**: 样本值分析 + 业务语义理解

## 评分权重
- Evidence Gate: 10分
- Contract Gate: 15分
- Blackbox Gate: 25分
- Runtime Gate: 20分
- Oracle Gate: 20分
- **Field Binding Quality**: 10分（新增维度）

**通过标准**: ≥70分，字段绑定准确率=100%

## 关键陷阱
- ❌ **错误1**: 直接绑定到列C"销售额"（忽略"净"字）
- ❌ **错误2**: 绑定到列D"销售金额"（含税金额，更不对）
- ✅ **正确**: 通过样本值+业务语义，绑定到列E"净销售收入"

## 变体场景
- H4: 4列金额（增加"销售额(未税)"列）
- H5: 日期字段歧义（"创建日期" vs "支付日期" vs "完成日期"）
