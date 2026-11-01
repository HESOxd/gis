"""Run with QGIS Python to build a portable, styled .qgz project."""
from pathlib import Path
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsFillSymbol,
    QgsLineSymbol, QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem, QgsRectangle, Qgis)
from qgis.PyQt.QtGui import QColor

ROOT=Path(__file__).resolve().parents[1]
app=QgsApplication([],False)
app.initQgis()
project=QgsProject.instance()
project.setFileName(str(ROOT/'moscow_walk_access.qgz'))
project.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
project.setTitle('Богородское и Преображенское — доступность школ и поликлиник (OSM, предварительно)')
project.setFilePathStorage(Qgis.FilePathType.Relative)
project.setBackgroundColor(QColor('#f8f6ef'))
gpkg=ROOT/'data/processed/accessibility.gpkg'
root=project.layerTreeRoot()


def layer(table,name,group=None,subset=None):
    result=QgsVectorLayer(str(gpkg)+'|layername='+table,name,'ogr')
    if not result.isValid():
        raise RuntimeError('Invalid layer: '+table)
    if subset: result.setSubsetString(subset)
    project.addMapLayer(result,False)
    (group or root).addLayer(result)
    return result


base=root.addGroup('Подложка OSM · © OpenStreetMap contributors / ODbL')
parks=layer('parks','Парки и лес',base)
parks.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'225,233,218,255','outline_style':'no'}))
water=layer('water','Вода',base)
water.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'187,220,227,255','outline_style':'no'}))
roads=layer('walk_network','Пешеходная сеть',base)
roads.renderer().setSymbol(QgsLineSymbol.createSimple({'line_color':'202,203,199,255','line_width':'0.15'}))
districts=layer('districts','Границы районов',base)
districts.renderer().setSymbol(QgsFillSymbol.createSimple({'style':'no','outline_color':'69,77,85,255','outline_style':'dash','outline_width':'0.4'}))
colors={'within_10':('#25866c','До 10 минут'),'within_15':('#e3b95c','10–15 минут'),
        'over_15':('#d95650','Более 15 минут'),'unknown':('#8c8c94','Нет надёжной привязки / маршрута')}
for kind,title in [('clinic','Поликлиники'),('school','Школы')]:
    group=root.insertGroup(0,title+' · предварительные данные OSM')
    homes=layer('homes','Доступность: жилые здания',group)
    categories=[]
    for value,(color,label) in colors.items():
        symbol=QgsFillSymbol.createSimple({'color':color,'outline_color':'255,255,255,180','outline_width':'0.1'})
        categories.append(QgsRendererCategory(value,symbol,label))
    homes.setRenderer(QgsCategorizedSymbolRenderer(kind+'_status',categories))
    homes.setDisplayExpression('coalesce("address", "id")')
    iso=layer('isochrones','15 минут · коридоры сети шириной 36 м',group,
              '"kind" = \''+kind+'\' AND "minutes" = 15')
    iso.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'138,199,176,50','outline_style':'no'}))
    facilities=layer('facilities',title+' OSM',group,'"kind" = \''+kind+'\'')
    facilities.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':'cross_fill' if kind=='clinic' else 'circle','color':'#233c54','outline_color':'white','size':'2.7'}))
    facilities.setDisplayExpression('"name"')
    group.setItemVisibilityChecked(kind=='school')
# Reverse drawing order within groups: points above homes, corridors beneath homes.
for group in root.findGroups():
    if group.name().startswith(('Школы','Поликлиники')):
        children=group.children()
        for child in list(children):
            clone=child.clone(); group.removeChildNode(child); group.insertChildNode(0,clone)
        # Current order facilities, isochrones, homes; swap homes and corridors.
        home_node=next(c for c in group.children() if c.name()=='Доступность: жилые здания')
        clone=home_node.clone(); group.removeChildNode(home_node); group.insertChildNode(1,clone)
project.viewSettings().setDefaultViewExtent(__import__('qgis.core',fromlist=['QgsReferencedRectangle']).QgsReferencedRectangle(QgsRectangle(districts.extent()),project.crs()))
project.setMetadata(project.metadata())
if not project.write(): raise RuntimeError('Cannot write project')
# Verify saved project and relative sources by reading it back.
project.clear()
assert project.read(str(ROOT/'moscow_walk_access.qgz'))
assert all(l.isValid() for l in project.mapLayers().values())
print('Saved and reopened project:',len(project.mapLayers()),'valid layers')
project.clear()
app.exitQgis()
