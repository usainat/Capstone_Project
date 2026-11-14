# Part 1 Statistics and Probability

This folder contains the reproducible work for Part 1, Tasks 2 and 3.

## Files

- `calculate_statistics.py` reads the verified SQLite database, calculates all
  required results, validates key values, and writes deterministic JSON.
- `results.json` is the generated machine-readable result set.
- `statistics_probability_analysis.md` presents the methodology, calculations,
  interpretations and limitations in report form.

## Run the analysis

From the repository root:

```bash
python3 part1_data_analytics/statistics/calculate_statistics.py
```

The default input is:

```text
part1_data_analytics/sql/traffic_analysis.db
```

The default output is:

```text
part1_data_analytics/statistics/results.json
```

Use `--database` or `--output` to provide alternative paths. Internal progress
and validation information is written through Python logging rather than status
`print()` calls.
