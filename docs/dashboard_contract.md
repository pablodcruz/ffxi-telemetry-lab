# Dashboard contract

## Audience and decision

The default view is for stream viewers and project contributors who want to
know whether the autonomous agent is progressing and whether combat,
navigation, and MCP control are reliable. Operators use the same app locally
with a current DuckDB database; the public deployment uses a reviewed aggregate
snapshot.

## Metric roles

- Hero: completed fights, MCP operations and success, collision probes, and
  malformed row count.
- Progression: daily fight activity and milestone events. EXP is shown only when
  state-observer counters cover the period.
- Combat: engagement mix, rejection rate, target-cycle errors, action counts,
  and latency distributions.
- Navigation: collision probes, relocations, transitions, nudges, failures, and
  retries. Teleport operations are labeled as a proxy.
- Data quality: source coverage, uniqueness, event-time completeness,
  quarantine, and latest-session reconciliation.

## Visual map

| Section | Question | Visual | Grain | Palette |
| --- | --- | --- | --- | --- |
| Progression | Is autonomous activity moving over time? | Marked line | Day | Blue |
| Milestones | When were goals achieved? | Marked line | Day | Gold |
| Combat | What is the proactive/reactive mix? | Stacked bar | Day and mode | Blue/gold |
| Navigation | Which navigation signals dominate? | Grouped bar | Day and event | Five-category |
| MCP | Which operations dominate control volume? | Ranked horizontal bar | Operation | Blue |

All charts use a zero baseline for count comparisons, explicit titles, quiet
grid lines, and non-color labels or ordering. The public extract excludes raw
payloads, agent IDs, lease IDs, full Git SHAs, targets, and row-level records.
