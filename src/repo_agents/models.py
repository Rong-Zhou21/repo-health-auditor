from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    severity: str
    title: str
    detail: str
    path: str | None = None
    line: int | None = None
    agent: str = "unknown"

    def sort_key(self) -> tuple[int, str]:
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
        return (severity_order.get(self.severity, 99), self.title)


@dataclass
class AgentResult:
    agent: str
    summary: str
    observations: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditContext:
    root: Path
    max_file_bytes: int
    ignored_dirs: set[str]
    results: list[AgentResult] = field(default_factory=list)

    def add_result(self, result: AgentResult) -> None:
        self.results.append(result)

    @property
    def all_findings(self) -> list[Finding]:
        findings: list[Finding] = []
        for result in self.results:
            findings.extend(result.findings)
        return sorted(findings, key=lambda item: item.sort_key())

