"""DatabaseManager schema, migration and round-trip tests on temporary SQLite files."""
import sqlite3

import pytest

from database import STREAMER_COLUMNS, DatabaseManager


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def streamer(user_id='1', **overrides):
    record = {
        'user_id': user_id, 'username': f'user{user_id}', 'display_name': f'User {user_id}',
        'description': 'desc', 'follower_count': 1234, 'game_name': 'Game', 'game_id': 'g1',
        'language': 'en', 'tags': ['English', 'FPS'], 'is_partner': True, 'broadcaster_type': 'partner',
        'is_live': True, 'viewer_count': 42, 'stream_title': 'title', 'thumbnail_url': 'thumb',
        'started_at': '2026-09-27 10:00:00+00:00',
        'content_classification_labels': ['Gambling'], 'is_branded_content': True,
        'profile_image_url': 'img', 'created_at': '2015-01-01 00:00:00+00:00',
    }
    record.update(overrides)
    return record


def columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_initialization_is_idempotent(tmp_path):
    path = str(tmp_path / 'twice.db')
    DatabaseManager(path).close()
    manager = DatabaseManager(path)
    assert columns(manager.conn, 'streamers') == set(STREAMER_COLUMNS) | {'last_updated'}
    manager.close()


def test_migrates_legacy_streamers_table(tmp_path):
    path = str(tmp_path / 'legacy.db')
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE streamers (
            user_id TEXT PRIMARY KEY, username TEXT NOT NULL, display_name TEXT, game_name TEXT,
            follower_count INTEGER, view_count INTEGER, language TEXT, is_partner BOOLEAN,
            is_live BOOLEAN, viewer_count INTEGER, stream_title TEXT, thumbnail_url TEXT,
            profile_image_url TEXT, created_at TEXT, is_mature BOOLEAN,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.execute("INSERT INTO streamers (user_id, username, follower_count, view_count, is_partner) "
                 "VALUES ('7', 'old', 99, 0, 1)")
    conn.commit()
    conn.close()

    manager = DatabaseManager(path)
    cols = columns(manager.conn, 'streamers')
    assert 'view_count' not in cols and 'is_mature' not in cols
    assert {'tags', 'description', 'content_classification_labels', 'is_branded_content'} <= cols

    [row] = manager.load_streamers()
    assert row['username'] == 'old' and row['follower_count'] == 99
    assert row['tags'] == [] and row['is_partner'] is True and row['is_branded_content'] is False
    manager.close()


def test_streamer_round_trip_keeps_lists_and_bools(db):
    original = streamer()
    assert db.save_streamers([original, streamer('2', tags=[], is_partner=False)]) == 2

    loaded = {s['user_id']: s for s in db.load_streamers()}
    for key, value in original.items():
        assert loaded['1'][key] == value, key
    assert loaded['2']['tags'] == [] and loaded['2']['is_partner'] is False


def test_save_streamers_replaces_latest_state(db):
    db.save_streamers([streamer(follower_count=10)])
    db.save_streamers([streamer(follower_count=20)])
    assert [s['follower_count'] for s in db.load_streamers()] == [20]


def test_unknown_follower_count_keeps_stored_value(db):
    db.save_streamers([streamer('1', follower_count=500)])
    db.save_streamers([
        streamer('1', follower_count=0, follower_count_known=False, viewer_count=99),
        streamer('2', follower_count=0, follower_count_known=False),
    ])
    loaded = {s['user_id']: s for s in db.load_streamers()}
    assert loaded['1']['follower_count'] == 500 and loaded['1']['viewer_count'] == 99
    assert loaded['2']['follower_count'] == 0  # never stored before: nothing to keep


def test_load_streamers_filters(db):
    db.save_streamers([streamer('1', language='en'), streamer('2', language='fr', follower_count=5)])
    assert [s['user_id'] for s in db.load_streamers({'language': 'fr'})] == ['2']
    assert [s['user_id'] for s in db.load_streamers({'min_followers': 100})] == ['1']


@pytest.mark.parametrize('save, load, rows', [
    ('save_stream_snapshots', 'load_stream_snapshots', [
        {'user_id': '1', 'ts': '2026-09-27T10:00:00', 'viewer_count': 5, 'game_id': 'g', 'game_name': 'G', 'title': 't'},
        {'user_id': '1', 'ts': '2026-09-27T10:05:00', 'viewer_count': 7, 'game_id': 'g', 'game_name': 'G', 'title': 't'},
    ]),
    ('save_follower_snapshots', 'load_follower_snapshots', [
        {'user_id': '1', 'ts': '2026-09-27T10:00:00', 'followers': 100},
    ]),
    ('save_top_games', 'load_top_games', [
        {'ts': '2026-09-27T10:00:00', 'game_id': 'g1', 'name': 'Game', 'rank': 1, 'viewer_sum': 9000},
    ]),
    ('save_raids', 'load_raids', [
        {'from_id': '1', 'to_id': '2', 'ts': '2026-09-27T10:00:00', 'viewers': 300},
    ]),
    ('save_team_members', 'load_team_members', [
        {'team_id': 't1', 'team_name': 'Team', 'user_id': '1'},
    ]),
    ('save_videos', 'load_videos', [
        {'video_id': 'v1', 'user_id': '1', 'created_at': '2026-09-26T10:00:00', 'duration_s': 3600,
         'view_count': 50, 'title': 'vod'},
    ]),
    ('save_clips', 'load_clips', [
        {'clip_id': 'c1', 'broadcaster_id': '1', 'created_at': '2026-09-26T10:00:00', 'view_count': 5,
         'game_id': 'g1', 'title': 'clip'},
    ]),
])
def test_table_round_trips(db, save, load, rows):
    assert getattr(db, save)(rows) == len(rows)
    assert getattr(db, load)() == rows
    # Saving the same rows again doesn't duplicate them
    getattr(db, save)(rows)
    assert getattr(db, load)() == rows


def test_snapshot_filters(db):
    db.save_stream_snapshots([
        {'user_id': u, 'ts': ts, 'viewer_count': 1, 'game_id': 'g', 'game_name': 'G', 'title': 't'}
        for u in ('1', '2') for ts in ('2026-09-26T00:00:00', '2026-09-27T00:00:00')
    ])
    assert len(db.load_stream_snapshots(user_id='1')) == 2
    assert len(db.load_stream_snapshots(since='2026-09-27T00:00:00')) == 2
    assert len(db.load_stream_snapshots(user_id='2', since='2026-09-27T00:00:00')) == 1


def test_chat_presence_merges_sightings(db):
    db.save_chat_presence([{'channel_id': '1', 'chatter_hash': 'h', 'first_seen': '2026-09-27T10:00:00',
                            'last_seen': '2026-09-27T10:01:00', 'msg_count': 3}])
    db.save_chat_presence([{'channel_id': '1', 'chatter_hash': 'h', 'first_seen': '2026-09-27T11:00:00',
                            'last_seen': '2026-09-27T11:30:00', 'msg_count': 2}])
    assert db.load_chat_presence('1') == [{'channel_id': '1', 'chatter_hash': 'h',
                                           'first_seen': '2026-09-27T10:00:00',
                                           'last_seen': '2026-09-27T11:30:00', 'msg_count': 5}]


def test_collab_pairs_are_normalized(db):
    db.save_collabs([{'a_id': '9', 'b_id': '3', 'ts': '2026-09-27T10:00:00', 'source': 'shared_chat'}])
    db.save_collabs([{'a_id': '3', 'b_id': '9', 'ts': '2026-09-27T10:00:00', 'source': 'shared_chat'}])
    assert db.load_collabs() == [{'a_id': '3', 'b_id': '9', 'ts': '2026-09-27T10:00:00', 'source': 'shared_chat'}]


def test_tracked_channels_keep_first_added_at(db):
    db.add_tracked_channels([{'user_id': '1', 'login': 'a', 'added_at': '2026-01-01T00:00:00'}])
    db.add_tracked_channels([{'user_id': '1', 'login': 'a'}, {'user_id': '2', 'login': 'b'}])
    tracked = db.load_tracked_channels()
    assert [t['user_id'] for t in tracked] == ['1', '2']
    assert tracked[0]['added_at'] == '2026-01-01T00:00:00'

    db.remove_tracked_channels(['1'])
    assert [t['user_id'] for t in db.load_tracked_channels()] == ['2']
