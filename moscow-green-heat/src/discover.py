"""Query public STAC catalogues; cache complete source item metadata."""
import json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
BBOX=[37.66,55.78,37.75,55.84]
DATE='2025-06-01T00:00:00Z/2025-08-31T23:59:59Z'
SEARCHES={
 'landsat':('https://planetarycomputer.microsoft.com/api/stac/v1/search','landsat-c2-l2'),
 'sentinel':('https://earth-search.aws.element84.com/v1/search','sentinel-2-l2a')}
for kind,(url,collection) in SEARCHES.items():
 path=ROOT/f'data/raw/{kind}_search.json'
 if path.exists():result=json.loads(path.read_text())
 else:
  response=requests.post(url,json={'collections':[collection],'bbox':BBOX,'datetime':DATE,'limit':100,'query':{'eo:cloud_cover':{'lt':15}}},timeout=40)
  response.raise_for_status();result=response.json();path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(kind,'items',len(result.get('features',[])),flush=True)
 for item in result.get('features',[])[:5]:print(item['id'],item['properties'].get('datetime'),item['properties'].get('eo:cloud_cover'),list(item['assets']),flush=True)
