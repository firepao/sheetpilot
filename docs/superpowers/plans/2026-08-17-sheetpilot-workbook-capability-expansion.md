# SheetPilot Workbook 能力逐步开放实施计划

> 本文是实施计划，不包含本轮代码实现。执行时按阶段推进；每个阶段的 Release Gate 全部通过后，才进入下一阶段。

**目标：** 在保持 Agent-facing Runtime 确定性、可审计和写入安全边界的前提下，把 `WorkbookContext` 已有能力逐步包装为版本化、强类型的公开 Task Type。

**总体架构：** Agent 继续只提交 Task Request，不提交 Atom、Capability、Recipe 或 DAG。每个 Task Type 独立拥有请求契约、绑定要求、确定性 Compiler、Acceptance 扩展器和 Validator。内部统一复用 `sheetpilot.workbook`，所有输出先写临时工作簿，验收通过后原子发布。

**公开接口约束：** 继续只保留 `task-types`、`task-run`、`task-status` 三个 Agent 可见命令。不得直接公开旧 `DEFAULT_REGISTRY`、Planner、Recipe、动态表达式或任意 openpyxl 脚本入口。

## 1. 已有能力与目标映射

| 内部能力 | 首次公开方式 | 风险等级 | 计划阶段 |
|---|---|---:|---:|
| `read_table`、`filter_rows`、`aggregate`、`select_columns`、`sort_rows` | 增强 `summarize_table` | 低 | Phase 1 |
| `derive_column` | `derive_table 1.0` | 中 | Phase 2 |
| 异常分类、清洗明细 | `clean_table 1.0` | 中 | Phase 3 |
| 多 Sheet、KPI、对账、样式、冻结窗格 | `build_operating_report 1.0` | 中高 | Phase 4 |
| `create_chart` | `build_operating_report 1.1` 或独立图表 Task | 高 | Phase 5 |
| `add_formula_column`、修改已有 Sheet | 受控编辑 Task | 最高 | Phase 6 |

以下约束贯穿所有阶段：

- 输入字段只能通过 Binding Snapshot 解析，Agent 不提交列字母。
- Compiler 输出必须可稳定哈希；相同冻结输入必须产生字节级相同计划。
- Acceptance、binding、coverage、effects、版本和 hash 都必须持久化。
- 默认只创建新 Sheet、输出新文件；禁止静默覆盖输入数据。
- 新能力必须通过 `WorkbookContext` 或内部 Operation 执行，不允许旁路为手写 openpyxl 脚本。
- 每种失败必须落入公开契约错误、字段绑定、能力不支持、输入变化、发布冲突或内部错误之一。

## 2. Phase 0：基础可靠性与 Task Type 骨架

**目的：** 先修复复杂工作簿已经暴露的基础问题，建立新增 Task Type 的统一扩展点。

**主要文件：**

- 修改 `src/sheetpilot/task_api/inventory.py`
- 修改 `src/sheetpilot/task_api/contract.py`
- 修改 `src/sheetpilot/task_api/compiler.py`
- 修改 `src/sheetpilot/task_api/runtime.py`
- 新建或补充 `src/sheetpilot/task_api/task_types.py`（若实现时决定拆包，则迁移为 `task_types/`）
- 补充 `tests/unit/`、`tests/integration/test_task_api.py`

- [ ] 增加统一 JSON 值标准化函数，明确处理 `date`、`datetime`、`time`、`Decimal`、空值及非有限浮点数。
- [ ] 字段清单样本、请求快照、Evidence 和状态文件统一使用稳定序列化；日期采用 ISO 8601，不依赖系统 locale。
- [ ] 用 Task Type Definition 统一生成 Manifest、契约版本、支持特性、最小示例和 Compiler/Validator 选择，先保持 `summarize_table 1.0` 行为不变。
- [ ] 在 Internal Plan 中增加 `task_type`、`compiler_version`、`validator_version`，保持 plan hash 确定性。
- [ ] 建立独立的工作簿对象保真专项测试套件（见下节），作为所有写工作簿阶段的共同门禁。
- [ ] 统一发布前验证与 Evidence schema，并为 schema 设置版本。

**测试：**

- [ ] 单元测试覆盖真实 Excel 日期、时区 datetime、Decimal、空值和敏感样本掩码。
- [ ] 集成测试用 `07_complex_retail_operations.xlsx`、`08_complex_saas_renewals.xlsx`、`09_complex_dirty_logistics.xlsx` 查询字段清单，保证不再出现 `datetime 类型无法 JSON 序列化`。
- [ ] 回归 `summarize_table 1.0` 的成功、绑定歧义、输入 hash 变化和发布冲突。
- [ ] 验证相同冻结输入两次编译的 Plan JSON 和 hash 完全一致。

### 2.1 工作簿对象保真专项测试套件

**目录与夹具：**

- 新建 `tests/workbook_fidelity/`，测试代码与二进制夹具分开存放。
- 新建 `tests/workbook_fidelity/fixtures/`，至少包含 `.xlsx` 综合夹具和带真实 `vbaProject.bin` 的 `.xlsm` 夹具。
- 新建 OOXML 快照帮助模块，按 ZIP part、relationship 和关键 XML 节点比较，不以文件整体 SHA-256 相等作为唯一依据；保存工作簿可能合法重排 XML 或更新时间元数据。

**强制覆盖矩阵：**

| 对象 | 必须检查的内容 | 主要失败信号 |
|---|---|---|
| 公式 | 公式文本、共享/数组公式范围、计算属性、外部链接关系 | 公式变成缓存值、引用改变、公式消失 |
| 图表 | drawing relationship、chart part、series/category 公式、anchor | 图表丢失、数据源漂移、锚点改变 |
| VBA | `vbaProject.bin` 字节 hash、content type、relationship、`.xlsm` 扩展名 | 宏部件丢失或 hash 改变 |
| 合并单元格 | 所有 merged ranges 及其所在 Sheet | 范围拆分、扩大、缩小或迁移 |
| 条件格式 | `sqref`、规则类型、公式、优先级、`dxf` 引用 | 规则丢失、应用范围或优先级变化 |

- [ ] 构造“只新增一个 Sheet”的基线操作，断言未授权 Sheet 上述对象语义完全不变。
- [ ] 分别测试普通 `.xlsx`、含图表 `.xlsx`、含宏 `.xlsm`；`.xlsm` 必须使用 `keep_vba=True` 的受控加载/保存路径。
- [ ] 增加公式缓存、定义名称、数据验证、隐藏 Sheet 和冻结窗格的伴随回归，避免对象关系被间接破坏。
- [ ] 输出文件必须能被 openpyxl 重新打开；在 CI 环境可用时增加 LibreOffice headless 打开/另存检查，但不能用其替代 OOXML 断言。
- [ ] 任何 Task Runtime 写入路径都必须运行同一套保真断言，禁止仅对 `WorkbookContext` 单元层测试。
- [ ] 将夹具来源、Excel 版本、是否含宏及预期部件 hash 记录在 `tests/workbook_fidelity/fixtures/README.md`。

**专项门禁：** 公式、图表、VBA、合并单元格或条件格式任一未授权对象发生语义变化，Phase 0 不得完成；`.xlsm` 夹具无法稳定保真时，后续版本必须明确拒绝 `.xlsm` 写入，不能降级保存。

**验收命令：**

```powershell
$env:PYTHONPATH = "src;."
python -m unittest tests.unit.test_inventory -v
python -m unittest tests.integration.test_task_api -v
python -m unittest discover -s tests -p "test_*.py" -v
```

**停止条件：** 任意合法 Excel 标量仍不能稳定序列化；原工作簿对象出现非预期损坏；Task Type Definition 与运行时契约产生两套事实来源。

## 3. Phase 1：`summarize_table 1.1`

**目的：** 在已有汇总能力上补齐高频查询需求，不引入任意计算表达式。

**契约增量：**

- 日期区间过滤与明确的日期解析规则。
- `is_empty`、`is_not_empty`、`not_in`、受控字符串匹配；每个操作符声明兼容字段类型。
- 多字段稳定排序，明确空值排序位置。
- 空值策略：跳过、归入固定标签或报错，不允许隐式决定。
- 日期粒度维度：年、季度、月、周；时区和周起始日必须进入 Acceptance。

- [ ] 新增 `summarize_table 1.1` 请求模型和 Manifest，保留 `1.0` 可执行性。
- [ ] Compiler 将日期分桶编译为白名单内部 Operation，不把格式字符串或表达式交给 Agent。
- [ ] coverage 覆盖每个 filter、dimension、metric 和 sort；effects 仍仅允许创建一个新 Sheet。
- [ ] Validator 从源数据独立复算各组值、空值策略、排序和日期边界。
- [ ] Evidence 增加源行数、过滤后行数、分组数、空值处理统计和期间边界。

**测试与 Agent Contract：**

- [ ] 月度续费、跨年季度、日期边界、空日期、多字段同值排序。
- [ ] 不兼容操作符、无效日期、未知时区和重复输出名必须在执行前拒绝。
- [ ] 基于复杂零售和 SaaS 数据新增至少 3 个提示词，其中包含一个预期停止场景。

**停止条件：** 日期口径无法被 Acceptance 完整冻结；排序结果依赖 Python dict 顺序之外的隐式行为；Validator 不能独立复算。

## 4. Phase 2：`derive_table 1.0`

**目的：** 允许从源列产生受控派生列，输出到新 Sheet，不修改原 Sheet。

**首版模板白名单：** `add`、`subtract`、`multiply`、`safe_divide`、`coalesce`。模板参数只能引用已绑定字段或类型匹配的字面量；禁止任意 Python/Excel 表达式。

- [ ] 定义 `derive_table 1.0`：source、可选过滤、保留列、派生列、有序输出列、目标 Sheet/anchor。
- [ ] Acceptance 冻结每个派生列的 ID、模板、输入绑定、常量、除零策略、空值策略、输出名称和顺序。
- [ ] Compiler 生成 `read_table → filter_rows? → derive_column* → project_columns → create_sheet → write_table`。
- [ ] 禁止派生列覆盖已有列名，禁止循环引用，限制列数、行数和模板链深度。
- [ ] Validator 逐行独立抽样并全列检查错误计数；Evidence 记录派生错误、除零和空值分支次数。

**测试与 Agent Contract：**

- [ ] 毛利额、毛利率、含税金额、缺失字段回填等成功场景。
- [ ] 除零、文本参与乘法、重复名称、未绑定字段、超出链深度等失败场景。
- [ ] 确认源 Sheet 内容和对象 hash 不变，派生结果仅出现在新 Sheet。

**停止条件：** 需要开放任意表达式才能完成首版；派生语义不能用白名单参数完整描述；原 Sheet 发生写入。

## 5. Phase 3：`clean_table 1.0`

**目的：** 把脏数据识别与处理变成显式、可审计的任务，而不是静默修改数据。

**首版输出：** 至少创建“清洗明细”和“异常明细”两个新 Sheet。原始值保留，新增规则 ID、异常原因、处理动作和处理后值等审计列。

- [ ] 定义规则白名单：必填、类型、枚举、范围、重复键、日期合法性和字段间一致性。
- [ ] 定义动作白名单：仅标记、排除到异常表、固定值替换、受控类型转换；默认动作是仅标记。
- [ ] Acceptance 冻结规则顺序、严重度、匹配字段、动作、输出 Sheet 和审计列。
- [ ] Compiler 使用内部 `classify_invalid_rows` 语义展开，不直接引用旧 Composite Registry。
- [ ] Validator 独立复跑规则，核对总行数守恒：有效行 + 异常行（按约定去重口径）与源行一致。
- [ ] Evidence 记录每条规则命中数、动作数、未处理异常数和 reconciliation。

**测试与 Agent Contract：**

- [ ] 使用复杂物流数据覆盖混合日期、空运单号、非法金额、重复记录和状态冲突。
- [ ] 同一行命中多规则、规则顺序冲突、转换失败和输出 Sheet 冲突。
- [ ] 明确验证没有任何脏值被无证据地覆盖或丢弃。

**停止条件：** 无法证明行数守恒；规则或动作依赖自由文本代码；异常处理没有逐行审计证据。

## 6. Phase 4：`build_operating_report 1.0`

**目的：** 在一次原子任务中生成可交付的多 Sheet 经营报告。

**首版内容：** 明细或清洗结果、维度汇总、KPI block、reconciliation Sheet、固定样式 preset 和冻结窗格。暂不包含图表。

- [ ] 定义报告 sections 的强类型契约，限制 Sheet 数、KPI 数、汇总数和目标区域。
- [ ] Compiler 为每个 section 生成稳定 step ID、coverage 和写入 effects，并在编译期检查 Sheet/区域冲突。
- [ ] 复用 `business_table`、`title`、`total_row`、`input_area`、`formula_area` preset，不开放任意字体、颜色或边框对象。
- [ ] 支持 freeze panes，但位置必须进入 Acceptance。
- [ ] 所有 Sheet 在同一临时工作簿完成，全部 Validator 通过后一次性发布；不允许部分成功。
- [ ] reconciliation 独立核对源总量、过滤排除量、报告总量和差异。

**测试与 Agent Contract：**

- [ ] 复杂零售经营报告、SaaS 续费报告、脏物流治理报告各一个端到端场景。
- [ ] Sheet 重名、目标区域重叠、KPI 引用不存在的指标、样式不支持、任一 section 验证失败。
- [ ] 对输出布局做结构检查，并人工抽查 Excel 打开效果。

**停止条件：** 任一 section 失败仍会发布部分结果；多 Sheet effects 无法在编译期完整枚举；对账不能闭合。

## 7. Phase 5：原生图表

**目的：** 只在本任务新建的连续结果区域上创建可验证的 Excel 原生图表。

- [ ] 首版只支持 `bar`、`column`、`line`；`pie` 在多系列和负数策略明确后再启用。
- [ ] 契约冻结 chart type、数据源 section、category、series、title、anchor 和尺寸。
- [ ] Compiler 只能引用同一计划已写入的结果区域，禁止任意单元格引用和外部链接。
- [ ] Validator 检查 drawing relationship、series/category 公式、源范围、anchor、标题及图表数量。
- [ ] 增加 LibreOffice/Excel 可打开性检查；对关键场景增加渲染截图或 drawing XML 检查。
- [ ] 图表失败必须使整个报告不发布。

**停止条件：** 图表引用可逃逸到未授权范围；保存后 drawing 丢失；只能凭“文件可打开”而无法核对图表语义。

## 8. Phase 6：受控编辑已有 Sheet

**目的：** 在充分的并发控制、差异证据和回滚保障下，最后开放最小范围的原位编辑。

首版只考虑“追加列”或“追加到明确空白区域”，不支持任意覆盖、删除行列、合并单元格或移动对象。

- [ ] 新建独立 Task Type，不扩张前述创建型 Task 的默认权限。
- [ ] 请求必须声明允许修改范围；Runtime 保存该范围的 precondition hash 和原值快照。
- [ ] 执行前复查输入文件 hash、目标范围 hash、Sheet 可见性和空白条件，任一变化均停止。
- [ ] 默认禁止覆盖公式、表格对象、数据验证、条件格式、合并单元格和图表锚点。
- [ ] `add_formula_column` 只允许白名单模板 `safe_ratio`、`subtract`、`add`、`multiply`，公式模板及引用进入 Acceptance。
- [ ] Evidence 输出逐单元格或逐区域 diff、修改前后 hash、公式清单和可恢复快照位置。
- [ ] 发布使用文件级原子替换；保留可恢复备份，并验证输出可重新打开。
- [ ] 建立独立安全测试套件（见下节），使用故障注入验证权限边界、并发控制、回滚和备份可靠性。

**测试与 Agent Contract：**

- [ ] 追加普通值列、追加公式列、目标区非空、输入并发变化、公式覆盖企图和图表锚点冲突。
- [ ] 验证未授权区域字节/对象级不变，备份可以恢复。
- [ ] 任何含宏工作簿必须单列保真测试，未通过前不开放 `.xlsm` 编辑。

**停止条件：** 无法可靠计算目标范围前置条件；不能生成完整 diff；无法保证未授权对象保真；恢复流程未经自动化验证。

### 8.1 受控编辑安全测试套件

**目录与测试基础设施：**

- 新建 `tests/security/workbook_editing/`。
- 提供可注入的文件系统/Publisher failure points，至少覆盖备份完成前、备份完成后、临时文件写入中、验证后发布前、原子替换时和替换后状态落盘前。
- 每个测试使用隔离临时目录和唯一任务状态目录，不依赖执行顺序；保留失败现场用于断言，但测试结束后清理。

**必须覆盖的攻击与故障矩阵：**

| 类别 | 场景 | 必须满足的结果 |
|---|---|---|
| 权限逃逸 | 越界单元格、整行/整列引用、命名区域逃逸、跨 Sheet 引用、路径穿越、软链接/重解析点、公式外部链接 | 编译或执行前拒绝；未授权区域和外部文件零修改 |
| 权限逃逸 | 通过合并单元格、表格对象、图表锚点或公式引用间接影响范围外对象 | 拒绝任务并给出目标冲突证据 |
| 并发竞争 | Acceptance 后源文件变化、目标范围变化、备份后发布前变化、两个任务同时编辑同一区域 | precondition/hash 或锁冲突；最多一个任务发布，禁止丢失更新 |
| 并发竞争 | 两个任务编辑不重叠区域 | 按明确策略串行或拒绝；不得依靠偶然时序合并 |
| 回滚失败 | 写临时文件失败、验证失败、原子替换失败、状态落盘失败 | 原文件保持有效或从已验证备份恢复；状态不得误报 PASS |
| 备份损坏 | 备份截断、hash 不符、无法重开、权限不足、空间不足 | 发布前停止；禁止使用损坏备份继续执行 |
| 恢复失败 | 发布后发现输出损坏且备份也不可用 | 进入明确的不可自动恢复终态，保留证据并禁止继续重试覆盖 |

- [ ] 为所有允许修改范围使用标准化坐标解析，增加 Unicode Sheet 名、引号、绝对引用和最大行列边界测试。
- [ ] 在 Compiler、Executor 和 Publisher 三层分别验证 effects/允许范围，形成纵深防御；测试逐层绕过时下一层仍能拒绝。
- [ ] 用屏障或可控 hook 构造确定性 TOCTOU 测试，禁止用不稳定的 `sleep` 模拟竞争。
- [ ] 验证锁或租约异常退出后的恢复策略，不允许永久锁死，也不允许无条件抢锁。
- [ ] 每次备份后校验文件 hash、大小、可重开性和关键 OOXML 部件；恢复后再次运行工作簿保真专项套件。
- [ ] 断言所有失败路径的状态、错误码、Evidence 和磁盘实际状态一致，不得出现“报告失败但已发布”或“报告成功但已回滚”。
- [ ] 增加重复提交、重复恢复和进程崩溃后重启测试，证明操作具备明确幂等语义。

**专项门禁：** 上述安全场景必须全部自动化通过，并进行一次独立安全评审；任何权限逃逸、丢失更新、不可解释的部分发布、未经校验的损坏备份继续执行，均阻止 Phase 6 发布。

## 9. 每阶段统一交付清单

每个 Phase 合并前必须同时满足：

- [ ] Task Type 契约、Manifest、最小示例和错误恢复提示来自同一版本化定义。
- [ ] Compiler 有 golden plan 测试、稳定 hash 测试和完整 coverage 测试。
- [ ] Runtime 有成功、能力不支持、字段歧义、目标冲突、输入变化和发布冲突测试。
- [ ] Validator 不信任 Compiler 自报结果，能够从冻结 Acceptance 和源/输出文件独立验收。
- [ ] Evidence 足够解释读取范围、写入范围、行数变化、业务结果和发布结果。
- [ ] 对应 Agent Contract 数据、提示词、Oracle 和评分规则已加入 `tests/agent_contract/`。
- [ ] 全量单元与集成测试通过，新增黑盒场景至少连续运行 3 次且 Critical Violation 为 0。
- [ ] 涉及工作簿写入的阶段通过 `tests/workbook_fidelity/`；Phase 6 额外通过 `tests/security/workbook_editing/`。
- [ ] 文档明确该版本支持与不支持的边界；不支持能力返回 `CAPABILITY_UNSUPPORTED`，不得猜测执行。

## 10. 推荐执行批次

1. 先执行 Phase 0，解决日期序列化并建立统一 Task Type 骨架。
2. Phase 1 和 Phase 2 分别交付，先增强查询汇总，再开放派生计算。
3. Phase 3 单独交付，因为清洗规则的审计和行数守恒需要独立 Release Gate。
4. Phase 4 先完成无图表的多 Sheet 报告，稳定后再做 Phase 5。
5. Phase 6 必须最后执行，并经过单独安全评审。

不建议一开始设计“通用 Workbook Task”或让 Agent提交任意步骤。那会绕过当前确定性 Compiler、Acceptance 和 Validator 边界，使能力发现、权限控制、审计和错误恢复重新耦合到 Agent 推理质量。
