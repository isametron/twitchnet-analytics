from twitchAPI.twitch import Twitch
import asyncio
import json
import time
from typing import List, Dict
from config import Config

class TwitchDataCollector:
    """Collect streamer data from Twitch API"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.twitch = None
        self.request_count = 0
        self.last_request_time = time.time()
        self.rate_limit_delay = 0.5  # 500ms delay between requests
    
    async def initialize(self):
        """Initialize Twitch API connection"""
        self.twitch = await Twitch(self.client_id, self.client_secret)
        print("Twitch API initialized successfully")
    
    async def _rate_limit_guard(self):
        """Proactive rate limiting to prevent hitting limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Every 10 requests, add extra delay
        if self.request_count % 10 == 0:
            await asyncio.sleep(1)
            print(f"🛡️ Rate limit protection: {self.request_count} requests completed")
    
    async def _retry_with_backoff(self, func, *args, max_retries=5, **kwargs):
        """Retry API calls with exponential backoff on rate limit errors"""
        for attempt in range(max_retries):
            try:
                await self._rate_limit_guard()  # Proactive rate limiting
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'rate limit' in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 10  # 10s, 20s, 40s, 80s, 160s
                        print(f"⚠️ Rate limit hit! Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ Rate limit exceeded after {max_retries} retries")
                        return None  # Return None instead of raising
                else:
                    print(f"Error in API call: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                    else:
                        return None
        return None
    
    async def get_top_streamers(self, game_name: str = None, max_results: int = 100, language: str = None) -> List[Dict]:
        """
        Get top streamers, optionally filtered by game and language
        
        Args:
            game_name: Optional game category to filter by
            max_results: Maximum number of streamers to fetch
            language: Optional language filter (e.g., 'en', 'es', 'fr', 'de', 'pt', 'ja', 'ko')
        
        Returns:
            List of streamer data dictionaries including diverse languages
        """
        streamers_data = []
        
        try:
            if game_name:
                # Get game ID first with retry
                async def get_game():
                    async for g in self.twitch.get_games(names=[game_name]):
                        return g
                    return None
                
                game = await self._retry_with_backoff(get_game)
                
                if not game:
                    print(f"Game '{game_name}' not found")
                    return []
                
                game_id = game.id
                
                # Add language filter if specified
                if language:
                    streams_gen = self.twitch.get_streams(
                        game_id=game_id, 
                        first=min(max_results * 2, 100),  # Fetch more to account for filtering
                        language=language
                    )
                else:
                    streams_gen = self.twitch.get_streams(game_id=game_id, first=max_results)
            else:
                if language:
                    streams_gen = self.twitch.get_streams(
                        first=min(max_results * 2, 100),
                        language=language
                    )
                else:
                    streams_gen = self.twitch.get_streams(first=max_results)
            
            # Iterate over streams
            count = 0
            async for stream in streams_gen:
                if count >= max_results:
                    break
                
                try:
                    # Add small delay every 5 streamers
                    if count > 0 and count % 5 == 0:
                        await asyncio.sleep(0.5)
                    
                    # Pass stream data to get more real-time information with retry
                    streamer_info = await self._retry_with_backoff(
                        self.get_streamer_details,
                        stream.user_login, 
                        stream.game_name,
                        stream_data=stream
                    )
                    
                    if streamer_info:
                        streamers_data.append(streamer_info)
                        count += 1
                except Exception as e:
                    print(f"⚠️ Error processing {stream.user_login}: {e}")
                    continue
            
            lang_text = f" (Language: {language})" if language else " (All languages)"
            print(f"✅ Collected {len(streamers_data)} streamers{lang_text}")
            return streamers_data
            
        except Exception as e:
            print(f"Error fetching streamers: {e}")
            return []
    
    async def get_diverse_streamers(self, game_name: str = None, max_per_language: int = 10) -> List[Dict]:
        """
        Get top streamers with diverse language representation (SEQUENTIAL to avoid rate limits)
        
        Args:
            game_name: Optional game category to filter by
            max_per_language: Number of streamers per language
        
        Returns:
            List of streamer data with diverse languages
        """
        languages = ['en', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'ru', 'zh']
        diverse_streamers = []
        
        print(f"Fetching streamers from {len(languages)} languages SEQUENTIALLY (rate-limit safe)...")
        
        # Fetch SEQUENTIALLY instead of parallel to avoid rate limits
        for idx, lang in enumerate(languages):
            print(f"Fetching {lang.upper()} streamers ({idx + 1}/{len(languages)})...")
            try:
                result = await self.get_top_streamers(game_name, max_per_language, language=lang)
                diverse_streamers.extend(result)
                
                # Add delay between language fetches
                if idx < len(languages) - 1:
                    await asyncio.sleep(2)  # 2 second pause between languages
            except Exception as e:
                print(f"Error fetching {lang}: {e}")
                continue
        
        print(f"Collected {len(diverse_streamers)} streamers with diverse language representation")
        return diverse_streamers
    
    async def get_streamer_details(self, username: str, stream_game_name: str = None, stream_data=None) -> Dict:
        """
        Get detailed information about a specific streamer
        
        Args:
            username: Twitch username
            stream_game_name: Game name from stream data (fallback source)
            stream_data: Optional stream object with real-time data
        
        Returns:
            Dictionary containing comprehensive streamer details
        """
        try:
            # Get user information
            user = None
            async for u in self.twitch.get_users(logins=[username]):
                user = u
                break
            
            if not user:
                return None
            
            # Get follower count
            try:
                follower_info = await self.twitch.get_channel_followers(broadcaster_id=user.id)
                follower_count = follower_info.total
            except Exception:
                follower_count = 0
            
            # Get channel information - await the coroutine first
            channel_info = None
            game_name = stream_game_name or 'Unknown'  # Use stream data as default
            language = None  # Will be determined from stream_data or channel_info
            
            # Extract language from stream data FIRST (most accurate for live streams)
            if stream_data and hasattr(stream_data, 'language'):
                language = stream_data.language
            
            try:
                channel_gen = await self.twitch.get_channel_information(broadcaster_id=user.id)
                async for ch in channel_gen:
                    channel_info = ch
                    break
            except Exception as e:
                # If that fails, use stream data
                channel_info = None
            
            # Prefer channel info for game, but keep stream language if already set
            if channel_info:
                game_name = channel_info.game_name if channel_info.game_name else game_name
                if not language:  # Only override if not set from stream data
                    language = channel_info.broadcaster_language if channel_info.broadcaster_language else 'en'
            
            # Final fallback
            if not language:
                language = 'en'
            
            # Extract real-time stream data if available
            is_live = False
            viewer_count = 0
            stream_title = ''
            thumbnail_url = ''
            started_at = None
            
            if stream_data:
                is_live = True
                viewer_count = stream_data.viewer_count if hasattr(stream_data, 'viewer_count') else 0
                stream_title = stream_data.title if hasattr(stream_data, 'title') else ''
                thumbnail_url = stream_data.thumbnail_url if hasattr(stream_data, 'thumbnail_url') else ''
                started_at = stream_data.started_at if hasattr(stream_data, 'started_at') else None
            
            streamer_data = {
                'user_id': user.id,
                'username': user.login,
                'display_name': user.display_name,
                'description': user.description if user.description else '',
                'follower_count': follower_count,
                'game_name': game_name,
                'game_id': channel_info.game_id if channel_info else '',
                'language': language,
                'tags': channel_info.tags if (channel_info and channel_info.tags) else [],
                'is_partner': user.broadcaster_type == 'partner',
                'view_count': user.view_count if user.view_count else 0,
                # New fields
                'is_live': is_live,
                'viewer_count': viewer_count,
                'stream_title': stream_title,
                'thumbnail_url': thumbnail_url,
                'started_at': str(started_at) if started_at else '',
                'profile_image_url': user.profile_image_url if hasattr(user, 'profile_image_url') else '',
                'created_at': str(user.created_at) if hasattr(user, 'created_at') else ''
            }
            
            return streamer_data
            
        except Exception as e:
            print(f"Error fetching details for {username}: {e}")
            return None
    
    async def get_follows_network(self, streamer_ids: List[str]) -> List[tuple]:
        """
        Build network edges based on mutual follows (simplified version)
        In real implementation, you'd need to check follower overlaps
        
        Args:
            streamer_ids: List of streamer IDs
        
        Returns:
            List of tuples representing edges
        """
        edges = []
        print("Note: Follower network requires additional data sources")
        return edges
    
    def save_data(self, data: List[Dict], filename: str):
        """Save collected data to JSON file"""
        filepath = f"{Config.RAW_DATA_DIR}/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filepath}")
    
    async def close(self):
        """Close Twitch API connection"""
        if self.twitch:
            await self.twitch.close()

async def main():
    """Example usage"""
    collector = TwitchDataCollector(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    await collector.initialize()
    
    # Collect top streamers
    streamers = await collector.get_top_streamers(game_name='League of Legends', max_results=10)
    
    print("\nCollected Streamers:")
    for streamer in streamers:
        print(f"- {streamer['display_name']} (@{streamer['username']}) - {streamer['follower_count']:,} followers")
    
    collector.save_data(streamers, 'streamers.json')
    
    await collector.close()

if __name__ == "__main__":
    asyncio.run(main())
