# Weekly Summary Workflow

Generate a comprehensive weekly token usage summary.

## Step 1: Run Full Analysis
```bash
PYTHONIOENCODING=utf-8 claude-insights full --days 7
```

## Step 2: Extract Key Metrics

From the output, note:
- Total sessions and tokens
- Cache hit rate
- Anomaly rate
- Usage trend direction
- Top consuming projects
- Forecast confidence

## Step 3: Identify Patterns

Look for:
- Days with unusual spikes
- Projects consuming most tokens
- Recurring anomaly types
- Efficiency improvements/declines

## Step 4: Generate Summary

### Response Template

```
## Weekly Token Usage Summary (Dec 23-30)

### Overview
| Metric | Value |
|--------|-------|
| Total Sessions | X |
| Output Tokens | X |
| Cache Hit Rate | X% |
| Anomalies | X |

### Health Indicators
- ✓ Cache Efficiency: GOOD/NEEDS ATTENTION
- ✓ Anomaly Rate: LOW/MEDIUM/HIGH
- ↑ Usage Trend: INCREASING/STABLE/DECREASING

### Top Projects by Usage
1. [Project] - X tokens (X%)
2. [Project] - X tokens (X%)
3. [Project] - X tokens (X%)

### Notable Events
- [Date]: [Event description]
- [Date]: [Event description]

### Recommendations
1. [Actionable recommendation]
2. [Actionable recommendation]

### Next Week Forecast
- Projected tokens: X
- Projected cost: $X
- Confidence: LOW/MEDIUM/HIGH
```

## Optional: Historical Comparison

If user wants trends, run:
```bash
PYTHONIOENCODING=utf-8 claude-insights predict
```

Compare current week to previous weeks to show improvement or regression.
