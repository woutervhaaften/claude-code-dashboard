"""Base classes and utilities for insights analyzers."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

from claude_monitor.core.pricing import PricingCalculator

logger = logging.getLogger(__name__)

# Shared pricing calculator instance
_pricing_calculator = PricingCalculator()


class SessionData:
    """Container for processed session data."""

    def __init__(self, session_id: str, project: str):
        self.session_id = session_id
        self.project = project
        self.is_agent = session_id.startswith("agent-")
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read = 0
        self.cache_create = 0
        self.cost = 0.0
        self.tool_calls: Dict[str, int] = defaultdict(int)
        self.file_ops: Dict[str, int] = defaultdict(int)
        self.mcp_calls: Dict[str, int] = defaultdict(int)
        self.skill_calls: Dict[str, int] = defaultdict(int)
        self.timestamps: List[str] = []
        self.first_msg: Optional[str] = None
        self.entries: List[Dict[str, Any]] = []

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read + self.cache_create

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project": self.project,
            "is_agent": self.is_agent,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read": self.cache_read,
            "cache_create": self.cache_create,
            "cost": self.cost,
            "total_tokens": self.total_tokens,
            "tool_calls": dict(self.tool_calls),
            "mcp_calls": dict(self.mcp_calls),
            "skill_calls": dict(self.skill_calls),
            "first_msg": self.first_msg,
        }


class LogLoader:
    """Efficient JSONL log loader with streaming and filtering."""

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path or "~/.claude/projects").expanduser()
        self._processed_hashes: Set[str] = set()

    def get_date_range(self, days_back: int = 7, target_date: Optional[str] = None) -> List[str]:
        """Get list of target dates."""
        if target_date:
            return [target_date]
        today = datetime.now()
        return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_back)]

    def _create_unique_hash(self, entry: Dict[str, Any]) -> Optional[str]:
        """Create unique hash for deduplication (matches claude-monitor logic)."""
        message = entry.get('message', {})
        message_id = entry.get('message_id') or (
            message.get('id') if isinstance(message, dict) else None
        )
        request_id = entry.get('requestId') or entry.get('request_id')
        return f"{message_id}:{request_id}" if message_id and request_id else None

    def iter_sessions(
        self,
        target_dates: List[str],
        entry_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Iterator[SessionData]:
        """Iterate over sessions matching date filter.

        Args:
            target_dates: List of date strings (YYYY-MM-DD) to include
            entry_filter: Optional function to filter individual entries

        Yields:
            SessionData objects for each matching session
        """
        if not self.data_path.exists():
            logger.warning(f"Data path does not exist: {self.data_path}")
            return

        # Reset deduplication set for each iteration
        self._processed_hashes.clear()

        for project_dir in self.data_path.iterdir():
            if not project_dir.is_dir():
                continue

            project_name = project_dir.name

            for jsonl_file in project_dir.glob("*.jsonl"):
                session = self._process_session_file(
                    jsonl_file, project_name, target_dates, entry_filter
                )
                if session and session.output_tokens > 0:
                    yield session

    def _process_session_file(
        self,
        jsonl_file: Path,
        project_name: str,
        target_dates: List[str],
        entry_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Optional[SessionData]:
        """Process a single session JSONL file."""
        session_id = jsonl_file.stem
        session = SessionData(session_id, project_name)
        has_target_date = False

        try:
            with open(jsonl_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = entry.get('timestamp', '')

                        # Check if entry is in target date range
                        if not any(d in ts for d in target_dates):
                            continue

                        # Apply custom filter if provided
                        if entry_filter and not entry_filter(entry):
                            continue

                        # Deduplicate entries by message_id + request_id
                        unique_hash = self._create_unique_hash(entry)
                        if unique_hash:
                            if unique_hash in self._processed_hashes:
                                continue
                            self._processed_hashes.add(unique_hash)

                        has_target_date = True
                        session.timestamps.append(ts)
                        session.entries.append(entry)

                        self._extract_usage(entry, session)
                        self._extract_tool_calls(entry, session)
                        self._extract_first_message(entry, session)

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Error reading {jsonl_file}: {e}")
            return None

        return session if has_target_date else None

    def _extract_usage(self, entry: Dict[str, Any], session: SessionData) -> None:
        """Extract token usage from entry and calculate cost."""
        if 'message' not in entry:
            return

        message = entry['message']
        usage = message.get('usage', {})

        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        cache_read = usage.get('cache_read_input_tokens', 0)
        cache_create = usage.get('cache_creation_input_tokens', 0)

        session.output_tokens += output_tokens
        session.input_tokens += input_tokens
        session.cache_read += cache_read
        session.cache_create += cache_create

        # Calculate cost from tokens using pricing calculator
        model = message.get('model', 'claude-3-5-sonnet')
        cost = _pricing_calculator.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_create,
            cache_read_tokens=cache_read,
        )
        session.cost += cost

    def _extract_tool_calls(self, entry: Dict[str, Any], session: SessionData) -> None:
        """Extract tool call information from entry."""
        if entry.get('type') != 'assistant':
            return

        content = entry.get('message', {}).get('content', [])
        if not isinstance(content, list):
            return

        for item in content:
            if not isinstance(item, dict) or item.get('type') != 'tool_use':
                continue

            tool_name = item.get('name', 'unknown')
            session.tool_calls[tool_name] += 1

            # Categorize MCP calls
            if tool_name.startswith('mcp__'):
                session.mcp_calls[tool_name] += 1

            # Detect skill invocations
            if tool_name == 'Skill':
                skill_input = item.get('input', {})
                skill_name = skill_input.get('skill', 'unknown')
                session.skill_calls[skill_name] += 1

            # Track file operations
            inp = item.get('input', {})
            file_path = inp.get('file_path', inp.get('path', ''))
            if file_path:
                session.file_ops[file_path] += 1

    def _extract_first_message(self, entry: Dict[str, Any], session: SessionData) -> None:
        """Extract first user message as task description."""
        if session.first_msg is not None:
            return

        if entry.get('type') != 'user':
            return

        content = entry.get('message', {}).get('content', '')
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    session.first_msg = c.get('text', '')[:200]
                    break
        elif isinstance(content, str):
            session.first_msg = content[:200]


def format_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def format_cost(cost: float) -> str:
    """Format cost in USD."""
    if cost >= 1.0:
        return f"${cost:.2f}"
    return f"${cost:.4f}"
