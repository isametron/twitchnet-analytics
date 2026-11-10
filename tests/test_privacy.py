"""Opt-outs: deleting stored data and keeping accounts out of new collection."""
import asyncio
import json
from types import SimpleNamespace

import networkx as nx
import pytest

import tracker
from twitchnet import privacy
from twitchnet.database import DatabaseManager
from twitchnet.privacy import OptOutList, forget_user, hash_chatter
from twitchnet.relations import ChatPresenceLogger, fetch_shared_chat, fetch_teams

SALT = 's'
GONE = '111'
KEPT = '222'


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, 'load_chat_salt', lambda: SALT)
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def forget(db, tmp_path, user_id=GONE):
    return forget_user(db, user_id, SALT, str(tmp_path / 'no_such_file.json'))


def populate(db):
    for uid in (GONE, KEPT):
        db.save_streamers([{'user_id': uid, 'username': f'u{uid}', 'follower_count': 1}])
        db.add_tracked_channels([{'user_id': uid, 'login': f'u{uid}'}])
        db.save_stream_snapshots([{'user_id': uid, 'ts': 't', 'viewer_count': 1, 'game_id': 'g', 'game_name': 'G',
                                   'title': 'x'}])
        db.save_follower_snapshots([{'user_id': uid, 'ts': 't', 'followers': 1}])
        db.save_chat_activity([{'channel_id': uid, 'minute': 'm', 'messages': 1}])
        db.save_team_members([{'team_id': 't', 'team_name': 'T', 'user_id': uid}])
        db.save_videos([{'video_id': f'v{uid}', 'user_id': uid, 'created_at': 'c', 'duration_s': 1, 'view_count': 1,
                         'title': 'x'}])
        db.save_clips([{'clip_id': f'c{uid}', 'broadcaster_id': uid, 'created_at': 'c', 'view_count': 1, 'game_id': 'g',
                        'title': 'x', 'url': 'u', 'thumbnail_url': 't'}])
        db.save_schedules([{'user_id': uid, 'fetched_at': 't', 'has_schedule': 1, 'scheduled_hours_7d': 1.0,
                            'segments_7d': 1}])
    # GONE chatted in KEPT's channel; someone else chatted in GONE's channel; a stranger chatted in KEPT's
    db.save_chat_presence([
        {'channel_id': KEPT, 'chatter_hash': hash_chatter(GONE, SALT), 'first_seen': 'a', 'last_seen': 'b', 'msg_count': 1},
        {'channel_id': GONE, 'chatter_hash': 'other', 'first_seen': 'a', 'last_seen': 'b', 'msg_count': 1},
        {'channel_id': KEPT, 'chatter_hash': 'other', 'first_seen': 'a', 'last_seen': 'b', 'msg_count': 1},
    ])
    db.save_raids([{'from_id': GONE, 'to_id': KEPT, 'ts': 'a', 'viewers': 1},
                   {'from_id': KEPT, 'to_id': GONE, 'ts': 'b', 'viewers': 1},
                   {'from_id': KEPT, 'to_id': '333', 'ts': 'c', 'viewers': 1}])
    db.save_collabs([{'a_id': GONE, 'b_id': KEPT, 'ts': 'a', 'source': 'shared_chat'},
                     {'a_id': KEPT, 'b_id': '333', 'ts': 'a', 'source': 'shared_chat'}])


def test_forget_user_deletes_everything_about_the_account(db, tmp_path):
    populate(db)
    deleted = forget(db, tmp_path)
    assert deleted['chat_presence'] == 2 and deleted['raids'] == 2

    assert [s['user_id'] for s in db.load_streamers()] == [KEPT]
    for load in (db.load_stream_snapshots, db.load_follower_snapshots, db.load_team_members, db.load_videos,
                 db.load_schedules, db.load_tracked_channels):
        assert [r['user_id'] for r in load()] == [KEPT]
    assert [r['broadcaster_id'] for r in db.load_clips()] == [KEPT]
    assert [r['channel_id'] for r in db.load_chat_activity()] == [KEPT]
    assert [(r['channel_id'], r['chatter_hash']) for r in db.load_chat_presence()] == [(KEPT, 'other')]
    assert [(r['from_id'], r['to_id']) for r in db.load_raids()] == [(KEPT, '333')]
    assert [(r['a_id'], r['b_id']) for r in db.load_collabs()] == [(KEPT, '333')]


def test_forget_user_stores_only_a_hash(db, tmp_path):
    forget(db, tmp_path)
    assert db.load_opt_outs() == {hash_chatter(GONE, SALT)}
    stored = db.conn.execute('SELECT * FROM opt_outs').fetchall()
    assert not any(GONE == value for row in stored for value in row)


def test_forget_user_cleans_saved_graphs_and_scores(db, tmp_path):
    graph = nx.path_graph([GONE, KEPT, '333'])
    graph_id = db.save_graph(graph, 'g')
    db.save_centrality_scores({'pagerank': {GONE: 0.5, KEPT: 0.5}}, graph_id)
    db.save_communities({0: [GONE, KEPT]}, graph_id)
    forget(db, tmp_path)

    loaded, _ = db.load_graph(graph_id=graph_id)
    assert set(loaded.nodes) == {KEPT, '333'}
    assert db.list_graphs()[0]['node_count'] == 2 and db.list_graphs()[0]['edge_count'] == 1
    assert list(db.load_centrality_scores(graph_id)['pagerank']) == [KEPT]
    assert db.load_communities(graph_id) == {0: [KEPT]}


def test_forget_user_removes_account_from_raw_json(db, tmp_path):
    path = tmp_path / 'streamers.json'
    path.write_text(json.dumps([{'user_id': GONE}, {'user_id': KEPT}]), encoding='utf-8')
    assert forget_user(db, GONE, SALT, str(path))['streamers.json'] == 1
    assert json.loads(path.read_text(encoding='utf-8')) == [{'user_id': KEPT}]


def test_opt_out_list(db, tmp_path):
    opt_outs = OptOutList(db, SALT)
    assert not opt_outs.contains(GONE)
    forget(db, tmp_path)
    assert not opt_outs.contains(GONE)  # not picked up until refresh
    opt_outs.refresh()
    assert opt_outs.contains(GONE) and not opt_outs.contains(KEPT)
    assert opt_outs.filter([{'user_id': GONE}, {'user_id': KEPT}]) == [{'user_id': KEPT}]


def test_chat_logger_drops_opted_out_accounts_even_if_already_buffered(db, tmp_path):
    logger = ChatPresenceLogger(db, ['a'], salt=SALT)
    logger.record(KEPT, GONE, ts='2026-11-09T10:00:00+00:00')    # opted-out chatter
    logger.record(GONE, '999', ts='2026-11-09T10:00:00+00:00')   # opted-out channel
    logger.record(KEPT, '999', ts='2026-11-09T10:00:00+00:00')   # unaffected
    logger.record_raid({'user-id': GONE, 'room-id': KEPT})
    logger.record_raid({'user-id': KEPT, 'room-id': GONE})
    logger.record_raid({'user-id': '333', 'room-id': KEPT})
    forget(db, tmp_path)  # arrives between the messages and the flush
    logger.flush()

    assert [(r['channel_id'], r['chatter_hash']) for r in db.load_chat_presence()] == [(KEPT, hash_chatter('999', SALT))]
    assert [r['from_id'] for r in db.load_raids()] == ['333']
    assert {r['channel_id'] for r in db.load_chat_activity()} == {KEPT}


class FakeTwitch:
    async def get_channel_teams(self, broadcaster_id):
        return [SimpleNamespace(id='t1')]

    async def get_teams(self, team_id=None):
        return SimpleNamespace(id=team_id, team_name='t', team_display_name='T',
                               users=[SimpleNamespace(user_id=GONE), SimpleNamespace(user_id=KEPT)])

    async def get_shared_chat_session(self, broadcaster_id):
        return SimpleNamespace(participants=[SimpleNamespace(broadcaster_id=b) for b in (GONE, KEPT, '333')],
                               created_at=None)


def test_new_team_and_co_stream_data_excludes_opted_out(db, tmp_path):
    forget(db, tmp_path)
    asyncio.run(fetch_teams(FakeTwitch(), db, [KEPT]))
    asyncio.run(fetch_shared_chat(FakeTwitch(), db, [KEPT]))
    assert [r['user_id'] for r in db.load_team_members()] == [KEPT]
    assert [(c['a_id'], c['b_id']) for c in db.load_collabs()] == [(KEPT, '333')]


def test_seed_skips_opted_out_channels(db, tmp_path):
    forget(db, tmp_path)
    tracker.seed(db, 10, [{'user_id': GONE, 'username': 'x', 'follower_count': 9},
                          {'user_id': KEPT, 'username': 'y', 'follower_count': 1}])
    assert [t['user_id'] for t in db.load_tracked_channels()] == [KEPT]
