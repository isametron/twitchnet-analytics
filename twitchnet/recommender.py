from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from twitchnet.config import Config
from twitchnet.similarity_calc import SimilarityCalculator


@dataclass
class CampaignObjectives:
    """Multi-objective campaign optimization parameters"""
    max_budget: float = 100000
    min_reach: int = 100000
    target_engagement_rate: float = 0.05
    brand_safety_threshold: float = 0.7
    diversity_weight: float = 0.3  # Prefer diverse streamers
    roi_weight: float = 0.5
    reach_weight: float = 0.2

@dataclass
class BudgetAllocation:
    """Budget allocation result"""
    streamer_id: str
    display_name: str
    allocated_budget: float
    estimated_reach: int
    estimated_engagement: float
    roi_score: float

class StreamerRecommender:
    """Main recommendation engine for matching companies with streamers"""

    def __init__(self, streamers_df: pd.DataFrame,
                 centrality_scores: Dict,
                 similarity_calculator: SimilarityCalculator):
        self.streamers_df = streamers_df
        self.centrality_scores = centrality_scores
        self.similarity_calculator = similarity_calculator

    def calculate_composite_score(self, streamer_id: str,
                                  content_similarity: float,
                                  engagement_score: float = None) -> float:
        """
        Calculate composite score combining multiple factors

        Args:
            streamer_id: Streamer identifier
            content_similarity: Content similarity score
            engagement_score: Optional engagement metric

        Returns:
            Composite score
        """
        # Content similarity
        content_component = content_similarity * Config.CONTENT_SIMILARITY_WEIGHT

        # Network centrality (PageRank)
        centrality_component = (
            self.centrality_scores.get('pagerank', {}).get(streamer_id, 0) *
            Config.CENTRALITY_WEIGHT
        )

        # Engagement (simplified - live viewers as a share of followers)
        if engagement_score is None:
            engagement_score = 0.0
            streamer_data = self.streamers_df[self.streamers_df['user_id'] == streamer_id]
            if not streamer_data.empty and 'viewer_count' in streamer_data:
                viewer_count = streamer_data['viewer_count'].fillna(0).values[0]
                follower_count = streamer_data['follower_count'].values[0]
                engagement_score = viewer_count / max(follower_count, 1)
                engagement_score = min(engagement_score / 0.1, 1.0)  # 10% of followers watching live = max

        engagement_component = engagement_score * Config.ENGAGEMENT_WEIGHT

        # Audience fit (placeholder - would need demographic data)
        audience_component = 0.5 * Config.AUDIENCE_FIT_WEIGHT

        composite_score = (content_component + centrality_component +
                          engagement_component + audience_component)

        return composite_score

    def recommend_streamers(self, company_feature: np.ndarray,
                           company_profile: Dict,
                           top_n: int = None) -> pd.DataFrame:
        """
        Generate streamer recommendations for a company

        Args:
            company_feature: Company feature vector
            company_profile: Company profile dictionary
            top_n: Number of recommendations (default from config)

        Returns:
            DataFrame with recommendations
        """
        if top_n is None:
            top_n = Config.TOP_N_RECOMMENDATIONS

        # Calculate content similarity
        similarities = self.similarity_calculator.calculate_similarity(company_feature)

        # Filter by hard criteria
        filtered_similarities = self.similarity_calculator.filter_by_criteria(
            similarities, self.streamers_df, company_profile
        )

        # Calculate composite scores
        recommendations = []
        for streamer_id, sim_score in filtered_similarities.items():
            composite_score = self.calculate_composite_score(streamer_id, sim_score)

            streamer_data = self.streamers_df[self.streamers_df['user_id'] == streamer_id]
            if not streamer_data.empty:
                recommendations.append({
                    'user_id': streamer_id,
                    'username': streamer_data['username'].values[0],
                    'display_name': streamer_data['display_name'].values[0],
                    'game_name': streamer_data['game_name'].values[0],
                    'follower_count': streamer_data['follower_count'].values[0],
                    'content_similarity': sim_score,
                    'pagerank_centrality': self.centrality_scores.get('pagerank', {}).get(streamer_id, 0),
                    'composite_score': composite_score
                })

        # Create DataFrame and sort
        recommendations_df = pd.DataFrame(recommendations)
        recommendations_df = recommendations_df.sort_values('composite_score', ascending=False)

        return recommendations_df.head(top_n)

    def optimize_multi_objective(self, company_feature: np.ndarray,
                                company_profile: Dict,
                                objectives: CampaignObjectives,
                                candidate_pool_size: int = 50) -> List[Dict]:
        """
        Multi-objective optimization for streamer selection

        Args:
            company_feature: Company feature vector
            company_profile: Company profile dictionary
            objectives: Campaign objectives and constraints
            candidate_pool_size: Size of initial candidate pool

        Returns:
            Optimized list of streamer recommendations
        """
        # Get initial candidate pool
        candidates = self.recommend_streamers(company_feature, company_profile, candidate_pool_size)

        optimized_recommendations = []

        for _, streamer in candidates.iterrows():
            # Calculate multi-objective score
            reach_score = np.log1p(streamer['follower_count']) / 20  # Normalized
            engagement_score = streamer.get('composite_score', 0)

            # Brand safety (based on partner status and follower count)
            streamer_data = self.streamers_df[self.streamers_df['user_id'] == streamer['user_id']]
            brand_safety = 0.8 if streamer_data['is_partner'].values[0] else 0.5

            # ROI estimation (higher engagement + lower cost per follower = better ROI)
            cost_estimate = streamer['follower_count'] * 0.01  # $0.01 per follower estimate
            roi_score = engagement_score / np.log1p(cost_estimate)

            # Multi-objective score
            mo_score = (
                objectives.reach_weight * reach_score +
                objectives.roi_weight * roi_score +
                objectives.diversity_weight * streamer['content_similarity']
            )

            # Filter by brand safety threshold
            if brand_safety >= objectives.brand_safety_threshold:
                optimized_recommendations.append({
                    'user_id': streamer['user_id'],
                    'display_name': streamer['display_name'],
                    'username': streamer['username'],
                    'game_name': streamer['game_name'],
                    'follower_count': streamer['follower_count'],
                    'multi_objective_score': mo_score,
                    'estimated_roi': roi_score,
                    'brand_safety_score': brand_safety,
                    'reach_score': reach_score,
                    'engagement_score': engagement_score
                })

        # Sort by multi-objective score
        optimized_recommendations.sort(key=lambda x: x['multi_objective_score'], reverse=True)

        return optimized_recommendations

    def allocate_budget(self, streamers: List[Dict],
                       total_budget: float,
                       allocation_strategy: str = 'balanced') -> List[BudgetAllocation]:
        """
        Optimally allocate budget across streamers

        Args:
            streamers: List of recommended streamers
            total_budget: Total campaign budget
            allocation_strategy: 'balanced', 'top_heavy', or 'roi_optimized'

        Returns:
            List of budget allocations
        """
        allocations = []

        if allocation_strategy == 'top_heavy':
            # 60% to top 3, 40% to rest
            weights = [0.3, 0.2, 0.1] + [0.4 / max(len(streamers) - 3, 1)] * (len(streamers) - 3)
        elif allocation_strategy == 'roi_optimized':
            # Weight by ROI scores
            roi_scores = [s.get('estimated_roi', 1) for s in streamers]
            total_roi = sum(roi_scores)
            weights = [roi / total_roi for roi in roi_scores]
        else:  # balanced
            weights = [1 / len(streamers)] * len(streamers)

        for streamer, weight in zip(streamers, weights[:len(streamers)]):
            allocated = total_budget * weight
            estimated_reach = int(streamer['follower_count'] * 0.3)  # 30% reach rate
            estimated_engagement = estimated_reach * 0.05  # 5% engagement

            allocations.append(BudgetAllocation(
                streamer_id=streamer['user_id'],
                display_name=streamer['display_name'],
                allocated_budget=allocated,
                estimated_reach=estimated_reach,
                estimated_engagement=estimated_engagement,
                roi_score=streamer.get('estimated_roi', 0.5)
            ))

        return allocations

    def simulate_campaign(self, allocations: List[BudgetAllocation],
                         num_simulations: int = 1000) -> Dict:
        """
        Monte Carlo simulation of campaign performance

        Args:
            allocations: Budget allocations
            num_simulations: Number of simulation runs

        Returns:
            Dictionary with simulation results
        """
        results = {
            'total_reach': [],
            'total_engagement': [],
            'total_roi': []
        }

        for _ in range(num_simulations):
            sim_reach = 0
            sim_engagement = 0
            total_cost = sum(a.allocated_budget for a in allocations)

            for allocation in allocations:
                # Add variance to estimates (±20%)
                variance = np.random.uniform(0.8, 1.2)
                sim_reach += int(allocation.estimated_reach * variance)
                sim_engagement += allocation.estimated_engagement * variance

            sim_roi = (sim_engagement * 100) / total_cost if total_cost > 0 else 0

            results['total_reach'].append(sim_reach)
            results['total_engagement'].append(sim_engagement)
            results['total_roi'].append(sim_roi)

        return {
            'mean_reach': np.mean(results['total_reach']),
            'std_reach': np.std(results['total_reach']),
            'mean_engagement': np.mean(results['total_engagement']),
            'std_engagement': np.std(results['total_engagement']),
            'mean_roi': np.mean(results['total_roi']),
            'confidence_95': {
                'reach_lower': np.percentile(results['total_reach'], 2.5),
                'reach_upper': np.percentile(results['total_reach'], 97.5),
                'roi_lower': np.percentile(results['total_roi'], 2.5),
                'roi_upper': np.percentile(results['total_roi'], 97.5)
            },
            'distributions': results
        }

    def compare_strategies(self, streamers: List[Dict], budget: float) -> pd.DataFrame:
        """
        Compare different budget allocation strategies

        Args:
            streamers: List of recommended streamers
            budget: Total budget

        Returns:
            DataFrame comparing strategies
        """
        strategies = ['balanced', 'top_heavy', 'roi_optimized']
        comparisons = []

        for strategy in strategies:
            allocations = self.allocate_budget(streamers[:10], budget, strategy)
            simulation = self.simulate_campaign(allocations, num_simulations=500)

            comparisons.append({
                'strategy': strategy,
                'expected_reach': int(simulation['mean_reach']),
                'reach_std': int(simulation['std_reach']),
                'expected_roi': round(simulation['mean_roi'], 2),
                'roi_confidence_lower': round(simulation['confidence_95']['roi_lower'], 2),
                'roi_confidence_upper': round(simulation['confidence_95']['roi_upper'], 2),
                'total_budget': budget
            })

        return pd.DataFrame(comparisons)

    def analyze_competitors(self, competitor_streamers: List[str]) -> Dict:
        """
        Analyze competitor streamer partnerships

        Args:
            competitor_streamers: List of streamer IDs used by competitors

        Returns:
            Analysis dictionary with gaps and opportunities
        """
        competitor_data = self.streamers_df[
            self.streamers_df['user_id'].isin(competitor_streamers)
        ]

        # Analyze competitor choices
        avg_followers = competitor_data['follower_count'].mean()
        games_used = competitor_data['game_name'].value_counts().to_dict()

        # Find gaps (high potential streamers not used by competitors)
        all_streamers = self.streamers_df[~self.streamers_df['user_id'].isin(competitor_streamers)]

        # Identify underutilized high-value streamers
        gaps = all_streamers[
            (all_streamers['follower_count'] > avg_followers * 0.5) &
            (all_streamers['follower_count'] < avg_followers * 1.5)
        ].copy()

        # Add opportunity score
        gaps['opportunity_score'] = (
            gaps['follower_count'] / avg_followers *
            self.centrality_scores.get('pagerank', {}).get(gaps['user_id'].values[0], 0.5)
        )

        return {
            'competitor_avg_followers': avg_followers,
            'competitor_games': games_used,
            'num_competitor_streamers': len(competitor_data),
            'gap_opportunities': gaps.nlargest(20, 'opportunity_score')[[
                'display_name', 'game_name', 'follower_count', 'opportunity_score'
            ]].to_dict('records'),
            'untapped_games': list(set(all_streamers['game_name']) - set(games_used.keys()))
        }

    def generate_match_report(self, recommendations_df: pd.DataFrame,
                             company_name: str) -> str:
        """
        Generate a detailed match report

        Args:
            recommendations_df: DataFrame with recommendations
            company_name: Company name

        Returns:
            Formatted report string
        """
        report = f"\n{'='*70}\n"
        report += f"STREAMER RECOMMENDATIONS FOR: {company_name}\n"
        report += f"{'='*70}\n\n"

        for idx, row in recommendations_df.iterrows():
            report += f"{idx+1}. {row['display_name']} (@{row['username']})\n"
            report += f"   Game: {row['game_name']}\n"
            report += f"   Followers: {row['follower_count']:,}\n"
            report += f"   Match Score: {row['composite_score']:.3f}\n"
            report += f"   - Content Similarity: {row['content_similarity']:.3f}\n"
            report += f"   - Network Influence: {row['pagerank_centrality']:.3f}\n"
            report += "\n"

        return report


if __name__ == "__main__":
    print("Recommender module - use main.py to run full pipeline")
