import streamlit as st
import pandas as pd
import json
import asyncio
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from collections import Counter
import traceback

from config import Config
from twitch_api import TwitchDataCollector
from graph_builder import StreamerNetworkBuilder
from centrality import CentralityAnalyzer
from community_detection import CommunityDetector
from similarity_calc import FeatureExtractor, SimilarityCalculator
from recommender import StreamerRecommender
from company_profiles import CompanyProfile, CompanyProfileManager
from network_viz import NetworkVisualizer
from scoring import AdvancedScorer
from dashboard import DashboardMetrics
from database import DatabaseManager
from advanced_viz import AdvancedVisualizer
from styles import CUSTOM_CSS, HEADER_HTML
import os

# Page configuration
st.set_page_config(
    page_title="TwitchNet Analytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Apply custom CSS on every rerun (Streamlit clears HTML on each run)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(HEADER_HTML, unsafe_allow_html=True)

# Initialize enhanced session state
if 'streamers_data' not in st.session_state:
    st.session_state.streamers_data = None
if 'graph' not in st.session_state:
    st.session_state.graph = None
if 'centrality_scores' not in st.session_state:
    st.session_state.centrality_scores = None
if 'communities' not in st.session_state:
    st.session_state.communities = None
if 'network_metrics' not in st.session_state:
    st.session_state.network_metrics = None
if 'advanced_scores' not in st.session_state:
    st.session_state.advanced_scores = None
if 'last_recommendations' not in st.session_state:
    st.session_state.last_recommendations = None
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()
if 'current_graph_id' not in st.session_state:
    st.session_state.current_graph_id = None

# Create directories
try:
    Config.create_directories()
except Exception as e:
    st.error(f"Failed to create directories: {str(e)}")

# Twitch-style top navigation
st.markdown("""
<style>
.stButton button {
    background: linear-gradient(135deg, rgba(0,255,218,0.15), rgba(138,43,226,0.15)) !important;
    border: 1px solid rgba(0,255,218,0.3) !important;
    border-radius: 12px !important;
    color: #e8ecf4 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.3s ease !important;
    text-transform: none !important;
    white-space: nowrap !important;
    min-width: auto !important;
}
.stButton button:hover {
    background: linear-gradient(135deg, rgba(0,255,218,0.25), rgba(138,43,226,0.25)) !important;
    border-color: #00ffda !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(0,255,218,0.3) !important;
}
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #00ffda, #8a2be2) !important;
    border-color: #00ffda !important;
    color: #0a0e1a !important;
    box-shadow: 0 4px 12px rgba(0,255,218,0.4) !important;
}
</style>
""", unsafe_allow_html=True)

# Initialize page in session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'

# Top navigation buttons - centered with proper spacing
col_left, col1, col2, col3, col4, col5, col_right = st.columns([1, 1, 1.3, 1.3, 1.3, 1, 1])

# Top navigation buttons - centered with proper spacing
col_left, col1, col2, col3, col4, col5, col_right = st.columns([1, 1, 1.3, 1.3, 1.3, 1, 1])

with col1:
    if st.button("HOME", width='stretch', type="primary" if st.session_state.current_page == 'Home' else "secondary"):
        st.session_state.current_page = 'Home'

with col2:
    if st.button("DATA COLLECTION", width='stretch', type="primary" if st.session_state.current_page == 'Data Collection' else "secondary"):
        st.session_state.current_page = 'Data Collection'

with col3:
    if st.button("NETWORK ANALYSIS", width='stretch', type="primary" if st.session_state.current_page == 'Network Analysis' else "secondary"):
        st.session_state.current_page = 'Network Analysis'

with col4:
    if st.button("RECOMMENDATIONS", width='stretch', type="primary" if st.session_state.current_page == 'Recommendations' else "secondary"):
        st.session_state.current_page = 'Recommendations'

with col5:
    if st.button("ANALYTICS", width='stretch', type="primary" if st.session_state.current_page == 'Analytics' else "secondary"):
        st.session_state.current_page = 'Analytics'

page = st.session_state.current_page
st.markdown("---")

# ==================== PERSISTENCE CONTROLS (Top) ====================
with st.expander("Quick Data Management", expanded=False):
    # Cache DB stats (refresh on button click)
    if 'db_stats' not in st.session_state:
        st.session_state.db_stats = st.session_state.db.get_stats()
    
    db_stats = st.session_state.db_stats
    
    col_stats1, col_stats2, col_stats3, col_stats4, col_refresh = st.columns([1,1,1,1,0.5])
    with col_stats1:
        st.metric("Streamers", db_stats['total_streamers'], label_visibility="visible")
    with col_stats2:
        st.metric("Graphs", db_stats['total_graphs'], label_visibility="visible")
    with col_stats3:
        st.metric("Cache", db_stats.get('active_cache_entries', 0), label_visibility="visible")
    with col_stats4:
        st.metric("DB Size", f"{db_stats.get('database_size_mb', 0)} MB", label_visibility="visible")
    with col_refresh:
        if st.button("Refresh", help="Refresh stats", key="refresh_stats_btn"):
            st.session_state.db_stats = st.session_state.db.get_stats()

# ==================== HOME PAGE ====================
if page == "Home":
    st.markdown("<h2 style='text-align: center;'>Welcome to TwitchNet Analytics</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #9ca3af; font-size: 1rem; margin-bottom: 2rem;'>Comprehensive influencer network intelligence platform</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            "Streamers Collected",
            len(st.session_state.streamers_data) if st.session_state.streamers_data else 0
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            "Network Nodes",
            st.session_state.graph.number_of_nodes() if st.session_state.graph else 0
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            "Communities Found",
            len(st.session_state.communities) if st.session_state.communities else 0
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Project Overview")
    st.write("""
This dashboard uses Social Network Analysis to match companies with niche Twitch streamers:

- Data collection from Twitch API
- Network graph construction with NetworkX
- Centrality analysis and community detection
- Hybrid content + network based recommendation engine
- Interactive visualization and exports
""")
    
    st.markdown("---")
    st.subheader("📦 Data Management")
    
    man_col1, man_col2, man_col3 = st.columns(3)
    
    with man_col1:
        st.markdown("**💾 Save Current State**")
        if st.button("Save Everything", width='stretch', type="primary"):
            saved_items = []
            
            if st.session_state.streamers_data:
                count = st.session_state.db.save_streamers(st.session_state.streamers_data)
                saved_items.append(f"{count} streamers")
            
            if st.session_state.graph:
                from datetime import datetime
                graph_id = st.session_state.db.save_graph(
                    st.session_state.graph,
                    f"graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    f"{st.session_state.graph.number_of_nodes()} nodes"
                )
                st.session_state.current_graph_id = graph_id
                saved_items.append("graph")
                
                if st.session_state.centrality_scores:
                    st.session_state.db.save_centrality_scores(
                        st.session_state.centrality_scores, graph_id
                    )
                    saved_items.append("centrality")
                
                if st.session_state.communities:
                    st.session_state.db.save_communities(
                        st.session_state.communities, graph_id
                    )
                    saved_items.append("communities")
            
            if saved_items:
                st.success(f"✅ Saved: {', '.join(saved_items)}")
            else:
                st.warning("Nothing to save yet!")
    
    with man_col2:
        st.markdown("**📂 Load Saved State**")
        saved_graphs = st.session_state.db.list_graphs()
        
        if saved_graphs:
            graph_options = {
                f"Graph #{g['graph_id']} ({g['node_count']} nodes) - {g['created_at'][:10]}": g['graph_id']
                for g in saved_graphs
            }
            
            selected = st.selectbox("Select graph to load", list(graph_options.keys()))
            
            if st.button("Load Selected", width='stretch'):
                graph_id = graph_options[selected]
                
                # Load streamers
                streamers = st.session_state.db.load_streamers()
                st.session_state.streamers_data = streamers
                
                # Load graph
                graph, _ = st.session_state.db.load_graph(graph_id=graph_id)
                st.session_state.graph = graph
                st.session_state.current_graph_id = graph_id
                
                # Load associated data
                st.session_state.centrality_scores = st.session_state.db.load_centrality_scores(graph_id)
                st.session_state.communities = st.session_state.db.load_communities(graph_id)
                
                st.success(f"✅ Loaded graph #{graph_id}")
                st.rerun()
        else:
            st.info("No saved graphs yet")
    
    with man_col3:
        st.markdown("**📤 Export/Import**")
        
        if st.button("Export to JSON", width='stretch'):
            export_file = f"{Config.PROCESSED_DATA_DIR}/export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
            st.session_state.db.export_to_json(export_file)
            
            with open(export_file, 'r') as f:
                st.download_button(
                    "Download Export",
                    f.read(),
                    file_name=f"twitchnet_export_{pd.Timestamp.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    width='stretch'
                )
        
        st.markdown("**🗑️ Cache Management**")
        if st.button("Clear Expired Cache", width='stretch'):
            deleted = st.session_state.db.clear_expired_cache()
            st.info(f"Cleared {deleted} expired entries")


# ==================== DATA COLLECTION PAGE ====================
elif page == "Data Collection":
    st.markdown("<h2>Data Collection</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #9ca3af; margin-bottom: 1.5rem;'>Collect streamer data from Twitch API</p>", unsafe_allow_html=True)

    # Load existing data option
    if os.path.exists(f"{Config.RAW_DATA_DIR}/streamers.json"):
        if st.button("Load Existing Data"):
            with open(f"{Config.RAW_DATA_DIR}/streamers.json", 'r', encoding="utf-8") as f:
                st.session_state.streamers_data = json.load(f)
            st.success(f"Loaded {len(st.session_state.streamers_data)} streamers from file")

    st.subheader("Fetch New Twitch Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        game_categories = st.multiselect(
            "Select Game Categories",
            [
                # Battle Royale & Shooters
                'Fortnite', 'Apex Legends', 'Call of Duty: Warzone', 'PUBG: BATTLEGROUNDS',
                'Call of Duty: Modern Warfare III', 'Call of Duty: Black Ops 6',
                
                # MOBA & Strategy
                'League of Legends', 'Dota 2', 'VALORANT', 'Teamfight Tactics',
                
                # FPS
                'Counter-Strike 2', 'CS:GO', 'Overwatch 2', 'Rainbow Six Siege',
                'Escape from Tarkov', 'The Finals',
                
                # Survival & Sandbox
                'Minecraft', 'Rust', 'ARK: Survival Evolved', 'Terraria', 'Palworld',
                
                # RPG & MMO
                'World of Warcraft', 'Final Fantasy XIV', 'Path of Exile', 'Diablo IV',
                'Elden Ring', 'Baldur\'s Gate 3', 'Old School RuneScape',
                
                # Sports & Racing
                'EA Sports FC 24', 'NBA 2K24', 'Rocket League', 'Gran Turismo 7',
                
                # Fighting Games
                'Street Fighter 6', 'Tekken 8', 'Mortal Kombat 1', 'Super Smash Bros. Ultimate',
                
                # Card & Auto Chess
                'Hearthstone', 'Marvel Snap', 'Yu-Gi-Oh! Master Duel', 'Legends of Runeterra',
                
                # Horror & Story
                'Dead by Daylight', 'Phasmophobia', 'Resident Evil', 'Silent Hill 2',
                
                # Indie & Creative
                'Stardew Valley', 'Lethal Company', 'Among Us', 'Fall Guys',
                
                # Mobile
                'Mobile Legends: Bang Bang', 'Genshin Impact', 'Honkai: Star Rail',
                
                # Just Chatting & IRL
                'Just Chatting', 'Music', 'Art', 'Slots', 'Poker', 'Chess',
                
                # Other Popular
                'Grand Theft Auto V', 'Roblox', 'Garry\'s Mod', 'Sea of Thieves'
            ],
            default=['League of Legends', 'VALORANT']
        )
        streamers_per_game = st.slider("Streamers per game", 5, 50, 20)
    
    with col2:
        enable_language_diversity = st.checkbox("Enable Language Diversity", value=True, 
                                                 help="Fetches streamers from multiple languages (English, Spanish, French, German, Portuguese, Japanese, Korean)")
        if enable_language_diversity:
            st.info("🌍 Will fetch diverse language representation")

    if st.button("Fetch Data from Twitch", type="primary"):
        async def fetch_data():
            collector = TwitchDataCollector(
                Config.TWITCH_CLIENT_ID,
                Config.TWITCH_CLIENT_SECRET
            )
            await collector.initialize()

            all_streamers = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, game in enumerate(game_categories):
                status_text.text(f"🎮 Fetching {game} streamers... ({idx + 1}/{len(game_categories)})")
                
                if enable_language_diversity:
                    # Fetch diverse language streamers
                    streamers = await collector.get_diverse_streamers(game, max_per_language=max(5, streamers_per_game // 3))
                else:
                    # Fetch top streamers (mostly English)
                    streamers = await collector.get_top_streamers(game, streamers_per_game)
                
                all_streamers.extend(streamers)
                progress_bar.progress((idx + 1) / len(game_categories))
                status_text.text(f"✅ Collected {len(all_streamers)} streamers so far...")

            status_text.text(f"💾 Saving data...")
            collector.save_data(all_streamers, 'streamers.json')
            await collector.close()
            progress_bar.progress(1.0)
            status_text.text(f"✅ Complete! Collected {len(all_streamers)} streamers")
            return all_streamers

        with st.spinner("Collecting data from Twitch..."):
            st.session_state.streamers_data = asyncio.run(fetch_data())

        st.success(f"🎉 Collected {len(st.session_state.streamers_data)} streamers from {len(game_categories)} games")
        
        # Auto-save to database
        with st.spinner("Saving to database..."):
            from datetime import datetime
            saved_count = st.session_state.db.save_streamers(st.session_state.streamers_data)
            
            # Save collection session
            st.session_state.db.save_session(
                games=game_categories,
                streamer_count=len(st.session_state.streamers_data),
                language_diversity=enable_language_diversity,
                started_at=datetime.now(),
                completed_at=datetime.now()
            )
        
        st.info(f"💾 Auto-saved {saved_count} streamers to database")

    if st.session_state.streamers_data:
        st.subheader("📊 Collected Streamers")
        df = pd.DataFrame(st.session_state.streamers_data)
        
        # Show summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Streamers", len(df))
        with col2:
            st.metric("Live Now", df['is_live'].sum() if 'is_live' in df.columns else 0)
        with col3:
            st.metric("Languages", df['language'].nunique() if 'language' in df.columns else 0)
        with col4:
            st.metric("Partners", df['is_partner'].sum() if 'is_partner' in df.columns else 0)
        
        # Enhanced dataframe with more columns
        display_columns = ['display_name', 'game_name', 'follower_count', 'language', 'is_partner']
        if 'viewer_count' in df.columns:
            display_columns.insert(3, 'viewer_count')
        if 'is_live' in df.columns:
            display_columns.insert(3, 'is_live')
        
        st.dataframe(
            df[display_columns],
            width='stretch'
        )

        csv = df.to_csv(index=False)
        st.download_button(
            "Download as CSV",
            csv,
            "streamers_data.csv",
            "text/csv"
        )


# ==================== NETWORK ANALYSIS PAGE ====================
elif page == "Network Analysis":
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
                    builder.build_comprehensive_network(use_all_methods=True)
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
            import random
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
                import statistics
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

            net = Network(
                height="650px",
                width="100%",
                bgcolor="#0f0e17",
                font_color="#e6e6e6",
                directed=False
            )

            # Static hierarchical layout like the reference images
            net.set_options("""
            var options = {
              "physics": {
                "enabled": false
              },
              "layout": {
                "improvedLayout": true,
                "hierarchical": {
                  "enabled": false
                }
              },
              "interaction": {
                "hover": true,
                "tooltipDelay": 100,
                "zoomView": true,
                "dragView": true,
                "dragNodes": true
              },
                            "nodes": {
                                "borderWidth": 2,
                                "borderWidthSelected": 3,
                                "font": {
                                    "size": 12,
                                    "color": "#e6e6e6"
                                },
                                "shadow": false
                            },
              "edges": {
                "smooth": {
                  "enabled": true,
                  "type": "continuous",
                  "roundness": 0.5
                },
                "width": 1,
                "selectionWidth": 2
              }
            }
            """)

            # Color mapping functions - cleaner colors for white background
            def get_node_color(node_data, color_mode):
                if color_mode == "Partner Status":
                    return "#3b82f6" if node_data.get("is_partner") else "#ef4444"
                
                elif color_mode == "Game":
                    games = list(set([d.get("game_name", "Unknown") for _, d in display_graph.nodes(data=True)]))
                    # Distinct, vibrant colors for white background
                    colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
                    game_colors = {game: colors[i % len(colors)] for i, game in enumerate(games)}
                    return game_colors.get(node_data.get("game_name", "Unknown"), "#6b7280")
                
                elif color_mode == "Language":
                    langs = list(set([d.get("language", "en") for _, d in display_graph.nodes(data=True)]))
                    colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
                    lang_colors = {lang: colors[i % len(colors)] for i, lang in enumerate(langs)}
                    return lang_colors.get(node_data.get("language", "en"), "#6b7280")
                
                elif color_mode == "Follower Count":
                    followers = node_data.get("follower_count", 0)
                    if followers > 500000:
                        return "#dc2626"  # Red - mega influencer
                    elif followers > 100000:
                        return "#3b82f6"  # Blue - large
                    elif followers > 50000:
                        return "#8b5cf6"  # Purple - medium
                    else:
                        return "#6b7280"  # Gray - small
                
                elif color_mode == "Live Status":
                    return "#10b981" if node_data.get("is_live") else "#6b7280"
                
                elif color_mode == "Account Age":
                    created = node_data.get("created_at", "")
                    if created:
                        try:
                            from datetime import datetime
                            created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            age_years = (datetime.now(created_date.tzinfo) - created_date).days / 365
                            if age_years > 8:
                                return "#dc2626"  # Red - veteran
                            elif age_years > 5:
                                return "#3b82f6"  # Blue - experienced
                            elif age_years > 2:
                                return "#8b5cf6"  # Purple - established
                            else:
                                return "#6b7280"  # Gray - new
                        except:
                            return "#6b7280"
                    return "#6b7280"
                
                return "#3b82f6"  # Default blue

            # Precompute layout positions to avoid expensive browser-side physics
            try:
                n_nodes = display_graph.number_of_nodes()
                if n_nodes > 0:
                    k = 1.0 / (np.sqrt(n_nodes))
                    pos = nx.spring_layout(display_graph, k=k, iterations=50, seed=42)
                else:
                    pos = {}
            except Exception:
                pos = {}

            # Add nodes with cleaner styling for white background
            for node, data in display_graph.nodes(data=True):
                # Size nodes by the selected centrality metric when available,
                # otherwise fall back to PageRank
                score_for_size = metric_scores.get(node, pagerank.get(node, 0))
                size = 12 + score_for_size * 80
                color = get_node_color(data, color_by)

                tooltip = f"{data.get('display_name','')} | {data.get('follower_count',0):,} followers | {data.get('game_name','Unknown')}"
                node_kwargs = dict(
                    label=data.get("display_name", "")[:15],
                    title=tooltip,
                    size=size,
                    color=color,
                    borderWidth=2,
                    font={'size': 11, 'color': '#e6e6e6'}
                )
                # If we computed positions, pass them to pyvis to avoid layout cost
                if node in pos:
                    try:
                        x, y = pos[node]
                        # Scale positions to pixels (pyvis accepts x/y numbers)
                        node_kwargs['x'] = float(x * 1000)
                        node_kwargs['y'] = float(y * 1000)
                        # disable physics for fixed-position nodes
                        node_kwargs['physics'] = False
                    except Exception:
                        pass

                net.add_node(node, **node_kwargs)

            # Add edges - thin gray lines for cleaner look
            edge_counts = {"same_game": 0, "same_language": 0, "strong_connections": 0, "both_partners": 0, "same_tier": 0}
            
            # Cap edges added to the visualization to keep rendering responsive
            max_edges = 1500
            added_edge_count = 0
            for u, v, attrs in display_graph.edges(data=True):
                w = attrs.get("weight", 0.5)
                # Support legacy single 'type' attribute or new 'types' set/list
                raw_types = attrs.get('types') or attrs.get('type') or []
                if isinstance(raw_types, str):
                    edge_types = {raw_types}
                elif isinstance(raw_types, (list, tuple, set)):
                    edge_types = set(raw_types)
                else:
                    try:
                        edge_types = set(raw_types)
                    except:
                        edge_types = set()

                # Show edges based on user selection with subtle colors
                if added_edge_count >= max_edges:
                    continue

                if 'same_game' in edge_types and show_same_game:
                    edge_color = "#94a3b8"  # Gray-blue
                    edge_counts["same_game"] += 1
                    net.add_edge(u, v, value=w, color=edge_color, width=0.8)
                    added_edge_count += 1

                if 'same_language' in edge_types and show_same_language:
                    edge_color = "#cbd5e1"  # Light gray
                    edge_counts["same_language"] += 1
                    net.add_edge(u, v, value=w, color=edge_color, width=0.6)
                    added_edge_count += 1

                # Strong connections: use edge weight threshold when requested
                if show_strong_connections and w is not None and w >= strong_conn_threshold:
                    edge_color = "#9ca3ff"  # Subtle blue for strong ties
                    edge_counts["strong_connections"] += 1
                    net.add_edge(u, v, value=w, color=edge_color, width=1)
                    added_edge_count += 1

                if 'both_partners' in edge_types and show_both_partners:
                    edge_color = "#f59e0b"  # Orange - stands out
                    edge_counts["both_partners"] += 1
                    net.add_edge(u, v, value=w, color=edge_color, width=1)
                    added_edge_count += 1

                if 'same_tier' in edge_types and show_same_tier:
                    edge_color = "#10b981"  # Green
                    edge_counts["same_tier"] += 1
                    net.add_edge(u, v, value=w, color=edge_color, width=0.7)
                    added_edge_count += 1

            net.save_graph("network.html")
            with open("network.html", 'r', encoding='utf-8') as f:
                html = f.read()

            # Replace local-relative helper with CDN UMD bundles for vis-data + vis-network
            # PyVis may emit a local helpers file (lib/bindings/utils.js) which provides vis DataSet
            # Replace it with CDN scripts so the HTML can run inside Streamlit iframe
            html = html.replace(
                '<script src="lib/bindings/utils.js"></script>',
                '<script src="https://cdn.jsdelivr.net/npm/vis-data@7.1.2/dist/vis-data.min.js"></script>'
                + '<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/dist/vis-network.min.js"></script>'
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
            
            components.html(html, height=650)

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
                from community_detection import CommunityDetector
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


# ==================== RECOMMENDATIONS PAGE ====================
elif page == "Recommendations":
    st.markdown("<h2>Influencer Recommendations</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #9ca3af; margin-bottom: 1.5rem;'>Match companies with ideal streamers based on network analysis</p>", unsafe_allow_html=True)

    if not st.session_state.graph or not st.session_state.streamers_data:
        st.warning("⚠️ Please build the network first on the Network Analysis page.")
    else:
        st.subheader("Create Company Profile")

        with st.form("company_form"):
            company_name = st.text_input("Company Name")

            col1, col2 = st.columns(2)

            with col1:
                target_games = st.multiselect(
                    "Target Games",
                    ['League of Legends', 'VALORANT', 'Call of Duty: Warzone', 'Fortnite', 'Minecraft',
                     'CS:GO', 'Apex Legends', 'Dota 2']
                )
                min_followers = st.number_input("Min Followers", 0, 1000000, 1000)
                max_followers = st.number_input("Max Followers", 10000, 10000000, 2500000)

            with col2:
                languages = st.multiselect(
                    "Target Languages",
                    ['en', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'ru', 'zh'],
                    default=['en', 'es', 'fr', 'de', 'pt']
                )
                product_category = st.selectbox(
                    "Product Category",
                    ['gaming_peripherals', 'food_beverage', 'game_developer', 'apparel', 'software']
                )

            top_n = st.slider("Number of Recommendations", 3, 20, 10)

            submit = st.form_submit_button("Get Recommendations")

        if submit and company_name:
            profile = CompanyProfile(
                company_id=f"comp_{company_name.lower().replace(' ', '_')}",
                name=company_name,
                target_games=target_games,
                target_languages=languages,
                min_followers=min_followers,
                max_followers=max_followers,
                product_category=product_category
            )

            with st.spinner("Generating recommendations..."):
                streamers_df = pd.DataFrame(st.session_state.streamers_data)

                extractor = FeatureExtractor()
                streamer_features = extractor.extract_streamer_features(streamers_df)

                similarity_calc = SimilarityCalculator(
                    streamer_features,
                    streamers_df['user_id'].tolist()
                )

                recommender = StreamerRecommender(
                    streamers_df,
                    st.session_state.centrality_scores,
                    similarity_calc
                )

                company_feature = extractor.extract_company_features(profile.to_feature_vector())
                recommendations = recommender.recommend_streamers(
                    company_feature,
                    profile.to_feature_vector(),
                    top_n=top_n
                )
                
                # Store in session state
                st.session_state.last_recommendations = recommendations
                st.session_state.last_company_name = company_name
                st.session_state.last_recommender = recommender

            st.success(f"Found {len(recommendations)} recommendations for {company_name}")

            st.subheader("Recommended Streamers")

            for idx, row in recommendations.iterrows():
                with st.expander(f"#{idx + 1} - {row['display_name']} (@{row['username']})"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Followers", f"{row['follower_count']:,}")
                        st.write(f"Game: {row['game_name']}")

                    with col2:
                        st.metric("Match Score", f"{row['composite_score']:.3f}")
                        st.metric("Content Similarity", f"{row['content_similarity']:.3f}")

                    with col3:
                        st.metric("Network Influence", f"{row['pagerank_centrality']:.4f}")

                    st.write(f"Twitch: https://twitch.tv/{row['username']}")

            csv = recommendations.to_csv(index=False)
            st.download_button(
                "Download Recommendations",
                csv,
                f"recommendations_{company_name.replace(' ', '_')}.csv",
                "text/csv"
            )
        
        # ============ ADVANCED OPTIMIZATION (Always show if recommendations exist) ============
        if st.session_state.last_recommendations is not None:
            st.markdown("---")
            st.markdown("### 🎯 Advanced Campaign Optimization")
            
            recommendations = st.session_state.last_recommendations
            recommender = st.session_state.last_recommender
            
            opt_tab1, opt_tab2, opt_tab3, opt_tab4 = st.tabs([
                "💰 Budget Allocation", 
                "📈 Strategy Comparison", 
                "🎲 Campaign Simulator",
                "🔍 Competitor Analysis"
            ])
            
            with opt_tab1:
                st.markdown("#### Optimal Budget Distribution")
                st.markdown("Allocate your campaign budget across selected streamers for maximum ROI")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    campaign_budget = st.number_input(
                        "Total Campaign Budget ($)", 
                        min_value=1000, 
                        max_value=1000000, 
                        value=50000, 
                        step=1000
                    )
                with col2:
                    allocation_strategy = st.selectbox(
                        "Allocation Strategy",
                        ['balanced', 'top_heavy', 'roi_optimized'],
                        format_func=lambda x: {
                            'balanced': '⚖️ Balanced',
                            'top_heavy': '⭐ Top Heavy',
                            'roi_optimized': '💹 ROI Optimized'
                        }[x]
                    )
                
                if st.button("Calculate Budget Allocation", type="primary"):
                    from recommender import BudgetAllocation
                    
                    # Convert recommendations to format expected by allocate_budget
                    streamers_list = []
                    for _, row in recommendations.iterrows():
                        streamers_list.append({
                            'user_id': row['user_id'],
                            'display_name': row['display_name'],
                            'username': row['username'],
                            'follower_count': row['follower_count'],
                            'estimated_roi': row['composite_score'] * 0.1
                        })
                    
                    allocations = recommender.allocate_budget(
                        streamers_list, 
                        campaign_budget, 
                        allocation_strategy
                    )
                    
                    # Display allocations
                    alloc_data = []
                    for alloc in allocations:
                        alloc_data.append({
                            'Streamer': alloc.display_name,
                            'Budget': f"${alloc.allocated_budget:,.2f}",
                            'Est. Reach': f"{alloc.estimated_reach:,}",
                            'Est. Engagement': f"{alloc.estimated_engagement:,.0f}",
                            'ROI Score': f"{alloc.roi_score:.2f}"
                        })
                    
                    alloc_df = pd.DataFrame(alloc_data)
                    
                    # Visualization
                    fig_budget = px.bar(
                        alloc_df,
                        x='Streamer',
                        y='Budget',
                        title=f"Budget Allocation ({allocation_strategy})",
                        color='ROI Score',
                        color_continuous_scale='Viridis'
                    )
                    fig_budget.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0",
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig_budget, width='stretch')
                    
                    st.dataframe(alloc_df, width='stretch')
                    
                    # Summary metrics
                    col1, col2, col3 = st.columns(3)
                    total_reach = sum(a.estimated_reach for a in allocations)
                    total_engagement = sum(a.estimated_engagement for a in allocations)
                    
                    with col1:
                        st.metric("Total Estimated Reach", f"{total_reach:,}")
                    with col2:
                        st.metric("Total Estimated Engagement", f"{total_engagement:,.0f}")
                    with col3:
                        avg_roi = np.mean([a.roi_score for a in allocations])
                        st.metric("Average ROI Score", f"{avg_roi:.2f}")
            
            with opt_tab2:
                st.markdown("#### Strategy Performance Comparison")
                st.markdown("Compare different allocation strategies to find the optimal approach")
                
                test_budget = st.number_input(
                    "Test Budget ($)", 
                    min_value=5000, 
                    max_value=500000, 
                    value=25000,
                    key="comparison_budget"
                )
                
                if st.button("Run Strategy Comparison", type="primary"):
                    streamers_list = []
                    for _, row in recommendations.iterrows():
                        streamers_list.append({
                            'user_id': row['user_id'],
                            'display_name': row['display_name'],
                            'username': row['username'],
                            'follower_count': row['follower_count'],
                            'estimated_roi': row['composite_score'] * 0.1
                        })
                    
                    with st.spinner("Running comparisons..."):
                        comparison_df = recommender.compare_strategies(streamers_list, test_budget)
                    
                    st.success("Comparison complete!")
                    
                    # Visualize comparison
                    fig_comparison = px.bar(
                        comparison_df,
                        x='strategy',
                        y=['expected_reach', 'expected_roi'],
                        title="Strategy Comparison: Reach vs ROI",
                        labels={'value': 'Metric Value', 'strategy': 'Strategy'},
                        barmode='group',
                        color_discrete_sequence=['#6474ff', '#f59e0b']
                    )
                    fig_comparison.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_comparison, width='stretch')
                    
                    # Detailed table
                    st.dataframe(comparison_df, width='stretch')
                    
                    # Winner recommendation
                    best_strategy = comparison_df.loc[comparison_df['expected_roi'].idxmax(), 'strategy']
                    st.info(f"📊 Recommended Strategy: **{best_strategy}** (Highest Expected ROI)")
            
            with opt_tab3:
                st.markdown("#### Campaign Performance Simulator")
                st.markdown("Monte Carlo simulation to predict campaign outcomes with confidence intervals")
                
                num_sims = st.slider("Number of Simulations", 100, 5000, 1000, step=100)
                sim_budget = st.number_input(
                    "Simulation Budget ($)",
                    min_value=5000,
                    max_value=500000,
                    value=30000,
                    key="sim_budget"
                )
                sim_strategy = st.selectbox(
                    "Strategy to Simulate",
                    ['balanced', 'top_heavy', 'roi_optimized'],
                    key="sim_strategy"
                )
                
                if st.button("Run Simulation", type="primary"):
                    from recommender import BudgetAllocation
                    
                    streamers_list = []
                    for _, row in recommendations.iterrows():
                        streamers_list.append({
                            'user_id': row['user_id'],
                            'display_name': row['display_name'],
                            'username': row['username'],
                            'follower_count': row['follower_count'],
                            'estimated_roi': row['composite_score'] * 0.1
                        })
                    
                    allocations = recommender.allocate_budget(streamers_list[:10], sim_budget, sim_strategy)
                    
                    with st.spinner(f"Running {num_sims} simulations..."):
                        simulation = recommender.simulate_campaign(allocations, num_simulations=num_sims)
                    
                    st.success("Simulation complete!")
                    
                    # Display results
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "Expected Reach",
                            f"{int(simulation['mean_reach']):,}",
                            delta=f"±{int(simulation['std_reach']):,}"
                        )
                    with col2:
                        st.metric(
                            "Expected Engagement",
                            f"{simulation['mean_engagement']:,.0f}",
                            delta=f"±{simulation['std_engagement']:.0f}"
                        )
                    with col3:
                        st.metric(
                            "Expected ROI",
                            f"{simulation['mean_roi']:.2f}",
                            delta="per $1K spent"
                        )
                    
                    # 95% Confidence Intervals
                    st.markdown("**95% Confidence Intervals:**")
                    conf_col1, conf_col2 = st.columns(2)
                    
                    with conf_col1:
                        st.write(f"**Reach Range:** {int(simulation['confidence_95']['reach_lower']):,} - {int(simulation['confidence_95']['reach_upper']):,}")
                    with conf_col2:
                        st.write(f"**ROI Range:** {simulation['confidence_95']['roi_lower']:.2f} - {simulation['confidence_95']['roi_upper']:.2f}")
                    
                    # Distribution visualizations
                    dist_col1, dist_col2 = st.columns(2)
                    
                    with dist_col1:
                        fig_reach_dist = px.histogram(
                            x=simulation['distributions']['total_reach'],
                            title="Reach Distribution",
                            labels={'x': 'Total Reach', 'y': 'Frequency'},
                            color_discrete_sequence=['#6474ff']
                        )
                        fig_reach_dist.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0"
                        )
                        st.plotly_chart(fig_reach_dist, width='stretch')
                    
                    with dist_col2:
                        fig_roi_dist = px.histogram(
                            x=simulation['distributions']['total_roi'],
                            title="ROI Distribution",
                            labels={'x': 'ROI', 'y': 'Frequency'},
                            color_discrete_sequence=['#f59e0b']
                        )
                        fig_roi_dist.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0"
                        )
                        st.plotly_chart(fig_roi_dist, width='stretch')
            
            with opt_tab4:
                st.markdown("#### Competitor Analysis")
                st.markdown("Analyze competitor partnerships and identify market opportunities")
                
                st.info("💡 Enter streamer usernames (comma-separated) that your competitors are working with")
                
                competitor_input = st.text_area(
                    "Competitor Streamers",
                    placeholder="e.g., ninja, pokimane, shroud",
                    height=100
                )
                
                if st.button("Analyze Competitors", type="primary") and competitor_input:
                    # Parse input
                    competitor_usernames = [s.strip() for s in competitor_input.split(',')]
                    
                    # Find corresponding user IDs
                    streamers_df = pd.DataFrame(st.session_state.streamers_data)
                    competitor_ids = streamers_df[
                        streamers_df['username'].isin(competitor_usernames)
                    ]['user_id'].tolist()
                    
                    if competitor_ids:
                        with st.spinner("Analyzing competitor strategies..."):
                            analysis = recommender.analyze_competitors(competitor_ids)
                        
                        st.success(f"Analyzed {analysis['num_competitor_streamers']} competitor streamers")
                        
                        # Key metrics
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric(
                                "Competitor Avg Followers",
                                f"{analysis['competitor_avg_followers']:,.0f}"
                            )
                        
                        with col2:
                            st.metric(
                                "Untapped Games",
                                len(analysis['untapped_games'])
                            )
                        
                        # Competitor game distribution
                        if analysis['competitor_games']:
                            games_df = pd.DataFrame(
                                list(analysis['competitor_games'].items()),
                                columns=['Game', 'Count']
                            ).sort_values('Count', ascending=False)
                            
                            fig_comp_games = px.bar(
                                games_df,
                                x='Game',
                                y='Count',
                                title="Competitor Game Focus",
                                color='Count',
                                color_continuous_scale='Reds'
                            )
                            fig_comp_games.update_layout(
                                plot_bgcolor="#0f172a",
                                paper_bgcolor="#0f172a",
                                font_color="#e2e8f0",
                                xaxis_tickangle=-45
                            )
                            st.plotly_chart(fig_comp_games, width='stretch')
                        
                        # Gap opportunities
                        st.markdown("#### 🎯 Gap Opportunities")
                        st.markdown("High-value streamers not being utilized by competitors")
                        
                        if analysis['gap_opportunities']:
                            gaps_df = pd.DataFrame(analysis['gap_opportunities'])
                            st.dataframe(gaps_df, width='stretch', height=400)
                        else:
                            st.info("No significant gaps identified")
                        
                        # Untapped games
                        if analysis['untapped_games']:
                            st.markdown("#### 🎮 Untapped Game Categories")
                            st.write(", ".join(analysis['untapped_games'][:10]))
                    else:
                        st.error("No matching streamers found. Check usernames and ensure data is collected.")


# ==================== ANALYTICS PAGE ====================
elif page == "Analytics":
    st.markdown("<h2>Network Analytics Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #9ca3af; margin-bottom: 1.5rem;'>Comprehensive insights into network structure and streamer performance</p>", unsafe_allow_html=True)

    if not st.session_state.streamers_data:
        st.warning("No data available. Please collect data first.")
    else:
        try:
            df = pd.DataFrame(st.session_state.streamers_data)
            
            # Analytics tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Overview", "🎮 Game Analytics", "👥 Demographics",
                "🏆 Top Performers", "🔗 Network Insights"
            ])

            # ========== TAB 1: OVERVIEW ==========
            with tab1:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Total Streamers", len(df))
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric("Avg Followers", f"{df['follower_count'].mean():,.0f}")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col3:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    partner_pct = (df['is_partner'].sum() / len(df) * 100)
                    st.metric("Partner %", f"{partner_pct:.1f}%")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col4:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    unique_games = df['game_name'].nunique()
                    st.metric("Unique Games", unique_games)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("---")

                # Follower distribution
                st.subheader("Follower Distribution Analysis")
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_followers = px.histogram(
                        df,
                        x='follower_count',
                        nbins=40,
                        title="Follower Count Distribution",
                        labels={'follower_count': 'Followers', 'count': 'Number of Streamers'},
                        color_discrete_sequence=['#0ea5e9']
                    )
                    fig_followers.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0",
                        xaxis_title="Followers",
                        yaxis_title="Count"
                    )
                    st.plotly_chart(fig_followers, width='stretch')
                
                with col2:
                    fig_box = px.box(
                        df,
                        y='follower_count',
                        title="Follower Distribution (Box Plot)",
                        color_discrete_sequence=['#06b6d4']
                    )
                    fig_box.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_box, width='stretch')

            # ========== TAB 2: GAME ANALYTICS ==========
            with tab2:
                st.subheader("Game Category Analysis")
                
                game_counts = df['game_name'].value_counts()
                game_avg_followers = df.groupby('game_name')['follower_count'].mean().sort_values(ascending=False)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_games = px.bar(
                        x=game_counts.index[:15],
                        y=game_counts.values[:15],
                        title="Top 15 Games by Streamer Count",
                        labels={'x': 'Game', 'y': 'Number of Streamers'},
                        color=game_counts.values[:15],
                        color_continuous_scale='Blues'
                    )
                    fig_games.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_games, width='stretch')
                
                with col2:
                    fig_followers_by_game = px.bar(
                        x=game_avg_followers.index[:15],
                        y=game_avg_followers.values[:15],
                        title="Avg Followers by Game",
                        labels={'x': 'Game', 'y': 'Avg Followers'},
                        color=game_avg_followers.values[:15],
                        color_continuous_scale='blues'
                    )
                    fig_followers_by_game.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_followers_by_game, width='stretch')

            # ========== TAB 3: DEMOGRAPHICS ==========
            with tab3:
                st.subheader("Streamer Demographics")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    partner_counts = df['is_partner'].value_counts()
                    fig_partner = px.pie(
                        values=partner_counts.values,
                        names=['Partner' if x else 'Affiliate' for x in partner_counts.index],
                        title="Partner Distribution",
                        color_discrete_sequence=['#0ea5e9', '#06b6d4']
                    )
                    fig_partner.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_partner, width='stretch')
                
                with col2:
                    lang_counts = df['language'].value_counts().head(10)
                    fig_lang = px.bar(
                        x=lang_counts.index,
                        y=lang_counts.values,
                        title="Top Languages",
                        labels={'x': 'Language', 'y': 'Count'},
                        color=lang_counts.values,
                        color_continuous_scale='Teal'
                    )
                    fig_lang.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_lang, width='stretch')
                
                with col3:
                    # Replacement visuals: follower distribution, engagement boxplot, account age
                    # Follower distribution (log scale)
                    if 'follower_count' in df.columns and df['follower_count'].dropna().shape[0] > 0:
                        followers = df['follower_count'].dropna()
                        fig_followers = px.histogram(
                            followers,
                            nbins=40,
                            title='Follower Count Distribution (log scale)',
                            labels={'value': 'Followers'},
                            color_discrete_sequence=['#7c3aed']
                        )
                        fig_followers.update_xaxes(type='log')
                        fig_followers.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e6e8f0")
                        st.plotly_chart(fig_followers, width='stretch')
                    else:
                        st.info("Follower counts not available for distribution")

                    # Engagement: viewers per follower boxplot
                    if set(['viewer_count','follower_count']).issubset(df.columns):
                        eng_df = df.loc[df['follower_count'] > 0].assign(engagement=lambda d: d['viewer_count'] / d['follower_count'])
                        if not eng_df.empty:
                            fig_eng = px.box(
                                eng_df,
                                y='engagement',
                                title='Engagement (viewers / followers) - boxplot',
                                color_discrete_sequence=['#06b6d4']
                            )
                            fig_eng.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e6e8f0")
                            st.plotly_chart(fig_eng, width='stretch')
                        else:
                            st.info("Not enough data to compute engagement")
                    else:
                        st.info("Viewer or follower counts missing for engagement calculation")

                    # Account age histogram
                    if 'created_at' in df.columns:
                        # Parse with UTC awareness to avoid tz-naive vs tz-aware subtraction errors
                        created_dates = pd.to_datetime(df['created_at'], errors='coerce', utc=True)
                        now = pd.Timestamp.now(tz='UTC')
                        # Use total_seconds for precise year calculation and avoid tz issues
                        age_years = (now - created_dates).dt.total_seconds() / (365.0 * 24 * 3600)
                        age_years = age_years.dropna()
                        if len(age_years) > 0:
                            fig_age = px.histogram(
                                age_years,
                                nbins=20,
                                labels={'value': 'Account age (years)'},
                                title='Account Age Distribution (years)',
                                color_discrete_sequence=['#10b981']
                            )
                            fig_age.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e6e8f0")
                            st.plotly_chart(fig_age, width='stretch')
                        else:
                            st.info("Account creation dates present but could not be parsed")
                    else:
                        st.info("Account creation dates not available")

            # ========== TAB 4: TOP PERFORMERS ==========
            with tab4:
                st.subheader("Top Streamers")
                
                n = st.slider("Show top N streamers", 5, 50, 10, step=5)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    top_followers = df.nlargest(n, 'follower_count')[
                        ['display_name', 'follower_count', 'game_name', 'is_partner']
                    ].reset_index(drop=True)
                    
                    fig_top = px.bar(
                        top_followers,
                        x='display_name',
                        y='follower_count',
                        title=f"Top {n} Streamers by Followers",
                        labels={'follower_count': 'Followers', 'display_name': 'Streamer'},
                        color='follower_count',
                        color_continuous_scale='Reds'
                    )
                    fig_top.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0",
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig_top, width='stretch')
                
                with col2:
                    st.markdown("**Top Performers Table:**")
                    st.dataframe(top_followers, width='stretch')

            # ========== TAB 5: NETWORK INSIGHTS ==========
            with tab5:
                if st.session_state.graph and st.session_state.centrality_scores:
                    st.subheader("Network Centrality Analysis")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        pagerank = st.session_state.centrality_scores.get("pagerank", {})
                        centrality_data = pd.DataFrame({
                            'Streamer': list(pagerank.keys())[:15],
                            'PageRank Score': list(pagerank.values())[:15]
                        }).sort_values('PageRank Score', ascending=False)
                        
                        fig_pagerank = px.bar(
                            centrality_data,
                            x='Streamer',
                            y='PageRank Score',
                            title="Top 15 by PageRank Centrality",
                            color='PageRank Score',
                            color_continuous_scale='Greens'
                        )
                        fig_pagerank.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            xaxis_tickangle=-45
                        )
                        st.plotly_chart(fig_pagerank, width='stretch')
                    
                    with col2:
                        degree = st.session_state.centrality_scores.get("degree", {})
                        degree_data = pd.DataFrame({
                            'Streamer': list(degree.keys())[:15],
                            'Degree': list(degree.values())[:15]
                        }).sort_values('Degree', ascending=False)
                        
                        fig_degree = px.bar(
                            degree_data,
                            x='Streamer',
                            y='Degree',
                            title="Top 15 by Degree Centrality",
                            color='Degree',
                            color_continuous_scale='Purples'
                        )
                        fig_degree.update_layout(
                            plot_bgcolor="#0f172a",
                            paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            xaxis_tickangle=-45
                        )
                        st.plotly_chart(fig_degree, width='stretch')

                    # Centrality comparison scatter
                    st.subheader("Centrality Metrics Comparison")
                    pagerank = st.session_state.centrality_scores.get("pagerank", {})
                    betweenness = st.session_state.centrality_scores.get("betweenness", {})
                    
                    comparison_data = []
                    for node in list(pagerank.keys())[:50]:
                        comparison_data.append({
                            'Streamer': st.session_state.graph.nodes[node].get('display_name', node),
                            'PageRank': pagerank.get(node, 0),
                            'Betweenness': betweenness.get(node, 0),
                            'Game': st.session_state.graph.nodes[node].get('game_name', 'Unknown')
                        })
                    
                    comp_df = pd.DataFrame(comparison_data)
                    fig_comp = px.scatter(
                        comp_df,
                        x='PageRank',
                        y='Betweenness',
                        color='Game',
                        hover_name='Streamer',
                        size='PageRank',
                        title="PageRank vs Betweenness Centrality",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig_comp.update_layout(
                        plot_bgcolor="#0f172a",
                        paper_bgcolor="#0f172a",
                        font_color="#e2e8f0"
                    )
                    st.plotly_chart(fig_comp, width='stretch')
                else:
                    st.info("Build a network first to see network insights")

        except Exception as e:
            st.error(f"Error in analytics: {str(e)}")
            st.error(traceback.format_exc())
