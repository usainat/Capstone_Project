"""Build the one-row-per-hour modelling table for the traffic capstone."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
CLEANED_COLUMNS = [
    "holiday",
    "temp",
    "rain_1h",
    "snow_1h",
    "clouds_all",
    "weather_main",
    "weather_description",
    "date_time",
    "traffic_volume",
]
CONGESTION_LABELS = ["Low", "Medium", "High", "Severe"]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Create an hourly feature table from the cleaned traffic data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=script_directory / "data/processed/traffic_cleaned.csv",
        help="Path to the cleaned record-level CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_directory / "data/processed/traffic_features.csv",
        help="Path for the hourly feature CSV.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=script_directory / "data/processed/feature_metadata.json",
        help="Path for feature definitions and audit metadata.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=script_directory / "logs/feature_engineering.log",
        help="Path for the feature-engineering log file.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum logging level for console and file output.",
    )
    return parser.parse_args()


def configure_logging(log_file: Path, level_name: str = "INFO") -> None:
    """Configure console and file handlers for this entry point only."""
    level = getattr(logging, level_name.upper())
    log_file = log_file.resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.handlers.clear()
    LOGGER.setLevel(level)
    LOGGER.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    LOGGER.addHandler(console_handler)
    LOGGER.addHandler(file_handler)
    LOGGER.info("Logging configured at %s level; file=%s", level_name, log_file)


def load_cleaned_csv(input_path: Path) -> pd.DataFrame:
    """Load the cleaned CSV while preserving the literal holiday value None."""
    try:
        frame = pd.read_csv(input_path, keep_default_na=False)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Cleaned CSV was not found: {input_path}. Run pipeline.py first."
        ) from exc
    except UnicodeDecodeError as exc:
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            "cleaned CSV encoding could not be decoded",
        ) from exc
    except pd.errors.ParserError as exc:
        raise pd.errors.ParserError(f"Cleaned CSV could not be parsed: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Cleaned CSV could not be read: {input_path}") from exc

    LOGGER.info(
        "Loaded cleaned CSV %s with %d rows and %d columns",
        input_path.name,
        *frame.shape,
    )
    return frame


def validate_and_convert_input(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the cleaned schema, data types and target consistency."""
    if frame.columns.tolist() != CLEANED_COLUMNS:
        missing = sorted(set(CLEANED_COLUMNS) - set(frame.columns))
        unexpected = sorted(set(frame.columns) - set(CLEANED_COLUMNS))
        raise ValueError(
            "Cleaned schema mismatch: "
            f"missing={missing}, unexpected={unexpected}, "
            f"order_matches={frame.columns.tolist() == CLEANED_COLUMNS}"
        )

    working = frame.copy(deep=True)
    working["date_time"] = pd.to_datetime(
        working["date_time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )
    if working["date_time"].isna().any():
        invalid_count = int(working["date_time"].isna().sum())
        raise ValueError(f"date_time contains {invalid_count} invalid values")

    numeric_columns = [
        "temp",
        "rain_1h",
        "snow_1h",
        "clouds_all",
        "traffic_volume",
    ]
    for column in numeric_columns:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    missing_numeric = {
        column: int(working[column].isna().sum())
        for column in numeric_columns
        if working[column].isna().any()
    }
    if missing_numeric:
        raise ValueError(f"Cleaned numerical values are missing or invalid: {missing_numeric}")

    target_conflicts = int(
        working.groupby("date_time")["traffic_volume"].nunique().gt(1).sum()
    )
    if target_conflicts:
        raise ValueError(
            f"Found {target_conflicts} timestamps with conflicting traffic targets"
        )
    LOGGER.info("Input validation and traffic-target consistency checks passed")
    return working


def _select_holiday(values: pd.Series) -> str:
    """Retain the non-default holiday label for an hourly group, if present."""
    labelled = sorted({str(value) for value in values if str(value) != "None"})
    return labelled[0] if labelled else "None"


def _any_weather(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Return a binary indicator for the presence of any available flag."""
    existing = [column for column in columns if column in frame.columns]
    if not existing:
        return pd.Series(0, index=frame.index, dtype="int8")
    return frame[existing].max(axis=1).astype("int8")


def engineer_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Consolidate records by hour and create reviewed modelling features."""
    cleaned = validate_and_convert_input(frame)
    input_rows = len(cleaned)

    hourly = (
        cleaned.groupby("date_time", as_index=False)
        .agg(
            holiday=("holiday", _select_holiday),
            temp=("temp", "median"),
            rain_1h=("rain_1h", "max"),
            snow_1h=("snow_1h", "max"),
            clouds_all=("clouds_all", "median"),
            traffic_volume=("traffic_volume", "first"),
        )
    )
    LOGGER.info(
        "Consolidated %d records into %d unique hourly rows",
        input_rows,
        len(hourly),
    )

    weather_flags = pd.crosstab(cleaned["date_time"], cleaned["weather_main"])
    weather_flags = weather_flags.clip(upper=1).astype("int8")
    weather_flags.columns = [
        f"weather_{column}" for column in weather_flags.columns
    ]
    weather_flags = weather_flags.reset_index()

    description_severity = (
        cleaned.assign(
            _description_severe=cleaned["weather_description"]
            .str.contains(
                r"heavy|thunderstorm|squall|freezing",
                case=False,
                regex=True,
                na=False,
            )
            .astype("int8")
        )
        .groupby("date_time", as_index=False)["_description_severe"]
        .max()
    )

    features = hourly.merge(
        weather_flags,
        on="date_time",
        how="left",
        validate="one_to_one",
    )
    features = features.merge(
        description_severity,
        on="date_time",
        how="left",
        validate="one_to_one",
    )
    weather_columns = sorted(
        column for column in features.columns if column.startswith("weather_")
    )
    LOGGER.info("Created %d multi-hot weather features", len(weather_columns))
    LOGGER.debug("Weather feature columns: %s", weather_columns)

    features["hour"] = features["date_time"].dt.hour.astype("int8")
    features["day_of_week"] = features["date_time"].dt.day_of_week.astype("int8")
    features["year"] = features["date_time"].dt.year.astype("int16")
    features["month"] = features["date_time"].dt.month.astype("int8")
    features["is_weekend"] = features["day_of_week"].isin([5, 6]).astype("int8")
    features["is_holiday"] = features["holiday"].ne("None").astype("int8")

    features["hour_sin"] = np.sin(2 * np.pi * features["hour"] / 24)
    features["hour_cos"] = np.cos(2 * np.pi * features["hour"] / 24)
    features["day_sin"] = np.sin(2 * np.pi * features["day_of_week"] / 7)
    features["day_cos"] = np.cos(2 * np.pi * features["day_of_week"] / 7)

    features["is_precipitation"] = (
        _any_weather(
            features,
            [
                "weather_Rain",
                "weather_Drizzle",
                "weather_Snow",
                "weather_Thunderstorm",
                "weather_Squall",
            ],
        ).eq(1)
        | features["rain_1h"].gt(0)
        | features["snow_1h"].gt(0)
    ).astype("int8")
    features["is_low_visibility"] = _any_weather(
        features,
        ["weather_Mist", "weather_Fog", "weather_Haze", "weather_Smoke"],
    )
    features["is_severe_weather"] = (
        _any_weather(features, ["weather_Thunderstorm", "weather_Squall"]).eq(1)
        | features["_description_severe"].eq(1)
    ).astype("int8")
    features = features.drop(columns=["_description_severe"])
    LOGGER.info("Created time, cyclical, holiday and derived weather indicators")

    scaling_parameters: dict[str, dict[str, float]] = {}
    for source_column, output_column in [
        ("temp", "temp_zscore"),
        ("clouds_all", "clouds_all_zscore"),
    ]:
        mean_value = float(np.mean(features[source_column]))
        standard_deviation = float(np.std(features[source_column], ddof=0))
        if standard_deviation == 0:
            raise ValueError(f"Cannot scale constant feature {source_column}")
        features[output_column] = (
            features[source_column] - mean_value
        ) / standard_deviation
        scaling_parameters[source_column] = {
            "mean": mean_value,
            "population_standard_deviation": standard_deviation,
        }
        LOGGER.debug(
            "Scaling parameters for %s: mean=%.6f std=%.6f",
            source_column,
            mean_value,
            standard_deviation,
        )

    features["rain_log1p"] = np.log1p(features["rain_1h"])
    features["snow_log1p"] = np.log1p(features["snow_1h"])
    LOGGER.info("Created two z-score features and two log-transformed features")

    q1, q2, q3 = (
        float(value)
        for value in features["traffic_volume"]
        .quantile([0.25, 0.50, 0.75])
        .tolist()
    )
    LOGGER.debug(
        "Congestion quartiles: q1=%.4f q2=%.4f q3=%.4f", q1, q2, q3
    )

    def bucket_congestion(value: float) -> str:
        if value <= q1:
            return "Low"
        if value <= q2:
            return "Medium"
        if value <= q3:
            return "High"
        return "Severe"

    features["congestion_category"] = pd.Categorical(
        features["traffic_volume"].map(bucket_congestion),
        categories=CONGESTION_LABELS,
        ordered=True,
    )
    features = features.sort_values("date_time").reset_index(drop=True)

    target_counts = features["congestion_category"].value_counts(sort=False)
    metadata: dict[str, Any] = {
        "input_record_rows": input_rows,
        "output_hourly_rows": len(features),
        "records_consolidated": input_rows - len(features),
        "output_columns": len(features.columns),
        "date_range": {
            "start": features["date_time"].min().strftime("%Y-%m-%d %H:%M:%S"),
            "end": features["date_time"].max().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "weather_feature_columns": weather_columns,
        "weather_feature_count": len(weather_columns),
        "congestion_thresholds": {"q1": q1, "q2": q2, "q3": q3},
        "congestion_category_counts": {
            label: int(target_counts[label]) for label in CONGESTION_LABELS
        },
        "scaling_parameters": scaling_parameters,
        "scaling_note": (
            "These full-dataset z-scores are exploratory features only. Refit all "
            "scalers using training data only during model evaluation."
        ),
        "missing_values": int(features.isna().sum().sum()),
        "duplicate_timestamps": int(features["date_time"].duplicated().sum()),
        "feature_columns": features.columns.tolist(),
    }
    validate_feature_table(features, weather_columns)
    LOGGER.info(
        "Feature engineering completed: output_rows=%d output_columns=%d",
        len(features),
        len(features.columns),
    )
    return features, metadata


def validate_feature_table(
    features: pd.DataFrame, weather_columns: list[str]
) -> None:
    """Stop if the engineered table violates modelling-table guarantees."""
    failures: list[str] = []
    if features.empty:
        failures.append("feature table is empty")
    if features.isna().any().any():
        failures.append("missing values remain")
    if features["date_time"].duplicated().any():
        failures.append("duplicate timestamps remain")
    if not features["date_time"].is_monotonic_increasing:
        failures.append("timestamps are not sorted")
    if not features[weather_columns].isin([0, 1]).all().all():
        failures.append("weather flags are not binary")
    if not features["congestion_category"].isin(CONGESTION_LABELS).all():
        failures.append("unexpected congestion category exists")
    cyclic_columns = ["hour_sin", "hour_cos", "day_sin", "day_cos"]
    if not features[cyclic_columns].apply(
        lambda series: series.between(-1, 1).all()
    ).all():
        failures.append("cyclical feature is outside -1 to 1")
    if failures:
        raise ValueError("Feature-table validation failed: " + "; ".join(failures))
    LOGGER.info("Feature-table validation passed")


def write_outputs(
    features: pd.DataFrame,
    metadata: dict[str, Any],
    output_path: Path,
    metadata_path: Path,
) -> None:
    """Atomically write the feature CSV and its JSON audit metadata."""
    output_path = output_path.resolve()
    metadata_path = metadata_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_csv = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_json = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    try:
        features.to_csv(
            temporary_csv,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
        )
        temporary_json.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_csv, output_path)
        os.replace(temporary_json, metadata_path)
    except OSError:
        for temporary_path in (temporary_csv, temporary_json):
            if temporary_path.exists():
                temporary_path.unlink()
        LOGGER.error("Could not write feature-engineering outputs", exc_info=True)
        raise

    LOGGER.info("Saved hourly feature table to %s", output_path)
    LOGGER.info("Saved feature metadata to %s", metadata_path)


def run_feature_engineering(
    input_path: Path,
    output_path: Path,
    metadata_path: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run feature engineering without configuring logging handlers."""
    cleaned = load_cleaned_csv(input_path.resolve())
    features, metadata = engineer_features(cleaned)
    write_outputs(features, metadata, output_path, metadata_path)
    return features, metadata


def main() -> int:
    """Configure logging, run feature engineering and exit gracefully."""
    args = parse_args()
    configure_logging(args.log_file, args.log_level)
    try:
        run_feature_engineering(args.input, args.output, args.metadata)
    except (
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        pd.errors.ParserError,
    ) as exc:
        LOGGER.error("Feature engineering could not complete: %s", exc, exc_info=True)
        return 1
    LOGGER.info("Feature-engineering pipeline completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
