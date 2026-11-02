"""Download the referenced archive separately and verify the frozen SHA256."""
import hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
audit=json.loads((ROOT/'outputs/feed_audit.json').read_text())
target=ROOT/'data/raw/moscow_gtfs_20260630.zip'
if not target.exists():
 target.parent.mkdir(parents=True,exist_ok=True)
 partial=target.with_suffix('.partial')
 with requests.get(audit['archive_url'],stream=True,timeout=(15,90)) as response:
  response.raise_for_status()
  with partial.open('wb') as out:
   for chunk in response.iter_content(1048576):out.write(chunk)
 assert hashlib.sha256(partial.read_bytes()).hexdigest()==audit['sha256'],'Source hash differs'
 partial.replace(target)
assert hashlib.sha256(target.read_bytes()).hexdigest()==audit['sha256']
print('Verified',target.name)
