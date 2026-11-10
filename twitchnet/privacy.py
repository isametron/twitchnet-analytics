"""
Chatter hashing and opt-outs.

Accounts that opt out are remembered only as a salted hash of their Twitch user id.
OptOutList keeps them out of newly collected data; forget_user removes what is already stored.
The salt is per installation, so opt-outs must be processed where the data lives (the tracker server).
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Dict, List

from twitchnet.config import Config

SALT_PATH = os.path.join(Config.PROCESSED_DATA_DIR, 'chat_salt.json')
RAW_STREAMERS_PATH = os.path.join(Config.RAW_DATA_DIR, 'streamers.json')


def load_chat_salt(path: str = SALT_PATH) -> str:
    """Per-installation secret salt for chatter hashes; created on first use"""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)['salt']
    salt = secrets.token_hex(16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'salt': salt}, f)
    return salt


def hash_chatter(user_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{user_id}".encode('utf-8')).hexdigest()


class OptOutList:
    """Checks user ids against the stored opt-outs; call refresh() to pick up new ones"""

    def __init__(self, db, salt: str = None):
        self.db = db
        self._salt = salt
        self.hashes = set()
        self.refresh()

    def refresh(self):
        self.hashes = self.db.load_opt_outs()

    def contains(self, user_id: str) -> bool:
        if not self.hashes:
            return False
        if self._salt is None:
            self._salt = load_chat_salt()
        return hash_chatter(str(user_id), self._salt) in self.hashes

    def filter(self, rows: List[Dict], key: str = 'user_id') -> List[Dict]:
        """Rows whose `key` column isn't an opted-out account"""
        return [row for row in rows if not self.contains(row[key])]


def forget_user(db, user_id: str, salt: str = None, raw_streamers_path: str = RAW_STREAMERS_PATH) -> Dict[str, int]:
    """
    Record an opt-out and delete everything stored about the account, as a chatter and as a channel.
    Returns the number of rows deleted per table.
    """
    chatter_hash = hash_chatter(str(user_id), salt or load_chat_salt())
    deleted = db.forget_user(str(user_id), chatter_hash, datetime.now(timezone.utc).isoformat(timespec='seconds'))

    if os.path.exists(raw_streamers_path):
        with open(raw_streamers_path, 'r', encoding='utf-8') as f:
            streamers = json.load(f)
        kept = [s for s in streamers if str(s.get('user_id')) != str(user_id)]
        if len(kept) != len(streamers):
            with open(raw_streamers_path, 'w', encoding='utf-8') as f:
                json.dump(kept, f, indent=2, ensure_ascii=False)
            deleted['streamers.json'] = len(streamers) - len(kept)
    return deleted
