# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Streamer records include `broadcaster_type`, `is_mature`, `content_classification_labels`, `is_branded_content` and `started_at`
- Database tables for stream/follower snapshots, chat presence, raids, teams, collabs, videos, clips, top games and tracked channels
- Automatic migration of existing databases to the new streamer schema
- pytest suite for the collector (against a fake Twitch client) and the database

### Changed
- Twitch collection batches user and channel lookups 100 at a time, fetches follower totals concurrently and removes the fixed sleeps; each run logs its duration and API request count
- Language-diverse collection queries all languages in parallel and looks up the game once
- The database stores the full streamer record (description, tags, game id and the new fields), so data loaded from it matches freshly collected data
- Engagement in recommendations uses live viewers relative to followers
- Split `app.py` into a thin page router and one module per page under `ui/`
- Moved the PyVis graph builder into `ui/network_graph.py`; it loads vis-network from a CDN and no longer writes `network.html` or a `lib/` folder
- Embedded the network graph with `st.iframe` (replaces the deprecated `components.html`); requires Streamlit 1.64+
- Moved the inline button CSS from `app.py` into `styles.py`

### Fixed
- "Get Recommendations" crashed with `KeyError: 'tags'` for streamers loaded from the database
- The "Weight Edges by Audience Size" option was ignored when comprehensive network building was enabled
- The top navigation row was created twice
- Channel information (tags, game id) was never collected: the collector iterated the channel list with `async for`, and the error was swallowed
- Recommendation engagement was always 0 because it used the deprecated `view_count`

### Removed
- Unused modules `network_viz.py`, `dashboard.py` and `streamer_scraper.py`
- Committed PyVis assets (`lib/`) and SQLite database; both are now gitignored
- `TwitchDataCollector.get_follows_network` stub
- The deprecated `view_count` field (Twitch always returns 0)
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
