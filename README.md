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

- ensure the `everyone` role cannot see any channels by default.
- Create a role named `verified` which can see the base channels (i.e. #general)
- Create a role named `future-volunteer` which can see the volunteer onboarding channel.
- Create a new channel category called 'welcome', block all users from reading this category in its permissions.
- Create another channel, visible only to the admins, named '#role-passwords', enter in it 1 message per role in the form `role : password`. Special case: for the `future-volunteer` role, please use the role name `team-SRZ`.
- Create each role named `team-{role}`.

And voila, any new users should automatically get their role assigned once they enter the correct password.

## Install instructions

1. Set up discord to the correct settings (see above)
2. Register a discord bot.
3. Add an .env file with `DISCORD_TOKEN=<bot-token>`
4. `pip install -r requirements.txt`
5. `python main.py`
