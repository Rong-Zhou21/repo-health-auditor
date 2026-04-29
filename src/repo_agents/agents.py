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
            language_counter[LANGUAGE_BY_SUFFIX.get(suffix, "其他")] += 1
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
                    title="缺少 README",
                    detail="仓库缺少 README.md，会增加新人接手和智能体交接的成本。",
                    agent=self.name,
                )
            )

        for rel in empty_files[:10]:
            findings.append(
                Finding(
                    severity="LOW",
                    title="空文件",
                    detail="空文件通常意味着未完成的工作或已经过期的占位文件。",
                    path=rel,
                    agent=self.name,
                )
            )

        observations = [
            f"已扫描 {display_path(context.root)} 下的 {len(files)} 个文件。",
            "主要语言和配置类型："
            + ", ".join(f"{name}={count}" for name, count in language_counter.most_common(5)),
            f"识别到 {len(key_files)} 个关键项目或配置文件。",
        ]

        return AgentResult(
            agent=self.name,
            summary=f"已映射 {len(files)} 个文件和 {len(language_counter)} 类语言或配置。",
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
                        title="跳过超大文件",
                        detail=f"文件大小为 {size} 字节，可能拖慢代码审查和智能体上下文加载。",
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
                                title="遗留待办标记",
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
                                title="源码中可能存在密钥",
                                detail="该行匹配常见密钥或令牌模式；如果是真实凭据，应立即轮换并迁移到环境变量或密钥管理系统。",
                                path=rel,
                                line=line_no,
                                agent=self.name,
                            )
                        )

        observations = [
            f"已扫描 {scanned_text_files} 个文本文件中的可维护性和安全信号。",
            f"发现 {todo_count} 个 TODO/FIXME/HACK 标记。",
            f"发现 {secret_hits} 处疑似密钥暴露。",
        ]
        severity_counts = Counter(finding.severity for finding in findings)

        return AgentResult(
            agent=self.name,
            summary=f"在仓库中识别到 {len(findings)} 条风险发现。",
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
                    title="未检测到测试",
                    detail="仓库存在源码文件，但没有发现明显的测试文件或测试目录。",
                    agent=self.name,
                )
            )
        if source_like and not commands:
            findings.append(
                Finding(
                    severity="LOW",
                    title="未推断出测试命令",
                    detail="未发现可用于推断自动化测试命令的标准项目元数据。",
                    agent=self.name,
                )
            )

        observations = [
            f"检测到 {len(test_files)} 个疑似测试文件。",
            "推断出的测试命令：" + (", ".join(commands) if commands else "无"),
            f"检测到 {len(source_like)} 个疑似源码文件。",
        ]

        return AgentResult(
            agent=self.name,
            summary=f"基于 {len(test_files)} 个测试文件和 {len(commands)} 条推断命令生成测试策略。",
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
            roadmap.append("P0：检查并移除疑似密钥，随后轮换受影响的凭据。")
        if any(finding.title == "未检测到测试" for finding in previous_findings):
            roadmap.append("P1：在大规模重构前，为核心流程补充冒烟测试。")
        if any(finding.title == "缺少 README" for finding in previous_findings):
            roadmap.append("P1：补充 README，明确安装、测试和协作说明。")
        if medium:
            roadmap.append("P2：梳理中风险维护问题，并在合适时拆分超大文件。")
        if low:
            roadmap.append("P3：将 TODO/FIXME 标记转成可跟踪任务，或删除过期注释。")
        if not roadmap:
            roadmap.append("P2：仓库健康状况较稳定，建议在 CI 中定期运行自动审计。")

        observations = [
            f"已消费 {len(context.results)} 个前序智能体输出。",
            f"已按优先级整理 {len(high)} 条高风险、{len(medium)} 条中风险、{len(low)} 条低风险发现。",
            f"已生成 {len(roadmap)} 条行动项。",
        ]

        return AgentResult(
            agent=self.name,
            summary="已将前序智能体输出汇总为可执行的工程改进路线图。",
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
                summary="由于未配置 AI_BASE_URL、AI_API_KEY 或 AI_MODEL，已跳过大模型总结。",
                observations=["确定性审计结果仍然完整可用。"],
            )

        prompt = build_llm_prompt(context)
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一名资深工程管理者。请用简洁中文总结代码库审计结果。",
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
                summary="大模型总结失败；确定性审计已成功完成。",
                observations=[f"错误：{exc}"],
            )

        content = payload["choices"][0]["message"]["content"].strip()
        return AgentResult(
            agent=self.name,
            summary="已使用配置的兼容 OpenAI 接口模型生成管理者摘要。",
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
