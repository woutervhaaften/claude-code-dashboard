"""ROI and value analyzer.

Analyzes return on investment by tracking value generated
versus tokens spent across different domains and activities.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


# Domain classification patterns
DOMAIN_PATTERNS = {
    "coding": ["edit", "write", "bash", "grep", "glob", "read"],
    "research": ["websearch", "webfetch"],
    "communication": ["mcp__outlook", "email"],
    "crm": ["mcp__pipedrive"],
    "meetings": ["mcp__ask-maia", "maia"],
    "automation": ["n8n", "workflow"],
    "data": ["sql", "database", "supabase"],
    "agents": ["task", "agent"],
}


@dataclass
class DomainStats:
    """Statistics for a domain."""
    name: str
    sessions: Set[str] = field(default_factory=set)
    tool_calls: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def tokens_per_call(self) -> float:
        return self.output_tokens / self.tool_calls if self.tool_calls > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sessions": self.session_count,
            "tool_calls": self.tool_calls,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
            "tokens_per_call": self.tokens_per_call,
        }


@dataclass
class ProjectROI:
    """ROI statistics for a project."""
    name: str
    sessions: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    domains: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sessions": self.sessions,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
            "tokens_per_session": self.output_tokens / self.sessions if self.sessions > 0 else 0,
            "cost_per_session": self.cost / self.sessions if self.sessions > 0 else 0,
            "primary_domains": sorted(self.domains.items(), key=lambda x: x[1], reverse=True)[:3],
        }


class ROIAnalyzer:
    """Analyzes ROI and value across domains and projects."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)
        self.domains: Dict[str, DomainStats] = {}
        self.projects: Dict[str, ProjectROI] = {}

    def analyze(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze ROI for the specified period.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with ROI analysis
        """
        target_dates = self.loader.get_date_range(days_back, target_date)
        self._reset()

        total_tokens = 0
        total_cost = 0.0
        session_count = 0

        for session in self.loader.iter_sessions(target_dates):
            session_count += 1
            total_tokens += session.output_tokens
            total_cost += session.cost

            self._classify_session(session)

        return {
            "period": {
                "start": target_dates[-1] if target_dates else None,
                "end": target_dates[0] if target_dates else None,
                "days": len(target_dates),
            },
            "summary": {
                "total_sessions": session_count,
                "total_output_tokens": total_tokens,
                "total_cost": total_cost,
                "avg_cost_per_session": total_cost / session_count if session_count > 0 else 0,
            },
            "by_domain": self._get_domain_breakdown(),
            "by_project": self._get_project_breakdown(),
            "value_analysis": self._analyze_value(),
            "recommendations": self._generate_recommendations(),
        }

    def _reset(self) -> None:
        """Reset analyzer state."""
        self.domains = {}
        self.projects = {}

    def _classify_session(self, session: SessionData) -> None:
        """Classify session activity into domains."""
        # Track project
        if session.project not in self.projects:
            self.projects[session.project] = ProjectROI(name=session.project)
        proj = self.projects[session.project]
        proj.sessions += 1
        proj.output_tokens += session.output_tokens
        proj.cost += session.cost

        # Classify tools into domains
        for tool_name, count in session.tool_calls.items():
            domain = self._get_domain(tool_name)

            if domain not in self.domains:
                self.domains[domain] = DomainStats(name=domain)

            stats = self.domains[domain]
            stats.sessions.add(session.session_id)
            stats.tool_calls += count

            # Estimate token allocation per tool (proportional)
            total_calls = sum(session.tool_calls.values())
            token_share = session.output_tokens * (count / total_calls) if total_calls > 0 else 0
            cost_share = session.cost * (count / total_calls) if total_calls > 0 else 0

            stats.output_tokens += int(token_share)
            stats.cost += cost_share

            # Track domain in project
            proj.domains[domain] = proj.domains.get(domain, 0) + count

    def _get_domain(self, tool_name: str) -> str:
        """Classify a tool into a domain."""
        tool_lower = tool_name.lower()

        for domain, patterns in DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if pattern in tool_lower:
                    return domain

        return "other"

    def _get_domain_breakdown(self) -> List[Dict[str, Any]]:
        """Get domains sorted by token usage."""
        sorted_domains = sorted(
            self.domains.values(),
            key=lambda d: d.output_tokens,
            reverse=True
        )
        return [d.to_dict() for d in sorted_domains]

    def _get_project_breakdown(self) -> List[Dict[str, Any]]:
        """Get projects sorted by cost."""
        sorted_projects = sorted(
            self.projects.values(),
            key=lambda p: p.cost,
            reverse=True
        )
        return [p.to_dict() for p in sorted_projects[:15]]

    def _analyze_value(self) -> Dict[str, Any]:
        """Analyze value distribution."""
        total_tokens = sum(d.output_tokens for d in self.domains.values())

        # Calculate domain percentages
        domain_pcts = {}
        for d in self.domains.values():
            pct = (d.output_tokens / total_tokens * 100) if total_tokens > 0 else 0
            domain_pcts[d.name] = pct

        # Identify high-value domains (coding, automation typically high ROI)
        high_value_domains = ["coding", "automation", "data"]
        high_value_pct = sum(domain_pcts.get(d, 0) for d in high_value_domains)

        # Identify support domains
        support_domains = ["research", "communication", "meetings"]
        support_pct = sum(domain_pcts.get(d, 0) for d in support_domains)

        return {
            "domain_percentages": domain_pcts,
            "high_value_percentage": high_value_pct,
            "support_percentage": support_pct,
            "balance_score": self._calculate_balance_score(domain_pcts),
        }

    def _calculate_balance_score(self, domain_pcts: Dict[str, float]) -> float:
        """Calculate a balance score (0-100) for domain distribution."""
        # Ideal: ~50% high-value, ~30% support, ~20% other
        high_value = sum(domain_pcts.get(d, 0) for d in ["coding", "automation", "data"])
        support = sum(domain_pcts.get(d, 0) for d in ["research", "communication", "meetings"])

        # Score based on having good distribution
        score = 100
        if high_value < 30:
            score -= 20  # Too little productive work
        if high_value > 80:
            score -= 10  # Maybe missing support activities
        if support > 50:
            score -= 15  # Too much time on support

        return max(0, min(100, score))

    def _generate_recommendations(self) -> List[str]:
        """Generate ROI recommendations."""
        recommendations = []

        value_analysis = self._analyze_value()

        if value_analysis["high_value_percentage"] > 70:
            recommendations.append(
                f"Great focus! {value_analysis['high_value_percentage']:.0f}% of tokens "
                f"spent on high-value activities (coding, automation, data)."
            )
        elif value_analysis["high_value_percentage"] < 40:
            recommendations.append(
                f"Consider shifting focus: only {value_analysis['high_value_percentage']:.0f}% "
                f"on high-value activities. More coding/automation may increase ROI."
            )

        # Check for expensive projects
        for proj in sorted(self.projects.values(), key=lambda p: p.cost, reverse=True)[:3]:
            if proj.cost > 10:
                recommendations.append(
                    f"Project '{proj.name[:30]}' cost {format_cost(proj.cost)}. "
                    f"Review for optimization opportunities."
                )

        # Check agent usage
        agent_domain = self.domains.get("agents")
        if agent_domain and agent_domain.output_tokens > 500000:
            recommendations.append(
                f"Agent spawning used {format_tokens(agent_domain.output_tokens)}. "
                f"Consider consolidating agent tasks."
            )

        return recommendations if recommendations else ["Token ROI looks balanced."]

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted ROI report."""
        period = data["period"]
        summary = data["summary"]
        value = data["value_analysis"]

        print("\n" + "=" * 90)
        print("  ROI & VALUE ANALYSIS")
        print(f"  Period: {period['start']} to {period['end']} ({period['days']} days)")
        print("=" * 90)

        # Summary
        print(f"\n  SUMMARY")
        print(f"  {'-'*50}")
        print(f"  Total Sessions:      {summary['total_sessions']:>10}")
        print(f"  Total Output Tokens: {format_tokens(summary['total_output_tokens']):>10}")
        print(f"  Total Cost:          {format_cost(summary['total_cost']):>10}")
        print(f"  Avg Cost/Session:    {format_cost(summary['avg_cost_per_session']):>10}")

        # Value analysis
        print(f"\n\n  VALUE DISTRIBUTION")
        print(f"  {'-'*50}")
        print(f"  High-Value (coding/automation/data): {value['high_value_percentage']:>6.1f}%")
        print(f"  Support (research/comms/meetings):   {value['support_percentage']:>6.1f}%")
        print(f"  Balance Score:                       {value['balance_score']:>6.0f}/100")

        # Domain breakdown
        if data["by_domain"]:
            print(f"\n\n  TOKEN USAGE BY DOMAIN")
            print(f"  {'-'*70}")
            total = summary['total_output_tokens']
            for domain in data["by_domain"]:
                pct = (domain["output_tokens"] / total * 100) if total > 0 else 0
                bar_len = int(pct / 2)
                bar = "#" * bar_len
                print(
                    f"  {domain['name']:<15} | {format_tokens(domain['output_tokens']):>10} "
                    f"({pct:>5.1f}%) | {bar}"
                )

        # Project breakdown
        if data["by_project"]:
            print(f"\n\n  TOP PROJECTS BY COST")
            print(f"  {'-'*86}")
            print(f"  {'Project':<40} | {'Sessions':>8} | {'Cost':>10} | Primary Domains")
            print(f"  {'-'*86}")
            for proj in data["by_project"][:10]:
                name = proj["name"][:40]
                domains = ", ".join([d[0] for d in proj["primary_domains"]])
                print(
                    f"  {name:<40} | {proj['sessions']:>8} | "
                    f"{format_cost(proj['cost']):>10} | {domains[:20]}"
                )

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
