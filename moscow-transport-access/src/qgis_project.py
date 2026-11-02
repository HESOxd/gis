"""Save/reopen portable point-only QGIS project for the limited GTFS pilot."""
from pathlib import Path
from qgis.core import (QgsApplication,QgsProject,QgsVectorLayer,QgsCoordinateReferenceSystem,Qgis,QgsReferencedRectangle,QgsFillSymbol,QgsMarkerSymbol,QgsGraduatedSymbolRenderer,QgsRendererRange)
from qgis.PyQt.QtGui import QColor
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/processed'
app=QgsApplication([],False);app.initQgis();p=QgsProject.instance();p.setFileName(str(ROOT/'moscow_transport_pilot.qgz'));p.setTitle('Трамвай13 · остановочный пилот · НЕ доступность центра');p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'));p.setFilePathStorage(Qgis.FilePathType.Relative);p.setBackgroundColor(QColor('#f7f5ef'))
def add(name,title,visible=True):
 l=QgsVectorLayer(str(DATA/'transport_pilot.gpkg')+'|layername='+name,title,'ogr');assert l.isValid();p.addMapLayer(l);p.layerTreeRoot().findLayer(l.id()).setItemVisibilityChecked(visible);return l
homes=add('homes','Жилые здания OSM · справочный слой',False);homes.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'#dadfd9','outline_style':'no'}))
d=add('districts','Богородское и Преображенское');d.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'#e0e7df','outline_color':'#778d86','outline_width':'.3'}))
stops=add('pilot_stops','Время с08:00 · маршрут13 · июньский архив')
ranges=[]
for lo,hi,c in [(0,15,'#fde725'),(15,30,'#5ec962'),(30,45,'#21918c'),(45,60,'#3b528b'),(60,90,'#440154')]:ranges.append(QgsRendererRange(lo,hi,QgsMarkerSymbol.createSimple({'color':c,'outline_color':'white','size':'2.5'}),f'{lo}–{hi} мин'))
stops.setRenderer(QgsGraduatedSymbolRenderer('elapsed_minutes',ranges))
o=add('origin','Исходная остановка · Метрогородок · 08:00МСК');o.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':'star','color':'#d05736','outline_color':'white','size':'5'}))
from qgis_context import apply_context
apply_context(p,ROOT)
p.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(stops.extent(),p.crs()));assert p.write();p.clear();assert p.read(str(ROOT/'moscow_transport_pilot.qgz'));assert all(l.isValid() for l in p.mapLayers().values());print('PASS saved/reopened',len(p.mapLayers()),'layers');p.clear();app.exitQgis()
