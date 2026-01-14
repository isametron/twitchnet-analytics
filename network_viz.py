"""
Advanced network visualization utilities for graph rendering and analysis
Provides methods for creating custom visualizations with different layouts and styles
"""

import networkx as nx
import numpy as np
import pandas as pd
from pyvis.network import Network
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Tuple, List, Optional
from collections import defaultdict


class NetworkVisualizer:
    """Advanced network visualization engine"""
    
    def __init__(self, graph: nx.Graph, height: str = "750px", width: str = "100%"):
        self.graph = graph
        self.height = height
        self.width = width
    
    def create_network_visualization(self, physics_enabled: bool = True,
                                    show_labels: bool = True,
                                    color_by_game: bool = True,
                                    size_by_centrality: str = None) -> Network:
        """
        Create a PyVis network visualization with customizable physics
        
        Args:
            physics_enabled: Enable physics simulation
            show_labels: Show node labels
            color_by_game: Color nodes by game category
            size_by_centrality: Size nodes by centrality metric ('pagerank', 'degree', 'betweenness')
        
        Returns:
            PyVis Network object
        """
        net = Network(
            height=self.height,
            width=self.width,
            bgcolor="#0f172a",
            font_color="#e2e8f0",
            directed=False
        )
        
        if physics_enabled:
            net.barnes_hut(
                gravity=-30000,
                central_gravity=0.25,
                spring_length=130,
                spring_strength=0.005,
                damping=0.85
            )
        
        # Calculate centrality if needed
        if size_by_centrality:
            if size_by_centrality == 'pagerank':
                centrality = nx.pagerank(self.graph)
            elif size_by_centrality == 'degree':
                centrality = dict(self.graph.degree())
            elif size_by_centrality == 'betweenness':
                centrality = nx.betweenness_centrality(self.graph)
            else:
                centrality = dict(self.graph.degree())
        else:
            centrality = dict(self.graph.degree())
        
        # Create game color map
        games = set(data.get('game_name', 'Unknown') 
                   for _, data in self.graph.nodes(data=True))
        game_colors = self._generate_color_palette(len(games))
        game_color_map = dict(zip(sorted(games), game_colors))
        
        # Add nodes
        for node, data in self.graph.nodes(data=True):
            display_name = data.get('display_name', node)
            game = data.get('game_name', 'Unknown')
            followers = data.get('follower_count', 0)
            is_partner = data.get('is_partner', False)
            
            # Size based on centrality
            size = 10 + (centrality.get(node, 0) * 100)
            
            # Color based on game or partnership
            if color_by_game:
                color = game_color_map.get(game, '#06b6d4')
            else:
                color = '#0ea5e9' if is_partner else '#06b6d4'
            
            # Hover title
            title = (
                f"<b>{display_name}</b><br>"
                f"Game: {game}<br>"
                f"Followers: {followers:,}<br>"
                f"Partner: {'Yes' if is_partner else 'No'}<br>"
                f"Centrality: {centrality.get(node, 0):.4f}"
            )
            
            net.add_node(
                node,
                label=display_name if show_labels else "",
                title=title,
                size=size,
                color=color,
                physics=True
            )
        
        # Add edges with style
        for u, v, attrs in self.graph.edges(data=True):
            weight = attrs.get('weight', 0.5)
            edge_type = attrs.get('type', 'other')
            
            # Edge color based on type
            if edge_type == 'same_game':
                edge_color = '#0ea5e9'
            elif edge_type == 'similar_tags':
                edge_color = '#06b6d4'
            else:
                edge_color = '#475569'
            
            net.add_edge(
                u, v,
                value=weight * 5,
                color=edge_color,
                title=f"Type: {edge_type}, Weight: {weight:.2f}"
            )
        
        return net
    
    def create_degree_distribution_plot(self) -> go.Figure:
        """Create degree distribution visualization"""
        degrees = dict(self.graph.degree())
        degree_counts = defaultdict(int)
        for degree in degrees.values():
            degree_counts[degree] += 1
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(degree_counts.keys()),
                y=list(degree_counts.values()),
                marker_color='#0ea5e9',
                name='Streamers'
            )
        ])
        
        fig.update_layout(
            title="Network Degree Distribution",
            xaxis_title="Degree (Connections)",
            yaxis_title="Number of Streamers",
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        
        return fig
    
    def create_community_network(self, communities: Dict[int, List],
                                community_id: int = None) -> Network:
        """
        Create network visualization for a specific community
        
        Args:
            communities: Dictionary of communities
            community_id: Specific community to visualize (None for all)
        
        Returns:
            PyVis Network object
        """
        net = Network(
            height=self.height,
            width=self.width,
            bgcolor="#0f172a",
            font_color="#e2e8f0",
            directed=False
        )
        
        net.barnes_hut(gravity=-25000, central_gravity=0.3)
        
        if community_id is not None and community_id in communities:
            # Visualize single community
            nodes = set(communities[community_id])
            subgraph = self.graph.subgraph(nodes)
            color = self._get_community_color(community_id)
        else:
            # Visualize all communities
            subgraph = self.graph
            color = None
        
        # Add nodes
        for node, data in subgraph.nodes(data=True):
            if color is None:
                # Find which community this node belongs to
                for comm_id, members in communities.items():
                    if node in members:
                        node_color = self._get_community_color(comm_id)
                        break
                else:
                    node_color = '#475569'
            else:
                node_color = color
            
            net.add_node(
                node,
                label=data.get('display_name', node),
                title=f"{data.get('display_name', node)} ({data.get('game_name', 'Unknown')})",
                size=15,
                color=node_color
            )
        
        # Add edges
        for u, v in subgraph.edges():
            net.add_edge(u, v, color='#0ea5e9', value=1)
        
        return net
    
    def create_centrality_comparison_plot(self, centrality_metrics: Dict[str, Dict]) -> go.Figure:
        """
        Create comparison of different centrality metrics
        
        Args:
            centrality_metrics: Dictionary of metric names to centrality scores
        
        Returns:
            Plotly Figure
        """
        # Get top 15 nodes by pagerank
        pagerank = centrality_metrics.get('pagerank', {})
        top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:15]
        
        data = []
        for metric_name, scores in centrality_metrics.items():
            values = [scores.get(node, 0) for node, _ in top_nodes]
            data.append(
                go.Bar(
                    x=[self.graph.nodes[n[0]].get('display_name', n[0]) for n in top_nodes],
                    y=values,
                    name=metric_name.replace('_', ' ').title()
                )
            )
        
        fig = go.Figure(data=data)
        fig.update_layout(
            title="Centrality Metrics Comparison (Top 15)",
            xaxis_title="Streamer",
            yaxis_title="Score",
            barmode='group',
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0",
            hovermode='x unified'
        )
        
        return fig
    
    def create_influence_map(self, centrality_metric: str = 'pagerank') -> go.Figure:
        """
        Create heatmap-style visualization of influence across games
        
        Args:
            centrality_metric: Centrality metric to use for influence
        
        Returns:
            Plotly Figure
        """
        # Group by game and calculate average influence
        game_influence = defaultdict(list)
        influence_scores = {}
        
        if centrality_metric == 'pagerank':
            influence_scores = nx.pagerank(self.graph)
        elif centrality_metric == 'degree':
            influence_scores = dict(self.graph.degree())
        elif centrality_metric == 'betweenness':
            influence_scores = nx.betweenness_centrality(self.graph)
        
        for node, influence in influence_scores.items():
            game = self.graph.nodes[node].get('game_name', 'Unknown')
            game_influence[game].append(influence)
        
        # Create summary
        game_stats = []
        for game, influences in game_influence.items():
            game_stats.append({
                'game': game,
                'avg_influence': np.mean(influences),
                'max_influence': np.max(influences),
                'count': len(influences)
            })
        
        df = pd.DataFrame(game_stats).sort_values('avg_influence', ascending=False).head(20)
        
        fig = px.bar(
            df,
            x='game',
            y='avg_influence',
            color='count',
            size='max_influence',
            title=f"Game Influence Map ({centrality_metric.title()})",
            labels={'game': 'Game', 'avg_influence': 'Average Influence', 'count': 'Streamer Count'},
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        
        return fig
    
    def _generate_color_palette(self, n: int) -> List[str]:
        """Generate n distinct colors for visualization"""
        colors = [
            '#0ea5e9', '#06b6d4', '#0891b2', '#0d9488', '#059669',
            '#10b981', '#14b8a6', '#06b6d4', '#2563eb', '#3b82f6',
            '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e',
            '#f97316', '#eab308', '#ca8a04', '#d97706', '#ea580c'
        ]
        
        # If we need more colors than available, cycle through
        if n <= len(colors):
            return colors[:n]
        else:
            return (colors * ((n // len(colors)) + 1))[:n]
    
    def _get_community_color(self, community_id: int) -> str:
        """Get a unique color for a community"""
        colors = [
            '#0ea5e9', '#06b6d4', '#0891b2', '#059669', '#10b981',
            '#3b82f6', '#8b5cf6', '#d946ef', '#ec4899', '#f97316'
        ]
        return colors[community_id % len(colors)]


class GraphAnalysisVisualizer:
    """Visualize advanced graph analysis metrics"""
    
    def __init__(self, graph: nx.Graph):
        self.graph = graph
    
    def create_clustering_coefficient_plot(self) -> go.Figure:
        """Visualize clustering coefficients"""
        clustering = nx.clustering(self.graph)
        
        # Group nodes by clustering coefficient ranges
        ranges = defaultdict(int)
        for coeff in clustering.values():
            range_key = int(coeff * 10) / 10
            ranges[range_key] += 1
        
        fig = go.Figure(data=[
            go.Bar(
                x=[f"{k:.1f}-{k+0.1:.1f}" for k in sorted(ranges.keys())],
                y=[ranges[k] for k in sorted(ranges.keys())],
                marker_color='#06b6d4'
            )
        ])
        
        fig.update_layout(
            title="Clustering Coefficient Distribution",
            xaxis_title="Clustering Coefficient",
            yaxis_title="Number of Nodes",
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        
        return fig
    
    def create_connected_components_plot(self) -> go.Figure:
        """Visualize connected components"""
        if nx.is_connected(self.graph):
            components = [list(self.graph.nodes())]
        else:
            components = list(nx.connected_components(self.graph))
        
        component_sizes = sorted([len(c) for c in components], reverse=True)
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(range(1, len(component_sizes) + 1)),
                y=component_sizes,
                marker_color='#0ea5e9',
                name='Component Size'
            )
        ])
        
        fig.update_layout(
            title="Connected Components Size Distribution",
            xaxis_title="Component Index",
            yaxis_title="Component Size",
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        
        return fig


if __name__ == "__main__":
    # Example usage would go here
    print("Network visualization module loaded")
