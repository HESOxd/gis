"""Readable city maps of school/clinic walking access from existing analysis."""
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from map_style import ROOT,BG,INK,MUTED,context,canvas,base,finish_map,header,paragraph,card,footer,save
DATA=ROOT/'data/processed/accessibility.gpkg';OUT=ROOT/'outputs'
COLORS={'within_10':'#2d8b79','within_15':'#e5bd61','over_15':'#bc4f43','unknown':'#8b969a'}
def plural(n):return 'дом' if n%10==1 and n%100!=11 else 'дома' if n%10 in [2,3,4] and n%100 not in [12,13,14] else 'домов'
def short(value):
 return str(value).replace('Краснобогатырская улица','Краснобогатырская ул.').replace('улица','ул.').strip() or 'Без адреса в OSM'
def render():
 d=gpd.read_file(DATA,layer='districts');homes=gpd.read_file(DATA,layer='homes');facilities=gpd.read_file(DATA,layer='facilities');ctx=context()
 for kind,noun,title in [('school','школы','Дойти до школы: где дальше 15 минут'),('clinic','поликлиники','Дойти до поликлиники: где дальше 15 минут')]:
  fig,ax,panel=canvas(title,'Богородское и Преображенское · оценка по пешеходной сети OSM · скорость 5 км/ч')
  base(ax,d,ctx);d.plot(ax=ax,color='#f1f1e9',linewidth=0,zorder=-4)
  for status,color in COLORS.items():
   g=homes.loc[homes[kind+'_status']==status]
   if len(g):g.plot(ax=ax,color=color,edgecolor='white',linewidth=.2,zorder=5)
  fs=facilities.loc[(facilities.kind==kind)&facilities.intersects(d.union_all().buffer(100))]
  if len(fs):fs.plot(ax=ax,marker='^' if kind=='school' else 'P',markersize=20 if kind=='school' else 28,color='#294f64',edgecolor='white',linewidth=.45,zorder=7)
  finish_map(ax,d,ctx)
  outside=homes.loc[homes[kind+'_status']=='over_15'].sort_values(kind+'_min',ascending=False)
  selected=outside.copy();selected['label']=selected.address.fillna('').map(short);selected=selected.drop_duplicates('label').head(3)
  for number,(_,r) in enumerate(selected.iterrows(),1):
   p=r.geometry.representative_point()
   crowded=any(p.distance(other.geometry.representative_point())<250 for _,other in selected.iterrows() if other.id!=r.id)
   offset=[(21,15),(-21,12),(0,-23)][number-1] if crowded else (0,0)
   ax.scatter(p.x,p.y,s=35,color=COLORS['over_15'],edgecolor='white',linewidth=.7,zorder=23)
   ax.annotate(str(number),(p.x,p.y),xytext=offset,textcoords='offset points',ha='center',va='center',fontweight='bold',fontsize=9,color='white',zorder=24,bbox={'boxstyle':'circle,pad=.28','fc':COLORS['over_15'],'ec':'white','lw':1.2},arrowprops={'arrowstyle':'-','color':COLORS['over_15'],'lw':1} if crowded else None)
  header(panel,'Время от жилого дома',.98)
  handles=[]
  for s,label in [('within_10','До 10 минут'),('within_15','10–15 минут'),('over_15','Дольше 15 минут'),('unknown','Не удалось оценить')]:
   n=int((homes[kind+'_status']==s).sum());handles.append(Patch(facecolor=COLORS[s],label=f'{label} — {n} {plural(n)}'))
  handles.append(Line2D([0],[0],marker='^' if kind=='school' else 'P',color='#294f64',ls='',markerfacecolor='#294f64',label='Школа OSM' if kind=='school' else 'Поликлиника OSM'))
  panel.legend(handles=handles,loc='upper left',bbox_to_anchor=(-.02,.91),frameon=False,fontsize=10,labelspacing=1.1)
  n=len(outside);panel.text(0,.61,f'{n} {plural(n)}',fontsize=25,fontweight='bold',color=COLORS['over_15'],transform=panel.transAxes)
  paragraph(panel,f'От этих домов путь до ближайшей {noun} занимает больше 15 минут.',.555,size=10,width=43)
  for number,(_,r) in enumerate(selected.iterrows(),1):card(panel,number,r['label'],f'≈{r[kind+"_min"]:.0f} мин пешком по сети',.44-(number-1)*.135,color=COLORS['over_15'])
  paragraph(panel,'Номера — примеры для проверки. Красный цвет относится к дому, а не ко всей территории вокруг.',.04,width=47,size=8.5,color=MUTED)
  footer(fig,'Цвет показывает время от жилого дома. Красные дома стоит проверить в первую очередь; серые в дефицит не включены.\nПредварительный расчёт: учреждения OSM требуют сверки, прикрепление, вместимость и фактические проходы не проверены.',satellite=False)
  save(fig,OUT,kind+'_access')
 print('Rendered school and clinic city maps')
if __name__=='__main__':render()
