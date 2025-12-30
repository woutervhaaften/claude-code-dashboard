# Session Analysis Workflow

When user asks about a specific session or recent activity:

## Step 1: Run Anomaly Detection
```bash
PYTHONIOENCODING=utf-8 claude-insights anomalies --days 1
```

Check for:
- Tool loops (>20 calls to same tool)
- File loops (>10 accesses to same file)
- SQL loops (>10 queries)
- Token spikes (>500K output)
- Excessive agent spawning (>10 sub-agents)

## Step 2: Analyze Tool Usage
```bash
PYTHONIOENCODING=utf-8 claude-insights tools --days 1
```

Identify:
- Top token-consuming tools
- Most called MCPs
- Operations breakdown

## Step 3: Check Cache Efficiency
```bash
PYTHONIOENCODING=utf-8 claude-insights cache --days 1
```

Look for:
- Sessions with <60% cache hit rate
- Wasted cache tokens (created but not read)
- Projects with poor efficiency

## Step 4: Generate Report

Summarize findings:
- What caused high usage?
- What patterns to avoid?
- What CLAUDE.md rules to add?

## Response Template

```
## Session Analysis

### Summary
- Sessions analyzed: X
- Anomalies found: X
- Cache hit rate: X%

### Issues Detected
1. [Type] Description - Impact: X tokens

### Root Cause
The high usage was caused by [explanation].

### Recommendations
1. Add circuit breaker rule to CLAUDE.md
2. Use X instead of Y pattern
3. Consider caching Z
```
