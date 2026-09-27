import networkx as nx
import pandas as pd
import pickle
from typing import List, Dict
from config import Config

class StreamerNetworkBuilder:
    """Build and manage streamer network graphs"""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.streamer_data = {}
    
    def add_streamers(self, streamers: List[Dict]):
        """
        Add streamers as nodes to the graph
        
        Args:
            streamers: List of streamer data dictionaries
        """
        for streamer in streamers:
            user_id = streamer['user_id']
            self.graph.add_node(user_id, **streamer)
            self.streamer_data[user_id] = streamer
        
        print(f"Added {len(streamers)} nodes to network graph")
    
    def add_edges_from_shared_games(self, weight_by_audience: bool = True):
        """
        Create edges between streamers who play the same games
        Edge weight based on game overlap and optionally audience size
        
        Args:
            weight_by_audience: If True, weight edges by combined audience reach
        """
        nodes = list(self.graph.nodes(data=True))
        edges_added = 0
        
        for i, (node1, data1) in enumerate(nodes):
            for node2, data2 in nodes[i+1:]:
                # Calculate game similarity
                game1 = data1.get('game_name', '')
                game2 = data2.get('game_name', '')
                
                if game1 and game2 and game1 == game2:
                    # Base weight for same game
                    weight = 1.0

                    if weight_by_audience:
                        # Factor in audience size for influence-based connections
                        followers1 = data1.get('follower_count', 0)
                        followers2 = data2.get('follower_count', 0)

                        # Normalize and add bonus (0.0 to 2.0 range)
                        audience_factor = min(2.0, (followers1 + followers2) / 100000)
                        weight = 1.0 + (audience_factor * 0.5)

                    if self.graph.has_edge(node1, node2):
                        self.graph[node1][node2]['weight'] += weight
                        # preserve or extend types set
                        types = self.graph[node1][node2].get('types') or set()
                        if isinstance(types, (list, tuple)):
                            types = set(types)
                        types.add('same_game')
                        self.graph[node1][node2]['types'] = types
                    else:
                        self.graph.add_edge(node1, node2, weight=weight, types={'same_game'})
                        edges_added += 1
        
        print(f"Added {edges_added} edges based on game similarity" + 
              (" (weighted by audience)" if weight_by_audience else ""))
    
    def add_edges_from_tags(self, similarity_threshold: float = 0.3):
        """
        Create edges based on shared tags
        
        Args:
            similarity_threshold: Minimum Jaccard similarity to create edge
        """
        nodes = list(self.graph.nodes(data=True))
        
        for i, (node1, data1) in enumerate(nodes):
            tags1 = set(data1.get('tags', []))
            
            for node2, data2 in nodes[i+1:]:
                tags2 = set(data2.get('tags', []))
                
                if tags1 and tags2:
                    # Jaccard similarity
                    intersection = len(tags1.intersection(tags2))
                    union = len(tags1.union(tags2))
                    similarity = intersection / union if union > 0 else 0
                    
                    if similarity >= similarity_threshold:
                        if self.graph.has_edge(node1, node2):
                            self.graph[node1][node2]['weight'] += similarity
                            types = self.graph[node1][node2].get('types') or set()
                            if isinstance(types, (list, tuple)):
                                types = set(types)
                            types.add('similar_tags')
                            self.graph[node1][node2]['types'] = types
                        else:
                            self.graph.add_edge(node1, node2, weight=similarity, types={'similar_tags'})
        
        print(f"Total edges after tag analysis: {self.graph.number_of_edges()}")
    
    def add_edges_from_language(self, same_language_weight: float = 0.5):
        """
        Create edges between streamers with the same language
        
        Args:
            same_language_weight: Weight for same language connections
        """
        nodes = list(self.graph.nodes(data=True))
        edges_added = 0
        
        for i, (node1, data1) in enumerate(nodes):
            lang1 = data1.get('language', 'unknown')
            
            for node2, data2 in nodes[i+1:]:
                lang2 = data2.get('language', 'unknown')
                
                if lang1 and lang2 and lang1 == lang2 and lang1 != 'unknown':
                    # Check if edge already exists
                    if self.graph.has_edge(node1, node2):
                        # Strengthen existing edge
                        self.graph[node1][node2]['weight'] += same_language_weight
                        types = self.graph[node1][node2].get('types') or set()
                        if isinstance(types, (list, tuple)):
                            types = set(types)
                        types.add('same_language')
                        self.graph[node1][node2]['types'] = types
                    else:
                        self.graph.add_edge(node1, node2, weight=same_language_weight, types={'same_language'})
                        edges_added += 1
        
        print(f"Added {edges_added} new edges based on language similarity")
    
    def add_edges_from_partner_status(self, partner_weight: float = 0.8):
        """
        Create edges between partner streamers (they're in similar tier)
        
        Args:
            partner_weight: Weight for partner-to-partner connections
        """
        nodes = list(self.graph.nodes(data=True))
        edges_added = 0

        for i, (node1, data1) in enumerate(nodes):
            is_partner1 = data1.get('is_partner', False)

            if not is_partner1:
                continue

            for node2, data2 in nodes[i+1:]:
                is_partner2 = data2.get('is_partner', False)

                if is_partner2:
                    # Both are partners
                    if self.graph.has_edge(node1, node2):
                        self.graph[node1][node2]['weight'] += partner_weight
                        types = self.graph[node1][node2].get('types') or set()
                        if isinstance(types, (list, tuple)):
                            types = set(types)
                        types.add('both_partners')
                        self.graph[node1][node2]['types'] = types
                    else:
                        self.graph.add_edge(node1, node2, weight=partner_weight, types={'both_partners'})
                        edges_added += 1

        print(f"Added {edges_added} new edges based on partner status")

    def add_edges_from_viewer_tier(self, tier_threshold: int = 50000):
        """
        Create edges between streamers in similar viewer tiers

        Args:
            tier_threshold: Follower count difference threshold for same tier
        """
        nodes = list(self.graph.nodes(data=True))
        edges_added = 0

        for i, (node1, data1) in enumerate(nodes):
            followers1 = data1.get('follower_count', 0)

            for node2, data2 in nodes[i+1:]:
                followers2 = data2.get('follower_count', 0)

                # If they're in similar follower tiers
                follower_diff = abs(followers1 - followers2)
                if follower_diff < tier_threshold:
                    tier_similarity = 1.0 - (follower_diff / tier_threshold)
                    weight = tier_similarity * 0.6

                    if self.graph.has_edge(node1, node2):
                        self.graph[node1][node2]['weight'] += weight
                        types = self.graph[node1][node2].get('types') or set()
                        if isinstance(types, (list, tuple)):
                            types = set(types)
                        types.add('same_tier')
                        self.graph[node1][node2]['types'] = types
                    else:
                        self.graph.add_edge(node1, node2, weight=weight, types={'same_tier'})
                        edges_added += 1

        print(f"Added {edges_added} new edges based on viewer tier similarity")
    
    def build_comprehensive_network(self, use_all_methods: bool = True, weight_by_audience: bool = True):
        """
        Build a comprehensive network using all available edge creation methods
        
        Args:
            use_all_methods: If True, uses all edge creation methods
            weight_by_audience: If True, weight same-game edges by combined audience reach
        """
        print("\nBuilding comprehensive network...")
        
        # Core connections
        self.add_edges_from_shared_games(weight_by_audience=weight_by_audience)
        
        if use_all_methods:
            self.add_edges_from_tags(similarity_threshold=0.3)
            self.add_edges_from_language(same_language_weight=0.5)
            self.add_edges_from_partner_status(partner_weight=0.8)
            self.add_edges_from_viewer_tier(tier_threshold=50000)
        
        print(f"Network built with {self.graph.number_of_edges()} total edges\n")
    
    def add_edges_from_external_data(self, edge_list: List[tuple]):
        """
        Add edges from external data (e.g., SNAP dataset)
        
        Args:
            edge_list: List of tuples (source, target, weight)
        """
        for edge in edge_list:
            if len(edge) == 2:
                self.graph.add_edge(edge[0], edge[1], weight=1.0)
            else:
                self.graph.add_edge(edge[0], edge[1], weight=edge[2])
        
        print(f"Added {len(edge_list)} edges from external data")
    
    def load_snap_dataset(self, edges_file: str, features_file: str = None):
        """
        Load SNAP Twitch dataset
        
        Args:
            edges_file: Path to edges CSV file
            features_file: Path to features CSV file (optional)
        """
        try:
            # Load edges
            edges_df = pd.read_csv(edges_file)
            edge_list = list(edges_df.itertuples(index=False, name=None))
            self.add_edges_from_external_data(edge_list)
            
            # Load features if provided
            if features_file:
                features_df = pd.read_csv(features_file)
                for _, row in features_df.iterrows():
                    node_id = str(row['node_id'])
                    node_attrs = row.to_dict()
                    if node_id in self.graph:
                        self.graph.nodes[node_id].update(node_attrs)
            
            print("SNAP dataset loaded successfully")
        except Exception as e:
            print(f"Error loading SNAP dataset: {e}")
    
    def get_graph_stats(self) -> Dict:
        """Get basic statistics about the network"""
        stats = {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'is_connected': nx.is_connected(self.graph)
        }
        
        if stats['is_connected']:
            stats['diameter'] = nx.diameter(self.graph)
            stats['avg_shortest_path'] = nx.average_shortest_path_length(self.graph)
        else:
            # Get largest connected component
            largest_cc = max(nx.connected_components(self.graph), key=len)
            stats['largest_component_size'] = len(largest_cc)
        
        return stats
    
    def save_graph(self, filename: str = 'streamer_network.gpickle'):
        """Save graph to file"""
        filepath = f"{Config.NETWORK_GRAPHS_DIR}/{filename}"
        with open(filepath, 'wb') as f:
            pickle.dump(self.graph, f, pickle.HIGHEST_PROTOCOL)
        print(f"Graph saved to {filepath}")
    
    def load_graph(self, filename: str = 'streamer_network.gpickle'):
        """Load graph from file"""
        filepath = f"{Config.NETWORK_GRAPHS_DIR}/{filename}"
        with open(filepath, 'rb') as f:
            self.graph = pickle.load(f)
        print(f"Graph loaded from {filepath}")
    
    def export_to_csv(self, nodes_file: str = 'nodes.csv', edges_file: str = 'edges.csv'):
        """Export graph to CSV files"""
        # Export nodes
        nodes_data = []
        for node, attrs in self.graph.nodes(data=True):
            node_dict = {'node_id': node}
            node_dict.update(attrs)
            nodes_data.append(node_dict)
        
        nodes_df = pd.DataFrame(nodes_data)
        nodes_df.to_csv(f"{Config.PROCESSED_DATA_DIR}/{nodes_file}", index=False)
        
        # Export edges
        edges_data = []
        for u, v, attrs in self.graph.edges(data=True):
            edge_dict = {'source': u, 'target': v}
            edge_dict.update(attrs)
            edges_data.append(edge_dict)
        
        edges_df = pd.DataFrame(edges_data)
        edges_df.to_csv(f"{Config.PROCESSED_DATA_DIR}/{edges_file}", index=False)
        
        print("Graph exported to CSV files")


if __name__ == "__main__":
    builder = StreamerNetworkBuilder()
    
    # Example: Load streamers from JSON
    import json
    with open(f"{Config.RAW_DATA_DIR}/streamers.json", 'r') as f:
        streamers = json.load(f)
    
    builder.add_streamers(streamers)
    builder.add_edges_from_shared_games()
    builder.add_edges_from_tags()
    
    stats = builder.get_graph_stats()
    print("\nNetwork Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    builder.save_graph()
