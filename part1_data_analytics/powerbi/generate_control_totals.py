"""Generate deterministic control totals for the Part 1 Power BI dashboard."""

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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    project_root = script_directory.parents[1]
    parser = argparse.ArgumentParser(
        description="Generate Power BI dashboard verification values."
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
        default=script_directory / "expected_dashboard_values.json",
        help="Path for the generated JSON control totals.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    """Configure entry-point console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def rows_as_dicts(
    connection: sqlite3.Connection,
    query: str,
) -> list[dict[str, Any]]:
    """Return query results as dictionaries using result-column names."""
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def calculate_control_totals(database_path: Path) -> dict[str, Any]:
    """Calculate all dashboard verification values."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        data_quality = rows_as_dicts(
            connection,
            """
            SELECT
                COUNT(*) AS source_rows,
                COUNT(DISTINCT date_time) AS distinct_hours,
                SUM(
                    CASE
                        WHEN holiday IS NULL OR temp IS NULL OR rain_1h IS NULL
                          OR snow_1h IS NULL OR clouds_all IS NULL
                          OR weather_main IS NULL OR weather_description IS NULL
                          OR date_time IS NULL OR traffic_volume IS NULL
                        THEN 1 ELSE 0
                    END
                ) AS rows_with_nulls
            FROM traffic
            """,
        )[0]
        data_quality["source_columns"] = 9
        data_quality["power_query_columns_after_transformations"] = 12

        category_counts = rows_as_dicts(
            connection,
            """
            SELECT
                CASE
                    WHEN traffic_volume < 4500 THEN 'Low'
                    WHEN traffic_volume <= 5500 THEN 'Medium'
                    ELSE 'High'
                END AS traffic_category,
                COUNT(*) AS source_records
            FROM traffic
            GROUP BY traffic_category
            ORDER BY traffic_category
            """,
        )

        daily_summary = rows_as_dicts(
            connection,
            """
            WITH daily AS (
                SELECT
                    CAST(strftime('%Y', date_time) AS INTEGER) AS year,
                    date(date_time) AS traffic_date,
                    AVG(traffic_volume) AS daily_average_traffic
                FROM traffic
                WHERE CAST(strftime('%Y', date_time) AS INTEGER)
                    BETWEEN 2015 AND 2017
                GROUP BY year, traffic_date
            )
            SELECT
                year,
                COUNT(*) AS observed_days,
                ROUND(AVG(daily_average_traffic), 2)
                    AS average_of_daily_averages,
                ROUND(MIN(daily_average_traffic), 2)
                    AS lowest_daily_average,
                ROUND(MAX(daily_average_traffic), 2)
                    AS highest_daily_average
            FROM daily
            GROUP BY year
            ORDER BY year
            """,
        )

        hourly_2017 = rows_as_dicts(
            connection,
            """
            SELECT
                CAST(strftime('%H', date_time) AS INTEGER) AS hour,
                COUNT(*) AS source_records,
                ROUND(AVG(traffic_volume), 2) AS average_traffic_volume
            FROM traffic
            WHERE strftime('%Y', date_time) = '2017'
            GROUP BY hour
            ORDER BY hour
            """,
        )

        weather_impact = rows_as_dicts(
            connection,
            """
            SELECT
                weather_main,
                COUNT(*) AS source_records,
                ROUND(AVG(traffic_volume), 2) AS average_traffic_volume
            FROM traffic
            GROUP BY weather_main
            ORDER BY average_traffic_volume DESC
            """,
        )

        kpis = rows_as_dicts(
            connection,
            """
            SELECT
                COUNT(*) AS source_rows,
                COUNT(DISTINCT date_time) AS total_hours_analyzed,
                ROUND(AVG(traffic_volume), 2) AS average_traffic_volume,
                ROUND(AVG(temp), 2) AS average_temperature_kelvin,
                ROUND(AVG(temp - 273.15), 2) AS average_temperature_celsius
            FROM traffic
            """,
        )[0]

        scatter_rows = connection.execute(
            "SELECT temp, traffic_volume FROM traffic ORDER BY row_id"
        ).fetchall()

    valid_high_traffic_temperatures = sorted(
        temperature
        for temperature, traffic_volume in scatter_rows
        if traffic_volume > 5_500 and temperature > 0
    )
    quartiles = statistics.quantiles(
        valid_high_traffic_temperatures,
        n=4,
        method="inclusive",
    )
    highest_weather = weather_impact[0]
    lowest_weather = weather_impact[-1]
    busiest_hour = max(hourly_2017, key=lambda row: row["average_traffic_volume"])
    quietest_hour = min(hourly_2017, key=lambda row: row["average_traffic_volume"])

    return {
        "data_quality": data_quality,
        "traffic_category_counts": category_counts,
        "daily_trend_summary_2015_2017": daily_summary,
        "hourly_traffic_2017": hourly_2017,
        "hourly_traffic_2017_summary": {
            "busiest_hour": busiest_hour,
            "quietest_hour": quietest_hour,
        },
        "weather_impact": weather_impact,
        "weather_impact_summary": {
            "highest_average": highest_weather,
            "lowest_average": lowest_weather,
            "highest_minus_lowest": round(
                highest_weather["average_traffic_volume"]
                - lowest_weather["average_traffic_volume"],
                2,
            ),
        },
        "temperature_scatter_summary": {
            "high_traffic_valid_temperature_records": len(
                valid_high_traffic_temperatures
            ),
            "high_traffic_temperature_minimum_kelvin": min(
                valid_high_traffic_temperatures
            ),
            "high_traffic_temperature_q1_kelvin": quartiles[0],
            "high_traffic_temperature_median_kelvin": statistics.median(
                valid_high_traffic_temperatures
            ),
            "high_traffic_temperature_q3_kelvin": quartiles[2],
            "high_traffic_temperature_maximum_kelvin": max(
                valid_high_traffic_temperatures
            ),
            "zero_kelvin_outliers": sum(
                temperature == 0 for temperature, _ in scatter_rows
            ),
            "zero_traffic_observations": sum(
                traffic_volume == 0 for _, traffic_volume in scatter_rows
            ),
        },
        "kpis": kpis,
        "slicers": {
            "hour_minimum": 0,
            "hour_maximum": 23,
            "weather_condition_count": len(weather_impact),
            "traffic_category_count": len(category_counts),
        },
    }


def validate_control_totals(results: dict[str, Any]) -> None:
    """Validate key dashboard values against the reviewed dataset."""
    quality = results["data_quality"]
    weather = results["weather_impact_summary"]
    hourly = results["hourly_traffic_2017_summary"]
    kpis = results["kpis"]

    if quality["source_rows"] != 48_204 or quality["distinct_hours"] != 40_575:
        raise RuntimeError("Unexpected Power BI source size")
    if quality["rows_with_nulls"] != 0:
        raise RuntimeError("Unexpected null values in Power BI source")
    if hourly["busiest_hour"]["hour"] != 16:
        raise RuntimeError("Unexpected busiest hour for 2017")
    if hourly["quietest_hour"]["hour"] != 3:
        raise RuntimeError("Unexpected quietest hour for 2017")
    if weather["highest_average"]["weather_main"] != "Clouds":
        raise RuntimeError("Unexpected highest-average weather condition")
    if weather["lowest_average"]["weather_main"] != "Squall":
        raise RuntimeError("Unexpected lowest-average weather condition")
    if not math.isclose(weather["highest_minus_lowest"], 1556.70, abs_tol=0.01):
        raise RuntimeError("Unexpected weather-average difference")
    if not math.isclose(kpis["average_traffic_volume"], 3259.82, abs_tol=0.01):
        raise RuntimeError("Unexpected average-traffic KPI")


def write_results(results: dict[str, Any], output_path: Path) -> None:
    """Write deterministic, formatted JSON control totals."""
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    LOGGER.info("Saved dashboard control totals to %s", output_path)


def main() -> int:
    """Run the Power BI control-total workflow."""
    configure_logging()
    args = parse_args()
    try:
        results = calculate_control_totals(args.database.resolve())
        validate_control_totals(results)
        write_results(results, args.output)
    except (FileNotFoundError, OSError, RuntimeError, sqlite3.Error) as exc:
        LOGGER.error("Could not generate dashboard controls: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
