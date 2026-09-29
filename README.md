# Withings Weight CSV Plotter

A small, dependency-free Python script that turns a Withings `weight.csv` export into an interactive chart you can open in your browser. The chart is generated locally as a standalone HTML file and works offline.

## Features

- Plot individual measurements for weight and body composition.
- Calculate body fat percentage from fat mass and weight, and muscle percentage from muscle mass and weight.
- Select up to three metrics at once. Each metric has its own vertical scale.
- View weekly averages, monthly averages, or both alongside the individual measurements.
- Hover over chart points to see the measurement and its applicable averages.
- Explore long date ranges with a draggable time navigator; use the mouse wheel over the chart to zoom.
- Read measurements directly from the CSV; the source file is not modified.

## Requirements

- Python 3.10 or newer
- A Withings `weight.csv` export with the columns described below
- No third-party Python packages are required

## Quick start

1. Export your data from Withings and place the file at `Data/weight.csv` inside the repository, or note its full path.
2. To use the default file, run this from the repository directory:

   ```bash
   python weight_plot.py
   ```

   With no `--csv` argument, the script reads `Data/weight.csv` relative to the location of `weight_plot.py` (not relative to the current working directory). If your CSV is elsewhere, pass its path explicitly:

   ```bash
   python weight_plot.py --csv "path/to/weight.csv"
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

- **Metrics:** check one to three metrics. At least one must stay selected. Available metrics are weight, fat mass, muscle mass, bone mass, water mass, body fat percentage, and muscle percentage. Percentages are calculated only when the corresponding mass and weight are present for a measurement.
- **Aggregation:** choose weekly averages, monthly averages, or both. Gray dots show individual measurements, the blue line shows weekly averages, and the red line shows monthly averages.
- **Details:** hover over a point to see its measurement and the weekly/monthly average for the matching period, when available.
- **Date range:** drag the highlighted selection or its handles in the navigator below the chart to move or resize the visible range. Scroll over the chart to zoom around the pointer position.

## CSV format

The file must contain these exact column names (as used in the Withings export):

```csv
Date,Gewicht (kg),Fettmasse (kg),Muskelmasse (kg),Knochenmasse (kg),Wasseranteil (kg)
```

`Date` must be an ISO-formatted date or date and time, such as `2026-09-28 07:26:52`. Measurement columns may be empty when a value is unavailable. The script accepts decimal points or decimal commas in values and skips rows where all measurement fields are empty. It reports an error if a required column is missing, a date or value cannot be parsed, or no usable measurements are found.

## Privacy

All processing happens on your computer. The generated chart contains the measurements from the CSV and is self-contained; no server, account, or network connection is used. Keep the generated HTML private, since it includes personal body measurements. The repository's `.gitignore` excludes the local `Data/` folder and generated HTML by default.

## Command-line options

| Option | Description |
| --- | --- |
| `--csv PATH` | Input CSV. Defaults to `Data/weight.csv` beside the script, under the repository's `Data/` folder. |
| `--output PATH` | Output HTML file. Defaults to `weight_plot.html` in the repository. |
| `--no-open` | Generate the HTML without opening it in a browser. |

## License

No license file is currently included. Add a license before redistributing or reusing this project if you want to grant others explicit usage rights.
