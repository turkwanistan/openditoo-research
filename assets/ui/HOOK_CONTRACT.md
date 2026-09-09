# Suggested Hook Contract

This is a suggested logical interface for wiring the UI to MCP activity hooks.

## MCP identities

Recommended internal IDs:

- `optiplex_lab`
- `optiplex_mcp`
- `wsl_mcp`

## Suggested state model

```json
{
  "mcps": {
    "optiplex_lab": {
      "connected": true,
      "last_seen_seconds_ago": 12,
      "status": "green",
      "activity_pulse": false
    },
    "optiplex_mcp": {
      "connected": true,
      "last_seen_seconds_ago": 480,
      "status": "yellow",
      "activity_pulse": false
    },
    "wsl_mcp": {
      "connected": true,
      "last_seen_seconds_ago": 2400,
      "status": "red",
      "activity_pulse": false
    }
  }
}
```

## Status derivation

Suggested derivation:

- if disconnected or no valid heartbeat / no data: `grey`
- else if `last_seen_seconds_ago < 300`: `green`
- else if `last_seen_seconds_ago < 1200`: `yellow`
- else: `red`

## Activity trigger

When an event is received for one MCP:

1. mark that column as active;
2. run the blue activity animation for ~4 pulse frames;
3. blue-override the letter + icon accent during those frames;
4. revert to derived state color.

## Event examples

### Message / packet event
```json
{
  "type": "mcp_activity",
  "mcp_id": "wsl_mcp",
  "timestamp": "2026-09-09T00:00:00Z"
}
```

### Heartbeat / connectivity update
```json
{
  "type": "mcp_status",
  "mcp_id": "optiplex_mcp",
  "connected": true,
  "last_seen_seconds_ago": 42
}
```

## Open questions for implementor

- whether idle and disconnected should remain combined as grey or split later;
- frame cadence / duration on real hardware;
- whether multiple simultaneous events should queue or merge.

