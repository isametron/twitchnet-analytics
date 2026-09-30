"""
Long-running tracker for tracked channels: live snapshots, relationships and content.

  python tracker.py --seed [--limit 100]           track the largest streamers already in the database
  python tracker.py --seed --live --limit 300      track the top channels live right now (collects them first)
  python tracker.py --seed --live --replace        same, replacing the current tracked list
  python tracker.py [--minutes 30]                 run until Ctrl+C (or for N minutes)

While running it records, for every tracked channel:
  every 5 min   live viewer snapshots, @mentions in titles, Shared Chat co-streams
  continuously  chat audience overlap and incoming raids (both read from chat)
  hourly        top categories
  every 6 h     follower counts, VODs, clips and stream schedules
  daily         team membership

Everything is written to the SQLite database; the dashboard reads it from there.
"""
import argparse
import asyncio
import time
from datetime import datetime, timezone

from twitchnet.config import Config
from twitchnet.content import fetch_clips, fetch_schedules, fetch_top_games, fetch_videos
from twitchnet.database import DatabaseManager
from twitchnet.metrics import SNAPSHOT_INTERVAL_S
from twitchnet.relations import (
    ChatPresenceLogger,
    extract_title_mentions,
    fetch_shared_chat,
    fetch_teams,
)
from twitchnet.twitch_api import TwitchDataCollector, _chunks

TOP_GAMES_REFRESH_S = 3600
FOLLOWERS_REFRESH_S = 6 * 3600
CONTENT_REFRESH_S = 6 * 3600
TEAMS_REFRESH_S = 24 * 3600
STATUS_INTERVAL_S = 300
DEFAULT_SEED_LIMIT = 100


async def collect_live(db: DatabaseManager, limit: int):
    """Collect and save the current top live streamers"""
    collector = TwitchDataCollector(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    await collector.initialize()
    try:
        streamers = await collector.get_top_streamers(max_results=limit)
    finally:
        await collector.close()
    db.save_streamers(streamers)
    return streamers


def seed(db: DatabaseManager, limit: int, streamers=None, replace: bool = False) -> int:
    """Track the given streamers, or the ones with the most followers in the database"""
    if streamers is None:
        streamers = db.load_streamers()
    streamers = sorted(streamers, key=lambda s: s.get('follower_count') or 0, reverse=True)[:limit]
    if replace:
        db.remove_tracked_channels([t['user_id'] for t in db.load_tracked_channels()])
    added = db.add_tracked_channels([{'user_id': s['user_id'], 'login': s['username']} for s in streamers])
    print(f"Tracking {len(db.load_tracked_channels())} channels ({added} submitted from the database)")
    return added


def snapshot_rows(streams, ts: str):
    return [{'user_id': s.user_id, 'ts': ts, 'viewer_count': s.viewer_count, 'game_id': s.game_id,
             'game_name': s.game_name, 'title': s.title} for s in streams]


async def poll_live(collector: TwitchDataCollector, db: DatabaseManager, tracked, stats: dict):
    """One pass over live tracked channels: viewer snapshots, @mentions in titles, Shared Chat co-streams"""
    ts = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    streams = []
    for chunk in _chunks([t['user_id'] for t in tracked]):
        async for stream in collector.twitch.get_streams(user_id=chunk, first=100):
            streams.append(stream)
    db.save_stream_snapshots(snapshot_rows(streams, ts))
    stats['snapshots'] += len(streams)

    known_logins = {t['login'].lower(): t['user_id'] for t in tracked}
    mentions = extract_title_mentions(
        [{'user_id': s.user_id, 'title': s.title, 'started_at': str(s.started_at)} for s in streams], known_logins
    )
    db.save_collabs(mentions)
    shared = await fetch_shared_chat(collector.twitch, db, [s.user_id for s in streams])
    print(f"🔗 {len(streams)} tracked channels live; {len(mentions)} title mentions, {shared} shared-chat pairs")


async def snapshot_followers(collector: TwitchDataCollector, db: DatabaseManager, ids):
    ts = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    totals = await collector._fetch_follower_totals(ids)
    rows = [{'user_id': uid, 'ts': ts, 'followers': total} for uid, total in totals.items() if total is not None]
    db.save_follower_snapshots(rows)
    print(f"👤 Follower counts saved for {len(rows)} channels")


async def refresh_content(collector: TwitchDataCollector, db: DatabaseManager, ids):
    videos = await fetch_videos(collector.twitch, db, ids)
    clips = await fetch_clips(collector.twitch, db, ids)
    schedules = await fetch_schedules(collector.twitch, db, ids)
    print(f"🎞️ Content refreshed: {videos} VODs, {clips} clips, {schedules} schedules")


async def refresh_top_games(collector: TwitchDataCollector, db: DatabaseManager):
    print(f"🎮 Top categories saved ({await fetch_top_games(collector.twitch, db)})")


async def every(interval_s: float, name: str, func, *args):
    """Run func(*args) now and then every interval_s seconds; errors are logged, not fatal"""
    while True:
        try:
            await func(*args)
        except Exception as e:
            print(f"⚠️ {name} failed: {e}")
        await asyncio.sleep(interval_s)


async def report_status(chat, stats, started):
    while True:
        await asyncio.sleep(STATUS_INTERVAL_S)
        parts = [f"up {(time.time() - started) / 60:.0f} min", f"{stats['snapshots']} snapshots"]
        if chat:
            parts.append(f"chat {chat.connected}/{chat.connection_count} connected, {chat.messages_seen} messages, "
                         f"{chat.raids_seen} raids")
        print("📊 " + " | ".join(parts))


async def run(args):
    db = DatabaseManager()
    tracked = db.load_tracked_channels()
    if not tracked:
        print("No tracked channels yet. Collect streamers in the app, then run: python tracker.py --seed")
        return
    ids = [t['user_id'] for t in tracked]
    print(f"Tracking {len(tracked)} channels")

    collector = TwitchDataCollector(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    await collector.initialize()

    # Chat carries both audience overlap and raid notices for every tracked channel
    chat = None if args.no_chat else ChatPresenceLogger(db, [t['login'] for t in tracked])

    stats = {'snapshots': 0}
    tasks = [
        asyncio.create_task(every(SNAPSHOT_INTERVAL_S, 'Live poll', poll_live, collector, db, tracked, stats)),
        asyncio.create_task(every(TOP_GAMES_REFRESH_S, 'Top categories', refresh_top_games, collector, db)),
        asyncio.create_task(every(FOLLOWERS_REFRESH_S, 'Follower snapshot', snapshot_followers, collector, db, ids)),
        asyncio.create_task(every(CONTENT_REFRESH_S, 'Content refresh', refresh_content, collector, db, ids)),
        asyncio.create_task(every(TEAMS_REFRESH_S, 'Team refresh', fetch_teams, collector.twitch, db, ids)),
        asyncio.create_task(report_status(chat, stats, time.time())),
    ]
    if chat:
        tasks.append(asyncio.create_task(chat.run()))

    try:
        await asyncio.wait(tasks, timeout=args.minutes * 60 if args.minutes else None)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)  # lets the chat logger flush
        await collector.close()
        print("Tracker stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed', action='store_true', help='add the largest collected streamers to the tracked list')
    parser.add_argument('--limit', type=int, default=DEFAULT_SEED_LIMIT, help='how many streamers --seed tracks')
    parser.add_argument('--live', action='store_true', help='with --seed: use the top channels live right now')
    parser.add_argument('--replace', action='store_true', help='with --seed: replace the current tracked list')
    parser.add_argument('--minutes', type=float, help='stop after this many minutes (default: run until Ctrl+C)')
    parser.add_argument('--no-chat', action='store_true', help='skip chat logging (audience overlap and raids)')
    args = parser.parse_args()

    Config.make_console_safe()
    Config.create_directories()
    if args.seed:
        db = DatabaseManager()
        seed(db, args.limit, asyncio.run(collect_live(db, args.limit)) if args.live else None, args.replace)
        return
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
