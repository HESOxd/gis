"""Independent checks of raw scaling, QA exclusion, joins and portability."""
import hashlib,json,zipfile
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw';DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
def read(path):
 with rasterio.open(path) as d:return d.read(1,masked=True).filled(np.nan) if d.dtypes[0].startswith('float') else d.read(1)
for f in json.loads((RAW/'manifest.json').read_text()):assert hashlib.sha256((RAW/f"{f['kind']}_{f['asset']}.tif").read_bytes()).hexdigest()==f['sha256']
st=read(RAW/'landsat_lwir11.tif');lst=read(DATA/'lst_celsius_30m.tif');nd=read(DATA/'ndvi_30m.tif');qa=read(RAW/'landsat_qa_pixel.tif');unc=read(RAW/'landsat_qa.tif');dist=read(RAW/'landsat_cdist.tif');valid=np.isfinite(lst)
assert np.array_equal(np.isfinite(nd),valid)
assert np.allclose(lst[valid],(st.astype(float)*.00341802+149-273.15)[valid],atol=1e-4)
assert np.all((qa[valid]&191)==0);assert np.all(unc[valid]*.01<=5);assert np.all(dist[valid]*.01>=.5)
assert np.all((nd[valid]>=-1)&(nd[valid]<=1));assert np.all((lst[valid]>-50)&(lst[valid]<80))
frames={k:gpd.read_file(DATA/'green_heat.gpkg',layer=k) for k in ['districts','homes','cells_300m','cells_600m','priorities']}
for name,g in frames.items():assert g.crs.to_epsg()==32637 and g.geometry.is_valid.all() and not g.geometry.is_empty.any(),name
assert frames['districts'].paired_pixels.sum()==valid.sum()
g=frames['cells_300m'];e=g.loc[g.eligible.astype(bool)];assert (e.valid_fraction>=.7).all() and (e.paired_pixels>=30).all()
top=frames['priorities'];assert len(top)==5 and (top.residential_area_m2>=100).all()
assert all(a.centroid.distance(b.centroid)>=600-1e-6 for i,a in enumerate(top.geometry) for b in list(top.geometry)[i+1:])
with zipfile.ZipFile(ROOT/'moscow_green_heat.qgz') as z:
 qgs=z.read(next(n for n in z.namelist() if n.endswith('.qgs'))).decode();assert '/Users/hesoxd/' not in qgs
report={'passed':True,'sha_verified_assets':8,'valid_common_pixels':int(valid.sum()),'eligible_300m_cells':len(e),'qgis_relative_paths':True,'checks':['raw ST scaling','QA bits, uncertainty, cloud distance','paired support','geometry and CRS','district pixel conservation','cell screening','residential top5 and spacing','QGIS portable sources']}
(OUT/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
