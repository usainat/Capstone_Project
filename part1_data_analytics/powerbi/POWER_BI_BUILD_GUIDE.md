# Power BI Traffic Intelligence Dashboard Build Guide

## Prerequisite

Power BI Desktop is a Windows application. Build the dashboard on a Windows 10
or later computer, Windows virtual machine, or an approved remote Windows
environment. Use a recent Power BI Desktop version and retain the `.pbix` file.

## 1. Import the supplied CSV

1. Open Power BI Desktop.
2. Select **Get data > Text/CSV**.
3. Choose `Metro_Interstate_Traffic_Volume.csv`.
4. Select **Transform Data**, not **Load**.
5. Rename the query to `Traffic`.

## 2. Apply Power Query preparation

Open **Home > Advanced Editor**. Copy the contents of `power_query.pq`, replace
the `CsvFilePath` placeholder with the full Windows CSV path, and select **Done**.

Confirm these source types:

| Column | Power Query type |
|---|---|
| holiday | Text |
| temp | Decimal Number |
| rain_1h | Decimal Number |
| snow_1h | Decimal Number |
| clouds_all | Whole Number |
| weather_main | Text |
| weather_description | Text |
| date_time | Date/Time |
| traffic_volume | Whole Number |

The query also standardises weather-description capitalisation and adds:

- `Hour`: whole number from 0 through 23
- `Temperature_Celsius`: decimal number
- `Traffic_Category`: Low, Medium or High

Traffic-category boundaries are:

- Low: below 4,500
- Medium: 4,500 through 5,500, inclusive
- High: above 5,500

Do not convert the text `None` in the holiday field to a null. It means the
record has no holiday label.

Before selecting **Close & Apply**, confirm:

- 48,204 rows
- 12 Power Query columns
- No null source fields
- Low: 31,237 rows
- Medium: 9,867 rows
- High: 7,100 rows

## 3. Create model calculations

Use **Table tools > New column** for the two calculated columns in
`model_calculations.dax`:

- `Traffic Date`
- `Year`

Use **New measure** for each measure in the same file. Format:

- Total Hours Analyzed: whole number
- Average Traffic Volume: two decimal places
- Average Temperature Celsius: two decimal places with `°C` in the title

## 4. Create KPI cards

Add three Card visuals:

| Card | Measure | Expected unfiltered value |
|---|---|---:|
| Total Hours Analyzed | `[Total Hours Analyzed]` | 40,575 |
| Average Traffic Volume | `[Average Traffic Volume]` | 3,259.82 |
| Average Temperature | `[Average Temperature Celsius]` | 8.06 °C |

The dataset has 48,204 source rows but 40,575 distinct hourly timestamps. The
hours KPI intentionally uses distinct timestamps.

## 5. Create daily traffic trend visual

Add a Line chart:

- X-axis: `Traffic Date`
- Y-axis: `[Daily Average Traffic]`
- Visual-level Year filter: 2015, 2016 and 2017
- X-axis type: Continuous
- Title: `Daily Average Traffic Volume, 2015–2017`

Observed-day controls:

- 2015: 195 days
- 2016: 366 days
- 2017: 365 days

The shorter 2015 series reflects missing source coverage and must not be hidden.

## 6. Create 2017 hourly traffic visual

Add a Clustered column chart:

- X-axis: `Hour`
- Y-axis: `[Average Traffic Volume]`
- Visual-level Year filter: 2017
- Sort: Hour ascending
- Title: `Average Traffic Volume by Hour, 2017`

Verify all 24 hours appear. Hour 16 should have the highest average, 5,797.54,
and hour 3 the lowest, 381.71.

## 7. Create weather-impact visual

Add a horizontal Bar chart:

- Y-axis: `weather_main`
- X-axis: `[Weather Average Traffic]`
- Sort: measure descending
- Title: `Average Traffic Volume by Weather Condition`

Expected extremes:

- Highest: Clouds, 3,618.45
- Lowest: Squall, 2,061.75
- Difference: 1,556.70

Add a note that Squall contains only four source records, so its average is not
stable enough for a broad policy conclusion.

## 8. Create temperature-versus-traffic scatter plot

Add a Scatter chart:

- X-axis: `Temperature_Celsius` and choose **Don't summarize**
- Y-axis: `traffic_volume` and choose **Don't summarize**
- Details: `date_time`
- Optional legend: `weather_main`
- Title: `Temperature vs. Traffic Volume`

Expected interpretation:

- The point cloud should not show a strong linear relationship.
- Raw Pearson correlation is approximately 0.13.
- The middle 50% of temperatures for high-traffic records is approximately
  274.31 K to 292.35 K, a broad range.
- Ten `0 K` observations are visible data-quality outliers.
- Two zero-traffic observations should be noted for later investigation.

## 9. Add slicers

Add these slicers and verify all visuals and cards respond:

- `Hour`: Between, minimum 0 and maximum 23
- `weather_main`: list or dropdown, 11 conditions
- `Traffic_Category`: list with Low, Medium and High

Use **Format > Edit interactions** to confirm every slicer filters the intended
visuals.

## 10. Add a limitations note

Include a visible text box stating that:

- Annual coverage is incomplete for several years.
- The CSV contains repeated timestamps with different weather descriptions.
- Ten temperatures are recorded as `0 K`.
- Squall has only four records.
- Dashboard relationships are descriptive and do not establish causation.

## 11. Save and export

Save the dashboard as:

```text
part1_data_analytics/powerbi/traffic_intelligence_dashboard.pbix
```

Also export the report page to PDF or save clear screenshots for inclusion in
the Part 1 insights report. Complete `DASHBOARD_VERIFICATION_CHECKLIST.md`
before committing the `.pbix` file.
