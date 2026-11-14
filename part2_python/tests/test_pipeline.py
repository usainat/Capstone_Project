"""Tests for the Part 2 data-cleaning pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from part2_python.pipeline import (
    EXPECTED_COLUMNS,
    clean_data,
    load_raw_csv,
    run_pipeline,
    validate_schema,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = PROJECT_ROOT / "Metro_Interstate_Traffic_Volume.csv"


def test_validate_schema_rejects_missing_column() -> None:
    frame = pd.DataFrame(columns=EXPECTED_COLUMNS[:-1])
    with pytest.raises(ValueError, match="Schema mismatch"):
        validate_schema(frame)


def test_clean_data_matches_reviewed_dataset() -> None:
    raw_frame = load_raw_csv(RAW_CSV)
    validate_schema(raw_frame)

    cleaned_frame, summary = clean_data(raw_frame)

    assert cleaned_frame.shape == (48_187, 9)
    assert summary["exact_duplicates_removed"] == 17
    assert summary["category_change_counts"]["weather_description"] == 1_730
    assert summary["unique_timestamps"] == 40_575
    assert summary["additional_timestamp_records_preserved"] == 7_612
    assert summary["zero_traffic_rows_retained"] == 2
    assert summary["unique_weather_descriptions"] == 37
    assert summary["outlier_imputations"]["temp"] == {
        "2014-01": {"affected_rows": 4, "replacement_median": 261.29},
        "2014-02": {"affected_rows": 6, "replacement_median": 259.5},
    }
    assert summary["outlier_imputations"]["rain_1h"] == {
        "2016-07": {"affected_rows": 1, "replacement_median": 0.0}
    }
    assert not cleaned_frame.duplicated().any()
    assert cleaned_frame["temp"].gt(0).all()
    assert cleaned_frame["rain_1h"].between(0, 9000).all()


def test_run_pipeline_writes_valid_outputs(tmp_path: Path) -> None:
    output_path = tmp_path / "traffic_cleaned.csv"
    summary_path = tmp_path / "cleaning_summary.json"

    cleaned_frame, summary = run_pipeline(
        RAW_CSV,
        output_path,
        summary_path,
    )

    assert output_path.is_file()
    assert summary_path.is_file()
    assert len(cleaned_frame) == 48_187
    assert summary["cleaned_rows"] == 48_187

    reloaded = pd.read_csv(output_path)
    assert reloaded.shape == (48_187, 9)
    assert reloaded["temp"].gt(0).all()
