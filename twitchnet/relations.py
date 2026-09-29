"""
Real relationship signals between streamers:

- ChatPresenceLogger: anonymous Twitch chat (IRC) reader recording which chatters appear in
  which channels. Chatters are stored only as salted hashes, never message text.
- RaidListener: EventSub WebSocket subscription to raids sent by tracked channels.
- fetch_teams / fetch_shared_chat / extract_title_mentions: team membership, Shared Chat
  co-streams and @mentions in stream titles.

Everything is written to DatabaseManager tables; graph_builder turns it into edges.
"""
import asyncio
import hashlib
import json
import os
import random
import re
import secrets
import time
from datetime import datetime, timezone
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import aiohttp
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.type import TwitchResourceNotFound

from twitchnet.config import Config

IRC_URL = 'wss://irc-ws.chat.twitch.tv:443'
IRC_JOINS_PER_WINDOW = 20  # anonymous connections may JOIN 20 channels per 10 seconds
IRC_JOIN_WINDOW_S = 10
IRC_MAX_CHANNELS = 100  # per connection, to stay well inside Twitch's limits
CHAT_FLUSH_INTERVAL_S = 30
EVENTSUB_MAX_SUBSCRIPTIONS = 300  # per WebSocket connection
API_CONCURRENCY = 8
SALT_PATH = os.path.join(Config.PROCESSED_DATA_DIR, 'chat_salt.json')

MENTION_RE = re.compile(r'@([A-Za-z0-9_]{3,25})')


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


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


def parse_irc_line(line: str) -> Tuple[Dict[str, str], str, List[str]]:
    """
    Split one IRC line into (tags, command, params).
    '@room-id=1;user-id=2 :nick!nick@nick.tmi.twitch.tv PRIVMSG #chan :hi'
    -> ({'room-id': '1', 'user-id': '2'}, 'PRIVMSG', ['#chan', 'hi'])
    """
    tags = {}
    if line.startswith('@'):
        raw_tags, _, line = line[1:].partition(' ')
        for item in raw_tags.split(';'):
            key, _, value = item.partition('=')
            tags[key] = value
    if line.startswith(':'):
        _, _, line = line.partition(' ')  # drop the prefix
    head, sep, trailing = line.partition(' :')
    parts = head.split()
    command = parts[0] if parts else ''
    params = parts[1:] + ([trailing] if sep else [])
    return tags, command, params


class ChatPresenceLogger:
    """Log which (hashed) chatters talk in which tracked channels, via anonymous IRC"""

    def __init__(self, db, channel_logins: List[str], salt: str = None,
                 flush_interval: float = CHAT_FLUSH_INTERVAL_S):
        if len(channel_logins) > IRC_MAX_CHANNELS:
            print(f"⚠️ Chat logger limited to {IRC_MAX_CHANNELS} of {len(channel_logins)} channels")
        self.db = db
        self.channel_logins = [login.lower() for login in channel_logins[:IRC_MAX_CHANNELS]]
        self.salt = salt or load_chat_salt()
        self.flush_interval = flush_interval
        self._buffer: Dict[Tuple[str, str], List] = {}  # (channel_id, chatter_hash) -> [first, last, count]
        self.messages_seen = 0
        self.connected = False

    def record(self, channel_id: str, chatter_id: str, ts: str = None):
        ts = ts or utc_now()
        key = (channel_id, hash_chatter(chatter_id, self.salt))
        entry = self._buffer.get(key)
        if entry:
            entry[1] = ts
            entry[2] += 1
        else:
            self._buffer[key] = [ts, ts, 1]
        self.messages_seen += 1

    def handle_line(self, line: str) -> Optional[str]:
        """Process one IRC line; returns a reply to send (PONG), 'RECONNECT', or None"""
        tags, command, params = parse_irc_line(line)
        if command == 'PING':
            return 'PONG :' + (params[0] if params else 'tmi.twitch.tv')
        if command == 'RECONNECT':
            return 'RECONNECT'
        if command == 'PRIVMSG' and tags.get('room-id') and tags.get('user-id'):
            self.record(tags['room-id'], tags['user-id'])
        return None

    def flush(self) -> int:
        rows = [
            {'channel_id': channel_id, 'chatter_hash': chatter_hash,
             'first_seen': first, 'last_seen': last, 'msg_count': count}
            for (channel_id, chatter_hash), (first, last, count) in self._buffer.items()
        ]
        self._buffer = {}
        return self.db.save_chat_presence(rows)

    async def _join_channels(self, ws):
        for i in range(0, len(self.channel_logins), IRC_JOINS_PER_WINDOW):
            batch = self.channel_logins[i:i + IRC_JOINS_PER_WINDOW]
            await ws.send_str('JOIN ' + ','.join(f'#{login}' for login in batch))
            if i + IRC_JOINS_PER_WINDOW < len(self.channel_logins):
                await asyncio.sleep(IRC_JOIN_WINDOW_S + 1)

    async def _flush_periodically(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            self.flush()

    async def _session(self, session: aiohttp.ClientSession):
        async with session.ws_connect(IRC_URL, heartbeat=60) as ws:
            # twitch.tv/tags adds room-id and user-id, so chatters are keyed by stable ids
            await ws.send_str('CAP REQ :twitch.tv/tags')
            await ws.send_str('PASS SCHMOOPIIE')
            await ws.send_str(f'NICK justinfan{random.randint(10000, 99999)}')
            self.connected = True
            print(f"💬 Chat logger connected; joining {len(self.channel_logins)} channels")
            joiner = asyncio.create_task(self._join_channels(ws))
            try:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    for line in msg.data.split('\r\n'):
                        if not line:
                            continue
                        reply = self.handle_line(line)
                        if reply == 'RECONNECT':
                            return
                        if reply:
                            await ws.send_str(reply)
            finally:
                joiner.cancel()
                self.connected = False

    async def run(self):
        """Log chat until cancelled, reconnecting with backoff and flushing to the database periodically"""
        flusher = asyncio.create_task(self._flush_periodically())
        backoff = 1
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    started = time.time()
                    try:
                        await self._session(session)
                    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                        print(f"⚠️ Chat connection error: {e}")
                    # Reset the backoff after a connection that stayed up for a while
                    backoff = 1 if time.time() - started > 60 else min(backoff * 2, 60)
                    print(f"💬 Chat logger reconnecting in {backoff}s")
                    await asyncio.sleep(backoff)
        finally:
            flusher.cancel()
            self.flush()


class RaidListener:
    """Record raids sent by tracked channels using EventSub over WebSocket (needs a user token)"""

    def __init__(self, db, user_twitch, channel_ids: List[str]):
        if len(channel_ids) > EVENTSUB_MAX_SUBSCRIPTIONS:
            print(f"⚠️ Raid listener limited to {EVENTSUB_MAX_SUBSCRIPTIONS} of {len(channel_ids)} channels")
        self.db = db
        self.user_twitch = user_twitch
        self.channel_ids = channel_ids[:EVENTSUB_MAX_SUBSCRIPTIONS]
        self.eventsub = None
        self.raids_seen = 0
        self.subscribed = 0

    async def on_raid(self, event):
        data = event.event
        timestamp = getattr(getattr(event, 'metadata', None), 'message_timestamp', None)
        ts = timestamp.isoformat(timespec='seconds') if isinstance(timestamp, datetime) else utc_now()
        self.db.save_raids([{'from_id': data.from_broadcaster_user_id, 'to_id': data.to_broadcaster_user_id,
                             'ts': ts, 'viewers': data.viewers}])
        self.raids_seen += 1
        print(f"🎯 Raid: {data.from_broadcaster_user_login} -> {data.to_broadcaster_user_login} ({data.viewers} viewers)")

    async def start(self):
        # EventSub runs its socket on its own thread; deliver callbacks on this loop so DB writes stay here
        self.eventsub = EventSubWebsocket(self.user_twitch, callback_loop=asyncio.get_running_loop())
        self.eventsub.start()
        for channel_id in self.channel_ids:
            try:
                await self.eventsub.listen_channel_raid(self.on_raid, from_broadcaster_user_id=channel_id)
                self.subscribed += 1
            except Exception as e:
                print(f"⚠️ Could not subscribe to raids from {channel_id}: {e}")
        print(f"🎯 Raid listener subscribed to {self.subscribed} channels")

    async def stop(self):
        if self.eventsub:
            await self.eventsub.stop()


async def _gather_limited(func, items, limit: int = API_CONCURRENCY):
    semaphore = asyncio.Semaphore(limit)

    async def run_one(item):
        async with semaphore:
            return await func(item)

    return await asyncio.gather(*(run_one(item) for item in items))


async def fetch_teams(twitch, db, user_ids: List[str]) -> int:
    """Look up the teams of each channel and store every team's member list"""
    async def channel_teams(user_id):
        try:
            return await twitch.get_channel_teams(user_id)
        except TwitchResourceNotFound:
            return []  # channel is in no team
        except Exception as e:
            print(f"⚠️ Team lookup failed for {user_id}: {e}")
            return []

    team_ids = {team.id for teams in await _gather_limited(channel_teams, user_ids) for team in teams or []}

    async def team_members(team_id):
        try:
            team = await twitch.get_teams(team_id=team_id)
        except Exception as e:
            print(f"⚠️ Team member lookup failed for team {team_id}: {e}")
            return []
        return [{'team_id': team.id, 'team_name': team.team_display_name or team.team_name, 'user_id': u.user_id}
                for u in team.users or []]

    rows = [row for members in await _gather_limited(team_members, sorted(team_ids)) for row in members]
    db.save_team_members(rows)
    print(f"👥 Stored {len(rows)} memberships across {len(team_ids)} teams")
    return len(rows)


async def fetch_shared_chat(twitch, db, user_ids: List[str]) -> int:
    """Record channels currently co-streaming through Twitch Shared Chat"""
    async def session_for(user_id):
        try:
            return await twitch.get_shared_chat_session(user_id)
        except Exception as e:
            print(f"⚠️ Shared chat lookup failed for {user_id}: {e}")
            return None

    rows = {}
    for session in await _gather_limited(session_for, user_ids):
        if not session:
            continue
        participants = sorted({p.broadcaster_id for p in session.participants or []})
        ts = session.created_at.isoformat(timespec='seconds') if session.created_at else utc_now()
        for a_id, b_id in combinations(participants, 2):
            rows[(a_id, b_id, ts)] = {'a_id': a_id, 'b_id': b_id, 'ts': ts, 'source': 'shared_chat'}
    db.save_collabs(list(rows.values()))
    return len(rows)


def extract_title_mentions(streams: List[Dict], known_logins: Dict[str, str]) -> List[Dict]:
    """
    Collab rows for '@login' mentions of other known streamers in stream titles.

    Args:
        streams: dicts with user_id, title and started_at (one per live stream)
        known_logins: lowercase login -> user_id for the streamers of interest
    """
    rows = []
    for stream in streams:
        ts = stream.get('started_at') or utc_now()  # one row per stream session
        for login in {m.lower() for m in MENTION_RE.findall(stream.get('title') or '')}:
            other_id = known_logins.get(login)
            if other_id and other_id != stream['user_id']:
                rows.append({'a_id': stream['user_id'], 'b_id': other_id, 'ts': ts, 'source': 'title_mention'})
    return rows
