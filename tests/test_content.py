"""Content fetchers (VODs, clips, schedules, top games) against a fake Twitch client."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from twitchnet import content
from twitchnet.content import (
    fetch_clips,
    fetch_schedules,
    fetch_top_games,
    fetch_videos,
    parse_duration,
    summarize_schedule,
)
from twitchnet.database import DatabaseManager

NOW = datetime.now(timezone.utc)


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


class FakeTwitch:
    def __init__(self):
        self.calls = []

    async def get_videos(self, user_id=None, video_type=None, first=20):
        self.calls.append(('videos', user_id, video_type))
        for i in range(30):  # more than requested: the fetcher must stop at `first`
            yield SimpleNamespace(id=f'{user_id}-v{i}', user_id=user_id, created_at=NOW, duration='1h30m',
                                  view_count=i, title=f'vod {i}')

    async def get_clips(self, broadcaster_id=None, started_at=None, first=20):
        self.calls.append(('clips', broadcaster_id, started_at))
        if broadcaster_id == 'bad':
            raise RuntimeError('boom')
        for i in range(3):
            yield SimpleNamespace(id=f'{broadcaster_id}-c{i}', broadcaster_id=broadcaster_id, created_at=NOW,
                                  view_count=10 * i, game_id='g', title='clip', url='https://clip',
                                  thumbnail_url='thumb')

    async def get_channel_stream_schedule(self, broadcaster_id, first=None):
        if broadcaster_id == 'none':
            raise content.TwitchResourceNotFound('no schedule')
        segment = lambda days, hours, canceled=None: SimpleNamespace(  # noqa: E731
            start_time=NOW + timedelta(days=days), end_time=NOW + timedelta(days=days, hours=hours),
            canceled_until=canceled)
        return SimpleNamespace(segments=[segment(1, 3), segment(2, 4), segment(3, 2, canceled='x'), segment(9, 5)])

    async def get_top_games(self, first=20):
        for i in range(5):
            yield SimpleNamespace(id=f'g{i}', name=f'Game {i}')

    async def get_streams(self, game_id=None, first=100):
        for viewers in (100, 50):
            yield SimpleNamespace(viewer_count=viewers)


@pytest.mark.parametrize('text, seconds', [
    ('3h2m1s', 10921), ('45m', 2700), ('59s', 59), ('2h', 7200), ('', 0), ('garbage', 0),
])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_fetch_videos_limits_per_channel_and_parses_duration(db):
    twitch = FakeTwitch()
    assert asyncio.run(fetch_videos(twitch, db, ['1', '2'], per_channel=5)) == 10
    videos = db.load_videos('1')
    assert len(videos) == 5 and videos[0]['duration_s'] == 5400
    assert all(call[2] == content.VideoType.ARCHIVE for call in twitch.calls)


def test_fetch_clips_skips_failed_channels(db, capsys):
    twitch = FakeTwitch()
    assert asyncio.run(fetch_clips(twitch, db, ['1', 'bad'])) == 3
    assert [c['url'] for c in db.load_clips('1')] == ['https://clip'] * 3
    assert 'Clip lookup failed for bad' in capsys.readouterr().out
    started_at = twitch.calls[0][2]
    assert timedelta(days=29) < NOW - started_at < timedelta(days=31)


def test_summarize_schedule_counts_next_7_days_only():
    segments = asyncio.run(FakeTwitch().get_channel_stream_schedule('1')).segments
    summary = summarize_schedule(segments, NOW, 'ts', '1')
    assert summary == {'user_id': '1', 'fetched_at': 'ts', 'has_schedule': True,
                       'scheduled_hours_7d': 7.0, 'segments_7d': 2}


def test_fetch_schedules_marks_channels_without_schedule(db):
    asyncio.run(fetch_schedules(FakeTwitch(), db, ['1', 'none']))
    rows = {r['user_id']: r for r in db.load_schedules()}
    assert rows['1']['scheduled_hours_7d'] == 7.0
    assert not rows['none']['has_schedule'] and rows['none']['segments_7d'] == 0


def test_fetch_top_games_ranks_and_viewer_sums(db):
    assert asyncio.run(fetch_top_games(FakeTwitch(), db, first=5, with_viewers=2)) == 5
    rows = db.load_top_games()
    assert [r['rank'] for r in rows] == [1, 2, 3, 4, 5]
    assert [r['viewer_sum'] for r in rows] == [150, 150, None, None, None]
    assert len({r['ts'] for r in rows}) == 1
