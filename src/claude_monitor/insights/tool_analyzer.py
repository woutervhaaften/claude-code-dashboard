"""Tool and MCP usage analyzer.

Tracks token consumption by tool, identifies expensive operations,
and provides recommendations for optimization.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .base import LogLoader, SessionData, format_tokens, format_cost

logger = logging.getLogger(__name__)


@dataclass
class ToolStats:
    """Statistics for a single tool."""
    name: str
    calls: int = 0
    sessions: Set[str] = field(default_factory=set)
    output_tokens: int = 0
    input_tokens: int = 0
    cost: float = 0.0

    @property
    def avg_tokens_per_call(self) -> float:
        return self.output_tokens / self.calls if self.calls > 0 else 0

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "sessions": self.session_count,
            "output_tokens": self.output_tokens,
            "input_tokens": self.input_tokens,
            "cost": self.cost,
            "avg_tokens_per_call": self.avg_tokens_per_call,
        }


@dataclass
class MCPStats:
    """Statistics for an MCP server."""
    server: str
    tools: Dict[str, ToolStats] = field(default_factory=dict)

    @property
    def total_calls(self) -> int:
        return sum(t.calls for t in self.tools.values())

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.tools.values())

    @property
    def total_cost(self) -> float:
        return sum(t.cost for t in self.tools.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server": self.server,
            "total_calls": self.total_calls,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "tools": {k: v.to_dict() for k, v in self.tools.items()},
        }


class ToolAnalyzer:
    """Analyzes tool and MCP usage patterns."""

    def __init__(self, data_path: Optional[str] = None):
        self.loader = LogLoader(data_path)
        self.tools: Dict[str, ToolStats] = {}
        self.mcps: Dict[str, MCPStats] = {}
        self.operations: Dict[str, int] = defaultdict(int)

    def analyze(
        self,
        days_back: int = 7,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze tool usage for the specified period.

        Args:
            days_back: Number of days to analyze
            target_date: Specific date (YYYY-MM-DD) to analyze

        Returns:
            Dictionary with tool statistics and recommendations
        """
        target_dates = self.loader.get_date_range(days_back, target_date)
        self._reset()

        total_output = 0
        total_cost = 0.0
        session_count = 0

        for session in self.loader.iter_sessions(target_dates):
            session_count += 1
            total_output += session.output_tokens
            total_cost += session.cost
            self._process_session(session)

        return {
            "period": {
                "start": target_dates[-1] if target_dates else None,
                "end": target_dates[0] if target_dates else None,
                "days": len(target_dates),
            },
            "summary": {
                "total_sessions": session_count,
                "total_output_tokens": total_output,
                "total_cost": total_cost,
            },
            "tools": self._get_top_tools(20),
            "mcps": self._get_mcp_breakdown(),
            "operations": dict(self.operations),
            "recommendations": self._generate_recommendations(),
        }

    def _reset(self) -> None:
        """Reset analyzer state."""
        self.tools = {}
        self.mcps = {}
        self.operations = defaultdict(int)

    def _process_session(self, session: SessionData) -> None:
        """Process a single session's tool usage."""
        # Calculate per-call token estimate (rough approximation)
        total_calls = sum(session.tool_calls.values())
        tokens_per_call = session.output_tokens / total_calls if total_calls > 0 else 0
        cost_per_call = session.cost / total_calls if total_calls > 0 else 0

        for tool_name, count in session.tool_calls.items():
            # Get or create tool stats
            if tool_name not in self.tools:
                self.tools[tool_name] = ToolStats(name=tool_name)

            stats = self.tools[tool_name]
            stats.calls += count
            stats.sessions.add(session.session_id)
            stats.output_tokens += int(tokens_per_call * count)
            stats.cost += cost_per_call * count

            # Categorize operations
            self._categorize_operation(tool_name, count)

            # Track MCP tools
            if tool_name.startswith('mcp__'):
                self._track_mcp_tool(tool_name, count, tokens_per_call, cost_per_call, session.session_id)

    def _categorize_operation(self, tool_name: str, count: int) -> None:
        """Categorize tool into operation type."""
        if tool_name in ['Read', 'Write', 'Edit', 'Glob', 'Grep']:
            self.operations['File Operations'] += count
        elif tool_name == 'Bash':
            self.operations['Shell Commands'] += count
        elif tool_name in ['Task', 'TaskOutput']:
            self.operations['Agent Spawning'] += count
        elif tool_name.startswith('mcp__'):
            self.operations['MCP Calls'] += count
        elif tool_name == 'Skill':
            self.operations['Skill Invocations'] += count
        elif tool_name in ['WebSearch', 'WebFetch']:
            self.operations['Web Operations'] += count
        elif tool_name in ['TodoWrite']:
            self.operations['Task Management'] += count
        else:
            self.operations['Other'] += count

    def _track_mcp_tool(
        self,
        tool_name: str,
        count: int,
        tokens_per_call: float,
        cost_per_call: float,
        session_id: str,
    ) -> None:
        """Track MCP server and tool usage."""
        parts = tool_name.split('__')
        if len(parts) >= 2:
            server = parts[1]
            operation = '__'.join(parts[2:]) if len(parts) > 2 else 'unknown'

            if server not in self.mcps:
                self.mcps[server] = MCPStats(server=server)

            mcp = self.mcps[server]
            if operation not in mcp.tools:
                mcp.tools[operation] = ToolStats(name=operation)

            tool_stats = mcp.tools[operation]
            tool_stats.calls += count
            tool_stats.sessions.add(session_id)
            tool_stats.output_tokens += int(tokens_per_call * count)
            tool_stats.cost += cost_per_call * count

    def _get_top_tools(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top tools by call count."""
        sorted_tools = sorted(
            self.tools.values(),
            key=lambda t: t.calls,
            reverse=True
        )
        return [t.to_dict() for t in sorted_tools[:limit]]

    def _get_mcp_breakdown(self) -> Dict[str, Any]:
        """Get MCP server breakdown."""
        return {
            server: mcp.to_dict()
            for server, mcp in sorted(
                self.mcps.items(),
                key=lambda x: x[1].total_calls,
                reverse=True
            )
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []

        # Check for heavy MCP usage
        for server, mcp in self.mcps.items():
            if mcp.total_calls > 100:
                recommendations.append(
                    f"High MCP usage: {server} ({mcp.total_calls} calls). "
                    f"Consider batching operations."
                )

        # Check for file operation patterns
        file_ops = self.operations.get('File Operations', 0)
        if file_ops > 200:
            recommendations.append(
                f"Heavy file operations ({file_ops} calls). "
                f"Consider using Explore agent for codebase searches."
            )

        # Check agent spawning
        agent_spawns = self.operations.get('Agent Spawning', 0)
        if agent_spawns > 50:
            recommendations.append(
                f"Frequent agent spawning ({agent_spawns} calls). "
                f"Consider consolidating related tasks."
            )

        # Check for specific expensive tools
        for tool in self.tools.values():
            if tool.calls > 50 and tool.avg_tokens_per_call > 5000:
                recommendations.append(
                    f"Expensive tool: {tool.name} ({tool.calls} calls, "
                    f"{format_tokens(int(tool.avg_tokens_per_call))} avg tokens/call)"
                )

        return recommendations if recommendations else ["No optimization issues detected."]

    def print_report(self, data: Dict[str, Any]) -> None:
        """Print formatted tool analysis report."""
        period = data["period"]
        summary = data["summary"]

        print("\n" + "=" * 90)
        print("  TOOL USAGE ANALYSIS")
        print(f"  Period: {period['start']} to {period['end']} ({period['days']} days)")
        print("=" * 90)

        print(f"\n  SUMMARY")
        print(f"  {'-'*50}")
        print(f"  Sessions:      {summary['total_sessions']:>10}")
        print(f"  Output Tokens: {format_tokens(summary['total_output_tokens']):>10}")
        print(f"  Total Cost:    {format_cost(summary['total_cost']):>10}")

        # Top tools
        print(f"\n\n  TOP TOOLS BY CALL COUNT")
        print(f"  {'-'*86}")
        print(f"  {'Tool':<40} | {'Calls':>8} | {'Sessions':>8} | {'Est. Tokens':>12}")
        print(f"  {'-'*86}")
        for tool in data["tools"][:15]:
            name = tool["name"][:40]
            print(f"  {name:<40} | {tool['calls']:>8} | {tool['sessions']:>8} | {format_tokens(tool['output_tokens']):>12}")

        # MCP breakdown
        if data["mcps"]:
            print(f"\n\n  MCP SERVER BREAKDOWN")
            print(f"  {'-'*86}")
            for server, mcp in list(data["mcps"].items())[:10]:
                print(f"\n  {server} ({mcp['total_calls']} total calls)")
                for op_name, op_stats in sorted(
                    mcp["tools"].items(),
                    key=lambda x: x[1]["calls"],
                    reverse=True
                )[:5]:
                    print(f"    - {op_name}: {op_stats['calls']} calls")

        # Operations breakdown
        print(f"\n\n  OPERATIONS BREAKDOWN")
        print(f"  {'-'*50}")
        for op, count in sorted(data["operations"].items(), key=lambda x: x[1], reverse=True):
            bar_len = min(30, int(count / max(data["operations"].values()) * 30))
            bar = "#" * bar_len
            print(f"  {op:<20} | {count:>6} | {bar}")

        # Recommendations
        print(f"\n\n  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for rec in data["recommendations"]:
            print(f"  - {rec}")

        print("\n" + "=" * 90)
