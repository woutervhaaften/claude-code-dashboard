# Optimization Tips Reference

Common optimization patterns based on detected issues.

## Tool Loop Patterns

### SQL Query Loops
**Problem**: Multiple individual queries instead of JOINs
**Solution**: Add to CLAUDE.md:
```markdown
### SQL Efficiency
- Maximum 10 SQL queries per request
- Use JOINs instead of N+1 queries
- Cache schema information after first read
```

### File Access Loops
**Problem**: Same file read repeatedly in session
**Solution**:
- Cache file contents in memory
- Use Explore agent for codebase searches
- Read files once at start of task

### Agent Spawning Loops
**Problem**: Too many sub-agents for related tasks
**Solution**:
- Consolidate related tasks in primary session
- Limit sub-agents to 5 per request
- Use agents only for truly independent tasks

## Cache Optimization

### Low Cache Hit Rate (<60%)
**Causes**:
- Short sessions (new context each time)
- Frequent topic switches
- Different projects

**Solutions**:
- Use `claude --continue` to resume sessions
- Stay on topic longer before switching
- Batch related tasks in single session

### High Cache Creation, Low Cache Read
**Cause**: Creating context that isn't reused
**Solution**: Keep sessions longer to amortize cache cost

## MCP Optimization

### High MCP Call Count
**Pattern**: Many small operations
**Solution**:
- Batch operations where supported (e.g., `pipedrive_batch`)
- Fetch related data in single query
- Cache MCP results when appropriate

### Expensive MCPs
**Pattern**: MCPs with large token overhead
**Solution**:
- Use `forceDownload=true` for large results
- Filter queries to return only needed data
- Consider local alternatives

## Circuit Breaker Rules

Add to project CLAUDE.md:
```markdown
## Circuit Breaker Pattern

If you detect any of these patterns, STOP and ask the user:
- More than 10 SQL queries for a single request
- Same table queried more than 3 times
- Same file edited more than 5 times
- INSERT/UPDATE/DELETE loop exceeds 5 operations
```

## General Best Practices

1. **Read before writing**: Understand existing code before modifying
2. **Use Explore agent**: For open-ended codebase searches
3. **Cache schema info**: Don't re-query table structures
4. **Batch operations**: Group related changes
5. **Long sessions**: Maximize cache reuse
6. **Clear task scope**: Avoid scope creep mid-session
