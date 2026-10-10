#!/usr/bin/env python3
"""Create an interactive, offline plot from a Withings CSV export."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
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
TEMPERATURE_VALUE_HEADER = re.compile(r"^value\s*[\(\[]\s*°\s*([cf])\s*[\)\]]$", re.IGNORECASE)


def metric_label(column: str) -> str:
    column = column.strip()
    temperature_header = TEMPERATURE_VALUE_HEADER.fullmatch(column)
    if temperature_header:
        return f"Körpertemperatur (°{temperature_header.group(1).upper()})"
    return column


def metric_unit(metric: str) -> str:
    match = re.search(r"[\(\[]\s*([^\)\]]+)\s*[\)\]]$", metric)
    if match:
        return match.group(1).strip()
    return "kg" if metric in SOURCE_METRICS else ""


def parse_numeric(value: str) -> float:
    return float(value.strip().replace(",", "."))


def week_start(date: datetime) -> str:
    return (date.date().fromordinal(date.date().toordinal() - date.weekday())).isoformat()


def read_measurements(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        date_column = next((column for column in fieldnames if column and column.strip().casefold() == "date"), None)
        if date_column is None:
            raise ValueError("Fehlende CSV-Spalte: Date")

        source_rows = list(reader)
        metric_columns = []
        normalized_source_metrics = {metric.casefold() for metric in SOURCE_METRICS}
        ignored_columns = {"comment", "comments", "note", "notes"}
        for column in fieldnames:
            if not column or column == date_column:
                continue
            label = metric_label(column)
            if column.strip().casefold() in ignored_columns:
                continue
            populated = [(row.get(column) or "").strip() for row in source_rows if (row.get(column) or "").strip()]
            if not populated:
                continue
            try:
                for value in populated:
                    parse_numeric(value)
            except ValueError as error:
                if column.strip().casefold() in normalized_source_metrics:
                    raise ValueError(f"Ungültiger Messwert in Spalte {column.strip()}: {error}") from error
                continue
            metric_columns.append((column, label))

        if not metric_columns:
            raise ValueError("Keine numerischen Messspalten gefunden. Die CSV benötigt mindestens eine Messgröße neben Date.")

        for line, row in enumerate(source_rows, start=2):
            try:
                date = datetime.fromisoformat((row.get(date_column) or "").strip())
                values = {
                    label: parse_numeric(row[column])
                    for column, label in metric_columns
                    if (row.get(column) or "").strip()
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
    present_metrics = list(dict.fromkeys(metric for row in rows for metric in row["values"]))
    ordered_metrics = [metric for metric in METRICS if metric in present_metrics]
    ordered_metrics.extend(metric for metric in present_metrics if metric not in METRICS)
    for metric in ordered_metrics:
        metric_rows = [row for row in rows if metric in row["values"]]
        if not metric_rows:
            continue
        series[metric] = {
            "unit": metric_unit(metric),
            "raw": [
                [row["date"].isoformat(sep=" "), row["values"][metric], week_start(row["date"]), row["date"].strftime("%Y-%m-01")]
                for row in metric_rows
            ],
            "week": averages(metric_rows, metric, "week"),
            "month": averages(metric_rows, metric, "month"),
        }

    payload = json.dumps(series, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    if any(metric in series for metric in ("Gewicht (kg)", "KFA (%)", "Muskelanteil (%)")):
        page_title = "Withings – Gewicht & Körperzusammensetzung"
    elif any(metric.startswith("Körpertemperatur (") for metric in series):
        page_title = "Withings – Körpertemperatur"
    else:
        page_title = "Withings – Messwerte"
    options = "\n".join(
        f'<label class="metric-option"><input type="checkbox" value="{html.escape(metric)}"{" checked" if index == 0 else ""}><span>{html.escape(metric)}</span></label>'
        for index, metric in enumerate(series)
    )
    page = '''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__</title>
<style>
*{box-sizing:border-box} body{margin:0;background:#f5f6f8;color:#242424;font:15px system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1200px;margin:30px auto;padding:0 22px} h1{font-size:23px;font-weight:600;margin:0 0 18px}
.controls{display:flex;gap:18px;align-items:end;flex-wrap:wrap;background:white;padding:16px 18px;border:1px solid #e5e5e5;border-radius:8px 8px 0 0}
.metric-picker{flex:1;min-width:280px}.metric-title{font-weight:600;margin-bottom:8px}.metric-options{display:flex;gap:8px 16px;flex-wrap:wrap}
.metric-option{display:flex;align-items:center;gap:6px;font-weight:400;white-space:nowrap}.metric-option input{accent-color:#1479c9;width:16px;height:16px;margin:0}
.aggregation-picker{display:grid;gap:6px;font-weight:550}select{font:inherit;padding:8px 34px 8px 10px;border:1px solid #c9cdd2;border-radius:5px;background:white;min-width:190px}
.selection-status{font-size:12px;color:#777;margin-top:7px;min-height:16px}
.chart{position:relative;background:white;border:1px solid #e5e5e5;border-top:0;padding:0 8px 4px;border-radius:0 0 8px 8px}svg{display:block;width:100%;height:auto}
.time-navigator{background:#fff;border:1px solid #e5e5e5;border-top:0;padding:4px 12px 12px;border-radius:0 0 8px 8px}.time-navigator svg{height:52px;touch-action:none;user-select:none}.nav-track{fill:#eef2f8;stroke:#d1d9e6}.nav-window{fill:#7ba4f8;fill-opacity:.22;stroke:#6792ef;stroke-width:1}.nav-handle{fill:#6792ef;cursor:ew-resize}.nav-window{cursor:grab}.nav-labels{display:flex;justify-content:space-between;color:#5b6470;font-size:12px}
.grid{stroke:#e2e2e2;stroke-width:1}.axis{stroke:#777;stroke-width:1}.tick{fill:#555;font-size:13px}.raw-dot{fill:#aaa;opacity:.52}
.week-line{fill:none;stroke:#1479c9;stroke-width:2}.month-line{fill:none;stroke:#e3262e;stroke-width:2.7}.month-dot{fill:#e3262e;stroke:#fff;stroke-width:1}
.hit-target{fill:transparent;stroke:transparent;pointer-events:all;cursor:crosshair}.raw-dot,.month-dot{cursor:crosshair}
.tooltip{display:none;position:absolute;z-index:2;pointer-events:none;min-width:210px;max-width:320px;background:rgba(255,255,255,.97);border:1px solid #c9cdd2;border-radius:6px;box-shadow:0 3px 14px #0002;padding:10px 12px;font-size:13px;line-height:1.5}
.tooltip-date{font-weight:650;margin-bottom:5px}.tooltip-metric{font-weight:600;margin-top:4px}.tooltip-values{color:#444}
.hint{color:#777;font-size:13px;margin:12px 2px}@media(max-width:600px){main{margin:16px auto;padding:0 10px}.controls{gap:12px}.metric-picker{min-width:100%}.aggregation-picker,select{width:100%}}
</style></head><body><main><h1>__PAGE_TITLE__</h1>
<section class="controls"><div class="metric-picker"><div class="metric-title">Messgrößen (bis zu 3)</div><div class="metric-options" id="metric-options">__METRIC_OPTIONS__</div><div class="selection-status" id="selection-status">1 von 3 ausgewählt</div></div>
<label class="aggregation-picker" for="aggregation">Aggregation<select id="aggregation"><option value="both">Woche + Monat</option><option value="week">Wöchentlich</option><option value="month">Monatlich</option></select></label></section>
<div class="chart"><svg id="weight-chart" viewBox="0 0 1100 465" role="img" aria-label="Interaktiver Verlauf der Withings-Messwerte"></svg><div class="tooltip" id="tooltip"></div></div>
<div class="time-navigator"><svg id="time-navigator" viewBox="0 0 1100 52" aria-label="Zeitraum auswählen"></svg><div class="nav-labels"><span id="range-start"></span><span id="range-end"></span></div></div>
<p class="hint">Graue Punkte zeigen Einzelmessungen. Wochenmittel sind blau, Monatsmittel rot. Beim Überfahren eines Punkts erscheinen Einzelwert und eingeschaltete Mittelwerte.</p></main>
<script>
const series=__SERIES_DATA__;
const svg=document.getElementById('weight-chart'),tooltip=document.getElementById('tooltip'),nav=document.getElementById('time-navigator'),NS='http://www.w3.org/2000/svg';
const NAV_W=1100,NAV_L=8,NAV_R=8,NAV_PW=NAV_W-NAV_L-NAV_R;
const domainDates=Object.values(series).flatMap(data=>data.raw.map(point=>new Date(point[0]).getTime())),domainStart=Math.min(...domainDates),domainEnd=Math.max(...domainDates);
let viewStart=domainStart,viewEnd=domainEnd,navDrag=null;
function el(tag,attrs={},parent=svg){const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);parent.appendChild(node);return node;}
function text(x,y,value,anchor='end',parent=svg){const node=el('text',{x,y,'text-anchor':anchor,class:'tick'},parent);node.textContent=value;return node;}
function pathFor(points,x,y){return points.map((point,index)=>(index?'L':'M')+x(new Date(point[0]).getTime()).toFixed(1)+','+y(point[1]).toFixed(1)).join(' ');}
function axisScale(values,unit){
  let low=Math.min(...values),high=Math.max(...values),span=high-low;
  if(span===0)span=Math.max(Math.abs(low)*.02,unit==='kg'?.5:.5);
  const roughStep=span/5,power=10**Math.floor(Math.log10(roughStep)),fraction=roughStep/power;
  const step=(fraction<=1?1:fraction<=2?2:fraction<=2.5?2.5:fraction<=5?5:10)*power;
  low=Math.floor((low-span*.04)/step)*step;high=Math.ceil((high+span*.04)/step)*step;
  if(unit==='kg')low=Math.max(0,low);
  if(high<=low)high=low+step;
  return {low,high,step};
}
function selectedMetrics(){return [...document.querySelectorAll('#metric-options input:checked')].map(input=>input.value);}
function formatDate(value){return new Date(value).toLocaleDateString('de-DE');}
function updateRange(start,end){const span=domainEnd-domainStart;viewStart=Math.max(domainStart,Math.min(start,domainEnd-span*.005));viewEnd=Math.max(viewStart+span*.005,Math.min(end,domainEnd));tooltip.style.display='none';render();renderNavigator();}
function renderNavigator(){
  nav.replaceChildren();const x=value=>NAV_L+(value-domainStart)/(domainEnd-domainStart||1)*NAV_PW;
  el('rect',{x:NAV_L,y:12,width:NAV_PW,height:28,rx:4,class:'nav-track'},nav);
  const overview=Object.values(series).find(data=>data.raw.length)?.raw||[];
  if(overview.length){const vals=overview.map(point=>point[1]),lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1;
    const path=overview.map((point,i)=>(i?'L':'M')+x(new Date(point[0]).getTime()).toFixed(1)+','+(35-(point[1]-lo)/span*18).toFixed(1)).join(' ');
    el('path',{d:path,fill:'none',stroke:'#b8c8e3','stroke-width':1.2},nav);
  }
  const left=x(viewStart),right=x(viewEnd);
  el('rect',{x:left,y:7,width:Math.max(1,right-left),height:38,rx:3,class:'nav-window'},nav);
  el('rect',{x:left-2,y:8,width:6,height:36,rx:2,class:'nav-handle','data-handle':'start'},nav);
  el('rect',{x:right-4,y:8,width:6,height:36,rx:2,class:'nav-handle','data-handle':'end'},nav);
  document.getElementById('range-start').textContent=formatDate(viewStart);document.getElementById('range-end').textContent=formatDate(viewEnd);
}
nav.addEventListener('pointerdown',event=>{const p=navPoint(event),target=event.target.closest('[data-handle]');navDrag={type:target?target.dataset.handle:'window',x:p,timeStart:viewStart,timeEnd:viewEnd};nav.setPointerCapture(event.pointerId);});
nav.addEventListener('pointermove',event=>{if(!navDrag)return;const p=navPoint(event),delta=(p-navDrag.x)/(NAV_W)*(domainEnd-domainStart);if(navDrag.type==='start')updateRange(Math.min(navDrag.timeStart+delta,viewEnd-(domainEnd-domainStart)*.005),viewEnd);else if(navDrag.type==='end')updateRange(viewStart,Math.max(navDrag.timeEnd+delta,viewStart+(domainEnd-domainStart)*.005));else updateRange(navDrag.timeStart+delta,navDrag.timeEnd+delta);});
nav.addEventListener('pointerup',()=>navDrag=null);nav.addEventListener('pointercancel',()=>navDrag=null);
function navPoint(event){const rect=nav.getBoundingClientRect();return NAV_L+(event.clientX-rect.left)/rect.width*NAV_W;}
function showTooltip(event,date,plotMetric,period){
  const mode=document.getElementById('aggregation').value,timestamp=new Date(date).getTime();
  const heading=document.createElement('div');heading.className='tooltip-date';
  heading.textContent=period==='week'?'Woche ab '+new Date(date).toLocaleDateString('de-DE'):period==='month'?'Monat ab '+new Date(date).toLocaleDateString('de-DE'):new Date(date).toLocaleString('de-DE');tooltip.replaceChildren(heading);
  for(const metric of [plotMetric]){
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
function bindTooltip(node,date,metric,period='raw'){node.addEventListener('mouseenter',event=>showTooltip(event,date,metric,period));node.addEventListener('mousemove',event=>showTooltip(event,date,metric,period));node.addEventListener('mouseleave',()=>tooltip.style.display='none');}
function render(){
  const metrics=selectedMetrics(),mode=document.getElementById('aggregation').value,W=1100,PANEL=420,H=metrics.length*PANEL+45,L=82,R=30,B=54,PW=W-L-R;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.replaceChildren();
  const start=viewStart,end=viewEnd,x=value=>L+(value-start)/(end-start||1)*PW;
  metrics.forEach((metric,index)=>{
    const data=series[metric],unit=data.unit,top=42+index*PANEL,bottom=top+PANEL-B,PH=bottom-top;
    let visiblePoints=data.raw.filter(point=>{const stamp=new Date(point[0]).getTime();return stamp>=start&&stamp<=end;});
    if(mode==='week'||mode==='both')visiblePoints=visiblePoints.concat(data.week.filter(point=>{const stamp=new Date(point[0]).getTime();return stamp>=start&&stamp<=end;}));
    if(mode==='month'||mode==='both')visiblePoints=visiblePoints.concat(data.month.filter(point=>{const stamp=new Date(point[0]).getTime();return stamp>=start&&stamp<=end;}));
    const scale=axisScale(visiblePoints.map(point=>point[1]),unit),{low,high,step}=scale,y=value=>top+(high-value)/(high-low)*PH;
    text(L,top-17,metric,'start');
    for(let value=low;value<=high+step*.001;value+=step){const yy=y(value);el('line',{x1:L,y1:yy,x2:W-R,y2:yy,class:'grid'});text(L-12,yy+4,value.toLocaleString('de-DE',{maximumFractionDigits:2}));}
    el('line',{x1:L,y1:top,x2:L,y2:bottom,class:'axis'});el('line',{x1:L,y1:bottom,x2:W-R,y2:bottom,class:'axis'});
    for(const point of data.raw){const stamp=new Date(point[0]).getTime();if(stamp<start||stamp>end)continue;const dot=el('circle',{cx:x(stamp),cy:y(point[1]),r:2.7,class:'raw-dot'});bindTooltip(dot,point[0],metric);}
    if(mode==='week'||mode==='both'){
      const visible=data.week.filter(point=>new Date(point[0]).getTime()>=start&&new Date(point[0]).getTime()<=end);el('path',{d:pathFor(visible,x,y),class:'week-line'});
      for(const point of visible){const target=el('circle',{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:7,class:'hit-target'});bindTooltip(target,point[0],metric,'week');}
    }
    if(mode==='month'||mode==='both'){
      const visible=data.month.filter(point=>new Date(point[0]).getTime()>=start&&new Date(point[0]).getTime()<=end);el('path',{d:pathFor(visible,x,y),class:'month-line'});
      for(const point of visible){const dot=el('circle',{cx:x(new Date(point[0]).getTime()),cy:y(point[1]),r:3.8,class:'month-dot'});bindTooltip(dot,point[0],metric,'month');}
    }
    const spanYears=(end-start)/(365.25*86400000),tickDates=[];
    if(spanYears>=3){
      const firstYear=new Date(start).getUTCFullYear();
      const lastYear=new Date(end).getUTCFullYear();
      const yearStep=Math.max(1,Math.ceil((lastYear-firstYear)/6));
      for(let year=Math.ceil(firstYear/yearStep)*yearStep;year<=lastYear;year+=yearStep)tickDates.push(new Date(Date.UTC(year,0,1)));
    }else{
      const first=new Date(start),last=new Date(end);
      const firstMonth=first.getUTCFullYear()*12+first.getUTCMonth();
      const lastMonth=last.getUTCFullYear()*12+last.getUTCMonth();
      const monthStep=Math.max(1,Math.ceil((lastMonth-firstMonth+1)/7));
      for(let month=Math.ceil(firstMonth/monthStep)*monthStep;month<=lastMonth;month+=monthStep)
        tickDates.push({date:new Date(Date.UTC(Math.floor(month/12),month%12,1)),yearBoundary:month%12===0});
    }
    for(const tick of tickDates){
      const date=tick.date||tick;
      const stamp=date.getTime();if(stamp<start||stamp>end)continue;
      const xx=x(stamp);
      if(tick.yearBoundary)el('line',{x1:xx,y1:top,x2:xx,y2:bottom,class:'grid year-boundary'});
      else el('line',{x1:xx,y1:top,x2:xx,y2:bottom,class:'grid'});
      if(index===metrics.length-1){
        const label=spanYears>=3?String(date.getUTCFullYear()):date.toLocaleDateString('de-DE',{month:'short',year:tick.yearBoundary?'numeric':undefined,timeZone:'UTC'});
        text(xx,bottom+25,label,'middle');
      }
    }
  });
  const legend=el('g',{transform:`translate(${W-R-340},20)`});
  el('circle',{cx:5,cy:0,r:3,class:'raw-dot'},legend);text(17,4,'Einzelmessungen','start',legend);
  el('line',{x1:145,y1:0,x2:167,y2:0,class:'week-line'},legend);text(174,4,'Wochenmittel','start',legend);
  el('line',{x1:265,y1:0,x2:287,y2:0,class:'month-line'},legend);text(294,4,'Monatsmittel','start',legend);
}
svg.addEventListener('wheel',event=>{event.preventDefault();const rect=svg.getBoundingClientRect(),coord=(event.clientX-rect.left)/rect.width*1100,fraction=Math.max(0,Math.min(1,(coord-82)/(1100-82-30))),anchor=viewStart+fraction*(viewEnd-viewStart),factor=event.deltaY<0?.8:1.25;const span=Math.min(domainEnd-domainStart,Math.max((domainEnd-domainStart)*.005,(viewEnd-viewStart)*factor));updateRange(anchor-fraction*span,anchor+(1-fraction)*span);},{passive:false});
document.querySelectorAll('#metric-options input').forEach(input=>input.addEventListener('change',event=>{
  const count=selectedMetrics().length,status=document.getElementById('selection-status');
  if(count>3){event.target.checked=false;status.textContent='Es können höchstens 3 Messgrößen ausgewählt werden.';return;}
  if(count===0){event.target.checked=true;status.textContent='Bitte mindestens eine Messgröße ausgewählt lassen.';return;}
  status.textContent=count+' von 3 ausgewählt';tooltip.style.display='none';render();
}));
document.getElementById('aggregation').addEventListener('change',()=>{tooltip.style.display='none';render();});render();renderNavigator();
</script></body></html>'''
    escaped_title = html.escape(page_title)
    page = page.replace("__PAGE_TITLE__", escaped_title).replace("__METRIC_OPTIONS__", options).replace("__SERIES_DATA__", payload)
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interaktiver Plot für einen Withings-CSV-Export")
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
