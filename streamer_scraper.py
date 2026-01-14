"""
Data scraping and cleaning utilities for Twitch streamer data
Handles data validation, cleaning, and normalization
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import re
from urllib.parse import quote_plus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamerDataCleaner:
    """Clean and validate streamer data"""
    
    def __init__(self):
        self.cleaning_log = []
    
    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Comprehensive data cleaning pipeline
        
        Args:
            df: Raw streamer DataFrame
        
        Returns:
            Cleaned DataFrame
        """
        df = df.copy()
        
        # Remove duplicates
        df, dup_count = self._remove_duplicates(df)
        self.cleaning_log.append(f"Removed {dup_count} duplicate entries")
        
        # Clean numeric columns
        df, num_changes = self._clean_numeric_columns(df)
        self.cleaning_log.append(f"Cleaned {num_changes} numeric values")
        
        # Clean string columns
        df, str_changes = self._clean_string_columns(df)
        self.cleaning_log.append(f"Cleaned {str_changes} string values")
        
        # Normalize data
        df, norm_changes = self._normalize_values(df)
        self.cleaning_log.append(f"Normalized {norm_changes} values")
        
        # Remove rows with critical missing values
        df, removed_count = self._handle_missing_values(df)
        self.cleaning_log.append(f"Removed {removed_count} rows with missing critical data")
        
        # Validate and fix data types
        df = self._validate_data_types(df)
        self.cleaning_log.append("Validated and corrected data types")
        
        return df
    
    def _remove_duplicates(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Remove duplicate streamers by user_id"""
        if len(df) == 0 or 'user_id' not in df.columns:
            return df, 0
        
        initial_count = len(df)
        df = df.drop_duplicates(subset=['user_id'], keep='first')
        removed = initial_count - len(df)
        
        return df, removed
    
    def _clean_numeric_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Clean numeric columns"""
        changes = 0
        numeric_cols = ['follower_count', 'view_count']
        
        for col in numeric_cols:
            if col in df.columns:
                # Replace negative values with 0
                mask = df[col] < 0
                if mask.any():
                    df.loc[mask, col] = 0
                    changes += mask.sum()
                
                # Replace inf with 0
                df[col] = df[col].replace([np.inf, -np.inf], 0)
        
        return df, changes
    
    def _clean_string_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Clean string columns"""
        changes = 0
        string_cols = ['display_name', 'username', 'game_name', 'language', 'description']
        
        for col in string_cols:
            if col in df.columns:
                # Strip whitespace
                initial_null = df[col].isnull().sum()
                df[col] = df[col].fillna('Unknown').astype(str).str.strip()
                
                # Remove leading/trailing quotes
                df[col] = df[col].str.replace(r'^["\']|["\']$', '', regex=True)
                
                # Normalize unicode
                df[col] = df[col].apply(lambda x: x.encode('utf-8', 'ignore').decode('utf-8'))
                
                changes += df[col].str.len().sum()
        
        return df, changes
    
    def _normalize_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Normalize common values"""
        changes = 0
        
        # Normalize boolean columns
        bool_cols = ['is_partner', 'mature_content']
        for col in bool_cols:
            if col in df.columns:
                mask = ~df[col].isin([True, False])
                df.loc[mask, col] = df.loc[mask, col].astype(str).str.lower().isin(['true', '1', 'yes'])
                changes += mask.sum()
        
        # Normalize language codes to lowercase
        if 'language' in df.columns:
            mask = df['language'].str.len() > 2
            df.loc[mask, 'language'] = df.loc[mask, 'language'].str[:2].str.lower()
            changes += mask.sum()
        
        # Fix common game name variations
        game_fixes = {
            'LOL': 'League of Legends',
            'CSGO': 'CS:GO',
            'CS:GO': 'CS:GO',
            'COD': 'Call of Duty',
            'WoW': 'World of Warcraft',
            'OW': 'Overwatch',
            'OW2': 'Overwatch 2'
        }
        
        if 'game_name' in df.columns:
            for old, new in game_fixes.items():
                mask = df['game_name'].str.upper() == old.upper()
                df.loc[mask, 'game_name'] = new
                changes += mask.sum()
        
        return df, changes
    
    def _handle_missing_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Handle missing values"""
        initial_count = len(df)
        
        # Drop rows missing critical columns
        critical_cols = ['user_id', 'display_name', 'follower_count']
        df = df.dropna(subset=critical_cols)
        
        # Fill optional columns with defaults
        optional_fills = {
            'game_name': 'Unknown',
            'language': 'en',
            'is_partner': False,
            'description': '',
            'view_count': 0
        }
        
        for col, fill_value in optional_fills.items():
            if col in df.columns:
                df[col] = df[col].fillna(fill_value)
        
        removed = initial_count - len(df)
        return df, removed
    
    def _validate_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure correct data types"""
        type_map = {
            'user_id': 'object',
            'display_name': 'object',
            'username': 'object',
            'game_name': 'object',
            'language': 'object',
            'follower_count': 'int64',
            'view_count': 'int64',
            'is_partner': 'bool',
            'mature_content': 'bool',
            'description': 'object',
            'profile_image_url': 'object',
            'created_at': 'object',
            'updated_at': 'object'
        }
        
        for col, dtype in type_map.items():
            if col in df.columns:
                try:
                    if dtype == 'int64':
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int64')
                    elif dtype == 'bool':
                        df[col] = df[col].astype(bool)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    logger.warning(f"Could not convert {col} to {dtype}: {str(e)}")
        
        return df
    
    def validate_row(self, row: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single streamer record
        
        Args:
            row: Dictionary with streamer data
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Check required fields
        required_fields = ['user_id', 'display_name', 'follower_count']
        for field in required_fields:
            if field not in row or row[field] is None or row[field] == '':
                errors.append(f"Missing required field: {field}")
        
        # Validate follower count
        try:
            followers = int(row.get('follower_count', -1))
            if followers < 0:
                errors.append("Invalid follower count (negative)")
        except (ValueError, TypeError):
            errors.append("Invalid follower count (not numeric)")
        
        # Validate user_id
        user_id = row.get('user_id', '')
        if not isinstance(user_id, (str, int)) or (isinstance(user_id, str) and len(user_id) == 0):
            errors.append("Invalid user_id")
        
        # Validate language code
        language = row.get('language', 'en')
        if isinstance(language, str) and len(language) > 5:
            errors.append("Invalid language code")
        
        # Validate display name
        display_name = row.get('display_name', '')
        if not isinstance(display_name, str) or len(display_name) == 0:
            errors.append("Invalid display name")
        
        return len(errors) == 0, errors
    
    def get_cleaning_report(self) -> str:
        """Get a report of all cleaning operations"""
        report = "DATA CLEANING REPORT\n"
        report += "=" * 50 + "\n"
        for log in self.cleaning_log:
            report += f"• {log}\n"
        return report


class DataEnricher:
    """Enrich streamer data with additional information"""
    
    def __init__(self):
        self.enrichment_log = []
    
    def add_follower_tier(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add follower tier classification"""
        df = df.copy()
        
        def categorize(count):
            if count >= 1000000:
                return 'Mega'
            elif count >= 100000:
                return 'Tier-1'
            elif count >= 10000:
                return 'Tier-2'
            elif count >= 1000:
                return 'Tier-3'
            else:
                return 'Emerging'
        
        df['follower_tier'] = df['follower_count'].apply(categorize)
        self.enrichment_log.append("Added follower_tier classification")
        return df
    
    def add_engagement_category(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engagement category based on partner status and followers"""
        df = df.copy()
        
        def categorize_engagement(row):
            if row['is_partner'] and row['follower_count'] >= 10000:
                return 'high_engagement'
            elif row['is_partner'] or row['follower_count'] >= 5000:
                return 'medium_engagement'
            else:
                return 'low_engagement'
        
        df['engagement_category'] = df.apply(categorize_engagement, axis=1)
        self.enrichment_log.append("Added engagement_category")
        return df
    
    def add_language_group(self, df: pd.DataFrame) -> pd.DataFrame:
        """Group languages into regional categories"""
        df = df.copy()
        
        language_groups = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'zh': 'Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
        }
        
        df['language_group'] = df['language'].map(language_groups).fillna('Other')
        self.enrichment_log.append("Added language_group classification")
        return df
    
    def add_market_potential(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate market potential for sponsorships"""
        df = df.copy()
        
        def calculate_potential(row):
            # Weighted scoring
            size_score = min(row['follower_count'] / 1000000, 1.0) * 0.4
            partner_score = (1.0 if row['is_partner'] else 0.5) * 0.3
            
            # Base potential calculation
            potential = (size_score + partner_score) * 100
            return min(potential, 100)
        
        df['market_potential'] = df.apply(calculate_potential, axis=1)
        self.enrichment_log.append("Added market_potential score")
        return df
    
    def get_enrichment_report(self) -> str:
        """Get enrichment operations report"""
        report = "DATA ENRICHMENT REPORT\n"
        report += "=" * 50 + "\n"
        for log in self.enrichment_log:
            report += f"• {log}\n"
        return report


class DataQualityAnalyzer:
    """Analyze and report on data quality"""
    
    @staticmethod
    def quality_score(df: pd.DataFrame) -> float:
        """
        Calculate overall data quality score (0-100)
        
        Args:
            df: DataFrame to analyze
        
        Returns:
            Quality score
        """
        if df.empty:
            return 0
        
        # Check completeness
        completeness = (1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
        
        # Check validity
        valid_rows = 0
        for _, row in df.iterrows():
            if all(row[col] not in [None, '', np.nan] for col in df.columns):
                valid_rows += 1
        
        validity = (valid_rows / len(df)) * 100 if len(df) > 0 else 0
        
        # Check consistency
        consistency = 100  # Could add more checks
        if 'follower_count' in df.columns:
            if (df['follower_count'] < 0).any():
                consistency -= 10
        if 'is_partner' in df.columns:
            if not df['is_partner'].isin([True, False]).all():
                consistency -= 10
        
        # Average quality score
        quality = (completeness * 0.4 + validity * 0.4 + consistency * 0.2)
        return quality
    
    @staticmethod
    def generate_quality_report(df: pd.DataFrame) -> str:
        """Generate detailed quality report"""
        report = "DATA QUALITY ANALYSIS\n"
        report += "=" * 50 + "\n"
        
        if df.empty:
            report += "Dataset is empty!\n"
            return report
        
        # Basic stats
        report += f"Total Records: {len(df):,}\n"
        report += f"Total Columns: {len(df.columns)}\n"
        report += f"Duplicates: {df.duplicated().sum()}\n"
        
        # Missing data
        report += "\nMissing Data:\n"
        missing = df.isnull().sum()
        for col, count in missing[missing > 0].items():
            pct = (count / len(df)) * 100
            report += f"  {col}: {count} ({pct:.1f}%)\n"
        
        # Data type issues
        report += "\nData Types:\n"
        for col, dtype in df.dtypes.items():
            report += f"  {col}: {dtype}\n"
        
        # Quality score
        quality = DataQualityAnalyzer.quality_score(df)
        report += f"\nOverall Quality Score: {quality:.1f}/100\n"
        
        return report


if __name__ == "__main__":
    print("Streamer data utilities module loaded")
