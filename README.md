# 多智能体代码库审计器

多智能体代码库审计器是一个轻量、可本地运行的代码库体检工具。它面向个人开发者和小团队的真实痛点：代码库增长后，技术债、测试缺口、文档缺失和潜在风险经常分散在不同文件里，人工体检成本高，也很难沉淀成可执行的改进计划。

项目内置 4 个协作 Agent：

1. `FileScoutAgent`：扫描代码库结构、语言分布、文件规模和关键配置。
2. `RiskAnalystAgent`：发现 TODO/FIXME、疑似密钥、超大文件、空文件等维护风险。
3. `TestStrategistAgent`：识别测试目录、测试文件、可运行测试命令和测试覆盖缺口。
4. `RoadmapAgent`：整合前序智能体的观察结果，生成按优先级排序的工程改进路线图。

可选的 `LLMSummarizerAgent` 支持兼容 OpenAI 接口的模型服务，可接入小米模型或其他兼容模型，对确定性审计结果做进一步总结。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
repo-auditor --path . --out audit-report.md --json audit-report.json
```

也可以直接运行模块：

```bash
python -m repo_agents.cli --path . --out audit-report.md
```

## 可选：接入兼容 OpenAI 接口的模型

设置环境变量后加 `--use-llm`：

```bash
export AI_BASE_URL="https://your-openai-compatible-endpoint/v1"
export AI_API_KEY="your-api-key"
export AI_MODEL="your-model-name"
repo-auditor --path . --out audit-report.md --use-llm
```

如果未配置 API，工具会自动跳过大模型总结，确定性多智能体审计仍可完整运行。

## 示例输出

报告会包含：

- 项目概览：文件数量、语言分布、最大文件、关键配置。
- 风险清单：按严重程度排序的潜在问题和证据。
- 测试策略：识别出的测试命令、缺口和建议。
- 行动计划：按优先级拆解的修复任务。
- 智能体轨迹：每个智能体产出的关键观察，便于复盘。

## 申请表可用描述

我构建了一个多智能体协同的代码库审计工具：多智能体代码库审计器。它解决的核心痛点是中小型项目在快速迭代后，技术债、测试缺口、文档缺失和潜在安全风险分散在代码库中，人工排查效率低且难以形成可执行路线图。

核心逻辑流包含 4 个专业智能体的长链协作：`FileScoutAgent` 首先扫描仓库结构、语言分布和关键配置；`RiskAnalystAgent` 基于扫描结果识别 TODO/FIXME、疑似密钥、超大文件等维护和安全风险；`TestStrategistAgent` 推断测试框架、可运行测试命令和覆盖缺口；最后 `RoadmapAgent` 汇总前序智能体的观察，生成按优先级排序的工程改进计划。项目还支持兼容 OpenAI 接口的模型服务，可接入小米模型作为 `LLMSummarizerAgent`，对确定性审计结果进行面向管理者的总结。

目前该项目可直接通过命令行对任意本地代码库生成 Markdown 和 JSON 审计报告，适合用于代码接手、重构前评估、PR 前自检和团队技术债治理。
