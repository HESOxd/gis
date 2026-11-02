"""Create and reopen a portable QGIS project (QGIS bundled Python)."""
from pathlib import Path
from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsCoordinateReferenceSystem,Qgis,QgsReferencedRectangle,QgsRasterShader,QgsColorRampShader,QgsSingleBandPseudoColorRenderer,QgsFillSymbol,QgsGraduatedSymbolRenderer,QgsRendererRange,QgsBilinearRasterResampler)
from qgis.PyQt.QtGui import QColor
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/processed'
app=QgsApplication([],False);app.initQgis();p=QgsProject.instance();p.setFileName(str(ROOT/'moscow_green_heat.qgz'));p.setTitle('Зелень и температура поверхности · 25–26.07.2025 · предварительный анализ');p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'));p.setFilePathStorage(Qgis.FilePathType.Relative);p.setBackgroundColor(QColor('#d9ddda'))
def raster(name,title,stops,visible):
 l=QgsRasterLayer(str(DATA/f'{name}.tif'),title);assert l.isValid(),name
 ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated);ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v,QColor(c),str(v)) for v,c in stops]);shader=QgsRasterShader();shader.setRasterShaderFunction(ramp);l.setRenderer(QgsSingleBandPseudoColorRenderer(l.dataProvider(),1,shader))
 if name=='lst_celsius_30m':
  l.resampleFilter().setZoomedInResampler(QgsBilinearRasterResampler());l.resampleFilter().setZoomedOutResampler(QgsBilinearRasterResampler())
 p.addMapLayer(l);p.layerTreeRoot().findLayer(l.id()).setItemVisibilityChecked(visible);return l
raster('ndvi_10m','NDVI · 10 м · Sentinel-2 26.07.2025',[(0,'#ffffcc'),(.5,'#78c679'),(.9,'#006837')],False)
raster('ndvi_30m','NDVI · общий пригодный участок · 30 м',[(0,'#ffffcc'),(.5,'#78c679'),(.9,'#006837')],False)
raster('lst_uncertainty_kelvin','Неопределённость LST · K',[(2,'#ffffcc'),(4,'#fd8d3c'),(6,'#800026')],False)
raster('s2_land_support','Доля ясной суши Sentinel в пикселе Landsat',[(0,'#d9ddda'),(1,'#156b46')],False)
raster('lst_celsius_30m','LST · °C · 25.07.2025 · общий пригодный участок',[(22,'#190b34'),(30,'#a52c60'),(37,'#ed6925'),(44,'#fcffa4')],True)
def vector(name,title,visible=False):
 l=QgsVectorLayer(str(DATA/'green_heat.gpkg')+'|layername='+name,title,'ogr');assert l.isValid(),name;p.addMapLayer(l);p.layerTreeRoot().findLayer(l.id()).setItemVisibilityChecked(visible);return l
homes=vector('homes','Жилые здания OSM');homes.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'#ddd9cc','outline_style':'no'}))
coarse=vector('cells_600m','Сетка 600 м · проверка масштаба');coarse.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#8d999d'}))
cells=vector('cells_300m','Приоритет обследования · пригодные ячейки 300 м');cells.setSubsetString('"eligible" = 1')
ranges=[]
for lo,hi,c in [(0,25,'#ffffb2'),(25,50,'#fecc5c'),(50,75,'#fd8d3c'),(75,100,'#bd0026')]:ranges.append(QgsRendererRange(lo,hi,QgsFillSymbol.createSimple({'color':c,'outline_color':'white','outline_width':'.1'}),f'{lo}–{hi}'))
cells.setRenderer(QgsGraduatedSymbolRenderer('priority_score',ranges))
top=vector('priorities','Топ-5 ячеек с жильём · нужен осмотр');top.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#1a3d45','outline_width':'.8'}))
d=vector('districts','Районы · статистика только пригодной площади',True);d.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'#243d45','outline_width':'.5'}))
from qgis_context import apply_context
apply_context(p,ROOT)
p.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(d.extent(),p.crs()));assert p.write();p.clear();assert p.read(str(ROOT/'moscow_green_heat.qgz'));assert all(l.isValid() for l in p.mapLayers().values());print('PASS saved/reopened',len(p.mapLayers()),'valid layers');p.clear();app.exitQgis()
