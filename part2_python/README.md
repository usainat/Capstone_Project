# Part 2 Python Traffic Analytics

This folder contains the reproducible Python workflow required for Part 2. The
current stage implements Tasks 1–3: schema validation, cleaning, outlier
handling, hourly feature engineering, Matplotlib visualisation, output
validation and auditable logging.

## Set up the environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the cleaning pipeline

From the repository root, activate the virtual environment and run:

```bash
source .venv/bin/activate
python part2_python/pipeline.py
```

Default input:

```text
Metro_Interstate_Traffic_Volume.csv
```

Generated outputs:

```text
part2_python/data/processed/traffic_cleaned.csv
part2_python/data/processed/cleaning_summary.json
part2_python/logs/pipeline.log
```

Alternative paths and logging level can be supplied with:

```bash
python part2_python/pipeline.py \
  --input path/to/raw.csv \
  --output path/to/cleaned.csv \
  --summary path/to/summary.json \
  --log-file path/to/pipeline.log \
  --log-level DEBUG
```

## Cleaning decisions

- The nine-column schema and column order are validated before processing.
- The holiday text `None` remains a valid category and is not treated as null.
- Categorical whitespace is removed and weather descriptions are lower-cased.
- Date/time values are parsed using the explicit source format.
- Seventeen exact duplicates are removed.
- Repeated timestamps with distinct weather descriptions are preserved in the
  record-level cleaned output.
- Ten impossible `0 K` temperatures are imputed using January and February 2014
  medians.
- One rainfall value above 9,000 mm is imputed using the July 2016 median.
- Missing continuous values, if encountered, use month-specific medians.
- Missing traffic targets or negative traffic values are dropped with warnings.
- Two zero-traffic observations are retained because there is insufficient
  evidence that they are invalid.

The cleaned dataset contains 48,187 rows and 40,575 unique timestamps. A later
feature-engineering stage will create a separate one-row-per-hour modelling
table so weather-report duplicates do not leak across model splits.

## Logging configuration

Every module obtains a named logger with `logging.getLogger(__name__)`. Only
`pipeline.py` when used as the entry point configures handlers. Logs are written
to both the console and `part2_python/logs/pipeline.log` with:

- Timestamp
- Log level
- Module name
- Message

Levels are used as follows:

- `DEBUG`: detailed intermediate values used during troubleshooting.
- `INFO`: successful loads, validation steps, saved files and milestones.
- `WARNING`: recoverable changes such as standardisation, removal or imputation.
- `ERROR`: failures that prevent safe completion, with exception details.

No `print()` statement is used for internal pipeline status.

## Run feature engineering

After the cleaning pipeline completes, run:

```bash
python part2_python/feature_engineering.py
```

Generated outputs:

```text
part2_python/data/processed/traffic_features.csv
part2_python/data/processed/feature_metadata.json
part2_python/logs/feature_engineering.log
```

This stage consolidates repeated weather reports into one row per timestamp,
while first verifying that every repeated timestamp has a consistent traffic
target. It creates multi-hot weather flags, calendar and cyclical time features,
holiday/weekend indicators, derived weather indicators, log transforms and a
four-level quartile-based congestion target.

The resulting modelling table contains 40,575 unique hourly rows and 36
columns. The metadata records feature names, congestion thresholds, category
counts and exploratory scaling parameters. During machine-learning evaluation,
scalers must be refitted on the training partition only to prevent leakage.

Alternative paths and logging levels are available through:

```bash
python part2_python/feature_engineering.py --help
```

## Generate visualisations

After feature engineering completes, run:

```bash
python part2_python/visualizations.py
```

Generated outputs:

```text
part2_python/reports/figures/01_hourly_weekday_weekend.png
part2_python/reports/figures/02_traffic_distribution.png
part2_python/reports/figures/03_temperature_traffic_hexbin.png
part2_python/reports/figures/04_weather_average_traffic.png
part2_python/reports/visualization_summary.json
part2_python/logs/visualizations.log
```

The figures compare weekday and weekend demand, show the traffic-volume
distribution, examine the temperature relationship and compare average traffic
across multi-hot weather indicators. Each figure has a documented
interpretation in the summary file. Weather and temperature results are treated
as descriptive associations rather than causal effects.

Every completed figure is logged at `INFO` level with its saved path, as
required by the project instructions. Alternative paths and logging levels are
available through:

```bash
python part2_python/visualizations.py --help
```

## Run tests

```bash
pytest -q part2_python/tests
```
