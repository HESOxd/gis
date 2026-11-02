"""Add real local city context and legible labels without recomputing analysis."""
from pathlib import Path
from qgis.core import (QgsVectorLayer,QgsFillSymbol,QgsLineSymbol,QgsMarkerSymbol,QgsPalLayerSettings,QgsTextFormat,QgsTextBufferSettings,QgsVectorLayerSimpleLabeling,QgsRasterShader,QgsColorRampShader,QgsSingleBandPseudoColorRenderer,Qgis)
from qgis.PyQt.QtGui import QColor,QFont

def label(layer,field,size=8,line=False):
 s=QgsPalLayerSettings();s.fieldName=field;s.isExpression=True
 if line:s.placement=Qgis.LabelPlacement.Line
 fmt=QgsTextFormat();fmt.setFont(QFont('DejaVu Sans',size));fmt.setSize(size);fmt.setColor(QColor('#304d56'));buffer=QgsTextBufferSettings();buffer.setEnabled(True);buffer.setSize(.8);buffer.setColor(QColor('#fbfaf7'));fmt.setBuffer(buffer);s.setFormat(fmt);layer.setLabeling(QgsVectorLayerSimpleLabeling(s));layer.setLabelsEnabled(True)

def apply_context(p,root):
 root=Path(root);tree=p.layerTreeRoot();p.setBackgroundColor(QColor('#fbfaf7'))
 def add(name,title):
  path=str(root/f'data/cartography/{name}.geojson');existing=[l for l in p.mapLayers().values() if l.source().split('|')[0]==path and l.name()==title]
  if existing:
   for duplicate in existing[1:]:p.removeMapLayer(duplicate.id())
   return existing[0]
  layer=QgsVectorLayer(path,title,'ogr');assert layer.isValid(),name;p.addMapLayer(layer);return layer
 # Keep house classes consistent with the new school/clinic map legend.
 for layer in p.mapLayers().values():
  if '|layername=homes' not in layer.source():continue
  renderer=layer.renderer()
  if renderer and renderer.type()=='categorizedSymbol' and renderer.classAttribute() in ['school_status','clinic_status']:
   palette={'within_10':'#2d8b79','within_15':'#e5bd61','over_15':'#bc4f43','unknown':'#8b969a'}
   for i,category in enumerate(renderer.categories()):
    if category.value() in palette:
     symbol=category.symbol().clone();symbol.setColor(QColor(palette[category.value()]));renderer.updateCategorySymbol(i,symbol)
 # Outline's source also supplies an underlay so missing pixels are distinguishable.
 district=next((l for l in p.mapLayers().values() if '|layername=districts' in l.source()),None)
 if district and not any(l.name()=='Районы · фон без оценки' for l in p.mapLayers().values()):
  bg=QgsVectorLayer(district.source(),'Районы · фон без оценки','ogr');bg.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'#dce1e2','outline_style':'no'}));p.addMapLayer(bg,False);tree.addLayer(bg)
 streets=add('streets','Улицы · ориентиры');streets.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'#98a7aa','line_width':'.15'}));label(streets,'CASE WHEN "kind" IN (\'primary\',\'secondary\',\'tertiary\') THEN "name" END',7,True)
 metro=add('metro','Метро · ориентиры');metro.setSubsetString('"name" IS NOT NULL AND "name" <> \'\'');metro.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':'square','color':'#fbfaf7','outline_color':'#b74742','size':'2.6'}));label(metro,'"name"',8)
 if district:label(district,'"district"',10)
 for l in p.mapLayers().values():
  if not hasattr(l,'dataProvider'):continue
  basename=Path(l.source()).name
  if basename=='lst_celsius_30m.tif':
   stops=[(22,'#447d96'),(27.5,'#c0dce0'),(33,'#fff1bd'),(38.5,'#ee9b64'),(44,'#b23c38')];l.setName('Температура поверхности, °C · 25.07.2025')
  elif basename in ['ndvi_10m.tif','ndvi_30m.tif']:
   stops=[(0,'#f4e8d2'),(.3,'#e1e9b0'),(.6,'#80b77f'),(.9,'#24634d')]
  else:continue
  ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated);ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in stops]);shader=QgsRasterShader();shader.setRasterShaderFunction(ramp);l.setRenderer(QgsSingleBandPseudoColorRenderer(l.dataProvider(),1,shader))
 apply_layouts(p,root)
 return len(p.mapLayers())


def apply_layouts(p,root):
 """Expose every reader-facing figure as a named printable QGIS layout."""
 from qgis.core import QgsPrintLayout,QgsLayoutItemPicture,QgsLayoutPoint,QgsLayoutSize
 root=Path(root)
 sets={
 'moscow-walk-access':[('Школы · 15 минут пешком','school_access'),('Поликлиники · 15 минут пешком','clinic_access')],
 'moscow-location-analysis':[('Места для кофейни','location_ranking'),('Устойчивость выбора','top5_sensitivity')],
 'moscow-transport-access':[('Трамвай 13 · остановочный пилот','tram13_stop_pilot_map')],
 'moscow-green-heat':[('Температура поверхности','surface_temperature_map'),('Растительность','ndvi_map'),('Приоритеты озеленения','greening_priorities_map'),('Зелень и нагрев · связь','ndvi_lst_scatter')]}
 manager=p.layoutManager()
 for title,filename in sets.get(root.name,[]):
  name='Портфолио · '+title;old=manager.layoutByName(name)
  if old:manager.removeLayout(old)
  layout=QgsPrintLayout(p);layout.initializeDefaults();layout.setName(name)
  from qgis.PyQt.QtGui import QImageReader
  path=root/f'outputs/{filename}.png';assert path.exists(),path
  size=QImageReader(str(path)).size();assert size.width()>0
  height=250; width=height*size.width()/size.height()
  layout.pageCollection().page(0).setPageSize(QgsLayoutSize(width,height))
  picture=QgsLayoutItemPicture(layout);layout.addLayoutItem(picture);picture.attemptMove(QgsLayoutPoint(0,0));picture.attemptResize(QgsLayoutSize(width,height));picture.setPicturePath(str(path))
  manager.addLayout(layout)
