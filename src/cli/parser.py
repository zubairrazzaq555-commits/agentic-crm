"""Command-line argument parser for the Agentic CRM intake layer."""

import argparse
from typing import List, Optional


def build_parser() -> argparse.ArgumentParser:
    """Construct and configure the CLI intake argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="agentic-crm",
        description="Agentic CRM — Command-line task intake and execution interface.",
    )

    parser.add_argument(
        "description",
        type=str,
        help="Task description or command (e.g. 'Qualify lead John Doe').",
    )

    parser.add_argument(
        "-t",
        "--task-type",
        type=str,
        default=None,
        help="Optional explicit task type (e.g. 'sales_lead_qualification'). Defaults to the description.",
    )

    parser.add_argument(
        "-p",
        "--payload",
        type=str,
        default=None,
        help="Optional JSON string carrying additional task payload attributes.",
    )

    parser.add_argument(
        "--priority",
        type=int,
        default=0,
        help="Integer priority for queue placement (higher executes first, default: 0).",
    )

    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Optional domain hint (e.g. 'sales', 'marketing').",
    )

    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output raw structured JSON result instead of human-readable text.",
    )

    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Optional override for the database URL.",
    )

    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from given list or sys.argv."""
    parser = build_parser()
    return parser.parse_args(argv)
