"""Inspect the original community GTFS without silently repairing/replacing it."""
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT/'data/raw/moscow_gtfs_20260630.zip'


def gtfs_seconds(value):
    h,m,s=map(int,value.split(':'))
    if h<0 or not 0<=m<60 or not 0<=s<60:raise ValueError(value)
    return h*3600+m*60+s


def reader(z,name):
    return csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8-sig',newline=''))


def main():
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        names={Path(n).name:n for n in z.namelist() if not n.endswith('/')}
        result={'source':'Mobility Database mdb-3226 / community feed',
          'archive_url':'https://files.mobilitydatabase.org/mdb-3226/mdb-3226-202606301640/mdb-3226-202606301640.zip',
          'sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'archive_bytes':ZIP.stat().st_size,
          'files':{},'license_verified':False,'current_service_date':'20261102'}
        for name,full in names.items():
            if name.endswith('.txt'):
                r=reader(z,full)
                sample=[]
                for _,row in zip(range(3),r):sample.append(row)
                result['files'][name]={'uncompressed_bytes':z.getinfo(full).file_size,'columns':r.fieldnames,'sample':sample}
        if 'routes.txt' in names:
            routes=list(reader(z,names['routes.txt']))
            result['routes_count']=len(routes)
            result['route_types']=dict(Counter(r.get('route_type','') for r in routes))
        if 'agency.txt' in names:result['agencies']=list(reader(z,names['agency.txt']))
        if 'calendar.txt' in names:
            calendars=list(reader(z,names['calendar.txt']))
            result['calendar_rows']=len(calendars)
            result['calendar_start_min']=min((r.get('start_date','') for r in calendars),default=None)
            result['calendar_end_max']=max((r.get('end_date','') for r in calendars),default=None)
            on_date=date(2026,11,2);key=on_date.strftime('%A').lower();ds=on_date.strftime('%Y%m%d')
            active={r['service_id'] for r in calendars if r.get('start_date','')<=ds<=r.get('end_date','') and r.get(key)=='1'}
            if 'calendar_dates.txt' in names:
                for r in reader(z,names['calendar_dates.txt']):
                    if r.get('date')==ds:
                        if r.get('exception_type')=='1':active.add(r['service_id'])
                        elif r.get('exception_type')=='2':active.discard(r['service_id'])
            result['active_services_on_target_date']=len(active)
        if 'stops.txt' in names:
            stops=list(reader(z,names['stops.txt']));result['stops_count']=len(stops)
            coordinates=[];invalid=0
            for r in stops:
                try:
                    lat,lon=float(r['stop_lat']),float(r['stop_lon'])
                    if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError()
                    coordinates.append((lat,lon))
                except (ValueError,KeyError):invalid+=1
            result['invalid_stop_coordinates']=invalid
            if coordinates:result['stops_bbox_lat_lon']=[min(x[0] for x in coordinates),min(x[1] for x in coordinates),max(x[0] for x in coordinates),max(x[1] for x in coordinates)]
        if 'trips.txt' in names:
            trips=list(reader(z,names['trips.txt']));result['trips_count']=len(trips)
            result['trip_type_counts']=dict(Counter(t.get('trip_type','') for t in trips))
        if 'stop_times.txt' in names:
            sample=[];count=0;missing=0;invalid_time=0;over24=0;negative=0
            for r in reader(z,names['stop_times.txt']):
                count+=1
                if len(sample)<10:sample.append(r)
                try:
                    arrival=gtfs_seconds(r['arrival_time']);departure=gtfs_seconds(r['departure_time'])
                    over24+=int(max(arrival,departure)>=86400);negative+=int(departure<arrival)
                except (ValueError,KeyError,AttributeError):
                    if not r.get('arrival_time') or not r.get('departure_time'):missing+=1
                    else:invalid_time+=1
            result['stop_times']={'rows':count,'missing_time_rows':missing,'invalid_time_rows':invalid_time,'over_24h_rows':over24,'departure_before_arrival':negative,'first_rows':sample}
        result['status']='AUDITED_COMMUNITY_FEED_NOT_FULL_TRANSPORT_ACCESSIBILITY_RESULT'
        (ROOT/'outputs/feed_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k not in ['files','agencies','stop_times']},ensure_ascii=False,indent=2))
        print('Stop-time audit:',{k:v for k,v in result.get('stop_times',{}).items() if k!='first_rows'})

if __name__=='__main__':main()
