-- Part 1, Task 1: SQLite schema for the Metro Interstate Traffic dataset.
-- The build_database.py script executes this file against a new database.

PRAGMA foreign_keys = ON;

CREATE TABLE traffic (
    row_id INTEGER PRIMARY KEY,
    holiday TEXT NOT NULL,
    temp REAL NOT NULL,
    rain_1h REAL NOT NULL,
    snow_1h REAL NOT NULL,
    clouds_all INTEGER NOT NULL,
    weather_main TEXT NOT NULL,
    weather_description TEXT NOT NULL,
    date_time TEXT NOT NULL,
    traffic_volume INTEGER NOT NULL
);

CREATE TABLE dataset_metadata (
    metadata_key TEXT PRIMARY KEY,
    metadata_value TEXT NOT NULL
);

CREATE INDEX idx_traffic_date_time ON traffic(date_time);
CREATE INDEX idx_traffic_holiday ON traffic(holiday);
CREATE INDEX idx_traffic_weather_main ON traffic(weather_main);
