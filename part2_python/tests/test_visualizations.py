"""Tests for the Part 2 Matplotlib visualisations."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from part2_python.visualizations import (
    EXPECTED_FIGURES,
    load_feature_table,
    run_visualizations,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURES_CSV = (
    PROJECT_ROOT / "part2_python/data/processed/traffic_features.csv"
)


def test_load_feature_table_rejects_duplicate_timestamp(tmp_path: Path) -> None:
    source = load_feature_table(FEATURES_CSV).head(2)
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    duplicate_path = tmp_path / "duplicate.csv"
    duplicate.to_csv(duplicate_path, index=False)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        load_feature_table(duplicate_path)


def test_run_visualizations_writes_four_valid_figures(tmp_path: Path) -> None:
    output_directory = tmp_path / "figures"
    summary_path = tmp_path / "visualization_summary.json"

    summary = run_visualizations(
        FEATURES_CSV,
        output_directory,
        summary_path,
    )

    assert summary["source_rows"] == 40_575
    assert summary["generated_figure_count"] == 4
    assert summary_path.is_file()
    assert sorted(path.name for path in output_directory.glob("*.png")) == sorted(
        EXPECTED_FIGURES
    )
    for filename in EXPECTED_FIGURES:
        figure_path = output_directory / filename
        assert figure_path.stat().st_size > 10_000
        assert figure_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    reloaded_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert reloaded_summary == summary


def test_visualization_metrics_match_reviewed_notebook(tmp_path: Path) -> None:
    summary = run_visualizations(
        FEATURES_CSV,
        tmp_path / "figures",
        tmp_path / "summary.json",
    )
    figures = summary["figures"]

    hourly = figures["01_hourly_weekday_weekend.png"]["peaks"]
    assert hourly["Weekday"]["hour"] == 16
    assert hourly["Weekend"]["hour"] == 13

    distribution = figures["02_traffic_distribution.png"]
    assert distribution["minimum"] == 0
    assert distribution["maximum"] == 7_280
    assert distribution["median"] == 3_427.0

    temperature = figures["03_temperature_traffic_hexbin.png"]
    assert np.isclose(
        temperature["pearson_correlation"],
        0.13955701991709782,
    )

    weather = figures["04_weather_average_traffic.png"]
    assert weather["highest_average"]["condition"] == "Clouds"
    assert weather["lowest_average"] == {
        "condition": "Squall",
        "average_traffic": 2061.75,
        "hourly_observations": 4,
    }
