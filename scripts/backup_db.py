"""
Make a consistent copy of the SQLite database, safe to run while tracker.py is writing.

  python scripts/backup_db.py                 -> data/processed/backups/twitchnet-<UTC timestamp>.db
  python scripts/backup_db.py --keep 7        also delete all but the 7 newest backups
"""
import argparse
import glob
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from twitchnet.config import Config  # noqa: E402

DB_PATH = os.path.join(Config.PROCESSED_DATA_DIR, 'twitchnet.db')
BACKUP_DIR = os.path.join(Config.PROCESSED_DATA_DIR, 'backups')


def backup(db_path: str = DB_PATH, backup_dir: str = BACKUP_DIR) -> str:
    """Copy db_path with SQLite's online backup API (consistent even during writes); returns the copy's path"""
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    target = os.path.join(backup_dir, f'twitchnet-{stamp}.db')
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def prune(backup_dir: str, keep: int) -> int:
    """Delete all but the `keep` newest backups; returns how many were deleted"""
    backups = sorted(glob.glob(os.path.join(backup_dir, 'twitchnet-*.db')))
    old = backups[:-keep] if keep > 0 else []
    for path in old:
        os.remove(path)
    return len(old)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--keep', type=int, default=0, help='keep only the N newest backups (default: keep all)')
    args = parser.parse_args()
    path = backup()
    print(f"Backup written to {path} ({os.path.getsize(path) / 1048576:.1f} MB)")
    if args.keep:
        print(f"Removed {prune(BACKUP_DIR, args.keep)} old backups")
