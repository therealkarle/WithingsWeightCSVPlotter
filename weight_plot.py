#!/usr/bin/env python3
"""Create an interactive, offline plot from a Withings weight.csv export."""

from __future__ import annotations

import argparse
import csv
import html
import json
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path


SOURCE_METRICS = [
    "Gewicht (kg)",
    "Fettmasse (kg)",
    "Muskelmasse (kg)",
    "Knochenmasse (kg)",
    "Wasseranteil (kg)",
]
METRICS = [*SOURCE_METRICS, "KFA (%)", "Muskelanteil (%)"]
PERCENT_METRICS = {"KFA (%)", "Muskelanteil (%)"}


def week_start(date: datetime) -> str:
    return (date.date().fromordinal(date.date().toordinal() - date.weekday())).isoformat()


def read_measurements(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = [column for column in ["Date", *SOURCE_METRICS] if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Fehlende CSV-Spalten: " + ", ".join(missing))
        for line, row in enumerate(reader, start=2):
            try:
                date = datetime.fromisoformat(row["Date"].strip())
                values = {
                    metric: float(row[metric].replace(",", "."))
                    for metric in SOURCE_METRICS
                    if row[metric].strip()
                }
            except (ValueError, AttributeError) as error:
                raise ValueError(f"Ungültiger Messwert in CSV-Zeile {line}: {error}") from error
            if not values:
                continue
            weight = values.get("Gewicht (kg)")
            if weight:
                if "Fettmasse (kg)" in values:
                    values["KFA (%)"] = values["Fettmasse (kg)"] / weight * 100
                if "Muskelmasse (kg)" in values:
                    values["Muskelanteil (%)"] = values["Muskelmasse (kg)"] / weight * 100
            rows.append({"date": date, "values": values})
    if not rows:
        raise ValueError("Die CSV-Datei enthält keine Messwerte.")
    return sorted(rows, key=lambda row: row["date"])


def averages(rows: list[dict], metric: str, period: str) -> list[list]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row["values"].get(metric)
        if value is None:
            continue
        date = row["date"]
        key = week_start(date) if period == "week" else date.strftime("%Y-%m-01")
        buckets[key].append(value)
    return [[key, sum(values) / len(values)] for key, values in sorted(buckets.items())]


def build_page(rows: list[dict], output: Path) -> None:
    series = {}
    for metric in METRICS:
        metric_rows = [row for row in rows if metric in row["values"]]
        if not metric_rows:
            continue
        series[metric] = {
            "unit": "%" if metric in PERCENT_METRICS else "kg",
            "raw": [
                [row["date"].isoformat(sep=" "), row["values"][metric], week_start(row["date"]), row["date"].strftime("%Y-%m-01")]
                for row in metric_rows
            ],
            "week": averages(metric_rows, metric, "week"),
            "month": averages(metric_rows, metric, "month"),
        }

    payload = json.dumps(series, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    options = "\n".join(
        f'<label class="metric-option"><input type="checkbox" value="{html.escape(metric)}"{" checked" if index == 0 else ""}><span>{html.escape(metric)}</span></label>'
        for index, metric in enumerate(series)
    )
    page = '''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Withings Gewichtsdaten</title>
<style>
*{box-sizing:border-box} body{margin:0;background:#f5f6f8;color:#242424;font:15px system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1200px;margin:30px auto;padding:0 22px} h1{font-size:23px;font-weight:600;margin:0 0 18px}
.controls{display:flex;gap:18px;align-items:end;flex-wrap:wrap;background:white;padding:16px 18px;border:1px solid #e5e5e5;border-radius:8px 8px 0 0}
.metric-picker{flex:1;min-width:280px}.metric-title{font-weight:600;margin-bottom:8px}.metric-options{display:flex;gap:8px 16px;flex-wrap:wrap}
.metric-option{display:flex;align-items:center;gap:6px;font-weight:400;white-space:nowrap}.metric-option input{accent-color:#1479c9;width:16px;height:16px;margin:0}
.aggregation-picker{display:grid;gap:6px;font-weight:550}select{font:inherit;padding:8px 34px 8px 10px;border:1px solid #c9cdd2;border-radius:5px;background:white;min-width:190px}
.selection-status{font-size:12px;color:#777;margin-top:7px;min-height:16px}
.chart{position:relative;background:white;border:1px solid #e5e5e5;border-top:0;padding:0 8px 4px;border-radius:0 0 8px 8px}svg{display:block;width:100%;height:auto}
.grid{stroke:#e2e2e2;stroke-width:1}.axis{stroke:#777;stroke-width:1}.tick{fill:#555;font-size:13px}.raw-dot{fill:#aaa;opacity:.52}
.week-line{fill:none;stroke:#1479c9;stroke-width:2}.month-line{fill:none;stroke:#e3262e;stroke-width:2.7}.month-dot{fill:#e3262e;stroke:#fff;stroke-width:1}
.hit-target{fill:transparent;stroke:transparent;pointer-events:all;cursor:crosshair}.raw-dot,.month-dot{cursor:crosshair}
.tooltip{display:none;position:absolute;z-index:2;pointer-events:none;min-width:210px;max-width:320px;background:rgba(255,255,255,.97);border:1px solid #c9cdd2;border-radius:6px;box-shadow:0 3px 14px #0002;padding:10px 12px;font-size:13px;line-height:1.5}
.tooltip-date{font-weight:650;margin-bottom:5px}.tooltip-metric{font-weight:600;margin-top:4px}.tooltip-values{color:#444}
.hint{color:#777;font-size:13px;margin:12px 2px}@media(max-width:600px){main{margin:16px auto;padding:0 10px}.controls{gap:12px}.metric-picker{min-width:100%}.aggregation-picker,select{width:100%}}
</style></head><body><main><h1>Withings – Gewicht &amp; Körperzusammensetzung</h1>
<section class="controls"><div class="metric-picker"><div class="metric-title">Messgrößen (bis zu 3)</div><div class="metric-options" id="metric-options">__METRIC_OPTIONS__</div><div class="selection-status" id="selection-status">1 von 3 ausgewählt</div></div>
<label class="aggregation-picker" for="aggregation">Aggregation<select id="aggregation"><option value="both">Woche + Monat</option><option value="week">Wöchentlich</option><option value="month">Monatlich</option></select></label></section>
<div class="chart"><svg id="weight-chart" viewBox="0 0 1100 465" role="img" aria-label="Interaktiver Verlauf der Withings-Messwerte"></svg><div class="tooltip" id="tooltip"></div></div>
<p class="hint">Graue Punkte zeigen Einzelmessungen. Wochenmittel sind blau, Monatsmittel rot. Beim Überfahren eines Punkts erscheinen Einzelwert und eingeschaltete Mittelwerte.</p></main>
<script>
const series=__SERIES_DATA__;
const svg=document.getElementById('weight-chart'),tooltip=document.getElementById('tooltip'),NS='http://www.w3.org/2000/svg';
function el(tag,attrs={},parent=svg){const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);parent.appendChild(node);return node;}
function text(x,y,value,anchor='end',parent=svg){const node=el('text',{x,y,'text-anchor':anchor,class:'tick'},parent);node.textContent=value;return node;}
function pathFor(points,x,y){return points.map((point,index)=>(index?'L':'M')+x(new Date(point[0]).getTime()).toFixed(1)+','+y(point[1]).toFixed(1)).join(' ');}
function selectedMetrics(){return [...document.querySelectorAll('#metric-options input:checked')].map(input=>input.value);}
function showTooltip(event,date,period){
  const mode=document.getElementById('aggregation').value,timestamp=new Date(date).getTime();
  const heading=document.createElement('div');heading.className='tooltip-date';
  heading.textContent=period==='week'?'Woche ab '+new Date(date).toLocaleDateString('de-DE'):period==='month'?'Monat ab '+new Date(date).toLocaleDateString('de-DE'):new Date(date).toLocaleString('de-DE');tooltip.replaceChildren(heading);
  for(const metric of selectedMetrics()){
    const data=series[metric],bucket=period==='week'?date.slice(0,10):date.slice(0,7)+'-01';
    const candidates=period==='week'?data.raw.filter(point=>point[2]===bucket):period==='month'?data.raw.filter(point=>point[3]===bucket):data.raw;
    let nearest=candidates[0]||data.raw[0];
    for(const point of candidates)if(Math.abs(new Date(point[0]).getTime()-timestamp)<Math.abs(new Date(nearest[0]).getTime()-timestamp))nearest=point;
    const title=document.createElement('div');title.className='tooltip-metric';title.textContent=metric;tooltip.appendChild(title);
    const rawDate=period==='raw'?'':' ('+new Date(nearest[0]).toLocaleString('de-DE')+')';
    const values=[`Einzelwert${rawDate}: ${nearest[1].toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} ${data.unit}`];
    if(mode==='week'||mode==='both'){const item=data.week.find(point=>point[0]===nearest[2]);if(item)values.push(`Woche: ${item[1].toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} ${data.unit}`);}
    if(mode==='month'||mode==='both'){const item=data.month.find(point=>point[0]===nearest[3]);if(item)values.push(`Monat: ${item[1].toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} ${data.unit}`);}
    const row=document.createElement('div');row.className='tooltip-values';row.textContent=values.join(' · ');tooltip.appendChild(row);
  }
  tooltip.style.display='block';const rect=svg.parentElement.getBoundingClientRect();
  tooltip.style.left=Math.min(Math.max(8,event.clientX-rect.left+12,8),rect.width-tooltip.offsetWidth-8)+'px';
  tooltip.style.top=Math.min(Math.max(8,event.clientY-rect.top+12,8),rect.height-tooltip.offsetHeight-8)+'px';
}
function bindTooltip(node,date,period='raw'){node.addEventListener('mouseenter',event=>showTooltip(event,date,period));node.addEventListener('mousemove',event=>showTooltip(event,date,period));node.addEventListener('mouseleave',()=>tooltip.style.display='none');}
function render(){
  const metrics=selectedMetrics(),mode=document.getElementById('aggregation').value,W=1100,PANEL=420,H=metrics.length*PANEL+45,L=82,R=30,B=54,PW=W-L-R;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.replaceChildren();
  const allDates=metrics.flatMap(metric=>series[metric].raw.map(point=>new Date(point[0]).getTime()));
  const start=Math.min(...allDates),end=Math.max(...allDates),x=value=>L+(value-start)/(end-start||1)*PW;
  metrics.forEach((metric,index)=>{
    const data=series[metric],unit=data.unit,top=42+index*PANEL,bottom=top+PANEL-B,PH=bottom-top;
    let values=data.raw.map(point=>point[1]);
    if(mode==='week'||mode==='both')values=values.concat(data.week.map(point=>point[1]));
    if(mode==='month'||mode==='both')values=values.concat(data.month.map(point=>point[1]));
    let low=Math.min(...values),high=Math.max(...values);const range=high-low||1;
    low=unit==='kg'?Math.max(0,Math.floor((low-range*.08)*2)/2):Math.floor((low-range*.08)*2)/2;
    high=Math.ceil((high+range*.08)*2)/2;const y=value=>top+(high-value)/(high-low||1)*PH;
    text(L,top-17,metric,'start');
    for(let tick=0;tick<=5;tick++){const value=low+(high-low)*tick/5,yy=y(value);el('line',{x1:L,y1:yy,x2:W-R,y2:yy,class:'grid'});text(L-12,yy+4,value.toFixed(1));}
    el('line',{x1:L,y1:top,x2:L,y2:bottom,class:'axis'});el('line',{x1:L,y1:bottom,x2:W-R,y2:bottom,class:'axis'});
    for(const point of data.raw){const dot=el('circle',{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:2.7,class:'raw-dot'});bindTooltip(dot,point[0]);}
    if(mode==='week'||mode==='both'){
      el('path',{d:pathFor(data.week,x,y),class:'week-line'});
      for(const point of data.week){const target=el('circle',{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:7,class:'hit-target'});bindTooltip(target,point[0],'week');}
    }
    if(mode==='month'||mode==='both'){
      el('path',{d:pathFor(data.month,x,y),class:'month-line'});
      for(const point of data.month){const dot=el('circle',{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:3.8,class:'month-dot'});bindTooltip(dot,point[0],'month');}
    }
    const tickCount=Math.min(7,Math.max(2,Math.ceil((end-start)/(365.25*86400000))+1));
    for(let tick=0;tick<tickCount;tick++){
      const date=new Date(start+(end-start)*tick/(tickCount-1)),xx=x(date.getTime());
      el('line',{x1:xx,y1:top,x2:xx,y2:bottom,class:'grid'});
      if(index===metrics.length-1)text(xx,bottom+25,String(date.getFullYear()),'middle');
    }
  });
  const legend=el('g',{transform:`translate(${W-R-340},20)`});
  el('circle',{cx:5,cy:0,r:3,class:'raw-dot'},legend);text(17,4,'Einzelmessungen','start',legend);
  el('line',{x1:145,y1:0,x2:167,y2:0,class:'week-line'},legend);text(174,4,'Wochenmittel','start',legend);
  el('line',{x1:265,y1:0,x2:287,y2:0,class:'month-line'},legend);text(294,4,'Monatsmittel','start',legend);
}
document.querySelectorAll('#metric-options input').forEach(input=>input.addEventListener('change',event=>{
  const count=selectedMetrics().length,status=document.getElementById('selection-status');
  if(count>3){event.target.checked=false;status.textContent='Es können höchstens 3 Messgrößen ausgewählt werden.';return;}
  if(count===0){event.target.checked=true;status.textContent='Bitte mindestens eine Messgröße ausgewählt lassen.';return;}
  status.textContent=count+' von 3 ausgewählt';tooltip.style.display='none';render();
}));
document.getElementById('aggregation').addEventListener('change',()=>{tooltip.style.display='none';render();});render();
</script></body></html>'''
    page = page.replace("__METRIC_OPTIONS__", options).replace("__SERIES_DATA__", payload)
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
