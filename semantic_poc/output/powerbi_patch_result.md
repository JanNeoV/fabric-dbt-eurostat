# Power BI Patch Result

Applied:
- Event Context Rate: formatString -> 0.0%
- Event Context Rate: displayFolder -> 03 Rates
- Record Integrity Rate: formatString -> 0.0%
- Record Integrity Rate: displayFolder -> 03 Rates
- Individual Profile Rate: formatString -> 0.0%
- Individual Profile Rate: displayFolder -> 03 Rates
- Model Residual Rate: formatString -> 0.0%
- Model Residual Rate: displayFolder -> 03 Rates
- Individual Hard Flag Rate: formatString -> 0.0%
- Individual Hard Flag Rate: displayFolder -> 03 Rates

Skipped:
- fct_result.distance_id -> dim_distance.distance_id
  Reason: structural changes are outside the safe patch scope

Protected properties:
- DAX expressions unchanged
- lineage tags unchanged
- relationships unchanged
- partitions unchanged
- table and column counts unchanged
- measure counts unchanged

Output: `semantic_poc/output/patched_powerbi_definition`
Status: success
