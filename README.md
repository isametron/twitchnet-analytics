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
- Twitch API integration with rate limiting
- Exponential backoff on API errors
- Multi-language streamer discovery
- Follower count, game, tags, partner status

</td>
<td width="50%">

### 🕸️ Network Analysis
- Multi-reason edge connections
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

### Relationship tracking

By default the network links streamers who share attributes (game, language, tags, partner status, follower tier). `tracker.py` collects **observed** relationships instead:

| Signal | Source | Needs |
|--------|--------|-------|
| Chat audience overlap | Anonymous Twitch chat (IRC) | Nothing |
| Raids | EventSub WebSocket | Twitch sign-in (one time) |
| Teams | Helix `teams` endpoints | App credentials |
| Co-streams | Shared Chat sessions + `@mentions` in stream titles | App credentials |

```bash
# 1. Choose channels to track: the top 100 live right now
python tracker.py --seed --live

# 2. One-time Twitch sign-in for raids (opens your browser)
#    Requires http://localhost:17563 as an OAuth Redirect URL on your Twitch application
python auth.py

# 3. Run the tracker (Ctrl+C to stop; --no-raids skips the sign-in)
python tracker.py

# Compare network structure with and without the observed relationships
python scripts/test_build.py --mode attribute
python scripts/test_build.py --mode real
```

`main.py --mode real|hybrid` builds the network from this data. `hybrid` keeps attribute edges as weak background ties.

**Privacy:** the chat logger never stores message text. Chatters are stored only as salted SHA-256 hashes of their user id, with the salt kept locally in `data/processed/chat_salt.json`, to measure audience overlap between channels.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT UI (app.py)                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│
│  │   Network    │ │  Analytics   │ │  Dashboard   │ │   Data      ││
│  │   Analysis   │ │   Charts     │ │   Metrics    │ │ Collection  ││
│  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│  twitch_api.py  │    │ graph_builder.py│    │   recommender.py    │
│  Data Collector │    │ Network Builder │    │ Recommendation      │
└─────────────────┘    └─────────────────┘    └─────────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│  centrality.py  │    │community_detect │    │    scoring.py       │
│  Network Metrics│    │ Louvain Algo    │    │ Advanced Scoring    │
└─────────────────┘    └─────────────────┘    └─────────────────────┘
```

---

## 📁 Project Structure

```
twitchnet-analytics/
├── 📄 app.py                 # Streamlit UI entrypoint (page router)
├── 📄 main.py                # CLI entrypoint
├── 📄 tracker.py             # Long-running relationship tracker
├── 📄 auth.py                # Twitch user sign-in (OAuth)
├── 📄 config.py              # Configuration settings
│
├── 🔌 Core Modules
│   ├── twitch_api.py         # Twitch API data collector
│   ├── graph_builder.py      # Network graph construction
│   ├── relations.py          # Chat overlap, raids, teams, collabs
│   ├── centrality.py         # Centrality calculations
│   ├── community_detection.py# Louvain community detection
│   ├── similarity_calc.py    # Feature extraction & similarity
│   ├── recommender.py        # Recommendation engine
│   └── scoring.py            # Advanced scoring algorithms
│
├── 🎨 UI & Visualization
│   ├── ui/                   # One module per Streamlit page
│   │   └── network_graph.py  # PyVis network builder
│   ├── advanced_viz.py       # Plotly charts
│   └── styles.py             # Custom CSS theming
│
├── 💾 Data Layer
│   ├── database.py           # SQLite persistence
│   └── company_profiles.py   # Company profile management
│
├── 📂 data/
│   ├── raw/                  # Raw API responses
│   ├── processed/            # Processed CSV files
│   └── network_graphs/       # Serialized graphs
│
└── 📂 scripts/               # Utility scripts
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

Edit `config.py` to customize:

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
