# NM observer contract

The NM carousel consumes an optional hourly, allowlisted snapshot produced by a
future read-only LandSandBoat map observer. The gameplay agent never calls or
waits for this observer. If the file is missing, partial, stale, or rejected,
gameplay and the rest of the telemetry refresh continue independently.

Set the ignored environment variable `TELEMETRY_NM_STATE_PATH` to the observer
file. The collector opens it read-only. The producer should replace the file
atomically and should never write game state or analytics tables.

## Accepted shape

```json
{
  "schema_version": 1,
  "observed_at": "2026-07-31T12:00:00Z",
  "map_started_at": "2026-07-27T10:10:37Z",
  "ruleset_git_sha": "0123456789abcdef",
  "nms": [
    {
      "nm_key": "valkurm-emperor",
      "status": "lottery_open",
      "cooldown_opens_at": "2026-07-31T09:58:53Z",
      "cooldown_remaining_seconds": 0,
      "is_spawned": false,
      "is_primed": false,
      "placeholder_status": "alive",
      "last_observed_kill_at": "2026-07-31T09:58:52Z",
      "next_lottery_opportunity_at": null,
      "effective_chance_percent": 10,
      "effective_cooldown_seconds": 1
    }
  ]
}
```

Accepted statuses are:

- `spawned`
- `primed`
- `cooldown_blocked`
- `lottery_open`
- `unknown`

The exporter rejects unknown NM keys, unexpected root or row fields, invalid
statuses, and any non-allowlisted content. It publishes only the first eight
characters of the observer's ruleset SHA. A direct observation older than two
hours becomes `unknown` in the public snapshot and is labeled stale.

The canonical 20-NM catalog, display order, artwork provenance, placeholder,
and pinned default rules live in `site/public/data/nm_catalog.json`.
