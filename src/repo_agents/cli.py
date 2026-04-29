from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import AuditOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a lightweight multi-agent audit over a local code repository.",
    )
    parser.add_argument("--path", default=".", help="Repository path to audit. Defaults to current directory.")
    parser.add_argument("--out", default="audit-report.md", help="Markdown report output path.")
    parser.add_argument("--json", dest="json_out", default=None, help="Optional JSON report output path.")
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=512_000,
        help="Files larger than this are listed as large files and skipped for text scanning.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable optional OpenAI-compatible LLM summary via AI_BASE_URL, AI_API_KEY, and AI_MODEL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    orchestrator = AuditOrchestrator(
        root=Path(args.path),
        max_file_bytes=args.max_file_bytes,
        use_llm=args.use_llm,
    )
    orchestrator.run()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(orchestrator.markdown(), encoding="utf-8")

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(orchestrator.json_payload(), encoding="utf-8")

    print(f"Audit complete: {out_path}")
    if args.json_out:
        print(f"JSON report: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

