"""Graph visualizations for Claude Monitor.

This module provides beautiful terminal graphs for daily and monthly spend
using plotext library with Rich integration.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)


class SpendGraphs:
    """Creates beautiful terminal graphs for spend visualization."""

    # Color schemes for graphs
    DAILY_COLORS = ["cyan", "blue", "magenta", "green", "yellow", "red", "white"]
    MONTHLY_COLORS = ["green", "cyan", "blue", "magenta", "yellow"]

    def __init__(self, console: Optional[Console] = None):
        """Initialize the graph controller.

        Args:
            console: Optional Rich Console instance
        """
        self.console = console or Console()

    def create_daily_spend_graph(
        self,
        daily_data: List[Dict[str, Any]],
        width: int = 80,
        height: int = 15,
        title: str = "Daily Spend"
    ) -> str:
        """Create a beautiful daily spend bar graph.

        Args:
            daily_data: List of daily aggregated data with 'date' and 'total_cost'
            width: Graph width in characters
            height: Graph height in lines
            title: Graph title

        Returns:
            String representation of the graph
        """
        if not daily_data:
            return "No data available for daily graph"

        # Take last 14 days max for readability
        data = daily_data[-14:]

        # Extract dates and costs
        dates = []
        costs = []
        for d in data:
            # Parse date and format shorter
            date_str = d.get("date", "")
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    dates.append(dt.strftime("%m/%d"))
                except ValueError:
                    dates.append(date_str[-5:])
            else:
                dates.append("?")
            costs.append(d.get("total_cost", 0))

        # Clear and configure plotext
        plt.clear_figure()
        plt.plotsize(width, height)

        # Create bar chart with gradient colors based on cost
        max_cost = max(costs) if costs else 1
        colors = []
        for cost in costs:
            ratio = cost / max_cost if max_cost > 0 else 0
            if ratio > 0.8:
                colors.append("red+")
            elif ratio > 0.6:
                colors.append("orange+")
            elif ratio > 0.4:
                colors.append("yellow+")
            elif ratio > 0.2:
                colors.append("cyan+")
            else:
                colors.append("green+")

        plt.bar(dates, costs, color=colors, fill=True)

        # Styling
        plt.title(f"💰 {title} (Last {len(data)} Days)")
        plt.xlabel("Date")
        plt.ylabel("Cost (USD)")
        plt.theme("pro")  # Professional dark theme

        # Add grid for readability
        plt.grid(True, True)

        # Build the graph string
        return plt.build()

    def create_monthly_spend_graph(
        self,
        monthly_data: List[Dict[str, Any]],
        width: int = 80,
        height: int = 12,
        title: str = "Monthly Spend"
    ) -> str:
        """Create a beautiful monthly spend bar graph.

        Args:
            monthly_data: List of monthly aggregated data with 'month' and 'total_cost'
            width: Graph width in characters
            height: Graph height in lines
            title: Graph title

        Returns:
            String representation of the graph
        """
        if not monthly_data:
            return "No data available for monthly graph"

        # Take last 6 months max
        data = monthly_data[-6:]

        # Extract months and costs
        months = [d.get("month", "?") for d in data]
        costs = [d.get("total_cost", 0) for d in data]

        # Clear and configure plotext
        plt.clear_figure()
        plt.plotsize(width, height)

        # Create horizontal bar chart for months (more readable)
        colors = ["green", "cyan", "blue", "magenta", "yellow", "red"][:len(months)]

        # Calculate gradient colors based on cost
        max_cost = max(costs) if costs else 1
        bar_colors = []
        for cost in costs:
            ratio = cost / max_cost if max_cost > 0 else 0
            if ratio > 0.7:
                bar_colors.append("magenta+")
            elif ratio > 0.4:
                bar_colors.append("blue+")
            else:
                bar_colors.append("cyan+")

        plt.bar(months, costs, color=bar_colors, fill=True)

        # Styling
        plt.title(f"📊 {title}")
        plt.xlabel("Month")
        plt.ylabel("Cost (USD)")
        plt.theme("pro")
        plt.grid(True, True)

        # Note: plt.text has issues with categorical x-axis, so we skip value labels

        return plt.build()

    def create_token_breakdown_graph(
        self,
        data: Dict[str, Any],
        width: int = 60,
        height: int = 10,
        title: str = "Token Distribution"
    ) -> str:
        """Create a pie-like visualization of token breakdown.

        Args:
            data: Dictionary with token types and counts
            width: Graph width
            height: Graph height
            title: Graph title

        Returns:
            String representation of the graph
        """
        labels = ["Input", "Output", "Cache Create", "Cache Read"]
        values = [
            data.get("input_tokens", 0),
            data.get("output_tokens", 0),
            data.get("cache_creation_tokens", 0),
            data.get("cache_read_tokens", 0),
        ]

        # Filter out zero values
        non_zero = [(l, v) for l, v in zip(labels, values) if v > 0]
        if not non_zero:
            return "No token data available"

        labels, values = zip(*non_zero)

        plt.clear_figure()
        plt.plotsize(width, height)

        colors = ["cyan", "magenta", "yellow", "green"][:len(labels)]
        plt.bar(labels, values, color=colors)

        plt.title(f"🔢 {title}")
        plt.ylabel("Tokens")
        plt.theme("pro")

        return plt.build()

    def create_model_cost_graph(
        self,
        daily_data: List[Dict[str, Any]],
        width: int = 80,
        height: int = 12
    ) -> str:
        """Create a trend line graph showing cost over time.

        Args:
            daily_data: Daily data with per-model breakdown
            width: Graph width
            height: Graph height

        Returns:
            String representation of the graph
        """
        if not daily_data:
            return "No model data available"

        # Take last 7 days
        data = daily_data[-7:]

        # Extract costs and create labels
        costs = [d.get("total_cost", 0) for d in data]
        labels = []
        for d in data:
            date_str = d.get("date", "")
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    labels.append(dt.strftime("%a"))  # Day name
                except ValueError:
                    labels.append(date_str[-5:])
            else:
                labels.append("?")

        plt.clear_figure()
        plt.plotsize(width, height)

        # Use numeric x-axis for line plot (plotext has issues with string x-axis)
        x_vals = list(range(len(costs)))

        # Use line plot with markers for trend visualization
        plt.plot(x_vals, costs, marker="braille", color="cyan+")
        plt.scatter(x_vals, costs, color="magenta+", marker="dot")

        # Set custom x-tick labels
        plt.xticks(x_vals, labels)

        plt.title("📈 Spend Trend (Last 7 Days)")
        plt.xlabel("Day")
        plt.ylabel("Cost (USD)")
        plt.theme("pro")
        plt.grid(True, True)

        return plt.build()

    def create_combined_dashboard(
        self,
        daily_data: List[Dict[str, Any]],
        monthly_data: List[Dict[str, Any]],
        totals: Dict[str, Any],
        width: int = 100
    ) -> str:
        """Create a combined dashboard with multiple graphs.

        Args:
            daily_data: Daily aggregated data
            monthly_data: Monthly aggregated data
            totals: Total statistics
            width: Total width

        Returns:
            Combined dashboard string
        """
        sections = []

        # Daily spend graph
        daily_graph = self.create_daily_spend_graph(daily_data, width=width, height=12)
        sections.append(daily_graph)
        sections.append("")

        # Trend line
        trend_graph = self.create_model_cost_graph(daily_data, width=width, height=10)
        sections.append(trend_graph)
        sections.append("")

        # Monthly graph (if data available)
        if monthly_data:
            monthly_graph = self.create_monthly_spend_graph(monthly_data, width=width, height=10)
            sections.append(monthly_graph)
            sections.append("")

        # Token breakdown
        if totals:
            token_graph = self.create_token_breakdown_graph(totals, width=width//2, height=8)
            sections.append(token_graph)

        return "\n".join(sections)

    def print_daily_graph(self, daily_data: List[Dict[str, Any]]) -> None:
        """Print daily spend graph to console.

        Args:
            daily_data: Daily aggregated data
        """
        graph = self.create_daily_spend_graph(daily_data)
        self.console.print(Panel(
            graph,
            title="[bold cyan]Daily Spend Analysis[/]",
            border_style="cyan",
            padding=(1, 2)
        ))

    def print_monthly_graph(self, monthly_data: List[Dict[str, Any]]) -> None:
        """Print monthly spend graph to console.

        Args:
            monthly_data: Monthly aggregated data
        """
        graph = self.create_monthly_spend_graph(monthly_data)
        self.console.print(Panel(
            graph,
            title="[bold green]Monthly Spend Analysis[/]",
            border_style="green",
            padding=(1, 2)
        ))

    def print_dashboard(
        self,
        daily_data: List[Dict[str, Any]],
        monthly_data: List[Dict[str, Any]],
        totals: Dict[str, Any]
    ) -> None:
        """Print full dashboard with all graphs.

        Args:
            daily_data: Daily aggregated data
            monthly_data: Monthly aggregated data
            totals: Total statistics
        """
        dashboard = self.create_combined_dashboard(daily_data, monthly_data, totals)
        self.console.print(Panel(
            dashboard,
            title="[bold magenta]Claude Usage Dashboard[/]",
            border_style="magenta",
            padding=(1, 2)
        ))


def create_spend_summary_box(
    daily_data: List[Dict[str, Any]],
    monthly_data: List[Dict[str, Any]]
) -> str:
    """Create a summary statistics box.

    Args:
        daily_data: Daily data
        monthly_data: Monthly data

    Returns:
        Formatted summary string
    """
    # Calculate stats
    total_daily_cost = sum(d.get("total_cost", 0) for d in daily_data)
    avg_daily_cost = total_daily_cost / len(daily_data) if daily_data else 0
    max_daily_cost = max((d.get("total_cost", 0) for d in daily_data), default=0)
    min_daily_cost = min((d.get("total_cost", 0) for d in daily_data), default=0)

    total_monthly_cost = sum(d.get("total_cost", 0) for d in monthly_data)

    lines = [
        "╔══════════════════════════════════════════╗",
        "║          📊 SPEND SUMMARY                ║",
        "╠══════════════════════════════════════════╣",
        f"║  Daily Average:     ${avg_daily_cost:>10.2f}       ║",
        f"║  Daily Max:         ${max_daily_cost:>10.2f}       ║",
        f"║  Daily Min:         ${min_daily_cost:>10.2f}       ║",
        "╠══════════════════════════════════════════╣",
        f"║  Period Total:      ${total_daily_cost:>10.2f}       ║",
        f"║  Monthly Total:     ${total_monthly_cost:>10.2f}       ║",
        "╚══════════════════════════════════════════╝",
    ]

    return "\n".join(lines)
