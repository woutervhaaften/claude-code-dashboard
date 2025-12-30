"""Usage prediction and forecasting.

Forecasts future token usage and costs based on historical patterns.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


@dataclass
class DailyStats:
    """Statistics for a single day."""
    date: str
    sessions: int = 0
    output_tokens: int = 0
    input_tokens: int = 0
    cache_read: int = 0
    cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "sessions": self.sessions,
            "output_tokens": self.output_tokens,
            "input_tokens": self.input_tokens,
            "cache_read": self.cache_read,
            "cost": self.cost,
        }


class UsagePredictor:
    """Predicts future usage based on historical patterns."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)

    def analyze(
        self,
        days_back: int = 30,
        forecast_days: int = 7,
    ) -> Dict[str, Any]:
        """Analyze historical usage and forecast future.

        Args:
            days_back: Number of historical days to analyze
            forecast_days: Number of days to forecast

        Returns:
            Dictionary with historical data and forecasts
        """
        target_dates = self.loader.get_date_range(days_back)

        # Collect daily statistics
        daily_stats: Dict[str, DailyStats] = {}

        for session in self.loader.iter_sessions(target_dates):
            if not session.timestamps:
                continue

            day = session.timestamps[0][:10]  # YYYY-MM-DD

            if day not in daily_stats:
                daily_stats[day] = DailyStats(date=day)

            stats = daily_stats[day]
            stats.sessions += 1
            stats.output_tokens += session.output_tokens
            stats.input_tokens += session.input_tokens
            stats.cache_read += session.cache_read
            stats.cost += session.cost

        # Convert to sorted list
        history = [daily_stats[d].to_dict() for d in sorted(daily_stats.keys())]

        # Calculate trends
        trends = self._calculate_trends(history)

        # Generate forecasts
        forecasts = self._generate_forecasts(history, trends, forecast_days)

        # Calculate summaries
        return {
            "period": {
                "historical_start": target_dates[-1] if target_dates else None,
                "historical_end": target_dates[0] if target_dates else None,
                "forecast_end": (datetime.now() + timedelta(days=forecast_days)).strftime("%Y-%m-%d"),
            },
            "historical": {
                "days_analyzed": len(history),
                "total_sessions": sum(d["sessions"] for d in history),
                "total_output_tokens": sum(d["output_tokens"] for d in history),
                "total_cost": sum(d["cost"] for d in history),
                "daily_average": {
                    "sessions": sum(d["sessions"] for d in history) / len(history) if history else 0,
                    "output_tokens": sum(d["output_tokens"] for d in history) / len(history) if history else 0,
                    "cost": sum(d["cost"] for d in history) / len(history) if history else 0,
                },
            },
            "trends": trends,
            "forecast": {
                "days": forecast_days,
                "projected_sessions": forecasts["sessions"],
                "projected_output_tokens": forecasts["output_tokens"],
                "projected_cost": forecasts["cost"],
                "confidence": forecasts["confidence"],
            },
            "daily_history": history[-14:],  # Last 2 weeks
            "recommendations": self._generate_recommendations(trends, forecasts),
        }

    def _calculate_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate usage trends."""
        if len(history) < 7:
            return {
                "direction": "insufficient_data",
                "sessions_change_pct": 0,
                "tokens_change_pct": 0,
                "cost_change_pct": 0,
            }

        # Compare first half to second half
        mid = len(history) // 2
        first_half = history[:mid]
        second_half = history[mid:]

        first_sessions = sum(d["sessions"] for d in first_half) / len(first_half)
        second_sessions = sum(d["sessions"] for d in second_half) / len(second_half)

        first_tokens = sum(d["output_tokens"] for d in first_half) / len(first_half)
        second_tokens = sum(d["output_tokens"] for d in second_half) / len(second_half)

        first_cost = sum(d["cost"] for d in first_half) / len(first_half)
        second_cost = sum(d["cost"] for d in second_half) / len(second_half)

        sessions_change = ((second_sessions - first_sessions) / first_sessions * 100) if first_sessions > 0 else 0
        tokens_change = ((second_tokens - first_tokens) / first_tokens * 100) if first_tokens > 0 else 0
        cost_change = ((second_cost - first_cost) / first_cost * 100) if first_cost > 0 else 0

        # Determine direction
        if tokens_change > 10:
            direction = "increasing"
        elif tokens_change < -10:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "sessions_change_pct": sessions_change,
            "tokens_change_pct": tokens_change,
            "cost_change_pct": cost_change,
        }

    def _generate_forecasts(
        self,
        history: List[Dict[str, Any]],
        trends: Dict[str, Any],
        forecast_days: int,
    ) -> Dict[str, Any]:
        """Generate usage forecasts."""
        if len(history) < 7:
            return {
                "sessions": 0,
                "output_tokens": 0,
                "cost": 0,
                "confidence": "low",
            }

        # Use weighted average of recent days (more weight to recent)
        recent = history[-7:]  # Last week
        weights = [1, 1, 2, 2, 3, 3, 4]  # More weight to recent days
        total_weight = sum(weights[:len(recent)])

        avg_sessions = sum(d["sessions"] * w for d, w in zip(recent, weights)) / total_weight
        avg_tokens = sum(d["output_tokens"] * w for d, w in zip(recent, weights)) / total_weight
        avg_cost = sum(d["cost"] * w for d, w in zip(recent, weights)) / total_weight

        # Apply trend adjustment
        trend_factor = 1.0
        if trends["direction"] == "increasing":
            trend_factor = 1 + (trends["tokens_change_pct"] / 100 * 0.5)  # Dampened trend
        elif trends["direction"] == "decreasing":
            trend_factor = 1 + (trends["tokens_change_pct"] / 100 * 0.5)

        # Calculate confidence based on data consistency
        token_variance = self._calculate_variance([d["output_tokens"] for d in recent])
        avg_token = avg_tokens
        cv = (token_variance ** 0.5 / avg_token) if avg_token > 0 else 1

        if cv < 0.3:
            confidence = "high"
        elif cv < 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "sessions": int(avg_sessions * forecast_days * trend_factor),
            "output_tokens": int(avg_tokens * forecast_days * trend_factor),
            "cost": avg_cost * forecast_days * trend_factor,
            "confidence": confidence,
        }

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    def _generate_recommendations(
        self,
        trends: Dict[str, Any],
        forecasts: Dict[str, Any],
    ) -> List[str]:
        """Generate predictions and recommendations."""
        recommendations = []

        if trends["direction"] == "increasing" and trends["tokens_change_pct"] > 20:
            recommendations.append(
                f"Usage trending up {trends['tokens_change_pct']:.0f}%. "
                f"Monitor for potential cost increases."
            )
        elif trends["direction"] == "decreasing":
            recommendations.append(
                f"Usage trending down {abs(trends['tokens_change_pct']):.0f}%. "
                f"Good for cost control."
            )
        else:
            recommendations.append("Usage patterns are stable.")

        # Cost projection warning
        if forecasts["cost"] > 100:
            recommendations.append(
                f"Projected weekly cost: {format_cost(forecasts['cost'])}. "
                f"Consider setting usage limits."
            )

        # Confidence note
        if forecasts["confidence"] == "low":
            recommendations.append(
                "Forecast confidence is low due to high usage variance. "
                "More consistent patterns will improve predictions."
            )

        return recommendations

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted prediction report."""
        period = data["period"]
        historical = data["historical"]
        trends = data["trends"]
        forecast = data["forecast"]

        print("\n" + "=" * 90)
        print("  USAGE PREDICTION & FORECAST")
        print(f"  Historical: {period['historical_start']} to {period['historical_end']}")
        print(f"  Forecast through: {period['forecast_end']}")
        print("=" * 90)

        # Historical summary
        print(f"\n  HISTORICAL USAGE ({historical['days_analyzed']} days)")
        print(f"  {'-'*50}")
        print(f"  Total Sessions:      {historical['total_sessions']:>10}")
        print(f"  Total Output Tokens: {format_tokens(historical['total_output_tokens']):>10}")
        print(f"  Total Cost:          {format_cost(historical['total_cost']):>10}")
        print(f"\n  Daily Averages:")
        print(f"    Sessions:          {historical['daily_average']['sessions']:>10.1f}")
        print(f"    Output Tokens:     {format_tokens(int(historical['daily_average']['output_tokens'])):>10}")
        print(f"    Cost:              {format_cost(historical['daily_average']['cost']):>10}")

        # Trends
        print(f"\n\n  USAGE TRENDS")
        print(f"  {'-'*50}")
        print(f"  Direction:           {trends['direction']:>10}")
        print(f"  Sessions Change:     {trends['sessions_change_pct']:>+9.1f}%")
        print(f"  Tokens Change:       {trends['tokens_change_pct']:>+9.1f}%")
        print(f"  Cost Change:         {trends['cost_change_pct']:>+9.1f}%")

        # Forecast
        print(f"\n\n  {forecast['days']}-DAY FORECAST (Confidence: {forecast['confidence']})")
        print(f"  {'-'*50}")
        print(f"  Projected Sessions:  {forecast['projected_sessions']:>10}")
        print(f"  Projected Tokens:    {format_tokens(forecast['projected_output_tokens']):>10}")
        print(f"  Projected Cost:      {format_cost(forecast['projected_cost']):>10}")

        # Daily history chart
        if data["daily_history"]:
            print(f"\n\n  DAILY TOKEN USAGE (Last 14 Days)")
            print(f"  {'-'*70}")
            max_tokens = max(d["output_tokens"] for d in data["daily_history"])
            for day in data["daily_history"]:
                bar_len = int(day["output_tokens"] / max_tokens * 40) if max_tokens > 0 else 0
                bar = "#" * bar_len
                print(f"  {day['date']} | {format_tokens(day['output_tokens']):>8} | {bar}")

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
