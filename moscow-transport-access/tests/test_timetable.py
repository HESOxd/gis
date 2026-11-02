import io
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from timetable import Connection as C, earliest_arrivals, seconds, active_services

class TimetableTests(unittest.TestCase):
 def test_waiting_and_missed_transfer(self):
  events=[C(600,1200,'A','B','one'),C(1250,1500,'B','C','two'),C(1400,1700,'B','C','three')]
  self.assertEqual(earliest_arrivals(events,'A',0,120)['C'],1700)
 def test_stay_on_same_vehicle_without_transfer_penalty(self):
  events=[C(600,1200,'A','B','one'),C(1210,1300,'B','C','one',pickup=False)]
  self.assertEqual(earliest_arrivals(events,'A',0,120)['C'],1300)
 def test_no_pickup_or_dropoff(self):
  self.assertNotIn('B',earliest_arrivals([C(100,200,'A','B','one',pickup=False)],'A',0))
  self.assertNotIn('B',earliest_arrivals([C(100,200,'A','B','one',dropoff=False)],'A',0))
 def test_service_day_time_over_24(self):
  self.assertEqual(seconds('25:30:00'),91800)
  with self.assertRaises(ValueError):seconds('25:60:00')
 def test_calendar_exception_overrides_weekday(self):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:
   z.writestr('calendar.txt','service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\na,1,1,1,1,1,0,0,20260101,20261231\n')
   z.writestr('calendar_dates.txt','service_id,date,exception_type\na,20261102,2\nb,20261102,1\n')
  with zipfile.ZipFile(stream) as z:self.assertEqual(active_services(z,'20261102'),{'b'})

if __name__=='__main__':unittest.main()
