# Claude Code Usage Monitor

A real-time terminal monitoring tool for Claude Code token usage with beautiful graphs and analytics.

## Commands

| Command | Description |
|---------|-------------|
| `claude-monitor` | Live realtime dashboard showing current session token usage, cost, and progress |
| `claude-monitor --view daily` | Daily usage table with spend graph (last 14 days) |
| `claude-monitor --view monthly` | Monthly usage table with spend graph |
| `claude-dashboard` | Combined daily + monthly view in one scrollable output |

## Installation

```bash
# Clone and install in editable mode
git clone https://github.com/woutervhaaften/claude-code-dashboard.git ~/.claude/usage-monitor
pip install -e ~/.claude/usage-monitor --user
```

## Features

- **Realtime monitoring**: Live token usage tracking with progress indicators
- **Daily/Monthly views**: Aggregated statistics with visual graphs (plotext)
- **Cost tracking**: USD cost calculation per session, day, and month
- **Token breakdown**: Input, output, cache creation, and cache read tokens
- **Beautiful UI**: Rich terminal interface with clean, non-distracting graphs

## Configuration

Settings are auto-saved to `~/.claude-monitor/last_used.json`. Clear with:
```bash
claude-monitor --clear
```

### Options

- `--plan {pro,max5,max20,custom}` - Your Claude subscription plan
- `--view {realtime,daily,monthly,session}` - View mode (default: realtime)
- `--timezone` - Display timezone (auto-detected)
- `--theme {light,dark,classic,auto}` - Color theme
- `--refresh-rate` - Data refresh interval in seconds (default: 10)

## Data Source

Reads JSONL conversation logs from `~/.claude/projects/` containing token counts and cost data.

## Dependencies

- rich (terminal UI)
- plotext (terminal graphs)
- pydantic (settings)
- numpy, pytz, pyyaml

## Customizations

This fork includes:
- Simplified monochrome graphs (less visual noise)
- Combined dashboard script (`claude-dashboard`)
- Windows compatibility improvements
