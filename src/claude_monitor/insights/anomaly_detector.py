"""Anomaly detection for Claude Code usage.

Detects loops, runaway sessions, unusual patterns,
and provides alerts for potential issues.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


# Anomaly thresholds
LOOP_THRESHOLD_TOOL = 20      # Tool called > N times in session
LOOP_THRESHOLD_FILE = 10      # Same file accessed > N times
LOOP_THRESHOLD_SQL = 10       # SQL queries > N per session
SPIKE_THRESHOLD_TOKENS = 500_000  # Session > N output tokens
SPIKE_THRESHOLD_COST = 5.0    # Session cost > $N


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    severity: str  # HIGH, MEDIUM, LOW
    type: str      # loop, spike, pattern
    session_id: str
    project: str
    description: str
    count: int
    tokens: int
    cost: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "type": self.type,
            "session_id": self.session_id,
            "project": self.project,
            "description": self.description,
            "count": self.count,
            "tokens": self.tokens,
            "cost": self.cost,
            "details": self.details,
        }


class AnomalyDetector:
    """Detects anomalies in Claude Code usage patterns."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)
        self.anomalies: List[Anomaly] = []

    def analyze(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Detect anomalies for the specified period.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with detected anomalies and summary
        """
        target_dates = self.loader.get_date_range(days_back, target_date)
        self.anomalies = []

        total_sessions = 0
        affected_sessions = 0
        total_loop_tokens = 0
        projects_affected: Set[str] = set()

        for session in self.loader.iter_sessions(target_dates):
            total_sessions += 1
            session_anomalies = self._detect_session_anomalies(session)

            if session_anomalies:
                affected_sessions += 1
                projects_affected.add(session.project)
                total_loop_tokens += session.output_tokens
                self.anomalies.extend(session_anomalies)

        # Sort by severity, then by token impact
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        self.anomalies.sort(key=lambda a: (severity_order.get(a.severity, 3), -a.tokens))

        return {
            "period": {
                "start": target_dates[-1] if target_dates else None,
                "end": target_dates[0] if target_dates else None,
                "days": len(target_dates),
            },
            "summary": {
                "total_sessions": total_sessions,
                "sessions_with_anomalies": affected_sessions,
                "anomaly_rate": (affected_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                "total_anomalies": len(self.anomalies),
                "total_loop_tokens": total_loop_tokens,
                "projects_affected": list(projects_affected),
            },
            "by_severity": {
                "high": [a.to_dict() for a in self.anomalies if a.severity == "HIGH"],
                "medium": [a.to_dict() for a in self.anomalies if a.severity == "MEDIUM"],
                "low": [a.to_dict() for a in self.anomalies if a.severity == "LOW"],
            },
            "by_type": self._group_by_type(),
            "recommendations": self._generate_recommendations(projects_affected),
        }

    def _detect_session_anomalies(self, session: SessionData) -> List[Anomaly]:
        """Detect anomalies in a single session."""
        anomalies = []

        # Check for tool loops
        for tool, count in session.tool_calls.items():
            if count > LOOP_THRESHOLD_TOOL:
                severity = "HIGH" if count > LOOP_THRESHOLD_TOOL * 3 else "MEDIUM"
                anomalies.append(Anomaly(
                    severity=severity,
                    type="tool_loop",
                    session_id=session.session_id,
                    project=session.project,
                    description=f"{tool} called {count}x in single session",
                    count=count,
                    tokens=session.output_tokens,
                    cost=session.cost,
                    details={"tool": tool, "threshold": LOOP_THRESHOLD_TOOL},
                ))

        # Check for file access loops
        for file_path, count in session.file_ops.items():
            if count > LOOP_THRESHOLD_FILE:
                file_name = Path(file_path).name
                severity = "MEDIUM" if count > LOOP_THRESHOLD_FILE * 2 else "LOW"
                anomalies.append(Anomaly(
                    severity=severity,
                    type="file_loop",
                    session_id=session.session_id,
                    project=session.project,
                    description=f"File '{file_name}' accessed {count}x",
                    count=count,
                    tokens=session.output_tokens,
                    cost=session.cost,
                    details={"file": file_path, "threshold": LOOP_THRESHOLD_FILE},
                ))

        # Check for SQL query loops (specific MCP pattern)
        sql_calls = sum(
            c for t, c in session.mcp_calls.items()
            if 'sql' in t.lower() or 'query' in t.lower() or 'execute' in t.lower()
        )
        if sql_calls > LOOP_THRESHOLD_SQL:
            severity = "HIGH" if sql_calls > LOOP_THRESHOLD_SQL * 5 else "MEDIUM"
            anomalies.append(Anomaly(
                severity=severity,
                type="sql_loop",
                session_id=session.session_id,
                project=session.project,
                description=f"{sql_calls} SQL queries in single session",
                count=sql_calls,
                tokens=session.output_tokens,
                cost=session.cost,
                details={"query_count": sql_calls, "threshold": LOOP_THRESHOLD_SQL},
            ))

        # Check for token spikes
        if session.output_tokens > SPIKE_THRESHOLD_TOKENS:
            severity = "HIGH" if session.output_tokens > SPIKE_THRESHOLD_TOKENS * 2 else "MEDIUM"
            anomalies.append(Anomaly(
                severity=severity,
                type="token_spike",
                session_id=session.session_id,
                project=session.project,
                description=f"High token usage: {format_tokens(session.output_tokens)} output",
                count=1,
                tokens=session.output_tokens,
                cost=session.cost,
                details={
                    "output_tokens": session.output_tokens,
                    "threshold": SPIKE_THRESHOLD_TOKENS,
                },
            ))

        # Check for cost spikes
        if session.cost > SPIKE_THRESHOLD_COST:
            severity = "HIGH" if session.cost > SPIKE_THRESHOLD_COST * 2 else "MEDIUM"
            # Avoid duplicate if already detected as token spike
            if not any(a.type == "token_spike" and a.severity == "HIGH" for a in anomalies):
                anomalies.append(Anomaly(
                    severity=severity,
                    type="cost_spike",
                    session_id=session.session_id,
                    project=session.project,
                    description=f"High session cost: {format_cost(session.cost)}",
                    count=1,
                    tokens=session.output_tokens,
                    cost=session.cost,
                    details={"cost": session.cost, "threshold": SPIKE_THRESHOLD_COST},
                ))

        # Check for excessive agent spawning
        agent_calls = session.tool_calls.get('Task', 0)
        if agent_calls > 10:
            severity = "MEDIUM" if agent_calls > 20 else "LOW"
            anomalies.append(Anomaly(
                severity=severity,
                type="agent_spawn_loop",
                session_id=session.session_id,
                project=session.project,
                description=f"{agent_calls} sub-agents spawned in single session",
                count=agent_calls,
                tokens=session.output_tokens,
                cost=session.cost,
                details={"agent_count": agent_calls},
            ))

        return anomalies

    def _group_by_type(self) -> Dict[str, int]:
        """Group anomalies by type."""
        by_type: Dict[str, int] = {}
        for a in self.anomalies:
            by_type[a.type] = by_type.get(a.type, 0) + 1
        return dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True))

    def _generate_recommendations(self, projects_affected: Set[str]) -> List[str]:
        """Generate recommendations based on detected anomalies."""
        recommendations = []

        # Count anomaly types
        type_counts = self._group_by_type()

        if type_counts.get("tool_loop", 0) >= 3:
            recommendations.append(
                "Multiple tool loops detected. Add circuit breaker rules to project CLAUDE.md files."
            )

        if type_counts.get("sql_loop", 0) >= 1:
            recommendations.append(
                "SQL query loops detected. Use JOINs instead of N+1 queries. "
                "Add 'Maximum 10 SQL queries per request' rule."
            )

        if type_counts.get("file_loop", 0) >= 2:
            recommendations.append(
                "File access loops detected. Cache file contents or use Explore agent for searches."
            )

        if type_counts.get("agent_spawn_loop", 0) >= 1:
            recommendations.append(
                "Excessive agent spawning detected. Consolidate related tasks in primary session."
            )

        if len(projects_affected) >= 3:
            recommendations.append(
                f"{len(projects_affected)} projects affected. Consider global CLAUDE.md rules."
            )

        # High severity count
        high_count = len([a for a in self.anomalies if a.severity == "HIGH"])
        if high_count >= 2:
            recommendations.append(
                f"{high_count} high-severity anomalies. Immediate attention recommended."
            )

        return recommendations if recommendations else ["No critical issues detected."]

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted anomaly detection report."""
        period = data["period"]
        summary = data["summary"]

        print("\n" + "=" * 90)
        print("  ANOMALY DETECTION REPORT")
        print(f"  Period: {period['start']} to {period['end']} ({period['days']} days)")
        print("=" * 90)

        # Summary
        print(f"\n  SUMMARY")
        print(f"  {'-'*50}")
        print(f"  Total Sessions:      {summary['total_sessions']:>10}")
        print(f"  Sessions w/Anomalies:{summary['sessions_with_anomalies']:>10}")
        print(f"  Anomaly Rate:        {summary['anomaly_rate']:>9.1f}%")
        print(f"  Total Anomalies:     {summary['total_anomalies']:>10}")
        print(f"  Token Impact:        {format_tokens(summary['total_loop_tokens']):>10}")

        # By type
        if data["by_type"]:
            print(f"\n\n  ANOMALIES BY TYPE")
            print(f"  {'-'*50}")
            for atype, count in data["by_type"].items():
                print(f"  {atype:<25} | {count:>5}")

        # High severity
        high = data["by_severity"]["high"]
        if high:
            print(f"\n\n  HIGH SEVERITY ANOMALIES ({len(high)})")
            print(f"  {'-'*86}")
            for a in high[:10]:
                print(f"\n  [{a['type']}] {a['description']}")
                print(f"    Project: {a['project'][:50]}")
                print(f"    Session: {a['session_id'][:40]}")
                print(f"    Impact: {format_tokens(a['tokens'])} tokens, {format_cost(a['cost'])}")

        # Medium severity
        medium = data["by_severity"]["medium"]
        if medium:
            print(f"\n\n  MEDIUM SEVERITY ANOMALIES ({len(medium)})")
            print(f"  {'-'*86}")
            for a in medium[:5]:
                print(f"  - [{a['type']}] {a['description']}")
                print(f"    Project: {a['project'][:40]}")

        # Projects affected
        if summary["projects_affected"]:
            print(f"\n\n  AFFECTED PROJECTS ({len(summary['projects_affected'])})")
            print(f"  {'-'*50}")
            for proj in summary["projects_affected"][:10]:
                print(f"  - {proj[:60]}")

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
