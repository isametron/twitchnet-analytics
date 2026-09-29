import streamlit as st

from twitchnet.config import Config
from twitchnet.database import DatabaseManager
from twitchnet.styles import BUTTON_CSS, CUSTOM_CSS, HEADER_HTML
from ui import analytics, data_collection, home, network_analysis, recommendations

Config.make_console_safe()

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

# Initialize session state
SESSION_DEFAULTS = {
    'streamers_data': None,
    'graph': None,
    'centrality_scores': None,
    'communities': None,
    'network_metrics': None,
    'advanced_scores': None,
    'last_recommendations': None,
    'current_graph_id': None,
    'current_page': 'Home',
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

# Create directories
try:
    Config.create_directories()
except Exception as e:
    st.error(f"Failed to create directories: {str(e)}")

st.markdown(BUTTON_CSS, unsafe_allow_html=True)

# Page label -> module that renders it
PAGES = {
    'Home': home,
    'Data Collection': data_collection,
    'Network Analysis': network_analysis,
    'Recommendations': recommendations,
    'Analytics': analytics,
}

# Top navigation buttons - centered with proper spacing
nav_cols = st.columns([1, 1, 1.3, 1.3, 1.3, 1, 1])
for col, label in zip(nav_cols[1:-1], PAGES):
    with col:
        is_current = st.session_state.current_page == label
        if st.button(label.upper(), width='stretch', type="primary" if is_current else "secondary"):
            st.session_state.current_page = label

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

PAGES[page].render()
