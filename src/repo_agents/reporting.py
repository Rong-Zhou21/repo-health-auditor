from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import AuditContext


def render_markdown_report(context: AuditContext) -> str:
    lines: list[str] = []
    lines.append("# Agentic Repo Audit Report")
    lines.append("")
    lines.append(f"- Repository: `{display_path(context.root)}`")
    lines.append(f"- Generated: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`")
    lines.append(f"- Agents: `{', '.join(result.agent for result in context.results)}`")
    lines.append("")

    file_result = next((result for result in context.results if result.agent == "FileScoutAgent"), None)
    if file_result:
        lines.append("## Repository Overview")
        lines.append("")
        lines.append(f"- Files scanned: `{file_result.data.get('file_count', 0)}`")
        languages = file_result.data.get("languages", {})
        if languages:
            lines.append("- Language/config distribution:")
            for language, count in list(languages.items())[:10]:
                lines.append(f"  - {language}: `{count}`")
        key_files = file_result.data.get("key_files", [])
        if key_files:
            lines.append("- Key files:")
            for item in key_files[:15]:
                lines.append(f"  - `{item}`")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    findings = context.all_findings
    if not findings:
        lines.append("No findings detected by the deterministic agents.")
    else:
        for finding in findings:
            location = ""
            if finding.path:
                location = f" (`{finding.path}`"
                if finding.line:
                    location += f":{finding.line}"
                location += ")"
            lines.append(f"- **{finding.severity}** {finding.title}{location}: {finding.detail}")
    lines.append("")

    test_result = next((result for result in context.results if result.agent == "TestStrategistAgent"), None)
    if test_result:
        lines.append("## Test Strategy")
        lines.append("")
        commands = test_result.data.get("commands", [])
        if commands:
            lines.append("Suggested commands:")
            for command in commands:
                lines.append(f"- `{command}`")
        else:
            lines.append("No standard test command could be inferred.")
        test_files = test_result.data.get("test_files", [])
        lines.append(f"Likely test files detected: `{len(test_files)}`")
        lines.append("")

    roadmap_result = next((result for result in context.results if result.agent == "RoadmapAgent"), None)
    if roadmap_result:
        lines.append("## Action Roadmap")
        lines.append("")
        for item in roadmap_result.data.get("roadmap", []):
            lines.append(f"- {item}")
        lines.append("")

    llm_result = next((result for result in context.results if result.agent == "LLMSummarizerAgent"), None)
    if llm_result:
        lines.append("## LLM Summary")
        lines.append("")
        lines.append(llm_result.observations[0] if llm_result.observations else llm_result.summary)
        lines.append("")

    lines.append("## Agent Trace")
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
