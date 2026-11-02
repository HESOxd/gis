"""Download a small, cached OSM study area. No API keys required."""
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
RAW.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'MoscowWalkAccessPortfolio/0.1 (educational GIS study)'


def get(url, path, params=None):
    if path.exists():
        return
    for attempt in range(3):
        try:
            response = SESSION.get(url, params=params, timeout=90)
            response.raise_for_status()
            path.write_bytes(response.content)
            print(f'Downloaded {path.name}: {len(response.content):,} bytes', flush=True)
            time.sleep(1.1)
            return
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def main():
    boundaries = []
    for name, query in [('bogorodskoe', 'район Богородское, Москва'),
                        ('preobrazhenskoe', 'район Преображенское, Москва')]:
        path = RAW / f'{name}.json'
        get('https://nominatim.openstreetmap.org/search', path,
            {'q': query, 'format': 'json', 'polygon_geojson': 1, 'limit': 1})
        result = json.loads(path.read_text())[0]
        assert result['osm_type'] == 'relation' and result['type'] == 'administrative'
        boundaries.append(shape(result['geojson']))
    project = Transformer.from_crs(4326, 32637, always_xy=True).transform
    unproject = Transformer.from_crs(32637, 4326, always_xy=True).transform
    # A 2 km margin exceeds 15 min at 5 km/h, including endpoint connectors.
    extent = transform(unproject, transform(project, unary_union(boundaries)).buffer(2000))
    west, south, east, north = extent.bounds
    nx, ny = math.ceil((east-west)/0.025), math.ceil((north-south)/0.02)
    for y in range(ny):
        for x in range(nx):
            bbox = [west+(east-west)*x/nx, south+(north-south)*y/ny,
                    west+(east-west)*(x+1)/nx, south+(north-south)*(y+1)/ny]
            get('https://www.openstreetmap.org/api/0.6/map',
                RAW / f'osm_{x:02}_{y:02}.osm', {'bbox': ','.join(f'{v:.7f}' for v in bbox)})
    manifest = {
        'download_completed_utc': datetime.now(timezone.utc).isoformat(),
        'bbox_wgs84': [west, south, east, north], 'routing_margin_m': 2000,
        'osm_api': 'https://www.openstreetmap.org/api/0.6/map',
        'nominatim': 'https://nominatim.openstreetmap.org/search',
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(RAW.iterdir()) if p.suffix in ('.json', '.osm') and p.name != 'manifest.json'}
    }
    (RAW / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
