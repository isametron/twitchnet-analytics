import sqlite3
import json
import pickle
import networkx as nx
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from config import Config

# Streamer record fields (as produced by TwitchDataCollector) and their SQLite types
STREAMER_COLUMNS = {
    'user_id': 'TEXT PRIMARY KEY',
    'username': 'TEXT NOT NULL',
    'display_name': 'TEXT',
    'description': 'TEXT',
    'game_name': 'TEXT',
    'game_id': 'TEXT',
    'follower_count': 'INTEGER',
    'language': 'TEXT',
    'tags': 'TEXT',
    'is_partner': 'BOOLEAN',
    'broadcaster_type': 'TEXT',
    'is_live': 'BOOLEAN',
    'viewer_count': 'INTEGER',
    'stream_title': 'TEXT',
    'thumbnail_url': 'TEXT',
    'started_at': 'TEXT',
    'content_classification_labels': 'TEXT',
    'is_branded_content': 'BOOLEAN',
    'profile_image_url': 'TEXT',
    'created_at': 'TEXT',
}
STREAMER_JSON_COLUMNS = {'tags', 'content_classification_labels'}
STREAMER_BOOL_COLUMNS = {'is_partner', 'is_live', 'is_branded_content'}
# Columns from earlier versions that are no longer collected
DROPPED_STREAMER_COLUMNS = [
    'view_count',  # deprecated by Twitch, always 0
    'is_mature',   # replaced by content_classification_labels, always false
]

# Time-series and relationship tables used by the tracker, relations and metrics modules
EXTRA_TABLES = [
    '''CREATE TABLE IF NOT EXISTS stream_snapshots (
        user_id TEXT, ts TEXT, viewer_count INTEGER, game_id TEXT, game_name TEXT, title TEXT,
        PRIMARY KEY (user_id, ts))''',
    '''CREATE TABLE IF NOT EXISTS follower_snapshots (
        user_id TEXT, ts TEXT, followers INTEGER,
        PRIMARY KEY (user_id, ts))''',
    # Chatters are stored as salted hashes: only set overlap between channels is needed
    '''CREATE TABLE IF NOT EXISTS chat_presence (
        channel_id TEXT, chatter_hash TEXT, first_seen TEXT, last_seen TEXT, msg_count INTEGER,
        PRIMARY KEY (channel_id, chatter_hash))''',
    '''CREATE TABLE IF NOT EXISTS raids (
        from_id TEXT, to_id TEXT, ts TEXT, viewers INTEGER,
        PRIMARY KEY (from_id, to_id, ts))''',
    '''CREATE TABLE IF NOT EXISTS team_members (
        team_id TEXT, team_name TEXT, user_id TEXT,
        PRIMARY KEY (team_id, user_id))''',
    # Undirected: a_id < b_id; source is 'shared_chat' or 'title_mention'
    '''CREATE TABLE IF NOT EXISTS collabs (
        a_id TEXT, b_id TEXT, ts TEXT, source TEXT,
        PRIMARY KEY (a_id, b_id, ts, source))''',
    '''CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY, user_id TEXT, created_at TEXT, duration_s INTEGER,
        view_count INTEGER, title TEXT)''',
    '''CREATE TABLE IF NOT EXISTS clips (
        clip_id TEXT PRIMARY KEY, broadcaster_id TEXT, created_at TEXT, view_count INTEGER,
        game_id TEXT, title TEXT)''',
    '''CREATE TABLE IF NOT EXISTS top_games (
        ts TEXT, game_id TEXT, name TEXT, rank INTEGER, viewer_sum INTEGER,
        PRIMARY KEY (ts, game_id))''',
    '''CREATE TABLE IF NOT EXISTS tracked_channels (
        user_id TEXT PRIMARY KEY, login TEXT, added_at TEXT)''',
]


class DatabaseManager:
    """Manage persistent storage for streamer data, graphs, and analytics"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = f"{Config.PROCESSED_DATA_DIR}/twitchnet.db"
        
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def initialize_database(self):
        """Create database tables if they don't exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Streamers table (latest state per streamer; history lives in the snapshot tables)
        column_defs = ',\n'.join(f"{name} {sql_type}" for name, sql_type in STREAMER_COLUMNS.items())
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS streamers (
                {column_defs},
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Network graphs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_graphs (
                graph_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                graph_data BLOB,
                node_count INTEGER,
                edge_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Communities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS communities (
                community_id INTEGER,
                graph_id INTEGER,
                node_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (graph_id) REFERENCES network_graphs(graph_id),
                PRIMARY KEY (community_id, graph_id, node_id)
            )
        ''')
        
        # Centrality scores table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS centrality_scores (
                node_id TEXT,
                graph_id INTEGER,
                metric_name TEXT,
                score REAL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (graph_id) REFERENCES network_graphs(graph_id),
                PRIMARY KEY (node_id, graph_id, metric_name)
            )
        ''')
        
        # Cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                cache_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        
        # Sessions table for tracking data collection runs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                games TEXT,
                streamer_count INTEGER,
                language_diversity BOOLEAN,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        for ddl in EXTRA_TABLES:
            cursor.execute(ddl)

        self.conn.commit()
        self._migrate()
        print(f"Database initialized at {self.db_path}")

    def _migrate(self):
        """Bring a streamers table created by an older version up to the current columns (idempotent)"""
        cursor = self.conn.cursor()
        existing = {row[1] for row in cursor.execute("PRAGMA table_info(streamers)")}

        for name, sql_type in STREAMER_COLUMNS.items():
            if name not in existing:
                # ADD COLUMN can't carry PRIMARY KEY / NOT NULL constraints; the plain type is enough
                cursor.execute(f"ALTER TABLE streamers ADD COLUMN {name} {sql_type.split()[0]}")

        for name in DROPPED_STREAMER_COLUMNS:
            if name in existing:
                cursor.execute(f"ALTER TABLE streamers DROP COLUMN {name}")

        self.conn.commit()

    def _insert_rows(self, table: str, rows: List[Dict], conflict: str = 'OR REPLACE') -> int:
        """Insert dict rows (all with the same keys) into an internal table in one transaction"""
        if not rows:
            return 0
        columns = list(rows[0])
        placeholders = ', '.join('?' for _ in columns)
        with self.conn:
            self.conn.executemany(
                f"INSERT {conflict} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                [tuple(row.get(col) for col in columns) for row in rows]
            )
        return len(rows)

    def _select_rows(self, table: str, conditions: Dict = None, order_by: str = None) -> List[Dict]:
        """Select rows from an internal table; condition keys are 'column' or 'column op' (e.g. 'ts >=')"""
        query = f"SELECT * FROM {table}"
        clauses, params = [], []
        for column_op, value in (conditions or {}).items():
            if value is not None:
                column, _, op = column_op.partition(' ')
                clauses.append(f"{column} {op or '='} ?")
                params.append(value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        if order_by:
            query += f" ORDER BY {order_by}"

        cursor = self.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # ==================== STREAMER OPERATIONS ====================
    
    def save_streamers(self, streamers_data: List[Dict]) -> int:
        """Save or update streamer data; records with follower_count_known=False keep the stored count"""
        unknown_ids = [s['user_id'] for s in streamers_data if s.get('follower_count_known') is False]
        stored_counts = {}
        if unknown_ids:
            placeholders = ', '.join('?' for _ in unknown_ids)
            stored_counts = dict(self.conn.execute(
                f"SELECT user_id, follower_count FROM streamers WHERE user_id IN ({placeholders})", unknown_ids
            ).fetchall())

        rows = []
        for streamer in streamers_data:
            row = {col: streamer.get(col) for col in STREAMER_COLUMNS}
            if streamer.get('follower_count_known') is False:
                row['follower_count'] = stored_counts.get(streamer['user_id'], row['follower_count'])
            for col in STREAMER_JSON_COLUMNS:
                row[col] = json.dumps(row[col] or [], ensure_ascii=False)
            rows.append(row)
        return self._insert_rows('streamers', rows)
    
    def load_streamers(self, filters: Dict = None) -> List[Dict]:
        """Load streamers with optional filters"""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM streamers"
        params = []
        
        if filters:
            conditions = []
            if 'game_name' in filters:
                conditions.append("game_name = ?")
                params.append(filters['game_name'])
            if 'language' in filters:
                conditions.append("language = ?")
                params.append(filters['language'])
            if 'min_followers' in filters:
                conditions.append("follower_count >= ?")
                params.append(filters['min_followers'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        
        streamers = []
        for row in cursor.fetchall():
            streamer = dict(zip(columns, row))
            for col in STREAMER_JSON_COLUMNS:
                streamer[col] = json.loads(streamer[col]) if streamer.get(col) else []
            for col in STREAMER_BOOL_COLUMNS:
                streamer[col] = bool(streamer.get(col))
            streamers.append(streamer)

        return streamers
    
    def get_streamer_count(self) -> int:
        """Get total number of streamers in database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM streamers")
        return cursor.fetchone()[0]
    
    # ==================== GRAPH OPERATIONS ====================
    
    def save_graph(self, graph: nx.Graph, name: str, description: str = "") -> int:
        """Save a NetworkX graph to database"""
        cursor = self.conn.cursor()
        
        # Serialize graph
        graph_bytes = pickle.dumps(graph)
        
        cursor.execute('''
            INSERT INTO network_graphs (name, description, graph_data, node_count, edge_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, graph_bytes, graph.number_of_nodes(), graph.number_of_edges()))
        
        graph_id = cursor.lastrowid
        self.conn.commit()
        
        print(f"Graph '{name}' saved with ID {graph_id}")
        return graph_id
    
    def load_graph(self, graph_id: int = None, name: str = None) -> Tuple[Optional[nx.Graph], Optional[int]]:
        """Load a graph by ID or name (returns most recent if name given)"""
        cursor = self.conn.cursor()
        
        if graph_id:
            cursor.execute("SELECT graph_id, graph_data FROM network_graphs WHERE graph_id = ?", (graph_id,))
        elif name:
            cursor.execute("""
                SELECT graph_id, graph_data FROM network_graphs 
                WHERE name = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (name,))
        else:
            cursor.execute("""
                SELECT graph_id, graph_data FROM network_graphs 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
        
        result = cursor.fetchone()
        if result:
            graph_id, graph_bytes = result
            graph = pickle.loads(graph_bytes)
            return graph, graph_id
        
        return None, None
    
    def list_graphs(self) -> List[Dict]:
        """List all saved graphs"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT graph_id, name, description, node_count, edge_count, created_at 
            FROM network_graphs 
            ORDER BY created_at DESC
        """)
        
        graphs = []
        for row in cursor.fetchall():
            graphs.append({
                'graph_id': row[0],
                'name': row[1],
                'description': row[2],
                'node_count': row[3],
                'edge_count': row[4],
                'created_at': row[5]
            })
        
        return graphs
    
    def delete_graph(self, graph_id: int):
        """Delete a graph and associated data"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM centrality_scores WHERE graph_id = ?", (graph_id,))
        cursor.execute("DELETE FROM communities WHERE graph_id = ?", (graph_id,))
        cursor.execute("DELETE FROM network_graphs WHERE graph_id = ?", (graph_id,))
        self.conn.commit()
    
    # ==================== COMMUNITY OPERATIONS ====================
    
    def save_communities(self, communities: Dict, graph_id: int):
        """Save community assignments"""
        cursor = self.conn.cursor()
        
        # Clear existing communities for this graph
        cursor.execute("DELETE FROM communities WHERE graph_id = ?", (graph_id,))
        
        # Insert new communities
        for comm_id, members in communities.items():
            for node_id in members:
                cursor.execute('''
                    INSERT INTO communities (community_id, graph_id, node_id)
                    VALUES (?, ?, ?)
                ''', (comm_id, graph_id, node_id))
        
        self.conn.commit()
    
    def load_communities(self, graph_id: int) -> Dict:
        """Load community assignments for a graph"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT community_id, node_id 
            FROM communities 
            WHERE graph_id = ?
        """, (graph_id,))
        
        communities = {}
        for comm_id, node_id in cursor.fetchall():
            if comm_id not in communities:
                communities[comm_id] = []
            communities[comm_id].append(node_id)
        
        return communities
    
    # ==================== CENTRALITY OPERATIONS ====================
    
    def save_centrality_scores(self, scores: Dict[str, Dict], graph_id: int):
        """Save centrality scores for a graph"""
        cursor = self.conn.cursor()
        
        # Clear existing scores for this graph
        cursor.execute("DELETE FROM centrality_scores WHERE graph_id = ?", (graph_id,))
        
        # Insert new scores
        for metric_name, node_scores in scores.items():
            for node_id, score in node_scores.items():
                cursor.execute('''
                    INSERT INTO centrality_scores (node_id, graph_id, metric_name, score)
                    VALUES (?, ?, ?, ?)
                ''', (node_id, graph_id, metric_name, score))
        
        self.conn.commit()
    
    def load_centrality_scores(self, graph_id: int) -> Dict[str, Dict]:
        """Load centrality scores for a graph"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT metric_name, node_id, score 
            FROM centrality_scores 
            WHERE graph_id = ?
        """, (graph_id,))
        
        scores = {}
        for metric_name, node_id, score in cursor.fetchall():
            if metric_name not in scores:
                scores[metric_name] = {}
            scores[metric_name][node_id] = score
        
        return scores
    
    # ==================== CACHE OPERATIONS ====================
    
    def set_cache(self, key: str, value: any, ttl_seconds: int = 3600):
        """Set a cache value with TTL"""
        cursor = self.conn.cursor()
        
        expires_at = datetime.now().timestamp() + ttl_seconds
        value_json = json.dumps(value)
        
        cursor.execute('''
            INSERT OR REPLACE INTO api_cache (cache_key, cache_value, expires_at)
            VALUES (?, ?, ?)
        ''', (key, value_json, expires_at))
        
        self.conn.commit()
    
    def get_cache(self, key: str) -> Optional[any]:
        """Get a cache value if not expired"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT cache_value, expires_at 
            FROM api_cache 
            WHERE cache_key = ?
        """, (key,))
        
        result = cursor.fetchone()
        if result:
            value_json, expires_at = result
            if datetime.now().timestamp() < expires_at:
                return json.loads(value_json)
            else:
                # Expired, delete it
                cursor.execute("DELETE FROM api_cache WHERE cache_key = ?", (key,))
                self.conn.commit()
        
        return None
    
    def clear_expired_cache(self):
        """Remove all expired cache entries"""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM api_cache 
            WHERE expires_at < ?
        """, (datetime.now().timestamp(),))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
    
    # ==================== SESSION OPERATIONS ====================
    
    def save_session(self, games: List[str], streamer_count: int, 
                    language_diversity: bool, started_at: datetime, 
                    completed_at: datetime = None) -> int:
        """Save a data collection session"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO collection_sessions 
            (games, streamer_count, language_diversity, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (json.dumps(games), streamer_count, language_diversity, 
              started_at.isoformat(), completed_at.isoformat() if completed_at else None))
        
        session_id = cursor.lastrowid
        self.conn.commit()
        return session_id
    
    def get_latest_session(self) -> Optional[Dict]:
        """Get the most recent collection session"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM collection_sessions 
            ORDER BY started_at DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if result:
            return {
                'session_id': result[0],
                'games': json.loads(result[1]),
                'streamer_count': result[2],
                'language_diversity': result[3],
                'started_at': result[4],
                'completed_at': result[5]
            }
        return None
    
    # ==================== TIME SERIES OPERATIONS ====================

    def save_stream_snapshots(self, snapshots: List[Dict]) -> int:
        """Save live stream samples: user_id, ts, viewer_count, game_id, game_name, title"""
        return self._insert_rows('stream_snapshots', snapshots)

    def load_stream_snapshots(self, user_id: str = None, since: str = None) -> List[Dict]:
        return self._select_rows('stream_snapshots', {'user_id': user_id, 'ts >=': since}, 'user_id, ts')

    def save_follower_snapshots(self, snapshots: List[Dict]) -> int:
        """Save follower totals over time: user_id, ts, followers"""
        return self._insert_rows('follower_snapshots', snapshots)

    def load_follower_snapshots(self, user_id: str = None, since: str = None) -> List[Dict]:
        return self._select_rows('follower_snapshots', {'user_id': user_id, 'ts >=': since}, 'user_id, ts')

    def save_top_games(self, rows: List[Dict]) -> int:
        """Save a top-categories snapshot: ts, game_id, name, rank, viewer_sum"""
        return self._insert_rows('top_games', rows)

    def load_top_games(self, since: str = None) -> List[Dict]:
        return self._select_rows('top_games', {'ts >=': since}, 'ts, rank')

    # ==================== RELATIONSHIP OPERATIONS ====================

    def save_chat_presence(self, rows: List[Dict]) -> int:
        """
        Merge chatter sightings: channel_id, chatter_hash, first_seen, last_seen, msg_count.
        Existing rows keep their first_seen, extend last_seen and add to msg_count.
        """
        if not rows:
            return 0
        with self.conn:
            self.conn.executemany('''
                INSERT INTO chat_presence (channel_id, chatter_hash, first_seen, last_seen, msg_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (channel_id, chatter_hash) DO UPDATE SET
                    last_seen = MAX(last_seen, excluded.last_seen),
                    msg_count = msg_count + excluded.msg_count
            ''', [(r['channel_id'], r['chatter_hash'], r['first_seen'], r['last_seen'], r['msg_count'])
                  for r in rows])
        return len(rows)

    def load_chat_presence(self, channel_id: str = None) -> List[Dict]:
        return self._select_rows('chat_presence', {'channel_id': channel_id})

    def save_raids(self, raids: List[Dict]) -> int:
        """Save raids: from_id, to_id, ts, viewers"""
        return self._insert_rows('raids', raids, conflict='OR IGNORE')

    def load_raids(self, since: str = None) -> List[Dict]:
        return self._select_rows('raids', {'ts >=': since}, 'ts')

    def save_team_members(self, members: List[Dict]) -> int:
        """Save team membership: team_id, team_name, user_id"""
        return self._insert_rows('team_members', members)

    def load_team_members(self, team_id: str = None) -> List[Dict]:
        return self._select_rows('team_members', {'team_id': team_id})

    def save_collabs(self, collabs: List[Dict]) -> int:
        """Save collaborations: a_id, b_id, ts, source (pair order is normalized)"""
        rows = [dict(c, a_id=min(c['a_id'], c['b_id']), b_id=max(c['a_id'], c['b_id'])) for c in collabs]
        return self._insert_rows('collabs', rows, conflict='OR IGNORE')

    def load_collabs(self, source: str = None) -> List[Dict]:
        return self._select_rows('collabs', {'source': source}, 'ts')

    # ==================== CONTENT OPERATIONS ====================

    def save_videos(self, videos: List[Dict]) -> int:
        """Save past broadcasts: video_id, user_id, created_at, duration_s, view_count, title"""
        return self._insert_rows('videos', videos)

    def load_videos(self, user_id: str = None) -> List[Dict]:
        return self._select_rows('videos', {'user_id': user_id}, 'created_at')

    def save_clips(self, clips: List[Dict]) -> int:
        """Save clips: clip_id, broadcaster_id, created_at, view_count, game_id, title"""
        return self._insert_rows('clips', clips)

    def load_clips(self, broadcaster_id: str = None) -> List[Dict]:
        return self._select_rows('clips', {'broadcaster_id': broadcaster_id}, 'created_at')

    # ==================== TRACKER OPERATIONS ====================

    def add_tracked_channels(self, channels: List[Dict]) -> int:
        """Add channels (user_id, login) for the tracker to follow; existing entries are kept"""
        now = datetime.now().isoformat()
        rows = [{'user_id': c['user_id'], 'login': c['login'], 'added_at': c.get('added_at', now)}
                for c in channels]
        return self._insert_rows('tracked_channels', rows, conflict='OR IGNORE')

    def load_tracked_channels(self) -> List[Dict]:
        return self._select_rows('tracked_channels', order_by='added_at')

    def remove_tracked_channels(self, user_ids: List[str]):
        with self.conn:
            self.conn.executemany("DELETE FROM tracked_channels WHERE user_id = ?", [(uid,) for uid in user_ids])

    # ==================== UTILITY OPERATIONS ====================
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM streamers")
        stats['total_streamers'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM network_graphs")
        stats['total_graphs'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT graph_id) FROM communities")
        stats['graphs_with_communities'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM api_cache WHERE expires_at > ?", 
                      (datetime.now().timestamp(),))
        stats['active_cache_entries'] = cursor.fetchone()[0]
        
        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['database_size_bytes'] = cursor.fetchone()[0]
        stats['database_size_mb'] = round(stats['database_size_bytes'] / (1024 * 1024), 2)
        
        return stats
    
    def export_to_json(self, output_file: str):
        """Export all data to JSON file"""
        data = {
            'streamers': self.load_streamers(),
            'graphs': self.list_graphs(),
            'export_date': datetime.now().isoformat()
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Data exported to {output_file}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()


if __name__ == "__main__":
    # Test database
    db = DatabaseManager()
    stats = db.get_stats()
    print("\nDatabase Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
