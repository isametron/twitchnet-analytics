"""TwitchDataCollector tests against an in-memory fake of the twitchAPI client."""
import asyncio
from collections import defaultdict
from types import SimpleNamespace

import pytest

from twitchnet import twitch_api
from twitchnet.twitch_api import TwitchDataCollector

LANGUAGES = twitch_api.DIVERSE_LANGUAGES


class FakeTwitch:
    """Mimics the twitchAPI 4.x methods the collector uses and records every call."""

    def __init__(self, n_streams=10, channel_tags=('ChannelTag',), missing_game=False, failing_followers=()):
        self.calls = defaultdict(list)
        self.failing_followers = set(failing_followers)
        self.channel_tags = list(channel_tags)
        self.missing_game = missing_game
        self.streams = [
            SimpleNamespace(
                user_id=str(i), user_login=f'user{i}', game_id='g1', game_name='Stream Game',
                language=LANGUAGES[i % len(LANGUAGES)], viewer_count=10_000 - i, title=f'title {i}',
                thumbnail_url=f'thumb{i}', started_at='2026-09-27 10:00:00+00:00',
                tags=['StreamTag'],
            )
            for i in range(n_streams)
        ]

    async def get_games(self, names=None):
        self.calls['get_games'].append(names)
        if not self.missing_game:
            yield SimpleNamespace(id='g1', name=names[0])

    async def get_streams(self, first=20, game_id=None, language=None, **kwargs):
        self.calls['get_streams'].append({'first': first, 'game_id': game_id, 'language': language})
        for stream in self.streams:
            if language is None or stream.language in language:
                yield stream

    async def get_users(self, user_ids=None, logins=None):
        self.calls['get_users'].append(list(user_ids or logins))
        for key in user_ids or logins:
            uid = key.removeprefix('user')
            yield SimpleNamespace(
                id=uid, login=f'user{uid}', display_name=f'User {uid}', description='desc',
                broadcaster_type='partner' if int(uid) % 3 == 0 else 'affiliate',
                profile_image_url='img', created_at='2015-01-01 00:00:00+00:00',
            )

    async def get_channel_information(self, broadcaster_id):
        self.calls['get_channel_information'].append(list(broadcaster_id))
        return [
            SimpleNamespace(
                broadcaster_id=uid, game_name='Channel Game', game_id='g2', broadcaster_language='en',
                tags=list(self.channel_tags), content_classification_labels=['Gambling'],
                is_branded_content=True,
            )
            for uid in broadcaster_id
        ]

    async def get_channel_followers(self, broadcaster_id, first=None):
        self.calls['get_channel_followers'].append(broadcaster_id)
        if broadcaster_id in self.failing_followers:
            raise ConnectionError('Cannot connect to host api.twitch.tv')
        return SimpleNamespace(total=int(broadcaster_id) * 10)


def make_collector(fake):
    collector = TwitchDataCollector('id', 'secret')
    collector.twitch = fake
    return collector


def test_top_streamers_batches_users_and_channels_in_chunks_of_100():
    fake = FakeTwitch(n_streams=250)
    records = asyncio.run(make_collector(fake).get_top_streamers('Some Game', max_results=250))

    assert len(records) == 250
    assert [len(c) for c in fake.calls['get_users']] == [100, 100, 50]
    assert [len(c) for c in fake.calls['get_channel_information']] == [100, 100, 50]
    assert len(fake.calls['get_channel_followers']) == 250
    assert fake.calls['get_streams'] == [{'first': 100, 'game_id': ['g1'], 'language': None}]
    # Helix returns streams by viewer count; that order is kept
    assert [r['user_id'] for r in records] == [str(i) for i in range(250)]


def test_top_streamers_respects_max_results():
    fake = FakeTwitch(n_streams=50)
    records = asyncio.run(make_collector(fake).get_top_streamers(max_results=7))

    assert len(records) == 7
    assert fake.calls['get_streams'][0]['first'] == 7
    assert fake.calls['get_games'] == []


def test_record_shape_and_field_sources():
    fake = FakeTwitch(n_streams=1)
    record = asyncio.run(make_collector(fake).get_top_streamers(max_results=1))[0]

    assert set(record) == {
        'user_id', 'username', 'display_name', 'description', 'follower_count', 'follower_count_known',
        'game_name', 'game_id', 'language', 'tags', 'is_partner', 'broadcaster_type', 'is_live',
        'viewer_count', 'stream_title', 'thumbnail_url', 'started_at', 'content_classification_labels',
        'is_branded_content', 'profile_image_url', 'created_at',
    }
    assert record['follower_count'] == 0  # user 0 -> fake total 0
    assert record['follower_count_known'] is True
    # Game and tags come from the channel, language from the live stream
    assert record['game_name'] == 'Channel Game'
    assert record['game_id'] == 'g2'
    assert record['tags'] == ['ChannelTag']
    assert record['language'] == 'en'
    assert record['is_live'] is True
    assert record['viewer_count'] == 10_000
    assert record['content_classification_labels'] == ['Gambling']
    assert record['is_branded_content'] is True
    assert record['is_partner'] is True and record['broadcaster_type'] == 'partner'


def test_failed_follower_lookup_is_marked_unknown(monkeypatch):
    async def no_sleep(_):
        pass
    monkeypatch.setattr(twitch_api.asyncio, 'sleep', no_sleep)

    fake = FakeTwitch(n_streams=3, failing_followers={'1'})
    records = {r['user_id']: r for r in asyncio.run(make_collector(fake).get_top_streamers(max_results=3))}

    assert records['1']['follower_count'] == 0 and records['1']['follower_count_known'] is False
    assert records['2']['follower_count'] == 20 and records['2']['follower_count_known'] is True
    assert fake.calls['get_channel_followers'].count('1') == 3  # retried before giving up


def test_stream_tags_used_when_channel_has_none():
    fake = FakeTwitch(n_streams=1, channel_tags=())
    record = asyncio.run(make_collector(fake).get_top_streamers(max_results=1))[0]
    assert record['tags'] == ['StreamTag']


def test_diverse_streamers_one_game_lookup_one_query_per_language():
    fake = FakeTwitch(n_streams=40)
    records = asyncio.run(make_collector(fake).get_diverse_streamers('Some Game', max_per_language=2))

    assert fake.calls['get_games'] == [['Some Game']]
    assert sorted(c['language'][0] for c in fake.calls['get_streams']) == sorted(LANGUAGES)
    assert len(records) == 2 * len(LANGUAGES)
    assert len({r['user_id'] for r in records}) == len(records)
    # All languages are enriched in a single batched pass
    assert len(fake.calls['get_users']) == 1


def test_unknown_game_returns_empty_list():
    fake = FakeTwitch(missing_game=True)
    collector = make_collector(fake)

    assert asyncio.run(collector.get_top_streamers('Nope')) == []
    assert asyncio.run(collector.get_diverse_streamers('Nope')) == []
    assert fake.calls['get_streams'] == []


def test_streamer_details_by_login():
    fake = FakeTwitch()
    record = asyncio.run(make_collector(fake).get_streamer_details('user4'))

    assert fake.calls['get_users'] == [['user4']]
    assert record['user_id'] == '4'
    assert record['follower_count'] == 40
    assert record['is_live'] is False


def test_retry_gives_up_and_returns_none(monkeypatch):
    async def no_sleep(_):
        pass
    monkeypatch.setattr(twitch_api.asyncio, 'sleep', no_sleep)

    attempts = []

    async def always_fails():
        attempts.append(1)
        raise RuntimeError('boom')

    collector = TwitchDataCollector('id', 'secret')
    assert asyncio.run(collector._retry_with_backoff(always_fails)) is None
    assert len(attempts) == 3


@pytest.mark.parametrize('failures', [1, 2])
def test_retry_recovers_after_transient_failures(monkeypatch, failures):
    async def no_sleep(_):
        pass
    monkeypatch.setattr(twitch_api.asyncio, 'sleep', no_sleep)

    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) <= failures:
            raise RuntimeError('429 rate limit')
        return 'ok'

    collector = TwitchDataCollector('id', 'secret')
    assert asyncio.run(collector._retry_with_backoff(flaky)) == 'ok'
