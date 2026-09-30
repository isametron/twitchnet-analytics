"""Metric computations on synthetic tracker data."""
from datetime import datetime, timedelta, timezone

import pytest

from twitchnet import metrics
from twitchnet.database import DatabaseManager
from twitchnet.metrics import circular_hour_spread, compute_all, enrich_streamers, shannon_entropy

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
STEP = timedelta(seconds=metrics.SNAPSHOT_INTERVAL_S)


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def iso(dt):
    return dt.isoformat(timespec='seconds')


def stream(db, user_id, start, samples, viewers, game='Game'):
    """Consecutive snapshots every SNAPSHOT_INTERVAL_S starting at `start`"""
    db.save_stream_snapshots([
        {'user_id': user_id, 'ts': iso(start + i * STEP), 'viewer_count': viewers[i % len(viewers)],
         'game_id': 'g', 'game_name': game, 'title': 't'}
        for i in range(samples)
    ])


def test_circular_spread_treats_midnight_as_close():
    assert circular_hour_spread([23, 1]) < 1.5
    assert circular_hour_spread([20, 20, 20]) == pytest.approx(0, abs=1e-6)
    assert circular_hour_spread([0, 12]) == 12.0
    assert circular_hour_spread([5]) is None


def test_shannon_entropy():
    assert shannon_entropy({'A': 1.0}) == 0
    assert shannon_entropy({'A': 0.5, 'B': 0.5}) == pytest.approx(1.0)


def test_viewer_hours_sessions_and_games(db):
    # Two 2-hour streams on different days, 20:00 and 21:00 UTC; the second is half 'Other'
    stream(db, '1', NOW - timedelta(days=2, hours=16), 24, [100, 300])
    stream(db, '1', NOW - timedelta(days=1, hours=15), 12, [200], game='Game')
    stream(db, '1', NOW - timedelta(days=1, hours=14), 12, [200], game='Other')
    row = compute_all(db, now=NOW).loc['1']

    assert row['avg_viewers'] == pytest.approx(200)
    assert row['peak_viewers'] == 300
    assert row['hours_streamed_7d'] == pytest.approx(4.0)
    assert row['sessions_7d'] == 2
    assert row['start_hour_spread'] == pytest.approx(0.5, abs=0.1)
    assert row['game_shares'] == {'Game': 0.75, 'Other': 0.25}
    assert row['category_variety'] == pytest.approx(0.811, abs=0.001)
    # Tracked for 3 days (rounded up), live on 2 of them
    assert row['days_live_share_7d'] == pytest.approx(2 / 3, abs=0.001)


def test_old_snapshots_only_count_in_30_day_window(db):
    stream(db, '1', NOW - timedelta(days=20), 12, [50])
    stream(db, '1', NOW - timedelta(days=1), 12, [50])
    row = compute_all(db, now=NOW).loc['1']
    assert row['hours_streamed_7d'] == pytest.approx(1.0)
    assert row['hours_streamed_30d'] == pytest.approx(2.0)


def test_follower_growth_and_viewer_ratio(db):
    stream(db, '1', NOW - timedelta(hours=3), 12, [500])
    db.save_follower_snapshots([
        {'user_id': '1', 'ts': iso(NOW - timedelta(days=10)), 'followers': 8000},
        {'user_id': '1', 'ts': iso(NOW - timedelta(days=6)), 'followers': 9000},
        {'user_id': '1', 'ts': iso(NOW - timedelta(hours=1)), 'followers': 10000},
    ])
    row = compute_all(db, now=NOW).loc['1']
    assert row['follower_growth_7d'] == 1000
    assert row['follower_growth_7d_pct'] == pytest.approx(11.111, abs=0.001)
    assert row['viewer_to_follower_ratio'] == pytest.approx(0.05)


def test_ratio_uses_record_followers_without_snapshots(db):
    stream(db, '1', NOW - timedelta(hours=3), 12, [500])
    row = compute_all(db, now=NOW, followers={'1': 1000}).loc['1']
    assert row['viewer_to_follower_ratio'] == pytest.approx(0.5)
    assert row['follower_growth_7d'] is None


def test_chat_raid_clip_vod_and_schedule_metrics(db):
    stream(db, '1', NOW - timedelta(hours=3), 24, [100])  # 2 hours at 100 viewers = 200 viewer-hours
    db.save_chat_presence([{'channel_id': '1', 'chatter_hash': f'h{i}', 'first_seen': 't', 'last_seen': 't',
                            'msg_count': 10} for i in range(40)])  # 40 unique chatters
    db.save_chat_activity([
        {'channel_id': '1', 'minute': iso(NOW - timedelta(hours=2)), 'messages': 300},
        {'channel_id': '1', 'minute': iso(NOW - timedelta(hours=1)), 'messages': 100},
        {'channel_id': '1', 'minute': iso(NOW - timedelta(hours=5)), 'messages': 999},  # before first snapshot
    ])  # 400 messages while tracked
    db.save_raids([{'from_id': '1', 'to_id': '2', 'ts': 'a', 'viewers': 5},
                   {'from_id': '3', 'to_id': '1', 'ts': 'b', 'viewers': 5},
                   {'from_id': '3', 'to_id': '1', 'ts': 'c', 'viewers': 5}])
    db.save_clips([{'clip_id': f'c{i}', 'broadcaster_id': '1', 'created_at': iso(NOW - timedelta(days=d)),
                    'view_count': 100, 'game_id': 'g', 'title': 'x', 'url': 'u', 'thumbnail_url': 't'}
                   for i, d in enumerate([1, 2, 40])])
    db.save_videos([{'video_id': 'v1', 'user_id': '1', 'created_at': 'x', 'duration_s': 7200, 'view_count': 1,
                     'title': 't'}, {'video_id': 'v2', 'user_id': '1', 'created_at': 'y', 'duration_s': 3600,
                                     'view_count': 1, 'title': 't'}])
    db.save_schedules([{'user_id': '1', 'fetched_at': 'x', 'has_schedule': True, 'scheduled_hours_7d': 12.5,
                        'segments_7d': 5}])
    m = compute_all(db, now=NOW)
    row = m.loc['1']

    assert row['unique_chatters'] == 40 and row['chat_messages'] == 400
    assert row['chat_msgs_per_viewer_hour'] == pytest.approx(2.0)
    assert row['raids_out'] == 1 and row['raids_in'] == 2
    assert m.loc['3', 'raids_out'] == 2
    assert row['clips_30d'] == 2 and row['clip_views_30d'] == 200  # the 40-day-old clip is excluded
    assert row['clip_velocity'] == pytest.approx(1.0)  # 2 clips / 2 hours streamed
    assert row['vods'] == 2 and row['avg_vod_hours'] == pytest.approx(1.5)
    assert row['has_schedule'] is True or row['has_schedule'] == 1
    assert row['scheduled_hours_7d'] == 12.5


def test_compute_all_on_empty_database(db):
    assert compute_all(db, now=NOW).empty


def test_enrich_streamers_adds_metrics_and_nones(db):
    stream(db, '1', NOW - timedelta(hours=1), 12, [100])
    enriched = enrich_streamers([{'user_id': '1', 'follower_count': 1000},
                                 {'user_id': '2', 'follower_count': 50}], db, now=NOW)
    assert enriched[0]['avg_viewers'] == pytest.approx(100)
    assert enriched[0]['viewer_to_follower_ratio'] == pytest.approx(0.1)
    assert enriched[0]['game_shares'] == {'Game': 1.0}
    assert enriched[1]['avg_viewers'] is None and enriched[1]['game_shares'] is None
    assert enriched[1]['follower_count'] == 50  # original fields kept
