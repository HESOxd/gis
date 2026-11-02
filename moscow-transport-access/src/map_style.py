"""Reusable local map design: real OSM context, legible labels and a reading panel."""
from pathlib import Path
from shapely.geometry import Point
import math,textwrap
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch,Patch
from matplotlib.colors import LinearSegmentedColormap
ROOT=Path(__file__).resolve().parents[1]
BG='#fbfaf7';INK='#203d47';MUTED='#5d7178';NODATA='#dce1e2'
HEAT=LinearSegmentedColormap.from_list('surface_heat',['#447d96','#c0dce0','#fff1bd','#ee9b64','#b23c38'])
GREEN=LinearSegmentedColormap.from_list('vegetation',['#f4e8d2','#e1e9b0','#80b77f','#24634d'])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'figure.facecolor':BG,'text.color':INK,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED})
def context(root=ROOT):
 return {name:gpd.read_file(root/f'data/cartography/{name}.geojson') for name in ['streets','landmarks','metro']}
def canvas(title,subtitle):
 fig=plt.figure(figsize=(14,10),facecolor=BG);ax=fig.add_axes([.025,.13,.60,.73]);panel=fig.add_axes([.66,.14,.31,.72]);panel.set_axis_off()
 fig.text(.045,.955,title,fontsize=23,fontweight='bold',va='top');fig.text(.045,.908,subtitle,fontsize=11,color=MUTED)
 return fig,ax,panel
def base(ax,d,ctx):
 xmin,ymin,xmax,ymax=d.total_bounds;pad=450
 ax.set_xlim(xmin-pad,xmax+pad);ax.set_ylim(ymin-pad,ymax+pad);ax.set_aspect('equal');ax.set_axis_off();ax.set_facecolor(BG)
 land=ctx['landmarks'];land.loc[land.kind=='park'].plot(ax=ax,color='#e3eadb',linewidth=0,zorder=-8)
 land.loc[land.kind=='water'].plot(ax=ax,color='#c9e1eb',linewidth=0,zorder=-7)
 d.plot(ax=ax,color=NODATA,linewidth=0,zorder=-5)
 streets=ctx['streets'];major=streets.kind.isin(['primary','secondary','tertiary']);minor=streets.loc[~major]
 minor.plot(ax=ax,color='#b4bcbc',linewidth=.23,alpha=.55,zorder=2)
 streets.loc[major].plot(ax=ax,color=BG,linewidth=1.8,alpha=.9,zorder=3)
 streets.loc[major].plot(ax=ax,color='#879494',linewidth=.55,alpha=.85,zorder=4)
 return xmin,ymin,xmax,ymax
def finish_map(ax,d,ctx,metro=True,street_names=True):
 d.boundary.plot(ax=ax,color='#46646a',linewidth=1,zorder=8)
 occupied=[]
 for _,r in d.iterrows():
  p=r.geometry.representative_point()
  if r.district=='Преображенское' and r.geometry.covers(Point(p.x+150,p.y-800)):p=Point(p.x+150,p.y-800)
  occupied.append(p)
  ax.text(p.x,p.y,r.district.upper(),ha='center',fontsize=10,fontweight='bold',color=INK,zorder=12,path_effects=[pe.withStroke(linewidth=4,foreground=BG,alpha=.9)])
 xmin,ymin,xmax,ymax=d.total_bounds
 if metro:
  hubs=ctx['metro'];hubs=hubs.loc[hubs.name.isin(['Преображенская площадь','Бульвар Рокоссовского','Электрозаводская','Семёновская','Черкизовская'])]
  for _,r in hubs.iterrows():
   p=r.geometry
   if not (xmin-420<p.x<xmax+420 and ymin-420<p.y<ymax+420):continue
   occupied.append(p);ax.scatter(p.x,p.y,s=95,marker='s',facecolor=BG,edgecolor='#b74742',linewidth=1,zorder=15);ax.text(p.x,p.y,'М',ha='center',va='center',fontsize=7.5,fontweight='bold',color='#a23632',zorder=16)
   name=r['name'].replace('Преображенская площадь','Преображенская\nплощадь').replace('Бульвар Рокоссовского','Бульвар\nРокоссовского')
   side=-1 if r['name']=='Электрозаводская' else 1
   ax.annotate(name,(p.x,p.y),xytext=(side*10,-3),textcoords='offset points',ha='left' if side==1 else 'right',va='top',fontsize=8.5,color=INK,zorder=16,path_effects=[pe.withStroke(linewidth=3,foreground=BG)])
 if street_names:
  for name in ['Краснобогатырская улица','Большая Черкизовская улица','Открытое шоссе','Электрозаводская улица','улица Хромова']:
   s=ctx['streets'];parts=s.loc[s.name==name]
   if len(parts)==0:continue
   region=d.union_all().envelope.buffer(30)
   clipped=parts.geometry.intersection(region);lines=[g for g in clipped if g.geom_type=='LineString' and not g.is_empty]
   if not lines:continue
   line=max(lines,key=lambda g:g.length)
   if line.length<100:continue
   candidates=[line.interpolate(t,normalized=True) for t in [.25,.5,.75]]
   point=max(candidates,key=lambda p:min((p.distance(o) for o in occupied),default=9999));near=min((point.distance(o) for o in occupied),default=9999)
   if near<170:continue
   pos=line.project(point);a=line.interpolate(max(0,pos-40));b=line.interpolate(min(line.length,pos+40));angle=math.degrees(math.atan2(b.y-a.y,b.x-a.x));angle=(angle+90)%180-90
   label=name.replace('улица','ул.');ax.text(point.x,point.y,label,rotation=angle,rotation_mode='anchor',fontsize=7.5,ha='center',va='center',color='#465b60',zorder=10,path_effects=[pe.withStroke(linewidth=3,foreground=BG,alpha=.95)]);occupied.append(point)
 ax.plot([xmin+100,xmin+1100],[ymax+180,ymax+180],color=INK,lw=2.5,zorder=20);ax.text(xmin+600,ymax+290,'1 км',ha='center',fontsize=8,zorder=20)
 ax.annotate('С',(xmax+180,ymax-50),(xmax+180,ymax-550),ha='center',fontsize=9,arrowprops={'arrowstyle':'->','color':INK},zorder=20)
def header(panel,title,y):panel.text(0,y,title,fontsize=15,fontweight='bold',va='top',transform=panel.transAxes)
def paragraph(panel,text,y,width=43,size=10,color=INK):
 lines=[]
 for line in text.split('\n'):lines.extend(textwrap.wrap(line,width=width) or [''])
 panel.text(0,y,'\n'.join(lines),fontsize=size,color=color,va='top',linespacing=1.5,transform=panel.transAxes)
 return y-len(lines)*.026

def card(panel,number,title,detail,y,color='#bb5545'):
 panel.add_patch(FancyBboxPatch((0,y-.115),1,.115,boxstyle='round,pad=.012,rounding_size=.012',transform=panel.transAxes,facecolor='white',edgecolor='#dce3e1',linewidth=.8))
 panel.text(.035,y-.02,str(number),fontsize=15,fontweight='bold',color=color,va='top',transform=panel.transAxes)
 panel.text(.13,y-.018,title,fontsize=10,fontweight='bold',va='top',transform=panel.transAxes)
 panel.text(.13,y-.065,detail,fontsize=9,color=MUTED,va='top',transform=panel.transAxes,linespacing=1.4)

def footer(fig,text,satellite=True):
 fig.text(.045,.074,text,fontsize=9,color=MUTED,linespacing=1.5,va='top')
 credit='Ориентиры © OpenStreetMap contributors (ODbL)'
 if satellite:credit+=' · Contains modified Copernicus Sentinel data 2025 / USGS Landsat'
 fig.text(.045,.018,credit,fontsize=7,color=MUTED)
def save(fig,out,name):
 for ext in ['png','svg']:fig.savefig(out/f'{name}.{ext}',dpi=170,facecolor=BG)
 plt.close(fig)
