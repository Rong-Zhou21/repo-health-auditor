from __future__ import annotations

import json
from pathlib import Path

from .agents import FileScoutAgent, LLMSummarizerAgent, RiskAnalystAgent, RoadmapAgent, TestStrategistAgent
from .models import AgentResult, AuditContext
from .reporting import render_markdown_report


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
}


class AuditOrchestrator:
    def __init__(
        self,
        root: Path,
        max_file_bytes: int = 512_000,
        ignored_dirs: set[str] | None = None,
        use_llm: bool = False,
    ) -> None:
        self.context = AuditContext(
            root=root.resolve(),
            max_file_bytes=max_file_bytes,
            ignored_dirs=ignored_dirs or DEFAULT_IGNORED_DIRS,
        )
        self.agents = [
            FileScoutAgent(),
            RiskAnalystAgent(),
            TestStrategistAgent(),
            RoadmapAgent(),
        ]
        if use_llm:
            self.agents.append(LLMSummarizerAgent())

    def run(self) -> list[AgentResult]:
        if not self.context.root.exists():
            raise FileNotFoundError(f"路径不存在：{self.context.root}")
        if not self.context.root.is_dir():
            raise NotADirectoryError(f"路径不是目录：{self.context.root}")

        for agent in self.agents:
            result = agent.run(self.context)
            self.context.add_result(result)
        return self.context.results

    def markdown(self) -> str:
        return render_markdown_report(self.context)

    def json_payload(self) -> str:
        payload = {
            "root": str(self.context.root),
            "results": [
                {
                    "agent": result.agent,
                    "summary": result.summary,
                    "observations": result.observations,
                    "findings": [finding.__dict__ for finding in result.findings],
                    "data": result.data,
                }
                for result in self.context.results
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
