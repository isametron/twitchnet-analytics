import networkx as nx
import pandas as pd
import pickle
from typing import List, Dict
from config import Config

NETWORK_MODES = ('attribute', 'real', 'hybrid')
HYBRID_ATTRIBUTE_WEIGHT = 0.2  # attribute edges count this much next to observed relationships in hybrid mode

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
    
    def _add_or_merge_edge(self, node1, node2, weight: float, edge_type: str, **attrs) -> bool:
        """Add an edge, or add weight and the edge type to an existing one. Returns True if the edge is new."""
        if self.graph.has_edge(node1, node2):
            edge = self.graph[node1][node2]
            edge['weight'] += weight
            types = edge.get('types') or set()
            if isinstance(types, (list, tuple)):
                types = set(types)
            types.add(edge_type)
            edge['types'] = types
            edge.update(attrs)
            return False
        self.graph.add_edge(node1, node2, weight=weight, types={edge_type}, **attrs)
        return True

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

                    if self._add_or_merge_edge(node1, node2, weight, 'same_game'):
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
                        self._add_or_merge_edge(node1, node2, similarity, 'similar_tags')

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
                    if self._add_or_merge_edge(node1, node2, same_language_weight, 'same_language'):
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
            if not data1.get('is_partner', False):
                continue

            for node2, data2 in nodes[i+1:]:
                if data2.get('is_partner', False):
                    if self._add_or_merge_edge(node1, node2, partner_weight, 'both_partners'):
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

                    if self._add_or_merge_edge(node1, node2, weight, 'same_tier'):
                        edges_added += 1

        print(f"Added {edges_added} new edges based on viewer tier similarity")

    # ---------- Real relationship edges (data collected by relations.py / tracker.py) ----------

    def add_edges_from_chat_overlap(self, db, min_shared: int = 5):
        """
        Connect streamers whose chats share chatters, weighted by the overlap coefficient
        |A ∩ B| / min(|A|, |B|) of their (hashed) chatter sets.

        Args:
            db: DatabaseManager with chat_presence data
            min_shared: Minimum number of shared chatters for an edge
        """
        rows = db.conn.execute('''
            WITH sizes AS (
                SELECT channel_id, COUNT(*) AS chatters FROM chat_presence GROUP BY channel_id
            ), shared AS (
                SELECT a.channel_id AS a_id, b.channel_id AS b_id, COUNT(*) AS shared
                FROM chat_presence a
                JOIN chat_presence b ON a.chatter_hash = b.chatter_hash AND a.channel_id < b.channel_id
                GROUP BY a.channel_id, b.channel_id
                HAVING COUNT(*) >= ?
            )
            SELECT shared.a_id, shared.b_id, shared.shared, MIN(sa.chatters, sb.chatters)
            FROM shared
            JOIN sizes sa ON sa.channel_id = shared.a_id
            JOIN sizes sb ON sb.channel_id = shared.b_id
        ''', (min_shared,)).fetchall()

        edges_added = 0
        for a_id, b_id, shared, smaller in rows:
            if a_id in self.graph and b_id in self.graph:
                overlap = shared / smaller
                if self._add_or_merge_edge(a_id, b_id, overlap, 'chat_overlap',
                                           shared_chatters=shared, chat_overlap=overlap):
                    edges_added += 1

        print(f"Added {edges_added} new edges based on chat audience overlap")

    def add_edges_from_raids(self, db):
        """
        Connect streamers who raided each other; weight is the number of raids.
        The 'raids' edge attribute maps each endpoint's id to how many raids it sent.
        """
        edges_added = 0
        counts = db.conn.execute(
            "SELECT from_id, to_id, COUNT(*) FROM raids GROUP BY from_id, to_id"
        ).fetchall()
        for from_id, to_id, count in counts:
            if from_id in self.graph and to_id in self.graph and from_id != to_id:
                is_new = self._add_or_merge_edge(from_id, to_id, float(count), 'raid')
                edge = self.graph[from_id][to_id]
                sent = dict(edge.get('raids') or {})
                sent[from_id] = sent.get(from_id, 0) + count
                edge['raids'] = sent
                edges_added += is_new

        print(f"Added {edges_added} new edges based on raids")

    def add_edges_from_teams(self, db, team_weight: float = 1.0):
        """Connect streamers who belong to the same Twitch team"""
        members_by_team = {}
        for row in db.load_team_members():
            if row['user_id'] in self.graph:
                members_by_team.setdefault(row['team_id'], []).append(row['user_id'])

        edges_added = 0
        for members in members_by_team.values():
            for i, node1 in enumerate(members):
                for node2 in members[i+1:]:
                    if self._add_or_merge_edge(node1, node2, team_weight, 'same_team'):
                        edges_added += 1

        print(f"Added {edges_added} new edges based on team membership")

    def add_edges_from_collabs(self, db):
        """Connect streamers who co-streamed (Shared Chat) or mentioned each other in titles"""
        edges_added = 0
        counts = db.conn.execute(
            "SELECT a_id, b_id, COUNT(*) FROM collabs GROUP BY a_id, b_id"
        ).fetchall()
        for a_id, b_id, count in counts:
            if a_id in self.graph and b_id in self.graph:
                if self._add_or_merge_edge(a_id, b_id, float(count), 'collab', collabs=count):
                    edges_added += 1

        print(f"Added {edges_added} new edges based on collaborations")

    def _add_attribute_edges(self, use_all_methods: bool, weight_by_audience: bool):
        """Edges inferred from shared attributes (game, tags, language, partner status, follower tier)"""
        self.add_edges_from_shared_games(weight_by_audience=weight_by_audience)

        if use_all_methods:
            self.add_edges_from_tags(similarity_threshold=0.3)
            self.add_edges_from_language(same_language_weight=0.5)
            self.add_edges_from_partner_status(partner_weight=0.8)
            self.add_edges_from_viewer_tier(tier_threshold=50000)

    def _add_relationship_edges(self, db):
        """Edges from observed relationships (chat overlap, raids, teams, collaborations)"""
        self.add_edges_from_chat_overlap(db)
        self.add_edges_from_raids(db)
        self.add_edges_from_teams(db)
        self.add_edges_from_collabs(db)

    def build_comprehensive_network(self, use_all_methods: bool = True, weight_by_audience: bool = True,
                                    mode: str = 'attribute', db=None):
        """
        Build a comprehensive network

        Args:
            use_all_methods: If True, uses all attribute edge methods (attribute and hybrid modes)
            weight_by_audience: If True, weight same-game edges by combined audience reach
            mode: 'attribute' - edges from shared attributes only
                  'real' - edges from observed relationships only (needs db)
                  'hybrid' - relationship edges plus attribute edges at HYBRID_ATTRIBUTE_WEIGHT
            db: DatabaseManager holding relationship data (for 'real' and 'hybrid')
        """
        if mode not in NETWORK_MODES:
            raise ValueError(f"mode must be one of {NETWORK_MODES}, got {mode!r}")
        if mode != 'attribute' and db is None:
            raise ValueError(f"mode {mode!r} needs a DatabaseManager (db=...)")

        print(f"\nBuilding comprehensive network ({mode} mode)...")

        if mode in ('attribute', 'hybrid'):
            self._add_attribute_edges(use_all_methods, weight_by_audience)
        if mode == 'hybrid':
            # Keep inferred edges as weak background ties next to the observed ones
            for _, _, attrs in self.graph.edges(data=True):
                attrs['weight'] *= HYBRID_ATTRIBUTE_WEIGHT
        if mode in ('real', 'hybrid'):
            self._add_relationship_edges(db)

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
