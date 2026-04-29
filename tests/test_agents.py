from __future__ import annotations

from pathlib import Path

from repo_agents.orchestrator import AuditOrchestrator


def test_auditor_detects_todo_and_missing_tests(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def run():\n    pass  # TODO: implement\n", encoding="utf-8")

    orchestrator = AuditOrchestrator(root=tmp_path)
    orchestrator.run()

    titles = [finding.title for finding in orchestrator.context.all_findings]
    assert "遗留待办标记" in titles
    assert "未检测到测试" in titles


def test_report_contains_roadmap(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")

    orchestrator = AuditOrchestrator(root=tmp_path)
    orchestrator.run()
    report = orchestrator.markdown()

    assert "# 多智能体代码库审计报告" in report
    assert "## 行动路线图" in report
    assert "FileScoutAgent" in report
