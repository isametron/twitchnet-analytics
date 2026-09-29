"""
User (OAuth) authentication for features that need a user token, such as EventSub raids.

The first run opens a browser to authorize on twitch.tv; the token is then stored in
data/processed/user_token.json (gitignored) and refreshed automatically.
Requires http://localhost:17563 as an OAuth Redirect URL on the Twitch application.
"""
import os
from pathlib import PurePath
from typing import List, Tuple

from twitchAPI.oauth import UserAuthenticationStorageHelper, UserAuthenticator
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

from twitchnet.config import Config

USER_TOKEN_PATH = PurePath(Config.PROCESSED_DATA_DIR) / 'user_token.json'
# channel.raid, stream.online and stream.offline need no scopes, only a user token
USER_SCOPES: List[AuthScope] = []


async def _authenticate_locally(twitch: Twitch, scopes: List[AuthScope]) -> Tuple[str, str]:
    """Browser sign-in whose callback server listens on 127.0.0.1 only (the library default is 0.0.0.0)"""
    authenticator = UserAuthenticator(twitch, scopes, force_verify=True, host='127.0.0.1')
    return await authenticator.authenticate()


def has_stored_user_token() -> bool:
    return os.path.exists(USER_TOKEN_PATH)


async def get_user_twitch() -> Twitch:
    """Twitch client with user authentication; signs in through the browser if no valid token is stored"""
    Config.create_directories()
    twitch = await Twitch(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    helper = UserAuthenticationStorageHelper(
        twitch, USER_SCOPES, storage_path=USER_TOKEN_PATH, auth_generator_func=_authenticate_locally
    )
    await helper.bind()
    return twitch


if __name__ == "__main__":
    import asyncio

    async def main():
        twitch = await get_user_twitch()
        print(f"User token ready (stored in {USER_TOKEN_PATH})")
        await twitch.close()

    asyncio.run(main())
