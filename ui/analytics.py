"""Analytics page: follower, game, demographic and network insight dashboards."""
import traceback

import pandas as pd
import plotly.express as px
import streamlit as st


def render():
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
