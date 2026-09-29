from typing import Dict

import networkx as nx
import pandas as pd

from twitchnet.config import Config


class CentralityAnalyzer:
    """Calculate and analyze network centrality measures"""

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.centrality_scores = {}

    def calculate_all_centralities(self, include_advanced: bool = True):
        """
        Calculate all centrality measures

        Args:
            include_advanced: If True, calculate advanced metrics (slower but more comprehensive)
        """
        print("🔢 Calculating centrality measures...")

        # Basic centrality measures
        self.centrality_scores['degree'] = nx.degree_centrality(self.graph)
        print("  ✓ Degree centrality calculated")

        self.centrality_scores['betweenness'] = nx.betweenness_centrality(
            self.graph, normalized=True
        )
        print("  ✓ Betweenness centrality calculated")

        self.centrality_scores['closeness'] = nx.closeness_centrality(self.graph)
        print("  ✓ Closeness centrality calculated")

        # Eigenvector centrality (may fail on disconnected graphs)
        try:
            self.centrality_scores['eigenvector'] = nx.eigenvector_centrality(
                self.graph, max_iter=1000
            )
            print("  ✓ Eigenvector centrality calculated")
        except Exception:
            print("  ⚠ Eigenvector centrality failed (disconnected graph)")
            self.centrality_scores['eigenvector'] = {node: 0 for node in self.graph.nodes()}

        self.centrality_scores['pagerank'] = nx.pagerank(self.graph)
        print("  ✓ PageRank calculated")

        if include_advanced:
            # Harmonic centrality (works better with disconnected graphs)
            self.centrality_scores['harmonic'] = nx.harmonic_centrality(self.graph)
            print("  ✓ Harmonic centrality calculated")

            # Load centrality (identifies bottlenecks)
            self.centrality_scores['load'] = nx.load_centrality(self.graph)
            print("  ✓ Load centrality calculated")

            # Clustering coefficient (measures local connectivity)
            self.centrality_scores['clustering'] = nx.clustering(self.graph)
            print("  ✓ Clustering coefficient calculated")

        print("✅ All centrality measures calculated\n")
        return self.centrality_scores

    def calculate_influence_score(self) -> Dict:
        """
        Calculate composite influence score combining multiple metrics

        Returns:
            Dictionary of node_id -> influence_score
        """
        influence_scores = {}

        # Weights for different metrics
        weights = {
            'pagerank': 0.3,
            'degree': 0.2,
            'betweenness': 0.2,
            'eigenvector': 0.15,
            'closeness': 0.15
        }

        for node in self.graph.nodes():
            score = 0
            for metric, weight in weights.items():
                if metric in self.centrality_scores:
                    score += self.centrality_scores[metric].get(node, 0) * weight

            # Bonus for partner status and follower count
            node_data = self.graph.nodes[node]
            if node_data.get('is_partner', False):
                score *= 1.2

            followers = node_data.get('follower_count', 0)
            follower_bonus = min(0.3, followers / 1000000)  # Cap at 0.3 for 1M+ followers
            score += follower_bonus

            influence_scores[node] = score

        self.centrality_scores['influence'] = influence_scores
        print("✨ Composite influence score calculated")
        return influence_scores

    def get_top_influencers(self, metric: str = 'pagerank', top_n: int = 10) -> list:
        """
        Get top influencers based on centrality metric

        Args:
            metric: Centrality metric to use
            top_n: Number of top influencers to return

        Returns:
            List of (node_id, score) tuples
        """
        if metric not in self.centrality_scores:
            print(f"Metric '{metric}' not calculated. Run calculate_all_centralities() first.")
            return []

        scores = self.centrality_scores[metric]
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_n]

    def get_centrality_dataframe(self) -> pd.DataFrame:
        """Convert centrality scores to DataFrame"""
        df_data = []

        for node in self.graph.nodes():
            node_data = {'node_id': node}
            node_data.update(self.graph.nodes[node])

            for metric, scores in self.centrality_scores.items():
                node_data[f'{metric}_centrality'] = scores.get(node, 0)

            df_data.append(node_data)

        return pd.DataFrame(df_data)

    def identify_niche_influencers(self, game_category: str, metric: str = 'pagerank', top_n: int = 5):
        """
        Find top influencers within a specific game category niche

        Args:
            game_category: Game category to filter by
            metric: Centrality metric to use
            top_n: Number of influencers to return

        Returns:
            List of top influencers in the niche
        """
        # Filter nodes by game category
        niche_nodes = [
            node for node, data in self.graph.nodes(data=True)
            if data.get('game_name') == game_category
        ]

        if not niche_nodes:
            print(f"No streamers found for game: {game_category}")
            return []

        # Create subgraph
        subgraph = self.graph.subgraph(niche_nodes)

        # Calculate centrality on subgraph
        if metric == 'degree':
            scores = nx.degree_centrality(subgraph)
        elif metric == 'betweenness':
            scores = nx.betweenness_centrality(subgraph)
        elif metric == 'pagerank':
            scores = nx.pagerank(subgraph)
        else:
            scores = self.centrality_scores.get(metric, {})

        # Get top influencers
        filtered_scores = {k: v for k, v in scores.items() if k in niche_nodes}
        sorted_scores = sorted(filtered_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_scores[:top_n]

    def save_centrality_scores(self, filename: str = 'centrality_scores.csv'):
        """Save centrality scores to CSV"""
        df = self.get_centrality_dataframe()
        filepath = f"{Config.PROCESSED_DATA_DIR}/{filename}"
        df.to_csv(filepath, index=False)
        print(f"Centrality scores saved to {filepath}")


if __name__ == "__main__":
    from twitchnet.graph_builder import StreamerNetworkBuilder
    # Load existing graph
    builder = StreamerNetworkBuilder()
    builder.load_graph()

    # Calculate centralities
    analyzer = CentralityAnalyzer(builder.graph)
    analyzer.calculate_all_centralities()

    # Get top influencers
    print("\nTop 10 Influencers (PageRank):")
    top_influencers = analyzer.get_top_influencers('pagerank', 10)
    for i, (node, score) in enumerate(top_influencers, 1):
        node_data = builder.graph.nodes[node]
        print(f"{i}. {node_data.get('display_name', node)} - Score: {score:.4f}")

    # Save results
    analyzer.save_centrality_scores()
