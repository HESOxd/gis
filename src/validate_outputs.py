"""Check exported facts, geometry and population conservation independently."""
import json
from pathlib import Path
import geopandas as gpd
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'data/processed/accessibility.gpkg'
report=json.loads((ROOT/'outputs/quality_report.json').read_text())
homes=gpd.read_file(path,layer='homes')
facilities=gpd.read_file(path,layer='facilities')
iso=gpd.read_file(path,layer='isochrones')
assert len(homes)==report['residential_buildings']
assert len(facilities)==report['facilities']
assert homes.geometry.is_valid.all() and iso.geometry.is_valid.all()
assert str(homes.crs)=='EPSG:32637'
for row in report['summary']:
 subset=homes[homes.district==row['district']]
 assert abs(subset.population_est.sum()-row['population'])<1e-5
 assert sum(row['homes_'+s] for s in ('within_10','within_15','over_15','unknown'))==len(subset)
 kind=row['kind']
 outside=subset[subset[kind+'_status']=='over_15']
 assert (outside[kind+'_min']>15).all()
 assert outside[kind+'_route_found'].all()
 assert len(outside)==row['homes_over_15']
 unknown=subset[subset[kind+'_status']=='unknown']
 assert ((unknown.snap_m>100)|(~unknown[kind+'_route_found'])).all()
for _,group in iso.groupby('facility_id'):
 if len(group)==2:
  ten=group[group.minutes==10].geometry.iloc[0]
  fifteen=group[group.minutes==15].geometry.iloc[0]
  assert ten.difference(fifteen.buffer(1.5)).area<1, '10 min not inside 15 min'
print('PASS: exported counts, classifications, population totals, CRS, valid geometries, nested isochrones')
