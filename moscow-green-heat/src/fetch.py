"""Fetch only AOI windows from public COGs; retain unsigned URLs and hashes."""
import json,hashlib,shutil
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds,Window
import planetary_computer
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw';RAW.mkdir(exist_ok=True,parents=True)
for name in ['districts','homes']:
 target=RAW/f'{name}.geojson'
 if not target.exists():shutil.copyfile(ROOT.parent/f'moscow-walk-access/data/processed/{name}.geojson',target)
bbox=gpd.read_file(RAW/'districts.geojson').total_bounds
chosen={'landsat':'LC09_L2SP_178021_20250725_02_T1','sentinel':'S2A_37UDB_20250726_0_L2A'}
assets={'landsat':['lwir11','qa_pixel','qa_radsat','qa','cdist'],'sentinel':['red','nir','scl']}
manifest=[]
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_MAX_RETRY='1'):
 for kind,scene in chosen.items():
  item=next(f for f in json.loads((RAW/f'{kind}_search.json').read_text())['features'] if f['id']==scene)
  (RAW/f'{kind}_item.json').write_text(json.dumps(item,ensure_ascii=False,indent=2))
  for key in assets[kind]:
   asset=item['assets'][key];url=asset['href'];target=RAW/f'{kind}_{key}.tif'
   if not target.exists():
    access=planetary_computer.sign(url) if kind=='landsat' else url
    with rasterio.open(access) as ds:
     bounds=transform_bounds('EPSG:4326',ds.crs,*bbox,densify_pts=21)
     # Outward rounding keeps every pixel touching the AOI bounding box.
     w=from_bounds(*bounds,ds.transform);c0=int(w.col_off)//1;r0=int(w.row_off)//1
     import math
     win=Window(c0,r0,math.ceil(w.col_off+w.width)-c0,math.ceil(w.row_off+w.height)-r0).intersection(Window(0,0,ds.width,ds.height))
     a=ds.read(1,window=win);profile=ds.profile.copy();profile.update(driver='GTiff',height=a.shape[0],width=a.shape[1],transform=ds.window_transform(win),compress='deflate',tiled=False)
     for k in ['blockxsize','blockysize']:profile.pop(k,None)
     with rasterio.open(target,'w',**profile) as out:out.write(a,1)
   with rasterio.open(target) as ds:
    record={'scene':scene,'kind':kind,'asset':key,'url':url,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'crs':str(ds.crs),'shape':[ds.height,ds.width],'transform':list(ds.transform)[:6],'raster_metadata':asset.get('raster:bands')}
   manifest.append(record);print(kind,key,record['shape'],record['bytes'],flush=True)
(RAW/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
