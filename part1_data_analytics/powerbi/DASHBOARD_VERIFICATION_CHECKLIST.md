# Power BI Dashboard Verification Checklist

## Data and Power Query

- [ ] The query is named `Traffic`.
- [ ] The source contains 48,204 rows and nine columns.
- [ ] The prepared Power Query table contains 12 columns.
- [ ] No source column contains null values.
- [ ] `date_time` is Date/Time.
- [ ] `traffic_volume`, `clouds_all` and `Hour` are Whole Number.
- [ ] Temperature and precipitation fields are Decimal Number.
- [ ] Weather and holiday fields are Text.
- [ ] Traffic categories contain Low, Medium and High.
- [ ] Category counts are 31,237 Low, 9,867 Medium and 7,100 High.

## KPI cards

- [ ] Total Hours Analyzed is 40,575 before filtering.
- [ ] Average Traffic Volume is 3,259.82 before filtering.
- [ ] Average Temperature is 8.06 °C before filtering.
- [ ] All cards respond to the three slicers.

## Required visuals

- [ ] Daily average line chart includes 2015, 2016 and 2017.
- [ ] The incomplete 2015 coverage is disclosed.
- [ ] The 2017 hourly chart contains 24 ordered columns.
- [ ] Hour 16 is the highest 2017 average.
- [ ] Weather chart is sorted by average traffic descending.
- [ ] Clouds is highest and Squall is lowest.
- [ ] The four-record Squall limitation is visible.
- [ ] Scatter plot uses Celsius and traffic volume with clear axis titles.
- [ ] The scatter interpretation describes a weak visible relationship.
- [ ] `0 K` and zero-traffic observations are mentioned as outliers.

## Slicers and usability

- [ ] Hour range slicer covers 0 through 23.
- [ ] Weather slicer contains 11 conditions.
- [ ] Traffic category slicer contains three categories.
- [ ] Visual interactions have been tested.
- [ ] Titles, labels and number formats are readable.
- [ ] The dashboard makes no unsupported causal claim.

## Submission artifact

- [ ] The `.pbix` opens successfully on another Windows computer.
- [ ] The report page has been exported to PDF or captured for the report.
- [ ] `traffic_intelligence_dashboard.pbix` is added to the repository.
