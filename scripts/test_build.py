from graph_builder import StreamerNetworkBuilder
import json
from config import Config

with open(f"{Config.RAW_DATA_DIR}/streamers.json","r",encoding='utf-8') as f:
    streamers = json.load(f)

print(f"Loaded {len(streamers)} streamers from json")

b = StreamerNetworkBuilder()
b.add_streamers(streamers)
b.build_comprehensive_network()
stats = b.get_graph_stats()
print('Graph stats:', stats)
