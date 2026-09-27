import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List

class AdvancedVisualizer:
    """Advanced visualization tools for network analysis"""
    
    def __init__(self, graph: nx.Graph = None):
        self.graph = graph
    
    def create_3d_network(self, centrality_scores: Dict = None, 
                         communities: Dict = None,
                         color_by: str = 'community') -> go.Figure:
        """
        Create interactive 3D network visualization
        
        Args:
            centrality_scores: Dictionary of centrality metrics
            communities: Community assignments
            color_by: 'community', 'centrality', or 'game'
        
        Returns:
            Plotly 3D scatter figure
        """
        if not self.graph:
            return None
        
        # Use spring layout in 3D
        pos = nx.spring_layout(self.graph, dim=3, seed=42, k=0.5)
        
        # Extract coordinates
        x_nodes = [pos[node][0] for node in self.graph.nodes()]
        y_nodes = [pos[node][1] for node in self.graph.nodes()]
        z_nodes = [pos[node][2] for node in self.graph.nodes()]
        
        # Prepare node data
        node_ids = list(self.graph.nodes())
        node_labels = [self.graph.nodes[node].get('display_name', node) for node in node_ids]
        node_sizes = []
        node_colors = []
        
        # Color and size based on preference
        if color_by == 'community' and communities:
            # Map nodes to communities
            node_to_comm = {}
            for comm_id, members in communities.items():
                for member in members:
                    node_to_comm[member] = comm_id
            
            node_colors = [node_to_comm.get(node, 0) for node in node_ids]
            
        elif color_by == 'centrality' and centrality_scores:
            pagerank = centrality_scores.get('pagerank', {})
            node_colors = [pagerank.get(node, 0) for node in node_ids]
            
        elif color_by == 'game':
            games = [self.graph.nodes[node].get('game_name', 'Unknown') for node in node_ids]
            # Convert to numeric
            unique_games = list(set(games))
            game_to_num = {game: idx for idx, game in enumerate(unique_games)}
            node_colors = [game_to_num[game] for game in games]
        else:
            node_colors = [0.5] * len(node_ids)
        
        # Size by follower count
        for node in node_ids:
            followers = self.graph.nodes[node].get('follower_count', 1000)
            size = 5 + np.log1p(followers) / 2
            node_sizes.append(size)
        
        # Create edges
        edge_x = []
        edge_y = []
        edge_z = []
        
        for edge in self.graph.edges():
            x0, y0, z0 = pos[edge[0]]
            x1, y1, z1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_z.extend([z0, z1, None])
        
        # Create edge trace
        edge_trace = go.Scatter3d(
            x=edge_x, y=edge_y, z=edge_z,
            mode='lines',
            line=dict(color='rgba(100, 116, 255, 0.2)', width=1),
            hoverinfo='none',
            name='Connections'
        )
        
        # Create node trace
        node_trace = go.Scatter3d(
            x=x_nodes, y=y_nodes, z=z_nodes,
            mode='markers',
            marker=dict(
                size=node_sizes,
                color=node_colors,
                colorscale='Viridis',
                line=dict(color='rgba(255,255,255,0.3)', width=0.5),
                showscale=True,
                colorbar=dict(
                    title=color_by.title(),
                    thickness=15,
                    x=1.1
                )
            ),
            text=node_labels,
            hovertemplate='<b>%{text}</b><br>Size: %{marker.size}<extra></extra>',
            name='Streamers'
        )
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace])
        
        fig.update_layout(
            title=dict(
                text="3D Network Visualization",
                font=dict(size=24, color='#e5e7eb')
            ),
            scene=dict(
                xaxis=dict(showgrid=False, showticklabels=False, title=''),
                yaxis=dict(showgrid=False, showticklabels=False, title=''),
                zaxis=dict(showgrid=False, showticklabels=False, title=''),
                bgcolor='rgba(10, 14, 39, 0.95)'
            ),
            paper_bgcolor='#0a0e27',
            plot_bgcolor='#0a0e27',
            font=dict(color='#e5e7eb'),
            showlegend=True,
            hovermode='closest',
            margin=dict(l=0, r=0, t=50, b=0)
        )
        
        return fig
    
    def create_time_series_growth(self, historical_data: pd.DataFrame,
                                  metric: str = 'follower_count') -> go.Figure:
        """
        Create time-series chart for growth tracking
        
        Args:
            historical_data: DataFrame with columns [date, streamer_id, metric]
            metric: Metric to track over time
        
        Returns:
            Plotly line chart
        """
        fig = go.Figure()
        
        # Group by date and aggregate
        if 'date' in historical_data.columns:
            daily_data = historical_data.groupby('date')[metric].agg(['mean', 'sum']).reset_index()
            
            fig.add_trace(go.Scatter(
                x=daily_data['date'],
                y=daily_data['mean'],
                mode='lines+markers',
                name='Average',
                line=dict(color='#6474ff', width=3),
                marker=dict(size=8)
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_data['date'],
                y=daily_data['sum'],
                mode='lines',
                name='Total',
                line=dict(color='#f59e0b', width=2, dash='dash')
            ))
        
        fig.update_layout(
            title=f"{metric.replace('_', ' ').title()} Over Time",
            xaxis_title="Date",
            yaxis_title=metric.replace('_', ' ').title(),
            plot_bgcolor='#0f172a',
            paper_bgcolor='#0f172a',
            font=dict(color='#e2e8f0'),
            hovermode='x unified',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    def create_community_evolution_sankey(self, temporal_snapshots: List[Dict]) -> go.Figure:
        """
        Create Sankey diagram showing community evolution over time
        
        Args:
            temporal_snapshots: List of community snapshots with timestamps
        
        Returns:
            Plotly Sankey diagram
        """
        if len(temporal_snapshots) < 2:
            return None
        
        source = []
        target = []
        value = []
        labels = []
        
        # Build node labels
        for i, snapshot in enumerate(temporal_snapshots):
            partition = snapshot['partition']
            communities = {}
            for node, comm_id in partition.items():
                if comm_id not in communities:
                    communities[comm_id] = []
                communities[comm_id].append(node)
            
            for comm_id in communities.keys():
                labels.append(f"T{i}-C{comm_id}")
        
        # Track flows between timestamps
        for i in range(len(temporal_snapshots) - 1):
            curr = temporal_snapshots[i]['partition']
            next_snap = temporal_snapshots[i + 1]['partition']
            
            # Find node migrations
            flows = {}
            for node in curr:
                if node in next_snap:
                    curr_comm = curr[node]
                    next_comm = next_snap[node]
                    flow_key = (f"T{i}-C{curr_comm}", f"T{i+1}-C{next_comm}")
                    flows[flow_key] = flows.get(flow_key, 0) + 1
            
            # Add flows to sankey
            for (src, tgt), count in flows.items():
                if src in labels and tgt in labels:
                    source.append(labels.index(src))
                    target.append(labels.index(tgt))
                    value.append(count)
        
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='rgba(0,0,0,0)', width=0.5),
                label=labels,
                color='#6474ff'
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
                color='rgba(100, 116, 255, 0.3)'
            )
        )])
        
        fig.update_layout(
            title="Community Evolution Over Time",
            font=dict(size=12, color='#e2e8f0'),
            plot_bgcolor='#0f172a',
            paper_bgcolor='#0f172a'
        )
        
        return fig
    
    def create_geographic_heatmap(self, streamers_df: pd.DataFrame) -> go.Figure:
        """
        Create geographic distribution heatmap
        
        Args:
            streamers_df: DataFrame with streamer data including language
        
        Returns:
            Plotly choropleth map
        """
        # Map languages to countries (simplified)
        lang_to_country = {
            'en': 'USA',
            'es': 'ESP',
            'fr': 'FRA',
            'de': 'DEU',
            'pt': 'BRA',
            'ja': 'JPN',
            'ko': 'KOR',
            'ru': 'RUS',
            'zh': 'CHN'
        }
        
        # Count streamers by language
        if 'language' in streamers_df.columns:
            lang_counts = streamers_df['language'].value_counts().to_dict()
            
            # Convert to country data
            country_data = []
            for lang, count in lang_counts.items():
                if lang in lang_to_country:
                    country_data.append({
                        'country': lang_to_country[lang],
                        'count': count,
                        'language': lang
                    })
            
            df_geo = pd.DataFrame(country_data)
            
            fig = px.choropleth(
                df_geo,
                locations='country',
                locationmode='ISO-3',
                color='count',
                hover_name='language',
                color_continuous_scale='Viridis',
                title="Streamer Distribution by Region"
            )
            
            fig.update_layout(
                geo=dict(
                    bgcolor='rgba(10, 14, 39, 0.95)',
                    lakecolor='rgba(10, 14, 39, 0.95)',
                    landcolor='#1e293b',
                    showframe=False
                ),
                paper_bgcolor='#0a0e27',
                font=dict(color='#e2e8f0')
            )
            
            return fig
        
        return None
    
    def create_interactive_filter_network(self, min_followers: int = 0,
                                         max_followers: int = float('inf'),
                                         games: List[str] = None,
                                         min_centrality: float = 0) -> nx.Graph:
        """
        Create filtered subgraph based on criteria
        
        Args:
            min_followers: Minimum follower count
            max_followers: Maximum follower count
            games: List of games to include
            min_centrality: Minimum PageRank centrality
        
        Returns:
            Filtered NetworkX graph
        """
        if not self.graph:
            return None
        
        filtered_nodes = []
        
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            
            # Follower filter
            followers = node_data.get('follower_count', 0)
            if not (min_followers <= followers <= max_followers):
                continue
            
            # Game filter
            if games:
                game = node_data.get('game_name', '')
                if game not in games:
                    continue
            
            filtered_nodes.append(node)
        
        # Create subgraph
        subgraph = self.graph.subgraph(filtered_nodes).copy()
        
        return subgraph
    
    def create_influence_propagation_animation(self, propagation_result: Dict) -> go.Figure:
        """
        Animate influence propagation through the network
        
        Args:
            propagation_result: Result from simulate_influence_propagation
        
        Returns:
            Plotly animation figure
        """
        timeline = propagation_result.get('timeline', [])
        
        # Create frames for animation
        frames = []
        
        for t in timeline:
            frame_data = {
                'Iteration': t['iteration'],
                'Influenced': t['influenced_count'],
                'New': t.get('new_this_round', 0)
            }
            frames.append(frame_data)
        
        df_frames = pd.DataFrame(frames)
        
        # Create animated bar chart
        fig = px.bar(
            df_frames,
            x='Iteration',
            y=['Influenced', 'New'],
            title="Influence Propagation Over Time",
            labels={'value': 'Node Count', 'Iteration': 'Iteration'},
            barmode='group',
            color_discrete_sequence=['#6474ff', '#f59e0b']
        )
        
        fig.update_layout(
            plot_bgcolor='#0f172a',
            paper_bgcolor='#0f172a',
            font=dict(color='#e2e8f0'),
            xaxis_title="Iteration",
            yaxis_title="Number of Nodes"
        )
        
        return fig
    
    def create_centrality_radar(self, node_id: str, 
                               centrality_scores: Dict[str, Dict]) -> go.Figure:
        """
        Create radar chart for a node's centrality metrics
        
        Args:
            node_id: Node identifier
            centrality_scores: Dictionary of all centrality metrics
        
        Returns:
            Plotly radar chart
        """
        metrics = []
        values = []
        
        for metric_name, scores in centrality_scores.items():
            if node_id in scores:
                metrics.append(metric_name.replace('_', ' ').title())
                # Normalize to 0-1 if needed
                score = scores[node_id]
                max_score = max(scores.values()) if scores.values() else 1
                normalized = score / max_score if max_score > 0 else 0
                values.append(normalized)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=metrics,
            fill='toself',
            fillcolor='rgba(100, 116, 255, 0.3)',
            line=dict(color='#6474ff', width=2),
            name=node_id
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor='#334155',
                    color='#e2e8f0'
                ),
                angularaxis=dict(
                    gridcolor='#334155',
                    color='#e2e8f0'
                ),
                bgcolor='#0f172a'
            ),
            paper_bgcolor='#0a0e27',
            font=dict(color='#e2e8f0'),
            title=f"Centrality Profile: {node_id}"
        )
        
        return fig


if __name__ == "__main__":
    print("Advanced visualization module - import into app.py")
