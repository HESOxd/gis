"""Build and reopen a relative-path QGIS project using QGIS Python."""
from pathlib import Path
from qgis.core import (QgsApplication,QgsProject,QgsVectorLayer,QgsFillSymbol,QgsLineSymbol,
 QgsMarkerSymbol,QgsGraduatedSymbolRenderer,QgsRendererRange,QgsCoordinateReferenceSystem,
 QgsReferencedRectangle,Qgis,QgsPalLayerSettings,QgsVectorLayerSimpleLabeling,QgsTextFormat)
from qgis.PyQt.QtGui import QColor,QFont
ROOT=Path(__file__).resolve().parents[1]
app=QgsApplication([],False);app.initQgis()
p=QgsProject.instance();p.setFileName(str(ROOT/'moscow_location_analysis.qgz'))
p.setTitle('Локации кофейни · Богородское и Преображенское · предварительная модель')
p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'));p.setFilePathStorage(Qgis.FilePathType.Relative)
p.setBackgroundColor(QColor('#f5f4ee'))
gpkg=ROOT/'data/processed/location_analysis.gpkg'

def add(name,title):
 l=QgsVectorLayer(str(gpkg)+'|layername='+name,title,'ogr');assert l.isValid(),name;p.addMapLayer(l);return l

roads=add('walk_network','Сеть проходов OSM')
roads.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'#c9ceca','line_width':'.12'}))
homes=add('homes','Жильё · население смоделировано')
homes.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'#dadfd9','outline_style':'no'}))
hexes=add('hexagons','Рейтинг ячеек · пригодные кандидаты');hexes.setSubsetString('"eligible" = 1')
ranges=[]
for low,high,color,label in [(-30,20,'#edf8b1','До 20'),(20,40,'#a1dab4','20–40'),(40,60,'#41b6c4','40–60'),(60,80,'#2c7fb8','60–80'),(80,100,'#253494','80–100')]:
 symbol=QgsFillSymbol.createSimple({'color':color,'outline_color':'white','outline_width':'.15'})
 ranges.append(QgsRendererRange(low,high,symbol,label))
hexes.setRenderer(QgsGraduatedSymbolRenderer('score_base',ranges))
buffers=add('top5_buffers','Зоны 500 м по прямой · топ-5')
buffers.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#607d8b','outline_style':'dash','outline_width':'.3'}))
districts=add('districts','Границы районов')
districts.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#374e59','outline_width':'.4'}))
poi=add('poi','Кафе OSM · конкуренты');poi.setSubsetString('"kind" = \'cafe\'')
poi.renderer().setSymbol(QgsMarkerSymbol.createSimple({'color':'#cc7545','outline_style':'no','size':'1.5'}))
hubs=add('metro_hubs','Группы входов метро · без пассажиропотока')
hubs.renderer().setSymbol(QgsMarkerSymbol.createSimple({'color':'#385b72','name':'diamond','size':'2.5'}))
top=add('top5','Топ-5 территорий · не помещения')
top.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#d05b40','outline_width':'1'}))
settings=QgsPalLayerSettings();settings.fieldName='place';format=QgsTextFormat();format.setFont(QFont('Arial',12));format.setColor(QColor('#17364d'));settings.setFormat(format)
top.setLabeling(QgsVectorLayerSimpleLabeling(settings));top.setLabelsEnabled(True)
from qgis_context import apply_context
apply_context(p,ROOT)
p.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(homes.extent(),p.crs()))
assert p.write();p.clear();assert p.read(str(ROOT/'moscow_location_analysis.qgz'));assert all(l.isValid() for l in p.mapLayers().values())
print('PASS: saved and reopened',len(p.mapLayers()),'layers');p.clear();app.exitQgis()
