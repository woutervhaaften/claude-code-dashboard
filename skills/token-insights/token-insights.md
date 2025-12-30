# Token Insights Skill

Comprehensive token usage analysis and optimization recommendations for Claude Code.

## Description

Analyzes Claude Code token usage patterns using the `claude-insights` CLI tool suite. Provides proactive advice on optimization, anomaly detection, cache efficiency, and cost management.

## When to Use

Invoke this skill when the user:
- Asks about token usage or costs ("How much am I spending?", "Why is this session expensive?")
- Wants to understand usage patterns ("What tools use the most tokens?")
- Needs optimization advice ("How can I reduce token usage?")
- Reports unexpected behavior ("Why did this take so long?")
- Wants proactive monitoring ("Check for any issues")

## Available Analyses

| Command | Purpose |
|---------|---------|
| `claude-insights anomalies` | Detect loops, spikes, unusual patterns |
| `claude-insights tools` | Tool/MCP usage breakdown |
| `claude-insights cache` | Cache efficiency analysis |
| `claude-insights skills` | Skill performance metrics |
| `claude-insights predict` | Usage forecasting |
| `claude-insights roi` | Value analysis by domain |
| `claude-insights full` | Comprehensive report |

## Workflow

### Step 1: Quick Assessment
Run anomaly detection first to identify immediate issues:
```bash
claude-insights anomalies --days 1
```

### Step 2: Deep Dive (if needed)
Based on findings, run targeted analysis:
- High tool usage → `claude-insights tools`
- Low cache efficiency → `claude-insights cache`
- Cost concerns → `claude-insights roi`

### Step 3: Recommendations
Provide actionable recommendations:
1. Add CLAUDE.md rules for detected loops
2. Suggest workflow optimizations
3. Identify expensive patterns to avoid

## Output Format

Present findings as:

```
## Token Insights Summary

### Health Status
- [✓/!/X] Cache Efficiency: X%
- [✓/!/X] Anomaly Rate: X%
- [↑/↓/→] Usage Trend: direction

### Key Findings
1. Finding 1
2. Finding 2

### Recommendations
1. Recommendation 1
2. Recommendation 2
```

## Proactive Triggers

Use this skill proactively when:
- SessionStart hook detects previous session had anomalies
- User mentions "expensive", "slow", "loops", or "tokens"
- After completing a task that involved many tool calls

## Example Invocations

**User asks about token usage:**
> "Why was my last session so expensive?"
→ Run `claude-insights anomalies --days 1` and `claude-insights tools --days 1`

**User wants weekly summary:**
> "Give me a token usage summary"
→ Run `claude-insights full --days 7`

**User asks about specific date:**
> "What happened on December 28?"
→ Run `claude-insights anomalies --date 2025-12-28`

## Integration Notes

- Always use `PYTHONIOENCODING=utf-8` when running commands on Windows
- The `--json` flag outputs machine-readable data if needed for further processing
- Default analysis is 1 day; use `--days N` for longer periods
