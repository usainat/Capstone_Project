"""Calculate Part 1 descriptive statistics, correlation and probabilities."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import statistics
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
CONGESTION_THRESHOLD = 5_500
HIGH_TEMPERATURE_THRESHOLD = 292
CLEAR_WEATHER = "Clear"
CLOUDY_WEATHER = "Clouds"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    project_root = script_directory.parents[1]
    parser = argparse.ArgumentParser(
        description="Calculate Part 1 traffic statistics and probabilities."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=project_root / "part1_data_analytics/sql/traffic_analysis.db",
        help="Path to the verified SQLite traffic database.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_directory / "results.json",
        help="Path for the generated JSON results.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    """Configure entry-point console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def load_records(
    database_path: Path,
) -> tuple[list[tuple[float, str, int]], list[int]]:
    """Load source records and one-value-per-hour traffic volumes."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        records = connection.execute(
            """
            SELECT temp, weather_main, traffic_volume
            FROM traffic
            ORDER BY row_id
            """
        ).fetchall()
        hourly_traffic_volumes = [
            row[0]
            for row in connection.execute(
                """
                SELECT MAX(traffic_volume)
                FROM traffic
                GROUP BY date_time
                """
            )
        ]

    LOGGER.info(
        "Loaded %d source records and %d unique hours",
        len(records),
        len(hourly_traffic_volumes),
    )
    return records, hourly_traffic_volumes


def calculate_results(
    records: list[tuple[float, str, int]],
    hourly_traffic_volumes: list[int],
) -> dict[str, Any]:
    """Calculate all required Part 1 statistics and probability results."""
    temperatures = [record[0] for record in records]
    weather_conditions = [record[1] for record in records]
    traffic_volumes = [record[2] for record in records]
    record_count = len(records)

    valid_temperature_pairs = [
        (temperature, traffic_volume)
        for temperature, traffic_volume in zip(temperatures, traffic_volumes)
        if temperature > 0
    ]

    congestion = [
        traffic_volume > CONGESTION_THRESHOLD
        for traffic_volume in traffic_volumes
    ]
    clear_weather = [
        weather == CLEAR_WEATHER for weather in weather_conditions
    ]
    cloudy_weather = [
        weather == CLOUDY_WEATHER for weather in weather_conditions
    ]
    high_temperature = [
        temperature > HIGH_TEMPERATURE_THRESHOLD
        for temperature in temperatures
    ]

    congestion_count = sum(congestion)
    clear_count = sum(clear_weather)
    cloudy_count = sum(cloudy_weather)
    congestion_and_clear_count = sum(
        is_congested and is_clear
        for is_congested, is_clear in zip(congestion, clear_weather)
    )
    high_temperature_and_congestion_count = sum(
        is_hot and is_congested
        for is_hot, is_congested in zip(high_temperature, congestion)
    )

    probability_congestion = congestion_count / record_count
    probability_clear = clear_count / record_count
    probability_joint = congestion_and_clear_count / record_count
    probability_clear_given_congestion = (
        congestion_and_clear_count / congestion_count
    )
    probability_high_temperature_given_congestion = (
        high_temperature_and_congestion_count / congestion_count
    )
    independence_product = probability_congestion * probability_clear

    clear_congested = sum(
        is_clear and is_congested
        for is_clear, is_congested in zip(clear_weather, congestion)
    )
    clear_not_congested = sum(
        is_clear and not is_congested
        for is_clear, is_congested in zip(clear_weather, congestion)
    )
    cloudy_congested = sum(
        is_cloudy and is_congested
        for is_cloudy, is_congested in zip(cloudy_weather, congestion)
    )
    cloudy_not_congested = sum(
        is_cloudy and not is_congested
        for is_cloudy, is_congested in zip(cloudy_weather, congestion)
    )

    clear_odds = clear_congested / clear_not_congested
    cloudy_odds = cloudy_congested / cloudy_not_congested
    odds_ratio = clear_odds / cloudy_odds

    return {
        "analysis_unit": "source record",
        "thresholds_and_definitions": {
            "congestion": f"traffic_volume > {CONGESTION_THRESHOLD}",
            "clear_weather": f"weather_main == '{CLEAR_WEATHER}'",
            "cloudy_weather": f"weather_main == '{CLOUDY_WEATHER}'",
            "high_temperature": f"temp > {HIGH_TEMPERATURE_THRESHOLD} K",
        },
        "descriptive_statistics": {
            "count": record_count,
            "mean": statistics.fmean(traffic_volumes),
            "median": statistics.median(traffic_volumes),
            "sample_standard_deviation": statistics.stdev(traffic_volumes),
            "sample_variance": statistics.variance(traffic_volumes),
            "population_standard_deviation": statistics.pstdev(traffic_volumes),
            "population_variance": statistics.pvariance(traffic_volumes),
            "minimum": min(traffic_volumes),
            "maximum": max(traffic_volumes),
            "range": max(traffic_volumes) - min(traffic_volumes),
        },
        "hourly_sensitivity": {
            "unique_hours": len(hourly_traffic_volumes),
            "mean": statistics.fmean(hourly_traffic_volumes),
            "median": statistics.median(hourly_traffic_volumes),
            "sample_standard_deviation": statistics.stdev(
                hourly_traffic_volumes
            ),
        },
        "correlation": {
            "raw_temperature_vs_traffic": statistics.correlation(
                temperatures,
                traffic_volumes,
            ),
            "excluding_zero_kelvin": statistics.correlation(
                [pair[0] for pair in valid_temperature_pairs],
                [pair[1] for pair in valid_temperature_pairs],
            ),
            "zero_kelvin_records_excluded": (
                record_count - len(valid_temperature_pairs)
            ),
        },
        "event_counts": {
            "all_records": record_count,
            "congestion": congestion_count,
            "clear_weather": clear_count,
            "cloudy_weather": cloudy_count,
            "congestion_and_clear": congestion_and_clear_count,
            "high_temperature_and_congestion": (
                high_temperature_and_congestion_count
            ),
        },
        "probabilities": {
            "P_congestion": probability_congestion,
            "P_clear_weather": probability_clear,
            "P_congestion_and_clear_weather": probability_joint,
            "P_clear_weather_given_congestion": (
                probability_clear_given_congestion
            ),
            "P_high_temperature_given_congestion": (
                probability_high_temperature_given_congestion
            ),
        },
        "independence": {
            "observed_joint_probability": probability_joint,
            "product_of_marginals": independence_product,
            "difference": probability_joint - independence_product,
            "independent_under_equality_rule": math.isclose(
                probability_joint,
                independence_product,
                rel_tol=0.0,
                abs_tol=1e-12,
            ),
        },
        "odds_ratio_clear_vs_cloudy": {
            "clear_congested": clear_congested,
            "clear_not_congested": clear_not_congested,
            "cloudy_congested": cloudy_congested,
            "cloudy_not_congested": cloudy_not_congested,
            "probability_congestion_given_clear": clear_congested / clear_count,
            "probability_congestion_given_cloudy": (
                cloudy_congested / cloudy_count
            ),
            "clear_congestion_odds": clear_odds,
            "cloudy_congestion_odds": cloudy_odds,
            "odds_ratio": odds_ratio,
        },
    }


def validate_results(results: dict[str, Any]) -> None:
    """Validate the calculations against the reviewed capstone dataset."""
    descriptive = results["descriptive_statistics"]
    probabilities = results["probabilities"]
    odds = results["odds_ratio_clear_vs_cloudy"]

    if descriptive["count"] != 48_204:
        raise RuntimeError("Unexpected source-record count")
    if not math.isclose(descriptive["mean"], 3259.8183553232097):
        raise RuntimeError("Unexpected mean traffic volume")
    if not math.isclose(
        results["correlation"]["raw_temperature_vs_traffic"],
        0.13029879817112516,
    ):
        raise RuntimeError("Unexpected temperature/traffic correlation")
    if not math.isclose(probabilities["P_congestion"], 0.1472906812712638):
        raise RuntimeError("Unexpected congestion probability")
    if not math.isclose(odds["odds_ratio"], 0.7353882125733118):
        raise RuntimeError("Unexpected clear-versus-cloudy odds ratio")


def write_results(results: dict[str, Any], output_path: Path) -> None:
    """Write deterministic, formatted JSON results."""
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    LOGGER.info("Saved validated results to %s", output_path)


def main() -> int:
    """Run the statistics and probability calculation workflow."""
    configure_logging()
    args = parse_args()
    try:
        records, hourly_traffic_volumes = load_records(args.database.resolve())
        results = calculate_results(records, hourly_traffic_volumes)
        validate_results(results)
        write_results(results, args.output)
    except (FileNotFoundError, OSError, RuntimeError, sqlite3.Error) as exc:
        LOGGER.error("Analysis could not complete: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
