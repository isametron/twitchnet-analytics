"""Build the interactive PyVis network HTML for the Network Analysis page."""
from datetime import datetime

import networkx as nx
import numpy as np
from pyvis.network import Network


def build_network_html(display_graph, color_by, metric_scores, pagerank,
                       show_same_game, show_same_language, show_strong_connections,
                       show_both_partners, show_same_tier, strong_conn_threshold):
    """Render display_graph with PyVis; returns (html, edge_counts per connection type)."""
    net = Network(
        height="650px",
        width="100%",
        bgcolor="#0f0e17",
        font_color="#e6e6e6",
        directed=False,
        cdn_resources="remote",  # load vis-network from cdnjs instead of writing a local lib/ folder
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
                except Exception:
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
            except Exception:
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

    return net.generate_html(), edge_counts
