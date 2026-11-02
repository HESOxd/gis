"""Remove only empty-name CSV columns. Keep original values and report changes."""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/raw/moscow_gtfs_20260630.zip'
TARGET=ROOT/'data/raw/moscow_gtfs_header_normalized.zip'

def main():
 changes=[]
 with zipfile.ZipFile(SOURCE) as source, zipfile.ZipFile(TARGET,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as target:
  for name in source.namelist():
   if name.endswith('/'):continue
   if not name.endswith('.txt'):
    target.writestr(name,source.read(name));continue
   with source.open(name) as raw:
    reader=csv.reader(io.TextIOWrapper(raw,encoding='utf-8-sig',newline=''))
    header=next(reader);keep=[i for i,column in enumerate(header) if column.strip()]
    removed=[i for i,column in enumerate(header) if not column.strip()]
    count=0;nonempty_removed=0;bad_width=0
    with target.open(name,'w',force_zip64=True) as out:
     wrapper=io.TextIOWrapper(out,encoding='utf-8',newline='');writer=csv.writer(wrapper,lineterminator='\n')
     writer.writerow([header[i] for i in keep])
     for row in reader:
      count+=1
      if len(row)!=len(header):bad_width+=1;raise ValueError(f'{name} row {count}: unexpected CSV width')
      if any(row[i].strip() for i in removed):nonempty_removed+=1;raise ValueError(f'{name}: nonempty value in unnamed column')
      writer.writerow([row[i] for i in keep])
     wrapper.flush();wrapper.detach()
    changes.append({'file':name,'removed_empty_column_indexes':removed,'rows':count,'nonempty_discarded_values':nonempty_removed,'bad_width_rows':bad_width})
 assert all(r['nonempty_discarded_values']==0 and r['bad_width_rows']==0 for r in changes)
 report={'operation':'remove_only_empty_name_columns_with_empty_values','semantic_schedule_changes':False,
  'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'normalized_sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),
  'changes':changes,'note':'This does not establish licensing, freshness, completeness or full GTFS validity.'}
 (ROOT/'outputs/header_normalization.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
