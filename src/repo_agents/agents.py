from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Iterable

from .models import AgentResult, AuditContext, Finding


LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".css": "CSS",
    ".html": "HTML",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


class BaseAgent:
    name = "BaseAgent"

    def run(self, context: AuditContext) -> AgentResult:
        raise NotImplementedError


def iter_repo_files(root: Path, ignored_dirs: set[str], max_file_bytes: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & ignored_dirs:
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                yield path
                continue
        except OSError:
            continue
        yield path


def safe_read_text(path: Path, max_chars: int = 80_000) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:1024]:
        return None
    try:
        return data[:max_chars].decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data[:max_chars].decode("latin-1")
        except UnicodeDecodeError:
            return None


class FileScoutAgent(BaseAgent):
    name = "FileScoutAgent"

    def run(self, context: AuditContext) -> AgentResult:
        files = list(iter_repo_files(context.root, context.ignored_dirs, context.max_file_bytes))
        language_counter: Counter[str] = Counter()
        large_files: list[tuple[str, int]] = []
        empty_files: list[str] = []
        key_files: list[str] = []

        key_names = {
            "README.md",
            "pyproject.toml",
            "package.json",
            "go.mod",
            "Cargo.toml",
            "pom.xml",
            "build.gradle",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
            ".github",
        }

        for file_path in files:
            rel = file_path.relative_to(context.root).as_posix()
            suffix = file_path.suffix.lower()
            language_counter[LANGUAGE_BY_SUFFIX.get(suffix, "Other")] += 1
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            if size == 0:
                empty_files.append(rel)
            if size > context.max_file_bytes:
                large_files.append((rel, size))
            if file_path.name in key_names or rel.startswith(".github/"):
                key_files.append(rel)

        findings: list[Finding] = []
        if not (context.root / "README.md").exists():
            findings.append(
                Finding(
                    severity="MEDIUM",
                    title="Missing README",
                    detail="Repository lacks README.md, which makes onboarding and agent handoff harder.",
                    agent=self.name,
                )
            )

        for rel in empty_files[:10]:
            findings.append(
                Finding(
                    severity="LOW",
                    title="Empty file",
                    detail="Empty files often indicate unfinished work or stale placeholders.",
                    path=rel,
                    agent=self.name,
                )
            )

        observations = [
            f"Scanned {len(files)} files under {display_path(context.root)}.",
            "Top languages: "
            + ", ".join(f"{name}={count}" for name, count in language_counter.most_common(5)),
            f"Detected {len(key_files)} key project/config files.",
        ]

        return AgentResult(
            agent=self.name,
            summary=f"Mapped {len(files)} files and {len(language_counter)} language/config categories.",
            observations=observations,
            findings=findings,
            data={
                "file_count": len(files),
                "languages": dict(language_counter.most_common()),
                "large_files": large_files[:20],
                "key_files": sorted(key_files)[:50],
            },
        )


class RiskAnalystAgent(BaseAgent):
    name = "RiskAnalystAgent"

    def run(self, context: AuditContext) -> AgentResult:
        findings: list[Finding] = []
        scanned_text_files = 0
        todo_count = 0
        secret_hits = 0

        for file_path in iter_repo_files(context.root, context.ignored_dirs, context.max_file_bytes):
            rel = file_path.relative_to(context.root).as_posix()
            try:
                size = file_path.stat().st_size
            except OSError:
                continue

            if size > context.max_file_bytes:
                findings.append(
                    Finding(
                        severity="MEDIUM",
                        title="Large file skipped",
                        detail=f"File is {size} bytes, which may slow reviews and agent context loading.",
                        path=rel,
                        agent=self.name,
                    )
                )
                continue

            text = safe_read_text(file_path)
            if text is None:
                continue
            scanned_text_files += 1
            for line_no, line in enumerate(text.splitlines(), start=1):
                if TODO_PATTERN.search(line):
                    todo_count += 1
                    if todo_count <= 25:
                        findings.append(
                            Finding(
                                severity="LOW",
                                title="Deferred work marker",
                                detail=line.strip()[:180],
                                path=rel,
                                line=line_no,
                                agent=self.name,
                            )
                        )
                for pattern in SECRET_PATTERNS:
                    if pattern.search(line):
                        secret_hits += 1
                        findings.append(
                            Finding(
                                severity="HIGH",
                                title="Possible secret in source",
                                detail="A line matches a common secret/token pattern. Rotate it if real and move it to environment-backed config.",
                                path=rel,
                                line=line_no,
                                agent=self.name,
                            )
                        )

        observations = [
            f"Scanned {scanned_text_files} text files for maintainability and security signals.",
            f"Found {todo_count} TODO/FIXME/HACK markers.",
            f"Found {secret_hits} possible secret exposures.",
        ]
        severity_counts = Counter(finding.severity for finding in findings)

        return AgentResult(
            agent=self.name,
            summary=f"Identified {len(findings)} risk findings across the repository.",
            observations=observations,
            findings=findings,
            data={"severity_counts": dict(severity_counts), "todo_count": todo_count, "secret_hits": secret_hits},
        )


class TestStrategistAgent(BaseAgent):
    name = "TestStrategistAgent"

    def run(self, context: AuditContext) -> AgentResult:
        files = list(iter_repo_files(context.root, context.ignored_dirs, context.max_file_bytes))
        rel_files = [path.relative_to(context.root).as_posix() for path in files]
        test_files = [
            rel for rel in rel_files if "/test" in f"/{rel.lower()}" or rel.lower().startswith("test_") or "_test." in rel
        ]
        commands: list[str] = []

        if (context.root / "pyproject.toml").exists() or (context.root / "requirements.txt").exists():
            commands.append("python -m pytest")
        if (context.root / "package.json").exists():
            commands.append("npm test")
        if (context.root / "go.mod").exists():
            commands.append("go test ./...")
        if (context.root / "Cargo.toml").exists():
            commands.append("cargo test")
        if (context.root / "pom.xml").exists():
            commands.append("mvn test")

        findings: list[Finding] = []
        source_like = [
            rel
            for rel in rel_files
            if Path(rel).suffix.lower() in {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".kt"}
            and "/test" not in f"/{rel.lower()}"
        ]
        if source_like and not test_files:
            findings.append(
                Finding(
                    severity="MEDIUM",
                    title="No tests detected",
                    detail="Source files exist, but no obvious test files or test directories were found.",
                    agent=self.name,
                )
            )
        if source_like and not commands:
            findings.append(
                Finding(
                    severity="LOW",
                    title="No test command inferred",
                    detail="No standard project metadata was found for inferring an automated test command.",
                    agent=self.name,
                )
            )

        observations = [
            f"Detected {len(test_files)} likely test files.",
            "Inferred test commands: " + (", ".join(commands) if commands else "none"),
            f"Detected {len(source_like)} source-like files.",
        ]

        return AgentResult(
            agent=self.name,
            summary=f"Built a test strategy from {len(test_files)} test files and {len(commands)} inferred commands.",
            observations=observations,
            findings=findings,
            data={"test_files": test_files[:50], "commands": commands, "source_like_file_count": len(source_like)},
        )


class RoadmapAgent(BaseAgent):
    name = "RoadmapAgent"

    def run(self, context: AuditContext) -> AgentResult:
        previous_findings = context.all_findings
        high = [finding for finding in previous_findings if finding.severity == "HIGH"]
        medium = [finding for finding in previous_findings if finding.severity == "MEDIUM"]
        low = [finding for finding in previous_findings if finding.severity == "LOW"]

        roadmap: list[str] = []
        if high:
            roadmap.append("P0: Review and remove possible secrets, then rotate affected credentials.")
        if any(finding.title == "No tests detected" for finding in previous_findings):
            roadmap.append("P1: Add smoke tests for core workflows before major refactoring.")
        if any(finding.title == "Missing README" for finding in previous_findings):
            roadmap.append("P1: Add README with setup, test, and contribution instructions.")
        if medium:
            roadmap.append("P2: Triage medium-risk maintenance issues and split oversized files where practical.")
        if low:
            roadmap.append("P3: Convert TODO/FIXME markers into tracked issues or remove stale comments.")
        if not roadmap:
            roadmap.append("P2: Repository health looks stable; schedule periodic automated audits in CI.")

        observations = [
            f"Consumed {len(context.results)} previous Agent outputs.",
            f"Prioritized {len(high)} high, {len(medium)} medium, and {len(low)} low severity findings.",
            f"Generated {len(roadmap)} action items.",
        ]

        return AgentResult(
            agent=self.name,
            summary="Synthesized previous Agent outputs into an actionable engineering roadmap.",
            observations=observations,
            data={"roadmap": roadmap},
        )


class LLMSummarizerAgent(BaseAgent):
    name = "LLMSummarizerAgent"

    def run(self, context: AuditContext) -> AgentResult:
        base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
        api_key = os.getenv("AI_API_KEY", "")
        model = os.getenv("AI_MODEL", "")
        if not base_url or not api_key or not model:
            return AgentResult(
                agent=self.name,
                summary="Skipped LLM summary because AI_BASE_URL, AI_API_KEY, or AI_MODEL is not configured.",
                observations=["Deterministic audit results remain available."],
            )

        prompt = build_llm_prompt(context)
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a senior engineering manager. Summarize repository audit results in concise Chinese.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            return AgentResult(
                agent=self.name,
                summary="LLM summary failed; deterministic audit completed successfully.",
                observations=[f"Error: {exc}"],
            )

        content = payload["choices"][0]["message"]["content"].strip()
        return AgentResult(
            agent=self.name,
            summary="Generated an executive summary with the configured OpenAI-compatible model.",
            observations=[content],
            data={"model": model},
        )


def build_llm_prompt(context: AuditContext) -> str:
    compact_results = []
    for result in context.results:
        compact_results.append(
            {
                "agent": result.agent,
                "summary": result.summary,
                "observations": result.observations[:5],
                "findings": [
                    {
                        "severity": finding.severity,
                        "title": finding.title,
                        "path": finding.path,
                        "line": finding.line,
                    }
                    for finding in result.findings[:10]
                ],
            }
        )
    return json.dumps(compact_results, ensure_ascii=False, indent=2)
