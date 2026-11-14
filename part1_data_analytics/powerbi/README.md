# Part 1 Power BI Dashboard

This folder contains the reproducible preparation and verification materials for
Part 1, Task 4.

## Files

- `power_query.pq`: Power Query M script for the supplied CSV.
- `model_calculations.dax`: calculated columns and dashboard measures.
- `generate_control_totals.py`: generates verified dashboard comparison values.
- `expected_dashboard_values.json`: generated control totals.
- `POWER_BI_BUILD_GUIDE.md`: step-by-step dashboard construction instructions.
- `DASHBOARD_VERIFICATION_CHECKLIST.md`: final `.pbix` review checklist.
- `traffic_intelligence_dashboard.pbix`: to be created in Power BI Desktop on
  Windows and added after verification.

## Generate control totals

From the repository root:

```bash
python3 part1_data_analytics/powerbi/generate_control_totals.py
```

The generated JSON should be used to compare the Power BI results before the
dashboard is committed. Running the script does not create or modify a `.pbix`
file.

## Platform note

Power BI Desktop requires Windows. Do not substitute a fabricated or renamed
file for the required `.pbix`. Build it in Power BI Desktop, verify it against
the checklist, and confirm it opens successfully before submission.
