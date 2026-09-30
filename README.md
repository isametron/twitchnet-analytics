<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/streamlit-1.28+-red.svg" alt="Streamlit">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/twitch-API-purple.svg" alt="Twitch API">
</p>

<h1 align="center">🎮 TwitchNet Analytics</h1>

<p align="center">
  <strong>Network analysis and recommendation system for Twitch streamer partnerships</strong>
</p>

<p align="center">
  Collect Twitch streamer data • Build relationship graphs • Perform centrality analysis • Detect communities • Recommend streamers for brand partnerships
</p>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 📊 Data Collection
- Batched Twitch API requests (100 streamers in seconds)
- Multi-language streamer discovery
- Follower count, game, tags, partner status
- Twitch content labels and branded-content flag
- Relationship tracking: chat audience overlap, raids, teams, co-streams

</td>
<td width="50%">

### 🕸️ Network Analysis
- Attribute, observed-relationship and hybrid networks
- Precomputed server-side layout
- Edge capping for performance
- 8+ centrality metrics

</td>
</tr>
<tr>
<td width="50%">

### 👥 Community Detection
- Louvain algorithm partitioning
- Bridge node identification
- Cross-game community detection
- Community statistics & insights

</td>
<td width="50%">

### 🎯 Recommendations
- Content similarity matching
- Multi-objective optimization
- Budget allocation algorithms
- Brand safety scoring

</td>
</tr>
</table>

---

## 🖼️ Screenshots

<details>
<summary>Click to expand screenshots</summary>

### Network Visualization
> Interactive PyVis network graph showing streamer connections
<img width="1919" height="899" alt="Screenshot 2025-12-30 021316" src="https://github.com/user-attachments/assets/f6c864a5-1ecd-47ab-8abc-93c0f71f1179" />
<img width="1919" height="803" alt="Screenshot 2025-12-30 021414" src="https://github.com/user-attachments/assets/a3a541d3-a5bd-4224-b169-284fa4e03908" />

### Analytics Dashboard
> Centrality scores, community stats, and demographic breakdowns
<img width="1919" height="768" alt="Screenshot 2025-12-30 021345" src="https://github.com/user-attachments/assets/95b1c881-a5fb-4e52-b890-c9ebbae357a9" />
<img width="1919" height="893" alt="Screenshot 2025-12-30 021543" src="https://github.com/user-attachments/assets/53a6fff4-d7c4-4578-b7df-5890908b1bc5" />

### Recommendation Engine
> Company profile matching with ROI estimation
<img width="1918" height="855" alt="Screenshot 2025-12-30 022050" src="https://github.com/user-attachments/assets/2916ffe7-b3e5-4a28-baa2-5d07af9298bb" />

</details>

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- [Twitch Developer Account](https://dev.twitch.tv/console)

### Installation

```bash
# Clone the repository
git clone https://github.com/isametron/twitchnet-analytics.git
cd twitchnet-analytics

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Twitch API credentials
```

### Usage

```bash
# Start the dashboard
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

### Tracking (relationships and history)

By default the network links streamers who share attributes (game, language, tags, partner status, follower tier). `tracker.py` collects **observed** relationships and history for a list of tracked channels:

| Data | Source | How often | Needs |
|------|--------|-----------|-------|
| Viewer snapshots, game history | Helix streams | Every 5 min | App credentials |
| Chat audience overlap | Anonymous Twitch chat (IRC) | Continuous | Nothing |
| Raids into tracked channels | Raid notices in chat (IRC) | Continuous | Nothing |
| Co-streams | Shared Chat sessions + `@mentions` in stream titles | Every 5 min | App credentials |
| Top categories | Helix games | Hourly | App credentials |
| Followers, VODs, clips, schedules | Helix | Every 6 h | App credentials |
| Teams | Helix teams | Daily | App credentials |

```bash
# 1. Choose channels to track: the top channels live right now
python tracker.py --seed --live --limit 300 --replace

# 2. Run the tracker (Ctrl+C to stop)
python tracker.py > tracker.log 2>&1

# Compare network structure with and without the observed relationships
python scripts/test_build.py --mode attribute
python scripts/test_build.py --mode real
```

A run of 10-12 hours covers most channels' end of stream, which is when raids happen. Tracking more channels gives more relationships in the same time; chat opens one connection per 100 channels. Raids are read from the raided channel's chat, so every raid between two tracked channels is captured (raids out to untracked channels are not).

`auth.py` signs in a Twitch user for EventSub features (`relations.RaidListener`). The tracker doesn't need it: Twitch limits EventSub WebSocket subscriptions for other people's channels to a total cost of 10, so it only suits a handful of channels.

`main.py --mode real|hybrid` builds the network from this data (`hybrid` keeps attribute edges as weak background ties). Recommendations use the tracked history automatically: engagement from average viewers and chat activity, content matching from game history, reach from average viewers, and brand safety from Twitch content labels.

**Privacy:** the chat logger never stores message text. Chatters are stored only as salted SHA-256 hashes of their user id, with the salt kept locally in `data/processed/chat_salt.json`, to measure audience overlap between channels.

### Tests

```bash
python -m pytest        # no network access or credentials needed
python -m ruff check .  # lint
```

---

## 🏗️ Architecture

```
  Streamlit UI (app.py → ui/)      CLI (main.py)             tracker.py (long-running)
              │                          │                              │
              └────────────┬─────────────┘                              │
                           ▼                                            ▼
            twitchnet.twitch_api                          twitchnet.relations
            live streamers, users, channels,              chat audience overlap, raids,
            followers (batched Helix calls)               teams, co-streams
                           │                                            │
                           └──────────────┐          ┌──────────────────┘
                                          ▼          ▼
                                 twitchnet.database (SQLite)
                                              │
                                              ▼
                     twitchnet.graph_builder  (attribute | real | hybrid)
                                              │
                   ┌──────────────────────────┴──────────────────────────┐
                   ▼                                                     ▼
     centrality · community_detection                 similarity_calc · recommender · scoring
```

---

## 📁 Project Structure

```
twitchnet-analytics/
├── 📄 app.py                   # Streamlit UI entrypoint (page router)
├── 📄 main.py                  # CLI pipeline: collect → network → recommend
├── 📄 tracker.py               # Long-running relationship tracker
├── 📄 auth.py                  # Twitch user sign-in for EventSub (optional)
│
├── 📦 twitchnet/               # Core library
│   ├── config.py               # Settings, paths and credentials
│   ├── twitch_api.py           # Twitch API data collector
│   ├── relations.py            # Chat overlap, raids, teams, collabs
│   ├── content.py              # VODs, clips, schedules, top categories
│   ├── metrics.py              # Per-streamer metrics from tracked history
│   ├── database.py             # SQLite persistence and migrations
│   ├── graph_builder.py        # Network construction (attribute/real/hybrid)
│   ├── centrality.py           # Centrality calculations
│   ├── community_detection.py  # Louvain community detection
│   ├── similarity_calc.py      # Feature extraction & similarity
│   ├── recommender.py          # Recommendation engine
│   ├── scoring.py              # Advanced scoring algorithms
│   ├── company_profiles.py     # Company profile management
│   ├── advanced_viz.py         # Plotly charts
│   └── styles.py               # Custom CSS theming
│
├── 🎨 ui/                      # One module per Streamlit page
│   └── network_graph.py        # PyVis network builder
│
├── 🧪 tests/                   # pytest suite (no network access needed)
├── 🔧 scripts/                 # Utility scripts (network stats by mode)
│
└── 📂 data/                    # Local data (contents gitignored)
    ├── raw/                    # Raw API responses
    ├── processed/              # SQLite database, CSV exports, tokens
    └── network_graphs/         # Serialized graphs
```

---

## 📈 Centrality Metrics

| Metric | Description | Use Case |
|--------|-------------|----------|
| **PageRank** | Influence via incoming links | Find influential streamers |
| **Degree** | Number of connections | Find well-networked streamers |
| **Betweenness** | Bridge between communities | Find diverse audience reach |
| **Closeness** | Average distance to others | Find central streamers |
| **Eigenvector** | Connected to important nodes | Find elite circles |
| **Harmonic** | Works on disconnected graphs | Handle fragmented networks |
| **Load** | Bottleneck identification | Find key connectors |
| **Clustering** | Local connectivity | Find tight-knit groups |
| **Influence** | Weighted composite | Overall recommendation ranking |

---

## ⚙️ Configuration

Edit `twitchnet/config.py` to customize:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_FOLLOWERS` | 100 | Minimum followers to include |
| `MAX_STREAMERS` | 1000 | Maximum streamers to analyze |
| `CONTENT_SIMILARITY_WEIGHT` | 0.4 | Content matching weight |
| `CENTRALITY_WEIGHT` | 0.3 | Network position weight |
| `ENGAGEMENT_WEIGHT` | 0.2 | Engagement metrics weight |
| `AUDIENCE_FIT_WEIGHT` | 0.1 | Audience demographics weight |

---

## 🧪 Data Pipeline

```
COLLECT → BUILD → ANALYZE → VISUALIZE

Twitch API → NetworkX Graph → Centrality + Louvain → PyVis + Plotly
    │              │                  │                    │
    ▼              ▼                  ▼                    ▼
streamers.json  .gpickle      centrality.csv        in-app graph
                              communities.csv
```

---

## 🔧 Troubleshooting

<details>
<summary><strong>Common Issues</strong></summary>

| Problem | Solution |
|---------|----------|
| Streamlit won't start | Run `python -m py_compile app.py` to check for syntax errors |
| Blank network visualization | The graph loads vis-network from cdnjs; check that your network allows it |
| Slow graph rendering | Reduce edge cap in settings or filter to subgraph |
| Twitch API rate limits | Built-in backoff handles this; wait 10+ min if persistent |
| Missing CSV files | Run data collection step in the UI first |

</details>

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Twitch API](https://dev.twitch.tv/docs/api/) for streamer data
- [NetworkX](https://networkx.org/) for graph algorithms
- [PyVis](https://pyvis.readthedocs.io/) for interactive visualizations
- [Streamlit](https://streamlit.io/) for the dashboard framework
- [python-louvain](https://github.com/taynaud/python-louvain) for community detection

---

<p align="center">
  Made with ❤️ for the Twitch community
</p>
