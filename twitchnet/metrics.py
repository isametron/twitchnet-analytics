"""
Per-streamer metrics computed from the tracker's tables:

- stream_snapshots (sampled every SNAPSHOT_INTERVAL_S while live): average/peak viewers,
  hours streamed, days live, start-time spread, game history and category variety
- follower_snapshots: follower growth
- chat_presence / chat_activity: unique chatters and chat messages per viewer-hour
- raids, clips, videos, schedules: raid counts, clip activity, VOD stats, scheduled hours

compute_all(db) returns one row per streamer; enrich_streamers(streamers, db) merges the
metrics into streamer records for scoring and recommendations.
"""
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

SNAPSHOT_INTERVAL_S = 300  # tracker.py samples live streams this often
# Consecutive snapshots further apart than this start a new stream session
SESSION_GAP_S = 3 * SNAPSHOT_INTERVAL_S

METRIC_COLUMNS = [
    'avg_viewers', 'peak_viewers', 'hours_streamed_7d', 'hours_streamed_30d', 'days_live_share_7d',
    'sessions_7d', 'start_hour_spread', 'follower_growth_7d', 'follower_growth_7d_pct',
    'viewer_to_follower_ratio', 'unique_chatters', 'chat_messages', 'chat_msgs_per_viewer_hour',
    'raids_in', 'raids_out', 'category_variety', 'clips_30d', 'clip_views_30d', 'clip_velocity',
    'vods', 'avg_vod_hours', 'has_schedule', 'scheduled_hours_7d',
]


def _utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, format='ISO8601')


def circular_hour_spread(hours: List[float]) -> Optional[float]:
    """Circular standard deviation of hours-of-day (0-24), so 23:00 and 01:00 count as close"""
    if len(hours) < 2:
        return None
    angles = np.asarray(hours) / 24 * 2 * math.pi
    resultant = abs(np.mean(np.exp(1j * angles)))
    if resultant <= 1e-12:
        return 12.0
    return float(math.sqrt(-2 * math.log(resultant)) * 24 / (2 * math.pi))


def shannon_entropy(shares: Dict[str, float]) -> float:
    """Entropy in bits of a share distribution (0 = one category only)"""
    values = [s for s in shares.values() if s > 0]
    return float(sum(s * math.log2(1 / s) for s in values))


def _session_starts(times: pd.Series) -> pd.Series:
    times = times.sort_values()
    new_session = times.diff().dt.total_seconds().fillna(float('inf')) > SESSION_GAP_S
    return times[new_session]


def snapshot_metrics(snapshots: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Viewer, schedule-regularity and game-history metrics from stream snapshots"""
    if snapshots.empty:
        return pd.DataFrame()
    snapshots = snapshots.assign(ts=_utc(snapshots['ts']))
    interval_h = SNAPSHOT_INTERVAL_S / 3600
    week_ago, month_ago = now - timedelta(days=7), now - timedelta(days=30)

    rows = {}
    for user_id, group in snapshots.groupby('user_id'):
        week = group[group['ts'] >= week_ago]
        # Only count days since tracking of this channel began, so new channels aren't penalised
        tracked_days = min(7, max(1, math.ceil((now - group['ts'].min()).total_seconds() / 86400)))
        starts = _session_starts(week['ts'])
        game_counts = group['game_name'].fillna('Unknown').value_counts()
        shares = (game_counts / game_counts.sum()).round(4).to_dict()
        rows[user_id] = {
            'avg_viewers': float(group['viewer_count'].mean()),
            'peak_viewers': int(group['viewer_count'].max()),
            'hours_streamed_7d': round(len(week) * interval_h, 2),
            'hours_streamed_30d': round(int((group['ts'] >= month_ago).sum()) * interval_h, 2),
            'days_live_share_7d': round(week['ts'].dt.date.nunique() / tracked_days, 3),
            'sessions_7d': len(starts),
            'start_hour_spread': circular_hour_spread(
                (starts.dt.hour + starts.dt.minute / 60).tolist()),
            'game_shares': shares,
            'category_variety': round(shannon_entropy(shares), 3),
        }
    return pd.DataFrame.from_dict(rows, orient='index')


def follower_metrics(snapshots: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Follower growth over the last 7 days (needs at least two samples in that window)"""
    if snapshots.empty:
        return pd.DataFrame()
    snapshots = snapshots.assign(ts=_utc(snapshots['ts'])).sort_values('ts')
    rows = {}
    for user_id, group in snapshots.groupby('user_id'):
        week = group[group['ts'] >= now - timedelta(days=7)]
        latest = int(group['followers'].iloc[-1])
        row = {'followers_latest': latest, 'follower_growth_7d': None, 'follower_growth_7d_pct': None}
        if len(week) >= 2:
            first = int(week['followers'].iloc[0])
            row['follower_growth_7d'] = latest - first
            row['follower_growth_7d_pct'] = round((latest - first) / first * 100, 3) if first else None
        rows[user_id] = row
    return pd.DataFrame.from_dict(rows, orient='index')


def chat_metrics(db, now: datetime) -> pd.DataFrame:
    """
    unique_chatters: all chatters ever seen. chat_messages: messages in the last 30 days, counted only
    from each channel's first viewer snapshot on, so they cover the same period as its viewer-hours.
    """
    chatters = db.conn.execute(
        "SELECT channel_id, COUNT(*) FROM chat_presence GROUP BY channel_id"
    ).fetchall()
    since = (now - timedelta(days=30)).isoformat(timespec='seconds')
    messages = db.conn.execute('''
        SELECT a.channel_id, SUM(a.messages)
        FROM chat_activity a
        JOIN (SELECT user_id, MIN(ts) AS first_ts FROM stream_snapshots GROUP BY user_id) s
          ON s.user_id = a.channel_id
        WHERE a.minute >= s.first_ts AND a.minute >= ?
        GROUP BY a.channel_id
    ''', (since,)).fetchall()
    return pd.concat([
        pd.DataFrame(chatters, columns=['user_id', 'unique_chatters']).set_index('user_id'),
        pd.DataFrame(messages, columns=['user_id', 'chat_messages']).set_index('user_id'),
    ], axis=1)


def raid_metrics(db) -> pd.DataFrame:
    raids_out = db.conn.execute("SELECT from_id, COUNT(*) FROM raids GROUP BY from_id").fetchall()
    raids_in = db.conn.execute("SELECT to_id, COUNT(*) FROM raids GROUP BY to_id").fetchall()
    return pd.concat([
        pd.DataFrame(raids_out, columns=['user_id', 'raids_out']).set_index('user_id'),
        pd.DataFrame(raids_in, columns=['user_id', 'raids_in']).set_index('user_id'),
    ], axis=1)


def clip_metrics(db, now: datetime) -> pd.DataFrame:
    since = (now - timedelta(days=30)).isoformat(timespec='seconds')
    rows = db.conn.execute(
        "SELECT broadcaster_id, COUNT(*), SUM(view_count) FROM clips WHERE created_at >= ? GROUP BY broadcaster_id",
        (since,)
    ).fetchall()
    return pd.DataFrame(rows, columns=['user_id', 'clips_30d', 'clip_views_30d']).set_index('user_id')


def video_metrics(db) -> pd.DataFrame:
    rows = db.conn.execute(
        "SELECT user_id, COUNT(*), AVG(duration_s) / 3600.0 FROM videos GROUP BY user_id"
    ).fetchall()
    df = pd.DataFrame(rows, columns=['user_id', 'vods', 'avg_vod_hours']).set_index('user_id')
    return df.round({'avg_vod_hours': 2})


def schedule_metrics(db) -> pd.DataFrame:
    rows = db.load_schedules()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index('user_id')[['has_schedule', 'scheduled_hours_7d']]
    return df.assign(has_schedule=df['has_schedule'].astype(bool))


def compute_all(db, now: datetime = None, followers: Dict[str, int] = None) -> pd.DataFrame:
    """
    One row of metrics per streamer, indexed by user_id.

    Args:
        db: DatabaseManager with tracker data
        now: Reference time (default: current UTC time)
        followers: Optional user_id -> follower count, used when no follower snapshot exists
    """
    now = now or datetime.now(timezone.utc)
    parts = [
        snapshot_metrics(pd.DataFrame(db.load_stream_snapshots()), now),
        follower_metrics(pd.DataFrame(db.load_follower_snapshots()), now),
        chat_metrics(db, now), raid_metrics(db), clip_metrics(db, now), video_metrics(db), schedule_metrics(db),
    ]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=METRIC_COLUMNS + ['game_shares'])
    metrics = pd.concat(parts, axis=1)
    metrics.index.name = 'user_id'
    for column in METRIC_COLUMNS + ['game_shares', 'followers_latest']:
        if column not in metrics:
            metrics[column] = None

    metrics[['raids_in', 'raids_out']] = metrics[['raids_in', 'raids_out']].fillna(0).astype(int)

    follower_base = metrics['followers_latest']
    if followers:
        follower_base = follower_base.fillna(pd.Series(followers, dtype=float))
    follower_base = pd.to_numeric(follower_base, errors='coerce')
    avg_viewers = pd.to_numeric(metrics['avg_viewers'], errors='coerce')
    metrics['viewer_to_follower_ratio'] = (avg_viewers / follower_base.where(follower_base > 0)).round(5)

    # Chat messages per viewer per streamed hour (chat is only logged while the tracker runs)
    viewer_hours = avg_viewers * pd.to_numeric(metrics['hours_streamed_30d'], errors='coerce')
    chat = pd.to_numeric(metrics['chat_messages'], errors='coerce')
    metrics['chat_msgs_per_viewer_hour'] = (chat / viewer_hours.where(viewer_hours > 0)).round(4)

    clip_hours = pd.to_numeric(metrics['hours_streamed_30d'], errors='coerce')
    clips = pd.to_numeric(metrics['clips_30d'], errors='coerce')
    metrics['clip_velocity'] = (clips / clip_hours.where(clip_hours > 0)).round(3)
    return metrics


def enrich_streamers(streamers: List[Dict], db, now: datetime = None) -> List[Dict]:
    """Streamer records with metric columns added (None where no data was collected yet)"""
    followers = {s['user_id']: s.get('follower_count') for s in streamers}
    metrics = compute_all(db, now, followers)
    enriched = []
    for streamer in streamers:
        row = dict(streamer)
        if streamer['user_id'] in metrics.index:
            values = metrics.loc[streamer['user_id']]
            for column in METRIC_COLUMNS + ['game_shares']:
                value = values[column]
                row[column] = None if not isinstance(value, dict) and pd.isna(value) else value
        else:
            row.update({column: None for column in METRIC_COLUMNS + ['game_shares']})
        enriched.append(row)
    return enriched
