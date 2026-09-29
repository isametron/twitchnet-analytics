"""
Advanced scoring algorithms for streamer-company matching
Provides multiple scoring methods for different recommendation strategies
"""

from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class AdvancedScorer:
    """Advanced scoring engine for generating confidence and compatibility scores"""

    def __init__(self):
        self.scaler = MinMaxScaler()

    def calculate_engagement_score(self, follower_count: int,
                                  avg_viewers: float = None,
                                  is_partner: bool = False) -> float:
        """
        Calculate engagement score based on follower count and partnership status

        Args:
            follower_count: Number of followers
            avg_viewers: Average concurrent viewers
            is_partner: Whether streamer is a Twitch partner

        Returns:
            Engagement score (0-1)
        """
        partner_bonus = 0.1 if is_partner else 0.0

        # Apply logarithmic scaling to avoid extremes
        engagement = (np.log1p(follower_count) / np.log1p(1000000)) * 0.9 + partner_bonus
        return min(engagement, 1.0)

    def calculate_niche_alignment_score(self, company_games: List[str],
                                       streamer_game: str,
                                       game_popularity: Dict[str, int] = None) -> float:
        """
        Calculate how well a streamer's game aligns with company target games

        Args:
            company_games: Target games for the company
            streamer_game: Primary game streamed by this streamer
            game_popularity: Optional popularity scores for games

        Returns:
            Alignment score (0-1)
        """
        if not company_games:
            return 0.5  # Neutral if no games specified

        # Direct match
        if streamer_game in company_games:
            return 1.0

        # Fuzzy match (similar game names)
        for game in company_games:
            if game.lower() == streamer_game.lower():
                return 0.95
            if any(word in game.lower() for word in streamer_game.lower().split()):
                return 0.7

        # No match
        return 0.2

    def calculate_audience_size_fit(self, follower_count: int,
                                   min_followers: int,
                                   max_followers: int,
                                   strict: bool = False) -> float:
        """
        Calculate how well follower count fits within company requirements

        Args:
            follower_count: Streamer's follower count
            min_followers: Minimum required followers
            max_followers: Maximum desired followers
            strict: If True, return 0 for out-of-range values

        Returns:
            Fit score (0-1)
        """
        if follower_count < min_followers:
            return 0.0 if strict else 0.3 + (follower_count / min_followers) * 0.2
        elif follower_count > max_followers:
            return 0.0 if strict else 0.5 + (1 - (follower_count / (max_followers * 2))) * 0.5
        else:
            # Perfect fit within range
            return 1.0

    def calculate_language_compatibility(self, company_languages: List[str],
                                        streamer_language: str) -> float:
        """
        Calculate language compatibility score

        Args:
            company_languages: Target languages
            streamer_language: Streamer's primary language

        Returns:
            Compatibility score (0-1)
        """
        if not company_languages:
            return 0.5

        if streamer_language in company_languages:
            return 1.0

        # English is often compatible with others
        if streamer_language == 'en' or 'en' in company_languages:
            return 0.8

        return 0.1

    def calculate_composite_confidence(self, engagement_score: float,
                                      alignment_score: float,
                                      audience_fit: float,
                                      language_compat: float,
                                      network_influence: float = 0.5,
                                      weights: Dict[str, float] = None) -> float:
        """
        Calculate weighted composite confidence score

        Args:
            engagement_score: Engagement metric (0-1)
            alignment_score: Game/niche alignment (0-1)
            audience_fit: Audience size fit (0-1)
            language_compat: Language compatibility (0-1)
            network_influence: Network centrality influence (0-1)
            weights: Custom weights for each metric

        Returns:
            Composite confidence score (0-1)
        """
        if weights is None:
            weights = {
                'engagement': 0.25,
                'alignment': 0.35,
                'audience': 0.20,
                'language': 0.10,
                'network': 0.10
            }

        scores = np.array([
            engagement_score,
            alignment_score,
            audience_fit,
            language_compat,
            network_influence
        ])

        weight_values = np.array([
            weights.get('engagement', 0.25),
            weights.get('alignment', 0.35),
            weights.get('audience', 0.20),
            weights.get('language', 0.10),
            weights.get('network', 0.10)
        ])

        # Normalize weights
        weight_values = weight_values / weight_values.sum()

        composite = np.average(scores, weights=weight_values)
        return float(np.clip(composite, 0, 1))

    def calculate_risk_score(self, follower_count: int,
                            is_partner: bool,
                            mature_content: bool = False) -> float:
        """
        Calculate risk score for partnership (0 = low risk, 1 = high risk)

        Args:
            follower_count: Streamer's follower count
            is_partner: Partnership status
            mature_content: Whether stream contains mature content

        Returns:
            Risk score (0-1) where 0 is best
        """
        risk = 0.0

        # Very small or very large audiences increase risk
        if follower_count < 1000:
            risk += 0.3
        elif follower_count > 5000000:
            risk += 0.2

        # Non-partners have slightly higher risk
        if not is_partner:
            risk += 0.15

        # Mature content increases risk
        if mature_content:
            risk += 0.2

        return min(risk, 1.0)

    def rank_recommendations(self, recommendations: pd.DataFrame,
                            confidence_column: str = 'composite_score',
                            risk_column: str = 'risk_score',
                            adjust_for_risk: bool = True,
                            top_n: int = None) -> pd.DataFrame:
        """
        Rank recommendations based on confidence and risk

        Args:
            recommendations: DataFrame with recommendation scores
            confidence_column: Column name for confidence scores
            risk_column: Column name for risk scores
            adjust_for_risk: Whether to adjust confidence by risk
            top_n: Return only top N recommendations

        Returns:
            Ranked DataFrame
        """
        ranked = recommendations.copy()

        if adjust_for_risk and risk_column in ranked.columns:
            ranked['adjusted_score'] = ranked[confidence_column] * (1 - ranked[risk_column])
            ranked = ranked.sort_values('adjusted_score', ascending=False)
        else:
            ranked = ranked.sort_values(confidence_column, ascending=False)

        if top_n:
            ranked = ranked.head(top_n)

        ranked['rank'] = range(1, len(ranked) + 1)
        return ranked

    def generate_score_explanation(self, row: pd.Series) -> str:
        """
        Generate human-readable explanation for a score

        Args:
            row: DataFrame row with score components

        Returns:
            Explanation string
        """
        score = row.get('composite_score', 0)

        if score >= 0.9:
            return "Excellent match - highly recommended"
        elif score >= 0.8:
            return "Very good match - strongly recommended"
        elif score >= 0.7:
            return "Good match - recommended"
        elif score >= 0.6:
            return "Fair match - consider for niche fit"
        elif score >= 0.5:
            return "Moderate match - potential backup option"
        else:
            return "Weak match - not recommended"


class ScoreBatchProcessor:
    """Process multiple scores efficiently in batches"""

    def __init__(self, scorer: AdvancedScorer):
        self.scorer = scorer

    def process_batch(self, streamers_df: pd.DataFrame,
                     company_profile: Dict) -> pd.DataFrame:
        """
        Process a batch of streamers with all scoring metrics

        Args:
            streamers_df: DataFrame with streamer data
            company_profile: Company profile dictionary

        Returns:
            DataFrame with all scoring metrics
        """
        results = []

        for idx, row in streamers_df.iterrows():
            scores = {
                'user_id': row.get('user_id', f'user_{idx}'),
                'display_name': row.get('display_name', 'Unknown'),
                'follower_count': row.get('follower_count', 0),
                'game_name': row.get('game_name', 'Unknown'),
                'is_partner': row.get('is_partner', False)
            }

            # Calculate individual scores
            scores['engagement_score'] = self.scorer.calculate_engagement_score(
                scores['follower_count'],
                is_partner=scores['is_partner']
            )

            scores['niche_alignment'] = self.scorer.calculate_niche_alignment_score(
                company_profile.get('games', []),
                scores['game_name']
            )

            scores['audience_fit'] = self.scorer.calculate_audience_size_fit(
                scores['follower_count'],
                company_profile.get('min_followers', 1000),
                company_profile.get('max_followers', 1000000)
            )

            scores['language_compat'] = self.scorer.calculate_language_compatibility(
                company_profile.get('languages', ['en']),
                row.get('language', 'en')
            )

            scores['risk_score'] = self.scorer.calculate_risk_score(
                scores['follower_count'],
                scores['is_partner']
            )

            results.append(scores)

        result_df = pd.DataFrame(results)

        # Calculate composite scores
        result_df['composite_score'] = result_df.apply(
            lambda r: self.scorer.calculate_composite_confidence(
                r['engagement_score'],
                r['niche_alignment'],
                r['audience_fit'],
                r['language_compat']
            ),
            axis=1
        )

        return result_df


if __name__ == "__main__":
    # Example usage
    scorer = AdvancedScorer()

    # Test scoring
    engagement = scorer.calculate_engagement_score(50000, is_partner=True)
    alignment = scorer.calculate_niche_alignment_score(
        ['League of Legends', 'Valorant'],
        'League of Legends'
    )
    audience = scorer.calculate_audience_size_fit(50000, 10000, 100000)
    language = scorer.calculate_language_compatibility(['en', 'es'], 'en')

    composite = scorer.calculate_composite_confidence(
        engagement, alignment, audience, language
    )

    print(f"Engagement: {engagement:.3f}")
    print(f"Alignment: {alignment:.3f}")
    print(f"Audience Fit: {audience:.3f}")
    print(f"Language: {language:.3f}")
    print(f"Composite: {composite:.3f}")
    print(f"Explanation: {scorer.generate_score_explanation({'composite_score': composite})}")
