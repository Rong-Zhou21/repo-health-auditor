from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import AuditOrchestrator


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        help_text = super().format_help()
        return (
            help_text.replace("usage:", "用法：")
            .replace("options:", "选项：")
            .replace("show this help message and exit", "显示帮助信息并退出。")
        )


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(
        prog="repo-auditor",
        description="对本地代码库运行轻量健康巡检。",
    )
    parser.add_argument("--path", default=".", help="要审计的仓库路径，默认是当前目录。")
    parser.add_argument("--out", default="audit-report.md", help="Markdown 报告输出路径。")
    parser.add_argument("--json", dest="json_out", default=None, help="可选的 JSON 报告输出路径。")
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=512_000,
        help="大于该字节数的文件会被标记为超大文件，并跳过文本扫描。",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="通过 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL 启用可选的模型总结。",
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

    print(f"审计完成：{out_path}")
    if args.json_out:
        print(f"JSON 报告：{args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
