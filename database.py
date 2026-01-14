import sqlite3
import json
import pickle
import networkx as nx
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from config import Config

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
        
        # Streamers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streamers (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                display_name TEXT,
                game_name TEXT,
                follower_count INTEGER,
                view_count INTEGER,
                language TEXT,
                is_partner BOOLEAN,
                is_live BOOLEAN,
                viewer_count INTEGER,
                stream_title TEXT,
                thumbnail_url TEXT,
                profile_image_url TEXT,
                created_at TEXT,
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
        
        self.conn.commit()
        print(f"Database initialized at {self.db_path}")
    
    # ==================== STREAMER OPERATIONS ====================
    
    def save_streamers(self, streamers_data: List[Dict]) -> int:
        """Save or update streamer data"""
        cursor = self.conn.cursor()
        saved_count = 0
        
        for streamer in streamers_data:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO streamers 
                    (user_id, username, display_name, game_name, follower_count, 
                     view_count, language, is_partner, is_live, viewer_count, 
                     stream_title, thumbnail_url, profile_image_url, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    streamer.get('user_id'),
                    streamer.get('username'),
                    streamer.get('display_name'),
                    streamer.get('game_name'),
                    streamer.get('follower_count'),
                    streamer.get('view_count'),
                    streamer.get('language'),
                    streamer.get('is_partner'),
                    streamer.get('is_live'),
                    streamer.get('viewer_count'),
                    streamer.get('stream_title'),
                    streamer.get('thumbnail_url'),
                    streamer.get('profile_image_url'),
                    streamer.get('created_at')
                ))
                saved_count += 1
            except Exception as e:
                print(f"Error saving streamer {streamer.get('username')}: {e}")
        
        self.conn.commit()
        return saved_count
    
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
