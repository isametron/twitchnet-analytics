"""Graph builder tests: edge merging, relationship edges and network modes."""
import pytest

from database import DatabaseManager
from graph_builder import HYBRID_ATTRIBUTE_WEIGHT, StreamerNetworkBuilder


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / 'test.db'))
    yield manager
    manager.close()


def streamers(n=4):
    return [{'user_id': str(i), 'username': f'u{i}', 'display_name': f'U{i}', 'game_name': 'Game',
             'language': 'en', 'tags': ['English'], 'is_partner': True, 'follower_count': 1000 * i}
            for i in range(1, n + 1)]


def builder_with(nodes=None):
    b = StreamerNetworkBuilder()
    b.add_streamers(nodes or streamers())
    return b


def add_chat(db, channel_id, chatters):
    db.save_chat_presence([{'channel_id': channel_id, 'chatter_hash': h, 'first_seen': 't', 'last_seen': 't',
                            'msg_count': 1} for h in chatters])


def test_merge_edge_accumulates_weight_and_types():
    b = builder_with()
    assert b._add_or_merge_edge('1', '2', 1.0, 'same_game') is True
    assert b._add_or_merge_edge('2', '1', 0.5, 'raid', extra=3) is False
    edge = b.graph['1']['2']
    assert edge['weight'] == 1.5 and edge['types'] == {'same_game', 'raid'} and edge['extra'] == 3


def test_chat_overlap_uses_overlap_coefficient(db):
    add_chat(db, '1', [f'h{i}' for i in range(10)])        # 10 chatters
    add_chat(db, '2', [f'h{i}' for i in range(5, 25)])     # 20 chatters, 5 shared with channel 1
    add_chat(db, '3', [f'h{i}' for i in range(20, 23)])    # 3 shared with channel 2 (< min_shared)
    add_chat(db, '99', [f'h{i}' for i in range(10)])       # not in the graph

    b = builder_with()
    b.add_edges_from_chat_overlap(db, min_shared=5)

    assert sorted(tuple(sorted(e)) for e in b.graph.edges()) == [('1', '2')]
    edge = b.graph['1']['2']
    assert edge['shared_chatters'] == 5
    assert edge['chat_overlap'] == pytest.approx(5 / 10)
    assert edge['types'] == {'chat_overlap'}


def test_raid_edges_count_raids_per_sender(db):
    db.save_raids([
        {'from_id': '1', 'to_id': '2', 'ts': 'a', 'viewers': 10},
        {'from_id': '1', 'to_id': '2', 'ts': 'b', 'viewers': 10},
        {'from_id': '2', 'to_id': '1', 'ts': 'c', 'viewers': 10},
        {'from_id': '1', 'to_id': '99', 'ts': 'd', 'viewers': 10},  # target not in graph
    ])
    b = builder_with()
    b.add_edges_from_raids(db)

    assert b.graph.number_of_edges() == 1
    edge = b.graph['1']['2']
    assert edge['weight'] == 3.0
    assert edge['raids'] == {'1': 2, '2': 1}


def test_team_and_collab_edges(db):
    db.save_team_members([{'team_id': 't', 'team_name': 'T', 'user_id': u} for u in ('1', '2', '3', '99')])
    db.save_collabs([{'a_id': '3', 'b_id': '4', 'ts': 'x', 'source': 'shared_chat'},
                     {'a_id': '4', 'b_id': '3', 'ts': 'y', 'source': 'title_mention'}])
    b = builder_with()
    b.add_edges_from_teams(db)
    b.add_edges_from_collabs(db)

    assert sorted(tuple(sorted(e)) for e in b.graph.edges()) == [('1', '2'), ('1', '3'), ('2', '3'), ('3', '4')]
    assert b.graph['3']['4']['collabs'] == 2 and b.graph['3']['4']['types'] == {'collab'}


def test_real_mode_has_only_relationship_edges(db):
    db.save_raids([{'from_id': '1', 'to_id': '2', 'ts': 'a', 'viewers': 1}])
    b = builder_with()
    b.build_comprehensive_network(mode='real', db=db)

    # All four share game, language, tags and partner status, but only the raid is an edge
    assert [tuple(sorted(e)) for e in b.graph.edges()] == [('1', '2')]
    assert b.graph['1']['2']['types'] == {'raid'}


def test_hybrid_mode_scales_attribute_edges(db):
    db.save_raids([{'from_id': '1', 'to_id': '2', 'ts': 'a', 'viewers': 1}])
    attribute = builder_with()
    attribute.build_comprehensive_network(mode='attribute')
    hybrid = builder_with()
    hybrid.build_comprehensive_network(mode='hybrid', db=db)

    assert set(hybrid.graph.edges()) == set(attribute.graph.edges())
    w = attribute.graph['1']['3']['weight']
    assert hybrid.graph['1']['3']['weight'] == pytest.approx(w * HYBRID_ATTRIBUTE_WEIGHT)
    # The raid is added at full weight on top of the scaled attribute edge
    assert hybrid.graph['1']['2']['weight'] == pytest.approx(attribute.graph['1']['2']['weight'] * HYBRID_ATTRIBUTE_WEIGHT + 1)
    assert 'raid' in hybrid.graph['1']['2']['types']


def test_mode_validation(db):
    with pytest.raises(ValueError):
        builder_with().build_comprehensive_network(mode='nope')
    with pytest.raises(ValueError):
        builder_with().build_comprehensive_network(mode='real')  # needs db
