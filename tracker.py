"""
Long-running tracker for relationship data between tracked channels.

  python tracker.py --seed [--limit 100]   track the largest streamers already in the database
  python tracker.py --seed --live          track the top channels live right now (collects them first)
  python tracker.py [--minutes 30]         log chat overlap, raids, collabs and teams (Ctrl+C to stop)
  python tracker.py --no-raids             skip EventSub raids (no Twitch sign-in needed)

Everything is written to the SQLite database; the dashboard reads it from there.
"""
import argparse
import asyncio
import time

from auth import get_user_twitch
from twitchnet.config import Config
from twitchnet.database import DatabaseManager
from twitchnet.relations import (
    ChatPresenceLogger,
    RaidListener,
    extract_title_mentions,
    fetch_shared_chat,
    fetch_teams,
)
from twitchnet.twitch_api import TwitchDataCollector, _chunks

RELATIONS_POLL_S = 300  # live streams: title mentions and Shared Chat sessions
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


def seed(db: DatabaseManager, limit: int, streamers=None) -> int:
    """Track the given streamers, or the ones with the most followers in the database"""
    if streamers is None:
        streamers = db.load_streamers()
    streamers = sorted(streamers, key=lambda s: s.get('follower_count') or 0, reverse=True)[:limit]
    added = db.add_tracked_channels([{'user_id': s['user_id'], 'login': s['username']} for s in streamers])
    print(f"Tracking {len(db.load_tracked_channels())} channels ({added} submitted from the database)")
    return added


async def poll_relations(collector: TwitchDataCollector, db: DatabaseManager, tracked):
    """One pass over live tracked channels: @mentions in titles and Shared Chat co-streams"""
    streams = []
    for chunk in _chunks([t['user_id'] for t in tracked]):
        async for stream in collector.twitch.get_streams(user_id=chunk, first=100):
            streams.append(stream)

    known_logins = {t['login'].lower(): t['user_id'] for t in tracked}
    mentions = extract_title_mentions(
        [{'user_id': s.user_id, 'title': s.title, 'started_at': str(s.started_at)} for s in streams], known_logins
    )
    db.save_collabs(mentions)
    shared = await fetch_shared_chat(collector.twitch, db, [s.user_id for s in streams])
    print(f"🔗 {len(streams)} tracked channels live; {len(mentions)} title mentions, {shared} shared-chat pairs")


async def every(interval_s: float, name: str, func, *args):
    """Run func(*args) now and then every interval_s seconds; errors are logged, not fatal"""
    while True:
        try:
            await func(*args)
        except Exception as e:
            print(f"⚠️ {name} failed: {e}")
        await asyncio.sleep(interval_s)


async def report_status(chat, raids, started):
    while True:
        await asyncio.sleep(STATUS_INTERVAL_S)
        parts = [f"up {(time.time() - started) / 60:.0f} min"]
        if chat:
            parts.append(f"chat {'connected' if chat.connected else 'DISCONNECTED'}, {chat.messages_seen} messages")
        if raids:
            parts.append(f"{raids.raids_seen} raids on {raids.subscribed} subscriptions")
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

    chat = None if args.no_chat else ChatPresenceLogger(db, [t['login'] for t in tracked])
    raids, user_twitch = None, None
    if not args.no_raids:
        user_twitch = await get_user_twitch()
        raids = RaidListener(db, user_twitch, ids)
        await raids.start()

    tasks = [
        asyncio.create_task(every(RELATIONS_POLL_S, 'Relations poll', poll_relations, collector, db, tracked)),
        asyncio.create_task(every(TEAMS_REFRESH_S, 'Team refresh', fetch_teams, collector.twitch, db, ids)),
        asyncio.create_task(report_status(chat, raids, time.time())),
    ]
    if chat:
        tasks.append(asyncio.create_task(chat.run()))

    try:
        await asyncio.wait(tasks, timeout=args.minutes * 60 if args.minutes else None)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)  # lets the chat logger flush
        if raids:
            await raids.stop()
        if user_twitch:
            await user_twitch.close()
        await collector.close()
        print("Tracker stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed', action='store_true', help='add the largest collected streamers to the tracked list')
    parser.add_argument('--limit', type=int, default=DEFAULT_SEED_LIMIT, help='how many streamers --seed tracks')
    parser.add_argument('--live', action='store_true', help='with --seed: use the top channels live right now')
    parser.add_argument('--minutes', type=float, help='stop after this many minutes (default: run until Ctrl+C)')
    parser.add_argument('--no-chat', action='store_true', help='skip the chat overlap logger')
    parser.add_argument('--no-raids', action='store_true', help='skip EventSub raids (no Twitch sign-in)')
    args = parser.parse_args()

    Config.make_console_safe()
    Config.create_directories()
    if args.seed:
        db = DatabaseManager()
        seed(db, args.limit, asyncio.run(collect_live(db, args.limit)) if args.live else None)
        return
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
