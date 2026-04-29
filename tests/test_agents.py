from __future__ import annotations

from pathlib import Path

from repo_agents.orchestrator import AuditOrchestrator


def test_auditor_detects_todo_and_missing_tests(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def run():\n    pass  # TODO: implement\n", encoding="utf-8")

    orchestrator = AuditOrchestrator(root=tmp_path)
    orchestrator.run()

    titles = [finding.title for finding in orchestrator.context.all_findings]
    assert "Deferred work marker" in titles
    assert "No tests detected" in titles


def test_report_contains_roadmap(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")

    orchestrator = AuditOrchestrator(root=tmp_path)
    orchestrator.run()
    report = orchestrator.markdown()

    assert "# Agentic Repo Audit Report" in report
    assert "## Action Roadmap" in report
    assert "FileScoutAgent" in report

