# Excel Agent 混合执行系统设计

## 文档说明

本目录描述一个集成到 Agent 的 Excel 混合执行系统。目标态允许固定能力、原子能力和受控动态能力混合执行；当前 MVP 以 V3 文档为实施基线，采用 LLM 语义映射、自研轻量 CLI Executor、Workbook SDK 和 openpyxl 单引擎，不开放动态脚本。

## 文档导航

- [01-overall-architecture.md](./01-overall-architecture.md)：目标、原则、系统边界、总体组件、核心流程和部署视图。
- [02-detailed-architecture.md](./02-detailed-architecture.md)：能力注册、规划与路由、工具编排、动态脚本、安全、审计、数据结构和接口设计。
- [03-mvp-architecture-v2.md](./03-mvp-architecture-v2.md)：现有设计问题审查，以及可直接实施的 MVP 范围、架构、契约和验收标准。
- [04-mvp-overall-architecture-v3.md](./04-mvp-overall-architecture-v3.md)：当前 MVP 总体架构基线，明确语义理解、分级门禁、执行器和引擎的职责。
- [05-mvp-detailed-design-v3.md](./05-mvp-detailed-design-v3.md)：当前 MVP 详细设计基线，定义数据契约、CLI、Executor、Workbook SDK、验证和测试。
- [06-capability-registry-and-tools-design-v1.md](./06-capability-registry-and-tools-design-v1.md)：能力工具的实施设计，定义唯一能力注册表、12 项编排级工具契约、Compiler/Dispatcher 接入和分阶段实现顺序。
- [07-test-retrospective-and-hybrid-script-architecture-v1.md](./07-test-retrospective-and-hybrid-script-architecture-v1.md)：两次脏订单实测复盘；明确脏订单是评测场景，并确立“中粒度 Composite 优先、稳定完整流程才提升 Recipe、长尾动态生成”的混合架构。
- [08-hybrid-planner-and-script-runtime-mvp-v1.md](./08-hybrid-planner-and-script-runtime-mvp-v1.md)：细化 Composite/Capability 实现、组合计划、Agent 自主规划、Recipe 提升门槛和动态脚本运行时，并给出可直接实施的 MVP 方案。
- [09-hybrid-mvp-implementation-status-v1.md](./09-hybrid-mvp-implementation-status-v1.md)：记录基于现有源码增量实施 A-D 阶段的判断、已完成模块、安全边界和剩余工作。
- [10-atomic-and-molecular-capability-architecture-v1.md](./10-atomic-and-molecular-capability-architecture-v1.md)：根据实测和后续讨论重新定义原子能力、可展开分子能力、统一能力目录、确定性组合器及任务级验收，并给出各分类能力的详细实现与分阶段 MVP 方案。
- [11-capability-catalog-and-usage-spec-v1.md](./11-capability-catalog-and-usage-spec-v1.md)：逐项定义 Atom/Molecule 的参数、输入输出、使用方式、展开步骤、验证要求、注册规范和 MVP 实施顺序。
- [12-lightweight-skill-test-findings-and-implementation-handoff-v1.md](./12-lightweight-skill-test-findings-and-implementation-handoff-v1.md)：复盘轻量 Skill 首次真实文件测试，记录 CLI、能力契约、动态脚本、写入与任务级验证缺口，并给出下一会话可直接执行的分阶段实施清单。
> 当前实施基线为 V3。V2 保留用于记录从目标态平台设计收敛到 MVP 的原因。

> `10` 是能力分层与组合规划的最新目标设计；涉及 Atom、Molecule、Planner 和任务级 Validator 的后续实现以该文档为准。`09` 仍用于说明当前代码已经实现到哪里，两者不要混同。

> `11` 是 `10` 的逐项能力契约补充；开发新能力或修改现有能力时，应先更新该文档中的定义和验收要求，再实施代码。

## 目标态历史决策

以下内容来自早期目标态设计，不代表 V3 MVP 全部进入首期实现。MVP 决策以 `04` 和 `05` 文档为准。

| 事项 | 决策 |
|---|---|
| 产品形态 | 集成到 Agent，通过自然语言操作 Excel |
| 首期文件格式 | 仅支持 `.xlsx` |
| 优先场景 | 经营报表、修改已有 Excel、财务模型 |
| 执行模式 | 少量成熟 Recipe 完整命中优先；通常由中粒度 Composite 与 Capability 组合；动态脚本补能力缺口 |
| 固定能力形态 | 以可复用业务模块 Composite 和区域级 Capability 为主，只将长期稳定的完整流程固化为 Recipe |
| 动态脚本 | 允许生成，但必须受到能力、路径、依赖、资源和风险限制 |
| 原文件策略 | 默认禁止覆盖，统一另存为新文件 |
| 可观测性 | 保存完整操作日志，并向用户展示处理进度 |
| 验收策略 | 默认严格验收，包括结构、公式、业务和视觉检查 |
| 用户交互 | 纯自然语言，同时允许选择或确认模板 |
| 风险操作 | 执行前必须获得用户确认 |
| 首期目标 | 先完成可演示的 MVP，再逐步产品化 |
| 真实输入策略 | 用户提供的 XLSX 始终是输入事实源，禁止用合成模板替代或重建 |
| 交付模式 | MVP 默认 XLSX-first；引擎工作格式只作为中间态，除非用户明确要求一并交付 |
| 执行边界 | 一次导入、一次有界编辑、一次导出、一次收尾；失败优先在当前工作副本上定向修复 |
| Agent 接入方式 | Skill 目录自动发现 + 本地 CLI/Shell 调用；MVP 不要求先实现 MCP |

## 目标态待决策事项

### 1. 底层引擎

目前不锁定唯一引擎。候选方案如下：

| 引擎 | 优势 | 主要限制 | 建议定位 |
|---|---|---|---|
| openpyxl | 轻量、成熟、适合直接处理 XLSX | 不计算公式，高级 Excel 对象保真有限 | MVP 主引擎候选 |
| Windows COM | 使用真实 Excel，原生功能和重算能力强 | 仅 Windows、需安装 Excel、并发和稳定性成本高 | 高保真与高级能力引擎 |
| Univer | 可维护 `.unv` 状态并提供 Web 表格工作台 | XLSX 导入导出存在兼容成本 | 需要 Web 编辑体验时接入 |

系统不强求不同引擎实现完全相同的单元格级 API。上层统一的是任务契约、产物契约、变更声明和验收契约；引擎内部可以采用不同流水线。例如 Univer 使用 `import -> inspect -> run -> export -> finalize`，openpyxl 直接处理工作副本，COM 则通过真实 Excel 会话执行和另存为。

### 2. 高级 Excel 对象的首期支持范围

首期先检测宏、Power Query、数据模型、复杂透视表、切片器等对象。若当前引擎无法安全保留，系统应停止、提示风险或路由到支持的引擎，不能静默降级。

## 核心定位

本系统不是单纯的固定模板生成器，也不是让 LLM 每次自由编写脚本。它采用受控的混合模式：

```text
长期稳定的完整流程         -> 少量 Recipe
常见业务计算和报表区块     -> Composite
跨业务的区域级 Excel 操作  -> Capability
固定能力无法覆盖的数据逻辑 -> Dynamic Transform
特殊且可控的工作簿任务     -> Dynamic Task
所有执行结果               -> 独立验收和可视化交付
```

动态脚本是兜底机制，不是默认路径。系统优先选择覆盖完整、风险更低、可验收性更强的执行方案。

## 从迁移版 Univer 吸收的设计结论

迁移版 Univer 的真实输入编辑链路是：

```text
原始 XLSX/CSV
  -> import 为 .unv 工作包
  -> inspect/search 确认可见状态
  -> 单个有界 run 脚本修改
  -> 读取工作簿可见状态复核
  -> export 为 XLSX
  -> finalize-xlsx 修复并审计导出物
  -> PNG/OOXML/业务规则验收
```

架构据此增加四项约束：

1. 区分输入事实源、引擎工作状态和最终交付物，不把三者混为一个文件。
2. 区分工作簿执行引擎与交付流水线；导入、导出和收尾修复都是一等能力。
3. 修改真实输入时不得调用只会生成合成数据的报表模板。
4. 工作态验证和交付态验证必须分别进行，Viewer 或 `.unv` 正常不能证明最终 XLSX 正常。

## 迁移版 Univer 如何接入 BitAgent

迁移版没有修改 BitAgent 核心，也没有注册 MCP Server。它使用两层接入：

```text
BitAgent 启动
  -> 扫描 %USERPROFILE%\.agents\skills
  -> 读取 univer-cli 等 SKILL.md
  -> 根据 Skill 路由和规则生成 Shell 命令
  -> 调用 PATH 中的 guard\bin\univer.cmd
  -> Guard 校验/恢复本地补丁
  -> 调用 patched univer-cli
  -> CLI 返回退出码、JSON 和文件产物
  -> BitAgent 根据 Skill 继续验证和交付
```

因此，Skill 是 BitAgent 的“能力发现与使用说明”，CLI 是实际执行面，Guard 是安装完整性和运行稳定性保护。三者缺一不可，但它们都位于 BitAgent 核心进程之外。
