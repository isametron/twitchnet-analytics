import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List

class FeatureExtractor:
    """Extract and encode features from streamer data"""
    
    def __init__(self):
        self.mlb_games = MultiLabelBinarizer()
        self.mlb_tags = MultiLabelBinarizer()
        self.scaler = StandardScaler()
        self.is_fitted = False
    
    def extract_streamer_features(self, streamers_df: pd.DataFrame) -> np.ndarray:
        """
        Extract feature matrix from streamer data
        
        Args:
            streamers_df: DataFrame with streamer information
        
        Returns:
            Feature matrix
        """
        features = []
        
        # Game categories (one-hot encoded)
        games = streamers_df['game_name'].fillna('Unknown').apply(lambda x: [x]).tolist()
        game_features = self.mlb_games.fit_transform(games)
        features.append(game_features)
        
        # Tags (multi-hot encoded); streamers loaded from the database have no tags column
        if 'tags' in streamers_df.columns:
            tags = streamers_df['tags'].apply(lambda x: x if isinstance(x, list) else []).tolist()
        else:
            tags = [[] for _ in range(len(streamers_df))]
        tag_features = self.mlb_tags.fit_transform(tags)
        features.append(tag_features)
        
        # Numerical features (normalized)
        numerical_cols = ['follower_count', 'viewer_count']
        numerical_features = streamers_df.reindex(columns=numerical_cols).fillna(0).values
        numerical_features = self.scaler.fit_transform(numerical_features)
        features.append(numerical_features)
        
        # Partner status (binary)
        partner_features = streamers_df['is_partner'].fillna(False).astype(int).values.reshape(-1, 1)
        features.append(partner_features)
        
        # Concatenate all features
        feature_matrix = np.hstack(features)
        self.is_fitted = True
        
        return feature_matrix
    
    def extract_company_features(self, company_profile: Dict) -> np.ndarray:
        """
        Extract feature vector from company profile
        
        Args:
            company_profile: Company profile dictionary
        
        Returns:
            Feature vector matching streamer feature dimensions
        """
        if not self.is_fitted:
            raise ValueError("Extractor must be fitted on streamer data first")
        
        # Game categories
        target_games = company_profile.get('games', [])
        game_features = self.mlb_games.transform([target_games])[0]
        
        # Tags (assume empty for companies)
        tag_features = np.zeros(len(self.mlb_tags.classes_))
        
        # Follower range (use midpoint)
        follower_range = company_profile.get('follower_range', (0, 1000000))
        follower_midpoint = (follower_range[0] + follower_range[1]) / 2
        
        # Normalize using fitted scaler
        numerical_features = self.scaler.transform([[follower_midpoint, follower_midpoint]])[0]
        
        # Partner preference (neutral)
        partner_features = np.array([0.5])
        
        # Concatenate
        feature_vector = np.concatenate([
            game_features,
            tag_features,
            numerical_features,
            partner_features
        ])
        
        return feature_vector


class SimilarityCalculator:
    """Calculate similarity between companies and streamers"""
    
    def __init__(self, streamer_features: np.ndarray, streamer_ids: List[str]):
        self.streamer_features = streamer_features
        self.streamer_ids = streamer_ids
    
    def calculate_similarity(self, company_feature: np.ndarray) -> Dict[str, float]:
        """
        Calculate cosine similarity between company and all streamers
        
        Args:
            company_feature: Company feature vector
        
        Returns:
            Dictionary mapping streamer_id to similarity score
        """
        # Reshape company feature
        company_feature = company_feature.reshape(1, -1)
        
        # Calculate cosine similarity
        similarities = cosine_similarity(company_feature, self.streamer_features)[0]
        
        # Create mapping
        similarity_dict = {
            streamer_id: float(sim)
            for streamer_id, sim in zip(self.streamer_ids, similarities)
        }
        
        return similarity_dict
    
    def filter_by_criteria(self, similarities: Dict[str, float], 
                          streamers_df: pd.DataFrame,
                          company_profile: Dict) -> Dict[str, float]:
        """
        Filter streamers based on hard criteria
        
        Args:
            similarities: Similarity scores
            streamers_df: DataFrame with streamer data
            company_profile: Company requirements
        
        Returns:
            Filtered similarity dictionary
        """
        filtered = {}
        
        follower_range = company_profile.get('follower_range', (0, float('inf')))
        target_languages = company_profile.get('languages', [])
        
        for streamer_id, sim_score in similarities.items():
            # Get streamer data
            streamer = streamers_df[streamers_df['user_id'] == streamer_id]
            
            if streamer.empty:
                continue
            
            follower_count = streamer['follower_count'].values[0]
            language = streamer['language'].values[0]
            
            # Check criteria
            if follower_range[0] <= follower_count <= follower_range[1]:
                if not target_languages or language in target_languages:
                    filtered[streamer_id] = sim_score
        
        return filtered


if __name__ == "__main__":
    # Example usage
    from config import Config
    import json
    
    # Load streamer data
    with open(f"{Config.RAW_DATA_DIR}/streamers.json", 'r') as f:
        streamers = json.load(f)
    
    streamers_df = pd.DataFrame(streamers)
    
    # Extract features
    extractor = FeatureExtractor()
    streamer_features = extractor.extract_streamer_features(streamers_df)
    
    print(f"Extracted features with shape: {streamer_features.shape}")
    