# Power BI Distance Relationship Decision

Decision date: 2026-07-17

Source branch: `feat/agentic-semantic-contract-m1`

Starting commit: `79c6d9e63900acf06c2b2b591c67e316084b24ef`

Canonical source: `models/semantic/triathlon_semantic.yml`

Baseline identifier: `PBI_RELATIONSHIP_DRIFT_FCT_RESULT_DISTANCE_ID`

## Finding

The canonical semantic metadata declares `fct_result.distance_id -> dim_distance.distance_id`. The generated Snowflake Semantic View contains the corresponding `results_to_distances` relationship, while the source Power BI TMDL does not contain that relationship.

The candidate Power BI columns both use the `string` data type. The dbt mart contract requires `dim_distance.distance_id` to be unique and not null, and it tests `fct_result.distance_id` for referential integrity against that key. This supports an expected many-to-one relationship from the result fact to the distance dimension.

## Existing Power BI Topology

Power BI already contains these active/default relationship paths:

- `dim_distance.distance -> dim_event.distance`
- `dim_event.event_id -> fct_result.event_id`

Together they allow filters to propagate from `dim_distance` through `dim_event` to `fct_result`. The relationship declarations do not explicitly override cardinality, cross-filter direction, or active state in TMDL. A direct canonical relationship intended to filter result rows would ordinarily need to be active, many-to-one, and single-direction from `dim_distance` to `fct_result`, but those effective properties must be confirmed in Power BI before any topology change.

Adding that direct relationship as active would introduce a second filter-propagation path between `dim_distance` and `fct_result`. Microsoft documents that only one active filter-propagation path can exist between two model tables; additional paths must be inactive and are used only when DAX explicitly activates them with `USERELATIONSHIP`. See [Model relationships in Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand).

## Usage and Result Risk

No checked-in measure DAX references `dim_distance`, `distance_id`, `USERELATIONSHIP`, or `CROSSFILTER`. However, a checked-in report visual combines `dim_distance.distance`, `dim_event` fields, and `fct_result` fields, so the current indirect path is behaviorally relevant.

An inactive direct relationship could satisfy the current structural signature comparison because that comparison inspects endpoints only; it would not provide the canonical default filter behavior. An active direct relationship could be rejected as ambiguous or could change filter behavior. Offline inspection cannot prove that either option preserves report results.

## Decision

Milestone 1 will not modify the source Power BI definition or change the canonical expectation. A Power BI model owner must review the effective relationship properties and choose whether to retain the indirect event path, replace it with the direct key relationship, or introduce an explicitly inactive relationship together with intentional DAX usage. Until that review occurs, strict validation may accept only this precisely identified baseline finding.

MANUAL_POWERBI_REVIEW_REQUIRED
