"""Cache efficiency analyzer.

Analyzes cache hit rates, identifies optimization opportunities,
and tracks wasted cache tokens.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


# Approximate costs per 1M tokens (as of 2025)
CACHE_READ_COST_PER_M = 0.30    # $0.30 per 1M cache read tokens
CACHE_CREATE_COST_PER_M = 3.75  # $3.75 per 1M cache creation tokens
INPUT_COST_PER_M = 3.00         # $3.00 per 1M input tokens
OUTPUT_COST_PER_M = 15.00       # $15.00 per 1M output tokens


@dataclass
class CacheStats:
    """Cache statistics for a period."""
    cache_read: int = 0
    cache_create: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    sessions: int = 0
    cost: float = 0.0

    @property
    def total_input_context(self) -> int:
        """Total input context including cache."""
        return self.cache_read + self.cache_create + self.input_tokens

    @property
    def cache_hit_rate(self) -> float:
        """Percentage of input from cache reads."""
        total = self.total_input_context
        return (self.cache_read / total * 100) if total > 0 else 0

    @property
    def cache_efficiency_score(self) -> float:
        """Score 0-100 based on cache utilization."""
        if self.total_input_context == 0:
            return 0

        # Good: high cache_read, low cache_create relative to cache_read
        read_ratio = self.cache_read / self.total_input_context
        create_efficiency = 1.0
        if self.cache_create > 0:
            # Penalize if we create more cache than we read
            create_efficiency = min(1.0, self.cache_read / (self.cache_create * 5))

        return min(100, (read_ratio * 80 + create_efficiency * 20))

    @property
    def estimated_cache_savings(self) -> float:
        """Estimated cost savings from cache usage."""
        # Without cache, cache_read would be input tokens at full price
        full_input_cost = (self.cache_read / 1_000_000) * INPUT_COST_PER_M
        actual_cache_cost = (self.cache_read / 1_000_000) * CACHE_READ_COST_PER_M
        return full_input_cost - actual_cache_cost

    @property
    def wasted_cache_tokens(self) -> int:
        """Cache creation tokens that were never read (approximation)."""
        # If cache_create >> cache_read, some cache was wasted
        if self.cache_create > self.cache_read:
            return self.cache_create - self.cache_read
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_read": self.cache_read,
            "cache_create": self.cache_create,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "sessions": self.sessions,
            "cost": self.cost,
            "total_input_context": self.total_input_context,
            "cache_hit_rate": self.cache_hit_rate,
            "cache_efficiency_score": self.cache_efficiency_score,
            "estimated_savings": self.estimated_cache_savings,
            "wasted_cache_tokens": self.wasted_cache_tokens,
        }


class CacheAnalyzer:
    """Analyzes cache efficiency and optimization opportunities."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)

    def analyze(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze cache efficiency for the specified period.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with cache statistics and recommendations
        """
        target_dates = self.loader.get_date_range(days_back, target_date)

        overall = CacheStats()
        by_project: Dict[str, CacheStats] = {}
        by_day: Dict[str, CacheStats] = {}
        sessions_with_low_cache: List[Dict[str, Any]] = []
        sessions_with_wasted_cache: List[Dict[str, Any]] = []

        for session in self.loader.iter_sessions(target_dates):
            # Update overall stats
            overall.cache_read += session.cache_read
            overall.cache_create += session.cache_create
            overall.input_tokens += session.input_tokens
            overall.output_tokens += session.output_tokens
            overall.sessions += 1
            overall.cost += session.cost

            # Update project stats
            if session.project not in by_project:
                by_project[session.project] = CacheStats()
            proj = by_project[session.project]
            proj.cache_read += session.cache_read
            proj.cache_create += session.cache_create
            proj.input_tokens += session.input_tokens
            proj.output_tokens += session.output_tokens
            proj.sessions += 1
            proj.cost += session.cost

            # Update daily stats
            if session.timestamps:
                day = session.timestamps[0][:10]  # YYYY-MM-DD
                if day not in by_day:
                    by_day[day] = CacheStats()
                daily = by_day[day]
                daily.cache_read += session.cache_read
                daily.cache_create += session.cache_create
                daily.input_tokens += session.input_tokens
                daily.output_tokens += session.output_tokens
                daily.sessions += 1
                daily.cost += session.cost

            # Track sessions with issues
            session_total = session.cache_read + session.cache_create + session.input_tokens
            if session_total > 100000:  # Only significant sessions
                cache_rate = (session.cache_read / session_total * 100) if session_total > 0 else 0
                if cache_rate < 50:
                    sessions_with_low_cache.append({
                        "session_id": session.session_id,
                        "project": session.project,
                        "cache_hit_rate": cache_rate,
                        "total_context": session_total,
                        "task": session.first_msg[:80] if session.first_msg else None,
                    })

                # Wasted cache check
                if session.cache_create > session.cache_read * 2 and session.cache_create > 50000:
                    sessions_with_wasted_cache.append({
                        "session_id": session.session_id,
                        "project": session.project,
                        "cache_create": session.cache_create,
                        "cache_read": session.cache_read,
                        "wasted": session.cache_create - session.cache_read,
                    })

        return {
            "period": {
                "start": target_dates[-1] if target_dates else None,
                "end": target_dates[0] if target_dates else None,
                "days": len(target_dates),
            },
            "overall": overall.to_dict(),
            "by_project": {
                k: v.to_dict()
                for k, v in sorted(
                    by_project.items(),
                    key=lambda x: x[1].total_input_context,
                    reverse=True
                )[:10]
            },
            "by_day": {
                k: v.to_dict()
                for k, v in sorted(by_day.items())
            },
            "low_cache_sessions": sorted(
                sessions_with_low_cache,
                key=lambda x: x["cache_hit_rate"]
            )[:10],
            "wasted_cache_sessions": sorted(
                sessions_with_wasted_cache,
                key=lambda x: x["wasted"],
                reverse=True
            )[:10],
            "recommendations": self._generate_recommendations(
                overall, sessions_with_low_cache, sessions_with_wasted_cache
            ),
        }

    def _generate_recommendations(
        self,
        overall: CacheStats,
        low_cache: List[Dict[str, Any]],
        wasted: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate cache optimization recommendations."""
        recommendations = []

        # Overall efficiency
        if overall.cache_hit_rate < 60:
            recommendations.append(
                f"Low cache hit rate ({overall.cache_hit_rate:.1f}%). "
                f"Consider longer conversations or --continue flag."
            )
        elif overall.cache_hit_rate > 80:
            recommendations.append(
                f"Excellent cache hit rate ({overall.cache_hit_rate:.1f}%). "
                f"Keep using long sessions!"
            )

        # Savings highlight
        if overall.estimated_cache_savings > 1.0:
            recommendations.append(
                f"Cache saved approximately {format_cost(overall.estimated_cache_savings)} "
                f"this period."
            )

        # Wasted cache
        if overall.wasted_cache_tokens > 1_000_000:
            recommendations.append(
                f"Approximately {format_tokens(overall.wasted_cache_tokens)} cache tokens "
                f"may have been wasted (created but not reused)."
            )

        # Specific session issues
        if len(low_cache) >= 3:
            recommendations.append(
                f"{len(low_cache)} sessions had low cache efficiency. "
                f"Consider using 'claude --continue' to resume sessions."
            )

        if len(wasted) >= 2:
            recommendations.append(
                f"{len(wasted)} sessions had significant cache waste. "
                f"Review for unnecessary context refreshes."
            )

        return recommendations if recommendations else ["Cache usage looks healthy."]

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted cache analysis report."""
        period = data["period"]
        overall = data["overall"]

        print("\n" + "=" * 90)
        print("  CACHE EFFICIENCY ANALYSIS")
        print(f"  Period: {period['start']} to {period['end']} ({period['days']} days)")
        print("=" * 90)

        # Overall summary
        print(f"\n  OVERALL CACHE METRICS")
        print(f"  {'-'*50}")
        print(f"  Cache Read Tokens:    {format_tokens(overall['cache_read']):>12}")
        print(f"  Cache Create Tokens:  {format_tokens(overall['cache_create']):>12}")
        print(f"  Regular Input Tokens: {format_tokens(overall['input_tokens']):>12}")
        print(f"  Output Tokens:        {format_tokens(overall['output_tokens']):>12}")
        print(f"  {'-'*50}")
        print(f"  Cache Hit Rate:       {overall['cache_hit_rate']:>11.1f}%")
        print(f"  Efficiency Score:     {overall['cache_efficiency_score']:>11.1f}/100")
        print(f"  Estimated Savings:    {format_cost(overall['estimated_savings']):>12}")

        if overall['wasted_cache_tokens'] > 0:
            print(f"  Wasted Cache (est):   {format_tokens(overall['wasted_cache_tokens']):>12}")

        # Daily trend
        if data["by_day"]:
            print(f"\n\n  DAILY CACHE HIT RATE TREND")
            print(f"  {'-'*60}")
            for day, stats in sorted(data["by_day"].items())[-14:]:
                rate = stats["cache_hit_rate"]
                bar_len = int(rate / 2)  # Scale to 50 chars max
                bar = "#" * bar_len
                print(f"  {day} | {rate:>5.1f}% | {bar}")

        # Project breakdown
        if data["by_project"]:
            print(f"\n\n  CACHE BY PROJECT (Top 10)")
            print(f"  {'-'*86}")
            print(f"  {'Project':<40} | {'Hit Rate':>8} | {'Efficiency':>10} | {'Context':>12}")
            print(f"  {'-'*86}")
            for proj, stats in list(data["by_project"].items())[:10]:
                proj_short = proj[:40]
                print(
                    f"  {proj_short:<40} | {stats['cache_hit_rate']:>7.1f}% | "
                    f"{stats['cache_efficiency_score']:>9.1f} | {format_tokens(stats['total_input_context']):>12}"
                )

        # Low cache sessions
        if data["low_cache_sessions"]:
            print(f"\n\n  SESSIONS WITH LOW CACHE EFFICIENCY")
            print(f"  {'-'*86}")
            for sess in data["low_cache_sessions"][:5]:
                print(f"  - {sess['project'][:35]}: {sess['cache_hit_rate']:.1f}% hit rate")
                if sess.get("task"):
                    print(f"    Task: {sess['task'][:60]}...")

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
