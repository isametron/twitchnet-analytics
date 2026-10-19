"""Database backup script: consistent copy and pruning."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import backup_db  # noqa: E402


def test_backup_copies_data_and_prune_keeps_newest(tmp_path):
    db_path = str(tmp_path / 'source.db')
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE t (x INTEGER)')
    conn.executemany('INSERT INTO t VALUES (?)', [(i,) for i in range(100)])
    conn.commit()

    backup_dir = str(tmp_path / 'backups')
    copy = backup_db.backup(db_path, backup_dir)
    conn.close()
    assert sqlite3.connect(copy).execute('SELECT COUNT(*) FROM t').fetchone()[0] == 100

    for stamp in ('20260101-000000', '20260102-000000', '20260103-000000'):
        open(os.path.join(backup_dir, f'twitchnet-{stamp}.db'), 'w').close()
    assert backup_db.prune(backup_dir, keep=2) == 2
    assert sorted(os.listdir(backup_dir))[0] == 'twitchnet-20260103-000000.db'
