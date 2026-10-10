# Withings Weight CSV Plotter

A small, dependency-free Python script that turns Withings CSV exports into interactive charts you can open in your browser. By default, it imports CSV files under `Data/` and CSV files inside ZIP archives there. The chart is generated locally as a standalone HTML file and works offline.

## Features

- Plot individual measurements from weight, body composition, body temperature, and other numeric Withings exports.
- Calculate body fat percentage from fat mass and weight, and muscle percentage from muscle mass and weight.
- Select up to three metrics at once. Each metric has its own vertical scale.
- View weekly averages, monthly averages, or both alongside the individual measurements.
- Reduce dense series to representative display points while keeping weekly and monthly averages based on every imported measurement.
- Hover over chart points to see the measurement and its applicable averages.
- Explore long date ranges with a draggable time navigator; use the mouse wheel over the chart to zoom.
- Read measurements directly from the CSV exports; source files are not modified.

## Requirements

- Python 3.10 or newer
- A Withings CSV export with a `Date` column and at least one numeric measurement column
- No third-party Python packages are required

## Quick start

1. Place your Withings CSV exports or export ZIP archive under `Data/`.
2. To import all data under `Data/`, run this from the repository directory:

   ```bash
   python weight_plot.py
   ```

   CSV files are found recursively. Files inside any folder named `plotignore` are skipped. CSV files in ZIP archives are included, except archive members under a `plotignore` folder. Non-time-series files without a supported date column and numeric measurements are skipped. To plot one CSV by itself, pass its path explicitly:

   ```bash
   python weight_plot.py --csv "path/to/weight.csv"
   ```

For another export, pass its CSV path in the same way. The repository includes a body-temperature example:

```bash
python weight_plot.py --csv "Data/body_temperature.csv" --output "body_temperature.html"
```

The script writes `weight_plot.html` next to `weight_plot.py` and opens it in your default browser. Open that HTML file again later to view the chart; the Python script does not need to stay running.

### Windows

```powershell
py weight_plot.py --csv "C:\path\to\weight.csv"
```

### Choose a different output path

```bash
python weight_plot.py --csv "path/to/weight.csv" --output "path/to/chart.html"
```

To create the HTML without opening a browser automatically, add `--no-open`:

```bash
python weight_plot.py --csv "path/to/weight.csv" --output "chart.html" --no-open
```

## Using the chart

- **Metrics:** check one to three metrics. At least one must stay selected. Numeric columns are detected from the imported data sources. Weight exports include weight, fat mass, muscle mass, bone mass, water mass, body fat percentage, and muscle percentage. Temperature exports such as `body_temperature.csv` show body temperature, labeled Körpertemperatur (°C) in the chart. Percentages are calculated only when the corresponding mass and weight are present for a measurement.
- **Aggregation:** choose weekly averages, monthly averages, or both. Gray dots show individual measurements, the blue line shows weekly averages, and the red line shows monthly averages.
- **Details:** hover over a point to see its measurement and the weekly/monthly average for the matching period, when available.
- **Dense series:** series with more than 5,000 points are reduced for display with their minima and maxima preserved per interval. Weekly and monthly averages use every imported point.
- **Date range:** drag the highlighted selection or its handles in the navigator below the chart to move or resize the visible range. Scroll over the chart to zoom around the pointer position.

To exclude files from the automatic import, move them into `Data/plotignore/`. The folder can contain CSV files or ZIP archives; both are skipped.

## CSV format

Each time-series CSV needs a date column (`Date`, `date`, `Datum`, `start`, or `von`) and at least one numeric measurement. Known weight-export columns keep their existing names, and body-fat and muscle percentages are derived from the corresponding mass and weight. Other numeric columns are detected automatically; nonnumeric columns such as comments are ignored. Empty measurement cells are allowed.

The weight export uses columns like these:

```csv
Date,Gewicht (kg),Fettmasse (kg),Muskelmasse (kg),Knochenmasse (kg),Wasseranteil (kg)
```

Dates should use ISO format or an ISO date and time, such as `2026-09-28 07:26:52`. Body-temperature exports can use a lowercase `date` header and a column such as `value (°C)`; that measurement is displayed as body temperature (Körpertemperatur (°C)). The script accepts decimal points or decimal commas in numeric values and skips rows where all measurement fields are empty. It reports an error if no usable measurements are found.

## Privacy

All processing happens on your computer. The generated chart contains measurements from the imported CSV files and ZIP archives and is self-contained; no server, account, or network connection is used. Keep the generated HTML private, since it includes personal health measurements. The repository's `.gitignore` excludes the local `Data/` folder and generated HTML by default.

## Command-line options

| Option | Description |
| --- | --- |
| `--csv PATH` | Import only this CSV. Without it, all supported CSVs under `Data/` and in ZIP archives there are imported, except files under `plotignore/`. |
| `--output PATH` | Output HTML file. Defaults to `weight_plot.html` in the repository. |
| `--no-open` | Generate the HTML without opening it in a browser. |

## License

No license file is currently included. Add a license before redistributing or reusing this project if you want to grant others explicit usage rights.
