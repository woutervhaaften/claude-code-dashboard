"""Combined insights report generator.

Combines all analyzers into comprehensive reports.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .tool_analyzer import ToolAnalyzer
from .cache_analyzer import CacheAnalyzer
from .anomaly_detector import AnomalyDetector
from .skill_analyzer import SkillAnalyzer
from .predictor import UsagePredictor
from .roi_analyzer import ROIAnalyzer
from .base import format_tokens, format_cost

logger = logging.getLogger(__name__)


class InsightsReport:
    """Generates comprehensive insights reports."""

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path
        self.tool_analyzer = ToolAnalyzer(data_path)
        self.cache_analyzer = CacheAnalyzer(data_path)
        self.anomaly_detector = AnomalyDetector(data_path)
        self.skill_analyzer = SkillAnalyzer(data_path)
        self.predictor = UsagePredictor(data_path)
        self.roi_analyzer = ROIAnalyzer(data_path)

    def generate_full_report(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a comprehensive report with all analyses.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with all analysis results
        """
        return {
            "tools": self.tool_analyzer.analyze(days_back, target_date),
            "cache": self.cache_analyzer.analyze(days_back, target_date),
            "anomalies": self.anomaly_detector.analyze(days_back, target_date),
            "skills": self.skill_analyzer.analyze(days_back, target_date),
            "predictions": self.predictor.analyze(days_back=max(30, days_back)),
            "roi": self.roi_analyzer.analyze(days_back, target_date),
        }

    def print_full_report(self, data: Dict[str, Any]) -> None:
        """Print comprehensive report."""
        # Header
        print("\n" + "=" * 100)
        print("  " + "=" * 96)
        print("  ||" + " " * 35 + "CLAUDE CODE INSIGHTS" + " " * 37 + "||")
        print("  ||" + " " * 32 + "COMPREHENSIVE ANALYSIS" + " " * 36 + "||")
        print("  " + "=" * 96)
        print("=" * 100)

        # Executive Summary
        self._print_executive_summary(data)

        # Tool Analysis
        print("\n\n")
        self.tool_analyzer.print_report(data["tools"])

        # Cache Analysis
        print("\n\n")
        self.cache_analyzer.print_report(data["cache"])

        # Anomaly Detection
        print("\n\n")
        self.anomaly_detector.print_report(data["anomalies"])

        # Skill Analysis
        print("\n\n")
        self.skill_analyzer.print_report(data["skills"])

        # Predictions
        print("\n\n")
        self.predictor.print_report(data["predictions"])

        # ROI Analysis
        print("\n\n")
        self.roi_analyzer.print_report(data["roi"])

        # Final recommendations
        self._print_combined_recommendations(data)

    def _print_executive_summary(self, data: Dict[str, Any]) -> None:
        """Print executive summary section."""
        print("\n\n  EXECUTIVE SUMMARY")
        print("  " + "-" * 96)

        # Key metrics
        tools = data["tools"]["summary"]
        cache = data["cache"]["overall"]
        anomalies = data["anomalies"]["summary"]
        predictions = data["predictions"]["forecast"]

        print(f"\n  KEY METRICS")
        print(f"  {'-'*50}")
        print(f"  Total Sessions:          {tools['total_sessions']:>10}")
        print(f"  Total Output Tokens:     {format_tokens(tools['total_output_tokens']):>10}")
        print(f"  Total Cost:              {format_cost(tools['total_cost']):>10}")
        print(f"  Cache Hit Rate:          {cache['cache_hit_rate']:>9.1f}%")
        print(f"  Anomalies Detected:      {anomalies['total_anomalies']:>10}")

        # Health indicators
        print(f"\n  HEALTH INDICATORS")
        print(f"  {'-'*50}")

        # Cache health
        cache_health = "GOOD" if cache["cache_hit_rate"] > 60 else "NEEDS ATTENTION"
        cache_symbol = "✓" if cache_health == "GOOD" else "!"
        print(f"  [{cache_symbol}] Cache Efficiency: {cache_health}")

        # Anomaly health
        anomaly_rate = anomalies["anomaly_rate"]
        anomaly_health = "GOOD" if anomaly_rate < 10 else "WARNING" if anomaly_rate < 25 else "CRITICAL"
        anomaly_symbol = "✓" if anomaly_health == "GOOD" else "!" if anomaly_health == "WARNING" else "X"
        print(f"  [{anomaly_symbol}] Anomaly Rate: {anomaly_health} ({anomaly_rate:.1f}%)")

        # Trend
        trend = data["predictions"]["trends"]["direction"]
        trend_symbol = "↑" if trend == "increasing" else "↓" if trend == "decreasing" else "→"
        print(f"  [{trend_symbol}] Usage Trend: {trend.upper()}")

        # Forecast
        print(f"\n  7-DAY FORECAST")
        print(f"  {'-'*50}")
        print(f"  Projected Sessions:      {predictions['projected_sessions']:>10}")
        print(f"  Projected Cost:          {format_cost(predictions['projected_cost']):>10}")
        print(f"  Confidence:              {predictions['confidence'].upper():>10}")

    def _print_combined_recommendations(self, data: Dict[str, Any]) -> None:
        """Print combined recommendations from all analyses."""
        print("\n\n" + "=" * 100)
        print("  TOP RECOMMENDATIONS")
        print("=" * 100)

        all_recs: List[str] = []

        # Collect high-priority recommendations
        if data["anomalies"]["by_severity"]["high"]:
            all_recs.append(
                f"[CRITICAL] {len(data['anomalies']['by_severity']['high'])} high-severity anomalies detected. "
                f"Review immediately."
            )

        for rec in data["anomalies"]["recommendations"][:2]:
            if "circuit breaker" in rec.lower() or "sql" in rec.lower():
                all_recs.append(f"[HIGH] {rec}")

        for rec in data["cache"]["recommendations"][:2]:
            if "low cache" in rec.lower():
                all_recs.append(f"[MEDIUM] {rec}")

        for rec in data["tools"]["recommendations"][:2]:
            all_recs.append(f"[MEDIUM] {rec}")

        for rec in data["predictions"]["recommendations"][:1]:
            all_recs.append(f"[INFO] {rec}")

        # Print unique recommendations
        seen = set()
        for rec in all_recs[:8]:
            if rec not in seen:
                print(f"\n  {rec}")
                seen.add(rec)

        print("\n" + "=" * 100)
        print("  TIP: Run individual reports for detailed analysis:")
        print("    claude-insights tools     - Tool usage breakdown")
        print("    claude-insights cache     - Cache efficiency")
        print("    claude-insights anomalies - Loop detection")
        print("    claude-insights skills    - Skill performance")
        print("    claude-insights predict   - Usage forecast")
        print("    claude-insights roi       - Value analysis")
        print("=" * 100 + "\n")


def run_insights_command(
    command: str,
    days_back: int = 7,
    target_date: Optional[str] = None,
    output_json: bool = False,
    data_path: Optional[str] = None,
) -> int:
    """Run insights command and print report.

    Args:
        command: Subcommand (tools, cache, anomalies, skills, predict, roi, full)
        days_back: Number of days to analyze
        target_date: Specific date to analyze
        output_json: Output as JSON instead of formatted report
        data_path: Path to Claude data directory

    Returns:
        Exit code (0 for success)
    """
    report = InsightsReport(data_path)

    try:
        if command == "tools":
            data = report.tool_analyzer.analyze(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.tool_analyzer.print_report(data)

        elif command == "cache":
            data = report.cache_analyzer.analyze(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.cache_analyzer.print_report(data)

        elif command == "anomalies":
            data = report.anomaly_detector.analyze(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.anomaly_detector.print_report(data)

        elif command == "skills":
            data = report.skill_analyzer.analyze(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.skill_analyzer.print_report(data)

        elif command == "predict":
            data = report.predictor.analyze(days_back=max(30, days_back))
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.predictor.print_report(data)

        elif command == "roi":
            data = report.roi_analyzer.analyze(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.roi_analyzer.print_report(data)

        elif command == "full":
            data = report.generate_full_report(days_back, target_date)
            if output_json:
                print(json.dumps(data, indent=2, default=str))
            else:
                report.print_full_report(data)

        else:
            print(f"Unknown command: {command}")
            print("Available commands: tools, cache, anomalies, skills, predict, roi, full")
            return 1

        return 0

    except Exception as e:
        logger.exception(f"Error running insights command: {e}")
        print(f"Error: {e}")
        return 1
