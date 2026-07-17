# Supported Patterns

The existing POC recognizes a narrow deterministic subset:

- `basic_count`: a simple metric backed by `sum` or `count` of `1` or `*`.
- `filtered_count`: a simple metric backed by `sum_boolean` with one boolean equality such as `is_valid_sbr_finisher = 1`.
- `ratio`: a numerator metric divided by a denominator metric.

Existing target forms include:

- Power BI filtered count: `CALCULATE(COUNTROWS(...), ... = TRUE())`
- Power BI ratio: `DIVIDE([Numerator], [Denominator])`
- Snowflake filtered count: `COUNT_IF(...)`
- Snowflake ratio: `numerator / NULLIF(denominator, 0)`

Classify nested logic, unsupported operators, arbitrary DAX, ambiguous mappings, or uncertain relationship behavior as `MANUAL_REVIEW_REQUIRED`. Do not approximate equivalence.
