"""Build the cleaned record-level dataset for the traffic capstone."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd


LOGGER = logging.getLogger(__name__)
EXPECTED_COLUMNS = [
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
NUMERIC_COLUMNS = [
    "temp",
    "rain_1h",
    "snow_1h",
    "clouds_all",
    "traffic_volume",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    project_root = script_directory.parent
    parser = argparse.ArgumentParser(
        description="Clean and validate the Metro Interstate Traffic dataset."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=project_root / "Metro_Interstate_Traffic_Volume.csv",
        help="Path to the raw traffic CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_directory / "data/processed/traffic_cleaned.csv",
        help="Path for the cleaned record-level CSV.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=script_directory / "data/processed/cleaning_summary.json",
        help="Path for the cleaning audit summary.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=script_directory / "logs/pipeline.log",
        help="Path for the pipeline log file.",
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


def load_raw_csv(input_path: Path) -> pd.DataFrame:
    """Load the raw CSV using specific, logged exception handling."""
    try:
        frame = pd.read_csv(input_path, keep_default_na=False)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Raw CSV was not found: {input_path}") from exc
    except UnicodeDecodeError as exc:
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            "raw CSV encoding could not be decoded",
        ) from exc
    except pd.errors.ParserError as exc:
        raise pd.errors.ParserError(f"Raw CSV could not be parsed: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Raw CSV could not be read: {input_path}") from exc

    LOGGER.info(
        "Loaded raw CSV %s with %d rows and %d columns",
        input_path.name,
        *frame.shape,
    )
    return frame


def validate_schema(frame: pd.DataFrame) -> None:
    """Validate required columns and order before data processing."""
    actual_columns = frame.columns.tolist()
    missing_columns = sorted(set(EXPECTED_COLUMNS) - set(actual_columns))
    unexpected_columns = sorted(set(actual_columns) - set(EXPECTED_COLUMNS))
    order_matches = actual_columns == EXPECTED_COLUMNS
    if missing_columns or unexpected_columns or not order_matches:
        raise ValueError(
            "Schema mismatch: "
            f"missing={missing_columns}, unexpected={unexpected_columns}, "
            f"order_matches={order_matches}"
        )
    LOGGER.info("Schema validation passed for %d columns", len(EXPECTED_COLUMNS))


def standardize_categories(frame: pd.DataFrame) -> dict[str, int]:
    """Standardize categorical whitespace and description capitalisation."""
    change_counts: dict[str, int] = {}
    for column in ["holiday", "weather_main", "weather_description"]:
        before = frame[column].copy()
        standardized = before.astype("string").str.strip()
        if column == "weather_description":
            standardized = standardized.str.lower()

        if column == "holiday":
            standardized = standardized.mask(standardized.eq(""), "None")
        else:
            standardized = standardized.mask(standardized.eq(""), "Unknown")

        frame[column] = standardized.astype(str)
        affected_rows = int(before.ne(frame[column]).sum())
        change_counts[column] = affected_rows
        if affected_rows:
            LOGGER.warning(
                "Standardized %d values in categorical column %s",
                affected_rows,
                column,
            )
        else:
            LOGGER.info("Categorical column %s required no changes", column)
    return change_counts


def convert_and_validate_types(frame: pd.DataFrame) -> dict[str, int]:
    """Parse date/time and coerce numerical fields, recording coercions."""
    try:
        parsed_dates = pd.to_datetime(
            frame["date_time"],
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )
    except (TypeError, ValueError) as exc:
        LOGGER.error("Date/time parsing failed: %s", exc, exc_info=True)
        raise

    invalid_date_count = int(parsed_dates.isna().sum())
    if invalid_date_count:
        raise ValueError(
            f"date_time contains {invalid_date_count} missing or invalid values"
        )
    frame["date_time"] = parsed_dates
    LOGGER.info(
        "Parsed date_time successfully; range %s to %s",
        frame["date_time"].min(),
        frame["date_time"].max(),
    )

    coercion_counts: dict[str, int] = {}
    for column in NUMERIC_COLUMNS:
        before_missing = frame[column].isna()
        converted = pd.to_numeric(frame[column], errors="coerce")
        newly_missing = converted.isna() & ~before_missing
        coercion_count = int(newly_missing.sum())
        coercion_counts[column] = coercion_count
        frame[column] = converted
        if coercion_count:
            LOGGER.warning(
                "Coerced %d non-numeric values to missing in %s",
                coercion_count,
                column,
            )
        else:
            LOGGER.info("Numerical conversion passed for %s", column)
    return coercion_counts


def impute_invalid_by_month(
    frame: pd.DataFrame,
    column: str,
    invalid_mask: pd.Series,
    reason: str,
) -> dict[str, dict[str, float | int]]:
    """Impute invalid values using an explicit month-by-month median loop."""
    invalid_mask = invalid_mask.fillna(True)
    if not invalid_mask.any():
        LOGGER.info("No values required imputation in %s: %s", column, reason)
        return {}

    audit: dict[str, dict[str, float | int]] = {}
    month_key = frame["date_time"].dt.to_period("M")
    valid_global_values = frame.loc[~invalid_mask & frame[column].notna(), column]
    if valid_global_values.empty:
        raise ValueError(f"No valid values are available to impute {column}")
    global_median = float(valid_global_values.median())

    for month in sorted(month_key.loc[invalid_mask].unique()):
        target_mask = invalid_mask & month_key.eq(month)
        valid_month_mask = (
            ~invalid_mask & month_key.eq(month) & frame[column].notna()
        )
        monthly_values = frame.loc[valid_month_mask, column]
        if monthly_values.empty:
            replacement = global_median
            LOGGER.warning(
                "No valid monthly values for %s in %s; using global median %.4f",
                column,
                month,
                replacement,
            )
        else:
            replacement = float(monthly_values.median())

        affected_rows = int(target_mask.sum())
        frame.loc[target_mask, column] = replacement
        audit[str(month)] = {
            "affected_rows": affected_rows,
            "replacement_median": replacement,
        }
        LOGGER.warning(
            "Imputed %d values in %s for %s with median %.4f: %s",
            affected_rows,
            column,
            month,
            replacement,
            reason,
        )
    return audit


def handle_missing_numerical_values(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, dict[str, float | int]]]]:
    """Handle missing numerical inputs using documented field-specific rules."""
    working = frame
    missing_target_rows = frame["traffic_volume"].isna()
    missing_target_count = int(missing_target_rows.sum())
    if missing_target_count:
        working = frame.loc[~missing_target_rows].reset_index(drop=True).copy()
        LOGGER.warning(
            "Dropped %d rows with missing traffic_volume targets",
            missing_target_count,
        )
    else:
        LOGGER.info("No rows had missing traffic_volume targets")

    audits: dict[str, dict[str, dict[str, float | int]]] = {}
    for column in ["temp", "rain_1h", "snow_1h", "clouds_all"]:
        audits[column] = impute_invalid_by_month(
            working,
            column,
            working[column].isna(),
            "missing numerical value",
        )
    return working, audits


def remove_exact_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicates after text and type standardisation."""
    duplicate_count = int(frame.duplicated().sum())
    if duplicate_count:
        frame = frame.drop_duplicates().reset_index(drop=True)
        LOGGER.warning(
            "Dropped %d exact duplicate rows; %d rows remain",
            duplicate_count,
            len(frame),
        )
    else:
        LOGGER.info("No exact duplicate rows were found")
    return frame, duplicate_count


def handle_impossible_values(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, dict[str, float | int]]]]:
    """Impute documented impossible/outlier values using monthly medians."""
    audits = {
        "temp": impute_invalid_by_month(
            frame,
            "temp",
            frame["temp"].le(0),
            "temperature must be above 0 K",
        ),
        "rain_1h": impute_invalid_by_month(
            frame,
            "rain_1h",
            frame["rain_1h"].lt(0) | frame["rain_1h"].gt(9000),
            "rainfall must be between 0 and 9,000 mm",
        ),
        "snow_1h": impute_invalid_by_month(
            frame,
            "snow_1h",
            frame["snow_1h"].lt(0),
            "snowfall cannot be negative",
        ),
        "clouds_all": impute_invalid_by_month(
            frame,
            "clouds_all",
            ~frame["clouds_all"].between(0, 100),
            "cloud percentage must be between 0 and 100",
        ),
    }

    negative_traffic_rows = frame["traffic_volume"].lt(0)
    negative_traffic_count = int(negative_traffic_rows.sum())
    if negative_traffic_count:
        frame = frame.loc[~negative_traffic_rows].reset_index(drop=True).copy()
        LOGGER.warning(
            "Dropped %d rows with impossible negative traffic volume",
            negative_traffic_count,
        )
    else:
        LOGGER.info("No negative traffic-volume rows were found")

    zero_traffic_count = int(frame["traffic_volume"].eq(0).sum())
    if zero_traffic_count:
        LOGGER.warning(
            "Retained %d zero-traffic rows for investigation; no evidence supports imputation",
            zero_traffic_count,
        )
    return frame, audits


def validate_cleaned_data(frame: pd.DataFrame) -> None:
    """Stop the pipeline if required post-cleaning guarantees are not met."""
    failures: list[str] = []
    if frame.columns.tolist() != EXPECTED_COLUMNS:
        failures.append("columns differ from the expected schema")
    if frame.duplicated().any():
        failures.append("exact duplicates remain")
    if frame.isna().any().any():
        failures.append("missing values remain")
    if not pd.api.types.is_datetime64_any_dtype(frame["date_time"]):
        failures.append("date_time is not datetime64")
    if frame["temp"].le(0).any():
        failures.append("nonpositive temperatures remain")
    if (frame["rain_1h"].lt(0) | frame["rain_1h"].gt(9000)).any():
        failures.append("invalid rainfall values remain")
    if frame["snow_1h"].lt(0).any():
        failures.append("negative snowfall remains")
    if (~frame["clouds_all"].between(0, 100)).any():
        failures.append("cloud percentage outside 0-100 remains")
    if frame["traffic_volume"].lt(0).any():
        failures.append("negative traffic volume remains")
    if failures:
        raise ValueError("Cleaned-data validation failed: " + "; ".join(failures))
    LOGGER.info("Cleaned-data validation passed")


def clean_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the ordered cleaning stages and return data plus an audit summary."""
    cleaned = frame.copy(deep=True)
    raw_rows = len(cleaned)

    category_changes = standardize_categories(cleaned)
    numeric_coercions = convert_and_validate_types(cleaned)
    cleaned, missing_value_audits = handle_missing_numerical_values(cleaned)
    cleaned, duplicate_count = remove_exact_duplicates(cleaned)
    cleaned, outlier_audits = handle_impossible_values(cleaned)

    cleaned["clouds_all"] = cleaned["clouds_all"].round().astype("int64")
    cleaned["traffic_volume"] = cleaned["traffic_volume"].round().astype("int64")

    timestamp_counts = cleaned["date_time"].value_counts()
    repeated_timestamp_rows = int(timestamp_counts[timestamp_counts.gt(1)].sum())
    additional_timestamp_records = int(len(cleaned) - timestamp_counts.size)
    if additional_timestamp_records:
        LOGGER.warning(
            "Preserved %d rows belonging to repeated timestamps (%d additional records) "
            "because they contain distinct weather observations",
            repeated_timestamp_rows,
            additional_timestamp_records,
        )

    validate_cleaned_data(cleaned)
    summary: dict[str, Any] = {
        "raw_rows": raw_rows,
        "cleaned_rows": len(cleaned),
        "rows_removed": raw_rows - len(cleaned),
        "exact_duplicates_removed": duplicate_count,
        "category_change_counts": category_changes,
        "numeric_coercion_counts": numeric_coercions,
        "missing_value_imputations": missing_value_audits,
        "outlier_imputations": outlier_audits,
        "unique_timestamps": int(cleaned["date_time"].nunique()),
        "additional_timestamp_records_preserved": additional_timestamp_records,
        "zero_traffic_rows_retained": int(cleaned["traffic_volume"].eq(0).sum()),
        "unique_weather_descriptions": int(
            cleaned["weather_description"].nunique()
        ),
    }
    LOGGER.info(
        "Cleaning completed: raw_rows=%d cleaned_rows=%d rows_removed=%d",
        summary["raw_rows"],
        summary["cleaned_rows"],
        summary["rows_removed"],
    )
    return cleaned, summary


def write_outputs(
    frame: pd.DataFrame,
    summary: dict[str, Any],
    output_path: Path,
    summary_path: Path,
) -> None:
    """Atomically write the cleaned CSV and JSON audit summary."""
    output_path = output_path.resolve()
    summary_path = summary_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_csv = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_json = summary_path.with_suffix(summary_path.suffix + ".tmp")
    try:
        frame.to_csv(
            temporary_csv,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
        )
        temporary_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_csv, output_path)
        os.replace(temporary_json, summary_path)
    except OSError:
        for temporary_path in (temporary_csv, temporary_json):
            if temporary_path.exists():
                temporary_path.unlink()
        LOGGER.error("Could not write pipeline outputs", exc_info=True)
        raise

    LOGGER.info("Saved cleaned dataset to %s", output_path)
    LOGGER.info("Saved cleaning summary to %s", summary_path)


def run_pipeline(
    input_path: Path,
    output_path: Path,
    summary_path: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the complete data pipeline without configuring handlers."""
    raw_frame = load_raw_csv(input_path.resolve())
    validate_schema(raw_frame)
    cleaned_frame, summary = clean_data(raw_frame)
    write_outputs(cleaned_frame, summary, output_path, summary_path)
    return cleaned_frame, summary


def main() -> int:
    """Configure logging, run the pipeline and exit gracefully."""
    args = parse_args()
    configure_logging(args.log_file, args.log_level)
    try:
        run_pipeline(args.input, args.output, args.summary)
    except (
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        pd.errors.ParserError,
    ) as exc:
        LOGGER.error("Pipeline could not complete: %s", exc, exc_info=True)
        return 1
    LOGGER.info("Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
