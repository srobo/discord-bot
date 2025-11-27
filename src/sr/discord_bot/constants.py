from discord import Permissions

# name of the category for new welcome channels to go.
WELCOME_CATEGORY_NAME = "Welcome"

# prefix used to identify the channels to listen to passwords in.
CHANNEL_PREFIX = "welcome-"

# prefix of the role to give the user once the password succeeds
ROLE_PREFIX = "Team "

# role to give user if they have correctly entered *any* password
VERIFIED_ROLE = "Verified"

SPECIAL_TEAM = "SRZ"
SPECIAL_ROLE = "Unverified Volunteer"
BLUESHIRT_ONBOARDING_CHANNEL_NAME = "blueshirt-onboarding"

VOLUNTEER_ROLE = "Blueshirt"
ADMIN_ROLE = "Admin"

TEAM_CATEGORY_NAME = "Team Channels"
TEAM_CHANNEL_PREFIX = "team-"
TEAM_VOICE_CATEGORY_NAME = "Team Voice Channels"
TEAM_LEADER_ROLE = "Team Supervisor"

FEED_URL = "https://studentrobotics.org/feed.xml"
FEED_CHECK_INTERVAL = 60 * 3  # in seconds

VERIFIED_PERMISSION_MASK = \
    Permissions.send_messages.flag | \
    Permissions.send_messages_in_threads.flag | \
    Permissions.connect.flag | \
    Permissions.create_public_threads.flag | \
    Permissions.embed_links.flag | \
    Permissions.attach_files.flag | \
    Permissions.add_reactions.flag | \
    Permissions.use_external_emojis.flag | \
    Permissions.use_external_stickers.flag | \
    Permissions.read_message_history.flag | \
    Permissions.speak.flag | \
    Permissions.stream.flag | \
    Permissions.use_voice_activation.flag | \
    Permissions.request_to_speak.flag | \
    Permissions.change_nickname.flag

EVERYONE_PERMISSION_MASK = \
    Permissions.change_nickname.flag | \
    Permissions.read_message_history.flag | \
    Permissions.use_application_commands.flag

BLUESHIRT_PERMISSION_MASK = VERIFIED_PERMISSION_MASK | \
    Permissions.manage_roles.flag | \
    Permissions.manage_emojis_and_stickers.flag | \
    Permissions.view_audit_log.flag | \
    Permissions.manage_nicknames.flag | \
    Permissions.mention_everyone.flag | \
    Permissions.manage_threads.flag | \
    Permissions.connect.flag | \
    Permissions.mute_members.flag | \
    Permissions.deafen_members.flag | \
    Permissions.move_members.flag | \
    Permissions.create_events.flag | \
    Permissions.manage_events.flag

ROBOTS_PERMISSION_MASK = \
    Permissions.read_messages.flag | \
    Permissions.read_message_history.flag | \
    Permissions.manage_roles.flag | \
    Permissions.use_external_emojis.flag | \
    Permissions.use_application_commands.flag

PERMISSIONS = {
    "everyone": Permissions(EVERYONE_PERMISSION_MASK),
    "verified": Permissions(VERIFIED_PERMISSION_MASK),
    "blueshirt": Permissions(BLUESHIRT_PERMISSION_MASK),
    "robots": Permissions(ROBOTS_PERMISSION_MASK),
    "admin": Permissions.elevated(),
}
