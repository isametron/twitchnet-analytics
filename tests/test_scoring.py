"""Brand safety, engagement, feature extraction, recommender reach and raid influence."""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from twitchnet.centrality import CentralityAnalyzer
from twitchnet.config import Config
from twitchnet.database import DatabaseManager
from twitchnet.recommender import (
    FOLLOWER_REACH_RATE,
    UNIQUE_VIEWERS_PER_CONCURRENT,
    StreamerRecommender,
)
from twitchnet.scoring import CONTENT_LABEL_RISK, AdvancedScorer
from twitchnet.similarity_calc import FeatureExtractor, SimilarityCalculator

scorer = AdvancedScorer()


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def test_content_labels_add_risk():
    base = scorer.calculate_risk_score(50_000, True)
    assert base == 0
    assert scorer.calculate_risk_score(50_000, True, content_labels=['Gambling']) == CONTENT_LABEL_RISK['Gambling']
    both = scorer.calculate_risk_score(50_000, True, content_labels=['Gambling', 'SexualThemes', 'Gambling'])
    assert both == pytest.approx(CONTENT_LABEL_RISK['Gambling'] + CONTENT_LABEL_RISK['SexualThemes'])
    assert scorer.calculate_risk_score(50_000, True, content_labels=['SomethingNew']) == pytest.approx(0.1)
    assert scorer.calculate_risk_score(500, False, content_labels=list(CONTENT_LABEL_RISK)) == 1.0


def test_live_engagement():
    assert scorer.calculate_live_engagement(0.05) == pytest.approx(0.5)
    assert scorer.calculate_live_engagement(0.5) == 1.0
    assert scorer.calculate_live_engagement(0.05, 1.0) == pytest.approx(0.6 * 0.5 + 0.4 * 0.5)
    assert scorer.calculate_live_engagement(None) == 0
    assert scorer.calculate_live_engagement(0.05, float('nan')) == pytest.approx(0.5)


def test_engagement_uses_avg_viewers_when_tracked():
    tracked = scorer.calculate_engagement_score(10_000, avg_viewers=500)
    assert tracked == pytest.approx(0.5)
    untracked = scorer.calculate_engagement_score(10_000, is_partner=True)
    assert untracked == pytest.approx(min(np.log1p(10_000) / np.log1p(1_000_000) * 0.9 + 0.1, 1))


def streamers_df(**extra_columns):
    df = pd.DataFrame([
        {'user_id': '1', 'username': 'a', 'display_name': 'A', 'game_name': 'Chess', 'language': 'en',
         'tags': ['English'], 'is_partner': True, 'follower_count': 10_000, 'viewer_count': 100,
         'content_classification_labels': []},
        {'user_id': '2', 'username': 'b', 'display_name': 'B', 'game_name': 'Poker', 'language': 'en',
         'tags': ['English'], 'is_partner': True, 'follower_count': 20_000, 'viewer_count': 4_000,
         'content_classification_labels': ['Gambling']},
    ])
    for column, values in extra_columns.items():
        df[column] = values
    return df


def test_game_features_use_game_history_shares():
    df = streamers_df(game_shares=[{'Chess': 0.7, 'Poker': 0.3}, None])
    extractor = FeatureExtractor()
    features = extractor.extract_streamer_features(df)
    classes = list(extractor.mlb_games.classes_)
    assert classes == ['Chess', 'Poker']
    assert features[0, :2].tolist() == [0.7, 0.3]
    assert features[1, :2].tolist() == [0.0, 1.0]  # no history: current game one-hot


def test_features_unchanged_without_tracker_columns():
    df = streamers_df()
    features = FeatureExtractor().extract_streamer_features(df)
    assert features[:, :2].tolist() == [[1.0, 0.0], [0.0, 1.0]]


def make_recommender(df):
    extractor = FeatureExtractor()
    features = extractor.extract_streamer_features(df)
    graph = nx.path_graph(['1', '2'])
    return StreamerRecommender(df, {'pagerank': nx.pagerank(graph)},
                               SimilarityCalculator(features, df['user_id'].tolist())), extractor


def test_brand_safety_uses_content_labels():
    recommender, _ = make_recommender(streamers_df())
    assert recommender.brand_safety('1') == 1.0
    assert recommender.brand_safety('2') == pytest.approx(1 - CONTENT_LABEL_RISK['Gambling'])
    assert recommender.brand_safety('missing') == 0.0


def test_engagement_prefers_tracked_metrics():
    plain, _ = make_recommender(streamers_df())
    tracked, _ = make_recommender(streamers_df(viewer_to_follower_ratio=[0.1, np.nan],
                                               chat_msgs_per_viewer_hour=[2.0, np.nan]))
    # Streamer 2 has no tracker data (NaN) and falls back to live viewer_count / followers
    assert tracked.calculate_composite_score('2', 0.0) == pytest.approx(plain.calculate_composite_score('2', 0.0))
    # Streamer 1: live fallback is 100 / 10k = 1% -> 0.1 engagement; tracked metrics give the maximum 1.0
    gain = tracked.calculate_composite_score('1', 0.0) - plain.calculate_composite_score('1', 0.0)
    assert gain == pytest.approx(Config.ENGAGEMENT_WEIGHT * (1.0 - 0.1))


def test_recommendations_include_viewers_and_safety():
    df = streamers_df(avg_viewers=[150.0, np.nan])
    recommender, extractor = make_recommender(df)
    profile = {'games': ['Chess'], 'follower_range': (0, 1_000_000), 'languages': ['en']}
    recs = recommender.recommend_streamers(extractor.extract_company_features(profile), profile, top_n=5)
    by_id = recs.set_index('user_id')
    assert by_id.loc['1', 'avg_viewers'] == 150.0 and pd.isna(by_id.loc['2', 'avg_viewers'])
    assert by_id.loc['2', 'brand_safety_score'] == pytest.approx(0.7)


def test_reach_uses_avg_viewers_when_known():
    recommender, _ = make_recommender(streamers_df())
    allocations = recommender.allocate_budget([
        {'user_id': '1', 'display_name': 'A', 'follower_count': 10_000, 'avg_viewers': 200.0},
        {'user_id': '2', 'display_name': 'B', 'follower_count': 20_000, 'avg_viewers': None},
    ], 1000)
    assert allocations[0].estimated_reach == 200 * UNIQUE_VIEWERS_PER_CONCURRENT
    assert allocations[1].estimated_reach == int(20_000 * FOLLOWER_REACH_RATE)


def test_raid_influence(db):
    graph = nx.Graph()
    graph.add_nodes_from(['1', '2', '3'])
    analyzer = CentralityAnalyzer(graph)
    assert set(analyzer.calculate_raid_influence(db).values()) == {0.0}

    db.save_raids([{'from_id': '1', 'to_id': '3', 'ts': 'a', 'viewers': 1},
                   {'from_id': '2', 'to_id': '3', 'ts': 'b', 'viewers': 1},
                   {'from_id': '9', 'to_id': '3', 'ts': 'c', 'viewers': 1}])  # 9 isn't in the graph
    scores = analyzer.calculate_raid_influence(db)
    assert max(scores, key=scores.get) == '3'
    assert scores['1'] == pytest.approx(scores['2'])
    assert analyzer.centrality_scores['raid_influence'] is scores
