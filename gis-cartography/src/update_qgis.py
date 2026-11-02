"""Add context to existing QGIS projects, preserving their analytical data/layers."""
import sys,zipfile,json
from pathlib import Path
from qgis.core import QgsApplication,QgsProject
PROJECTS=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECTS/'moscow-green-heat/src'))
from qgis_context import apply_context
app=QgsApplication([],False);app.initQgis();p=QgsProject.instance();report={}
for folder,name in [('moscow-walk-access','moscow_walk_access.qgz'),('moscow-green-heat','moscow_green_heat.qgz'),('moscow-location-analysis','moscow_location_analysis.qgz'),('moscow-transport-access','moscow_transport_pilot.qgz')]:
 root=PROJECTS/folder;path=root/name;p.clear();assert p.read(str(path)),name
 count=apply_context(p,root);assert p.write();p.clear();assert p.read(str(path));assert all(l.isValid() for l in p.mapLayers().values())
 with zipfile.ZipFile(path) as z:
  qgs=z.read(next(n for n in z.namelist() if n.endswith('.qgs'))).decode();assert '/Users/hesoxd/' not in qgs
 layouts=p.layoutManager().layouts()
 for layout in layouts:
  for item in layout.items():
   if hasattr(item,'picturePath'):
    value=item.picturePath();resolved=p.pathResolver().readPath(value);assert Path(resolved).exists(),resolved
 report[folder]={'valid_layers':count,'reopened':True,'relative_paths':True,'reader_layouts':[l.name() for l in layouts if l.name().startswith('Портфолио · ')]};print('PASS',folder,count,'valid layers, relative paths',flush=True)
(PROJECTS/'gis-cartography/qgis_validation.json').write_text(json.dumps(report,indent=2));p.clear();app.exitQgis()
