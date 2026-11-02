"""Package every city-style map under fresh paths and build one offline gallery."""
import base64,hashlib,html,json,shutil
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[2];OUT=P/'portfolio-maps';OUT.mkdir(exist_ok=True)
ITEMS=[
 ('01-school-city','Школы: где дольше 15 минут','Цвет дома — время до ближайшей школы по сети. Красные дома выделены для проверки.','moscow-walk-access','school_access','Карта'),
 ('02-clinic-city','Поликлиники: где дольше 15 минут','Те же правила чтения: зелёный — ближе, красный — дольше 15 минут, серый — нет оценки.','moscow-walk-access','clinic_access','Карта'),
 ('03-coffee-city','Где проверить место для кофейни','Пять номеров связаны с адресами справа. Спрос модельный; это список для обследования.','moscow-location-analysis','location_ranking','Карта'),
 ('04-location-stability','Устойчивость выбранных мест','Число в клетке — место в рейтинге при других весах. Меньше число — выше место.','moscow-location-analysis','top5_sensitivity','Диаграмма'),
 ('05-tram-city','Трамвай 13: остановочный пилот','Четыре контрольные остановки и времена по архивному расписанию. Полный кейс до центра не выполнен.','moscow-transport-access','tram13_stop_pilot_map','Карта'),
 ('06-heat-city','Где сильнее нагревается поверхность','Улицы и метро помогают ориентироваться. Серое — нет оценки; цвет показывает температуру поверхности.','moscow-green-heat','surface_temperature_map','Карта'),
 ('07-vegetation-city','Где больше растительности','Светлее — менее выраженная растительность, темнее — более выраженная. Серое — исключённые данные.','moscow-green-heat','ndvi_map','Карта'),
 ('08-greening-city','Где проверить возможность озеленения','Пять номеров, адреса-ориентиры и краткое основание отбора. Места посадок ещё не согласованы.','moscow-green-heat','greening_priorities_map','Карта'),
 ('09-green-heat-relation','Зелень и температура: как связаны','Одна точка — ячейка 300 м. Правее — больше зелени, ниже — прохладнее. Связь не доказывает эффект посадок.','moscow-green-heat','ndvi_lst_scatter','Диаграмма')]
blocks=[];inventory=[]
for slug,title,note,folder,name,kind in ITEMS:
 for ext in ['png','svg']:shutil.copyfile(P/f'{folder}/outputs/{name}.{ext}',OUT/f'{slug}.{ext}')
 content=(OUT/f'{slug}.png').read_bytes();uri='data:image/png;base64,'+base64.b64encode(content).decode()
 blocks.append(f'<section id="{slug}"><div class="eyebrow">{kind} · {slug[:2]}</div><h2>{html.escape(title)}</h2><p>{html.escape(note)}</p><a href="{slug}.png" title="Открыть крупно"><img loading="lazy" src="{uri}" alt="{html.escape(title)}"></a><div class="links"><a href="{slug}.png">Открыть PNG крупно</a><a href="{slug}.svg">Векторный SVG</a><a href="../{folder}/README.md">Данные и методика</a></div></section>')
 inventory.append({'id':slug,'title':title,'kind':kind,'source':f'{folder}/outputs/{name}.png','png_sha256':hashlib.sha256(content).hexdigest()})
nav=''.join(f'<a href="#{i[0]}">{i[0][:2]} · {html.escape(i[1])}</a>' for i in ITEMS)
doc='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Все карты портфолио · городское оформление</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#fbfaf7;color:#203d47;font:16px system-ui,sans-serif}main{max-width:1460px;margin:auto;padding:36px 24px}h1{font-size:clamp(30px,4vw,48px);line-height:1.1;max-width:1000px}p{line-height:1.6;max-width:1050px;color:#5d7178}nav{display:flex;gap:8px;flex-wrap:wrap;margin:28px 0}a{color:#236a70}nav a{padding:9px 13px;border:1px solid #d9e0dd;border-radius:9px;text-decoration:none;font-size:13px;background:white}section{margin:34px 0;padding:24px;background:white;border:1px solid #dce3e1;border-radius:18px;scroll-margin-top:20px}h2{font-size:27px;margin:12px 0}.eyebrow{font-size:12px;color:#687e83;letter-spacing:.06em}img{display:block;width:100%;height:auto;border:1px solid #eee;margin:18px 0}.links{display:flex;flex-wrap:wrap;gap:20px;font-size:14px}.intro{padding:18px 23px;border-left:4px solid #2d8b79;background:#edf3ec;border-radius:0 10px 10px 0}footer{font-size:13px;line-height:1.7;color:#5d7178;margin:34px 0}button{border:0;background:#203d47;color:white;padding:11px 15px;border-radius:8px;cursor:pointer}@media(max-width:700px){main{padding:22px 12px}section{padding:15px}h2{font-size:23px}}@media print{nav,button{display:none}section{break-before:page;border:0;padding:0}img{max-height:85vh;object-fit:contain}p{font-size:12px}}
</style><main><div class="eyebrow">ГИС-ПОРТФОЛИО · ОБНОВЛЕНО 02.11.2026</div><h1>Все карты — с улицами, метро и понятными пояснениями</h1><p class="intro"><strong>4 проекта · 7 карт · 2 диаграммы.</strong> Это локальная обновлённая версия. Все изображения встроены: галерея работает без интернета. Нажмите на карту, чтобы открыть её крупно.</p><p>Предварительные результаты и ограничения сохранены. Для проекта транспорта готов остановочный пилот; карта доступности центра на всех режимах пока не рассчитана.</p><nav>__NAV__</nav>__CONTENT__<footer><a href="../moscow-walk-access/outputs/interactive_map.html">Интерактивная карта школ и поликлиник</a> · <a href="../GIS-PORTFOLIO.md">Все файлы проектов, QGIS и архивы</a><br>Городские ориентиры © OpenStreetMap contributors (ODbL). Спутниковые данные: Copernicus Sentinel-2 / USGS Landsat. Условия и происхождение расписаний описаны в проекте 3. Новая версия не публиковалась на GitHub.</footer></main></html>'''
(OUT/'all-maps-city.html').write_text(doc.replace('__NAV__',nav).replace('__CONTENT__',''.join(blocks)))
(OUT/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
fig,axes=plt.subplots(2,2,figsize=(20,15),facecolor='#fbfaf7')
for ax,(slug,title) in zip(axes.flat,[('01-school-city','1 · Школы'),('03-coffee-city','2 · Кофейня'),('05-tram-city','3 · Транспортный пилот'),('08-greening-city','4 · Озеленение')]):
 ax.imshow(plt.imread(OUT/f'{slug}.png'));ax.set_axis_off();ax.set_title(title,fontfamily='DejaVu Sans',fontsize=16,color='#203d47',loc='left',pad=10)
fig.subplots_adjust(left=.02,right=.98,bottom=.02,top=.96,wspace=.04,hspace=.10);fig.savefig(OUT/'all-projects-overview.png',dpi=130,facecolor=fig.get_facecolor());plt.close(fig)
print('Built offline gallery:',len(inventory),'figures, 4-project overview')
if __name__=='__main__':pass
