-- Part 1, Task 1: SQL-based traffic analysis.
-- Run against traffic_analysis.db after executing build_database.py.

-- 1.1 Verify the import.
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT date_time) AS unique_timestamps,
    MIN(date_time) AS earliest_timestamp,
    MAX(date_time) AS latest_timestamp,
    SUM(
        CASE
            WHEN holiday IS NULL
              OR temp IS NULL
              OR rain_1h IS NULL
              OR snow_1h IS NULL
              OR clouds_all IS NULL
              OR weather_main IS NULL
              OR weather_description IS NULL
              OR date_time IS NULL
              OR traffic_volume IS NULL
            THEN 1 ELSE 0
        END
    ) AS rows_with_nulls
FROM traffic;

-- Confirm the number of source rows that are exact duplicates.
SELECT COALESCE(SUM(group_size - 1), 0) AS exact_duplicate_rows
FROM (
    SELECT COUNT(*) AS group_size
    FROM traffic
    GROUP BY
        holiday,
        temp,
        rain_1h,
        snow_1h,
        clouds_all,
        weather_main,
        weather_description,
        date_time,
        traffic_volume
    HAVING COUNT(*) > 1
);

-- Confirm that repeated timestamps agree on traffic volume.
SELECT COUNT(*) AS timestamps_with_conflicting_traffic
FROM (
    SELECT date_time
    FROM traffic
    GROUP BY date_time
    HAVING MIN(traffic_volume) <> MAX(traffic_volume)
);

-- Inspect data coverage before interpreting annual totals.
SELECT
    CAST(strftime('%Y', date_time) AS INTEGER) AS year,
    COUNT(*) AS source_records,
    COUNT(DISTINCT date_time) AS unique_hours,
    MIN(date_time) AS first_record,
    MAX(date_time) AS last_record
FROM traffic
WHERE CAST(strftime('%Y', date_time) AS INTEGER) BETWEEN 2012 AND 2017
GROUP BY year
ORDER BY year;

-- 1.2 Requested raw-record annual totals and year-on-year changes.
-- Caution: repeated weather observations cause some hours to be counted
-- multiple times, and several years have incomplete coverage.
WITH annual AS (
    SELECT
        CAST(strftime('%Y', date_time) AS INTEGER) AS year,
        COUNT(*) AS source_records,
        COUNT(DISTINCT date_time) AS unique_hours,
        SUM(traffic_volume) AS total_traffic_volume,
        ROUND(AVG(traffic_volume), 2) AS average_traffic_volume
    FROM traffic
    WHERE CAST(strftime('%Y', date_time) AS INTEGER) BETWEEN 2012 AND 2017
    GROUP BY year
),
annual_with_previous AS (
    SELECT
        *,
        LAG(total_traffic_volume) OVER (ORDER BY year) AS previous_total
    FROM annual
)
SELECT
    year,
    source_records,
    unique_hours,
    total_traffic_volume,
    average_traffic_volume,
    total_traffic_volume - previous_total AS year_on_year_change,
    CASE
        WHEN previous_total IS NULL THEN NULL
        ELSE ROUND(
            100.0 * (total_traffic_volume - previous_total) / previous_total,
            2
        )
    END AS year_on_year_percent
FROM annual_with_previous
ORDER BY year;

-- Sensitivity analysis: one traffic observation per timestamp.
-- All repeated timestamps have consistent traffic volume, so MAX safely
-- selects the single hourly value without multiplying it by weather reports.
WITH hourly_traffic AS (
    SELECT
        date_time,
        MAX(traffic_volume) AS traffic_volume
    FROM traffic
    GROUP BY date_time
),
annual AS (
    SELECT
        CAST(strftime('%Y', date_time) AS INTEGER) AS year,
        COUNT(*) AS unique_hours,
        SUM(traffic_volume) AS hourly_total_traffic_volume,
        ROUND(AVG(traffic_volume), 2) AS average_hourly_traffic
    FROM hourly_traffic
    WHERE CAST(strftime('%Y', date_time) AS INTEGER) BETWEEN 2012 AND 2017
    GROUP BY year
),
annual_with_previous AS (
    SELECT
        *,
        LAG(hourly_total_traffic_volume) OVER (ORDER BY year) AS previous_total
    FROM annual
)
SELECT
    year,
    unique_hours,
    hourly_total_traffic_volume,
    average_hourly_traffic,
    hourly_total_traffic_volume - previous_total AS year_on_year_change,
    CASE
        WHEN previous_total IS NULL THEN NULL
        ELSE ROUND(
            100.0 * (hourly_total_traffic_volume - previous_total) / previous_total,
            2
        )
    END AS year_on_year_percent
FROM annual_with_previous
ORDER BY year;

-- 1.3 Holiday-tagged observations, including missing combinations.
WITH years(year) AS (
    VALUES (2015), (2016), (2017)
),
holidays(holiday) AS (
    VALUES ('New Years Day'), ('Labor Day')
),
expected AS (
    SELECT year, holiday
    FROM years
    CROSS JOIN holidays
)
SELECT
    expected.year,
    expected.holiday,
    COUNT(traffic.row_id) AS source_records,
    COUNT(DISTINCT traffic.date_time) AS unique_timestamps,
    ROUND(AVG(traffic.temp), 2) AS average_temp_kelvin,
    ROUND(AVG(traffic.traffic_volume), 2) AS average_traffic_volume
FROM expected
LEFT JOIN traffic
    ON CAST(strftime('%Y', traffic.date_time) AS INTEGER) = expected.year
   AND traffic.holiday = expected.holiday
GROUP BY expected.year, expected.holiday
ORDER BY expected.year, expected.holiday DESC;

-- Full-day temperature patterns for each observed holiday date.
-- The inner query consolidates multiple weather observations to one timestamp.
WITH holiday_dates AS (
    SELECT DISTINCT
        CAST(strftime('%Y', date_time) AS INTEGER) AS year,
        holiday,
        date(date_time) AS holiday_date
    FROM traffic
    WHERE holiday IN ('New Years Day', 'Labor Day')
      AND CAST(strftime('%Y', date_time) AS INTEGER) BETWEEN 2015 AND 2017
),
hourly_holiday_data AS (
    SELECT
        holiday_dates.year,
        holiday_dates.holiday,
        holiday_dates.holiday_date,
        traffic.date_time,
        AVG(traffic.temp) AS hourly_temp_kelvin,
        MAX(traffic.traffic_volume) AS hourly_traffic_volume
    FROM holiday_dates
    JOIN traffic
        ON date(traffic.date_time) = holiday_dates.holiday_date
    GROUP BY
        holiday_dates.year,
        holiday_dates.holiday,
        holiday_dates.holiday_date,
        traffic.date_time
)
SELECT
    year,
    holiday,
    holiday_date,
    COUNT(*) AS observed_hours,
    ROUND(MIN(hourly_temp_kelvin), 2) AS minimum_temp_kelvin,
    ROUND(AVG(hourly_temp_kelvin), 2) AS average_temp_kelvin,
    ROUND(MAX(hourly_temp_kelvin), 2) AS maximum_temp_kelvin,
    ROUND(AVG(hourly_traffic_volume), 2) AS average_traffic_volume
FROM hourly_holiday_data
GROUP BY year, holiday, holiday_date
ORDER BY holiday, year;
