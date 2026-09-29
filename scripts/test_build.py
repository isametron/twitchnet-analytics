"""Build the network from collected streamers and print structure stats, e.g. to compare modes:

  python scripts/test_build.py --mode attribute
  python scripts/test_build.py --mode real
"""
import argparse
import json
import os
import sys

import community as community_louvain
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from twitchnet.config import Config  # noqa: E402
from twitchnet.database import DatabaseManager  # noqa: E402
from twitchnet.graph_builder import NETWORK_MODES, StreamerNetworkBuilder  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=NETWORK_MODES, default='attribute')
args = parser.parse_args()

db = DatabaseManager()
json_path = f"{Config.RAW_DATA_DIR}/streamers.json"
if os.path.exists(json_path):
    with open(json_path, "r", encoding='utf-8') as f:
        streamers = json.load(f)
    print(f"Loaded {len(streamers)} streamers from json")
else:
    streamers = db.load_streamers()
    print(f"Loaded {len(streamers)} streamers from the database")

b = StreamerNetworkBuilder()
b.add_streamers(streamers)
b.build_comprehensive_network(mode=args.mode, db=db)
graph = b.graph

connected = [n for n in graph if graph.degree(n) > 0]
partition = community_louvain.best_partition(graph, random_state=42) if graph.number_of_edges() else {}
print(f"Mode: {args.mode}")
print(f"Nodes: {graph.number_of_nodes()} ({len(connected)} with at least one edge)")
print(f"Edges: {graph.number_of_edges()}")
print(f"Density: {nx.density(graph):.4f}")
if partition:
    print(f"Communities: {len(set(partition.values()))}")
    print(f"Modularity: {community_louvain.modularity(partition, graph):.4f}")
