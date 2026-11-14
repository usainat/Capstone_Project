# Part 1: Descriptive Statistics, Correlation and Probability Analysis

## Method and definitions

This analysis uses the 48,204 source records in the verified SQLite database.
The primary results remain at source-record level so they correspond directly to
the supplied dataset. Because some timestamps contain multiple weather
descriptions with the same traffic volume, a one-record-per-hour sensitivity
check is reported separately.

The following definitions were applied consistently:

- Congestion: `traffic_volume > 5,500`
- Clear weather: `weather_main = 'Clear'`
- Cloudy weather: `weather_main = 'Clouds'`
- High temperature: `temp > 292 K`

The assignment does not state whether standard deviation and variance should use
sample or population formulas. The sample values are presented as the primary
results, matching common analytical-tool defaults; population values are also
recorded in `results.json` for transparency.

## Descriptive statistics

| Measure | Raw source-record result |
|---|---:|
| Count | 48,204 |
| Mean | 3,259.82 vehicles |
| Median | 3,380 vehicles |
| Sample standard deviation | 1,986.86 vehicles |
| Sample variance | 3,947,615.32 vehicles² |
| Minimum | 0 vehicles |
| Maximum | 7,280 vehicles |
| Range | 7,280 vehicles |

The mean and median are relatively close, but the standard deviation is large
relative to the mean. Hourly traffic demand therefore varies substantially,
consistent with overnight low-demand periods and daytime commuting peaks. The
range includes two zero-volume observations. They are retained in this raw-data
analysis and will be investigated during Part 2 cleaning rather than silently
changed.

The sensitivity dataset contains 40,575 unique hours. After retaining one
traffic value per timestamp, the mean is 3,290.65, the median is 3,427, and the
sample standard deviation is 1,984.77. The modest difference confirms that
repeated weather observations slightly reweight the raw-record summary.

## Temperature and traffic correlation

The raw Pearson correlation between temperature and traffic volume is
`r = 0.1303`. Using the stated interpretation guide in the learning notebook,
this is a **very weak positive** linear relationship. Excluding the ten
physically impossible `0 K` observations changes the coefficient only slightly,
to `r = 0.1323`.

Temperature alone therefore explains little of the hourly traffic variation.
The positive association does not establish causation. Hour of day, weekday,
season, holidays, incomplete yearly coverage and commuting behaviour may affect
both variables. A causal conclusion would require a research design that
controls for these confounders.

## Probability results

| Required probability | Result | Percentage |
|---|---:|---:|
| P(Congestion) | 0.147291 | 14.73% |
| P(Clear Weather) | 0.277799 | 27.78% |
| P(Congestion AND Clear Weather) | 0.036574 | 3.66% |
| P(Clear Weather \| Congestion) | 0.248310 | 24.83% |
| P(High Temperature \| Congestion) | 0.262958 | 26.30% |

For the assignment's independence rule:

- Observed `P(Congestion AND Clear) = 0.036574`
- `P(Congestion) × P(Clear) = 0.040917`
- Difference = `-0.004343`

The two values are not equal, so congestion and clear weather are **not
independent** under the required equality test. This result describes the
observed records and should not be treated as a causal weather effect.

## Clear-versus-cloudy congestion odds

The 2×2 counts are:

| Weather group | Congested | Not congested |
|---|---:|---:|
| Clear | 1,763 | 11,628 |
| Clouds | 2,592 | 12,572 |

`P(Congestion | Clear) = 13.17%`, while
`P(Congestion | Clouds) = 17.09%`. The clear-weather congestion odds are
`0.151617`, and the cloudy-weather congestion odds are `0.206172`.

The clear-versus-cloudy odds ratio is:

`OR = 0.151617 / 0.206172 = 0.735388`

An odds ratio below 1 means that, in this dataset, congestion odds under clear
weather are approximately 26.5% lower than under cloudy weather. Odds are not
the same as probabilities, and this association does not mean clouds cause
congestion. Time-of-day patterns, seasonal coverage and repeated weather
reporting are important limitations.

## Smart-city interpretation

The analysis indicates that congestion is primarily a recurring traffic-demand
problem rather than something that can be explained by temperature alone.
Weather may help refine forecasting, but time features and commuting patterns
should receive greater attention in the later predictive models. Traffic
management decisions should therefore combine weather with hour, weekday,
holiday and seasonal information rather than relying on a single weather
variable.
