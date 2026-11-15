"""Create and save the required Part 2 traffic visualisations."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any

VISUALIZATION_CACHE = Path(tempfile.gettempdir()) / "capstone_visualization_cache"
os.environ.setdefault("MPLCONFIGDIR", str(VISUALIZATION_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(VISUALIZATION_CACHE))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
EXPECTED_FIGURES = [
    "01_hourly_weekday_weekend.png",
    "02_traffic_distribution.png",
    "03_temperature_traffic_hexbin.png",
    "04_weather_average_traffic.png",
]
REQUIRED_COLUMNS = {
    "date_time",
    "traffic_volume",
    "temp",
    "hour",
    "is_weekend",
}
COLORS = {
    "blue": "#1f77b4",
    "orange": "#ff7f0e",
    "green": "#2ca02c",
    "red": "#d62728",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate the Part 2 Matplotlib traffic figures."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=script_directory / "data/processed/traffic_features.csv",
        help="Path to the hourly feature CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=script_directory / "reports/figures",
        help="Directory for generated PNG figures.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=script_directory / "reports/visualization_summary.json",
        help="Path for calculated values and short interpretations.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=script_directory / "logs/visualizations.log",
        help="Path for the visualisation log file.",
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


def load_feature_table(input_path: Path) -> pd.DataFrame:
    """Load and validate the one-row-per-hour feature table."""
    try:
        frame = pd.read_csv(input_path, keep_default_na=False)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Feature CSV was not found: {input_path}. "
            "Run feature_engineering.py first."
        ) from exc
    except UnicodeDecodeError as exc:
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            "feature CSV encoding could not be decoded",
        ) from exc
    except pd.errors.ParserError as exc:
        raise pd.errors.ParserError(f"Feature CSV could not be parsed: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Feature CSV could not be read: {input_path}") from exc

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    weather_columns = sorted(
        column for column in frame.columns if column.startswith("weather_")
    )
    if missing_columns:
        raise ValueError(f"Feature table is missing columns: {missing_columns}")
    if not weather_columns:
        raise ValueError("Feature table contains no weather indicator columns")

    frame["date_time"] = pd.to_datetime(
        frame["date_time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )
    if frame["date_time"].isna().any():
        raise ValueError(
            f"Feature table contains {int(frame['date_time'].isna().sum())} "
            "invalid timestamps"
        )
    if frame["date_time"].duplicated().any():
        raise ValueError("Feature table contains duplicate timestamps")

    numeric_columns = ["traffic_volume", "temp", "hour", "is_weekend"]
    for column in [*numeric_columns, *weather_columns]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid_counts = {
        column: int(frame[column].isna().sum())
        for column in [*numeric_columns, *weather_columns]
        if frame[column].isna().any()
    }
    if invalid_counts:
        raise ValueError(f"Feature table has invalid numerical values: {invalid_counts}")
    if not frame["hour"].between(0, 23).all():
        raise ValueError("hour must be between 0 and 23")
    if not frame["is_weekend"].isin([0, 1]).all():
        raise ValueError("is_weekend must be binary")
    if not frame[weather_columns].isin([0, 1]).all().all():
        raise ValueError("weather indicator columns must be binary")

    LOGGER.info(
        "Loaded validated feature table %s with %d rows and %d columns",
        input_path.name,
        *frame.shape,
    )
    LOGGER.debug(
        "Feature date range: %s to %s",
        frame["date_time"].min(),
        frame["date_time"].max(),
    )
    return frame


def save_figure(fig: plt.Figure, output_path: Path) -> Path:
    """Atomically save one figure and log its completed path."""
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.stem}.tmp.png")
    try:
        fig.savefig(
            temporary_path,
            dpi=160,
            bbox_inches="tight",
            facecolor="white",
            format="png",
        )
        if temporary_path.stat().st_size == 0:
            raise OSError(f"Generated an empty figure: {temporary_path}")
        os.replace(temporary_path, output_path)
    except OSError:
        if temporary_path.exists():
            temporary_path.unlink()
        LOGGER.error("Could not save figure %s", output_path, exc_info=True)
        raise
    finally:
        plt.close(fig)

    LOGGER.info("Saved figure: %s", output_path)
    return output_path


def plot_hourly_profiles(
    features: pd.DataFrame, output_path: Path
) -> dict[str, Any]:
    """Plot and summarise weekday and weekend hourly demand profiles."""
    hourly_profile = (
        features.assign(
            day_type=np.where(
                features["is_weekend"].eq(1), "Weekend", "Weekday"
            )
        )
        .groupby(["hour", "day_type"], as_index=False)["traffic_volume"]
        .mean()
    )

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for day_type, color in [
        ("Weekday", COLORS["blue"]),
        ("Weekend", COLORS["orange"]),
    ]:
        subset = hourly_profile.loc[hourly_profile["day_type"].eq(day_type)]
        ax.plot(
            subset["hour"],
            subset["traffic_volume"],
            marker="o",
            linewidth=2.2,
            markersize=4,
            label=day_type,
            color=color,
        )
    ax.set(
        title="Average Traffic Demand by Hour: Weekday vs Weekend",
        xlabel="Hour of day",
        ylabel="Average traffic volume (vehicles/hour)",
    )
    ax.set_xticks(range(0, 24, 2))
    ax.legend(title="Day type")
    save_figure(fig, output_path)

    peak_rows = hourly_profile.loc[
        hourly_profile.groupby("day_type")["traffic_volume"].idxmax()
    ]
    peak_summary = {
        row.day_type: {
            "hour": int(row.hour),
            "average_traffic": float(row.traffic_volume),
        }
        for row in peak_rows.itertuples(index=False)
    }
    return {
        "peaks": peak_summary,
        "interpretation": (
            "Weekday demand has distinct morning and afternoon commuter peaks, "
            "while weekend demand is flatter and peaks around midday."
        ),
    }


def plot_traffic_distribution(
    features: pd.DataFrame, output_path: Path
) -> dict[str, Any]:
    """Plot and summarise the hourly traffic-volume distribution."""
    quartiles = features["traffic_volume"].quantile([0.25, 0.50, 0.75])
    LOGGER.debug("Traffic quartiles: %s", quartiles.to_dict())

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(
        features["traffic_volume"],
        bins=40,
        color=COLORS["blue"],
        edgecolor="white",
        alpha=0.85,
    )
    for quantile, label, color in [
        (0.25, "Q1", COLORS["green"]),
        (0.50, "Median", COLORS["orange"]),
        (0.75, "Q3", COLORS["red"]),
    ]:
        value = float(quartiles.loc[quantile])
        ax.axvline(
            value,
            color=color,
            linestyle="--",
            linewidth=2,
            label=f"{label}: {value:,.1f}",
        )
    ax.set(
        title="Distribution of Hourly Traffic Volume",
        xlabel="Traffic volume (vehicles/hour)",
        ylabel="Number of hourly observations",
    )
    ax.legend()
    save_figure(fig, output_path)

    return {
        "minimum": int(features["traffic_volume"].min()),
        "maximum": int(features["traffic_volume"].max()),
        "mean": float(features["traffic_volume"].mean()),
        "q1": float(quartiles.loc[0.25]),
        "median": float(quartiles.loc[0.50]),
        "q3": float(quartiles.loc[0.75]),
        "interpretation": (
            "The broad, non-normal distribution reflects a mixture of overnight "
            "low demand and daytime or commuter demand."
        ),
    }


def plot_temperature_relationship(
    features: pd.DataFrame, output_path: Path
) -> dict[str, Any]:
    """Plot temperature against traffic using density-aware hexagonal bins."""
    temperature_celsius = features["temp"] - 273.15
    correlation = float(temperature_celsius.corr(features["traffic_volume"]))
    LOGGER.debug("Temperature and traffic Pearson correlation: %.6f", correlation)

    fig, ax = plt.subplots(figsize=(10, 5.8))
    hexbin = ax.hexbin(
        temperature_celsius,
        features["traffic_volume"],
        gridsize=42,
        mincnt=1,
        cmap="viridis",
        bins="log",
    )
    colorbar = fig.colorbar(hexbin, ax=ax)
    colorbar.set_label("Observation density (log scale)")
    ax.set(
        title=f"Temperature vs Traffic Volume (Pearson r = {correlation:.3f})",
        xlabel="Temperature (°C)",
        ylabel="Traffic volume (vehicles/hour)",
    )
    save_figure(fig, output_path)

    return {
        "pearson_correlation": correlation,
        "temperature_celsius_minimum": float(temperature_celsius.min()),
        "temperature_celsius_maximum": float(temperature_celsius.max()),
        "interpretation": (
            "Temperature has only a weak positive linear relationship with traffic. "
            "The association is descriptive and does not establish causation."
        ),
    }


def plot_weather_comparison(
    features: pd.DataFrame, output_path: Path
) -> dict[str, Any]:
    """Plot average traffic and sample size for every multi-hot weather flag."""
    weather_columns = sorted(
        column for column in features.columns if column.startswith("weather_")
    )
    weather_summary = pd.DataFrame(
        {
            "condition": [
                column.removeprefix("weather_") for column in weather_columns
            ],
            "average_traffic": [
                features.loc[features[column].eq(1), "traffic_volume"].mean()
                for column in weather_columns
            ],
            "hourly_observations": [
                int(features[column].sum()) for column in weather_columns
            ],
        }
    ).sort_values("average_traffic", ascending=True)
    LOGGER.debug(
        "Weather summary: %s", weather_summary.to_dict(orient="records")
    )

    fig, ax = plt.subplots(figsize=(10, 6.5))
    bars = ax.barh(
        weather_summary["condition"],
        weather_summary["average_traffic"],
        color=COLORS["blue"],
        alpha=0.88,
    )
    ax.bar_label(
        bars,
        labels=[
            f"{mean:,.0f} (n={count:,})"
            for mean, count in zip(
                weather_summary["average_traffic"],
                weather_summary["hourly_observations"],
            )
        ],
        padding=4,
        fontsize=8,
    )
    ax.set(
        title="Average Traffic Volume by Recorded Weather Condition",
        xlabel="Average traffic volume (vehicles/hour)",
        ylabel="Weather condition",
    )
    ax.set_xlim(0, float(weather_summary["average_traffic"].max()) * 1.32)
    save_figure(fig, output_path)

    descending = weather_summary.sort_values(
        "average_traffic", ascending=False
    ).reset_index(drop=True)
    highest = descending.iloc[0]
    lowest = descending.iloc[-1]
    return {
        "highest_average": {
            "condition": str(highest["condition"]),
            "average_traffic": float(highest["average_traffic"]),
            "hourly_observations": int(highest["hourly_observations"]),
        },
        "lowest_average": {
            "condition": str(lowest["condition"]),
            "average_traffic": float(lowest["average_traffic"]),
            "hourly_observations": int(lowest["hourly_observations"]),
        },
        "conditions": descending.to_dict(orient="records"),
        "interpretation": (
            "Weather-category differences are descriptive. Rare conditions have "
            "unstable averages, and an hour may contain multiple weather flags."
        ),
    }


def write_summary(summary: dict[str, Any], summary_path: Path) -> None:
    """Atomically write calculated values and interpretations as JSON."""
    summary_path = summary_path.resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, summary_path)
    except OSError:
        if temporary_path.exists():
            temporary_path.unlink()
        LOGGER.error("Could not write visualisation summary", exc_info=True)
        raise
    LOGGER.info("Saved visualisation summary: %s", summary_path)


def generate_visualizations(
    features: pd.DataFrame,
    output_directory: Path,
    summary_path: Path,
) -> dict[str, Any]:
    """Generate all required figures and return their supporting findings."""
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    summary: dict[str, Any] = {
        "source_rows": len(features),
        "figures": {},
        "method_note": (
            "The source is a one-row-per-hour table. Weather flags are multi-hot, "
            "so one hour can contribute to multiple weather conditions."
        ),
    }
    summary["figures"][EXPECTED_FIGURES[0]] = plot_hourly_profiles(
        features, output_directory / EXPECTED_FIGURES[0]
    )
    summary["figures"][EXPECTED_FIGURES[1]] = plot_traffic_distribution(
        features, output_directory / EXPECTED_FIGURES[1]
    )
    summary["figures"][EXPECTED_FIGURES[2]] = plot_temperature_relationship(
        features, output_directory / EXPECTED_FIGURES[2]
    )
    summary["figures"][EXPECTED_FIGURES[3]] = plot_weather_comparison(
        features, output_directory / EXPECTED_FIGURES[3]
    )
    summary["generated_figure_count"] = len(EXPECTED_FIGURES)
    write_summary(summary, summary_path)
    LOGGER.info("Generated and validated %d visualisations", len(EXPECTED_FIGURES))
    return summary


def run_visualizations(
    input_path: Path,
    output_directory: Path,
    summary_path: Path,
) -> dict[str, Any]:
    """Load the feature table and generate all visualisation outputs."""
    features = load_feature_table(input_path.resolve())
    return generate_visualizations(features, output_directory, summary_path)


def main() -> int:
    """Configure logging, generate figures and exit gracefully."""
    args = parse_args()
    configure_logging(args.log_file, args.log_level)
    try:
        run_visualizations(args.input, args.output_dir, args.summary)
    except (
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        pd.errors.ParserError,
    ) as exc:
        LOGGER.error("Visualisation generation could not complete: %s", exc, exc_info=True)
        return 1
    LOGGER.info("Visualisation pipeline completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
