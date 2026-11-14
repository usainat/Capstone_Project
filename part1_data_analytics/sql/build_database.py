"""Build the Part 1 SQLite database from the supplied traffic CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import sqlite3
from pathlib import Path


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
INSERT_SQL = """
    INSERT INTO traffic (
        holiday,
        temp,
        rain_1h,
        snow_1h,
        clouds_all,
        weather_main,
        weather_description,
        date_time,
        traffic_volume
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    script_directory = Path(__file__).resolve().parent
    project_root = script_directory.parents[1]
    parser = argparse.ArgumentParser(
        description="Build the SQLite database for Part 1 traffic analysis."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=project_root / "Metro_Interstate_Traffic_Volume.csv",
        help="Path to the supplied traffic CSV.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=script_directory / "traffic_analysis.db",
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output database.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    """Configure console logging for this entry-point script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def sha256_file(path: Path) -> str:
    """Calculate a source-file checksum without loading the full file in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_records(csv_path: Path) -> list[tuple[object, ...]]:
    """Read, validate and convert source records for SQLite insertion."""
    records: list[tuple[object, ...]] = []
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        actual_columns = reader.fieldnames or []
        if actual_columns != EXPECTED_COLUMNS:
            raise ValueError(
                "CSV schema mismatch: "
                f"expected {EXPECTED_COLUMNS!r}, received {actual_columns!r}"
            )

        for csv_line_number, row in enumerate(reader, start=2):
            try:
                records.append(
                    (
                        row["holiday"],
                        float(row["temp"]),
                        float(row["rain_1h"]),
                        float(row["snow_1h"]),
                        int(row["clouds_all"]),
                        row["weather_main"],
                        row["weather_description"],
                        row["date_time"],
                        int(row["traffic_volume"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid value on CSV line {csv_line_number}: {exc}"
                ) from exc
    return records


def build_database(
    csv_path: Path,
    database_path: Path,
    schema_path: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Build and atomically publish a verified SQLite database."""
    csv_path = csv_path.resolve()
    database_path = database_path.resolve()
    schema_path = schema_path.resolve()

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema file does not exist: {schema_path}")
    if database_path.exists() and not overwrite:
        raise FileExistsError(
            f"Database already exists: {database_path}. Use --overwrite to replace it."
        )

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = database_path.with_suffix(database_path.suffix + ".tmp")
    if temporary_path.exists():
        temporary_path.unlink()

    records = read_records(csv_path)
    source_checksum = sha256_file(csv_path)
    LOGGER.info("Validated %d CSV records from %s", len(records), csv_path.name)

    try:
        with sqlite3.connect(temporary_path) as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            connection.executemany(INSERT_SQL, records)
            metadata = {
                "source_filename": csv_path.name,
                "source_sha256": source_checksum,
                "source_row_count": str(len(records)),
            }
            connection.executemany(
                "INSERT INTO dataset_metadata(metadata_key, metadata_value) VALUES (?, ?)",
                metadata.items(),
            )

            row_count = connection.execute("SELECT COUNT(*) FROM traffic").fetchone()[0]
            unique_timestamps = connection.execute(
                "SELECT COUNT(DISTINCT date_time) FROM traffic"
            ).fetchone()[0]
            if row_count != len(records):
                raise RuntimeError(
                    f"Database verification failed: inserted {row_count} of {len(records)} rows"
                )
            if row_count != 48_204 or unique_timestamps != 40_575:
                raise RuntimeError(
                    "Database does not match the reviewed capstone dataset: "
                    f"rows={row_count}, unique_timestamps={unique_timestamps}"
                )

        os.replace(temporary_path, database_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    LOGGER.info(
        "Created %s with %d rows and %d unique timestamps",
        database_path,
        row_count,
        unique_timestamps,
    )


def main() -> int:
    """Run the database build command."""
    configure_logging()
    args = parse_args()
    schema_path = Path(__file__).resolve().parent / "01_create_schema.sql"
    try:
        build_database(
            args.csv,
            args.database,
            schema_path,
            overwrite=args.overwrite,
        )
    except (
        FileNotFoundError,
        FileExistsError,
        OSError,
        RuntimeError,
        sqlite3.Error,
        ValueError,
    ) as exc:
        LOGGER.error("Could not build the SQLite database: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
