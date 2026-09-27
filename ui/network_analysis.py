"""Network Analysis page: build the graph, centrality, communities and visualizations."""
import random
import statistics
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from advanced_viz import AdvancedVisualizer
from centrality import CentralityAnalyzer
from community_detection import CommunityDetector
from graph_builder import StreamerNetworkBuilder
from ui.network_graph import build_network_html


def render():
    st.markdown("<h2>Network Analysis</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #9ca3af; margin-bottom: 1.5rem;'>Build and analyze streamer network topology</p>", unsafe_allow_html=True)

    if not st.session_state.streamers_data:
        st.warning("⚠️ Please collect data first from the Data Collection page.")
    else:
        st.subheader("⚙️ Network Building Options")
        
        col1, col2 = st.columns(2)
        with col1:
            use_comprehensive = st.checkbox("Use Comprehensive Network Building", value=True, 
                                           help="Uses all edge creation methods: games, tags, language, partner status, and viewer tiers")
            weight_by_audience = st.checkbox("Weight Edges by Audience Size", value=True,
                                            help="Gives more weight to connections between larger streamers")
        
        with col2:
            include_advanced_metrics = st.checkbox("Calculate Advanced Metrics", value=True,
                                                   help="Includes harmonic centrality, load centrality, and clustering coefficient (slower)")
            calculate_influence = st.checkbox("Calculate Composite Influence Score", value=True,
                                            help="Combines multiple metrics into a single influence score")
        
        if st.button("🔨 Build Network Graph", type="primary"):
            with st.spinner("Building network and calculating metrics..."):
                progress_text = st.empty()
                
                # Build network
                progress_text.text("🕸️ Building network structure...")
                builder = StreamerNetworkBuilder()
                builder.add_streamers(st.session_state.streamers_data)
                
                if use_comprehensive:
                    builder.build_comprehensive_network(use_all_methods=True, weight_by_audience=weight_by_audience)
                else:
                    builder.add_edges_from_shared_games(weight_by_audience=weight_by_audience)
                    builder.add_edges_from_tags(similarity_threshold=0.2)

                st.session_state.graph = builder.graph
                
                # Calculate centrality
                progress_text.text("🔢 Calculating centrality metrics...")
                analyzer = CentralityAnalyzer(builder.graph)
                st.session_state.centrality_scores = analyzer.calculate_all_centralities(
                    include_advanced=include_advanced_metrics
                )
                
                if calculate_influence:
                    progress_text.text("✨ Calculating influence scores...")
                    analyzer.calculate_influence_score()
                
                # Detect communities
                progress_text.text("🔍 Detecting communities...")
                detector = CommunityDetector(builder.graph)
                st.session_state.communities = detector.detect_communities_louvain()
                
                progress_text.text("✅ Network analysis complete!")

            st.success("🎉 Network built successfully with enhanced metrics!")

        if st.session_state.graph:
            st.subheader("📊 Network Statistics")

            col1, col2, col3, col4, col5 = st.columns(5)
            stats = {
                'num_nodes': st.session_state.graph.number_of_nodes(),
                'num_edges': st.session_state.graph.number_of_edges(),
                'density': nx.density(st.session_state.graph),
                'communities': len(st.session_state.communities) if st.session_state.communities else 0,
                'avg_clustering': nx.average_clustering(st.session_state.graph) if st.session_state.graph.number_of_nodes() > 0 else 0
            }

            with col1:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Nodes", stats['num_nodes'])
                st.markdown('</div>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Edges", stats['num_edges'])
                st.markdown('</div>', unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Density", f"{stats['density']:.4f}")
                st.markdown('</div>', unsafe_allow_html=True)
            with col4:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Communities", stats['communities'])
                st.markdown('</div>', unsafe_allow_html=True)
            with col5:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Avg Clustering", f"{stats['avg_clustering']:.3f}")
                st.markdown('</div>', unsafe_allow_html=True)

            # ---------- MAIN NETWORK GRAPH (optimized) ----------
            st.subheader("Interactive Network Visualization")
            
            # Visualization controls
            col_vis1, col_vis2, col_vis3 = st.columns(3)
            
            with col_vis1:
                max_nodes = st.slider("Max nodes to display (for performance)", 20, 200, 40, 10)
            
            with col_vis2:
                color_by = st.selectbox(
                    "Color nodes by",
                    ["Partner Status", "Game", "Language", "Follower Count", "Live Status", "Account Age"],
                    help="Choose what attribute to use for node coloring"
                )
            
            with col_vis3:
                selection_mode = st.selectbox(
                    "Node selection",
                    ["Top by PageRank", "Top by Centrality", "Random Sample"],
                    help="How to select which nodes to display"
                )

            # Centrality metric selector for 'Top by Centrality' mode
            centrality_metric = st.selectbox(
                "Centrality metric (used when 'Top by Centrality' selected)",
                ["pagerank", "degree", "betweenness", "closeness", "eigenvector", "harmonic", "influence"],
                index=0,
                help="Choose which centrality metric to rank nodes by"
            )
            
            # Edge type filters
            st.markdown("**Show connections:**")
            edge_col1, edge_col2, edge_col3, edge_col4, edge_col5 = st.columns(5)
            
            with edge_col1:
                show_same_game = st.checkbox("🎮 Same Game", value=True, help="Show cyan lines for same game")
            with edge_col2:
                show_same_language = st.checkbox("🌍 Same Language", value=False, help="Show pink lines for same language")
            with edge_col3:
                show_strong_connections = st.checkbox("🔗 Strong Connections (weight>threshold)", value=False, help="Show lines for edges stronger than a chosen weight threshold")
                # Compute suggested threshold from entire graph edge weights (75th percentile)
                try:
                    all_weights = [attrs.get('weight', 0) for _, _, attrs in st.session_state.graph.edges(data=True)]
                except Exception:
                    all_weights = []

                if all_weights:
                    suggested = float(np.percentile(all_weights, 75))
                    min_w = float(round(min(all_weights), 2))
                    max_w = float(round(max(all_weights), 2))
                    if min_w == max_w:
                        max_w = min_w + 0.1
                    step = max(0.01, round((max_w - min_w) / 100.0, 2))
                    default_val = float(round(suggested, 2))
                else:
                    min_w, max_w, default_val, step = 0.1, 10.0, 1.0, 0.1

                # Slider to control threshold when strong connections are enabled
                strong_conn_threshold = st.slider(
                    "Strong connection weight threshold",
                    min_value=min_w,
                    max_value=max_w,
                    value=default_val,
                    step=step,
                    help="Edges with weight >= threshold are considered strong connections"
                )
            with edge_col4:
                show_both_partners = st.checkbox("⭐ Both Partners", value=False, help="Show yellow lines for partners")
            with edge_col5:
                show_same_tier = st.checkbox("📊 Same Tier", value=False, help="Show green lines for same follower tier")
            
            # Get nodes based on selection mode
            pagerank = st.session_state.centrality_scores.get("pagerank", {})
            metric_scores = st.session_state.centrality_scores.get(centrality_metric, {})

            if selection_mode == "Random Sample":
                all_nodes = list(st.session_state.graph.nodes())
                if len(all_nodes) > max_nodes:
                    random.seed(42)  # Consistent random selection
                    top_node_ids = random.sample(all_nodes, max_nodes)
                else:
                    top_node_ids = all_nodes
            elif selection_mode == "Top by Centrality":
                # Use the chosen centrality metric to rank nodes
                ranked = sorted(metric_scores.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
                top_node_ids = [node for node, _ in ranked]
            else:
                top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
                top_node_ids = [node for node, _ in top_nodes]
            
            # Create subgraph with only selected nodes
            display_graph = st.session_state.graph.subgraph(top_node_ids)
            
            st.info(f"Displaying {display_graph.number_of_nodes()} nodes and {display_graph.number_of_edges()} edges | Selection: {selection_mode} | Colored by: {color_by}")

            # Edge weight distribution histogram to help choose a threshold
            weights = [attrs.get('weight', 0) for _, _, attrs in display_graph.edges(data=True)]
            if len(weights) == 0:
                st.info("No edges in the current subgraph to compute weight distribution.")
            else:
                w_min = min(weights)
                w_median = statistics.median(weights)
                w_max = max(weights)
                col_w1, col_w2, col_w3 = st.columns(3)
                col_w1.metric("Min edge weight", f"{w_min:.2f}")
                col_w2.metric("Median edge weight", f"{w_median:.2f}")
                col_w3.metric("Max edge weight", f"{w_max:.2f}")

                w_df = pd.DataFrame({'weight': weights})
                fig_w = px.histogram(
                    w_df,
                    x='weight',
                    nbins=30,
                    title="Edge weight distribution",
                    color_discrete_sequence=['#9ca3ff']
                )
                fig_w.update_layout(
                    plot_bgcolor="#0f172a",
                    paper_bgcolor="#0f172a",
                    font_color="#e6e6e6",
                    xaxis_title='Edge weight',
                    yaxis_title='Count'
                )
                # show vertical line for the current threshold
                try:
                    fig_w.update_layout(shapes=[dict(type='line', x0=strong_conn_threshold, x1=strong_conn_threshold, y0=0, y1=1, yref='paper', line=dict(color='#ff6b6b', width=2, dash='dash'))])
                except Exception:
                    pass

                st.plotly_chart(fig_w, width='stretch')

            html, edge_counts = build_network_html(
                display_graph, color_by, metric_scores, pagerank,
                show_same_game, show_same_language, show_strong_connections,
                show_both_partners, show_same_tier, strong_conn_threshold,
            )
            
            # Dynamic legend based on what's shown
            st.markdown("**📊 Active Connections:**")
            legend_parts = []
            if show_same_game and edge_counts["same_game"] > 0:
                legend_parts.append(f"<span style='color:#94a3b8'>━━━</span> Same Game ({edge_counts['same_game']})")
            if show_same_language and edge_counts["same_language"] > 0:
                legend_parts.append(f"<span style='color:#cbd5e1'>━━━</span> Same Language ({edge_counts['same_language']})")
            if show_strong_connections and edge_counts["strong_connections"] > 0:
                legend_parts.append(f"<span style='color:#9ca3ff'>━━━</span> Strong Connections ({edge_counts['strong_connections']})")
            if show_both_partners and edge_counts["both_partners"] > 0:
                legend_parts.append(f"<span style='color:#f59e0b'>━━━</span> Both Partners ({edge_counts['both_partners']})")
            if show_same_tier and edge_counts["same_tier"] > 0:
                legend_parts.append(f"<span style='color:#10b981'>━━━</span> Same Tier ({edge_counts['same_tier']})")
            
            if legend_parts:
                st.markdown(" | ".join(legend_parts), unsafe_allow_html=True)
            else:
                st.info("No connections selected. Check at least one connection type above to see links.")
            
            st.iframe(html, height=650)

            # ---------- EXTRA GRAPH 1: DEGREE DISTRIBUTION ----------
            st.subheader("Degree Distribution of Streamers")

            degrees = dict(st.session_state.graph.degree())
            degree_values = list(degrees.values())
            
            # Count occurrences of each degree value
            degree_counts = Counter(degree_values)
            deg_df = pd.DataFrame({
                "Degree": sorted(degree_counts.keys()),
                "Count": [degree_counts[d] for d in sorted(degree_counts.keys())]
            })

            fig_deg = px.bar(
                deg_df,
                x="Degree",
                y="Count",
                title="Network Degree Distribution",
                color="Count",
                color_continuous_scale="Blues"
            )
            fig_deg.update_layout(
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0",
                xaxis_title="Degree (Number of Connections)",
                yaxis_title="Number of Streamers"
            )
            st.plotly_chart(fig_deg, width='stretch')

            # ---------- EXTRA GRAPH 2: PAGERANK vs FOLLOWERS ----------
            st.subheader("Influence (PageRank) vs Followers")

            nodes = []
            for n, data in st.session_state.graph.nodes(data=True):
                nodes.append({
                    "display_name": data.get("display_name", n),
                    "pagerank": pagerank.get(n, 0),
                    "followers": data.get("follower_count", 0),
                    "game": data.get("game_name", "Unknown")
                })
            cent_df = pd.DataFrame(nodes)

            fig_scatter = px.scatter(
                cent_df,
                x="followers",
                y="pagerank",
                color="game",
                size="pagerank",
                hover_name="display_name",
                color_discrete_sequence=px.colors.qualitative.Set3,
                labels={"followers": "Followers", "pagerank": "PageRank"}
            )
            fig_scatter.update_layout(
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0"
            )
            st.plotly_chart(fig_scatter, width='stretch')

            # ============ EXTRA GRAPHS ============
            st.markdown("---")
            st.subheader("Advanced Network Visualizations")
            
            graph_col1, graph_col2 = st.columns(2)
            
            # Community size distribution
            with graph_col1:
                if st.session_state.communities:
                    # Enhanced community size with game breakdown
                    community_game_data = []
                    for comm_id, members in st.session_state.communities.items():
                        comm_size = len(members)
                        # Get game distribution in this community
                        games = {}
                        for member_id in members:
                            node_data = st.session_state.graph.nodes[member_id]
                            game = node_data.get('game_name', 'Unknown')
                            games[game] = games.get(game, 0) + 1
                        
                        # Create a compact game breakdown string
                        top_games = sorted(games.items(), key=lambda x: x[1], reverse=True)[:3]
                        game_breakdown = ', '.join([f"{g[0]}({g[1]})" for g in top_games])
                        
                        community_game_data.append({
                            'Community': f'C{comm_id}',
                            'Size': comm_size,
                            'Games': game_breakdown,
                            'Primary Game': top_games[0][0] if top_games else 'Unknown'
                        })
                    
                    comm_df = pd.DataFrame(community_game_data)
                    
                    fig_comm_size = px.bar(
                        comm_df,
                        x='Community',
                        y='Size',
                        color='Primary Game',
                        title="Community Size Distribution by Primary Game",
                        labels={'Size': 'Community Size', 'Community': 'Community ID'},
                        hover_data=['Games'],
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig_comm_size.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0",
                        xaxis_tickangle=-45,
                        hovermode='closest'
                    )
                    st.plotly_chart(fig_comm_size, width='stretch')
            
            # Centrality distribution with game breakdown
            with graph_col2:
                # Collect PageRank scores with game information
                pagerank_game_data = []
                for node_id, score in pagerank.items():
                    game = st.session_state.graph.nodes[node_id].get('game_name', 'Unknown')
                    pagerank_game_data.append({
                        'PageRank Score': score,
                        'Game': game
                    })
                
                pr_df = pd.DataFrame(pagerank_game_data)
                
                fig_pagerank_dist = px.histogram(
                    pr_df,
                    x='PageRank Score',
                    nbins=30,
                    color='Game',
                    title="PageRank Score Distribution by Game",
                    labels={'PageRank Score': 'PageRank Score', 'count': 'Frequency'},
                    barmode='stack',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_pagerank_dist.update_layout(
                    plot_bgcolor="#0f172a",
                    paper_bgcolor="#0f172a",
                    font_color="#e2e8f0",
                    hovermode='x unified'
                )
                st.plotly_chart(fig_pagerank_dist, width='stretch')
            
            # Language and additional insights
            st.markdown("---")
            st.subheader("Network Language & Metadata Distribution")
            
            lang_col1, lang_col2 = st.columns(2)
            
            with lang_col1:
                # Language distribution
                language_stats = {}
                for node_id, node_data in st.session_state.graph.nodes(data=True):
                    lang = node_data.get('language', 'Unknown')
                    language_stats[lang] = language_stats.get(lang, 0) + 1
                
                if language_stats:
                    lang_df = pd.DataFrame(list(language_stats.items()), columns=['Language', 'Count'])
                    lang_df = lang_df.sort_values('Count', ascending=False)
                    
                    fig_lang = px.bar(
                        lang_df,
                        x='Language',
                        y='Count',
                        title="Streamer Distribution by Language",
                        labels={'Count': 'Number of Streamers', 'Language': 'Language'},
                        color='Count',
                        color_continuous_scale='Purples'
                    )
                    fig_lang.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0",
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig_lang, width='stretch')
            
            with lang_col2:
                # Partner vs Non-Partner distribution
                partner_stats = {'Partner': 0, 'Non-Partner': 0}
                for node_id, node_data in st.session_state.graph.nodes(data=True):
                    if node_data.get('is_partner', False):
                        partner_stats['Partner'] += 1
                    else:
                        partner_stats['Non-Partner'] += 1
                
                partner_df = pd.DataFrame(list(partner_stats.items()), columns=['Status', 'Count'])
                
                fig_partner = px.pie(
                    partner_df,
                    values='Count',
                    names='Status',
                    title="Partner Status Distribution",
                    color_discrete_sequence=['#f59e0b', '#6366f1']
                )
                fig_partner.update_traces(textposition='inside', textinfo='label+percent+value')
                fig_partner.update_layout(
                    plot_bgcolor="#0f172a",
                    paper_bgcolor="#0f172a",
                    font_color="#e2e8f0"
                )
                st.plotly_chart(fig_partner, width='stretch')
            
            # Community composition
            
            if st.session_state.communities:
                selected_community = st.selectbox(
                    "Select a community to analyze",
                    list(st.session_state.communities.keys())
                )
                
                community_members = st.session_state.communities[selected_community]
                games_in_community = Counter()
                partners_in_community = 0
                
                for member in community_members:
                    node_data = st.session_state.graph.nodes[member]
                    game = node_data.get('game_name', 'Unknown')
                    games_in_community[game] += 1
                    if node_data.get('is_partner', False):
                        partners_in_community += 1
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Community Size", len(community_members))
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Partners", partners_in_community)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col3:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Unique Games", len(games_in_community))
                    st.markdown('</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Metric selector - what to visualize
                    viz_metric = st.selectbox(
                        "📊 What to Visualize",
                        ['Streamer Influence (Followers)', 'Live Viewership', 'Language Distribution', 
                         'Partner vs Non-Partner', 'Engagement Score', 'Network Centrality'],
                        help="Choose which metric to visualize for this community"
                    )
                    
                    # Chart type selector
                    chart_type = st.selectbox(
                        "🎨 Chart Type",
                        ['Bar Chart', 'Pie Chart', 'Treemap', 'Sunburst'],
                        help="Choose visualization style"
                    )
                    
                    # Enhanced data collection with ALL relevant metrics
                    community_data = []
                    for member in community_members:
                        node_data = st.session_state.graph.nodes[member]
                        
                        # Calculate engagement score
                        followers = node_data.get('follower_count', 0)
                        viewers = node_data.get('viewer_count', 0)
                        engagement = (viewers / max(followers, 1)) * 10000 if followers > 0 else 0
                        
                        # Determine per-node centrality score from available centrality metrics
                        centrality_score = 0
                        if st.session_state.centrality_scores:
                            # Prefer composite 'influence' if present, then pagerank, then degree, then any available metric
                            preferred = ['influence', 'pagerank', 'degree', 'betweenness', 'closeness', 'eigenvector', 'harmonic']
                            for metric_name in preferred:
                                metric_map = st.session_state.centrality_scores.get(metric_name)
                                if isinstance(metric_map, dict) and member in metric_map:
                                    centrality_score = metric_map.get(member, 0)
                                    break

                        community_data.append({
                            'Streamer': node_data.get('display_name', member),
                            'Game': node_data.get('game_name', 'Unknown'),
                            'Followers': followers,
                            'Viewers': viewers,
                            'Engagement': round(engagement, 2),
                            'Language': node_data.get('language', 'Unknown'),
                            'Partner': 'Partner' if node_data.get('is_partner', False) else 'Non-Partner',
                            'Live': node_data.get('is_live', False),
                            'Centrality': centrality_score
                        })
                    
                    df = pd.DataFrame(community_data)
                    
                    # Generate visualization based on selected metric
                    if viz_metric == 'Streamer Influence (Followers)':
                        plot_df = df.nlargest(15, 'Followers')[['Streamer', 'Followers', 'Game']].sort_values('Followers')
                        title = f"🌟 Top Influencers in Community {selected_community}"
                        
                        if chart_type == 'Bar Chart':
                            fig = px.bar(plot_df, y='Streamer', x='Followers', orientation='h',
                                       color='Followers', color_continuous_scale='Plasma',
                                       title=title, hover_data=['Game'])
                        elif chart_type == 'Pie Chart':
                            fig = px.pie(plot_df, values='Followers', names='Streamer', title=title,
                                       color_discrete_sequence=px.colors.sequential.Plasma)
                            fig.update_traces(textposition='inside', textinfo='label+percent')
                        elif chart_type == 'Treemap':
                            fig = px.treemap(plot_df, path=['Streamer'], values='Followers',
                                           color='Followers', title=title, color_continuous_scale='Plasma')
                        else:
                            plot_df['Community'] = f'Community {selected_community}'
                            fig = px.sunburst(plot_df, path=['Community', 'Streamer'], values='Followers',
                                            color='Followers', title=title, color_continuous_scale='Plasma')
                    
                    elif viz_metric == 'Live Viewership':
                        live_df = df[df['Live'] == True]
                        if len(live_df) > 0:
                            plot_df = live_df.nlargest(15, 'Viewers')[['Streamer', 'Viewers', 'Game']].sort_values('Viewers')
                            title = f"🔴 Live Viewership in Community {selected_community}"
                            
                            if chart_type == 'Bar Chart':
                                fig = px.bar(plot_df, y='Streamer', x='Viewers', orientation='h',
                                           color='Viewers', color_continuous_scale='Reds',
                                           title=title, hover_data=['Game'])
                            elif chart_type == 'Pie Chart':
                                fig = px.pie(plot_df, values='Viewers', names='Streamer', title=title,
                                           color_discrete_sequence=px.colors.sequential.Reds)
                                fig.update_traces(textposition='inside', textinfo='label+percent')
                            elif chart_type == 'Treemap':
                                fig = px.treemap(plot_df, path=['Streamer'], values='Viewers',
                                               color='Viewers', title=title, color_continuous_scale='Reds')
                            else:
                                plot_df['Community'] = f'Community {selected_community}'
                                fig = px.sunburst(plot_df, path=['Community', 'Streamer'], values='Viewers',
                                                color='Viewers', title=title, color_continuous_scale='Reds')
                        else:
                            st.info("No streamers currently live in this community")
                            fig = None
                    
                    elif viz_metric == 'Language Distribution':
                        lang_df = df.groupby('Language').agg({
                            'Followers': 'sum',
                            'Streamer': 'count',
                            'Viewers': 'sum'
                        }).reset_index()
                        lang_df.columns = ['Language', 'Total Followers', 'Streamer Count', 'Total Viewers']
                        lang_df = lang_df.sort_values('Total Followers', ascending=False)
                        title = f"🌍 Language Distribution in Community {selected_community}"
                        
                        if chart_type == 'Bar Chart':
                            fig = px.bar(lang_df, y='Language', x='Total Followers', orientation='h',
                                       color='Streamer Count', color_continuous_scale='Teal',
                                       title=title, hover_data=['Streamer Count', 'Total Viewers'])
                        elif chart_type == 'Pie Chart':
                            fig = px.pie(lang_df, values='Streamer Count', names='Language', title=title,
                                       color_discrete_sequence=px.colors.sequential.Teal)
                            fig.update_traces(textposition='inside', textinfo='label+percent')
                        elif chart_type == 'Treemap':
                            fig = px.treemap(lang_df, path=['Language'], values='Total Followers',
                                           color='Streamer Count', title=title, color_continuous_scale='Teal')
                        else:
                            lang_df['Community'] = f'Community {selected_community}'
                            fig = px.sunburst(lang_df, path=['Community', 'Language'], values='Total Followers',
                                            color='Streamer Count', title=title, color_continuous_scale='Teal')
                    
                    elif viz_metric == 'Partner vs Non-Partner':
                        partner_df = df.groupby('Partner').agg({
                            'Followers': ['sum', 'mean'],
                            'Streamer': 'count',
                            'Viewers': 'sum'
                        }).reset_index()
                        partner_df.columns = ['Status', 'Total Followers', 'Avg Followers', 'Count', 'Total Viewers']
                        title = f"⭐ Partner Status Analysis in Community {selected_community}"
                        
                        if chart_type in ['Bar Chart', 'Treemap', 'Sunburst']:
                            fig = px.bar(partner_df, x='Status', y='Total Followers',
                                       color='Status', title=title,
                                       color_discrete_map={'Partner': '#ffd60a', 'Non-Partner': '#6366f1'},
                                       hover_data=['Count', 'Avg Followers', 'Total Viewers'])
                        else:
                            fig = px.pie(partner_df, values='Count', names='Status', title=title,
                                       color='Status',
                                       color_discrete_map={'Partner': '#ffd60a', 'Non-Partner': '#6366f1'})
                            fig.update_traces(textposition='inside', textinfo='label+percent+value')
                    
                    elif viz_metric == 'Engagement Score':
                        # Filter out zero engagement
                        engagement_df = df[df['Engagement'] > 0].copy()
                        if len(engagement_df) > 0:
                            plot_df = engagement_df.nlargest(15, 'Engagement')[['Streamer', 'Engagement', 'Viewers', 'Followers']].sort_values('Engagement')
                            title = f"🔥 Top Engagement Rates in Community {selected_community}"
                            
                            if chart_type == 'Bar Chart':
                                fig = px.bar(plot_df, y='Streamer', x='Engagement', orientation='h',
                                           color='Engagement', color_continuous_scale='Hot',
                                           title=title, hover_data=['Viewers', 'Followers'])
                            elif chart_type == 'Pie Chart':
                                fig = px.pie(plot_df, values='Engagement', names='Streamer', title=title,
                                           color_discrete_sequence=px.colors.sequential.Hot)
                                fig.update_traces(textposition='inside', textinfo='label+percent')
                            elif chart_type == 'Treemap':
                                fig = px.treemap(plot_df, path=['Streamer'], values='Engagement',
                                               color='Engagement', title=title, color_continuous_scale='Hot')
                            else:
                                plot_df['Community'] = f'Community {selected_community}'
                                fig = px.sunburst(plot_df, path=['Community', 'Streamer'], values='Engagement',
                                                color='Engagement', title=title, color_continuous_scale='Hot')
                        else:
                            st.info("No engagement data available (streamers need to be live)")
                            fig = None
                    
                    else:  # Network Centrality
                        if st.session_state.centrality_scores and len(st.session_state.centrality_scores) > 0:
                            # Filter to only include nodes with centrality > 0
                            centrality_df = df[df['Centrality'] > 0].copy()
                            if len(centrality_df) > 0:
                                plot_df = centrality_df.nlargest(15, 'Centrality')[['Streamer', 'Centrality', 'Game']].sort_values('Centrality')
                                title = f"🕸️ Network Centrality in Community {selected_community}"
                                
                                if chart_type == 'Bar Chart':
                                    fig = px.bar(plot_df, y='Streamer', x='Centrality', orientation='h',
                                               color='Centrality', color_continuous_scale='Viridis',
                                               title=title, hover_data=['Game'])
                                elif chart_type == 'Pie Chart':
                                    fig = px.pie(plot_df, values='Centrality', names='Streamer', title=title,
                                               color_discrete_sequence=px.colors.sequential.Viridis)
                                    fig.update_traces(textposition='inside', textinfo='label+percent')
                                elif chart_type == 'Treemap':
                                    fig = px.treemap(plot_df, path=['Streamer'], values='Centrality',
                                                   color='Centrality', title=title, color_continuous_scale='Viridis')
                                else:
                                    plot_df['Community'] = f'Community {selected_community}'
                                    fig = px.sunburst(plot_df, path=['Community', 'Streamer'], values='Centrality',
                                                    color='Centrality', title=title, color_continuous_scale='Viridis')
                            else:
                                st.info("No centrality data available for this community")
                                fig = None
                        else:
                            st.info("Centrality scores not calculated. Run network analysis first.")
                            fig = None
                    
                    # Display the chart
                    if fig:
                        fig.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            height=500
                        )
                        st.plotly_chart(fig, width='stretch')
                    
                    # Show summary stats table based on visualization
                    st.markdown("**📋 Detailed Breakdown:**")
                    
                    # Show different table based on metric
                    if viz_metric == 'Language Distribution':
                        lang_summary = df.groupby('Language').agg({
                            'Followers': ['sum', 'mean'],
                            'Viewers': ['sum', 'mean'],
                            'Streamer': 'count',
                            'Partner': lambda x: (x == 'Partner').sum()
                        }).round(0)
                        lang_summary.columns = ['Total Followers', 'Avg Followers', 'Total Viewers', 'Avg Viewers', 'Streamers', 'Partners']
                        st.dataframe(lang_summary, width='stretch', height=250)
                    elif viz_metric == 'Partner vs Non-Partner':
                        partner_summary = df.groupby('Partner').agg({
                            'Followers': ['sum', 'mean', 'median'],
                            'Viewers': ['sum', 'mean'],
                            'Streamer': 'count'
                        }).round(0)
                        partner_summary.columns = ['Total Followers', 'Avg Followers', 'Median Followers', 'Total Viewers', 'Avg Viewers', 'Count']
                        st.dataframe(partner_summary, width='stretch', height=150)
                    else:
                        # Top performers table
                        top_df = df.nlargest(10, 'Followers' if viz_metric == 'Streamer Influence (Followers)' else 
                                            'Viewers' if viz_metric == 'Live Viewership' else
                                            'Engagement' if viz_metric == 'Engagement Score' else 'Centrality')
                        display_cols = ['Streamer', 'Game', 'Followers', 'Viewers', 'Language', 'Partner']
                        st.dataframe(top_df[display_cols], width='stretch', height=250, hide_index=True)
                
                with col2:
                    st.markdown("**👥 Community Members (Detailed)**")
                    members_list = [
                        {
                            'Rank': idx + 1,
                            'Streamer': st.session_state.graph.nodes[m].get('display_name', m),
                            'Game': st.session_state.graph.nodes[m].get('game_name', 'Unknown'),
                            'Followers': st.session_state.graph.nodes[m].get('follower_count', 0),
                            'Viewers': st.session_state.graph.nodes[m].get('viewer_count', 0),
                            'Language': st.session_state.graph.nodes[m].get('language', 'Unknown'),
                            'Partner': '⭐' if st.session_state.graph.nodes[m].get('is_partner', False) else '',
                            'Live': '🔴' if st.session_state.graph.nodes[m].get('is_live', False) else ''
                        }
                        for idx, m in enumerate(sorted(
                            community_members,
                            key=lambda x: st.session_state.graph.nodes[x].get('follower_count', 0),
                            reverse=True
                        ))
                    ]
                    members_df = pd.DataFrame(members_list)
                    
                    st.dataframe(
                        members_df,
                        width='stretch',
                        height=650,
                        hide_index=True,
                        column_config={
                            'Rank': st.column_config.NumberColumn(width='small'),
                            'Followers': st.column_config.NumberColumn(format='%d'),
                            'Viewers': st.column_config.NumberColumn(format='%d'),
                            'Partner': st.column_config.TextColumn(width='small'),
                            'Live': st.column_config.TextColumn(width='small')
                        }
                    )
            
            # ============ ADVANCED COMMUNITY INSIGHTS ============
            st.markdown("---")
            st.markdown("### 🔬 Advanced Community Analytics")
            
            if st.session_state.communities:
                detector = CommunityDetector(st.session_state.graph)
                detector.communities = st.session_state.communities
                detector.partition = {node: comm for comm, members in st.session_state.communities.items() for node in members}
                
                tab1, tab2, tab3 = st.tabs(["🏥 Community Health", "🌉 Bridge Nodes", "📊 Cross-Game Analysis"])
                
                with tab1:
                    st.markdown("#### Community Health Metrics")
                    st.markdown("Comprehensive health scores based on diversity, engagement, and network structure")
                    
                    health_df = detector.get_all_health_metrics()
                    
                    if not health_df.empty:
                        # Display top communities by health
                        st.markdown("**Top Communities by Health Score:**")
                        top_health = health_df.head(10)
                        
                        fig_health = px.bar(
                            top_health,
                            x='community_id',
                            y='health_score',
                            color='health_score',
                            title="Community Health Scores (Top 10)",
                            labels={'community_id': 'Community ID', 'health_score': 'Health Score (0-100)'},
                            color_continuous_scale='RdYlGn',
                            hover_data=['size', 'game_diversity', 'partner_ratio']
                        )
                        fig_health.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0"
                        )
                        st.plotly_chart(fig_health, width='stretch')
                        
                        # Detailed health metrics table
                        st.markdown("**Detailed Health Metrics:**")
                        st.dataframe(health_df, width='stretch', height=400)
                        
                        # Health component breakdown
                        col1, col2 = st.columns(2)
                        with col1:
                            fig_diversity = px.scatter(
                                health_df,
                                x='game_diversity',
                                y='language_diversity',
                                size='size',
                                color='health_score',
                                title="Diversity Analysis",
                                labels={'game_diversity': 'Game Diversity', 'language_diversity': 'Language Diversity'},
                                color_continuous_scale='Viridis',
                                hover_data=['community_id']
                            )
                            fig_diversity.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e2e8f0")
                            st.plotly_chart(fig_diversity, width='stretch')
                        
                        with col2:
                            fig_engagement = px.scatter(
                                health_df,
                                x='network_density',
                                y='partner_ratio',
                                size='avg_followers',
                                color='health_score',
                                title="Engagement & Network Structure",
                                labels={'network_density': 'Network Density', 'partner_ratio': 'Partner Ratio'},
                                color_continuous_scale='Plasma',
                                hover_data=['community_id']
                            )
                            fig_engagement.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e2e8f0")
                            st.plotly_chart(fig_engagement, width='stretch')
                
                with tab2:
                    st.markdown("#### Bridge Nodes: Community Connectors")
                    st.markdown("Streamers who connect multiple communities and facilitate cross-pollination")
                    
                    min_connections = st.slider("Minimum Communities Connected", 2, 5, 2)
                    bridges = detector.identify_bridge_nodes(min_communities=min_connections)
                    
                    if bridges:
                        st.success(f"Found {len(bridges)} bridge nodes connecting {min_connections}+ communities")
                        
                        # Top bridges visualization
                        bridge_df = pd.DataFrame(bridges[:20])
                        
                        fig_bridges = px.bar(
                            bridge_df,
                            x='display_name',
                            y='bridge_score',
                            color='connected_communities',
                            title="Top Bridge Nodes by Influence",
                            labels={'display_name': 'Streamer', 'bridge_score': 'Bridge Influence Score'},
                            color_continuous_scale='Sunset',
                            hover_data=['follower_count', 'connected_communities']
                        )
                        fig_bridges.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            xaxis_tickangle=-45
                        )
                        st.plotly_chart(fig_bridges, width='stretch')
                        
                        # Detailed bridge table
                        st.markdown("**Bridge Node Details:**")
                        bridge_display = pd.DataFrame(bridges)
                        st.dataframe(
                            bridge_display[['display_name', 'connected_communities', 'follower_count', 'bridge_score']],
                            width='stretch',
                            height=400
                        )
                    else:
                        st.info(f"No streamers connecting {min_connections}+ communities found. Try lowering the threshold.")
                
                with tab3:
                    st.markdown("#### Cross-Game Communities")
                    st.markdown("Communities that span multiple game categories")
                    
                    cross_game = detector.detect_cross_game_communities()
                    
                    if cross_game:
                        st.success(f"Found {len(cross_game)} cross-game community bridges")
                        
                        # Visualize cross-game connections
                        cross_game_data = []
                        for game_pair, comm_ids in cross_game.items():
                            for comm_id in comm_ids:
                                comm_size = len(detector.communities[comm_id])
                                cross_game_data.append({
                                    'Game Bridge': game_pair,
                                    'Community ID': comm_id,
                                    'Size': comm_size
                                })
                        
                        cross_df = pd.DataFrame(cross_game_data)
                        
                        fig_cross = px.bar(
                            cross_df,
                            x='Game Bridge',
                            y='Size',
                            color='Community ID',
                            title="Cross-Game Community Sizes",
                            labels={'Size': 'Community Size', 'Game Bridge': 'Game Pair'},
                            color_continuous_scale='Teal'
                        )
                        fig_cross.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            xaxis_tickangle=-45
                        )
                        st.plotly_chart(fig_cross, width='stretch')
                        
                        # Detailed breakdown
                        st.markdown("**Cross-Game Community Details:**")
                        for game_pair, comm_ids in cross_game.items():
                            with st.expander(f"🎮 {game_pair} ({len(comm_ids)} communities)"):
                                for comm_id in comm_ids:
                                    members = detector.communities[comm_id]
                                    st.write(f"**Community {comm_id}** - {len(members)} members")
                                    
                                    # Show game distribution in this cross-game community
                                    games = [st.session_state.graph.nodes[m].get('game_name', 'Unknown') for m in members]
                                    game_counts = pd.Series(games).value_counts()
                                    st.write(game_counts)
                    else:
                        st.info("No cross-game communities detected. Communities are highly game-specific.")
            
            # ============ ADVANCED VISUALIZATIONS ============
            st.markdown("---")
            st.markdown("### 🎨 Advanced Visualizations")
            
            viz_tab1, viz_tab2, viz_tab3, viz_tab4 = st.tabs([
                "🌐 3D Network",
                "📊 Interactive Filters", 
                "🌍 Geographic Map",
                "📈 Centrality Profiles"
            ])
            
            with viz_tab1:
                st.markdown("#### 3D Network Visualization")
                st.markdown("Explore the network in three dimensions with interactive rotation and zoom")
                
                color_option = st.selectbox(
                    "Color nodes by",
                    ['community', 'centrality', 'game'],
                    format_func=lambda x: {
                        'community': '👥 Community',
                        'centrality': '⭐ Centrality (PageRank)',
                        'game': '🎮 Game'
                    }[x]
                )
                
                if st.button("Generate 3D Visualization", type="primary"):
                    with st.spinner("Rendering 3D network..."):
                        visualizer = AdvancedVisualizer(st.session_state.graph)
                        fig_3d = visualizer.create_3d_network(
                            centrality_scores=st.session_state.centrality_scores,
                            communities=st.session_state.communities,
                            color_by=color_option
                        )
                        
                        if fig_3d:
                            st.plotly_chart(fig_3d, width='stretch', height=700)
                            st.info("💡 Drag to rotate, scroll to zoom, click nodes for details")
                        else:
                            st.error("Failed to generate 3D visualization")
            
            with viz_tab2:
                st.markdown("#### Interactive Network Filtering")
                st.markdown("Filter the network in real-time and see immediate visual updates")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.session_state.streamers_data:
                        df = pd.DataFrame(st.session_state.streamers_data)
                        min_f = int(df['follower_count'].min())
                        max_f = int(df['follower_count'].max())
                        
                        follower_range = st.slider(
                            "Follower Count Range",
                            min_value=min_f,
                            max_value=max_f,
                            value=(min_f, max_f),
                            format="%d"
                        )
                        
                        # Get unique games
                        all_games = df['game_name'].unique().tolist()
                        selected_games = st.multiselect(
                            "Filter by Games",
                            all_games,
                            default=all_games[:5] if len(all_games) > 5 else all_games
                        )
                
                with col2:
                    st.markdown("**Filter Results:**")
                    
                    if st.button("Apply Filters", type="primary"):
                        visualizer = AdvancedVisualizer(st.session_state.graph)
                        filtered_graph = visualizer.create_interactive_filter_network(
                            min_followers=follower_range[0],
                            max_followers=follower_range[1],
                            games=selected_games if selected_games else None
                        )
                        
                        if filtered_graph:
                            st.success(f"✅ Filtered network: {filtered_graph.number_of_nodes()} nodes, {filtered_graph.number_of_edges()} edges")
                            
                            # Show filtered stats
                            st.metric("Nodes Remaining", filtered_graph.number_of_nodes())
                            st.metric("Edges Remaining", filtered_graph.number_of_edges())
                            st.metric("Density", f"{nx.density(filtered_graph):.4f}")
                            
                            # Visualize filtered network
                            visualizer_filtered = AdvancedVisualizer(filtered_graph)
                            fig_filtered = visualizer_filtered.create_3d_network(
                                color_by='game'
                            )
                            
                            if fig_filtered:
                                st.plotly_chart(fig_filtered, width='stretch', height=500)
                        else:
                            st.warning("No nodes match the filter criteria")
            
            with viz_tab3:
                st.markdown("#### Geographic Distribution")
                st.markdown("Visualize streamer locations by language/region")
                
                if st.session_state.streamers_data:
                    df = pd.DataFrame(st.session_state.streamers_data)
                    visualizer = AdvancedVisualizer()
                    
                    fig_geo = visualizer.create_geographic_heatmap(df)
                    
                    if fig_geo:
                        st.plotly_chart(fig_geo, width='stretch', height=500)
                        
                        # Language breakdown
                        st.markdown("**Language Distribution:**")
                        if 'language' in df.columns:
                            lang_stats = df['language'].value_counts()
                            lang_df = pd.DataFrame({
                                'Language': lang_stats.index,
                                'Count': lang_stats.values,
                                'Percentage': (lang_stats.values / len(df) * 100).round(1)
                            })
                            st.dataframe(lang_df, width='stretch')
                    else:
                        st.info("Language data not available for geographic mapping")
                else:
                    st.warning("No streamer data available")
            
            with viz_tab4:
                st.markdown("#### Centrality Profile Analysis")
                st.markdown("Compare centrality metrics for individual streamers")
                
                if st.session_state.centrality_scores and st.session_state.streamers_data:
                    # Get list of streamers
                    df = pd.DataFrame(st.session_state.streamers_data)
                    streamer_options = {
                        f"{row['display_name']} (@{row['username']})": row['user_id']
                        for _, row in df.iterrows()
                    }
                    
                    selected_streamer = st.selectbox(
                        "Select Streamer to Analyze",
                        list(streamer_options.keys())
                    )
                    
                    if selected_streamer:
                        user_id = streamer_options[selected_streamer]
                        
                        # Create radar chart
                        visualizer = AdvancedVisualizer()
                        fig_radar = visualizer.create_centrality_radar(
                            user_id,
                            st.session_state.centrality_scores
                        )
                        
                        if fig_radar:
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                st.plotly_chart(fig_radar, width='stretch')
                            
                            with col2:
                                st.markdown("**Centrality Scores:**")
                                for metric, scores in st.session_state.centrality_scores.items():
                                    if user_id in scores:
                                        st.write(f"**{metric.replace('_', ' ').title()}:** {scores[user_id]:.4f}")
                                
                                # Show streamer info
                                streamer_data = df[df['user_id'] == user_id].iloc[0]
                                st.markdown("---")
                                st.markdown("**Streamer Info:**")
                                st.write(f"**Game:** {streamer_data.get('game_name', 'Unknown')}")
                                st.write(f"**Followers:** {streamer_data.get('follower_count', 0):,}")
                                st.write(f"**Language:** {streamer_data.get('language', 'Unknown')}")
                else:
                    st.warning("Centrality scores not calculated yet")
