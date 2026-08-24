# SheetPilot 测试数据集调研与重构方案

## 一、现状分析

### 1.1 现有测试集问题

**测试数据文件**（`tests/agent_contract/data/`）：
- ✅ 已有文件：01-06（简单）+ 07-09（complex）
- ❌ **问题1：数据过于干净**
  - `09_complex_dirty_logistics.xlsx`：198行中只有6个客户编号空值，187/198都是"审核=通过, 清洗=有效, 无异常"
  - 真实物流数据会有更多：异常件、地址不全、客户信息缺失、时效延误、签收状态混乱
  
- ❌ **问题2：业务场景单一**
  - 当前：销售汇总、工单统计、订单分析
  - 缺失：财务对账、库存周转、人力成本、客户留存、渠道ROI、合规审计

- ❌ **问题3：不贴合实际使用**
  - Prompt过于精确："按未税口径统计（左列未税，右列含税 = 未税 × 1.13）"
  - 真实场景：用户只会说"统计销售额"，不会提前告诉Agent哪列是未税
  - 缺少：模糊需求、分步澄清、需求变更、历史数据关联

**评估框架**（`tests/agent_contract/evaluation/`）：
- ✅ **可复用部分**：
  - `oracle.py`：独立Oracle验证（无需导入SheetPilot）
  - `evaluator.py`：Gate机制、Critical Violation检测、评分breakdown
  - `cli.py`：归档目录命名
  
- ❌ **问题4：评估维度不足**
  - 当前主要验证：契约遵守、黑盒纪律、数学正确性
  - 缺失：
    - **模糊需求处理能力**：用户说"销售额"，Agent如何选择正确列？
    - **错误恢复路径**：遇到NEEDS_BINDING后的修订质量
    - **交互轮次效率**：理想3-6轮，实际多少？
    - **语义理解准确度**：绑定的字段是否符合业务意图？

**Skill脚本**（从别处搬来的）：
- `skills/sheetpilot-run-review/`：执行记录评审
- `skills/sheetpilot-run-scorer/`：执行记录打分
- ❌ **问题5：与新评估框架未对齐**
  - 这两个skill可能基于旧版契约或不同的评分逻辑
  - 需要重构以匹配 `evaluation/evaluator.py` 的Gate+Score体系

---

## 二、真实业务场景调研

### 2.1 学术基准数据集（Agent调研结果）

**SpreadsheetBench (NeurIPS 2024)**：
- **来源**：912个Excel论坛真实问题（ExcelForum、Chandoo、MrExcel、ExcelGuru）
- **复杂度**：平均85.7词/指令，反映真实用户上下文
- **特征**：35.7%包含多张表，42.7%有非标准关系表
- **规模**：表格超过100列和20,000行
- **评估**：OJ风格（每个指令平均3个测试用例）

**SpreadsheetBench 2 (2026)**：
- **来源**：企业财务报告和公司文件的真实业务数据
- **任务分类**：生成（财务建模/模板）、调试、可视化
- **复杂度**：平均11.8个工作表/文件，593.5个单元格修改/任务
- **规模**：财务建模任务平均修改1,164.5个单元格
- **领域**：会计、DCF、LBO、M&A、可比公司分析

**FINCH Benchmark (2025年12月)**：
- **来源**：Enron语料库（15,000个电子表格，来自150名员工的500,000封电子邮件）+ EUSES财务电子表格
- **工作流**：172个复合工作流，包含384个任务
- **规模**：1,710个电子表格，含2700万个单元格
- **任务类型**：数据录入、结构化、格式化、计算、建模、验证、可视化、报告
- **评估**：GPT-5.1 Pro在48小时后仅达到38.4%通过率

**Alpha Excel Benchmark**：
- **来源**：113个财务建模世界杯（FMWC）竞赛挑战
- **分类**：35%财务建模、40%游戏模拟、15%数据分析、10%其他
- **人类基准**：世界Excel冠军85% vs 最佳LLM 80%
- **关键难点**：状态追踪、多步计算、规则应用

### 2.2 真实分析模式（从学术基准提炼）

**财务与会计（35-40%任务）**：
- 财务建模（DCF、LBO、M&A分析）
- 账户对账与合并
- 递延税计算
- 资产管理与追踪
- 预算vs实际差异分析

**业务运营（30-35%）**：
- 区域/类别销售汇总+过滤（如"已审核"状态、未取消）
- 客户细分与队列分析
- 库存管理（缺货检测、安全库存监控）
- SaaS续约追踪与流失分析
- 供应链运营与物流追踪

**数据质量与转换（15-20%）**：
- 多条件AND/OR逻辑过滤
- 多维度分组（区域+类别）
- 聚合：SUM、COUNT、AVG、加权平均
- 按计算指标排序
- 跨表数据检索与验证

### 2.3 常见数据质量问题（从SpreadsheetBench）

**结构性问题**：
- 非标准表：嵌套表头、不完整表头、缺失表头
- 每张工作表多个表，无明确边界
- 自由文本与表格数据混合
- 版本间列位置不一致

**数据质量问题**：
- 空单元格 vs 零值（语义模糊）
- 关键字段空值（典型空值率12-15%）
- 格式不一致（日期、货币、百分比）
- 列中数据类型混合
- 不平衡分类账（财务数据中借方≠贷方）

**语义歧义**：
- 多个相似名称的金额列（"销售额"、"销售金额(含税)"、"净销售收入"）
- 需要领域知识选择正确字段
- 需要解释的状态标志（"通过" vs 其他审核状态）

### 2.4 复杂度维度

**数据量**：
- 简单：37-221行，2-7列（当前SheetPilot测试）
- 中等：141-961行，7-23列
- 复杂：1,100-20,000行，24-100+列
- 企业级：多工作表工作簿（平均11.8张表），跨表引用

**Schema复杂度**：
- 多分组维度（区域×类别×时间段）
- 层级关系（会计中一级科目→二级科目）
- 跨表查找与依赖
- 非关系布局（透视表样式、报告格式数据）

**过滤复杂度**：
- 多条件AND/OR逻辑（审核状态="通过" AND 是否取消="否"）
- 时间范围（日期区间、同比）
- 空值感知条件（库存<安全库存 WHERE 安全库存 IS NOT NULL）
- 特定领域规则（按账户代码前缀分类资产）

**计算复杂度**：
- 加权平均（sum(金额) / count(交易)）
- 比率与百分比（毛利率）
- 同比增长率
- 错误引用级联错误（#REF!、#VALUE!）

**当前SheetPilot差距**：测试范围37-1,501行，但缺少：
- 跨表引用的多工作表工作簿（只有1个测试含2-4张表）
- 非标准表布局
- 显式数据质量问题（空值、格式不一致）
- 复杂领域计算（加权指标、财务比率）

### 2.5 行业特定模式

**零售**：
- 区域×类别×时间多维分析
- 按购买行为细分客户
- 库存周转与缺货追踪
- 利润率分析（毛利、净销售额）

**SaaS**：
- 队列留存分析
- MRR/ARR计算与流失率
- 客户生命周期价值建模
- 续约预测

**财务**：
- 账户对账（交易匹配）
- 按账户层级汇总总账
- 财务报表编制
- 差异分析（预算vs实际）

**供应链**：
- 准时交付追踪
- 异常识别（延迟、损坏货物）
- 仓库运营指标
- 供应商绩效记分卡

### 2.6 SheetPilot测试增强建议（基于学术基准）

根据SpreadsheetBench/FINCH/Alpha Excel的发现，建议：

1. **采用OJ风格评估**：每个任务多个测试用例（遵循SpreadsheetBench模式）
2. **增加数据质量复杂度**：显式空值、格式不一致、不平衡数据
3. **添加多工作表场景**：跨表查找、版本对比、合并任务
4. **包含模糊字段绑定**：需要领域推理的多个相似列
5. **添加调试任务**：识别并修复#REF!、#VALUE!、循环引用
6. **扩大数据量**：添加5,000+行数据集以测试性能
7. **添加可视化任务**：从分析数据生成图表
8. **包含工作流任务**：多步操作（导入→清洗→分析→报告）
9. **增加非标准表布局**：嵌套表头、报告格式、自由文本混合
10. **真实复杂度**：平均11.8张表/工作簿，593.5个单元格修改/任务

**差距总结**：
- 当前测试：结构良好的基础操作
- 行业基准：需在复杂度、规模、真实混乱度上显著扩展才能匹配

---

## 三、测试集重构方案（基于调研更新）

**典型交互路径**：
```
用户："帮我统计一下各城市的销售情况"
Agent：调用task-types查看字段 → 发现有"城市"、"销售额"、"销售金额(含税)"、"净销售额"
Agent：需要澄清："您想统计的销售情况是指含税金额还是不含税金额？"
用户："就正常的销售额"
Agent：判断"净销售额"更符合财务口径 → 构造Request
Runtime：返回NEEDS_BINDING（"销售额"和"销售金额(含税)"都模糊匹配）
Agent：对比样本值，选择正确候选 → 提交Amendment
Runtime：RUNTIME_PASS
Agent：复核task-status → 交付
```

**数据质量真实分布**（参考物流、电商）：
- 空值率：5-15%（客户信息、地址、联系方式）
- 异常标记：10-20%（退货、取消、审核不通过）
- 重复记录：2-5%（系统bug、人工重复录入）
- 格式不一致：省市名称（"北京" vs "北京市"）、日期格式混乱
- 隐含规则：退货订单金额为负、取消订单不计入有效销售

---

## 三、测试集重构方案

### 3.1 数据集分层设计

**Layer 1：基础能力验证（保留现有S1-S2，微调数据）**
- S1：单维度求和 + 排序（部门销售）
- S2：行数计数（工单统计）
- **新增S9**：精确字段名 + 无空值 + 单一状态 → 验证最简路径（3轮交付）

**Layer 2：中等复杂度（保留M1-M4，增加脏数据）**
- M1：多维度 + 多指标（城市×渠道）
- M2-M4：多过滤、in运算符
- **改造**：在M系列中注入10%空值、5%异常状态、日期格式不一致

**Layer 3：困难挑战（重构H系列）**
- H1：双维度 + 非空计数（保留）
- H2：重复表头 + Field Binding（保留）
- **新增H3**：模糊需求 + 样本判断
  - Prompt："统计各区域销售情况"（不指定含税/不含税）
  - 数据：有"销售额"、"销售金额"、"净销售收入"三列
  - 样本值关系：销售金额 = 销售额 × 1.13，净销售收入 = 销售额 - 退货金额
  - Oracle：验证Agent是否通过样本值推理选择正确字段
  
- **新增H4**：分步澄清
  - Prompt（Round 1）："按城市统计订单"
  - Agent应询问：统计什么指标？过滤条件？
  - Prompt（Round 2）："统计销售额，只要有效订单"
  - 验证：Agent能否在两轮对话后构造完整Request

**Layer 4：真实业务场景（新增R系列，对标学术基准）**

基于SpreadsheetBench/FINCH/Alpha Excel的真实复杂度：

| 场景ID | 业务类型 | 数据特征 | Prompt示例 | 验证重点 |
|--------|---------|---------|-----------|---------|
| **R1** | 财务对账 | 科目余额表，600行，借贷不平衡8条，空值率12% | "筛选资产类科目，按一级科目汇总借方、贷方余额" | 账户分类逻辑、层级汇总、不平衡数据处理 |
| **R2** | 电商库存 | SKU库存，1500行，安全库存空值15% | "找出缺货的在售商品，按类目统计缺货SKU数量" | 空值感知过滤（IS NOT NULL）、多条件AND逻辑 |
| **R3** | 人力成本 | 薪资明细，800行，迟到扣款空值=无迟到 | "计算每个部门的实发工资总额和平均工资" | 空值语义（NULL vs 0）、加权平均、派生计算 |
| **R4** | 客户RFM | 订单流水，5000行，30%客户只下1单 | "按客户统计最近购买天数、购买次数、累计金额，找出高价值客户（F≥3且M≥5000）" | 时间计算、客户聚合、二次过滤 |
| **R5** | 渠道ROI | 广告投放，400行，含负ROI | "统计各渠道投放效果，ROI=(销售收入-投放成本)/投放成本，只保留ROI>0.5" | 派生计算、百分比格式、过滤计算字段 |
| **R6** | 物流时效 | 配送记录，3000行，超时率18% | "按配送类型统计超时件数和超时率（同城24h/省内48h/跨省72h）" | 分段规则、比率计算、多条件判断 |

**Layer 5：多工作表工作流（对标SpreadsheetBench 2平均11.8张表）**

| 场景ID | 工作表数 | 场景描述 | 当前能力 |
|--------|---------|---------|---------|
| **W1** | 2张 | 订单表(5000行) + 退货表(800行)，计算净销售额 | ❌ 需跨表VLOOKUP（标记CAPABILITY_UNSUPPORTED） |
| **W2** | 2张 | 2025Q1 vs 2025Q2销售对比，计算增长率 | ❌ 需跨表引用 + 同比计算 |
| **W3** | 3张 | 多渠道数据合并（天猫+京东+拼多多） | ❌ 需UNION操作 |

**复杂度对比表**：

| 维度 | 当前测试 | 学术基准 | R系列目标 |
|------|---------|---------|----------|
| 数据量 | 37-1,501行 | 1,100-20,000行 | 600-5,000行 |
| 空值率 | 3%（09_dirty） | 12-15% | 10-15% |
| 工作表数 | 1张（除1个测试） | 平均11.8张 | 1-2张（W系列标记不支持） |
| 异常状态 | 5%（187/198正常） | 15-20% | 15-20% |
| 语义歧义 | 无（精确字段名） | 多列模糊匹配 | H3/R系列含3列模糊匹配 |
| 单元格修改 | N/A | 平均593.5个 | N/A（SheetPilot是汇总而非修改） |

**数据生成策略**：
1. 从Kaggle下载基础数据（Sample Sales、Supermarket Sales）
2. 用Python脚本注入真实脏数据：
   ```python
   # 空值注入（10-15%）
   df.loc[df.sample(frac=0.12).index, '客户编号'] = None
   
   # 异常状态（15-20%）
   df.loc[df.sample(frac=0.18).index, '订单状态'] = np.random.choice(['已取消', '退货中', '待审核'])
   
   # 格式不一致
   df['省份'] = df['省份'].replace({'北京': np.random.choice(['北京', '北京市'], p=[0.7, 0.3])})
   
   # 隐含业务规则
   df.loc[df['订单状态'] == '已取消', '销售额'] = 0
   df.loc[df['订单状态'] == '退货', '销售额'] *= -1
   ```

### 3.2 Prompt模板分级

**Level 1：精确指令**（用于基础验证）
```
使用 $sheetpilot-excel-agent 处理：
输入：<file>
测试场景：<ID>
输出：<AUTO-RESULT-DIR>/<output>

使用工作表"<sheet>"，筛选<field>=<value>的记录，
按<dimension>汇总<metric>（函数：<function>），
按<sort_field>降序写入新工作表"<target_sheet>"。
```

**Level 2：业务语言**（用于中等难度）
```
用$sheetpilot-excel-agent分析：
输入：<file>
场景：<ID>

需求：统计各城市的有效订单销售情况，只看已完成且未退货的订单，
按销售额从高到低排序，输出到"城市销售汇总"。
```

### 3.3 评估框架升级（基于学术基准OJ风格）

**保留现有评估维度**（从`evaluation/evaluator.py`）：
- Gate 1: Evidence Complete（trace文件完整性）
- Gate 2: Contract Adherence（契约遵守）
- Gate 3: Blackbox Discipline（黑盒纪律）
- Gate 4: Runtime Validation（Runtime数学正确性）
- Gate 5: Oracle Match（独立Oracle验证）
- Critical Violations：源码访问、手工写工作簿、acceptance削减

**新增评估维度**（基于SpreadsheetBench OJ风格）：

**Dimension 1：交互效率**
```python
def evaluate_interaction_efficiency(bundle: dict) -> dict:
    """评估Agent交互轮次和CLI调用效率"""
    ideal_rounds = bundle["scenario"]["ideal_rounds"]  # 理想轮次（如4轮）
    ideal_cli_calls = bundle["scenario"]["ideal_cli_calls"]  # 理想CLI调用（如3次）
    
    actual_rounds = len(bundle.get("commands", []))
    actual_cli_calls = sum(1 for cmd in bundle["commands"] if "task-types" in cmd or "task-run" in cmd or "task-status" in cmd)
    
    round_score = max(0, 100 - abs(actual_rounds - ideal_rounds) * 15)  # 偏离1轮扣15分
    cli_score = max(0, 100 - abs(actual_cli_calls - ideal_cli_calls) * 20)  # 偏离1次扣20分
    
    return {
        "round_efficiency": round_score,
        "cli_efficiency": cli_score,
        "actual_rounds": actual_rounds,
        "actual_cli_calls": actual_cli_calls,
    }
```

**Dimension 2：字段绑定质量**
```python
def evaluate_field_binding_quality(bundle: dict) -> dict:
    """评估模糊字段选择的准确性"""
    if "binding_slots" not in bundle.get("task_status", {}):
        return {"binding_required": False}
    
    # 从场景定义获取正确的候选ID
    expected_bindings = bundle["scenario"].get("expected_bindings", {})
    actual_bindings = bundle["task_status"].get("resolved_bindings", {})
    
    correct = sum(1 for slot_id, expected_cid in expected_bindings.items()
                  if actual_bindings.get(slot_id) == expected_cid)
    total = len(expected_bindings)
    
    accuracy = (correct / total * 100) if total > 0 else 0
    
    return {
        "binding_accuracy": accuracy,
        "correct_bindings": correct,
        "total_bindings": total,
        "mismatched_slots": [k for k, v in expected_bindings.items() if actual_bindings.get(k) != v],
    }
```

**Dimension 3：需求澄清能力**（针对Level 3模糊Prompt）
```python
def evaluate_clarification_coverage(bundle: dict) -> dict:
    """评估Agent对模糊需求的澄清完整性"""
    if not bundle["scenario"].get("requires_clarification", False):
        return {"clarification_required": False}
    
    # 从场景定义获取必须澄清的要素
    required_clarifications = bundle["scenario"]["required_clarifications"]  # ["dimension", "metric", "filter"]
    
    # 从commands中提取Agent的问题（启发式：包含"？"且不是CLI命令）
    questions = [cmd for cmd in bundle["commands"] if "?" in cmd and "task-" not in cmd]
    
    covered = []
    for req in required_clarifications:
        if any(req in q for q in questions):
            covered.append(req)
    
    coverage = (len(covered) / len(required_clarifications) * 100) if required_clarifications else 100
    
    return {
        "clarification_coverage": coverage,
        "covered_aspects": covered,
        "missing_aspects": [r for r in required_clarifications if r not in covered],
        "total_questions_asked": len(questions),
    }
```

**新评分公式**（兼容旧测试）：
```python
def compute_quality_score_v2(bundle: dict) -> int | None:
    """新版评分（兼容旧测试的100分制）"""
    if not all_gates_passed(bundle):
        return None  # 任意Gate失败 → null
    
    base_score = 100
    
    # 扣分项1：交互效率（最多扣20分）
    efficiency = evaluate_interaction_efficiency(bundle)
    efficiency_penalty = max(0, 20 - (efficiency["round_efficiency"] + efficiency["cli_efficiency"]) / 10)
    
    # 扣分项2：字段绑定（最多扣15分）
    binding = evaluate_field_binding_quality(bundle)
    if binding.get("binding_required"):
        binding_penalty = max(0, 15 - binding["binding_accuracy"] / 100 * 15)
    else:
        binding_penalty = 0
    
    # 扣分项3：需求澄清（最多扣10分）
    clarification = evaluate_clarification_coverage(bundle)
    if clarification.get("clarification_required"):
        clarification_penalty = max(0, 10 - clarification["clarification_coverage"] / 100 * 10)
    else:
        clarification_penalty = 0
    
    final_score = base_score - efficiency_penalty - binding_penalty - clarification_penalty
    return max(0, round(final_score))
```

**对比旧版**：
- 旧版：100分（5个Gate全过）或 null（任意Gate失败）
- 新版：保留Gate门槛，增加3个细分维度的扣分项
- 向后兼容：旧测试（无binding、无clarification）不触发新扣分项，仍为100分
- 有过滤条件吗？（有效订单？时间范围？）
- 结果要排序吗？

**Level 4：真实对话**（用于业务场景）
```
Round 1（用户）：
"帮我分析一下这个月的库存情况"

Round 1（Agent）：
（调用task-types查看字段）
"请问您想关注哪些维度？比如按类目、按仓库、还是按SKU？"

Round 2（用户）：
"按类目吧，看看哪些类目缺货了"

Round 2（Agent）：
"明白了，缺货是指库存低于安全库存吗？另外需要筛选在售商品，还是包括下架的？"

Round 3（用户）：
"对，库存低于安全库存，只看在售的"

Round 3（Agent）：
（构造Request并提交）
```

### 3.4 Skill脚本重构方案

**现有Skill分析**：
- `skills/sheetpilot-run-review/SKILL.md`：执行记录评审（18KB）
- `skills/sheetpilot-run-scorer/SKILL.md`：执行记录打分（12KB）
- 来源：从别的地方搬来的，需要对齐新的Gate+Score体系

**重构目标**：
1. 对齐新评估框架（5个Gate + 3个新维度）
2. 支持场景JSON schema（ideal_rounds、expected_bindings、requires_clarification）
3. 输出结构化评估报告（JSON格式，可自动化解析）
4. 减少手工判断，增加程序化验证

**重构后的Skill职责划分**：

| Skill | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **sheetpilot-run-review** | 执行过程评审（定性） | 执行trace、场景定义 | Gate通过/失败原因、Critical违规清单、改进建议 |
| **sheetpilot-run-scorer** | 执行质量打分（定量） | 执行trace、Oracle结果 | 100分制质量分、各维度扣分明细、对标基准 |
| **sheetpilot-oracle-verify** | Oracle验证（新增） | Task输出文件、场景expected值 | Oracle通过/失败、数值差异报告 |

**实施路线**：
- Phase 1（本周）：更新evaluator.py（✅已完成）
- Phase 2（下周）：生成R3-R6数据并手工验证Oracle（✅已完成数据生成，待验证）
- Phase 3（Week 3）：重构sheetpilot-run-review.md对齐新Gate
- Phase 4（Week 4）：重构sheetpilot-run-scorer.md输出新维度
- Phase 5（Week 5）：实现runner.py自动化测试（需对接Agent API）

---

## 四、自动化测试方法

### 4.1 测试执行流程（5步）

```
┌─────────────────────────────────────────────────────────┐
│ 1. 准备阶段                                              │
│    - 加载场景JSON（scenarios/<ID>.json）                 │
│    - 验证数据文件存在（data/<file>.xlsx）                │
│    - 创建结果目录（results/<ID>__<timestamp>）           │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Agent执行阶段                                         │
│    - 调用Agent API，传入场景Prompt                       │
│    - 记录所有命令调用（task-types/task-run/task-status）│
│    - 捕获交互轮次、CLI调用次数、耗时                     │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Runtime验证阶段                                       │
│    - 提取task_id和output_file                           │
│    - 调用task-status获取Runtime状态                     │
│    - 验证artifact_integrity和delivery_valid             │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Oracle验证阶段                                        │
│    - 调用evaluation/oracle.py验证输出                   │
│    - 对比expected值（从场景JSON读取）                    │
│    - 计算数值差异、记录通过/失败                         │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 5. 评估打分阶段                                          │
│    - 调用evaluation/evaluator.py                        │
│    - 计算5个Gate + 3个新维度                            │
│    - 生成评估报告JSON（可归档可对比）                    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 runner.py设计（伪代码）

```python
# tests/agent_contract/runner.py

def run_scenario(scenario_id: str, agent_api_url: str) -> dict:
    """执行单个场景的完整测试流程"""
    # 1. 准备
    scenario = load_scenario_json(f"scenarios/{scenario_id}.json")
    data_file = Path("data") / scenario["data_file"]
    result_dir = create_result_directory(scenario_id)
    
    # 2. Agent执行
    trace = []
    start_time = time.time()
    
    response = agent_api.send_message(
        prompt=scenario["prompt"],
        skill="sheetpilot-excel-agent",
    )
    trace.append({"role": "user", "content": scenario["prompt"]})
    trace.append({"role": "assistant", "content": response})
    
    # 提取命令调用
    commands = extract_commands_from_response(response)
    
    # 如果返回NEEDS_BINDING，自动处理
    if "NEEDS_BINDING" in response:
        binding_response = handle_binding(scenario, response)
        trace.append({"role": "assistant", "content": binding_response})
        commands.extend(extract_commands_from_response(binding_response))
    
    elapsed = time.time() - start_time
    
    # 3. Runtime验证
    task_id = extract_task_id(commands)
    status_result = call_cli(["task-status", "--task-id", task_id])
    
    # 4. Oracle验证
    output_file = extract_output_file(status_result)
    oracle_result = evaluate_oracle(scenario, output_file)
    
    # 5. 评估打分
    bundle = {
        "scenario": scenario,
        "commands": commands,
        "task_status": status_result,
        "oracle_result": oracle_result,
        "trace": trace,
        "elapsed_ms": int(elapsed * 1000),
    }
    evaluation = evaluate_run(bundle)
    
    # 6. 保存结果
    save_bundle(result_dir / "bundle.json", bundle)
    save_evaluation(result_dir / "evaluation.json", evaluation)
    
    return evaluation


def run_test_suite(scenario_ids: list[str]) -> dict:
    """执行整套测试并生成汇总报告"""
    results = []
    
    for scenario_id in scenario_ids:
        print(f"[RUN] {scenario_id}")
        evaluation = run_scenario(scenario_id, AGENT_API_URL)
        results.append(evaluation)
        
        status = "✅ PASS" if evaluation["task_result"] == "PASS" else "❌ FAIL"
        score = evaluation.get("quality_score", "N/A")
        print(f"[{status}] {scenario_id}: {score}/100")
    
    # 汇总统计
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["task_result"] == "PASS"),
        "failed": sum(1 for r in results if r["task_result"] == "FAIL"),
        "avg_score": sum(r.get("quality_score", 0) or 0 for r in results) / len(results),
        "results": results,
    }
    
    save_summary("test-suite-summary.json", summary)
    print_summary_table(summary)
    
    return summary
```

### 4.3 执行方式

**单场景测试**：
```bash
python -m tests.agent_contract.runner --scenario R3 --agent-api http://localhost:8080
```

**批量测试**：
```bash
python -m tests.agent_contract.runner --suite basic  # S1-S2
python -m tests.agent_contract.runner --suite medium  # M1-M4
python -m tests.agent_contract.runner --suite hard  # H1-H4
python -m tests.agent_contract.runner --suite real  # R1-R6
python -m tests.agent_contract.runner --suite all  # 全部
```

**结果归档**：
```
tests/agent_contract/archives/
  2026-08-21T14:30:00+0800__suite-real__run-001/
    R1__evaluation.json
    R2__evaluation.json
    R3__evaluation.json
    ...
    suite-summary.json
```

---

## 五、实施路线图

### Phase 0：调研与设计（✅已完成）
- ✅ 调研学术基准（SpreadsheetBench/FINCH/Alpha Excel）
- ✅ 提炼真实业务场景
- ✅ 设计测试集分层（S/M/H/R/W）
- ✅ 设计评估框架升级方案

### Phase 1：核心基础设施（✅已完成）
- ✅ 更新evaluator.py（3个新维度）
- ✅ 生成R1-R2数据（已在前序完成）
- ✅ 生成R3-R6数据
- ✅ 创建R3-R6场景JSON

### Phase 2：Oracle验证（待完成，优先级P0）
- ⏳ 手工打开R1-R6 Excel文件
- ⏳ 计算Oracle expected值（如R1各科目借贷合计）
- ⏳ 更新场景JSON的oracle_params
- ⏳ 补充H3场景JSON（模糊字段绑定）

### Phase 3：现有数据改造（Week 1-2，优先级P1）
- ⏳ 为01-09数据注入真实脏度（空值、异常、格式不一致）
- ⏳ 从Kaggle下载Sample Sales/Supermarket Sales
- ⏳ 改造为M5-M8场景（中等复杂度+脏数据）
- ⏳ 补充S9场景（最简路径基准）

### Phase 4：Skill重构（Week 2-4，优先级P2）
- ⏳ 重构sheetpilot-run-review.md对齐新Gate
- ⏳ 重构sheetpilot-run-scorer.md输出新维度
- ⏳ 新增sheetpilot-oracle-verify.md（独立Oracle验证）
- ⏳ 更新Skill使用文档和示例

### Phase 5：自动化Runner（Week 4-6，优先级P2）
- ⏳ 实现runner.py（需Agent API接入）
- ⏳ 实现自动归档和汇总报告
- ⏳ 执行完整测试套件（S/M/H/R四层）
- ⏳ 分析结果并迭代优化

### Phase 6：多工作表场景（Week 6+，优先级P3）
- ⏳ 设计W1-W3场景（跨表引用）
- ⏳ 标记CAPABILITY_UNSUPPORTED预期
- ⏳ 为未来跨表能力预留测试用例

---

## 六、预期成果

### 6.1 测试数据集规模

| 层级 | 场景数 | 数据量 | 空值率 | 异常状态 | 语义歧义 |
|------|-------|--------|--------|---------|---------|
| S简单 | 3 | 37-221行 | 0% | 0% | 无 |
| M中等 | 8 | 141-961行 | 10% | 10% | 无 |
| H困难 | 4 | 200-1,501行 | 12% | 15% | 有（3列模糊） |
| R真实 | 6 | 600-6,000行 | 12-15% | 15-20% | 有（业务判断） |
| W工作流 | 3 | 5,000+行 | N/A | N/A | 跨表引用 |
| **总计** | **24** | **37-6,000行** | **0-15%** | **0-20%** | **S/M无，H/R有** |

### 6.2 对标学术基准

| 维度 | SpreadsheetBench | SheetPilot目标 |
|------|------------------|---------------|
| 数据来源 | Excel论坛真实问题 | 真实业务场景+公开数据 |
| 复杂度 | 85.7词/指令 | 分级Prompt（精确→模糊） |
| 数据量 | 20,000行 | 600-6,000行 |
| 评估方式 | OJ风格多测试用例 | Gate+Score+Oracle |
| 空值率 | 12-15% | 10-15%（R系列） |
| 工作表数 | 平均11.8张 | 1-2张（W系列标记不支持） |

### 6.3 质量提升指标

**测试覆盖度**：
- 从2个简单场景 → 24个分层场景
- 从单一干净数据 → 真实脏数据（空值、异常、格式不一致）
- 从精确字段名 → 模糊字段+样本判断

**评估精细度**：
- 从5个Gate → 5个Gate + 3个新维度
- 从100分/null → 100分制+细分扣分项
- 从手工判断 → 自动化验证（runner.py）

**业务贴合度**：
- 从"左列未税，右列含税=未税×1.13" → "统计各区域销售情况"（模糊需求）
- 从玩具数据 → 真实业务模式（财务对账、RFM分析、ROI计算）
- 从187/198正常状态 → 15-20%异常状态

---

## 七、关键决策记录

### 决策1：为什么是4层而不是3层？
**理由**：学术基准显示真实Excel使用复杂度远超当前测试，需要R系列弥补差距，同时保留S/M/H三层作为能力爬坡。

### 决策2：为什么W系列标记CAPABILITY_UNSUPPORTED？
**理由**：当前SheetPilot的`summarize_table`契约不支持跨表引用，W系列用于：
1. 明确当前能力边界
2. 为未来跨表能力预留测试用例
3. 防止Agent尝试不支持的操作

### 决策3：为什么不直接改quality_score公式？
**理由**：向后兼容旧测试，新维度作为观察指标，待积累足够数据后再决定是否纳入主评分。

### 决策4：为什么需要runner.py而不是手工执行？
**理由**：
1. 可重复性：相同场景多次执行对比
2. 规模化：24个场景手工执行成本过高
3. 持续集成：可集成到CI/CD流程
4. 数据积累：自动归档结果用于趋势分析

---

## 附录：参考资料

### 学术基准论文
- SpreadsheetBench (NeurIPS 2024): "912 real questions from Excel forums"
- SpreadsheetBench 2 (2026): "Financial modeling with 11.8 sheets average"
- FINCH Benchmark (Dec 2025): "1,710 spreadsheets, 27M cells, Enron corpus"
- Alpha Excel Benchmark: "113 FMWC challenges, world champion vs LLM"

### 公开数据集
- Kaggle: Sample Sales Data, Supermarket Sales
- Enron Corpus: 15,000 spreadsheets from corporate emails
- EUSES: Financial spreadsheets collection

### 项目内部文档
- `ARCHITECTURE.md`: SheetPilot架构与设计思路
- `docs/current/13-summarize-table-task-request-contract-prototype-v1.md`: Task Request契约详细规范
- `skills/sheetpilot-excel-agent/SKILL.md`: Agent使用指南（18KB）

```

**评分权重调整**：
```python
# 旧权重（当前）
interface_compliance: 30分
execution_efficiency: 20分
recovery_behavior: 15分
evidence_and_report: 20分
output_usability: 15分

# 新权重（R系列场景）
interface_compliance: 20分
execution_efficiency: 15分
interaction_efficiency: 15分（新）
binding_quality: 15分（新）
clarification_capability: 10分（新，仅模糊场景）
recovery_behavior: 10分
evidence_and_report: 10分
output_usability: 5分
```

### 3.4 Skill脚本重构方案

**重构目标**：
1. 对齐新的Gate+Score体系
2. 支持多轮对话评审（不只是单轮Task执行）
3. 输出结构化评分 breakdown

**`skills/sheetpilot-run-review/SKILL.md` 改造**：

```markdown
---
name: sheetpilot-run-review
description: 评审SheetPilot Agent执行记录，验证黑盒纪律、交互效率、字段绑定质量
---

## 输入格式

执行记录目录：`tests/agent_contract/results/<scenario>__<timestamp>__<run-id>/`
- `replay.json`：完整对话记录
- `request.json`：最终Task Request
- `oracle-result.json`：独立Oracle验证结果
- `task-status.json`：Runtime返回的status

## 评审流程

1. **读取执行记录**：`replay.json` → 提取conversation、commands、timing
2. **调用评估框架**：`python -m tests.agent_contract.evaluation.cli evaluate <run-dir>`
3. **解读评估结果**：
   - Gates通过情况（6个门）
   - Critical Violations（8类违规）
   - Score breakdown（各维度得分）
   - 交互效率（轮次、CLI调用）
   - 字段绑定质量（如有）

## 输出格式

```markdown
# 执行记录评审报告

## 基本信息
- 场景ID：<scenario_id>
- 执行时间：<timestamp>
- Agent模型：<model>
- Skill版本：<skill_version>

## 评审结论
- **任务结果**：PASS / FAIL
- **质量评分**：85/100

## Gates检查（6项）
- [✓] expected_outcome：符合预期结果
- [✓] acceptance_complete：验收条件完整
- [✓] critical_violations_zero：无严重违规
- [✓] semantic_review：语义正确
- [✓] input_unchanged：输入文件未变
- [✓] evidence_complete：证据完整

## Critical Violations（8类）
- source_access_attempts: 0
- legacy_cli_calls: 0
- manual_workbook_writes: 0
- run_dir_operations: 0
- agent_authored_internal_plans: 0
- unauthorized_amendments: 0
- acceptance_reductions: 0
- false_success_claims: 0

## 评分Breakdown
- interface_compliance: 20/20（使用正确CLI）
- execution_efficiency: 12/15（CLI调用4次，理想3次）
- interaction_efficiency: 13/15（6轮对话，理想4轮）
- binding_quality: 15/15（字段绑定100%正确）
- recovery_behavior: 10/10（正确处理NEEDS_BINDING）
- evidence_and_report: 10/10（完整证据）
- output_usability: 5/5（输出正确）

## 改进建议
1. 减少不必要的task-types重复调用（第2、4次调用返回相同结果）
2. 首次Request可直接使用精确字段名，避免进入NEEDS_BINDING
```

**`skills/sheetpilot-run-scorer/SKILL.md` 改造**：

简化为批量评分工具：
```markdown
---
name: sheetpilot-run-scorer
description: 批量评分多个SheetPilot执行记录，生成汇总报告
---

## 用法

输入：测试结果目录 `tests/agent_contract/results/`
输出：`score-summary-<timestamp>.json`

## 评分逻辑

调用 `evaluation/evaluator.py` 的 `evaluate_run()` 批量处理所有run-bundle，
汇总统计：
- 通过率：PASS数量 / 总数
- 平均分：所有PASS场景的quality_score均值
- Gate通过率：各Gate的通过率分布
- 高频违规：Critical Violations的分布

## 输出示例

```json
{
  "summary": {
    "total_runs": 15,
    "passed": 12,
    "failed": 3,
    "pass_rate": 0.80,
    "average_quality_score": 87.5
  },
  "gate_pass_rates": {
    "expected_outcome": 0.93,
    "acceptance_complete": 0.87,
    "critical_violations_zero": 0.80,
    "semantic_review": 1.00,
    "input_unchanged": 1.00,
    "evidence_complete": 0.93
  },
  "violation_distribution": {
    "source_access_attempts": 2,
    "acceptance_reductions": 1,
    "false_success_claims": 0
  }
}
```
```

---

## 四、自动化测试方法

### 4.1 测试执行流程

```
┌─────────────────────────────────────────────┐
│ 1. 准备阶段                                   │
│  - 读取场景定义JSON（scenario + prompt）      │
│  - 检查数据文件存在性                         │
│  - 生成结果目录<AUTO-RESULT-DIR>              │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 2. Agent执行阶段                             │
│  - 启动Agent会话（via API或CLI）              │
│  - 发送Prompt                                │
│  - 记录完整对话（conversation, commands）     │
│  - 捕获Runtime响应（task-run, task-status）   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 3. Oracle验证阶段                            │
│  - 调用evaluate_summarize_table()            │
│  - 独立计算expected结果                      │
│  - 对比actual vs expected                    │
│  - 检查input_unchanged                       │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 4. 评估阶段                                  │
│  - 调用evaluate_run(bundle)                  │
│  - Gates检查                                 │
│  - Critical Violations统计                   │
│  - 评分breakdown计算                         │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 5. 归档阶段                                  │
│  - 保存run-bundle.json                       │
│  - 保存replay.json                           │
│  - 保存oracle-result.json                    │
│  - 保存evaluation-result.json                │
│  - 归档到reviews/<scenario>_<hash>_<time>/   │
└─────────────────────────────────────────────┘
```

### 4.2 自动化脚本设计

**`tests/agent_contract/runner.py`**（新建）：

```python
"""
SheetPilot Agent Contract 自动化测试执行器
"""
import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from tests.agent_contract.evaluation.oracle import evaluate_summarize_table, sha256_file
from tests.agent_contract.evaluation.evaluator import evaluate_run
from tests.agent_contract.evaluation.cli import archive_directory_name


@dataclass
class TestScenario:
    id: str
    prompt: str
    data_file: Path
    expected_outcome: str  # "success" | "correct_stop"
    ideal_rounds: int
    ideal_cli_calls: int
    requires_clarification: bool
    oracle_params: dict[str, Any]


def load_scenarios(scenario_dir: Path) -> list[TestScenario]:
    """从JSON文件加载测试场景定义"""
    scenarios = []
    for file in scenario_dir.glob("*.json"):
        with file.open(encoding="utf-8") as f:
            data = json.load(f)
            scenarios.append(TestScenario(**data))
    return scenarios


def execute_agent_session(scenario: TestScenario, agent_api_key: str) -> dict:
    """
    启动Agent会话并执行场景
    
    返回：
    {
        "conversation": [...],  # 完整对话
        "commands": [...],      # 执行的命令
        "task_request": {...},  # 最终Request
        "task_status": {...},   # Runtime status
        "timing": {...}         # 时间统计
    }
    """
    # TODO: 对接实际Agent API
    # 这里需要调用BitAgent或其他Agent平台的API
    # 记录完整交互过程
    pass


def run_test_suite(
    scenario_dir: Path,
    data_dir: Path,
    results_dir: Path,
    agent_api_key: str,
) -> dict[str, Any]:
    """运行完整测试套件"""
    scenarios = load_scenarios(scenario_dir)
    results = []
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Running scenario: {scenario.id}")
        print(f"{'='*60}")
        
        # 1. 执行Agent会话
        session = execute_agent_session(scenario, agent_api_key)
        
        # 2. Oracle验证
        input_file = data_dir / scenario.data_file
        input_sha_before = sha256_file(input_file)
        task_request = session["task_request"]
        oracle_result = evaluate_summarize_table(
            task_request,
            input_sha256_before=input_sha_before,
            **scenario.oracle_params,
        )
        
        # 3. 构造Bundle
        bundle = {
            "scenario": {
                "id": scenario.id,
                "expected_outcome": scenario.expected_outcome,
                "ideal_rounds": scenario.ideal_rounds,
                "ideal_cli_calls": scenario.ideal_cli_calls,
                "requires_clarification": scenario.requires_clarification,
            },
            "prompt": scenario.prompt,
            "conversation": session["conversation"],
            "commands": session["commands"],
            "task_request": task_request,
            "task_status": session["task_status"],
            "oracle_result": oracle_result,
            "timing": session["timing"],
        }
        
        # 4. 评估
        evaluation = evaluate_run(bundle)
        
        # 5. 归档
        archive_dir = results_dir / archive_directory_name(bundle, scenario.id)
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        (archive_dir / "run-bundle.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (archive_dir / "evaluation-result.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        
        results.append({
            "scenario_id": scenario.id,
            "result": evaluation["task_result"],
            "score": evaluation.get("quality_score"),
            "archive_dir": str(archive_dir),
        })
        
        print(f"Result: {evaluation['task_result']}")
        if evaluation.get("quality_score"):
            print(f"Score: {evaluation['quality_score']}/100")
    
    # 6. 汇总报告
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["result"] == "PASS"),
        "failed": sum(1 for r in results if r["result"] == "FAIL"),
        "average_score": sum(r["score"] or 0 for r in results) / len([r for r in results if r["score"]]),
        "details": results,
    }
    
    return summary


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python runner.py <agent_api_key>")
        sys.exit(1)
    
    project_root = Path(__file__).resolve().parents[2]
    summary = run_test_suite(
        scenario_dir=project_root / "tests/agent_contract/scenarios",
        data_dir=project_root / "tests/agent_contract/data",
        results_dir=project_root / "tests/agent_contract/results",
        agent_api_key=sys.argv[1],
    )
    
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass Rate: {summary['passed']/summary['total']*100:.1f}%")
    print(f"Average Score: {summary['average_score']:.1f}/100")
```

### 4.3 场景定义JSON示例

**`tests/agent_contract/scenarios/R1_finance_reconciliation.json`**：

```json
{
  "id": "R1",
  "prompt": "帮我用$sheetpilot-excel-agent分析这个科目余额表：\n输入：tests/agent_contract/data/R1_finance_ledger.xlsx\n场景：R1\n\n筛选资产类科目，按一级科目汇总借方、贷方余额，输出到"资产科目汇总"。",
  "data_file": "R1_finance_ledger.xlsx",
  "expected_outcome": "success",
  "ideal_rounds": 4,
  "ideal_cli_calls": 3,
  "requires_clarification": false,
  "oracle_params": {
    "tolerance": 0.01,
    "expected_groups": 5,
    "expected_total_debit": 1250000.00,
    "expected_total_credit": 850000.00
  }
}
```

**`tests/agent_contract/scenarios/H3_ambiguous_field.json`**：

```json
{
  "id": "H3",
  "prompt": "用$sheetpilot-excel-agent统计各区域的销售情况：\n输入：tests/agent_contract/data/H3_sales_multi_amount.xlsx\n场景：H3\n\n按区域汇总销售，输出到"区域销售汇总"。",
  "data_file": "H3_sales_multi_amount.xlsx",
  "expected_outcome": "success",
  "ideal_rounds": 5,
  "ideal_cli_calls": 4,
  "requires_clarification": false,
  "oracle_params": {
    "tolerance": 0.01,
    "correct_field": "净销售收入",
    "binding_required": true
  }
}
```

---

## 五、实施路线图

### Phase 1：数据准备（Week 1-2）
- [ ] 下载Kaggle数据集（Sample Sales, Supermarket Sales, Retail Dataset）
- [ ] 编写Python脚本生成R1-R6业务场景数据
- [ ] 注入真实脏数据（空值、异常、格式不一致）
- [ ] 验证数据Oracle（手工计算预期结果）

### Phase 2：评估框架升级（Week 2-3）
- [ ] 在`evaluator.py`中实现新评估维度
  - `_interaction_efficiency()`
  - `_binding_quality()`
  - `_clarification_capability()`
- [ ] 调整评分权重
- [ ] 编写单元测试验证评估逻辑

### Phase 3：Skill重构（Week 3-4）
- [ ] 重构`sheetpilot-run-review`对齐新评估框架
- [ ] 重构`sheetpilot-run-scorer`支持批量评分
- [ ] 编写使用文档和示例

### Phase 4：自动化脚本（Week 4-5）
- [ ] 实现`runner.py`测试执行器
- [ ] 实现Agent API对接（BitAgent或其他平台）
- [ ] 编写场景定义JSON（S1-S9, M1-M4, H1-H4, R1-R6）
- [ ] 实现归档和报告生成

### Phase 5：测试验证（Week 5-6）
- [ ] 用现有Agent执行S1-S9基础场景
- [ ] 执行M1-M4中等场景
- [ ] 执行H1-H4困难场景
- [ ] 执行R1-R6真实业务场景
- [ ] 收集通过率、平均分、高频问题

### Phase 6：迭代优化（Week 6+）
- [ ] 根据测试结果调整评分权重
- [ ] 补充边缘场景（如果发现新问题）
- [ ] 优化Oracle验证逻辑
- [ ] 完善文档

---

## 六、成功标准

**数据集质量**：
- ✅ 覆盖6大业务场景（财务、电商、人力、客户、渠道、物流）
- ✅ 真实数据脏度：空值10-15%、异常15-20%、格式不一致5-10%
- ✅ 每个场景有明确Oracle和业务规则文档

**评估框架**：
- ✅ 支持8类Critical Violations检测
- ✅ 支持6个Gate检查
- ✅ 支持新维度（交互效率、绑定质量、澄清能力）
- ✅ 评分breakdown与业务场景复杂度匹配

**自动化测试**：
- ✅ 一键执行全部场景测试
- ✅ 自动归档执行记录和评估结果
- ✅ 生成汇总报告（通过率、平均分、分布）
- ✅ 支持回归测试（对比历史结果）

**通过率目标**：
- S系列（简单）：≥ 95%
- M系列（中等）：≥ 85%
- H系列（困难）：≥ 70%
- R系列（真实）：≥ 60%（首版）

---

## 附录

### A. 参考资源
- Kaggle Business Datasets: https://www.kaggle.com/datasets?tags=11102-Business
- Excel练习数据Hub: https://excelx.com/practice-data/
- 中文企业场景参考：电商库存管理、财务对账、人力成本分析

### B. 现有评估框架接口
- `oracle.py::evaluate_summarize_table()` - 独立Oracle验证
- `evaluator.py::evaluate_run()` - Gate+Score评估
- `evaluator.py::inspect_commands()` - 命令审计

### C. 待定问题
1. Agent API对接方式：BitAgent API还是通用MCP接口？
2. 多轮对话场景如何记录完整conversation？
3. 需求澄清场景的预期问题列表如何定义？（人工标注 vs 自动推理）
