"""Tracker seeding and polling against a fake Twitch client."""
import asyncio
from types import SimpleNamespace

import pytest

import tracker
from twitchnet.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def streamer(user_id, followers):
    return {'user_id': user_id, 'username': f'user{user_id}', 'display_name': f'U{user_id}',
            'follower_count': followers}


class FakeTwitch:
    def __init__(self, live):
        self.live = live
        self.stream_calls = []

    async def get_streams(self, user_id=None, first=100):
        self.stream_calls.append(list(user_id))
        for uid in user_id:
            if uid in self.live:
                yield SimpleNamespace(user_id=uid, viewer_count=100 * int(uid), game_id='g', game_name='Game',
                                      title='with @user2' if uid == '1' else 'solo',
                                      started_at='2026-10-01 10:00:00+00:00')

    async def get_shared_chat_session(self, broadcaster_id):
        return None


class FakeCollector:
    def __init__(self, live):
        self.twitch = FakeTwitch(live)

    async def _fetch_follower_totals(self, ids):
        return {uid: (None if uid == '3' else 1000 * int(uid)) for uid in ids}


def test_seed_takes_largest_and_replace_resets(db):
    tracker.seed(db, 2, [streamer('1', 10), streamer('2', 30), streamer('3', 20)])
    assert sorted(t['user_id'] for t in db.load_tracked_channels()) == ['2', '3']

    tracker.seed(db, 1, [streamer('1', 99)])
    assert sorted(t['user_id'] for t in db.load_tracked_channels()) == ['1', '2', '3']

    tracker.seed(db, 1, [streamer('4', 5)], replace=True)
    assert [t['user_id'] for t in db.load_tracked_channels()] == ['4']


def test_poll_live_saves_snapshots_and_mentions(db):
    tracked = [{'user_id': str(i), 'login': f'user{i}'} for i in range(1, 4)]
    collector = FakeCollector(live={'1', '2'})
    stats = {'snapshots': 0}
    asyncio.run(tracker.poll_live(collector, db, tracked, stats))

    snapshots = db.load_stream_snapshots()
    assert [(s['user_id'], s['viewer_count']) for s in snapshots] == [('1', 100), ('2', 200)]
    assert snapshots[0]['ts'] == snapshots[1]['ts'] and snapshots[0]['ts'].endswith(':00+00:00')
    assert stats['snapshots'] == 2
    assert [(c['a_id'], c['b_id'], c['source']) for c in db.load_collabs()] == [('1', '2', 'title_mention')]


def test_poll_live_batches_100_ids_per_request(db):
    tracked = [{'user_id': str(i), 'login': f'user{i}'} for i in range(1, 251)]
    collector = FakeCollector(live=set())
    asyncio.run(tracker.poll_live(collector, db, tracked, {'snapshots': 0}))
    assert [len(c) for c in collector.twitch.stream_calls] == [100, 100, 50]


def test_follower_snapshot_skips_failed_lookups(db):
    asyncio.run(tracker.snapshot_followers(FakeCollector(live=set()), db, ['1', '2', '3']))
    assert sorted((r['user_id'], r['followers']) for r in db.load_follower_snapshots()) == [('1', 1000), ('2', 2000)]
