"""Cross-check real pilot against a separate repeated per-trip relaxation oracle."""
import json,zipfile
from collections import defaultdict
from pathlib import Path
from timetable import connections,seconds
ROOT=Path(__file__).resolve().parents[1]
def main():
 result=json.loads((ROOT/'outputs/tram13_stop_pilot.json').read_text());start=seconds(result['departure']);origin=result['origin_stop'];transfer=result['minimum_transfer_seconds']
 with zipfile.ZipFile(ROOT/'data/raw/moscow_gtfs_header_normalized.zip') as z:events=connections(z,result['service_date'],set(result['route_ids']))
 trips=defaultdict(list)
 for event in events:trips[event.trip].append(event)
 labels={origin:start};passes=0
 # Different traversal from chronological Connection Scan: repeatedly scan whole trips
 # in reverse ID order until stop labels reach a fixed point.
 while True:
  old=labels.copy();passes+=1
  for trip in sorted(trips,reverse=True):
   onboard=False
   for e in sorted(trips[trip],key=lambda x:(x.departure,x.arrival)):
    if e.departure<start:continue
    ready=labels.get(e.origin,float('inf'))+(0 if e.origin==origin else transfer)
    if e.pickup and ready<=e.departure:onboard=True
    if onboard and e.dropoff:labels[e.destination]=min(labels.get(e.destination,float('inf')),e.arrival)
  if old==labels:break
  if passes>len(events):raise AssertionError('Oracle did not converge')
 expected={r['stop_id']:r['arrival_seconds'] for r in result['arrivals']}
 assert labels==expected,'Independent stop-time oracle differs'
 report={'passed':True,'reference':'repeated whole-trip relaxation, reverse trip order','passes':passes,'connections':len(events),'reached_stops':len(labels),'matched_all_arrival_times':True}
 (ROOT/'outputs/independent_timetable_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
