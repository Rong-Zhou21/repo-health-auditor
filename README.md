# 代码库健康巡检器

代码库健康巡检器是一个轻量、可本地运行的代码库体检工具。它面向个人开发者和小团队的日常维护场景：代码库增长后，技术债、测试缺口、文档缺失和潜在风险经常分散在不同文件里，人工排查成本高，也很难沉淀成可执行的改进计划。

项目内置 4 个协作模块：

1. `FileScoutAgent`：扫描代码库结构、语言分布、文件规模和关键配置。
2. `RiskAnalystAgent`：发现 TODO/FIXME、疑似密钥、超大文件、空文件等维护风险。
3. `TestStrategistAgent`：识别测试目录、测试文件、可运行测试命令和测试覆盖缺口。
4. `RoadmapAgent`：整合前序检查结果，生成按优先级排序的工程改进路线图。

可选的 `LLMSummarizerAgent` 支持兼容 OpenAI 接口的模型服务，可对确定性审计结果做进一步总结。

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

## 可选：接入模型总结

设置环境变量后加 `--use-llm`：

```bash
export LLM_BASE_URL="https://your-openai-compatible-endpoint/v1"
export LLM_API_KEY="your-api-key"
export LLM_MODEL="your-model-name"
repo-auditor --path . --out audit-report.md --use-llm
```

如果未配置模型服务，工具会自动跳过模型总结，基础巡检仍可完整运行。

## 示例输出

报告会包含：

- 项目概览：文件数量、语言分布、最大文件、关键配置。
- 风险清单：按严重程度排序的潜在问题和证据。
- 测试策略：识别出的测试命令、缺口和建议。
- 行动计划：按优先级拆解的修复任务。
- 巡检轨迹：每个模块产出的关键观察，便于复盘。

## 使用场景

- 接手一个陌生仓库时，快速了解项目结构和风险点。
- 重构前做一次轻量体检，先补齐测试和文档缺口。
- PR 前本地自检，提前发现疑似密钥、过期 TODO 和维护风险。
- 定期生成 Markdown 或 JSON 报告，用于团队技术债治理。
