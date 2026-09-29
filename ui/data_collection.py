"""Data Collection page: fetch streamers from the Twitch API."""
import asyncio
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from twitchnet.config import Config
from twitchnet.twitch_api import TwitchDataCollector


def render():
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

            status_text.text("💾 Saving data...")
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
