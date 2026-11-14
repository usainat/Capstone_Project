let
    // Replace this placeholder with the full Windows path to the supplied CSV.
    CsvFilePath = "C:\\REPLACE_WITH_YOUR_PATH\\Metro_Interstate_Traffic_Volume.csv",

    Source = Csv.Document(
        File.Contents(CsvFilePath),
        [
            Delimiter = ",",
            Columns = 9,
            Encoding = 65001,
            QuoteStyle = QuoteStyle.Csv
        ]
    ),

    PromotedHeaders = Table.PromoteHeaders(
        Source,
        [PromoteAllScalars = true]
    ),

    ChangedTypes = Table.TransformColumnTypes(
        PromotedHeaders,
        {
            {"holiday", type text},
            {"temp", type number},
            {"rain_1h", type number},
            {"snow_1h", type number},
            {"clouds_all", Int64.Type},
            {"weather_main", type text},
            {"weather_description", type text},
            {"date_time", type datetime},
            {"traffic_volume", Int64.Type}
        },
        "en-US"
    ),

    StandardizedWeatherDescription = Table.TransformColumns(
        ChangedTypes,
        {
            {
                "weather_description",
                each Text.Lower(Text.Trim(_)),
                type text
            }
        }
    ),

    AddedHour = Table.AddColumn(
        StandardizedWeatherDescription,
        "Hour",
        each Time.Hour(DateTime.Time([date_time])),
        Int64.Type
    ),

    AddedTemperatureCelsius = Table.AddColumn(
        AddedHour,
        "Temperature_Celsius",
        each [temp] - 273.15,
        type number
    ),

    AddedTrafficCategory = Table.AddColumn(
        AddedTemperatureCelsius,
        "Traffic_Category",
        each
            if [traffic_volume] < 4500 then "Low"
            else if [traffic_volume] <= 5500 then "Medium"
            else "High",
        type text
    ),

    ReorderedColumns = Table.ReorderColumns(
        AddedTrafficCategory,
        {
            "holiday",
            "temp",
            "rain_1h",
            "snow_1h",
            "clouds_all",
            "weather_main",
            "weather_description",
            "date_time",
            "traffic_volume",
            "Hour",
            "Temperature_Celsius",
            "Traffic_Category"
        }
    )
in
    ReorderedColumns
