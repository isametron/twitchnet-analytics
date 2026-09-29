from twitchAPI.twitch import Twitch
import asyncio
import json
import math
import time
from typing import Dict, List, Optional
from config import Config

HELIX_BATCH_SIZE = 100  # Helix accepts up to 100 ids per users/channels/streams request
FOLLOWER_CONCURRENCY = 8  # follower totals need one request per channel
DIVERSE_LANGUAGES = ['en', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'ru', 'zh']


def _chunks(items: List, size: int = HELIX_BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class TwitchDataCollector:
    """Collect streamer data from Twitch API using batched Helix requests"""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.twitch = None
        self.request_count = 0

    async def initialize(self):
        """Initialize Twitch API connection"""
        self.twitch = await Twitch(self.client_id, self.client_secret)
        print("Twitch API initialized successfully")

    async def _retry_with_backoff(self, func, *args, max_retries=3, **kwargs):
        """
        Retry an API call with exponential backoff.

        twitchAPI already sleeps until the rate-limit window resets when Twitch reports
        the budget is exhausted, so this is only a safety net for transient failures.
        Returns None if every attempt fails.
        """
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = '429' in error_msg or 'rate limit' in error_msg
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * (10 if is_rate_limit else 1)
                    print(f"⚠️ API call failed ({e}); retry {attempt + 1}/{max_retries - 1} in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ API call failed after {max_retries} attempts: {e}")
        return None

    async def _get_game_id(self, game_name: str) -> Optional[str]:
        """Resolve a game/category name to its Twitch id"""
        async def fetch():
            async for game in self.twitch.get_games(names=[game_name]):
                return game.id
            return None

        self.request_count += 1
        return await self._retry_with_backoff(fetch)

    async def _collect_streams(self, game_id: str = None, language: str = None,
                               max_results: int = 100) -> List:
        """Fetch up to max_results live streams (sorted by viewers), paginating 100 at a time"""
        async def fetch():
            streams = []
            async for stream in self.twitch.get_streams(
                first=min(max_results, HELIX_BATCH_SIZE),
                game_id=[game_id] if game_id else None,
                language=[language] if language else None
            ):
                streams.append(stream)
                if len(streams) >= max_results:
                    break
            return streams

        streams = await self._retry_with_backoff(fetch) or []
        self.request_count += max(1, math.ceil(len(streams) / HELIX_BATCH_SIZE))
        return streams

    async def _fetch_users(self, user_ids: List[str] = None, logins: List[str] = None) -> Dict:
        """Fetch user profiles in batches of 100, keyed by user id"""
        users = {}
        for key, values in (('user_ids', user_ids or []), ('logins', logins or [])):
            for chunk in _chunks(values):
                async def fetch():
                    return [u async for u in self.twitch.get_users(**{key: chunk})]

                self.request_count += 1
                for user in await self._retry_with_backoff(fetch) or []:
                    users[user.id] = user
        return users

    async def _fetch_channels(self, user_ids: List[str]) -> Dict:
        """Fetch channel information in batches of 100, keyed by broadcaster id"""
        channels = {}
        for chunk in _chunks(user_ids):
            self.request_count += 1
            for channel in await self._retry_with_backoff(self.twitch.get_channel_information, chunk) or []:
                channels[channel.broadcaster_id] = channel
        return channels

    async def _fetch_follower_totals(self, user_ids: List[str]) -> Dict[str, Optional[int]]:
        """Fetch follower totals concurrently (Helix has no batch endpoint for this); None if the lookup failed"""
        semaphore = asyncio.Semaphore(FOLLOWER_CONCURRENCY)

        async def fetch_one(user_id):
            async with semaphore:
                result = await self._retry_with_backoff(
                    self.twitch.get_channel_followers, broadcaster_id=user_id, first=1
                )
                return user_id, (result.total if result else None)

        self.request_count += len(user_ids)
        return dict(await asyncio.gather(*(fetch_one(uid) for uid in user_ids)))

    async def _build_records(self, streams: List) -> List[Dict]:
        """Turn live streams into streamer records with user, channel and follower data"""
        # Deduplicate while keeping the viewer-count order from Helix
        streams_by_user = {}
        for stream in streams:
            streams_by_user.setdefault(stream.user_id, stream)
        user_ids = list(streams_by_user)

        users, channels, followers = await asyncio.gather(
            self._fetch_users(user_ids=user_ids),
            self._fetch_channels(user_ids),
            self._fetch_follower_totals(user_ids)
        )

        unknown = sum(1 for uid in user_ids if uid in users and followers.get(uid) is None)
        if unknown:
            print(f"⚠️ Follower count unavailable for {unknown} streamers; saving keeps their previous count")

        return [
            self._build_record(users[uid], channels.get(uid), followers.get(uid), streams_by_user[uid])
            for uid in user_ids if uid in users
        ]

    @staticmethod
    def _build_record(user, channel=None, follower_count: Optional[int] = 0, stream=None) -> Dict:
        """
        Merge user, channel and (optional) live stream data into one streamer record.
        A follower_count of None means the lookup failed: the record gets 0 with
        follower_count_known=False so DatabaseManager.save_streamers keeps the stored count.
        """
        # Language: live stream first (most accurate), then channel setting, then English
        language = (stream.language if stream else None) or \
                   (channel.broadcaster_language if channel else None) or 'en'
        # Game and tags: channel settings first, then the live stream
        game_name = (channel.game_name if channel else None) or \
                    (stream.game_name if stream else None) or 'Unknown'
        game_id = (channel.game_id if channel else None) or (stream.game_id if stream else None) or ''
        tags = (channel.tags if channel else None) or (stream.tags if stream else None) or []

        return {
            'user_id': user.id,
            'username': user.login,
            'display_name': user.display_name,
            'description': user.description or '',
            'follower_count': follower_count or 0,
            'follower_count_known': follower_count is not None,
            'game_name': game_name,
            'game_id': game_id,
            'language': language,
            'tags': list(tags),
            'is_partner': user.broadcaster_type == 'partner',
            'broadcaster_type': user.broadcaster_type or '',
            'is_live': stream is not None,
            'viewer_count': stream.viewer_count if stream else 0,
            'stream_title': stream.title if stream else '',
            'thumbnail_url': stream.thumbnail_url if stream else '',
            'started_at': str(stream.started_at) if stream and stream.started_at else '',
            'content_classification_labels': list(channel.content_classification_labels or []) if channel else [],
            'is_branded_content': bool(channel.is_branded_content) if channel else False,
            'profile_image_url': user.profile_image_url or '',
            'created_at': str(user.created_at) if user.created_at else ''
        }

    async def get_top_streamers(self, game_name: str = None, max_results: int = 100, language: str = None) -> List[Dict]:
        """
        Get top live streamers, optionally filtered by game and language

        Args:
            game_name: Optional game category to filter by
            max_results: Maximum number of streamers to fetch
            language: Optional language filter (e.g., 'en', 'es', 'fr', 'de', 'pt', 'ja', 'ko')

        Returns:
            List of streamer data dictionaries
        """
        start, start_requests = time.time(), self.request_count

        game_id = None
        if game_name:
            game_id = await self._get_game_id(game_name)
            if not game_id:
                print(f"Game '{game_name}' not found")
                return []

        streams = await self._collect_streams(game_id, language, max_results)
        streamers_data = await self._build_records(streams)

        lang_text = f" (Language: {language})" if language else " (All languages)"
        print(f"✅ Collected {len(streamers_data)} streamers{lang_text} in {time.time() - start:.1f}s "
              f"using {self.request_count - start_requests} API requests")
        return streamers_data

    async def get_diverse_streamers(self, game_name: str = None, max_per_language: int = 10) -> List[Dict]:
        """
        Get top streamers with diverse language representation

        Args:
            game_name: Optional game category to filter by
            max_per_language: Number of streamers per language

        Returns:
            List of streamer data with diverse languages
        """
        start, start_requests = time.time(), self.request_count

        game_id = None
        if game_name:
            game_id = await self._get_game_id(game_name)
            if not game_id:
                print(f"Game '{game_name}' not found")
                return []

        # One stream query per language in parallel, then a single batched enrichment pass
        per_language = await asyncio.gather(*(
            self._collect_streams(game_id, lang, max_per_language) for lang in DIVERSE_LANGUAGES
        ))
        streams = [stream for lang_streams in per_language for stream in lang_streams]
        diverse_streamers = await self._build_records(streams)

        print(f"Collected {len(diverse_streamers)} streamers across {len(DIVERSE_LANGUAGES)} languages "
              f"in {time.time() - start:.1f}s using {self.request_count - start_requests} API requests")
        return diverse_streamers

    async def get_streamer_details(self, username: str, stream_game_name: str = None, stream_data=None) -> Dict:
        """
        Get detailed information about a specific streamer

        Args:
            username: Twitch username
            stream_game_name: Game name to use if neither the channel nor stream has one
            stream_data: Optional live stream object with real-time data

        Returns:
            Dictionary containing comprehensive streamer details, or None if not found
        """
        users = await self._fetch_users(logins=[username])
        if not users:
            return None

        user = next(iter(users.values()))
        channels, followers = await asyncio.gather(
            self._fetch_channels([user.id]),
            self._fetch_follower_totals([user.id])
        )
        record = self._build_record(user, channels.get(user.id), followers.get(user.id), stream_data)
        if record['game_name'] == 'Unknown' and stream_game_name:
            record['game_name'] = stream_game_name
        return record

    def save_data(self, data: List[Dict], filename: str):
        """Save collected data to JSON file"""
        filepath = f"{Config.RAW_DATA_DIR}/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filepath}")

    async def close(self):
        """Close Twitch API connection"""
        if self.twitch:
            await self.twitch.close()

async def main():
    """Example usage"""
    collector = TwitchDataCollector(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    await collector.initialize()

    # Collect top streamers
    streamers = await collector.get_top_streamers(game_name='League of Legends', max_results=10)

    print("\nCollected Streamers:")
    for streamer in streamers:
        print(f"- {streamer['display_name']} (@{streamer['username']}) - {streamer['follower_count']:,} followers")

    collector.save_data(streamers, 'streamers.json')

    await collector.close()

if __name__ == "__main__":
    Config.make_console_safe()
    asyncio.run(main())
