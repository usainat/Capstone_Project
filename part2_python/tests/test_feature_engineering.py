"""Tests for the Part 2 hourly feature-engineering pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from part2_python.feature_engineering import (
    CLEANED_COLUMNS,
    engineer_features,
    load_cleaned_csv,
    run_feature_engineering,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLEANED_CSV = (
    PROJECT_ROOT / "part2_python/data/processed/traffic_cleaned.csv"
)


def test_conflicting_hourly_target_is_rejected() -> None:
    rows = [
        ["None", 280, 0, 0, 10, "Clear", "clear sky", "2020-01-01 01:00:00", 100],
        ["None", 280, 0, 0, 10, "Rain", "light rain", "2020-01-01 01:00:00", 200],
    ]
    frame = pd.DataFrame(rows, columns=CLEANED_COLUMNS)

    with pytest.raises(ValueError, match="conflicting traffic targets"):
        engineer_features(frame)


def test_engineered_features_match_reviewed_dataset() -> None:
    cleaned = load_cleaned_csv(CLEANED_CSV)
    features, metadata = engineer_features(cleaned)

    assert features.shape == (40_575, 36)
    assert metadata["input_record_rows"] == 48_187
    assert metadata["records_consolidated"] == 7_612
    assert metadata["weather_feature_count"] == 11
    assert metadata["missing_values"] == 0
    assert metadata["duplicate_timestamps"] == 0
    assert metadata["congestion_thresholds"] == {
        "q1": 1248.5,
        "q2": 3427.0,
        "q3": 4952.0,
    }
    assert metadata["congestion_category_counts"] == {
        "Low": 10_144,
        "Medium": 10_144,
        "High": 10_145,
        "Severe": 10_142,
    }
    assert features["date_time"].is_monotonic_increasing
    assert not features["date_time"].duplicated().any()
    assert np.isclose(features["temp_zscore"].mean(), 0.0, atol=1e-12)
    assert np.isclose(features["temp_zscore"].std(ddof=0), 1.0, atol=1e-12)


def test_run_feature_engineering_writes_reloadable_outputs(tmp_path: Path) -> None:
    output_path = tmp_path / "traffic_features.csv"
    metadata_path = tmp_path / "feature_metadata.json"

    features, metadata = run_feature_engineering(
        CLEANED_CSV,
        output_path,
        metadata_path,
    )

    assert output_path.is_file()
    assert metadata_path.is_file()
    assert features.shape == (40_575, 36)
    assert metadata["output_columns"] == 36

    reloaded = pd.read_csv(output_path, keep_default_na=False)
    assert reloaded.shape == (40_575, 36)
    assert reloaded["holiday"].eq("None").any()
    assert reloaded["congestion_category"].isin(
        ["Low", "Medium", "High", "Severe"]
    ).all()
