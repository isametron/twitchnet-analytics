# Processed Data Directory

This directory contains the local database, analysis exports and local credentials.

## Contents

- `twitchnet.db` - SQLite database: streamers, saved graphs, snapshots and relationship data
- `nodes.csv` - Streamer node attributes
- `edges.csv` - Edge list with weights and connection types
- `centrality_scores.csv` - Calculated centrality metrics
- `communities.csv` - Community assignments
- `recommendations_*.csv` - Generated recommendations
- `user_token.json` - Twitch user token from `auth.py` (keep private)
- `chat_salt.json` - Local salt for chatter hashes (keep private)

## Notes

- Files in this directory are excluded from version control
- Run the dashboard, `main.py` or `tracker.py` to populate this directory
