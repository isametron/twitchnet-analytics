import os
import sys

from dotenv import load_dotenv

# Repository root (this file lives in <root>/twitchnet/), so paths work from any working directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


class Config:
    """Configuration settings for the Twitch-Company matching system"""

    # Twitch API credentials
    TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID', 'your_client_id_here')
    TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET', 'your_client_secret_here')

    # Data paths
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
    RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
    PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
    NETWORK_GRAPHS_DIR = os.path.join(DATA_DIR, 'network_graphs')

    # Network analysis parameters
    MIN_FOLLOWERS = 100  # Minimum followers to include in analysis
    MAX_STREAMERS = 1000  # Maximum number of streamers to analyze

    # Matching algorithm weights
    CONTENT_SIMILARITY_WEIGHT = 0.4
    CENTRALITY_WEIGHT = 0.3
    ENGAGEMENT_WEIGHT = 0.2
    AUDIENCE_FIT_WEIGHT = 0.1

    # Output settings
    TOP_N_RECOMMENDATIONS = 10

    @staticmethod
    def make_console_safe():
        """
        Stop emoji progress prints from crashing when stdout isn't UTF-8 (e.g. redirected on Windows),
        and flush output line by line so long-running processes like tracker.py show up in log files.
        """
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(errors='backslashreplace', line_buffering=True)

    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(cls.RAW_DATA_DIR, exist_ok=True)
        os.makedirs(cls.PROCESSED_DATA_DIR, exist_ok=True)
        os.makedirs(cls.NETWORK_GRAPHS_DIR, exist_ok=True)
