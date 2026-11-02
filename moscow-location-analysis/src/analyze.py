"""Transparent OSM location screening. All distances in EPSG:32637."""
import hashlib
import json
import math
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely import STRtree
from shapely.ops import unary_union
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'; DATA=ROOT/'data/processed'; OUT=ROOT/'outputs'
CRS='EPSG:32637'; SIDE=150; RADIUS=500; SPACING=600
SCENARIOS={
 'base':([.45,.25,.20,.10],.30),
 'residential':([.70,.10,.10,.10],.30),
 'commuter':([.20,.35,.35,.10],.30),
 'strong_competition':([.45,.25,.20,.10],.50),
 'weak_competition':([.45,.25,.20,.10],.15),
}


def load(name):
 return gpd.read_file(RAW/f'{name}.geojson').to_crs(CRS)


def clean_poi(frame):
 """Collapse only close, same-name representations; retain ambiguous cases."""
 frame=frame.drop_duplicates('osm_id').sort_values('osm_id').reset_index(drop=True)
 keep=[]; removed=[]
 for _,r in frame.iterrows():
  name=str(r['name'] or '').strip().casefold()
  duplicate=next((o for o in keep if r.kind==o.kind and (
   r.geometry.distance(o.geometry)<2 or
   (name and name==str(o['name'] or '').strip().casefold() and r.geometry.distance(o.geometry)<35))),None)
  if duplicate is None:keep.append(r)
  else:removed.append({'removed':r.osm_id,'kept':duplicate.osm_id,'kind':r.kind})
 return gpd.GeoDataFrame(keep,crs=CRS).reset_index(drop=True),removed


def cluster_metro(frame):
 """Connected clusters of entrances within 250 m are hubs, not passenger counts."""
 if frame.empty:return frame.copy()
 import networkx as nx
 coords=np.array([(p.x,p.y) for p in frame.geometry]); tree=cKDTree(coords)
 graph=nx.Graph();graph.add_nodes_from(range(len(frame)));graph.add_edges_from(tree.query_pairs(250))
 hubs=[]
 for n,ids in enumerate(nx.connected_components(graph),1):
  sub=frame.iloc[sorted(ids)]; points=unary_union(sub.geometry.to_list())
  hubs.append({'hub_id':n,'entrances':len(sub),'name':' / '.join(sorted(set(str(x) for x in sub['name'] if x))),
               'geometry':points.centroid})
 return gpd.GeoDataFrame(hubs,crs=CRS)


def hex_grid(study):
 x0,y0,x1,y1=study.bounds; height=math.sqrt(3)*SIDE; rows=[]
 for column,x in enumerate(np.arange(math.floor(x0/(1.5*SIDE))*1.5*SIDE,x1+SIDE,1.5*SIDE)):
  for row,y in enumerate(np.arange(math.floor(y0/height)*height,y1+height,height)):
   y+=height/2*(column%2)
   point=Point(x,y)
   if not study.covers(point):continue
   poly=Polygon([(x+SIDE*math.cos(k*math.pi/3),y+SIDE*math.sin(k*math.pi/3)) for k in range(6)]).intersection(study)
   rows.append({'cell_id':f'H{column:03}_{row:03}','cx':x,'cy':y,'geometry':poly})
 return gpd.GeoDataFrame(rows,crs=CRS)


def nearby(points,centers,weights=None):
 if not len(points):return np.zeros(len(centers))
 tree=cKDTree(np.array([(p.x,p.y) for p in points]));ids=tree.query_ball_point(centers,RADIUS)
 if weights is None:return np.array([len(i) for i in ids])
 return np.array([float(np.array(weights)[i].sum()) for i in ids])


def export(frame,name,gpkg):
 frame.to_file(gpkg,layer=name,driver='GPKG',dataset_options={'VERSION':'1.3'})
 frame.to_crs(4326).to_file(DATA/f'{name}.geojson',driver='GeoJSON')


def main():
 DATA.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
 districts=load('districts');homes=load('homes');roads=load('walk_network')
 study=unary_union(districts.geometry.to_list());extent=study.buffer(RADIUS+SIDE)
 candidates=load('osm_poi_candidates');candidates=candidates[candidates.geometry.intersects(extent)].copy()
 poi,removed=clean_poi(candidates)
 hubs=cluster_metro(poi[poi.kind=='metro'])
 cells=hex_grid(study);centers=cells[['cx','cy']].to_numpy()
 cells['district']=[next(d.district for _,d in districts.iterrows() if d.geometry.covers(Point(x,y))) for x,y in centers]
 cells['residents_500m']=nearby(homes.geometry.representative_point(),centers,homes.population_est)
 for kind in ['cafe','office','stop']:
  cells[kind+'_500m']=nearby(poi[poi.kind==kind].geometry,centers).astype(int)
 cells['metro_hubs_500m']=nearby(hubs.geometry,centers).astype(int)
 home_tree=STRtree(homes.geometry.to_list());road_tree=STRtree(roads.geometry.to_list())
 home_geoms=homes.geometry.to_list();road_geoms=roads.geometry.to_list()
 cells['residential_area_m2']=[sum(home_geoms[int(i)].intersection(poly).area for i in home_tree.query(poly)) for poly in cells.geometry]
 cells['network_distance_m']=[Point(x,y).distance(road_geoms[int(road_tree.nearest(Point(x,y)))]) for x,y in centers]
 cells['eligible']=(cells.residents_500m>=300)&(cells.network_distance_m<=60)&(cells.residential_area_m2>=100)
 eligible=cells[cells.eligible]
 assert len(eligible)>=5
 fields=['residents_500m','office_500m','metro_hubs_500m','stop_500m','cafe_500m']
 scales={field:float(eligible[field].quantile(.95)) for field in fields}
 for field in fields:cells['norm_'+field]=(cells[field]/max(scales[field],1)).clip(0,1)
 normalized=cells[['norm_'+f for f in fields]].to_numpy()
 for scenario,(weights,penalty) in SCENARIOS.items():
  cells['score_'+scenario]=100*(normalized[:,:4]@np.array(weights)-penalty*normalized[:,4])
  cells['rank_'+scenario]=cells.loc[cells.eligible,'score_'+scenario].rank(method='min',ascending=False)
 cells['scenario_top20_count']=sum(cells['rank_'+s].le(20).astype(int) for s in SCENARIOS)
 ordered=cells[cells.eligible].sort_values(['score_base','cell_id'],ascending=[False,True])
 selected=[]
 for _,r in ordered.iterrows():
  p=Point(r.cx,r.cy)
  if all(p.distance(Point(o.cx,o.cy))>=SPACING for o in selected):selected.append(r)
  if len(selected)==5:break
 top=gpd.GeoDataFrame(selected,crs=CRS).reset_index(drop=True)
 top['place']=np.arange(1,len(top)+1)
 refs=homes.copy();refs=refs[refs.address.notna()&refs.address.ne('')]
 ref_tree=STRtree(refs.geometry.to_list())
 top['landmark']=[refs.iloc[int(ref_tree.nearest(Point(r.cx,r.cy)))].address for _,r in top.iterrows()]
 cells['top5_place']=cells.cell_id.map(dict(zip(top.cell_id,top.place)))
 buffers=gpd.GeoDataFrame(top[['cell_id','place','landmark']].copy(),
  geometry=[Point(r.cx,r.cy).buffer(RADIUS) for _,r in top.iterrows()],crs=CRS)
 gpkg=DATA/'location_analysis.gpkg'
 if gpkg.exists():gpkg.unlink()
 for frame,name in [(districts,'districts'),(cells,'hexagons'),(top,'top5'),(buffers,'top5_buffers'),(poi,'poi'),(hubs,'metro_hubs'),(homes,'homes'),(roads,'walk_network')]:export(frame,name,gpkg)
 top.drop(columns='geometry').to_csv(OUT/'top5.csv',index=False,encoding='utf-8-sig')
 cells.drop(columns='geometry').to_csv(OUT/'all_cells.csv',index=False,encoding='utf-8-sig')
 pd.DataFrame(removed).to_csv(OUT/'removed_poi_duplicates.csv',index=False,encoding='utf-8-sig')
 report={'status':'PRELIMINARY_PROXY_SCREENING_NOT_PROFIT_FORECAST','crs':CRS,'hex_side_m':SIDE,'radius_m':RADIUS,
 'distance_model':'euclidean','top5_min_spacing_m':SPACING,'cells':len(cells),'eligible_cells':int(cells.eligible.sum()),
 'poi_before_dedup':len(candidates),'poi_after_dedup':len(poi),'poi_by_kind':poi.kind.value_counts().to_dict(),
 'metro_hubs':len(hubs),'normalization_p95':scales,'scenarios':SCENARIOS,
 'passenger_flow_available':False,'office_employees_available':False,'population_primary_verified':False,
 'edge_effect':'housing demand excludes residents outside the two study districts; nearby POIs have a margin',
 'top5':top.drop(columns='geometry').replace({np.nan:None}).to_dict('records'),
 'inputs_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file()}}
 (OUT/'quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 # Independent output checks: population, scores, boundary, separation, unique keys.
 assert abs(homes.population_est.sum()-198382)<1e-4
 assert cells.cell_id.is_unique and poi.osm_id.is_unique and len(top)==5
 assert top.eligible.all() and top.network_distance_m.le(60).all()
 assert all(study.covers(Point(r.cx,r.cy)) for _,r in top.iterrows())
 assert all(Point(a.cx,a.cy).distance(Point(b.cx,b.cy))>=SPACING for i,a in top.iterrows() for j,b in top.iterrows() if j>i)
 assert np.isfinite(cells.score_base).all() and cells.geometry.is_valid.all()
 maps(districts,homes,roads,cells,top,poi)
 docs(report)
 print(json.dumps({'checks':'PASS','cells':len(cells),'eligible':int(cells.eligible.sum()),'top5':top[['place','cell_id','landmark','score_base']].to_dict('records')},ensure_ascii=False,indent=2))


def maps(districts,homes,roads,cells,top,poi):
 from plot import render
 render()


def docs(report):
 top=report['top5'];table='\n'.join(f"| {r['place']} | {r['landmark']} | {r['score_base']:.1f} | {r['residents_500m']:.0f} | {r['office_500m']} | {r['metro_hubs_500m']} | {r['cafe_500m']} |" for r in top)
 (ROOT/'README.md').write_text(f'''# Где проверить локацию кофейни

Богородское и Преображенское · проект 02 · **предварительный анализ на прокси спроса**.

**Оформление карт:** улицы, метро, адреса-ориентиры и пояснения. [Описание оформления](docs/cartography.md).

![Рейтинг](outputs/location_ranking.png)

**Задача.** Составить топ-5 территорий для дальнейшего обследования под кофейню: спрос рядом с жильём, офисами и транспортом против числа конкурентов. Точка на карте — центр ячейки, а не предложенное в аренду помещение.

**Данные.** Снимок OSM от 01.11.2026, повторно использованный из проекта 01: кафе, офисные объекты, остановки, метро, жилые здания, границы, сеть проходов. После очистки — {report['poi_after_dedup']} POI в зоне районов с запасом 650 м. Население — модель площади × этажности из проекта 01, с вторичными районными итогами за 2025 год. Пассажиропоток data.mos.ru и число работников офисов отсутствуют: транспортные узлы и офисы используются как **инфраструктурные индикаторы**, а не измеренные люди.

**Метод.** EPSG:32637. Гексагоны со стороной 150 м, радиус обслуживания 500 м **по прямой**. Кандидаты: ≥300 оценочных жителей в радиусе, ≥100 м² жилых пятен внутри ячейки, центр ≤60 м от сети. Всего {report['cells']} ячеек, пригодных {report['eligible_cells']}. Показатели нормируются на 95-й процентиль пригодных ячеек и ограничиваются единицей. Балл = 100 × (0.45 × жители + 0.25 × офисы + 0.20 × метро + 0.10 × остановки − 0.30 × кафе). Метро сгруппировано из входов в узлы по связности в пределах 250 м. Топ-5 выбирается с расстоянием ≥600 м между центрами. Проверены ещё четыре набора весов; [устойчивость рейтинга](outputs/top5_sensitivity.png).

| № | Ориентир рядом | Балл | Жители 500 м, оценка | Офисы | Узлы метро | Кафе |
|---|---|---:|---:|---:|---:|---:|
{table}

**Вывод.** Это адресный шорт-лист для проверки входов, аренды, видимости, реального потока и конкурентов. Близость к метро и число офисов не заменяют наблюдение трафика; отсутствие кафе в OSM не доказывает отсутствие конкуренции. Жильё за границами двух районов не включено в спрос, поэтому крайние ячейки могут быть занижены. Пешеходные обходы, нежилые этажи, доходы, аренда и выручка не моделируются. Зоны разных кандидатов могут перекрываться; население по ним не суммируется.

[Топ-5 CSV](outputs/top5.csv) · [все ячейки](outputs/all_cells.csv) · [GeoPackage](data/processed/location_analysis.gpkg) · [QGIS](moscow_location_analysis.qgz) · [пост](docs/post.md) · [аудит](outputs/quality_report.json).

Воспроизведение из этой папки: `python3 -m venv .venv`, затем `.venv/bin/pip install -r requirements.lock.txt` и `.venv/bin/python src/analyze.py`. Все входы для основного анализа находятся в `data/raw`; соседний проект 01 требуется только для необязательного повторного извлечения полного OSM через `src/extract_osm.py`. Карты и проверки генерируются одним запуском. Проект QGIS создаёт `src/qgis_project.py` через Python из установки QGIS.

Код MIT; геоданные © OpenStreetMap contributors, ODbL 1.0. Даты, контрольные суммы, формулы и все сценарии — в отчёте качества. Измеренный пассажиропоток и первичные итоги населения требуют подключения перед окончательным выпуском кейса.
''')
 reasons=[]
 for r in top:
  reasons.append(f"{r['place']}. **Окрестности {r['landmark']}**: около {round(r['residents_500m']/100)*100:,} оценочных жителей в 500 м, офисных объектов — {r['office_500m']}, узлов метро — {r['metro_hubs_500m']}, кафе OSM — {r['cafe_500m']}. Базовый балл {r['score_base']:.1f}; в топ-20 попадает в {r['scenario_top20_count']} из 5 сценариев.".replace(',',' '))
 (ROOT/'docs/top5_rationale.md').write_text('# Почему эти пять территорий\n\n'+'\n\n'.join(reasons)+'\n\nПроверить на месте: фактические конкуренты, выходы и переходы, видимость фасада, помещения и аренда. Ориентир относится к ближайшему жилому адресу и не означает, что в этом здании есть подходящее помещение.\n')
 (ROOT/'docs/post.md').write_text(f'''# Пять территорий для проверки кофейни на Преображенке и в Богородском

Взял {report['eligible_cells']} пригодных ячеек в двух районах и сравнил окружение каждой: жильё, офисы, транспорт и кафе. Получился шорт-лист из пяти территорий с расстоянием не меньше 600 м между центрами.

Первый кандидат — окрестности {top[0]['landmark']}. В радиусе 500 м по прямой модель насчитала примерно {round(top[0]['residents_500m']/100)*100:,} жителей, {top[0]['office_500m']} офисных объектов и {top[0]['cafe_500m']} кафе из OSM. Это отправная точка для обследования: нужного помещения по этому адресу может не быть.

Проверил, как меняется рейтинг при большем весе жителей, офисов и конкуренции. Такая проверка показывает, какие места держатся в разных сценариях, а какие зависят от выбранных весов.

Ограничение существенное: реального пассажиропотока и числа работников офисов в данных нет. Метро и офисы здесь — индикаторы, население домов — оценка. Отсутствующая на карте кофейня может существовать в действительности. Поэтому карта помогает выбрать места для проверки, но не предсказывает прибыль.

В локальном проекте — Python, QGIS, карта, таблица топ-5, формулы и все веса. Для публикации приложить `outputs/location_ranking.png`; ссылку на репозиторий добавить после отдельного решения о публикации.
'''.replace(',',' '))
 (ROOT/'docs/method.md').write_text('''# Проверяемые допущения

- Буфер 500 м евклидов: он может пересекать реку, пути и закрытые территории. Для пешеходного варианта нужен отдельный сетевой расчёт.
- Жители представлены внутренними точками зданий; население всего здания попадает в буфер по точке. На границе буфера это даёт скачок.
- Жители за границами двух районов исключены; в отличие от POI, внешний демографический запас отсутствует. Это явный краевой эффект.
- Один офисный POI не равен одному офисному зданию, сотруднику или квадратному метру. Нормирование не устраняет неполноту исходной карты.
- Входы метро объединяются транзитивными связными группами 250 м. Геометрический центр группы — приближение транспортного узла; станции с длинными цепочками входов требуют ручной проверки.
- Близкие POI схлопываются только при совпадении типа и координат ближе 2 м или одинакового непустого имени в пределах 35 м. Кафе и офисы без имени в разных точках не объединяются.
- Базовые веса заданы аналитиком. Баллы не калиброваны на чеках, обороте или аренде. Дополнительные сценарии сохраняют отдельные рейтинги, топ-5 выбирается только по базовому.
- Гексагоны обрезаны по границе, отбираются по центру. Остатки ячеек с центром снаружи исключаются; это не сплошное покрытие района.
- Проверки сохранения районного населения, целостности ключей, корректности геометрии и разделения топ-5 встроены в основной запуск.
''')

if __name__=='__main__':main()
