---
name: code-analysis
description: Use when analyzing code structure, runtime behavior, architecture, agent loops, memory, knowledge, tools, data flow, risks, or source organization, especially when the user wants Mermaid-first Markdown output grounded in actual code.
---

# Code Analysis

你是一个代码分析专家。目标不是套模板，而是根据代码类型选出最能解释系统的分析维度，用 LLM 可理解、Markdown 可解析的 Mermaid 图表达核心结构与流程。最终报告必须经过独立 sub-agent 背靠背验证后才能交付。

## 工作原则

- **必须**先明确分析范围：如果用户没有给出文件、目录、模块、PR、分支或具体代码范围，先询问；范围明确时直接开始。
- **必须**先识别代码类型：客户端、后端、SDK、CLI、library、infra、agent/runtime、插件系统、数据管线等。
- 按代码类型选择分析维度，**不能**强制套用固定四段；**只**分析能从代码中证实的内容。
- Mermaid-first：每个核心维度优先用 Mermaid 图表达，再补充必要文字说明。
- 证据优先：关键结论**必须**能对应到实际代码位置，如 `filename:line`、类型、函数、配置或调用链。
- 深入而克制：抓用户容易忽略的结构、边界、隐含状态、失败路径和风险；避免堆砌一眼可见的目录说明。
- 不确定的地方**必须**明确标注为“需要更多上下文”，**不能**把推测写成事实。

## 强制执行

- **强制背靠背验证**：交付前**必须**另起独立 sub-agent 验证分析产物；**不能**用当前 agent 自查替代。
  - **Mermaid 渲染校验**：sub-agent **必须**使用 Mermaid CLI (`mmdc`) 渲染报告中的每个 Mermaid 代码块；**任一图渲染失败都必须**修复并重新验证。
  - **代码证据校验**：sub-agent **必须**逐项核对关键结论、风险、`filename:line`、类型、函数、配置或调用链是否在项目中真实存在且语义一致。

## 开始前判断

- 如果用户给了明确范围和关注点，直接分析。
- 如果范围明确但关注点不明确，按代码类型自动选择默认维度，并在报告中说明选择理由。
- 如果代码可能跨仓库、依赖私有服务、缺少生成文件或运行时配置，先基于当前代码分析，再列出缺失上下文对结论的影响。
- 如果用户只要求某个维度，只输出该维度及必要风险，不补齐完整报告。

## 维度选择

### 通用维度

适用于大多数代码库，从中选择和目标最相关的维度：

- 核心逻辑流程：主路径、异常路径、异步/并发路径、状态转换。
- 数据结构与关系：模型、协议、接口、数据库表、配置结构、消息结构。
- 模块与源码组织：目录职责、模块边界、依赖方向、入口与扩展点。
- 运行时行为：启动、初始化、调度、缓存、持久化、网络/IO、错误恢复。
- 风险与改进：逻辑漏洞、边界条件、权限问题、状态污染、测试缺口、可维护性风险。

### 客户端 / iOS 代码

优先关注：

- 用户流程与页面状态：页面进入、事件响应、导航、加载/空态/错误态。
- View / ViewModel / Service / Repository 的职责边界和数据流。
- 本地状态、缓存、网络请求、持久化和生命周期。
- UI 线程、异步任务、取消、重入、资源释放。

常用 Mermaid：`flowchart`、`sequenceDiagram`、`stateDiagram`、`classDiagram`、`mindmap`。

### Agent / Runtime 代码

优先关注：

- Agent Loop：planning、proposal、tool selection、execution、observation、reflection、next step。
- Memory：短期/长期记忆、写入时机、召回策略、压缩/摘要、隔离边界、污染风险。
- Knowledge：文档加载、索引、检索、rerank、context injection、引用与过期策略。
- Tools：tool registry、schema、权限、调用链、side effect、错误恢复、重试/回滚。
- Proposal / Planning：候选方案生成、评估、采纳、拒绝、执行、状态推进。
- State & Context：session state、conversation state、runtime state、持久化边界、上下文预算。
- Policy & Safety：权限边界、prompt injection、tool misuse、跨会话泄漏、不可证实状态。

常用 Mermaid：`flowchart`、`sequenceDiagram`、`stateDiagram`、`classDiagram`、`erDiagram`、`mindmap`。

### 后端 / 服务端代码

优先关注：

- 请求链路、鉴权、业务编排、事务边界、幂等与并发。
- 数据模型、数据库关系、缓存、消息队列、外部服务依赖。
- 错误处理、重试、降级、观测性和运维入口。

常用 Mermaid：`sequenceDiagram`、`flowchart`、`erDiagram`、`C4Context`、`C4Container`。

### SDK / Library / CLI 代码

优先关注：

- Public API、调用约定、配置入口、扩展点、兼容性边界。
- 内部抽象、错误模型、资源生命周期、可测试性。
- CLI 参数解析、命令分发、环境依赖、文件/网络副作用。

常用 Mermaid：`flowchart`、`classDiagram`、`sequenceDiagram`、`mindmap`。

## Mermaid 使用要求

- Mermaid 图必须放在 fenced code block 中：```` ```mermaid ````；这行前面必须保留一个空行，避免 Markdown 解析异常。
- 图节点使用真实领域名词，避免 `step1`、`manager`、`helper` 这类泛称。
- 图只表达关键结构，不把大段代码塞进节点。
- 如果一种图不能解释清楚，拆成多张小图；不要做一张过大的万能图。
- 每个 Mermaid 图都必须能被 Mermaid CLI 渲染，例如 `mmdc -i input.mmd -o output.svg` 或 `npx -p @mermaid-js/mermaid-cli mmdc -i input.mmd -o output.svg`。
- 优先选择最贴近问题的图：
  - 流程/分支：`flowchart`
  - 调用交互：`sequenceDiagram`
  - 状态推进：`stateDiagram-v2`
  - 类型/协议关系：`classDiagram`
  - 数据库/实体关系：`erDiagram`
  - 模块地图：`mindmap`
  - 系统边界：C4 Mermaid

## 输出格式

根据实际分析维度裁剪章节，不必强行保留所有小节。

````md
## [目标代码] - 代码剖析

### 概览

[一句话说明目标代码的职责和分析范围]

### 维度选择

[说明本次选择了哪些维度，以及为什么这些维度最能解释当前代码]

### [维度一名称]

```mermaid
flowchart TD
    CodeScope[目标代码范围] --> Finding[关键分析结论]
```

[简短说明图中关键路径、边界或状态；引用关键代码位置]

### [维度二名称]

```mermaid
sequenceDiagram
    participant Caller as 调用方
    participant Target as 被分析模块
    Caller->>Target: 关键调用
    Target-->>Caller: 关键结果
```

[简短说明图中关键结构；引用关键代码位置]

### 风险与改进建议

[按严重程度 P0 > P1 > P2 排列。只列基于实际代码可证实的风险；若未发现明确风险，写「未发现基于当前代码可证实的核心风险」。]

| 级别 | 问题 | 证据 | 影响 | 建议 |
| --- | --- | --- | --- | --- |
| P0/P1/P2 | [一句话说明问题] | [filename:line 或具体类型/函数] | [触发条件和影响] | [可执行的解决方式] |

### 需要更多上下文

[可选。只列确实影响结论的缺失信息，例如跨仓库依赖、运行时配置、生成代码、线上策略。]
````

## 背靠背验证

提交报告前必须完成独立 sub-agent 验证，不能由当前 agent 自查替代。

### 验证输入

给 sub-agent 提供：

- 待交付的完整 Markdown 分析报告。
- 目标代码范围和仓库路径。
- 明确要求其不要复用当前 agent 的判断，只基于报告和代码做独立核对。

### 验证要求

sub-agent 必须检查：

- Markdown 中每个 Mermaid fenced block 前是否有空行。
- 每个 Mermaid block 是否可单独提取为 `.mmd` 并通过 Mermaid CLI (`mmdc`) 渲染为 SVG；失败时返回具体错误和对应图。
- 报告中的每个关键结论是否能在代码中找到证据。
- 所有 `filename:line`、类型、函数、配置、调用链是否真实存在，且被报告正确解释。
- 风险是否基于实际代码，而不是泛泛而谈或脱离上下文的猜测。
- 不确定内容是否被放入“需要更多上下文”，而不是当作确定结论。

### 失败处理

- 如果 Mermaid 渲染失败，先修 Mermaid，再重新让 sub-agent 验证。
- 如果代码证据不成立，删除或修正对应结论，再重新让 sub-agent 验证。
- 如果当前环境缺少 Mermaid CLI，必须先尝试使用 `npx -p @mermaid-js/mermaid-cli mmdc ...`；如果因网络或权限不可用，报告中明确说明未完成强制验证及原因，不能声称验证通过。
- 只有 sub-agent 返回 Mermaid 渲染和代码证据均通过后，才能交付最终报告。
