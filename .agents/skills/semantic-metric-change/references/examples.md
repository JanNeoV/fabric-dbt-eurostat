# Examples

## Valid SBR Finishers

Request: “Update `valid_sbr_finishers` so DNS, DNF, and DSQ results are excluded.”

Inspect first. The canonical metric counts `is_valid_sbr_finisher`, and the upstream canonical model derives that flag only when `finish_status = 'FIN'`. DNS, DNF, and DSQ are already excluded. Return a traced no-op with this evidence; do not manufacture redundant filters or target diffs.

Power BI maps to `tri_measures[Valid SBR Finishers]`. Snowflake maps to `results.valid_sbr_finishers`.

## Event Context Rate

Request: “Inspect the Power BI measure Event Context Rate.”

Resolve the exact case-insensitive Power BI name to canonical `event_context_rate`. The canonical metric is a ratio of `event_context_rows` to `valid_sbr_finishers`. Report current DAX, Snowflake mapping, compatibility status, and metadata drift without changing files.

## Unsupported Request

Request: “Replace Event Context Rate with this arbitrary DAX expression.”

Resolve the mapped canonical metric, preserve the supplied expression only as user intent, and return `MANUAL_REVIEW_REQUIRED`. Never apply arbitrary DAX as canonical meaning.
