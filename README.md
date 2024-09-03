# discord-gated-entry

[![CircleCI](https://circleci.com/gh/srobo/discord-gated-entry.svg?style=svg)](https://circleci.com/gh/srobo/discord-gated-entry)

A discord bot to gate the entry of a discord server on multiple passwords (each one giving a different role)

The use case is as follows:

- Send different people/groups the same discord link, with a different password.
- Each user is prompted for their password on entry. If they enter the correct password, they are given their appropriate role.

## Requirements

See requirements.txt

For development, see `script/requirements.txt`

# Discord server set-up instructions

- Ensure the `@everyone` role cannot see any channels by default.
- Create a role named `Verified` which can see the base channels (i.e. #general)
- Create a role named `Unverified Volunteer` which can see the volunteer onboarding channel.
- Create a role named `Blueshirt`.
- Create a role named `Team Supervisor`.
- Create a new channel category called `welcome`, block all users from reading this category in its permissions.
- Create channel categories called `Team Channels` and `Team Voice Channels`.
- Create a channel named `#blog`, block all users from sending messages in it.
- Set a Blueshirt password using `/passwd tla:SRZ new_password:`
- Make sure that the SRbot role is at the top of the role list (it can only assign roles below its own)
- Create teams using the `/team new` command.

And voilà, any new users should automatically get their role assigned once they enter the correct password.

## Install instructions

1. Set up discord to the correct settings (see above)
2. Register a discord bot.
3. Copy `.env` and fill it out with the application token and guild ID. In order to get the guild ID, you will need to enable developer mode in Discord's settings. Once enabled, right click the guild (server) in the sidebar and click `Copy Server ID`.
4. `pip install .`
5. `python -m sr.discord_bot`
6. In the server settings, ensure the `/join` command can be used by `@everyone` but cannot be used by the `Verified` role
7. Ensure the `/passwd` commands can only be used by `Blueshirt`s
