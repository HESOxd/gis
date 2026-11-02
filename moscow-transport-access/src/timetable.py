"""Small stop-to-stop Connection Scan reference engine; no invented walking links."""
import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def seconds(value):
    h,m,s=map(int,value.split(':'))
    if h<0 or not 0<=m<60 or not 0<=s<60:raise ValueError(value)
    return 3600*h+60*m+s


def rows(archive,name):
    return csv.DictReader(io.TextIOWrapper(archive.open(name),encoding='utf-8-sig',newline=''))


def active_services(archive,service_date):
    day=datetime.strptime(service_date,'%Y%m%d');weekday=day.strftime('%A').lower();active=set()
    if 'calendar.txt' in archive.namelist():
        active={r['service_id'] for r in rows(archive,'calendar.txt') if r['start_date']<=service_date<=r['end_date'] and r[weekday]=='1'}
    if 'calendar_dates.txt' in archive.namelist():
        for r in rows(archive,'calendar_dates.txt'):
            if r['date']!=service_date:continue
            if r['exception_type']=='1':active.add(r['service_id'])
            elif r['exception_type']=='2':active.discard(r['service_id'])
    return active


@dataclass(frozen=True)
class Connection:
    departure:int
    arrival:int
    origin:str
    destination:str
    trip:str
    pickup:bool=True
    dropoff:bool=True


def connections(archive,service_date,route_ids):
    if any(name in archive.namelist() for name in ('frequencies.txt','transfers.txt','pathways.txt')):
        raise NotImplementedError('Feed contains frequency/transfer/pathway rules: this reference pilot must not silently ignore them')
    active=active_services(archive,service_date)
    trips={r['trip_id'] for r in rows(archive,'trips.txt') if r['service_id'] in active and r['route_id'] in route_ids}
    stops=defaultdict(list)
    for r in rows(archive,'stop_times.txt'):
        if r['trip_id'] in trips:stops[r['trip_id']].append(r)
    output=[]
    for trip,events in stops.items():
        events.sort(key=lambda r:int(r['stop_sequence']))
        for a,b in zip(events,events[1:]):
            departure=seconds(a['departure_time']);arrival=seconds(b['arrival_time'])
            if arrival<departure:raise ValueError(f'Non-monotonic times: {trip}')
            output.append(Connection(departure,arrival,a['stop_id'],b['stop_id'],trip,
                                     a.get('pickup_type','') in {'','0'}, b.get('drop_off_type','') in {'','0'}))
    return sorted(output,key=lambda c:(c.departure,c.arrival,c.trip))


def earliest_arrivals(events,origin,start,minimum_transfer=120):
    """Waiting included; stay seated on same trip without transfer penalty.

    Only same-stop transfers are supported. No footpaths, metro, origin access,
    destination egress or realtime delays are silently supplied.
    """
    if minimum_transfer<0:raise ValueError('Negative transfer time')
    arrivals={origin:start};ready={origin:start};boarded=set()
    for c in sorted(events,key=lambda c:(c.departure,c.arrival,c.trip)):
        if c.departure<start:continue
        if c.trip not in boarded:
            if not c.pickup or ready.get(c.origin,float('inf'))>c.departure:continue
            boarded.add(c.trip)
        if c.dropoff and c.arrival<arrivals.get(c.destination,float('inf')):
            arrivals[c.destination]=c.arrival
            ready[c.destination]=c.arrival+minimum_transfer
    return arrivals


def main():
    parser=argparse.ArgumentParser(description='Explicitly scoped GTFS stop-to-stop pilot, not full city accessibility')
    parser.add_argument('--feed',type=Path,required=True);parser.add_argument('--service-date',required=True)
    parser.add_argument('--route-id',action='append',required=True);parser.add_argument('--origin-stop',required=True)
    parser.add_argument('--departure',default='08:00:00');parser.add_argument('--transfer-seconds',type=int,default=120)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with zipfile.ZipFile(args.feed) as archive:
        stops={r['stop_id']:r['stop_name'] for r in rows(archive,'stops.txt')}
        if args.origin_stop not in stops:raise ValueError('Unknown origin stop')
        events=connections(archive,args.service_date,set(args.route_id))
    arrival=earliest_arrivals(events,args.origin_stop,seconds(args.departure),args.transfer_seconds)
    result={'status':'SCOPED_SURFACE_STOP_TO_STOP_PILOT','service_date':args.service_date,'departure':args.departure,
            'route_ids':args.route_id,'origin_stop':args.origin_stop,'connections':len(events),
            'minimum_transfer_seconds':args.transfer_seconds,
            'limitations':['selected routes only','same-stop transfers only','no walking access or egress','no metro or MCD','no previous-service-day carryover','no realtime delays','community archive freshness unverified'],
            'arrivals':[{'stop_id':stop,'name':stops.get(stop,''),'arrival_seconds':value,'elapsed_minutes':(value-seconds(args.departure))/60} for stop,value in sorted(arrival.items(),key=lambda x:x[1])]}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(f'{len(events)} connections; {len(arrival)} reached stops')

if __name__=='__main__':main()
