"""Home page: overview metrics and save/load/export of analysis state."""
from datetime import datetime

import pandas as pd
import streamlit as st

from twitchnet.config import Config


def render():
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
