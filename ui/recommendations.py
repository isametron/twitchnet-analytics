"""Recommendations page: company profile matching, budget optimization and campaigns."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from twitchnet.company_profiles import CompanyProfile
from twitchnet.metrics import enrich_streamers
from twitchnet.recommender import StreamerRecommender
from twitchnet.similarity_calc import FeatureExtractor, SimilarityCalculator


def render():
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
                streamers_df = pd.DataFrame(
                    enrich_streamers(st.session_state.streamers_data, st.session_state.db))

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

                    # Convert recommendations to format expected by allocate_budget
                    streamers_list = []
                    for _, row in recommendations.iterrows():
                        streamers_list.append({
                            'user_id': row['user_id'],
                            'display_name': row['display_name'],
                            'username': row['username'],
                            'follower_count': row['follower_count'],
                            'estimated_roi': row['composite_score'] * 0.1,
                            'avg_viewers': row.get('avg_viewers')
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
                            'estimated_roi': row['composite_score'] * 0.1,
                            'avg_viewers': row.get('avg_viewers')
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

                    streamers_list = []
                    for _, row in recommendations.iterrows():
                        streamers_list.append({
                            'user_id': row['user_id'],
                            'display_name': row['display_name'],
                            'username': row['username'],
                            'follower_count': row['follower_count'],
                            'estimated_roi': row['composite_score'] * 0.1,
                            'avg_viewers': row.get('avg_viewers')
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
