"""Aggregate paired NDVI/LST to clipped metric grids; report descriptive association."""
import json,math
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import box
from scipy.stats import spearmanr,pearsonr
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw';DATA=ROOT/'data/processed';OUT=ROOT/'outputs'
CRS='EPSG:32637'
def load(name):
 with rasterio.open(DATA/f'{name}.tif') as d:return d.read(1,masked=True).filled(np.nan),d.transform
ndvi,transform=load('ndvi_30m');lst,_=load('lst_celsius_30m');unc,_=load('lst_uncertainty_kelvin')
districts=gpd.read_file(RAW/'districts.geojson').to_crs(CRS);homes=gpd.read_file(RAW/'homes.geojson').to_crs(CRS);area=districts.union_all()
print('district fields',list(districts.columns),'home fields',list(homes.columns),flush=True)
def summarize(geom):
 inside=geometry_mask([geom],out_shape=lst.shape,transform=transform,invert=True)
 paired=inside&np.isfinite(ndvi)&np.isfinite(lst);n=int(paired.sum());total=int(inside.sum())
 return {'total_pixels':total,'paired_pixels':n,'valid_fraction':n/total if total else 0,'mean_ndvi':float(np.nanmean(ndvi[paired])) if n else None,'mean_lst_c':float(np.nanmean(lst[paired])) if n else None,'mean_uncertainty_k':float(np.nanmean(unc[paired])) if n else None}
def grid(size):
 xmin,ymin,xmax,ymax=area.bounds;rows=[]
 for x in range(math.floor(xmin/size)*size,math.ceil(xmax/size)*size,size):
  for y in range(math.floor(ymin/size)*size,math.ceil(ymax/size)*size,size):
   g=box(x,y,x+size,y+size).intersection(area)
   if g.area<size*size*.5:continue
   stats=summarize(g);centroid=g.centroid
   rows.append({'cell_id':f'{size}_{x}_{y}','area_m2':g.area,'district':districts.loc[districts.intersects(centroid),'district'].iloc[0] if districts.intersects(centroid).any() else 'граница','eligible':stats['valid_fraction']>=.7 and stats['paired_pixels']>=30,**stats,'geometry':g})
 return gpd.GeoDataFrame(rows,geometry='geometry',crs=CRS)
def association(g):
 a=g.loc[g.eligible,['mean_ndvi','mean_lst_c']].dropna()
 if len(a)<3:return {'cells':len(a),'warning':'too few cells'}
 return {'cells':len(a),'pearson_r':float(pearsonr(a.mean_ndvi,a.mean_lst_c).statistic),'spearman_rho':float(spearmanr(a.mean_ndvi,a.mean_lst_c).statistic),'note':'Descriptive only: spatially dependent cells, one scene pair; no causal or independent-sample significance claim.'}
def export(g,name):
 g.to_file(DATA/'green_heat.gpkg',layer=name,driver='GPKG',dataset_options={'VERSION':'1.3'})
 g.to_file(DATA/f'{name}.geojson',driver='GeoJSON');g.drop(columns='geometry').to_csv(OUT/f'{name}.csv',index=False)
def main():
 d=districts.copy()
 for k in ['total_pixels','paired_pixels','valid_fraction','mean_ndvi','mean_lst_c','mean_uncertainty_k']:d[k]=[summarize(g)[k] for g in d.geometry]
 g=grid(300);coarse=grid(600)
 eligible=g.loc[g.eligible].copy();g['priority_score']=np.nan;g['residential_area_m2']=0.
 for i,row in eligible.iterrows():g.loc[i,'residential_area_m2']=sum(homes.loc[homes.intersects(row.geometry)].intersection(row.geometry).area)
 scores=50*(eligible.mean_lst_c.rank(pct=True)+eligible.mean_ndvi.rank(pct=True,ascending=False));g.loc[eligible.index,'priority_score']=scores
 eligible=g.loc[g.eligible];hot=eligible.mean_lst_c.quantile(.75);low=eligible.mean_ndvi.quantile(.25)
 g['hot_low_green']=g.eligible&(g.mean_lst_c>=hot)&(g.mean_ndvi<=low)
 candidates=g.loc[g.eligible&(g.residential_area_m2>=100)].sort_values('priority_score',ascending=False);selected=[]
 for i,row in candidates.iterrows():
  if all(row.geometry.centroid.distance(g.loc[j].geometry.centroid)>=600 for j in selected):selected.append(i)
  if len(selected)==5:break
 top=g.loc[selected].copy();top['rank']=range(1,len(top)+1)
 top['nearest_home_address']=[str(homes.loc[homes.distance(geom.centroid).idxmin(),'address']) for geom in top.geometry]
 for frame,name in [(d,'districts'),(homes,'homes'),(g,'cells_300m'),(coarse,'cells_600m'),(top,'priorities')]:export(frame,name)
 report={'grid_300m':association(g),'grid_600m':association(coarse),'main_cloud_distance_km':.5,'main_max_uncertainty_k':5,'min_cell_valid_fraction':.7,'min_cell_pixels':30,'priority_thresholds':{'lst_upper_quartile_c':float(hot),'ndvi_lower_quartile':float(low)},'hot_low_green_cells':int(g.hot_low_green.sum()),'residential_candidates':len(candidates),'priority_cells':len(top),'district_coverage':d[['district','valid_fraction','mean_ndvi','mean_lst_c','mean_uncertainty_k']].to_dict('records')}
 # Same-screening sensitivity: cap uncertainty at4K rather than5K.
 global ndvi,lst
 backup_n,backup_l=ndvi.copy(),lst.copy();ndvi=np.where(unc<=4,ndvi,np.nan);lst=np.where(unc<=4,lst,np.nan)
 report['uncertainty_4k_grid300']=association(grid(300));ndvi,lst=backup_n,backup_l
 (OUT/'analysis_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
