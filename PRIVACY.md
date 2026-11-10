# TwitchNet privacy notice

TwitchNet is a non-commercial student research project at BMS College of Engineering, Bengaluru, India. It studies how Twitch creators are connected, by comparing networks inferred from shared attributes (such as game or language) with networks observed through behaviour (shared chat audiences, raids, teams and co-streams).

**To opt out, see [How to opt out](#how-to-opt-out).** Contact: **siddhantverma.ad23@bmsce.ac.in**

## What we collect

From public Twitch channels we track:

- **Channel and stream data:** username, display name, description, profile image link, follower and viewer counts, stream titles and categories, tags, content classification labels, partner status, teams, schedules, past broadcasts and clips.
- **Raids and co-streams:** which channel raided or co-streamed with which, when, and the raid's viewer count.
- **Chat activity:** for each person who chats in a tracked channel, a salted one-way hash of their Twitch user id, the channel, when they were first and last seen there, and how many messages they sent. We also count messages per channel per minute.

## What we don't collect

- **We never store the text of chat messages.**
- We don't store chatters' usernames or display names. We read chat only to count activity.
- We never post in chat, contact chatters, or try to work out who a hash belongs to.
- We don't collect private messages, emails, payment details or anything that isn't already public on Twitch.

## How the data is used and protected

The data is used only for this research, which we intend to publish as an academic paper. We publish code and aggregated statistics, not raw Twitch data or per-chatter records.

Hashing makes chatter records pseudonymous, not fully anonymous: someone holding the secret salt could link a hash to a known user id. The salt is kept out of our code repository and is destroyed when the raw data is deleted. The data is held on a private server and on the research team's computers.

## How long we keep it

We will delete all raw data and the salt by **31 March 2027**.

## How to opt out

Email **siddhantverma.ad23@bmsce.ac.in** with your Twitch username and "TwitchNet opt-out" in the subject. This works for chatters and for streamers. We will:

1. delete everything stored about your account, both as a chatter and as a channel;
2. keep your account out of future collection, by retaining only a salted hash of your user id for that purpose; and
3. confirm by email once it's done.

Copies in our automatic backups are removed as those backups rotate out, within 7 days. Results that were already aggregated or published can't be changed, but they don't identify individual chatters.

## Changes

We will update this page if the project's data use changes. Last updated: November 2026.
