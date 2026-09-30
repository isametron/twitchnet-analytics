"""
Content data for tracked channels: past broadcasts (VODs), clips, stream schedules and
top categories. Each fetcher writes to its DatabaseManager table; metrics.py reads them.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from twitchAPI.type import TwitchResourceNotFound, VideoType

API_CONCURRENCY = 8
VIDEOS_PER_CHANNEL = 20
CLIPS_PER_CHANNEL = 20
CLIP_WINDOW_DAYS = 30
TOP_GAMES = 100
TOP_GAMES_WITH_VIEWERS = 20  # viewer totals cost one request per game

DURATION_RE = re.compile(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$')


def parse_duration(duration: str) -> int:
    """Helix video duration like '3h2m1s' -> seconds"""
    match = DURATION_RE.match(duration or '')
    if not match or not any(match.groups()):
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _iso(value) -> Optional[str]:
    return value.isoformat(timespec='seconds') if isinstance(value, datetime) else value


async def _per_channel(func, user_ids: List[str], what: str) -> List:
    """Run func(user_id) for every channel with limited concurrency; failures are logged and skipped"""
    semaphore = asyncio.Semaphore(API_CONCURRENCY)

    async def run_one(user_id):
        async with semaphore:
            try:
                return await func(user_id)
            except Exception as e:
                print(f"⚠️ {what} lookup failed for {user_id}: {e}")
                return []

    results = await asyncio.gather(*(run_one(uid) for uid in user_ids))
    return [row for rows in results for row in rows]


async def fetch_videos(twitch, db, user_ids: List[str], per_channel: int = VIDEOS_PER_CHANNEL) -> int:
    """Store each channel's most recent past broadcasts (stream length and VOD views)"""
    async def videos_for(user_id):
        rows = []
        async for video in twitch.get_videos(user_id=user_id, video_type=VideoType.ARCHIVE, first=per_channel):
            rows.append({'video_id': video.id, 'user_id': video.user_id, 'created_at': _iso(video.created_at),
                         'duration_s': parse_duration(video.duration), 'view_count': video.view_count,
                         'title': video.title})
            if len(rows) >= per_channel:
                break
        return rows

    rows = await _per_channel(videos_for, user_ids, 'VOD')
    return db.save_videos(rows)


async def fetch_clips(twitch, db, user_ids: List[str], days: int = CLIP_WINDOW_DAYS,
                      per_channel: int = CLIPS_PER_CHANNEL) -> int:
    """Store each channel's top clips from the last `days` days"""
    started_at = datetime.now(timezone.utc) - timedelta(days=days)

    async def clips_for(user_id):
        rows = []
        async for clip in twitch.get_clips(broadcaster_id=user_id, started_at=started_at, first=per_channel):
            rows.append({'clip_id': clip.id, 'broadcaster_id': clip.broadcaster_id,
                         'created_at': _iso(clip.created_at), 'view_count': clip.view_count,
                         'game_id': clip.game_id, 'title': clip.title, 'url': clip.url,
                         'thumbnail_url': clip.thumbnail_url})
            if len(rows) >= per_channel:
                break
        return rows

    rows = await _per_channel(clips_for, user_ids, 'Clip')
    return db.save_clips(rows)


def summarize_schedule(segments, now: datetime, fetched_at: str, user_id: str) -> Dict:
    """Scheduled hours and segment count over the next 7 days (canceled segments excluded)"""
    horizon = now + timedelta(days=7)
    hours, count = 0.0, 0
    for segment in segments or []:
        start, end = segment.start_time, segment.end_time
        if not start or segment.canceled_until or not (now <= start < horizon):
            continue
        count += 1
        if end:
            hours += (end - start).total_seconds() / 3600
    return {'user_id': user_id, 'fetched_at': fetched_at, 'has_schedule': count > 0,
            'scheduled_hours_7d': round(hours, 2), 'segments_7d': count}


async def fetch_schedules(twitch, db, user_ids: List[str]) -> int:
    """Store a 7-day schedule summary per channel (channels without a schedule get has_schedule=False)"""
    now = datetime.now(timezone.utc)
    fetched_at = _iso(now)

    async def schedule_for(user_id):
        try:
            schedule = await twitch.get_channel_stream_schedule(user_id, first=25)
        except TwitchResourceNotFound:
            schedule = None  # Helix returns 404 when a channel has never set a schedule
        segments = schedule.segments if schedule else []
        return [summarize_schedule(segments, now, fetched_at, user_id)]

    rows = await _per_channel(schedule_for, user_ids, 'Schedule')
    return db.save_schedules(rows)


async def fetch_top_games(twitch, db, first: int = TOP_GAMES, with_viewers: int = TOP_GAMES_WITH_VIEWERS) -> int:
    """
    Store a snapshot of the top categories by rank. For the top `with_viewers` categories,
    viewer_sum is the total viewers across their top 100 live streams (None for the rest).
    """
    ts = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    games = []
    async for game in twitch.get_top_games(first=min(first, 100)):
        games.append(game)
        if len(games) >= first:
            break

    async def first_page_viewers(game_id):
        total, count = 0, 0
        async for stream in twitch.get_streams(game_id=[game_id], first=100):
            total += stream.viewer_count
            count += 1
            if count >= 100:
                break
        return total

    sums = await asyncio.gather(*(first_page_viewers(g.id) for g in games[:with_viewers]),
                                return_exceptions=True)
    rows = []
    for rank, game in enumerate(games, start=1):
        viewer_sum = sums[rank - 1] if rank <= len(sums) and not isinstance(sums[rank - 1], Exception) else None
        rows.append({'ts': ts, 'game_id': game.id, 'name': game.name, 'rank': rank, 'viewer_sum': viewer_sum})
    return db.save_top_games(rows)
