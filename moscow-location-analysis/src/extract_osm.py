"""Reuse the frozen OSM snapshot from portfolio project 1; no network access."""
import json
import sys
from collections import Counter
from pathlib import Path
from shapely.geometry import Point, Polygon, mapping

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT.parent / 'moscow-walk-access'
sys.path.insert(0, str(PREVIOUS / 'src'))
from analyze import parse_osm


def category(tags):
    if tags.get('amenity') == 'cafe':
        return 'cafe'
    if tags.get('office') not in {None, 'no', 'vacant'}:
        return 'office'
    if tags.get('railway') == 'subway_entrance' or tags.get('station') == 'subway':
        return 'metro'
    if tags.get('highway') == 'bus_stop' or tags.get('railway') == 'tram_stop':
        return 'stop'
    return None


def main():
    nodes, ways, _ = parse_osm()
    features = []
    for ident, (lon, lat, tags) in nodes.items():
        kind = category(tags)
        if kind:
            features.append(feature(f'node/{ident}', kind, Point(lon, lat), tags))
    for ident, (refs, tags) in ways.items():
        kind = category(tags)
        if not kind or len(refs) < 4 or refs[0] != refs[-1] or not all(n in nodes for n in refs):
            continue
        poly = Polygon([(nodes[n][0], nodes[n][1]) for n in refs])
        if poly.is_valid:
            features.append(feature(f'way/{ident}', kind, poly.representative_point(), tags))
    output = ROOT / 'data/processed/osm_poi_candidates.geojson'
    output.write_text(json.dumps({'type':'FeatureCollection', 'features':features}, ensure_ascii=False))
    counts = dict(Counter(f['properties']['kind'] for f in features))
    (ROOT / 'data/processed/extraction_status.json').write_text(json.dumps({
        'stage':'raw_candidates_not_deduplicated_or_clipped',
        'source':'../moscow-walk-access/data/raw/manifest.json',
        'counts':counts,
        'note':'Transit points are infrastructure proxies, not measured passenger flow.'
    }, ensure_ascii=False, indent=2))
    print(counts)


def feature(ident, kind, geometry, tags):
    return {'type':'Feature', 'geometry':mapping(geometry), 'properties':{
        'osm_id':ident, 'kind':kind, 'name':tags.get('name',''),
        'address':' '.join(filter(None,[tags.get('addr:street'),tags.get('addr:housenumber')])),
        'office':tags.get('office'), 'amenity':tags.get('amenity'),
        'source':'OSM snapshot 2026-11-01'
    }}


if __name__ == '__main__':
    main()
