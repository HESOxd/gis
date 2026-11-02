"""City reference map and four explicit checkpoints of the limited real GTFS pilot."""
from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from map_style import ROOT,BG,INK,MUTED,context,canvas,base,finish_map,header,paragraph,card,footer,save
DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
stops=gpd.read_file(DATA/'transport_pilot.gpkg',layer='pilot_stops');d=gpd.read_file(DATA/'transport_pilot.gpkg',layer='districts');ctx=context()
fig,ax,panel=canvas('Трамвай 13: поездка от «Метрогородка»','Остановочный пилот · отправление 02.11.2026 в 08:00 МСК · расчёт по архиву июня')
base(ax,d,ctx);finish_map(ax,d,ctx,metro=True,street_names=False)
stops.plot(ax=ax,color='#9caaa9',markersize=20,edgecolor='white',linewidth=.6,zorder=10)
selected=[]
for term in ['Метрогородок','Бульвар Рокоссовского','Преображенская площадь','Каланчёвская']:
 selected.append(stops.loc[stops.name.str.contains(term,regex=False)].sort_values('elapsed_minutes').iloc[0])
for i,r in enumerate(selected,1):
 p=r.geometry;ax.scatter(p.x,p.y,s=220,color='#1f6b75',edgecolor='white',linewidth=1.8,zorder=22);ax.text(p.x,p.y,str(i),ha='center',va='center',fontsize=10,color='white',fontweight='bold',zorder=23)
xmin,ymin,xmax,ymax=stops.total_bounds;dx0,dy0,dx1,dy1=d.total_bounds;ax.set_xlim(min(xmin,dx0)-650,max(xmax,dx1)+500);ax.set_ylim(min(ymin,dy0)-500,max(ymax,dy1)+500)
header(panel,'Контрольные остановки',.98)
for i,r in enumerate(selected,1):
 name=['Метрогородок','Бульвар Рокоссовского','Преображенская площадь','Каланчёвская улица'][i-1]
 detail='Начальная остановка · 08:00' if i==1 else f"{r.elapsed_minutes:.0f} мин с начала расчёта · ожидание включено"
 card(panel,i,name,detail,.86-(i-1)*.15,color='#1f6b75')
paragraph(panel,'Серые точки — все 46 рассчитанных stop_id, включая начальный. Платформы учтены отдельно, пеших переходов между ними нет.',.21,width=44,size=9)
footer(fig,'Номера связывают остановки на карте со временем справа. Это расчёт по расписанию одного маршрута.\nАктуальность июньского архива на ноябрь и лицензия не подтверждены. Полная доступность центра не рассчитана.',satellite=False)
fig.text(.66,.13,'Расписание: Mobility Database mdb-3226 · локальный пилот',fontsize=8,color=MUTED)
save(fig,OUT,'tram13_stop_pilot_map');print('Rendered city-context pilot and checkpoint times')
