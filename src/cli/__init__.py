"""CLI intake layer for Agentic CRM."""

from src.cli.intake import (
    format_task_output,
    main,
    run_cli,
    submit_task,
)
from src.cli.parser import (
    build_parser,
    parse_args,
)

__all__ = [
    "build_parser",
    "format_task_output",
    "main",
    "parse_args",
    "run_cli",
    "submit_task",
]
