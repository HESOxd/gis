"""Build a fully offline SVG map; no tile server, external JS, or tracking."""
import html
import json
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, LineString
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed/accessibility.gpkg'


def title(value): return '<title>'+html.escape(value)+'</title>'
def path(geometry):
    if geometry.is_empty:return ''
    typ=geometry.geom_type
    if typ=='Polygon':
        return ' '.join('M'+' L'.join(f'{x:.1f},{-y:.1f}' for x,y in ring.coords)+' Z' for ring in [geometry.exterior,*geometry.interiors])
    if typ=='LineString': return 'M'+' L'.join(f'{x:.1f},{-y:.1f}' for x,y in geometry.coords)
    if hasattr(geometry,'geoms'):return ' '.join(path(g) for g in geometry.geoms)
    return ''


def main():
    homes=gpd.read_file(DATA,layer='homes')
    districts=gpd.read_file(DATA,layer='districts')
    roads=gpd.read_file(ROOT/'data/cartography/streets.geojson')
    metro=gpd.read_file(ROOT/'data/cartography/metro.geojson')
    facilities=gpd.read_file(DATA,layer='facilities')
    parks=gpd.read_file(DATA,layer='parks')
    water=gpd.read_file(DATA,layer='water')
    x0,y0,x1,y1=districts.total_bounds
    parts=[f'<svg id="map" viewBox="{x0-120} {-y1-120} {x1-x0+240} {y1-y0+240}" role="img" aria-label="Карта доступности школ и поликлиник">']
    for frame,color in [(parks,'#e0eadb'),(water,'#bedee5')]:
        parts.extend(f'<path d="{path(g)}" fill="{color}" fill-rule="evenodd"/>' for g in frame.geometry)
    parts.append('<g fill="none" stroke="#d0d3ce" stroke-width="2">')
    parts.extend(f'<path d="{path(g)}"/>' for g in roads.geometry);parts.append('</g>')
    # Labels and metro are real contextual landmarks, independent of routing.
    labels=[]
    for name in ['Краснобогатырская улица','Большая Черкизовская улица','Открытое шоссе','Электрозаводская улица','улица Хромова']:
        rows=roads.loc[roads.name==name]
        if len(rows):
            g=max(rows.geometry,key=lambda g:g.length);p=g.interpolate(.5,normalized=True)
            labels.append(f'<text x="{p.x}" y="{-p.y}" text-anchor="middle" font-size="65" fill="#465b60" style="paint-order:stroke;stroke:#fbfaf7;stroke-width:15px;pointer-events:none">{html.escape(name)}</text>')
    for _,h in homes.iterrows():
        school=f"{h.school_min:.0f} мин" if h.school_status!='unknown' else 'не удалось оценить'
        clinic=f"{h.clinic_min:.0f} мин" if h.clinic_status!='unknown' else 'не удалось оценить'
        details=f"{h['address'] or h['id']} · {h['district']} · школа: {school}; поликлиника: {clinic}"
        parts.append(f'<path class="home" data-school="{h.school_status}" data-clinic="{h.clinic_status}" d="{path(h.geometry)}" stroke="white" stroke-width=".8" fill-rule="evenodd">{title(details)}</path>')
    for _,b in districts.iterrows():
        parts.append(f'<path d="{path(b.geometry)}" fill="none" stroke="#45515b" stroke-width="8" stroke-dasharray="25 15" pointer-events="none"/>')
        p=b.geometry.representative_point()
        parts.append(f'<text x="{p.x}" y="{-p.y}" text-anchor="middle" font-size="105" font-weight="700" fill="#233746" style="paint-order:stroke;stroke:#fbfaf7;stroke-width:18px;pointer-events:none">{html.escape(b.district)}</text>')
    for _,f in facilities.iterrows():
        if any(g.buffer(100).covers(f.geometry) for g in districts.geometry):
            p=f.geometry
            details=f"{f['name']} · OSM {f['id']} · привязка {f.snap_m:.0f} м"
            parts.append(f'<circle class="facility" data-kind="{f.kind}" cx="{p.x}" cy="{-p.y}" r="18" fill="#233c54" stroke="white" stroke-width="5">{title(details)}</circle>')
    parts.extend(labels)
    for _,m in metro.iterrows():
        if not m['name']:continue
        p=m.geometry
        if not (x0-350<p.x<x1+350 and y0-350<p.y<y1+350):continue
        parts.append(f'<rect x="{p.x-35}" y="{-p.y-35}" width="70" height="70" fill="#fbfaf7" stroke="#b74742" stroke-width="6"/>'
                     f'<text x="{p.x}" y="{-p.y+22}" text-anchor="middle" font-size="58" font-weight="700" fill="#b74742">М</text>'
                     f'<text x="{p.x+65}" y="{-p.y+55}" font-size="65" fill="#203d47" style="paint-order:stroke;stroke:#fbfaf7;stroke-width:15px;pointer-events:none">{html.escape(m["name"])}</text>')
    parts.append('</svg>')
    report=json.loads((ROOT/'outputs/quality_report.json').read_text())
    table=''.join('<tr>'+''.join(f'<td>{html.escape(str({'school':'Школы','clinic':'Поликлиники'}.get(r[k],r[k])))}</td>' for k in ['district','kind','homes_over_15','people_est_over_15','homes_unknown'])+'</tr>' for r in report['summary'])
    document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>15 минут пешком — Богородское и Преображенское</title>
<style>*{box-sizing:border-box}body{margin:0;background:#fbfaf7;color:#203d47;font:15px system-ui,sans-serif}main{max-width:1450px;margin:auto;padding:28px}h1{font-size:clamp(25px,4vw,42px);line-height:1.12;max-width:900px;margin:12px 0}p{line-height:1.5;max-width:850px}.tag{font-size:12px;letter-spacing:.07em;color:#8b4737}button{border:1px solid #b8c3c1;background:transparent;padding:10px 18px;border-radius:8px;color:inherit;font:inherit;cursor:pointer}button[aria-pressed=true]{background:#203d47;color:white}nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:20px 0}.panel{border:1px solid #d5d9d2;border-radius:15px;overflow:hidden;background:#fbfaf7}svg{width:100%;height:min(78vh,1000px);display:block;touch-action:none;cursor:grab}svg:active{cursor:grabbing}.legend{display:flex;flex-wrap:wrap;gap:18px;font-size:13px;padding:15px;border-top:1px solid #d5d9d2}.legend span::before{content:'';display:inline-block;width:12px;height:12px;margin-right:6px;background:var(--c);border-radius:2px}.note{font-size:13px;color:#5b676e}table{border-collapse:collapse;font-size:13px;width:100%;max-width:900px}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid #d9ddd6}a{color:#246f68}.table{overflow-x:auto}.status{padding:16px;background:#eee7d7;border-radius:10px}footer{margin:25px 0;font-size:12px;color:#657176}.city-layout{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(270px,1fr);gap:24px}aside{padding:24px;background:white;border:1px solid #dce3e1;border-radius:15px}aside h2{font-size:21px;margin-top:8px}aside p{line-height:1.6}@media(max-width:850px){.city-layout{grid-template-columns:1fr}aside{padding:20px}}body{background:#fbfaf7;color:#203d47}</style>
<main><div class="tag">ГИС-ПОРТФОЛИО / ПРОЕКТ 01 / ПРЕДВАРИТЕЛЬНЫЙ РАСЧЁТ</div><h1>Школа и поликлиника<br>за 15 минут пешком</h1><p>Богородское и Преображенское. Цвет показывает оценку доступности каждого жилого здания по сети OpenStreetMap при скорости 5 км/ч.</p><nav><button data-mode="school" aria-pressed="true">Школы</button><button data-mode="clinic" aria-pressed="false">Поликлиники</button><button id="reset">Весь район</button><span class="note">Масштаб — колесо; сдвиг — перетаскивание; детали — наведите на объект.</span></nav><div class="city-layout"><div class="panel">__SVG__<div class="legend"><span style="--c:#25866c">До 10 мин</span><span style="--c:#e3b95c">10–15 мин</span><span style="--c:#d95650">Более 15 мин</span><span style="--c:#8c8c94">Нет привязки / маршрута</span></div></div><aside><h2>Как читать карту</h2><p>Найдите знакомую улицу или метро. Цвет жилого дома показывает время пешком до ближайшего объекта выбранного типа.</p><p><strong>Красные дома</strong> — путь дольше 15 минут. Серые — оценка недоступна; они не записаны в дефицит.</p><h2>Что можно узнать</h2><p>Переключите школы и поликлиники. Наведите на дом: увидите адрес и время для обоих типов объектов.</p><p>М — метро для ориентирования. Тёмные точки — школы или поликлиники OSM.</p><p class="note">Расчёт не проверяет прикрепление, вместимость и фактическую доступность входов.</p></aside></div><p class="status">Это оценка по OSM: официальный реестр data.mos.ru ещё не подключён. Число жителей смоделировано по площади и этажности домов; районные итоги за 2025 год взяты из вторичного источника со ссылкой на Росстат и требуют проверки оригинала.</p><h2>Где обнаружен возможный дефицит</h2><div class="table"><table><thead><tr><th>Район</th><th>Тип</th><th>Домов вне 15 мин</th><th>Жителей, оценка</th><th>Нет маршрута / привязки</th></tr></thead><tbody>__TABLE__</tbody></table></div><p class="note">Дома без маршрута или надёжной привязки не включены в дефицит. Население по двум категориям не суммируется: одни и те же жители могут попадать в обе. Расчёт не учитывает прикрепление, вместимость, очереди и расписание.</p><p><a href="../README.md">Методика и воспроизведение</a> · <a href="district_deficit.csv">Скачать таблицу CSV</a> · <a href="../moscow_walk_access.qgz">Проект QGIS</a></p><footer>Данные OSM: 01.11.2026 · © OpenStreetMap contributors · ODbL 1.0 · Проекция анализа EPSG:32637. Карта работает без интернета.</footer></main>
<script>const svg=document.querySelector('#map'),original=svg.getAttribute('viewBox').split(' ').map(Number),colors={within_10:'#25866c',within_15:'#e3b95c',over_15:'#d95650',unknown:'#8c8c94'};function mode(kind){document.querySelectorAll('.home').forEach(e=>e.setAttribute('fill',colors[e.dataset[kind]]));document.querySelectorAll('.facility').forEach(e=>e.style.display=e.dataset.kind===kind?'':'none');document.querySelectorAll('[data-mode]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.mode===kind)))}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>mode(b.dataset.mode));let box=[...original],drag=null;function draw(){svg.setAttribute('viewBox',box.join(' '))}document.querySelector('#reset').onclick=()=>{box=[...original];draw()};svg.addEventListener('wheel',e=>{e.preventDefault();const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse()),scale=e.deltaY>0?1.16:1/1.16;if(box[2]*scale<150||box[2]*scale>original[2]*4)return;box=[p.x+(box[0]-p.x)*scale,p.y+(box[1]-p.y)*scale,box[2]*scale,box[3]*scale];draw()},{passive:false});svg.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,box:[...box],scale:svg.getScreenCTM().a};svg.setPointerCapture(e.pointerId)});svg.addEventListener('pointermove',e=>{if(!drag)return;box=[drag.box[0]-(e.clientX-drag.x)/drag.scale,drag.box[1]-(e.clientY-drag.y)/drag.scale,drag.box[2],drag.box[3]];draw()});svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);mode('school');</script></html>'''
    document=document.replace('__SVG__',''.join(parts)).replace('__TABLE__',table)
    (ROOT/'outputs/interactive_map.html').write_text(document)
    print('Saved offline interactive map')

if __name__=='__main__':main()
