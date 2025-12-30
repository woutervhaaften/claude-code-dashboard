"""Skill performance analyzer.

Tracks skill invocation frequency, token efficiency,
and success patterns.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


@dataclass
class SkillStats:
    """Statistics for a single skill."""
    name: str
    invocations: int = 0
    sessions: Set[str] = field(default_factory=set)
    total_output_tokens: int = 0
    total_cost: float = 0.0
    projects: Set[str] = field(default_factory=set)

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def avg_tokens_per_invocation(self) -> float:
        return self.total_output_tokens / self.invocations if self.invocations > 0 else 0

    @property
    def avg_cost_per_invocation(self) -> float:
        return self.total_cost / self.invocations if self.invocations > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "invocations": self.invocations,
            "sessions": self.session_count,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "avg_tokens_per_invocation": self.avg_tokens_per_invocation,
            "avg_cost_per_invocation": self.avg_cost_per_invocation,
            "projects": list(self.projects),
        }


class SkillAnalyzer:
    """Analyzes skill performance and usage patterns."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)
        self.skills: Dict[str, SkillStats] = {}

    def analyze(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze skill usage for the specified period.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with skill statistics
        """
        target_dates = self.loader.get_date_range(days_back, target_date)
        self.skills = {}

        total_invocations = 0
        total_tokens = 0
        total_cost = 0.0
        sessions_with_skills = 0

        for session in self.loader.iter_sessions(target_dates):
            if not session.skill_calls:
                continue

            sessions_with_skills += 1

            # Estimate tokens/cost per skill invocation
            total_skill_calls = sum(session.skill_calls.values())
            tokens_per_call = session.output_tokens / total_skill_calls if total_skill_calls > 0 else 0
            cost_per_call = session.cost / total_skill_calls if total_skill_calls > 0 else 0

            for skill_name, count in session.skill_calls.items():
                if skill_name not in self.skills:
                    self.skills[skill_name] = SkillStats(name=skill_name)

                stats = self.skills[skill_name]
                stats.invocations += count
                stats.sessions.add(session.session_id)
                stats.projects.add(session.project)
                stats.total_output_tokens += int(tokens_per_call * count)
                stats.total_cost += cost_per_call * count

                total_invocations += count
                total_tokens += int(tokens_per_call * count)
                total_cost += cost_per_call * count

        return {
            "period": {
                "start": target_dates[-1] if target_dates else None,
                "end": target_dates[0] if target_dates else None,
                "days": len(target_dates),
            },
            "summary": {
                "total_skills": len(self.skills),
                "total_invocations": total_invocations,
                "sessions_with_skills": sessions_with_skills,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
            },
            "skills": self._get_skills_ranking(),
            "by_efficiency": self._get_efficiency_ranking(),
            "recommendations": self._generate_recommendations(),
        }

    def _get_skills_ranking(self) -> List[Dict[str, Any]]:
        """Get skills ranked by invocation count."""
        sorted_skills = sorted(
            self.skills.values(),
            key=lambda s: s.invocations,
            reverse=True
        )
        return [s.to_dict() for s in sorted_skills]

    def _get_efficiency_ranking(self) -> List[Dict[str, Any]]:
        """Get skills ranked by token efficiency (lower is better)."""
        # Filter to skills with meaningful usage
        significant_skills = [s for s in self.skills.values() if s.invocations >= 3]
        sorted_skills = sorted(
            significant_skills,
            key=lambda s: s.avg_tokens_per_invocation
        )
        return [s.to_dict() for s in sorted_skills]

    def _generate_recommendations(self) -> List[str]:
        """Generate skill usage recommendations."""
        recommendations = []

        # Check for rarely used skills
        rarely_used = [s for s in self.skills.values() if s.invocations == 1]
        if len(rarely_used) >= 3:
            recommendations.append(
                f"{len(rarely_used)} skills used only once. "
                f"Consider consolidating or removing unused skills."
            )

        # Check for expensive skills
        for skill in self.skills.values():
            if skill.invocations >= 3 and skill.avg_tokens_per_invocation > 50000:
                recommendations.append(
                    f"Skill '{skill.name}' is expensive "
                    f"({format_tokens(int(skill.avg_tokens_per_invocation))} avg tokens/invocation). "
                    f"Consider optimization."
                )

        # Check for heavily used efficient skills
        efficient = [s for s in self.skills.values()
                     if s.invocations >= 5 and s.avg_tokens_per_invocation < 10000]
        if efficient:
            top = sorted(efficient, key=lambda s: s.invocations, reverse=True)[0]
            recommendations.append(
                f"'{top.name}' is your most efficient frequently-used skill "
                f"({top.invocations} invocations, {format_tokens(int(top.avg_tokens_per_invocation))} avg)."
            )

        return recommendations if recommendations else ["No skill optimization issues detected."]

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted skill analysis report."""
        period = data["period"]
        summary = data["summary"]

        print("\n" + "=" * 90)
        print("  SKILL PERFORMANCE ANALYSIS")
        print(f"  Period: {period['start']} to {period['end']} ({period['days']} days)")
        print("=" * 90)

        # Summary
        print(f"\n  SUMMARY")
        print(f"  {'-'*50}")
        print(f"  Total Skills Used:   {summary['total_skills']:>10}")
        print(f"  Total Invocations:   {summary['total_invocations']:>10}")
        print(f"  Sessions w/Skills:   {summary['sessions_with_skills']:>10}")
        print(f"  Total Tokens:        {format_tokens(summary['total_tokens']):>10}")
        print(f"  Total Cost:          {format_cost(summary['total_cost']):>10}")

        # Skills by usage
        if data["skills"]:
            print(f"\n\n  SKILLS BY USAGE")
            print(f"  {'-'*86}")
            print(f"  {'Skill':<35} | {'Invocations':>11} | {'Sessions':>8} | {'Avg Tokens':>12}")
            print(f"  {'-'*86}")
            for skill in data["skills"][:15]:
                name = skill["name"][:35]
                print(
                    f"  {name:<35} | {skill['invocations']:>11} | "
                    f"{skill['sessions']:>8} | {format_tokens(int(skill['avg_tokens_per_invocation'])):>12}"
                )

        # Efficiency ranking
        if data["by_efficiency"]:
            print(f"\n\n  SKILLS BY EFFICIENCY (lowest tokens = best)")
            print(f"  {'-'*60}")
            for i, skill in enumerate(data["by_efficiency"][:5], 1):
                print(
                    f"  {i}. {skill['name'][:30]}: "
                    f"{format_tokens(int(skill['avg_tokens_per_invocation']))} avg, "
                    f"{skill['invocations']} invocations"
                )

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
