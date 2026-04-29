from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import AuditContext


def render_markdown_report(context: AuditContext) -> str:
    lines: list[str] = []
    lines.append("# 代码库健康巡检报告")
    lines.append("")
    lines.append(f"- 仓库路径：`{display_path(context.root)}`")
    lines.append(f"- 生成时间：`{datetime.now(timezone.utc).isoformat(timespec='seconds')}`")
    lines.append(f"- 参与模块：`{', '.join(result.agent for result in context.results)}`")
    lines.append("")

    file_result = next((result for result in context.results if result.agent == "FileScoutAgent"), None)
    if file_result:
        lines.append("## 仓库概览")
        lines.append("")
        lines.append(f"- 已扫描文件数：`{file_result.data.get('file_count', 0)}`")
        languages = file_result.data.get("languages", {})
        if languages:
            lines.append("- 语言和配置分布：")
            for language, count in list(languages.items())[:10]:
                lines.append(f"  - {language}: `{count}`")
        key_files = file_result.data.get("key_files", [])
        if key_files:
            lines.append("- 关键文件：")
            for item in key_files[:15]:
                lines.append(f"  - `{item}`")
        lines.append("")

    lines.append("## 风险发现")
    lines.append("")
    findings = context.all_findings
    if not findings:
        lines.append("未发现风险项。")
    else:
        for finding in findings:
            location = ""
            if finding.path:
                location = f" (`{finding.path}`"
                if finding.line:
                    location += f":{finding.line}"
                location += ")"
            lines.append(f"- **{translate_severity(finding.severity)}** {finding.title}{location}：{finding.detail}")
    lines.append("")

    test_result = next((result for result in context.results if result.agent == "TestStrategistAgent"), None)
    if test_result:
        lines.append("## 测试策略")
        lines.append("")
        commands = test_result.data.get("commands", [])
        if commands:
            lines.append("建议运行命令：")
            for command in commands:
                lines.append(f"- `{command}`")
        else:
            lines.append("未推断出标准测试命令。")
        test_files = test_result.data.get("test_files", [])
        lines.append(f"检测到的疑似测试文件数：`{len(test_files)}`")
        lines.append("")

    roadmap_result = next((result for result in context.results if result.agent == "RoadmapAgent"), None)
    if roadmap_result:
        lines.append("## 行动路线图")
        lines.append("")
        for item in roadmap_result.data.get("roadmap", []):
            lines.append(f"- {item}")
        lines.append("")

    llm_result = next((result for result in context.results if result.agent == "LLMSummarizerAgent"), None)
    if llm_result:
        lines.append("## 大模型总结")
        lines.append("")
        lines.append(llm_result.observations[0] if llm_result.observations else llm_result.summary)
        lines.append("")

    lines.append("## 巡检轨迹")
    lines.append("")
    for result in context.results:
        lines.append(f"### {result.agent}")
        lines.append("")
        lines.append(result.summary)
        lines.append("")
        for observation in result.observations:
            lines.append(f"- {observation}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def translate_severity(severity: str) -> str:
    return {
        "HIGH": "高风险",
        "MEDIUM": "中风险",
        "LOW": "低风险",
        "INFO": "信息",
    }.get(severity, severity)
