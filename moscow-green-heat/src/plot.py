"""Reader-facing city maps: local street context, metro and explicit interpretation."""
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.colors import Normalize
import rasterio
from rasterio.plot import plotting_extent
from map_style import (ROOT,BG,INK,MUTED,NODATA,HEAT,GREEN,context,canvas,base,finish_map,header,paragraph,card,footer,save)
DATA=ROOT/'data/processed';OUT=ROOT/'outputs';ctx=context();d=gpd.read_file(DATA/'green_heat.gpkg',layer='districts');cells=gpd.read_file(DATA/'green_heat.gpkg',layer='cells_300m');top=gpd.read_file(DATA/'green_heat.gpkg',layer='priorities')

def satellite(kind):
 heat=kind=='lst_celsius_30m'
 title='Где сильнее нагревается поверхность' if heat else 'Где в районах больше растительности'
 subtitle='Богородское и Преображенское · спутниковый снимок 25 июля 2025' if heat else 'Богородское и Преображенское · спутниковый снимок 26 июля 2025'
 fig,ax,panel=canvas(title,subtitle);base(ax,d,ctx)
 with rasterio.open(DATA/f'{kind}.tif') as ds:
  a=ds.read(1,masked=True);im=ax.imshow(a,extent=plotting_extent(ds),cmap=HEAT if heat else GREEN,vmin=22 if heat else 0,vmax=44 if heat else .9,interpolation='bilinear' if heat else 'nearest',interpolation_stage='rgba',zorder=0)
 finish_map(ax,d,ctx)
 header(panel,'Как читать карту',.98)
 paragraph(panel,'Цвет показывает температуру поверхности: крыш, дорог и растительности.' if heat else 'Зелёный цвет показывает выраженность растительности по спутниковому индексу NDVI.',.91)
 cax=fig.add_axes([.67,.66,.28,.025]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[24,30,36,42] if heat else [0,.3,.6,.9]);cb.ax.tick_params(labelsize=10,length=0,pad=5)
 panel.text(.035,.665,'прохладнее' if heat else 'мало растительности',fontsize=9,color=MUTED,transform=panel.transAxes)
 panel.text(.93,.665,'горячее · °C' if heat else 'много',ha='right',fontsize=9,color=MUTED,transform=panel.transAxes)
 panel.legend(handles=[Patch(facecolor=NODATA,edgecolor='#a7b1b4',label='Нет надёжной оценки'),plt.Line2D([0],[0],marker='s',color='#b74742',ls='',markerfacecolor=BG,label='Метро — ориентир на карте')],loc='upper left',bbox_to_anchor=(-.02,.62),frameon=False,fontsize=10,labelspacing=1.2)
 header(panel,'Что здесь видно',.45)
 paragraph(panel,'На выбранном снимке участки с меньшим количеством зелени обычно нагреваются сильнее.' if heat else 'Внутри одних и тех же районов растительность распределена неравномерно. Светлые участки стоит рассмотреть внимательнее.',.38)
 header(panel,'Границы вывода',.23)
 paragraph(panel,'Оценена 61% площади районов. Серое — исключённые данные, а не прохладные места. Температура поверхности отличается от температуры воздуха. Неопределённость LST около 3,4 °C.' if heat else 'Показан общий пригодный участок двух снимков — 61% площади. Серое не означает отсутствие зелени. Индекс не измеряет тень, качество парка или доступность зелёных зон.',.16,size=9,color=MUTED,width=47)
 footer(fig,'Улицы и метро помогают найти знакомое место. Цвет относится к поверхности на дату снимка.\nСглаживание — оформление карты; расчётная сетка 30 м и исходные значения сохранены.' if heat else 'Светлый цвет → менее выраженная растительность. Тёмно-зелёный → более выраженная.\nNDVI рассчитан по Sentinel-2; сравнение с температурой сделано по общим пригодным пикселям.')
 save(fig,OUT,'surface_temperature_map' if heat else 'ndvi_map')

def priorities():
 fig,ax,panel=canvas('Пять территорий для проверки озеленения','Богородское и Преображенское · предварительный отбор по снимкам 25–26 июля 2025')
 base(ax,d,ctx);eligible=cells.loc[cells.eligible.astype(bool)];eligible.plot(ax=ax,column='priority_score',cmap='YlOrRd',vmin=0,vmax=100,alpha=.72,edgecolor='white',linewidth=.25,zorder=0)
 top.boundary.plot(ax=ax,color='#9d3f33',linewidth=1.6,zorder=9);finish_map(ax,d,ctx)
 for _,r in top.iterrows():
  p=r.geometry.centroid;ax.scatter(p.x,p.y,s=210,color='#a44839',edgecolor='white',linewidth=1.6,zorder=22);ax.text(p.x,p.y,str(r['rank']),color='white',ha='center',va='center',fontweight='bold',fontsize=10,zorder=23)
 header(panel,'Сначала обследовать',.99)
 for i,(_,r) in enumerate(top.sort_values('rank').iterrows()):
  addr=r.nearest_home_address.replace('Электрозаводская улица','Электрозаводская ул.').replace('Краснобогатырская улица','Краснобогатырская ул.').replace('улица Девятая Рота','Девятая Рота,')
  card(panel,r['rank'],addr,f"Поверхность ≈{r.mean_lst_c:.0f} °C · мало зелени",.89-i*.135)
 paragraph(panel,'Краснее — выше относительный приоритет. Участок включён, если в ячейке есть жилые здания. Адреса — ориентиры, а не места посадки. Серое — без оценки.',.18,width=46,size=9)
 footer(fig,'Номера на карте соответствуют списку справа. Выбор учитывает жару, малое количество растительности и наличие жилья.\nПеред посадками нужны осмотр, проверка тени, коммуникаций и прав на землю. Это предварительный список.')
 save(fig,OUT,'greening_priorities_map')

def scatter():
 fig=plt.figure(figsize=(13,8),facecolor=BG);ax=fig.add_axes([.09,.25,.59,.52]);panel=fig.add_axes([.73,.24,.24,.55]);panel.set_axis_off()
 a=cells.loc[cells.eligible.astype(bool)]
 for district,c in [('Богородское','#2f8b76'),('Преображенское','#ca7850')]:
  b=a.loc[a.district==district];ax.scatter(b.mean_ndvi,b.mean_lst_c,s=45,alpha=.8,c=c,label=district,edgecolor='white',linewidth=.5)
 coef=np.polyfit(a.mean_ndvi,a.mean_lst_c,1);xx=np.array([a.mean_ndvi.min(),a.mean_ndvi.max()]);ax.plot(xx,np.polyval(coef,xx),color='#6f7b7e',ls='--',lw=1)
 ax.set_xlabel('Меньше растительности   ←   NDVI   →   Больше растительности',fontsize=10,labelpad=12);ax.set_ylabel('Температура поверхности, °C',labelpad=10);ax.grid(alpha=.13);ax.legend(frameon=False,fontsize=9);ax.spines[['top','right']].set_visible(False)
 fig.text(.06,.93,'Более зелёные участки обычно прохладнее',fontsize=22,fontweight='bold');fig.text(.06,.865,'Одна точка — одна территория размером около 300 × 300 м',fontsize=12,color=MUTED)
 header(panel,'Как читать точки',.98);paragraph(panel,'Правее — больше растительности. Ниже — прохладнее поверхность. Наклон линии показывает общую связь.',.87,width=29)
 header(panel,'Что получилось',.57);paragraph(panel,'96 пригодных ячеек.\nКорреляция r = −0,81.\nНа сетке 600 м направление связи сохраняется.',.46,width=29)
 paragraph(panel,'Это наблюдаемая связь одной пары снимков. Она не показывает, на сколько градусов охладит место будущая посадка.',.15,width=31,size=9,color=MUTED)
 fig.text(.09,.10,'Снимки 25–26.07.2025 · общая пригодная площадь 61% · неопределённость LST около 3,4 °C.\nСоседние ячейки зависимы; влияние застройки, покрытий и других факторов отдельно не оценивалось.',fontsize=9,color=MUTED,linespacing=1.6)
 save(fig,OUT,'ndvi_lst_scatter')
if __name__=='__main__':
 satellite('lst_celsius_30m');satellite('ndvi_30m');priorities();scatter();print('Rendered city maps and reader-facing chart')
