import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze import walkable, connect_points, service_lines
from shapely.geometry import Point, LineString
import networkx as nx

class NetworkTests(unittest.TestCase):
    def test_access_rules(self):
        self.assertFalse(walkable({'highway':'motorway'}))
        self.assertFalse(walkable({'highway':'path','access':'private'}))
        self.assertTrue(walkable({'highway':'path','access':'private','foot':'yes'}))
        self.assertFalse(walkable({'highway':'cycleway'}))
        self.assertFalse(walkable({'highway':'primary','foot':'use_sidepath'}))

    def test_edge_splitting_keeps_network_distance(self):
        graph=nx.Graph()
        graph.add_node(1,x=0,y=0); graph.add_node(2,x=100,y=0)
        line=LineString([(0,0),(100,0)])
        graph.add_edge(1,2,length=100,geometry=line)
        objects=[{'point':Point(20,10)},{'point':Point(80,5)}]
        connect_points(graph,[(1,2,line)],objects)
        distance=nx.shortest_path_length(graph,objects[0]['graph_node'],objects[1]['graph_node'],weight='length')
        self.assertAlmostEqual(distance+sum(o['snap_m'] for o in objects),75)
        self.assertAlmostEqual(sum(e['length'] for _,_,e in graph.edges(data=True)),100)

    def test_partial_edge_is_interpolated(self):
        graph=nx.Graph()
        graph.add_node(1,x=0,y=0); graph.add_node(2,x=100,y=0)
        graph.add_edge(1,2,length=100,geometry=LineString([(100,0),(0,0)]))
        lines=service_lines(graph,{1:0,2:100},25)
        self.assertEqual(len(lines),1)
        self.assertAlmostEqual(lines[0].length,25)
        self.assertEqual(tuple(lines[0].coords[-1]),(25,0))

    def test_disconnected_is_not_zero_time(self):
        graph=nx.Graph()
        for i,x in [(1,0),(2,100),(3,300),(4,400)]: graph.add_node(i,x=x,y=0)
        graph.add_edge(1,2,length=100,geometry=LineString([(0,0),(100,0)]))
        graph.add_edge(3,4,length=100,geometry=LineString([(300,0),(400,0)]))
        distances=nx.single_source_dijkstra_path_length(graph,1,weight='length')
        self.assertNotIn(3,distances)
        self.assertAlmostEqual(sum(l.length for l in service_lines(graph,distances,50)),50)

if __name__=='__main__': unittest.main()
