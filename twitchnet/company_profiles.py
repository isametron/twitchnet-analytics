from typing import Dict


class CompanyProfile:
    """Represents a company looking for streamer partnerships"""

    def __init__(self, company_id: str, name: str, **kwargs):
        self.company_id = company_id
        self.name = name
        self.target_games = kwargs.get('target_games', [])
        self.target_languages = kwargs.get('target_languages', ['en'])
        self.min_followers = kwargs.get('min_followers', 1000)
        self.max_followers = kwargs.get('max_followers', 1000000)
        self.budget_tier = kwargs.get('budget_tier', 'medium')  # low, medium, high
        self.target_demographics = kwargs.get('target_demographics', {})
        self.brand_values = kwargs.get('brand_values', [])
        self.product_category = kwargs.get('product_category', '')

    def to_feature_vector(self) -> Dict:
        """Convert company profile to feature dictionary for matching"""
        return {
            'games': self.target_games,
            'languages': self.target_languages,
            'follower_range': (self.min_followers, self.max_followers),
            'budget_tier': self.budget_tier,
            'product_category': self.product_category
        }

    def __repr__(self):
        return f"CompanyProfile(id={self.company_id}, name={self.name})"


class CompanyProfileManager:
    """Manage company profiles for matching"""

    def __init__(self):
        self.profiles = {}

    def add_profile(self, profile: CompanyProfile):
        """Add a company profile"""
        self.profiles[profile.company_id] = profile

    def get_profile(self, company_id: str) -> CompanyProfile:
        """Get a specific company profile"""
        return self.profiles.get(company_id)

    def create_sample_profiles(self):
        """Create sample company profiles for testing"""

        # Gaming peripheral company
        gaming_tech = CompanyProfile(
            company_id='comp_001',
            name='ProGaming Tech',
            target_games=['League of Legends', 'Valorant', 'CS:GO'],
            target_languages=['en'],
            min_followers=5000,
            max_followers=100000,
            budget_tier='medium',
            product_category='gaming_peripherals',
            brand_values=['competitive', 'performance', 'esports']
        )

        # Energy drink brand
        energy_drink = CompanyProfile(
            company_id='comp_002',
            name='PowerBoost Energy',
            target_games=['Fortnite', 'Call of Duty', 'Apex Legends'],
            target_languages=['en', 'es'],
            min_followers=10000,
            max_followers=500000,
            budget_tier='high',
            product_category='food_beverage',
            brand_values=['energy', 'gaming', 'lifestyle']
        )

        # Indie game studio
        indie_studio = CompanyProfile(
            company_id='comp_003',
            name='Pixel Dreams Studio',
            target_games=['Indie Games', 'Roguelike', 'Platformer'],
            target_languages=['en'],
            min_followers=1000,
            max_followers=50000,
            budget_tier='low',
            product_category='game_developer',
            brand_values=['indie', 'creative', 'community']
        )

        self.add_profile(gaming_tech)
        self.add_profile(energy_drink)
        self.add_profile(indie_studio)

        print(f"Created {len(self.profiles)} sample company profiles")
        return self.profiles


if __name__ == "__main__":
    manager = CompanyProfileManager()
    profiles = manager.create_sample_profiles()

    for profile in profiles.values():
        print(profile)
        print(f"  Target games: {profile.target_games}")
        print(f"  Budget tier: {profile.budget_tier}")
