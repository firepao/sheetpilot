# SheetPilot Agent Contract 测试场景定义

本目录是 Agent Contract 场景注册表。每个 JSON 文件定义一个场景；只有 `status=active` 的场景属于默认可运行测试集，`status=draft` 的场景是尚缺 fixture 或判定契约的候选场景。

## 场景身份

- `scenario_key` 是全局唯一身份，必须等于 JSON 文件名（不含 `.json`），例如 `M3_marketing_roi`。
- `id` 与 `scenario_key` 相同，供现有 evaluator 和归档目录使用。
- `short_id` 只表示难度系列中的显示编号，例如 `M3`。它不唯一，禁止用于查找、目录命名、结果关联或 replay 匹配。
- `data_file` 是 `tests/agent_contract/data/` 下的文件名，不包含其他目录前缀。

运行或评分前先验证注册表：

```powershell
python tests\agent_contract\validate_scenarios.py
```

当前 canonical 注册表包含 26 个正式 Prompt 场景，全部必须为 active。validator 会检查唯一键、Prompt、fixture、Sheet 和表头契约；任何一项不一致都会使注册表验证失败，批量测评必须在验证通过后运行。

## 场景分类

### S系列：简单场景（Simple）
- **S1**：单维度求和 + 排序
- **S2**：行数计数
- **S8**：精确字段名查询
- **S9**：最简路径验证（3轮交付）

**特征**：
- 单一维度或简单指标
- 精确字段名，无歧义
- 数据干净，无空值或异常
- 理想交互：3-4轮

### M系列：中等场景（Medium）
- **M1**：多维度 + 多指标（城市×渠道）
- **M2**：多过滤条件组合
- **M3**：复杂排序规则
- **M4**：in运算符过滤

**特征**：
- 多个维度或指标组合
- 多条件过滤
- 数据中含10%空值、5%异常
- 理想交互：4-5轮

### H系列：困难场景（Hard）
- **H1**：双维度 + 四指标 + 非空计数
- **H2**：重复表头触发Field Binding
- **H3**：模糊需求 + 样本判断
- **H4**：分步澄清需求

**特征**：
- 复杂维度指标组合
- 字段绑定必需
- 模糊业务需求
- 理想交互：5-7轮

### R系列：真实业务场景（Real-world）
- **R1**：财务对账（科目余额表）
- **R2**：电商库存（SKU缺货分析）
- **R3**：人力成本（薪资汇总）
- **R4**：客户留存（新客复购流失）
- **R5**：渠道ROI（广告投放效果）
- **R6**：物流时效（配送超时分析）

**特征**：
- 真实业务数据脏度（空值15%、异常20%）
- 隐含业务规则（退货为负、取消不计入）
- 复杂计算逻辑（ROI、留存率、超时率）
- 理想交互：6-8轮

## JSON Schema

```json
{
  "scenario_key": "全局唯一标识，等于文件名 stem",
  "id": "与 scenario_key 相同",
  "short_id": "仅展示用的系列编号，如 S1、R2",
  "status": "active | draft",
  "evaluation_mode": "deterministic_request | semantic | correct_stop",
  "user_prompt": "完整的 Agent Prompt",
  "data_file": "tests/agent_contract/data 下的文件名",
  "expected_outcome": "success | correct_stop",
  "ideal_rounds": "理想交互轮次（用于效率评分）",
  "ideal_cli_calls": "理想CLI调用次数（用于效率评分）",
  "requires_clarification": "是否需要主动澄清需求（布尔值）",
  "oracle_params": {
    "tolerance": "数值容差（默认1e-6）",
    "expected_groups": "预期分组数量（可选）",
    "correct_field": "正确字段名（用于H3类场景，可选）",
    "binding_required": "是否必须经过Field Binding（布尔值，可选）",
    "其他业务特定参数": "..."
  }
}
```

## 场景命名规范

```
<分类><序号>_<业务描述>.json；完整 stem 就是 scenario_key

示例：
- S1_department_sales.json          # 简单：部门销售汇总
- M1_city_channel_multi.json        # 中等：城市渠道多维度
- H3_ambiguous_field.json            # 困难：模糊字段选择
- R1_finance_reconciliation.json    # 真实：财务对账
```

## 使用方法

### 1. 单个场景测试
```bash
python -m tests.agent_contract.runner \
  --scenario tests/agent_contract/scenarios/S1_department_sales.json \
  --agent-api-key <your-key>
```

### 2. 批量测试（某一分类）
```bash
python -m tests.agent_contract.runner \
  --scenario-dir tests/agent_contract/scenarios \
  --filter "S*" \
  --agent-api-key <your-key>
```

### 3. 完整测试套件
```bash
python -m tests.agent_contract.runner \
  --scenario-dir tests/agent_contract/scenarios \
  --agent-api-key <your-key>
```

## 添加新场景

1. 准备数据文件：`tests/agent_contract/data/<scenario_key>.xlsx`（业务上需要其他名称时必须在 JSON 中显式引用）
2. 手工验证Oracle：计算预期结果
3. 创建场景 JSON：按上述 Schema 填写；文件名 stem、`scenario_key`、`id` 三者必须相同
4. 运行注册表验证：
   ```powershell
   python tests\agent_contract\validate_scenarios.py
   ```
5. 验证场景 Oracle：
   ```bash
   python -m tests.agent_contract.oracle_validator \
     tests/agent_contract/scenarios/<新场景>.json
   ```
6. 执行测试：
   ```bash
   python -m tests.agent_contract.runner \
     --scenario tests/agent_contract/scenarios/<新场景>.json
   ```

## 注意事项

1. **Prompt一致性**：同一场景的Prompt在多次测试中保持完全一致
2. **数据稳定性**：数据文件只读，不在测试中修改
3. **Oracle独立性**：Oracle验证不依赖SheetPilot Runtime实现
4. **场景隔离**：每个场景使用独立的Agent会话，不共享上下文
5. **草稿隔离**：缺少数据文件、Prompt 或判定契约的场景保持 `status=draft`，不得进入默认批量结果
