"""Tests for chat parsing/logging, raids, teams, shared chat and title mentions (no network)."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from twitchnet import relations
from twitchnet.database import DatabaseManager
from twitchnet.relations import (
    ChatPresenceLogger,
    RaidListener,
    extract_title_mentions,
    fetch_shared_chat,
    fetch_teams,
    hash_chatter,
    load_chat_salt,
    parse_irc_line,
)

PRIVMSG = ('@badge-info=;color=#FF0000;display-name=Viewer;room-id=111;tmi-sent-ts=1;user-id=999 '
           ':viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #somechannel :hello @there :)')


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def test_parse_tagged_privmsg():
    tags, command, params = parse_irc_line(PRIVMSG)
    assert command == 'PRIVMSG'
    assert tags['room-id'] == '111' and tags['user-id'] == '999'
    assert params == ['#somechannel', 'hello @there :)']


@pytest.mark.parametrize('line, expected', [
    ('PING :tmi.twitch.tv', ({}, 'PING', ['tmi.twitch.tv'])),
    (':tmi.twitch.tv RECONNECT', ({}, 'RECONNECT', [])),
    (':tmi.twitch.tv CAP * ACK :twitch.tv/tags', ({}, 'CAP', ['*', 'ACK', 'twitch.tv/tags'])),
])
def test_parse_other_lines(line, expected):
    assert parse_irc_line(line) == expected


def test_hash_is_stable_and_salted():
    assert hash_chatter('999', 'a') == hash_chatter('999', 'a')
    assert hash_chatter('999', 'a') != hash_chatter('999', 'b')
    assert '999' not in hash_chatter('999', 'a')


def test_salt_is_created_once(tmp_path):
    path = str(tmp_path / 'salt.json')
    salt = load_chat_salt(path)
    assert len(salt) == 32 and load_chat_salt(path) == salt


def test_logger_replies_and_records(db):
    logger = ChatPresenceLogger(db, ['SomeChannel'], salt='s')
    assert logger.channel_logins == ['somechannel']
    assert logger.handle_line('PING :tmi.twitch.tv') == 'PONG :tmi.twitch.tv'
    assert logger.handle_line(':tmi.twitch.tv RECONNECT') == 'RECONNECT'
    assert logger.handle_line(PRIVMSG) is None
    assert logger.messages_seen == 1


def test_logger_aggregates_and_flushes_hashes_only(db):
    logger = ChatPresenceLogger(db, ['a'], salt='s')
    logger.record('111', '999', ts='2026-09-30T10:00:00+00:00')
    logger.record('111', '999', ts='2026-09-30T10:05:00+00:00')
    logger.record('222', '999', ts='2026-09-30T10:06:00+00:00')
    assert logger.flush() == 2
    assert logger.flush() == 0  # buffer cleared

    rows = {r['channel_id']: r for r in db.load_chat_presence()}
    assert rows['111']['msg_count'] == 2
    assert rows['111']['first_seen'] == '2026-09-30T10:00:00+00:00'
    assert rows['111']['last_seen'] == '2026-09-30T10:05:00+00:00'
    assert rows['111']['chatter_hash'] == rows['222']['chatter_hash'] == hash_chatter('999', 's')


def test_logger_caps_channels(db, capsys):
    logger = ChatPresenceLogger(db, [f'c{i}' for i in range(relations.IRC_MAX_CHANNELS + 5)], salt='s')
    assert len(logger.channel_logins) == relations.IRC_MAX_CHANNELS
    assert 'limited' in capsys.readouterr().out


def test_raid_handler_writes_raid(db):
    listener = RaidListener(db, user_twitch=None, channel_ids=['1'])
    event = SimpleNamespace(
        metadata=SimpleNamespace(message_timestamp=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)),
        event=SimpleNamespace(from_broadcaster_user_id='1', from_broadcaster_user_login='a',
                              to_broadcaster_user_id='2', to_broadcaster_user_login='b', viewers=250),
    )
    asyncio.run(listener.on_raid(event))
    asyncio.run(listener.on_raid(event))  # EventSub may redeliver: same timestamp, stored once
    assert db.load_raids() == [{'from_id': '1', 'to_id': '2', 'ts': '2026-09-30T12:00:00+00:00', 'viewers': 250}]
    assert listener.raids_seen == 2


class FakeTwitch:
    async def get_channel_teams(self, broadcaster_id):
        if broadcaster_id == '3':
            raise relations.TwitchResourceNotFound('no teams')
        return [SimpleNamespace(id='t1')] if broadcaster_id in ('1', '2') else []

    async def get_teams(self, team_id=None):
        return SimpleNamespace(id=team_id, team_name='team', team_display_name='Team One', users=[
            SimpleNamespace(user_id='1'), SimpleNamespace(user_id='2'), SimpleNamespace(user_id='50')])

    async def get_shared_chat_session(self, broadcaster_id):
        if broadcaster_id in ('1', '2'):
            return SimpleNamespace(
                participants=[SimpleNamespace(broadcaster_id=b) for b in ('1', '2', '7')],
                created_at=datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc))
        return None


def test_fetch_teams_stores_all_members(db):
    assert asyncio.run(fetch_teams(FakeTwitch(), db, ['1', '2', '3', '4'])) == 3
    assert sorted(r['user_id'] for r in db.load_team_members('t1')) == ['1', '2', '50']
    assert db.load_team_members()[0]['team_name'] == 'Team One'


def test_fetch_shared_chat_stores_each_pair_once(db):
    # Both hosts report the same session; its pairs are stored once
    asyncio.run(fetch_shared_chat(FakeTwitch(), db, ['1', '2', '3']))
    pairs = sorted((c['a_id'], c['b_id']) for c in db.load_collabs('shared_chat'))
    assert pairs == [('1', '2'), ('1', '7'), ('2', '7')]


def test_title_mentions():
    known = {'alice': '1', 'bob': '2'}
    streams = [
        {'user_id': '1', 'title': 'Duo w/ @Bob and @stranger, ping @alice', 'started_at': '2026-09-30T08:00:00'},
        {'user_id': '2', 'title': 'no mentions here', 'started_at': '2026-09-30T08:00:00'},
    ]
    assert extract_title_mentions(streams, known) == [
        {'a_id': '1', 'b_id': '2', 'ts': '2026-09-30T08:00:00', 'source': 'title_mention'}
    ]
