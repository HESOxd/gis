"""Network accessibility in UTM 37N; exports open GIS data and portfolio maps."""
import csv
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import networkx as nx
from pyproj import Transformer
from shapely import STRtree, make_valid, buffer as vector_buffer, union_all
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import transform, unary_union, polygonize, substring

ROOT = Path(__file__).resolve().parents[1]
RAW, DATA, OUT = ROOT/'data/raw', ROOT/'data/processed', ROOT/'outputs'
CRS = 'EPSG:32637'
PROJECT = Transformer.from_crs(4326, CRS, always_xy=True).transform
SPEED = 5000/60  # metres per minute
MAX_SNAP = 100
RESIDENTIAL = {'apartments', 'residential', 'house', 'detached', 'terrace', 'dormitory', 'semidetached_house'}
FORBIDDEN_HW = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'construction', 'proposed', 'raceway', 'bus_guideway'}
FOOT_ALLOWED = {'yes', 'designated', 'permissive', 'destination'}


def walkable(tags):
    if not tags.get('highway') or tags.get('area') == 'yes':
        return False
    if tags.get('foot') in {'no', 'private', 'use_sidepath'}:
        return False
    if tags.get('access') in {'no', 'private'} and tags.get('foot') not in FOOT_ALLOWED:
        return False
    if tags['highway'] in FORBIDDEN_HW and tags.get('foot') not in FOOT_ALLOWED:
        return False
    if tags['highway'] == 'cycleway' and tags.get('foot') not in FOOT_ALLOWED:
        return False
    return True


def parse_osm():
    nodes, ways, relations = {}, {}, {}
    for path in sorted(RAW.glob('osm_*.osm')):
        for _, e in ET.iterparse(path, events=('end',)):
            if e.tag not in {'node', 'way', 'relation'}:
                continue
            ident = int(e.attrib['id'])
            tags = {t.attrib['k']: t.attrib['v'] for t in e.findall('tag')}
            if e.tag == 'node':
                nodes[ident] = (float(e.attrib['lon']), float(e.attrib['lat']), tags)
            elif e.tag == 'way':
                ways[ident] = ([int(n.attrib['ref']) for n in e.findall('nd')], tags)
            else:
                relations[ident] = ([(m.attrib['type'], int(m.attrib['ref']), m.attrib.get('role', ''))
                                     for m in e.findall('member')], tags)
            e.clear()
        print(f'Parsed {path.name}', flush=True)
    return nodes, ways, relations


def classify(tags):
    if tags.get('amenity') == 'school':
        return 'school'
    # Conservative public polyclinic proxy. Excludes private clinics and dentists.
    if 'поликлиник' in tags.get('name', '').lower() and (
        tags.get('amenity') == 'clinic' or tags.get('healthcare') in {'clinic', 'centre'}):
        if tags.get('healthcare:speciality') == 'dentistry' or tags.get('ownership') == 'private':
            return None
        return 'clinic'
    return None


def records_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry='geometry', crs=CRS)


def write_layer(rows, name, gpkg):
    if not rows:
        return
    frame = records_gdf(rows)
    frame.to_file(gpkg, layer=name, driver='GPKG', dataset_options={'VERSION':'1.3'})
    frame.to_crs(4326).to_file(DATA/f'{name}.geojson', driver='GeoJSON')


def connect_points(graph, edges, objects):
    """Split nearest edges at projected locations; preserve along-edge distance."""
    tree = STRtree([e[2] for e in edges])
    groups = defaultdict(list)
    for index, obj in enumerate(objects):
        p = obj['point']
        ei = int(tree.nearest(p))
        line = edges[ei][2]
        position = line.project(p)
        q = line.interpolate(position)
        offset = p.distance(q)
        obj['snap_m'] = offset
        obj['graph_node'] = f'object_{index}'
        if offset <= MAX_SNAP:
            groups[ei].append((position, obj['graph_node'], q))
    for ei, locations in groups.items():
        a, b, line = edges[ei]
        graph.remove_edge(a, b)
        stops = [(0.0, a, Point(line.coords[0]))] + sorted(locations) + [(line.length, b, Point(line.coords[-1]))]
        for (_, u, p), (_, v, q) in zip(stops, stops[1:]):
            graph.add_node(u, x=p.x, y=p.y)
            graph.add_node(v, x=q.x, y=q.y)
            graph.add_edge(u, v, length=p.distance(q), geometry=LineString([p, q]))


def service_lines(graph, distances, budget):
    result = []
    nearby = [n for n, distance in distances.items() if distance < budget]
    for u, v, edge in graph.edges(nearby, data=True):
        du, dv, length = distances.get(u, math.inf), distances.get(v, math.inf), edge['length']
        if length < 1e-8:
            continue
        line = edge['geometry']
        # Stored geometry can be reversed relative to undirected edge iteration.
        if math.hypot(line.coords[0][0]-graph.nodes[u]['x'], line.coords[0][1]-graph.nodes[u]['y']) > 0.001:
            line = LineString(list(line.coords)[::-1])
        left, right = min(length, max(0, budget-du)), min(length, max(0, budget-dv))
        if left + right >= length and left + right > 0:
            result.append(line)
        else:
            if left > 0:
                result.append(substring(line, 0, left))
            if right > 0:
                result.append(substring(line, length-right, length))
    return result


def main():
    DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
    boundaries = []
    for file, label in [('bogorodskoe', 'Богородское'), ('preobrazhenskoe', 'Преображенское')]:
        value = json.loads((RAW/f'{file}.json').read_text())[0]
        boundaries.append({'district': label, 'osm_relation': value['osm_id'],
                           'geometry': transform(PROJECT, __import__('shapely').geometry.shape(value['geojson']))})
    study = unary_union([x['geometry'] for x in boundaries])
    extent = study.buffer(2000)
    nodes, ways, relations = parse_osm()
    xy = {i: PROJECT(n[0], n[1]) for i, n in nodes.items()}
    blocked = {i for i, (_, _, t) in nodes.items() if
               (t.get('barrier') in {'wall', 'fence', 'block'} or
                (t.get('barrier') and t.get('access') in {'no', 'private'})) and t.get('foot') not in FOOT_ALLOWED}
    graph = nx.Graph()
    buildings, candidates, parks, water = [], [], [], []
    missing_ways = 0
    features = []
    for wid, (refs, tags) in ways.items():
        if not all(i in xy for i in refs) or len(refs) < 2:
            missing_ways += 1
            continue
        coords = [xy[i] for i in refs]
        if walkable(tags):
            for a, b in zip(refs, refs[1:]):
                if a == b or a in blocked or b in blocked:
                    continue
                line = LineString([xy[a], xy[b]])
                if line.length > 0 and line.intersects(extent):
                    graph.add_node(a, x=xy[a][0], y=xy[a][1]); graph.add_node(b, x=xy[b][0], y=xy[b][1])
                    graph.add_edge(a, b, length=line.length, geometry=line)
        if refs[0] == refs[-1] and len(refs) >= 4:
            poly = make_valid(Polygon(coords))
            if not poly.is_empty and poly.intersects(extent):
                features.append((f'way/{wid}', poly, tags, refs))
    # Multipolygon buildings / campuses: only complete geometries, with inner rings removed.
    relation_members = set()
    incomplete_relations = 0
    for rid, (members, tags) in relations.items():
        if tags.get('type') != 'multipolygon' or not (tags.get('building') or classify(tags)):
            continue
        relevant = [(mid, role) for typ, mid, role in members if typ == 'way']
        if any(mid not in ways or not all(n in xy for n in ways[mid][0]) for mid, _ in relevant):
            incomplete_relations += 1
            continue
        outer, inner = [], []
        refs = []
        for mid, role in relevant:
            nids = ways[mid][0]; refs.extend(nids)
            line = LineString([xy[n] for n in nids])
            (inner if role == 'inner' else outer).append(line)
        geom = unary_union(list(polygonize(unary_union(outer))))
        if inner:
            geom = geom.difference(unary_union(list(polygonize(unary_union(inner)))))
        if not geom.is_empty and geom.intersects(extent):
            features.append((f'relation/{rid}', geom, tags, refs))
            if tags.get('building'):
                relation_members.update(f'way/{mid}' for mid, _ in relevant)
    for ident, poly, tags, refs in features:
        kind = classify(tags)
        if kind:
            candidates.append({'id': ident, 'kind': kind, 'name': tags.get('name', kind), 'geometry': poly, 'refs': refs})
        if tags.get('building') in RESIDENTIAL and ident not in relation_members:
            p = poly.representative_point()
            district = next((b['district'] for b in boundaries if b['geometry'].covers(p)), None)
            if district:
                try:
                    floors = float(tags.get('building:levels', '').replace(',', '.'))
                    if not 1 <= floors <= 100: floors = None
                except ValueError:
                    floors = None
                buildings.append({'id': ident, 'district': district, 'geometry': poly,
                                  'point': p, 'refs': refs, 'floors': floors,
                                  'address': ' '.join(filter(None, [tags.get('addr:street'), tags.get('addr:housenumber')]))})
        if tags.get('leisure') in {'park', 'garden'} or tags.get('landuse') == 'forest' or tags.get('natural') == 'wood':
            parks.append({'geometry': poly.intersection(study)})
        if tags.get('natural') == 'water':
            water.append({'geometry': poly.intersection(study)})
    for nid, (_, _, tags) in nodes.items():
        kind = classify(tags)
        if kind and extent.covers(Point(xy[nid])):
            candidates.append({'id': f'node/{nid}', 'kind': kind, 'name': tags.get('name', kind),
                               'geometry': Point(xy[nid]), 'refs': [nid]})
    # OSM sometimes tags both campus and its constituent school buildings.
    facilities = [f for f in candidates if not any(
        f is not other and f['kind'] == other['kind'] and other['geometry'].area > f['geometry'].area
        and other['geometry'].covers(f['geometry'].representative_point()) for other in candidates)]
    original_edges = []
    for u,v,d in graph.edges(data=True):
        line=d['geometry']
        if line.coords[0] != (graph.nodes[u]['x'],graph.nodes[u]['y']):
            line=LineString(list(line.coords)[::-1])
        original_edges.append((u,v,line))
    tree = STRtree([e[2] for e in original_edges])
    for obj in facilities + buildings:
        entrances = [Point(xy[n]) for n in obj['refs'] if nodes[n][2].get('entrance') not in {None, 'no', 'exit'}
                     and nodes[n][2].get('access') not in {'no', 'private'}]
        if entrances:
            obj['point'] = min(entrances, key=lambda p: p.distance(original_edges[int(tree.nearest(p))][2]))
            obj['entry_method'] = 'osm_entrance'
        else:
            obj['point'] = obj['geometry'].representative_point()
            obj['entry_method'] = 'representative_point'
    connect_points(graph, original_edges, facilities + buildings)
    print(f'Graph: {len(graph):,} nodes; homes {len(buildings)}; facilities {len(facilities)}', flush=True)
    iso, reachable = [], {'school': {}, 'clinic': {}}
    for index, f in enumerate(facilities):
        if f['snap_m'] > MAX_SNAP:
            continue
        d = nx.single_source_dijkstra_path_length(graph, f['graph_node'], cutoff=SPEED*15, weight='length')
        d = {n: dist + f['snap_m'] for n, dist in d.items()}
        for n, dist in d.items():
            reachable[f['kind']][n] = min(reachable[f['kind']].get(n, math.inf), dist)
        previous_corridor = None
        for minutes in (10, 15):
            lines = service_lines(graph, d, SPEED*minutes)
            if lines:
                # Buffer segments separately before dissolving. This avoids the expensive
                # all-at-once MultiLineString buffer on dense urban intersections.
                inside = [line for line in lines if line.intersects(study)]
                if inside:
                    corridor = union_all(vector_buffer(inside,18,quad_segs=2),grid_size=1).intersection(study)
                    # Coarse rounded caps can introduce tiny non-nested slivers.
                    # Preserve monotonicity of the display polygons explicitly.
                    if previous_corridor is not None:
                        corridor = union_all([corridor,previous_corridor])
                    previous_corridor = corridor
                    iso.append({'facility_id':f['id'], 'kind':f['kind'], 'minutes':minutes,
                                'name':f['name'], 'geometry':corridor})
        if index % 10 == 0: print(f'Isochrones {index+1}/{len(facilities)}', flush=True)
    # Full distances distinguish a long valid route from a disconnected component.
    # A temporary source carries each facility's connector cost into Dijkstra.
    for kind in ('school','clinic'):
        source = '__source_'+kind
        graph.add_node(source)
        for f in facilities:
            if f['kind']==kind and f['snap_m']<=MAX_SNAP:
                graph.add_edge(source,f['graph_node'],length=f['snap_m'])
        reachable[kind] = nx.single_source_dijkstra_path_length(graph,source,weight='length')
        reachable[kind].pop(source,None)
        graph.remove_node(source)
    population_path = RAW/'population.csv'
    population = {}
    if population_path.exists():
        with population_path.open() as handle:
            population = {r['district']: int(r['population']) for r in csv.DictReader(handle)}
    import statistics
    medians = {b['district']: statistics.median([h['floors'] for h in buildings if h['district']==b['district'] and h['floors']]) for b in boundaries}
    weights = defaultdict(float)
    for h in buildings:
        h['floor_imputed'] = h['floors'] is None
        h['floor_used'] = h['floors'] or medians[h['district']]
        h['weight'] = h['geometry'].area*h['floor_used']
        weights[h['district']] += h['weight']
    for h in buildings:
        h['population_est'] = population.get(h['district'], math.nan) * h['weight']/weights[h['district']]
        for kind in ('school','clinic'):
            distance = reachable[kind].get(h['graph_node'], math.inf) + h['snap_m']
            h[f'{kind}_min'] = distance/SPEED if math.isfinite(distance) else None
            h[f'{kind}_route_found'] = math.isfinite(distance)
            h[f'{kind}_status'] = ('unknown' if h['snap_m'] > MAX_SNAP or not math.isfinite(distance) else
                                    'within_10' if distance <= SPEED*10 else
                                    'within_15' if distance <= SPEED*15 else 'over_15')
    # Conservation check: unknown connections stay separate from uncovered homes.
    for district, total in population.items():
        assert abs(sum(h['population_est'] for h in buildings if h['district']==district)-total) < 1e-5
    summary = []
    for b in boundaries:
        homes = [h for h in buildings if h['district']==b['district']]
        for kind in ('school','clinic'):
            row={'district':b['district'], 'kind':kind, 'homes':len(homes), 'population':population.get(b['district'])}
            for status in ('within_10','within_15','over_15','unknown'):
                selected=[h for h in homes if h[f'{kind}_status']==status]
                row[f'homes_{status}']=len(selected)
                row[f'people_est_{status}']=round(sum(h['population_est'] for h in selected)) if population else None
            row['over_15_pct_homes']=round(100*row['homes_over_15']/len(homes),1)
            summary.append(row)
    summary.sort(key=lambda r: (r['kind'], -(r['people_est_over_15'] or r['homes_over_15'])))
    sensitivity=[]
    for b in boundaries:
        homes=[h for h in buildings if h['district']==b['district']]
        for kind in ('school','clinic'):
            for speed in (4,5):
                selected=[h for h in homes if h[f'{kind}_status']!='unknown' and h[f'{kind}_min']*5/speed>15]
                sensitivity.append({'district':b['district'],'kind':kind,'walking_kmh':speed,
                                    'homes_over_15':len(selected),
                                    'people_est_over_15':round(sum(h['population_est'] for h in selected))})
    with (OUT/'speed_sensitivity.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sensitivity[0]); writer.writeheader(); writer.writerows(sensitivity)
    with (OUT/'district_deficit.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=summary[0]); writer.writeheader(); writer.writerows(summary)
    gpkg=DATA/'accessibility.gpkg'
    if gpkg.exists(): gpkg.unlink()
    for rows,name in [(boundaries,'districts'),(parks,'parks'),(water,'water'),(iso,'isochrones')]:
        write_layer(rows,name,gpkg)
    home_rows=[{k:v for k,v in h.items() if k not in {'refs','point','graph_node'}} for h in buildings]
    facility_rows=[{k:v for k,v in f.items() if k not in {'refs','graph_node','geometry','point'}} | {'geometry':f['point']} for f in facilities]
    write_layer(home_rows,'homes',gpkg)
    write_layer(facility_rows,'facilities',gpkg)
    records_gdf(home_rows).drop(columns='geometry').to_csv(OUT/'building_accessibility.csv',index=False,encoding='utf-8-sig')
    records_gdf(facility_rows).drop(columns='geometry').to_csv(OUT/'facilities_review.csv',index=False,encoding='utf-8-sig')
    roads=[{'geometry':line.intersection(study)} for _,_,line in original_edges if line.intersects(study)]
    write_layer(roads,'walk_network',gpkg)
    write_layer([h for h in home_rows if h['school_status']=='over_15'],'school_white_spots',gpkg)
    audit={'status':'preliminary_osm_not_validated_against_data_mos',
           'walking_kmh':5, 'max_connector_m':MAX_SNAP, 'crs':CRS,
           'graph_nodes':len(graph), 'graph_edges':graph.number_of_edges(),
           'connected_components':nx.number_connected_components(graph),
           'residential_buildings':len(buildings), 'facilities':len(facilities),
           'facilities_by_kind':{k:sum(f['kind']==k for f in facilities) for k in ('school','clinic')},
           'facilities_unconnected':sum(f['snap_m']>MAX_SNAP for f in facilities),
           'home_floor_imputed':sum(h['floor_imputed'] for h in buildings),
           'home_entry_proxy':sum(h['entry_method']!='osm_entrance' for h in buildings),
           'homes_disconnected_by_kind':{k:sum(not h[f'{k}_route_found'] for h in buildings) for k in ('school','clinic')},
           'incomplete_ways_skipped':missing_ways, 'incomplete_multipolygons_skipped':incomplete_relations,
           'population_source_available':bool(population),
           'population_provenance':'secondary_wikipedia_citing_rosstat_not_primary_verified', 'summary':summary,
           'speed_sensitivity':sensitivity}
    (OUT/'quality_report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    make_maps(boundaries,home_rows,facility_rows,roads,parks,water,iso)
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)


def make_maps(boundaries,homes,facilities,roads,parks,water,iso):
    from plot import render
    render()


if __name__=='__main__':
    main()
