import argparse
import asyncio
import pandas as pd
import json
from config import Config
from twitch_api import TwitchDataCollector
from company_profiles import CompanyProfileManager
from database import DatabaseManager
from graph_builder import NETWORK_MODES, StreamerNetworkBuilder
from centrality import CentralityAnalyzer
from community_detection import CommunityDetector
from similarity_calc import FeatureExtractor, SimilarityCalculator
from recommender import StreamerRecommender

async def collect_data():
    """Step 1: Collect Twitch data"""
    print("\n" + "="*70)
    print("STEP 1: COLLECTING TWITCH DATA")
    print("="*70)
    
    collector = TwitchDataCollector(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    await collector.initialize()
    
    # Collect streamers from multiple game categories
    all_streamers = []
    game_categories = ['League of Legends', 'Valorant', 'Fortnite', 'Minecraft', 'Just Chatting']
    
    for game in game_categories:
        streamers = await collector.get_top_streamers(game_name=game, max_results=20)
        all_streamers.extend(streamers)
        print(f"Collected {len(streamers)} streamers from {game}")
    
    collector.save_data(all_streamers, 'streamers.json')
    await collector.close()
    
    return all_streamers

def build_network(streamers, mode='attribute'):
    """Step 2: Build network graph"""
    print("\n" + "="*70)
    print("STEP 2: BUILDING NETWORK GRAPH")
    print("="*70)

    builder = StreamerNetworkBuilder()
    builder.add_streamers(streamers)

    if mode == 'attribute':
        # Add all attribute connection types
        builder.add_edges_from_shared_games()
        builder.add_edges_from_tags(similarity_threshold=0.2)
        builder.add_edges_from_language(same_language_weight=0.5)
        builder.add_edges_from_partner_status(partner_weight=0.8)
        builder.add_edges_from_viewer_tier(tier_threshold=50000)
    else:
        # Relationship data comes from tracker.py
        builder.build_comprehensive_network(mode=mode, db=DatabaseManager())
    
    stats = builder.get_graph_stats()
    print("\nNetwork Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    builder.save_graph()
    builder.export_to_csv()
    
    return builder

def analyze_network(builder):
    """Step 3: Analyze network and detect communities"""
    print("\n" + "="*70)
    print("STEP 3: NETWORK ANALYSIS")
    print("="*70)
    
    # Calculate centrality
    analyzer = CentralityAnalyzer(builder.graph)
    analyzer.calculate_all_centralities()
    analyzer.save_centrality_scores()
    
    print("\nTop 5 Influencers (PageRank):")
    top_influencers = analyzer.get_top_influencers('pagerank', 5)
    for i, (node, score) in enumerate(top_influencers, 1):
        node_data = builder.graph.nodes[node]
        print(f"  {i}. {node_data.get('display_name', node)} - {score:.4f}")
    
    # Detect communities
    detector = CommunityDetector(builder.graph)
    communities = detector.detect_communities_louvain()
    
    stats_df = detector.get_community_stats()
    print(f"\nDetected {len(communities)} communities")
    print("\nTop 5 Communities:")
    print(stats_df.head())
    
    detector.export_communities()
    
    return analyzer, detector

def generate_recommendations(streamers, centrality_scores):
    """Step 4: Generate recommendations"""
    print("\n" + "="*70)
    print("STEP 4: GENERATING RECOMMENDATIONS")
    print("="*70)
    
    # Prepare data
    streamers_df = pd.DataFrame(streamers)
    
    # Extract features
    extractor = FeatureExtractor()
    streamer_features = extractor.extract_streamer_features(streamers_df)
    
    # Initialize similarity calculator
    similarity_calc = SimilarityCalculator(
        streamer_features,
        streamers_df['user_id'].tolist()
    )
    
    # Initialize recommender
    recommender = StreamerRecommender(
        streamers_df,
        centrality_scores,
        similarity_calc
    )
    
    # Create company profiles
    profile_manager = CompanyProfileManager()
    profiles = profile_manager.create_sample_profiles()
    
    # Generate recommendations for each company
    all_recommendations = {}
    
    for company_id, profile in profiles.items():
        print(f"\nGenerating recommendations for {profile.name}...")
        
        company_feature = extractor.extract_company_features(profile.to_feature_vector())
        recommendations = recommender.recommend_streamers(
            company_feature,
            profile.to_feature_vector(),
            top_n=5
        )
        
        all_recommendations[company_id] = recommendations
        
        # Print report
        report = recommender.generate_match_report(recommendations, profile.name)
        print(report)
        
        # Save to CSV
        recommendations.to_csv(
            f"{Config.PROCESSED_DATA_DIR}/recommendations_{company_id}.csv",
            index=False
        )
    
    return all_recommendations

async def main(mode='attribute'):
    """Main execution pipeline"""
    print("\n" + "="*70)
    print("TWITCH STREAMER - COMPANY MATCHING SYSTEM")
    print("Social Network Analysis Project")
    print("="*70)
    
    Config.make_console_safe()

    # Create directories
    Config.create_directories()
    
    # Check if data already exists
    try:
        with open(f"{Config.RAW_DATA_DIR}/streamers.json", 'r', encoding='utf-8') as f:
            streamers = json.load(f)
        print("\nUsing existing streamer data...")
    except FileNotFoundError:
        print("\nNo existing data found. Collecting new data...")
        streamers = await collect_data()
    
    # Build network
    builder = build_network(streamers, mode)
    
    # Analyze network
    analyzer, detector = analyze_network(builder)
    
    # Generate recommendations
    generate_recommendations(streamers, analyzer.centrality_scores)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE!")
    print("="*70)
    print(f"\nResults saved to: {Config.PROCESSED_DATA_DIR}/")
    print("- centrality_scores.csv")
    print("- communities.csv")
    print("- recommendations_*.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full collect -> network -> recommend pipeline")
    parser.add_argument('--mode', choices=NETWORK_MODES, default='attribute',
                        help="network edges: shared attributes, observed relationships (real), or both (hybrid)")
    asyncio.run(main(parser.parse_args().mode))
