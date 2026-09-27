# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Split `app.py` into a thin page router and one module per page under `ui/`
- Moved the PyVis graph builder into `ui/network_graph.py`; it loads vis-network from a CDN and no longer writes `network.html` or a `lib/` folder
- Embedded the network graph with `st.iframe` (replaces the deprecated `components.html`); requires Streamlit 1.64+
- Moved the inline button CSS from `app.py` into `styles.py`

### Fixed
- "Get Recommendations" crashed with `KeyError: 'tags'` for streamers loaded from the database
- The "Weight Edges by Audience Size" option was ignored when comprehensive network building was enabled
- The top navigation row was created twice

### Removed
- Unused modules `network_viz.py`, `dashboard.py` and `streamer_scraper.py`
- Committed PyVis assets (`lib/`) and SQLite database; both are now gitignored
- `TwitchDataCollector.get_follows_network` stub
- Unused dependencies `matplotlib`, `seaborn` and `sqlalchemy`, plus unused imports and variables

## [1.0.0] - 2025-01-14

### Added
- Initial release of TwitchNet Analytics
- Twitch API integration with rate limiting and exponential backoff
- Network graph construction with multi-reason edge connections
- 8+ centrality metrics (PageRank, Betweenness, Eigenvector, etc.)
- Louvain community detection algorithm
- Composite influence scoring
- Streamer recommendation engine with budget optimization
- Interactive Streamlit dashboard
- PyVis network visualization
- Plotly analytics charts
- SQLite persistence layer
- Company profile management
- Custom Twitch-inspired dark theme

### Features
- Multi-language streamer discovery
- Cross-game community bridge detection
- Brand safety scoring
- ROI estimation for campaigns
- Configurable recommendation weights
