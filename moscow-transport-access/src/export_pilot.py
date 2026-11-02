"""Join real pilot arrivals to source stop coordinates; export point layers only."""
import csv,hashlib,io,json,shutil,zipfile
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw';DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
def main():
 pilot=json.loads((OUT/'tram13_stop_pilot.json').read_text());audit=json.loads((OUT/'feed_audit.json').read_text());source=RAW/'moscow_gtfs_20260630.zip'
 assert hashlib.sha256(source.read_bytes()).hexdigest()==audit['sha256']
 with zipfile.ZipFile(source) as z:
  stops={r['stop_id']:r for r in csv.DictReader(io.TextIOWrapper(z.open('stops.txt'),encoding='utf-8-sig',newline=''))}
 rows=[]
 for arrival in pilot['arrivals']:
  src=stops[arrival['stop_id']];assert src['stop_name']==arrival['name']
  rows.append({**arrival,'lon':float(src['stop_lon']),'lat':float(src['stop_lat']),'is_origin':arrival['stop_id']==pilot['origin_stop'],'service_date':pilot['service_date'],'departure':pilot['departure'],'route_id':'422','route_short_name':'13','scope':'selected-route stop-to-stop; not city accessibility'})
 frame=pd.DataFrame(rows);assert len(frame)==46 and frame.stop_id.nunique()==46
 assert frame.elapsed_minutes.ge(0).all() and frame.loc[frame.is_origin,'elapsed_minutes'].iloc[0]==0
 frame.to_csv(OUT/'tram13_stop_arrivals.csv',index=False)
 subset=frame[['stop_id','name','lon','lat']].rename(columns={'name':'stop_name','lon':'stop_lon','lat':'stop_lat'});subset.to_csv(RAW/'pilot_stops_source.csv',index=False)
 g=gpd.GeoDataFrame(frame,geometry=[Point(x,y) for x,y in zip(frame.lon,frame.lat)],crs=4326).to_crs(32637)
 for name in ['districts','homes']:
  target=RAW/f'{name}.geojson'
  if not target.exists():shutil.copyfile(ROOT.parent/f'moscow-walk-access/data/processed/{name}.geojson',target)
 districts=gpd.read_file(RAW/'districts.geojson').to_crs(g.crs);homes=gpd.read_file(RAW/'homes.geojson').to_crs(g.crs)
 layers={'pilot_stops':g,'origin':g.loc[g.is_origin].copy(),'districts':districts,'homes':homes}
 for name,data in layers.items():
  assert data.geometry.is_valid.all() and not data.geometry.is_empty.any()
  data.to_file(DATA/'transport_pilot.gpkg',layer=name,driver='GPKG',dataset_options={'VERSION':'1.3'});data.to_file(DATA/f'{name}.geojson',driver='GeoJSON')
 report={'source_url':audit['archive_url'],'source_sha256':audit['sha256'],'matched_stops':len(g),'minimum_elapsed_min':float(g.elapsed_minutes.min()),'maximum_elapsed_min':float(g.elapsed_minutes.max()),'geometry':'source GTFS stop points only; no fabricated route lines','source_freshness':'unverified June archive used for November service date','license':'unconfirmed; local review only'}
 (OUT/'pilot_export_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
