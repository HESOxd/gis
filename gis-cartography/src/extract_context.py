"""Extract real labelled street/park/water context from the frozen local OSM XML."""
import contextlib,hashlib,io,json,sys
from pathlib import Path
import geopandas as gpd
from shapely.geometry import LineString,Polygon
ROOT=Path(__file__).resolve().parents[1];PROJECTS=ROOT.parent
sys.path.insert(0,str(PROJECTS/'moscow-walk-access/src'))
from analyze import parse_osm
with contextlib.redirect_stdout(io.StringIO()):nodes,ways,_=parse_osm()
districts=gpd.read_file(PROJECTS/'moscow-green-heat/data/raw/districts.geojson').to_crs(32637);extent=districts.union_all().buffer(1200)
pilot=PROJECTS/'moscow-transport-access/data/processed/pilot_stops.geojson'
if pilot.exists():extent=extent.union(gpd.read_file(pilot).to_crs(32637).union_all().buffer(700))
roads=[];land=[]
for ident,(refs,tags) in ways.items():
 if len(refs)<2 or not all(n in nodes for n in refs):continue
 coords=[nodes[n][:2] for n in refs]
 highway=tags.get('highway')
 if highway in {'primary','secondary','tertiary','residential','unclassified','living_street','primary_link','secondary_link','tertiary_link'}:
  roads.append({'osm_id':str(ident),'name':tags.get('name',''),'kind':highway,'geometry':LineString(coords)})
 if len(refs)>=4 and refs[0]==refs[-1] and (tags.get('leisure') in {'park','garden'} or tags.get('natural')=='water' or tags.get('waterway')=='riverbank'):
  geom=Polygon(coords)
  if geom.is_valid:land.append({'osm_id':str(ident),'name':tags.get('name',''),'kind':'water' if tags.get('natural')=='water' or tags.get('waterway')=='riverbank' else 'park','geometry':geom})
manifest={'source':'OpenStreetMap snapshot 2026-11-01; reused project1 XML','attribution':'© OpenStreetMap contributors, ODbL','context_only':True,'files':{}}
for name,rows in [('streets',roads),('landmarks',land)]:
 g=gpd.GeoDataFrame(rows,geometry='geometry',crs=4326).to_crs(32637);g=g.loc[g.intersects(extent)].copy();g.geometry=g.geometry.intersection(extent);path=ROOT/f'data/{name}.geojson';g.to_file(path,driver='GeoJSON');manifest['files'][name]={'features':len(g),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()};print(name,len(g))
hubs=gpd.read_file(PROJECTS/'moscow-location-analysis/data/processed/metro_hubs.geojson').to_crs(32637);hubs=hubs.loc[hubs.intersects(extent)];path=ROOT/'data/metro.geojson';hubs.to_file(path,driver='GeoJSON');manifest['files']['metro']={'features':len(hubs),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(ROOT/'data/context_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('Context ready; calculations untouched')
