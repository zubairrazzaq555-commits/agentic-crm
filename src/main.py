"""Agentic CRM — Main command-line application entrypoint.

Allows developers and automation workflows to submit tasks into the
persistent task queue and hierarchical agent orchestration pipeline.

Usage:
    python -m src.main "Qualify lead John Doe"
    python -m src.main "Qualify lead John Doe" --json
    python -m src.main "Quarterly forecast" -t opportunity_forecast
    python -m src.main "Export contacts" -t data_export_csv -p '{"format": "csv"}'
"""

import sys
from src.cli.intake import main

if __name__ == "__main__":
    sys.exit(main())
