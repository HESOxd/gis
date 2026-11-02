"""City-facing location shortlist and readable scenario rank matrix."""
from pathlib import Path
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,Normalize,ListedColormap,BoundaryNorm
from matplotlib.lines import Line2D
from map_style import ROOT,BG,INK,MUTED,context,canvas,base,finish_map,header,paragraph,card,footer,save
DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
def short(address):
 return address.replace('Большая Черкизовская улица','Б. Черкизовская ул.').replace('улица Хромова','ул. Хромова').replace('3-я Гражданская улица','3-я Гражданская ул.').replace('4-я Гражданская улица','4-я Гражданская ул.')
def render():
 d=gpd.read_file(DATA/'location_analysis.gpkg',layer='districts');cells=gpd.read_file(DATA/'location_analysis.gpkg',layer='hexagons');top=gpd.read_file(DATA/'location_analysis.gpkg',layer='top5').sort_values('place');poi=gpd.read_file(DATA/'location_analysis.gpkg',layer='poi');ctx=context()
 fig,ax,panel=canvas('Где проверить место для кофейни','Богородское и Преображенское · пять территорий для обследования')
 base(ax,d,ctx);eligible=cells.loc[cells.eligible.astype(bool)];palette=LinearSegmentedColormap.from_list('location',['#edf2e5','#91c0ac','#227e79','#174d5a'])
 eligible.plot(ax=ax,column='score_base',cmap=palette,vmin=0,vmax=70,edgecolor='white',linewidth=.2,alpha=.9,zorder=0)
 cafes=poi.loc[poi.kind=='cafe'];cafes.plot(ax=ax,markersize=8,color='#ac754e',edgecolor=BG,linewidth=.3,alpha=.7,zorder=6)
 finish_map(ax,d,ctx)
 for _,r in top.iterrows():
  ax.scatter(r.cx,r.cy,s=210,color='#174f59',edgecolor='white',linewidth=1.5,zorder=22);ax.text(r.cx,r.cy,str(r.place),ha='center',va='center',color='white',fontsize=10,fontweight='bold',zorder=23)
 header(panel,'Пять мест для проверки',.99)
 for i,(_,r) in enumerate(top.iterrows()):
  people=round(r.residents_500m/1000)
  card(panel,r.place,short(r.landmark),f"≈{people} тыс. жителей* · {int(r.cafe_500m)} кафе в 500 м",.89-i*.135,color='#227e79')
 paragraph(panel,'Темнее — выше балл модели. Коричневые точки — существующие кафе OSM. Номер на карте соответствует адресу справа.',.18,width=45,size=9)
 footer(fig,'Адреса — ориентиры выбранных территорий, а не доступные помещения. Радиус 500 м измерен по прямой.\n*Жители оценены моделью. Пассажиропоток и аренда не измерялись; список не прогнозирует прибыль.',satellite=False)
 save(fig,OUT,'location_ranking')
 # Scenario matrix: names and numbers replace opaque cell IDs.
 scenarios=['base','residential','commuter','strong_competition','weak_competition'];matrix=np.array([[r['rank_'+s] for s in scenarios] for _,r in top.iterrows()])
 fig=plt.figure(figsize=(13,7.5),facecolor=BG);ax=fig.add_axes([.37,.22,.53,.51]);colours=ListedColormap(['#d9ece0','#f4e5bc','#e7c4bb']);norm=BoundaryNorm([0,20.5,40.5,1e6],3);ax.imshow(matrix,cmap=colours,norm=norm,aspect='auto')
 ax.set_yticks(range(5),[f'{r.place}. {short(r.landmark)}' for _,r in top.iterrows()],fontsize=10)
 ax.set_xticks(range(5),['Базовый\nрасчёт','Важнее\nжители','Важнее\nофисы и метро','Сильнее\nконкуренция','Слабее\nконкуренция'],fontsize=9);ax.tick_params(length=0,pad=9)
 for i in range(5):
  for j in range(5):ax.text(j,i,str(int(matrix[i,j])),ha='center',va='center',fontsize=15,fontweight='bold',color=INK)
 for x in np.arange(-.5,5,1):ax.axhline(x,color=BG,lw=4);ax.axvline(x,color=BG,lw=4)
 ax.spines[:].set_visible(False)
 fig.text(.06,.93,'Насколько устойчив выбранный список',fontsize=22,fontweight='bold');fig.text(.06,.855,'Число в клетке — место территории в рейтинге при другом наборе весов',fontsize=11,color=MUTED)
 fig.text(.10,.11,'Зелёный — место в топ-20. Чем меньше число, тем выше территория в рейтинге.\nПять адресов отобраны с разносом не менее 600 м; это не обязательно первые пять строк общего рейтинга.',fontsize=10,color=MUTED,linespacing=1.6)
 save(fig,OUT,'top5_sensitivity');print('Rendered location city map and scenario matrix')
if __name__=='__main__':render()
