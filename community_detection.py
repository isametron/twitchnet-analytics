import networkx as nx
import community as community_louvain
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from typing import Dict, List, Optional
from datetime import datetime
import json
from config import Config

class CommunityDetector:
    """Detect and analyze communities in the streamer network"""
    
    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.communities = {}
        self.partition = {}
        self.temporal_snapshots = []  # Store historical community states
        self.bridge_nodes = []  # Streamers connecting multiple communities
    
    def detect_communities_louvain(self):
        """Detect communities using Louvain method"""
        print("Detecting communities using Louvain method...")
        self.partition = community_louvain.best_partition(self.graph)
        
        # Organize by community
        self.communities = defaultdict(list)
        for node, comm_id in self.partition.items():
            self.communities[comm_id].append(node)
        
        print(f"Found {len(self.communities)} communities")
        return self.communities
    
    def get_community_stats(self) -> pd.DataFrame:
        """Get statistics for each community"""
        stats = []
        
        for comm_id, members in self.communities.items():
            subgraph = self.graph.subgraph(members)
            
            # Get game distribution in community
            games = [self.graph.nodes[node].get('game_name', 'Unknown') 
                    for node in members]
            game_counts = pd.Series(games).value_counts()
            top_game = game_counts.index[0] if len(game_counts) > 0 else 'Unknown'
            
            # Get language distribution
            languages = [self.graph.nodes[node].get('language', 'Unknown') 
                        for node in members]
            lang_counts = pd.Series(languages).value_counts()
            top_language = lang_counts.index[0] if len(lang_counts) > 0 else 'Unknown'
            
            # Calculate average followers
            followers = [self.graph.nodes[node].get('follower_count', 0) 
                        for node in members]
            avg_followers = sum(followers) / len(followers) if followers else 0
            
            stats.append({
                'community_id': comm_id,
                'size': len(members),
                'density': nx.density(subgraph),
                'top_game': top_game,
                'top_language': top_language,
                'avg_followers': avg_followers
            })
        
        return pd.DataFrame(stats).sort_values('size', ascending=False)
    
    def detect_cross_game_communities(self) -> Dict[str, List[int]]:
        """
        Find streamers who bridge multiple game communities
        
        Returns:
            Dictionary mapping game pairs to bridge community IDs
        """
        cross_game_comms = defaultdict(list)
        
        for comm_id, members in self.communities.items():
            # Get games played in this community
            games = [self.graph.nodes[node].get('game_name', 'Unknown') 
                    for node in members]
            game_counts = Counter(games)
            
            # If community has significant presence (>20%) in multiple games
            total = len(members)
            significant_games = [game for game, count in game_counts.items() 
                               if count / total > 0.2 and game != 'Unknown']
            
            if len(significant_games) >= 2:
                game_pair = tuple(sorted(significant_games[:2]))
                cross_game_comms[f"{game_pair[0]} ↔ {game_pair[1]}"].append(comm_id)
        
        print(f"Found {len(cross_game_comms)} cross-game community bridges")
        return dict(cross_game_comms)
    
    def identify_bridge_nodes(self, min_communities: int = 2) -> List[Dict]:
        """
        Find streamers who connect multiple communities (bridge nodes)
        
        Args:
            min_communities: Minimum number of communities to connect
        
        Returns:
            List of bridge node data with influence metrics
        """
        bridges = []
        
        for node in self.graph.nodes():
            # Get neighbors and their communities
            neighbors = list(self.graph.neighbors(node))
            neighbor_communities = [self.partition.get(n) for n in neighbors]
            unique_comms = set(neighbor_communities)
            
            if len(unique_comms) >= min_communities:
                node_data = self.graph.nodes[node]
                bridges.append({
                    'node': node,
                    'display_name': node_data.get('display_name', node),
                    'primary_community': self.partition.get(node),
                    'connected_communities': len(unique_comms),
                    'bridge_score': len(unique_comms) * node_data.get('follower_count', 0) / 1000,
                    'follower_count': node_data.get('follower_count', 0)
                })
        
        bridges.sort(key=lambda x: x['bridge_score'], reverse=True)
        print(f"Found {len(bridges)} bridge nodes connecting multiple communities")
        return bridges
    
    def get_niche_communities(self, min_size: int = 5, max_size: int = 100) -> List[int]:
        """
        Identify niche communities of appropriate size
        
        Args:
            min_size: Minimum community size
            max_size: Maximum community size
        
        Returns:
            List of community IDs
        """
        niche_comms = [
            comm_id for comm_id, members in self.communities.items()
            if min_size <= len(members) <= max_size
        ]
        
        print(f"Found {len(niche_comms)} niche communities")
        return niche_comms
    
    def calculate_community_health(self, community_id: int) -> Dict:
        """
        Calculate comprehensive health metrics for a community
        
        Args:
            community_id: ID of the community to analyze
        
        Returns:
            Dictionary with health metrics
        """
        members = self.communities.get(community_id, [])
        if not members:
            return {}
        
        subgraph = self.graph.subgraph(members)
        
        # Diversity metrics
        games = [self.graph.nodes[node].get('game_name', 'Unknown') for node in members]
        languages = [self.graph.nodes[node].get('language', 'Unknown') for node in members]
        game_diversity = len(set(games)) / len(games) if games else 0
        language_diversity = len(set(languages)) / len(languages) if languages else 0
        
        # Engagement metrics
        followers = [self.graph.nodes[node].get('follower_count', 0) for node in members]
        avg_followers = np.mean(followers) if followers else 0
        follower_std = np.std(followers) if len(followers) > 1 else 0
        
        # Network metrics
        density = nx.density(subgraph)
        try:
            avg_clustering = nx.average_clustering(subgraph)
        except Exception:
            avg_clustering = 0
        
        # Activity metrics (based on partner status as proxy for activity)
        partners = [self.graph.nodes[node].get('is_partner', False) for node in members]
        partner_ratio = sum(partners) / len(partners) if partners else 0
        
        # Overall health score (0-100)
        health_score = (
            game_diversity * 20 +
            language_diversity * 15 +
            min(density * 100, 20) +
            min(avg_clustering * 100, 20) +
            partner_ratio * 25
        )
        
        return {
            'community_id': community_id,
            'size': len(members),
            'health_score': round(health_score, 2),
            'game_diversity': round(game_diversity, 3),
            'language_diversity': round(language_diversity, 3),
            'network_density': round(density, 3),
            'avg_clustering': round(avg_clustering, 3),
            'partner_ratio': round(partner_ratio, 3),
            'avg_followers': round(avg_followers, 0),
            'follower_std': round(follower_std, 0)
        }
    
    def get_all_health_metrics(self) -> pd.DataFrame:
        """Calculate health metrics for all communities"""
        health_data = []
        for comm_id in self.communities.keys():
            health = self.calculate_community_health(comm_id)
            if health:
                health_data.append(health)
        
        return pd.DataFrame(health_data).sort_values('health_score', ascending=False)
    
    def save_temporal_snapshot(self, timestamp: Optional[str] = None):
        """
        Save current community state as temporal snapshot
        
        Args:
            timestamp: Optional timestamp string, defaults to current time
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        snapshot = {
            'timestamp': timestamp,
            'partition': self.partition.copy(),
            'num_communities': len(self.communities),
            'total_nodes': len(self.graph.nodes())
        }
        
        self.temporal_snapshots.append(snapshot)
        print(f"Saved snapshot at {timestamp} with {len(self.communities)} communities")
        
        # Save to disk
        snapshot_file = f"{Config.PROCESSED_DATA_DIR}/community_snapshot_{timestamp.replace(':', '-')}.json"
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f)
    
    def analyze_community_evolution(self) -> pd.DataFrame:
        """
        Analyze how communities have evolved over time
        
        Returns:
            DataFrame with evolution metrics
        """
        if len(self.temporal_snapshots) < 2:
            print("Need at least 2 snapshots for evolution analysis")
            return pd.DataFrame()
        
        evolution_data = []
        
        for i in range(1, len(self.temporal_snapshots)):
            prev = self.temporal_snapshots[i-1]
            curr = self.temporal_snapshots[i]
            
            # Calculate membership changes
            prev_partition = prev['partition']
            curr_partition = curr['partition']
            
            # Find nodes that changed communities
            changed_nodes = sum(1 for node in prev_partition 
                              if node in curr_partition and 
                              prev_partition[node] != curr_partition[node])
            
            evolution_data.append({
                'from_timestamp': prev['timestamp'],
                'to_timestamp': curr['timestamp'],
                'communities_before': prev['num_communities'],
                'communities_after': curr['num_communities'],
                'nodes_changed': changed_nodes,
                'stability_score': 1 - (changed_nodes / prev['total_nodes'])
            })
        
        return pd.DataFrame(evolution_data)
    
    def simulate_influence_propagation(self, seed_nodes: List[str], iterations: int = 10, 
                                      propagation_rate: float = 0.3) -> Dict:
        """
        Simulate how influence/trends spread through the network
        
        Args:
            seed_nodes: Initial nodes where trend starts
            iterations: Number of propagation steps
            propagation_rate: Probability of influence spreading to neighbor
        
        Returns:
            Dictionary with propagation metrics and timeline
        """
        influenced = set(seed_nodes)
        timeline = [{'iteration': 0, 'influenced_count': len(seed_nodes)}]
        
        for iteration in range(1, iterations + 1):
            new_influenced = set()
            
            for node in influenced:
                if node not in self.graph:
                    continue
                    
                neighbors = list(self.graph.neighbors(node))
                for neighbor in neighbors:
                    if neighbor not in influenced:
                        # Weight by edge strength and follower count
                        edge_weight = self.graph[node][neighbor].get('weight', 1)
                        follower_factor = self.graph.nodes[neighbor].get('follower_count', 1000) / 10000
                        influence_prob = propagation_rate * edge_weight * min(follower_factor, 1)
                        
                        if np.random.random() < influence_prob:
                            new_influenced.add(neighbor)
            
            influenced.update(new_influenced)
            timeline.append({
                'iteration': iteration,
                'influenced_count': len(influenced),
                'new_this_round': len(new_influenced)
            })
            
            if len(new_influenced) == 0:
                print(f"Propagation stopped at iteration {iteration}")
                break
        
        # Analyze which communities were most affected
        community_spread = defaultdict(int)
        for node in influenced:
            if node in self.partition:
                community_spread[self.partition[node]] += 1
        
        return {
            'total_influenced': len(influenced),
            'propagation_rate_actual': len(influenced) / len(self.graph.nodes()),
            'iterations_to_complete': len(timeline) - 1,
            'timeline': timeline,
            'influenced_nodes': list(influenced),
            'community_spread': dict(community_spread)
        }
    
    def get_community_members(self, community_id: int) -> List[str]:
        """Get all members of a specific community"""
        return self.communities.get(community_id, [])
    
    def export_communities(self, filename: str = 'communities.csv'):
        """Export community assignments to CSV"""
        data = []
        for node, comm_id in self.partition.items():
            node_data = self.graph.nodes[node]
            data.append({
                'node_id': node,
                'community_id': comm_id,
                'display_name': node_data.get('display_name', ''),
                'game_name': node_data.get('game_name', ''),
                'follower_count': node_data.get('follower_count', 0)
            })
        
        df = pd.DataFrame(data)
        filepath = f"{Config.PROCESSED_DATA_DIR}/{filename}"
        df.to_csv(filepath, index=False)
        print(f"Community assignments saved to {filepath}")


if __name__ == "__main__":
    from graph_builder import StreamerNetworkBuilder
    # Load graph
    builder = StreamerNetworkBuilder()
    builder.load_graph()
    
    # Detect communities
    detector = CommunityDetector(builder.graph)
    communities = detector.detect_communities_louvain()
    
    # Get statistics
    stats_df = detector.get_community_stats()
    print("\nCommunity Statistics:")
    print(stats_df.head(10))
    
    # Export
    detector.export_communities()
