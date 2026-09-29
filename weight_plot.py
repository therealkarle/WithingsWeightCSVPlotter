#!/usr/bin/env python3
"""Create a simple, interactive plot from a Withings weight.csv export."""

from __future__ import annotations

import argparse
import csv
import html
import json
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path

METRICS = [
    "Gewicht (kg)",
    "Fettmasse (kg)",
    "Muskelmasse (kg)",
    "Knochenmasse (kg)",
    "Wasseranteil (kg)",
]


def read_measurements(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = [column for column in ["Date", *METRICS] if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Fehlende CSV-Spalten: " + ", ".join(missing))
        for line, row in enumerate(reader, start=2):
            try:
                date = datetime.fromisoformat(row["Date"].strip())
                values = {metric: float(row[metric].replace(",", ".")) for metric in METRICS if row[metric].strip()}
            except (ValueError, AttributeError) as error:
                raise ValueError(f"Ungültiger Messwert in CSV-Zeile {line}: {error}") from error
            if values:
                rows.append({"date": date, "values": values})
    if not rows:
        raise ValueError("Die CSV-Datei enthält keine Messwerte.")
    return sorted(rows, key=lambda row: row["date"])


def averages(rows: list[dict], metric: str, period: str) -> tuple[list[str], list[float]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row["values"].get(metric)
        if value is None:
            continue
        date = row["date"]
        if period == "week":
            # ISO weeks begin on Monday.
            key = (date.date().fromordinal(date.date().toordinal() - date.weekday())).isoformat()
        else:
            key = date.strftime("%Y-%m-01")
        buckets[key].append(value)
    keys = sorted(buckets)
    return keys, [sum(buckets[key]) / len(buckets[key]) for key in keys]


def build_page(rows: list[dict], output: Path) -> None:
    series = {}
    for metric in METRICS:
        metric_rows = [row for row in rows if metric in row["values"]]
        if not metric_rows:
            continue
        week_x, week_y = averages(metric_rows, metric, "week")
        month_x, month_y = averages(metric_rows, metric, "month")
        series[metric] = {
            "raw": [[row["date"].isoformat(sep=" "), row["values"][metric]] for row in metric_rows],
            "week": [[x, y] for x, y in zip(week_x, week_y)],
            "month": [[x, y] for x, y in zip(month_x, month_y)],
        }

    payload = json.dumps(series, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    options = "\n".join(f'<option value="{html.escape(metric)}">{html.escape(metric)}</option>' for metric in series)
    page = f'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Withings Gewichtsdaten</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#f5f6f8;color:#242424;font:15px system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1200px;margin:30px auto;padding:0 22px}} h1{{font-size:23px;font-weight:600;margin:0 0 18px}}
.controls{{display:flex;gap:18px;align-items:end;flex-wrap:wrap;background:white;padding:16px 18px;border:1px solid #e5e5e5;border-radius:8px 8px 0 0}}
label{{display:grid;gap:6px;font-weight:550}} select{{font:inherit;padding:8px 34px 8px 10px;border:1px solid #c9cdd2;border-radius:5px;background:white;min-width:190px}}
.chart{{background:white;border:1px solid #e5e5e5;border-top:0;padding:0 8px 4px;border-radius:0 0 8px 8px}} svg{{display:block;width:100%;height:auto;min-height:320px}}
.grid{{stroke:#e2e2e2;stroke-width:1}} .axis{{stroke:#777;stroke-width:1}} .tick{{fill:#555;font-size:13px}} .raw-dot{{fill:#aaa;opacity:.52}} .week-line{{fill:none;stroke:#1479c9;stroke-width:2}} .month-line{{fill:none;stroke:#e3262e;stroke-width:2.7}} .month-dot{{fill:#e3262e;stroke:#fff;stroke-width:1}}
.hint{{color:#777;font-size:13px;margin:12px 2px}} @media(max-width:600px){{main{{margin:16px auto;padding:0 10px}}.controls{{gap:12px}}label,select{{width:100%}}}}
</style></head><body><main><h1>Withings – Gewicht &amp; Körperzusammensetzung</h1>
<section class="controls"><label for="metric">Messgröße<select id="metric">{options}</select></label>
<label for="aggregation">Aggregation<select id="aggregation"><option value="both">Woche + Monat</option><option value="week">Wöchentlich</option><option value="month">Monatlich</option></select></label></section>
<div class="chart"><svg id="weight-chart" viewBox="0 0 1100 590" role="img" aria-label="Interaktiver Verlauf der Withings-Messwerte"></svg></div>
<p class="hint">Graue Punkte zeigen Einzelmessungen. Wochenmittel sind blau, Monatsmittel rot. Für Details auf einen Messpunkt zeigen.</p></main>
<script>
const series={payload}; const svg=document.getElementById('weight-chart'); const NS='http://www.w3.org/2000/svg';
function el(tag,attrs={{}},parent=svg){{const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);parent.appendChild(node);return node;}}
function text(x,y,value,anchor='end',parent=svg){{const node=el('text',{{x,y,'text-anchor':anchor,class:'tick'}},parent);node.textContent=value;return node;}}
function pathFor(points,x,y){{return points.map((point,index)=>(index?'L':'M')+x(new Date(point[0]).getTime()).toFixed(1)+','+y(point[1]).toFixed(1)).join(' ');}}
function render(){{const metric=document.getElementById('metric').value;const mode=document.getElementById('aggregation').value;const data=series[metric];svg.replaceChildren();
const W=1100,H=590,L=82,R=30,T=62,B=65,PW=W-L-R,PH=H-T-B;const dates=data.raw.map(p=>new Date(p[0]).getTime());
const start=Math.min(...dates),end=Math.max(...dates);let all=data.raw.map(p=>p[1]);if(mode==='week'||mode==='both')all=all.concat(data.week.map(p=>p[1]));if(mode==='month'||mode==='both')all=all.concat(data.month.map(p=>p[1]));
let low=Math.min(...all),high=Math.max(...all);const range=high-low||1;low=Math.max(0,Math.floor((low-range*.08)*2)/2);high=Math.ceil((high+range*.08)*2)/2;
const x=v=>L+(v-start)/(end-start||1)*PW;const y=v=>T+(high-v)/(high-low)*PH;
for(let i=0;i<=5;i++){{const value=low+(high-low)*i/5,yy=y(value);el('line',{{x1:L,y1:yy,x2:W-R,y2:yy,class:'grid'}});text(L-12,yy+4,value.toFixed(1));}}
const tickCount=Math.min(7,Math.max(2,Math.ceil((end-start)/(365.25*86400000))+1));for(let i=0;i<tickCount;i++){{const date=new Date(start+(end-start)*i/(tickCount-1)),xx=x(date.getTime());el('line',{{x1:xx,y1:T,x2:xx,y2:H-B,class:'grid'}});text(xx,H-B+25,String(date.getFullYear()),'middle');}}
el('line',{{x1:L,y1:T,x2:L,y2:H-B,class:'axis'}});el('line',{{x1:L,y1:H-B,x2:W-R,y2:H-B,class:'axis'}});
const yl=el('text',{{x:20,y:T+PH/2,transform:`rotate(-90 20 ${{T+PH/2}})`,'text-anchor':'middle',class:'tick'}});yl.textContent=metric;
for(const point of data.raw){{const dot=el('circle',{{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:2.7,class:'raw-dot'}});const title=el('title',{{}},dot);title.textContent=new Date(point[0]).toLocaleString('de-DE')+': '+point[1].toFixed(2)+' kg';}}
if(mode==='week'||mode==='both')el('path',{{d:pathFor(data.week,x,y),class:'week-line'}});
if(mode==='month'||mode==='both'){{el('path',{{d:pathFor(data.month,x,y),class:'month-line'}});for(const point of data.month)el('circle',{{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:3.8,class:'month-dot'}});}}
const legend=el('g',{{transform:`translate(${{W-R-310}},28)`}});el('circle',{{cx:5,cy:0,r:3,class:'raw-dot'}},legend);text(17,4,'Einzelmessungen','start',legend);
let offset=142;if(mode==='week'||mode==='both'){{el('line',{{x1:offset,y1:0,x2:offset+22,y2:0,class:'week-line'}},legend);text(offset+29,4,'Wochenmittel','start',legend);offset+=125;}}
if(mode==='month'||mode==='both'){{el('line',{{x1:offset,y1:0,x2:offset+22,y2:0,class:'month-line'}},legend);text(offset+29,4,'Monatsmittel','start',legend);}}
}}
document.getElementById('metric').addEventListener('change',render);document.getElementById('aggregation').addEventListener('change',render);render();
</script></body></html>'''
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interaktiver Plot für einen Withings weight.csv Export")
    parser.add_argument("--csv", type=Path, default=Path(__file__).parent / "Data" / "weight.csv", help="Pfad zur Withings-CSV")
    parser.add_argument("--output", type=Path, help="HTML-Ausgabedatei (Standard: neben dem Skript)")
    parser.add_argument("--no-open", action="store_true", help="HTML-Datei nicht automatisch im Browser öffnen")
    args = parser.parse_args()
    output = args.output or Path(__file__).parent / "weight_plot.html"
    try:
        rows = read_measurements(args.csv)
        build_page(rows, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Plot erstellt: {output.resolve()} ({len(rows):,} Messungen)".replace(",", "."))
    if not args.no_open:
        webbrowser.open(output.resolve().as_uri())


if __name__ == "__main__":
    main()
