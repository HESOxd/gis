"""Create cloud-masked NDVI and LST, retain quality/support rasters."""
import json
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import reproject,Resampling
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw';OUT=ROOT/'data/processed';OUT.mkdir(exist_ok=True)
def read(name):
 with rasterio.open(RAW/f'{name}.tif') as d:return d.read(1),d.profile.copy()
def warp(a,profile,target,resampling=Resampling.nearest,nodata=None):
 out=np.full((target['height'],target['width']),np.nan,dtype='float32')
 reproject(a,out,src_transform=profile['transform'],src_crs=profile['crs'],dst_transform=target['transform'],dst_crs=target['crs'],src_nodata=nodata,dst_nodata=np.nan,resampling=resampling)
 return out
def save(name,a,p,nodata=-9999):
 p=p.copy();p.update(driver='GTiff',count=1,dtype='float32',nodata=nodata,compress='deflate',tiled=False)
 for k in ['blockxsize','blockysize']:p.pop(k,None)
 with rasterio.open(OUT/f'{name}.tif','w',**p) as d:d.write(np.where(np.isfinite(a),a,nodata).astype('float32'),1)
def main():
 item=json.loads((RAW/'sentinel_item.json').read_text());flag=item['properties']['earthsearch:boa_offset_applied']
 # These COGs have already removed the +1000 baseline shift. Never subtract twice.
 if flag is not True:raise ValueError('This workflow requires verified harmonized Sentinel COGs')
 red,sp=read('sentinel_red');nir,np_=read('sentinel_nir');scl,scp=read('sentinel_scl')
 assert sp['transform']==np_['transform'] and red.shape==nir.shape
 scene=warp(scl,scp,sp)
 ndvi=(nir.astype(float)-red)/(nir.astype(float)+red)
 valid=np.isin(scene,[4,5])&(red>0)&(nir>0)&np.isfinite(ndvi)&(np.abs(ndvi)<=1)
 ndvi[~valid]=np.nan;save('ndvi_10m',ndvi,sp)
 st,lp=read('landsat_lwir11');qa,_=read('landsat_qa_pixel');sat,_=read('landsat_qa_radsat');unc,_=read('landsat_qa');cdist,_=read('landsat_cdist')
 lsitem=json.loads((RAW/'landsat_item.json').read_text());scale=lsitem['assets']['lwir11']['raster:bands'][0]
 assert scale['scale']==0.00341802 and scale['offset']==149
 lst=st.astype(float)*scale['scale']+scale['offset']-273.15
 # Bits 0-5 remove fill, dilation, cirrus, cloud, shadow and snow; bit7 water.
 lvalid=((qa&191)==0)&(sat==0)&(st>0)&(unc>=0)
 nd30=warp(ndvi.astype('float32'),sp,lp,Resampling.average,nodata=np.nan)
 support=warp(valid.astype('float32'),sp,lp,Resampling.average)
 water=warp((scene==6).astype('float32'),sp,lp,Resampling.average)
 districts=gpd.read_file(RAW/'districts.geojson').to_crs(lp['crs'])
 inside=geometry_mask(districts.geometry,out_shape=st.shape,transform=lp['transform'],invert=True)
 base=lvalid&(support>=.8)&(water<.2)&inside&np.isfinite(nd30)
 audits=[]
 for uncertainty in [2,3,4,5]:
  for distance in [0,.3,.5,1]:
   mask=base&(unc*.01<=uncertainty)&(cdist*.01>=distance)
   audits.append({'max_st_uncertainty_k':uncertainty,'min_cloud_distance_km':distance,'valid_pixels':int(mask.sum()),'fraction_of_district_area_pixels':float(mask.sum()/inside.sum())})
 # Main explicit screening: <=5K uncertainty and >=500m from detected clouds.
 joint=base&(unc*.01<=5)&(cdist*.01>=.5)
 save('ndvi_30m',np.where(joint,nd30,np.nan),lp);save('lst_celsius_30m',np.where(joint,lst,np.nan),lp)
 save('common_valid_mask',joint.astype(float),lp);save('s2_land_support',support,lp)
 save('lst_unmasked_celsius',np.where(st>0,lst,np.nan),lp)
 save('lst_uncertainty_kelvin',np.where(unc>=0,unc*.01,np.nan),lp)
 report={'sentinel_scene':item['id'],'landsat_scene':lsitem['id'],'sentinel_effective_scale':.0001,'sentinel_effective_offset':0,'metadata_offset_ignored_because_already_applied':True,'ndvi_native_m':10,'lst_grid_m':30,'lst_sensor_native_m':100,'district_pixels':int(inside.sum()),'joint_valid_pixels':int(joint.sum()),'district_valid_fraction':float(joint.sum()/inside.sum()),'sensitivity':audits,'lst_valid_range_c':list(map(float,[lst[joint].min(),lst[joint].max()])),'ndvi_joint_range':list(map(float,[nd30[joint].min(),nd30[joint].max()]))}
 (ROOT/'outputs/preprocess_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
