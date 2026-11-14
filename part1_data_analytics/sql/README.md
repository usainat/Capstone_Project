# Part 1 SQL Traffic Analysis

This folder contains the reproducible SQLite work for Part 1, Task 1.

## Files

- `01_create_schema.sql` defines the typed traffic and metadata tables.
- `02_traffic_analysis.sql` contains import verification, annual trend, coverage,
  duplicate-hour sensitivity and holiday-temperature queries.
- `build_database.py` validates the supplied CSV and builds the database.
- `traffic_analysis.db` is the generated SQLite database.

## Build the database

From the repository root, run:

```bash
python3 part1_data_analytics/sql/build_database.py
```

To deliberately replace an existing generated database:

```bash
python3 part1_data_analytics/sql/build_database.py --overwrite
```

The default source file is `Metro_Interstate_Traffic_Volume.csv` in the
repository root. The builder validates the exact column order, converts data to
the declared SQLite types, records the source SHA-256 checksum, and verifies the
expected row and timestamp counts before publishing the database.

## Run the analysis

Using the SQLite command-line tool:

```bash
sqlite3 -header -column \
  part1_data_analytics/sql/traffic_analysis.db \
  < part1_data_analytics/sql/02_traffic_analysis.sql
```

You can also open `traffic_analysis.db` in DB Browser for SQLite and run the
queries from `02_traffic_analysis.sql` one section at a time.

## Interpretation cautions

- The dataset contains repeated timestamps with multiple weather descriptions.
  The repeated timestamps agree on traffic volume, but raw-record totals count
  some hours more than once. The analysis therefore reports both the requested
  raw-record total and a one-record-per-hour sensitivity result.
- Several years have incomplete coverage. In particular, 2012 begins in
  October, 2014 ends in August, and 2015 begins in June. Year-to-year total
  changes must not be interpreted as pure changes in traffic demand.
- There is no 2015 New Year's Day observation. The SQL intentionally returns a
  missing result instead of estimating or inventing one.
