#!/usr/bin/env python3
"""CLI entry point for Claude Code insights commands.

Usage:
    claude-insights                # Default: today's overview
    claude-insights tools          # Tool/MCP usage analysis
    claude-insights cache          # Cache efficiency analysis
    claude-insights anomalies      # Loop/spike detection
    claude-insights skills         # Skill performance
    claude-insights predict        # Usage forecasting
    claude-insights roi            # ROI/value analysis
    claude-insights full           # Comprehensive report

Options:
    --days N         Analyze last N days (default: 1)
    --date YYYY-MM-DD  Analyze specific date
    --json           Output as JSON
"""

import argparse
import sys
from typing import List, Optional

from .report import run_insights_command


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for claude-insights CLI."""
    parser = argparse.ArgumentParser(
        prog="claude-insights",
        description="Deep insights into Claude Code token usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-insights                  # Today's overview
  claude-insights tools            # Tool usage breakdown
  claude-insights anomalies        # Detect loops and spikes
  claude-insights --days 7 full    # Full week analysis
  claude-insights --date 2025-12-28 anomalies  # Specific date
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="anomalies",
        choices=["tools", "cache", "anomalies", "skills", "predict", "roi", "full"],
        help="Analysis type (default: anomalies)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Days to analyze (default: 1 = today)",
    )

    parser.add_argument(
        "--date",
        type=str,
        help="Specific date to analyze (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted report",
    )

    parser.add_argument(
        "--path",
        type=str,
        help="Path to Claude data directory (default: ~/.claude/projects)",
    )

    args = parser.parse_args(argv)

    print(f"\nAnalyzing Claude Code logs ({args.command})...")

    return run_insights_command(
        command=args.command,
        days_back=args.days,
        target_date=args.date,
        output_json=args.json,
        data_path=args.path,
    )


if __name__ == "__main__":
    sys.exit(main())
