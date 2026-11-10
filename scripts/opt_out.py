"""
Process a privacy opt-out: delete everything stored about a Twitch account and keep it out of
future collection. Run this where the data lives (the tracker server), from the repository root.

  python scripts/opt_out.py some_username [another_username ...]
  python scripts/opt_out.py --user-id 123456     for accounts whose username no longer resolves
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from twitchAPI.twitch import Twitch  # noqa: E402

from twitchnet.config import Config  # noqa: E402
from twitchnet.database import DatabaseManager  # noqa: E402
from twitchnet.privacy import forget_user  # noqa: E402


async def resolve_user_ids(logins):
    """Twitch login -> user id; logins Twitch doesn't know are left out"""
    twitch = await Twitch(Config.TWITCH_CLIENT_ID, Config.TWITCH_CLIENT_SECRET)
    try:
        return {user.login.lower(): user.id async for user in twitch.get_users(logins=logins)}
    finally:
        await twitch.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('logins', nargs='*', help='Twitch usernames to opt out')
    parser.add_argument('--user-id', action='append', default=[], help='numeric Twitch user id (repeatable)')
    args = parser.parse_args()
    if not args.logins and not args.user_id:
        parser.error('give at least one username or --user-id')

    Config.make_console_safe()
    logins = [login.lower().lstrip('@') for login in args.logins]
    resolved = asyncio.run(resolve_user_ids(logins)) if logins else {}
    unknown = [login for login in logins if login not in resolved]

    db = DatabaseManager()
    for user_id in list(resolved.values()) + args.user_id:
        deleted = forget_user(db, user_id)
        print(f"Opted out one account: {sum(deleted.values())} rows deleted {deleted}")
    db.close()

    if unknown:
        print(f"NOT processed, Twitch doesn't know these usernames: {', '.join(unknown)}. "
              "Ask for the numeric user id and use --user-id.")
    print("Backups keep old rows until they rotate out (7 days on the server). "
          "Re-export any CSVs and replace downloaded copies of the database.")
    sys.exit(1 if unknown else 0)


if __name__ == '__main__':
    main()
