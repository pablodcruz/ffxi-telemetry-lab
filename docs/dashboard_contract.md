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
- Progression: daily fight activity, milestone events, EXP, and gil. EXP and
  gil trends use consecutive state-observer counter deltas only.
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
| EXP velocity | Is leveling pace improving? | Small-multiple bars | Hour/day/week | Violet |
| Gil velocity | Is earning pace improving? | Small-multiple bars | Hour/day/week | Gold |
| Combat | What is the proactive/reactive mix? | Stacked bar | Day and mode | Blue/gold |
| Navigation | Which navigation signals dominate? | Grouped bar | Day and event | Five-category |
| MCP | Which operations dominate control volume? | Ranked horizontal bar | Operation | Blue |

All charts use a zero baseline for count comparisons, explicit titles, quiet
grid lines, and non-color labels or ordering. The public extract excludes raw
payloads, agent IDs, lease IDs, full Git SHAs, targets, and row-level records.

EXP/hour and gil/hour are weighted rates:

`sum(counter delta) / sum(active elapsed-time delta) * 3600`

Hourly rates are never added together. Day and week views recompute the rate
from their aggregate numerator and denominator. The same buckets also expose
the period total. Minute grain is intentionally local-only because short combat
bursts make it too volatile for the public progression view. Intervals are
excluded when counters reset, active time is non-positive, or the observer gap
exceeds five minutes. Visible dates use America/New_York boundaries.
