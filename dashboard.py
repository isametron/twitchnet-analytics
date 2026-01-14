"""
Dashboard metrics and components for real-time analytics
Provides pre-built metric cards, KPIs, and summary statistics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import networkx as nx
from collections import Counter, defaultdict


class DashboardMetrics:
    """Calculate and manage dashboard metrics"""
    
    def __init__(self, streamers_df: pd.DataFrame = None, graph: nx.Graph = None):
        self.streamers_df = streamers_df
        self.graph = graph
    
    def get_overview_metrics(self) -> Dict:
        """
        Get key overview metrics for dashboard
        
        Returns:
            Dictionary with key metrics
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {
                'total_streamers': 0,
                'avg_followers': 0,
                'total_followers': 0,
                'partner_count': 0,
                'partner_pct': 0,
                'avg_language_diversity': 0
            }
        
        df = self.streamers_df
        
        metrics = {
            'total_streamers': len(df),
            'avg_followers': df['follower_count'].mean(),
            'total_followers': df['follower_count'].sum(),
            'median_followers': df['follower_count'].median(),
            'max_followers': df['follower_count'].max(),
            'min_followers': df['follower_count'].min(),
            'partner_count': df['is_partner'].sum(),
            'partner_pct': (df['is_partner'].sum() / len(df) * 100),
            'unique_games': df['game_name'].nunique(),
            'unique_languages': df['language'].nunique(),
            'total_games': len(df['game_name'].unique()),
        }
        
        return metrics
    
    def get_network_metrics(self) -> Dict:
        """
        Get network-specific metrics
        
        Returns:
            Dictionary with network metrics
        """
        if self.graph is None or self.graph.number_of_nodes() == 0:
            return {
                'nodes': 0,
                'edges': 0,
                'density': 0,
                'avg_degree': 0,
                'avg_clustering': 0,
                'diameter': 0,
                'communities': 0
            }
        
        g = self.graph
        
        metrics = {
            'nodes': g.number_of_nodes(),
            'edges': g.number_of_edges(),
            'density': nx.density(g),
            'avg_degree': sum(dict(g.degree()).values()) / g.number_of_nodes(),
            'avg_clustering': nx.average_clustering(g),
            'is_connected': nx.is_connected(g),
            'num_components': nx.number_connected_components(g),
        }
        
        # Safe diameter calculation for connected graphs
        if metrics['is_connected']:
            metrics['diameter'] = nx.diameter(g)
        else:
            # Calculate for largest component
            largest_cc = max(nx.connected_components(g), key=len)
            subgraph = g.subgraph(largest_cc)
            metrics['diameter'] = nx.diameter(subgraph) if len(largest_cc) > 1 else 1
        
        return metrics
    
    def get_game_metrics(self) -> Dict[str, Dict]:
        """
        Get detailed metrics for each game
        
        Returns:
            Dictionary mapping game names to metrics
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {}
        
        df = self.streamers_df
        game_metrics = {}
        
        for game in df['game_name'].unique():
            game_df = df[df['game_name'] == game]
            game_metrics[game] = {
                'streamer_count': len(game_df),
                'avg_followers': game_df['follower_count'].mean(),
                'total_followers': game_df['follower_count'].sum(),
                'partner_pct': (game_df['is_partner'].sum() / len(game_df) * 100),
                'avg_partner': game_df['is_partner'].mean(),
                'language_diversity': game_df['language'].nunique()
            }
        
        return game_metrics
    
    def get_language_metrics(self) -> Dict[str, Dict]:
        """
        Get metrics for each language
        
        Returns:
            Dictionary mapping languages to metrics
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {}
        
        df = self.streamers_df
        lang_metrics = {}
        
        for lang in df['language'].unique():
            lang_df = df[df['language'] == lang]
            lang_metrics[lang] = {
                'streamer_count': len(lang_df),
                'avg_followers': lang_df['follower_count'].mean(),
                'partner_pct': (lang_df['is_partner'].sum() / len(lang_df) * 100),
                'games_count': lang_df['game_name'].nunique(),
                'top_game': lang_df['game_name'].value_counts().index[0] if len(lang_df) > 0 else 'Unknown'
            }
        
        return lang_metrics
    
    def get_influencer_tiers(self) -> Dict[str, List]:
        """
        Categorize streamers into influence tiers
        
        Returns:
            Dictionary mapping tier names to streamer lists
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {'mega': [], 'tier1': [], 'tier2': [], 'tier3': [], 'emerging': []}
        
        df = self.streamers_df.sort_values('follower_count', ascending=False)
        total = len(df)
        
        tiers = {
            'mega': df.iloc[:max(1, int(total * 0.01))][['display_name', 'follower_count', 'game_name']].to_dict('records'),
            'tier1': df.iloc[max(1, int(total * 0.01)):max(2, int(total * 0.05))][['display_name', 'follower_count', 'game_name']].to_dict('records'),
            'tier2': df.iloc[max(2, int(total * 0.05)):max(3, int(total * 0.20))][['display_name', 'follower_count', 'game_name']].to_dict('records'),
            'tier3': df.iloc[max(3, int(total * 0.20)):max(4, int(total * 0.50))][['display_name', 'follower_count', 'game_name']].to_dict('records'),
            'emerging': df.iloc[max(4, int(total * 0.50)):][['display_name', 'follower_count', 'game_name']].to_dict('records')
        }
        
        return tiers
    
    def get_trending_metrics(self, top_n: int = 5) -> Dict:
        """
        Get trending metrics and top performers
        
        Args:
            top_n: Number of top items to return
        
        Returns:
            Dictionary with trending information
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {}
        
        df = self.streamers_df
        
        trends = {
            'top_streamers': df.nlargest(top_n, 'follower_count')[
                ['display_name', 'follower_count', 'game_name']
            ].to_dict('records'),
            'top_games': df['game_name'].value_counts().head(top_n).to_dict(),
            'top_languages': df['language'].value_counts().head(top_n).to_dict(),
            'highest_avg_followers_game': self._get_highest_avg_game(df),
            'most_diverse_language': self._get_most_diverse_language(df),
        }
        
        return trends
    
    def _get_highest_avg_game(self, df: pd.DataFrame) -> Dict:
        """Get game with highest average followers"""
        if len(df) == 0:
            return {}
        
        game_avg = df.groupby('game_name')['follower_count'].mean().sort_values(ascending=False)
        if len(game_avg) > 0:
            top_game = game_avg.index[0]
            return {
                'game': top_game,
                'avg_followers': game_avg.iloc[0],
                'streamer_count': len(df[df['game_name'] == top_game])
            }
        return {}
    
    def _get_most_diverse_language(self, df: pd.DataFrame) -> Dict:
        """Get most language-diverse game"""
        if len(df) == 0:
            return {}
        
        game_diversity = df.groupby('game_name')['language'].nunique().sort_values(ascending=False)
        if len(game_diversity) > 0:
            diverse_game = game_diversity.index[0]
            return {
                'game': diverse_game,
                'language_count': game_diversity.iloc[0],
                'streamer_count': len(df[df['game_name'] == diverse_game])
            }
        return {}
    
    def get_partnership_metrics(self) -> Dict:
        """
        Get partnership-related metrics
        
        Returns:
            Dictionary with partnership statistics
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {}
        
        df = self.streamers_df
        partners = df[df['is_partner'] == True]
        non_partners = df[df['is_partner'] == False]
        
        metrics = {
            'total_partners': len(partners),
            'total_non_partners': len(non_partners),
            'partner_pct': (len(partners) / len(df) * 100) if len(df) > 0 else 0,
            'avg_followers_partner': partners['follower_count'].mean() if len(partners) > 0 else 0,
            'avg_followers_non_partner': non_partners['follower_count'].mean() if len(non_partners) > 0 else 0,
            'partner_follower_advantage': (
                (partners['follower_count'].mean() / non_partners['follower_count'].mean() - 1) * 100
                if len(partners) > 0 and len(non_partners) > 0 else 0
            )
        }
        
        return metrics
    
    def get_recommendation_stats(self) -> Dict:
        """
        Get statistics relevant for recommendations
        
        Returns:
            Dictionary with recommendation statistics
        """
        if self.streamers_df is None or len(self.streamers_df) == 0:
            return {}
        
        df = self.streamers_df
        
        stats = {
            'recommended_count': len(df[df['follower_count'] >= df['follower_count'].quantile(0.25)]),
            'niche_opportunity': len(df[(df['follower_count'] >= 1000) & (df['follower_count'] <= 50000)]),
            'highly_visible': len(df[df['follower_count'] >= df['follower_count'].quantile(0.75)]),
            'avg_recommendation_tier_followers': df[
                (df['follower_count'] >= 5000) & (df['follower_count'] <= 500000)
            ]['follower_count'].mean() if len(df) > 0 else 0
        }
        
        return stats
    
    def generate_summary_report(self) -> str:
        """
        Generate a text summary of all metrics
        
        Returns:
            Formatted string report
        """
        overview = self.get_overview_metrics()
        network = self.get_network_metrics()
        partnership = self.get_partnership_metrics()
        recommendations = self.get_recommendation_stats()
        
        report = f"""
╔════════════════════════════════════════════════════════════════════╗
║                    DASHBOARD SUMMARY REPORT                        ║
╠════════════════════════════════════════════════════════════════════╣

OVERVIEW METRICS
  • Total Streamers: {overview.get('total_streamers', 0):,}
  • Average Followers: {overview.get('avg_followers', 0):,.0f}
  • Total Followers: {overview.get('total_followers', 0):,}
  • Median Followers: {overview.get('median_followers', 0):,.0f}
  • Partners: {overview.get('partner_count', 0)} ({overview.get('partner_pct', 0):.1f}%)

GAME COVERAGE
  • Unique Games: {overview.get('unique_games', 0)}
  • Unique Languages: {overview.get('unique_languages', 0)}

NETWORK METRICS
  • Nodes: {network.get('nodes', 0):,}
  • Edges: {network.get('edges', 0):,}
  • Density: {network.get('density', 0):.4f}
  • Avg Degree: {network.get('avg_degree', 0):.2f}
  • Avg Clustering: {network.get('avg_clustering', 0):.4f}
  • Components: {network.get('num_components', 0)}

PARTNERSHIP ANALYSIS
  • Partners: {partnership.get('total_partners', 0):,}
  • Non-Partners: {partnership.get('total_non_partners', 0):,}
  • Partner Follower Advantage: {partnership.get('partner_follower_advantage', 0):.1f}%

RECOMMENDATION POTENTIAL
  • Recommended Count: {recommendations.get('recommended_count', 0):,}
  • Niche Opportunities: {recommendations.get('niche_opportunity', 0):,}
  • Highly Visible: {recommendations.get('highly_visible', 0):,}

╚════════════════════════════════════════════════════════════════════╝
        """
        
        return report


class DashboardCache:
    """Cache for expensive dashboard calculations"""
    
    def __init__(self, cache_time_seconds: int = 300):
        self.cache = {}
        self.cache_time = cache_time_seconds
        self.timestamps = {}
    
    def get(self, key: str):
        """Get cached value if fresh"""
        import time
        
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.cache_time:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        
        return None
    
    def set(self, key: str, value):
        """Set cache value"""
        import time
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.timestamps.clear()


if __name__ == "__main__":
    print("Dashboard metrics module loaded")
