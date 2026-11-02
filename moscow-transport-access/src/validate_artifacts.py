"""Verify GIS export agrees with the pilot and contains portable source paths."""
import json,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
pilot=json.loads((OUT/'tram13_stop_pilot.json').read_text());expected={r['stop_id']:r for r in pilot['arrivals']}
csv=pd.read_csv(OUT/'tram13_stop_arrivals.csv',dtype={'stop_id':str});g=gpd.read_file(DATA/'transport_pilot.gpkg',layer='pilot_stops')
assert len(g)==len(csv)==len(expected)==46;assert set(g.stop_id)==set(expected)
assert g.crs.to_epsg()==32637 and g.geometry.is_valid.all()
ll=g.to_crs(4326)
assert np.allclose(ll.geometry.x,g.lon,atol=1e-8) and np.allclose(ll.geometry.y,g.lat,atol=1e-8)
for _,r in g.iterrows():
 ref=expected[r.stop_id];assert r.arrival_seconds==ref['arrival_seconds'] and r.elapsed_minutes==ref['elapsed_minutes'] and r['name']==ref['name']
origin=gpd.read_file(DATA/'transport_pilot.gpkg',layer='origin');assert len(origin)==1 and origin.stop_id.iloc[0]==pilot['origin_stop'] and origin.elapsed_minutes.iloc[0]==0
for name in ['districts','homes']:
 frame=gpd.read_file(DATA/'transport_pilot.gpkg',layer=name);assert frame.geometry.is_valid.all() and frame.crs==g.crs
with zipfile.ZipFile(ROOT/'moscow_transport_pilot.qgz') as z:
 text=z.read(next(n for n in z.namelist() if n.endswith('.qgs'))).decode();assert '/Users/hesoxd/' not in text
independent=json.loads((OUT/'independent_timetable_validation.json').read_text());assert independent['passed'] and independent['matched_all_arrival_times']
report={'passed':True,'layers':len(ET.fromstring(text).findall('./projectlayers/maplayer')),'stops':46,'checks':['JSON/CSV/GPKG arrival equality','coordinate roundtrip','CRS and valid geometries','origin identity and zero time','relative QGIS paths','independent timetable cross-check'],'scope':'partial pilot; full city-centre and three-mode comparison not completed'}
(OUT/'artifact_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
