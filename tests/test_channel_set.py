import discord

from sr.discord_bot.channel import ChannelSet, CreateCategoryCommand, DeleteChannelCommand, AlterChannelCommand, \
    CreateChannelCommand

from unittest.mock import Mock

blank = ChannelSet()

def test_create_category():
    channel_set = ChannelSet()
    channel_set.create_category("Test Category")

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites=None)
    ]

def test_delete_category():
    channel_set = ChannelSet()
    channel_set.create_category("Test Category")

    commands = ChannelSet.diff(channel_set, blank)

    assert commands == [DeleteChannelCommand("Test Category", is_category=True)]

def test_rename_category():
    channel_set_old = ChannelSet()
    channel_set_old.create_category("Old Name")

    channel_set_new = ChannelSet()
    channel_set_new.create_category("New Name", old_names=["Old Name"])

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Old Name", new_name="New Name", is_category=True),
    ]

def test_create_category_if_old_name_not_found():
    channel_set_old = ChannelSet()
    channel_set_old.create_category("Old Category")

    channel_set_new = ChannelSet()
    channel_set_new.create_category("New Category")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Old Category", is_category=True),
        CreateCategoryCommand("New Category", overwrites=None),
    ]

def test_create_multiple_categories():
    channel_set = ChannelSet()
    channel_set.create_category("Category 1")
    channel_set.create_category("Category 2")

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Category 1", overwrites=None),
        CreateCategoryCommand("Category 2", overwrites=None),
    ]

def test_create_category_with_overwrites():
    role = Mock(discord.Role)

    channel_set = ChannelSet()
    channel_set.create_category("Test Category", overwrites={role: discord.PermissionOverwrite(read_messages=True)})

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites={role: discord.PermissionOverwrite(read_messages=True)})
    ]

def test_no_changes():
    channel_set = ChannelSet()
    channel_set.create_category("Category 1")
    channel_set.create_category("Category 2")

    commands = ChannelSet.diff(channel_set, channel_set)

    assert commands == []

def test_move_category():
    channel_set_old = ChannelSet()
    channel_set_old.create_category("Category 1")
    channel_set_old.create_category("Category 2")

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Category 2")
    channel_set_new.create_category("Category 1")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand("Category 2", new_name="Category 2", position=0, is_category=True),
        AlterChannelCommand("Category 1", new_name="Category 1", position=1, is_category=True),
    ]

def test_move_category_to_end():
    channel_set_old = ChannelSet()
    channel_set_old.create_category("Category 1")
    channel_set_old.create_category("Category 2")
    channel_set_old.create_category("Category 3")

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Category 2")
    channel_set_new.create_category("Category 3")
    channel_set_new.create_category("Category 1")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand("Category 2", new_name="Category 2", position=0, is_category=True),
        AlterChannelCommand("Category 3", new_name="Category 3", position=1, is_category=True),
        AlterChannelCommand("Category 1", new_name="Category 1", position=2, is_category=True),
    ]

def test_create_text_channel():
    channel_set = ChannelSet()
    category = channel_set.create_category("Test Category")
    channel_set.create_text_channel("Test Channel", category=category)

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites=None),
        CreateChannelCommand("Test Channel", type=discord.ChannelType.text, overwrites=None, category=category, topic=""),
    ]

def test_delete_text_channel():
    channel_set_old = ChannelSet()
    category = channel_set_old.create_category("Test Category")
    channel_set_old.create_text_channel("Test Channel", category=category)

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Test Category")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Test Channel")
    ]

def test_rename_text_channel():
    channel_set_old = ChannelSet()
    channel_set_old.create_text_channel(
        "Old Channel Name",
        category=channel_set_old.create_category("Test Category")
    )

    channel_set_new = ChannelSet()
    channel_set_new.create_text_channel(
        "New Channel Name",
        category=channel_set_new.create_category("Test Category"),
        old_names=["Old Channel Name"]
    )

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Old Channel Name", new_name="New Channel Name"),
    ]

def test_create_text_channel_if_old_name_not_found():
    channel_set_old = ChannelSet()
    channel_set_old.create_text_channel(
        "Old Channel Name",
        category=channel_set_old.create_category("Test Category")
    )

    channel_set_new = ChannelSet()
    category = channel_set_new.create_category("Test Category")
    channel_set_new.create_text_channel("New Channel Name", category=category)

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Old Channel Name"),
        CreateChannelCommand("New Channel Name", overwrites=None, type=discord.ChannelType.text, category=category, topic=""),
    ]

def test_create_multiple_text_channels():
    channel_set = ChannelSet()
    category = channel_set.create_category("Test Category")
    channel_set.create_text_channel("Channel 1", overwrites=None, category=category)
    channel_set.create_text_channel("Channel 2", overwrites=None, category=category)

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites=None),
        CreateChannelCommand("Channel 1", overwrites=None, type=discord.ChannelType.text, category=category, topic=""),
        CreateChannelCommand("Channel 2", overwrites=None, type=discord.ChannelType.text, category=category, topic="")
    ]

def test_create_text_channel_with_overwrites():
    role = Mock(discord.Role)

    channel_set = ChannelSet()
    category = channel_set.create_category("Test Category")
    channel_set.create_text_channel("Test Channel", category=category, overwrites={role: discord.PermissionOverwrite(read_messages=True)})

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites=None),
        CreateChannelCommand("Test Channel", type=discord.ChannelType.text, category=category, topic="", overwrites={role: discord.PermissionOverwrite(read_messages=True)})
    ]

def test_move_channel_between_categories():
    channel_set_old = ChannelSet()
    category1 = channel_set_old.create_category("Category 1")
    channel_set_old.create_category("Category 2")
    channel_set_old.create_text_channel("Test Channel", category=category1)

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Category 1")
    category2 = channel_set_new.create_category("Category 2")
    channel_set_new.create_text_channel("Test Channel", category=category2)

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Test Channel", new_name="Test Channel", category=category2),
    ]

def test_create_voice_channel():
    channel_set = ChannelSet()
    category = channel_set.create_category("Test Category")
    channel_set.create_voice_channel("Test Voice Channel", category=category)

    commands = ChannelSet.diff(blank, channel_set)

    assert commands == [
        CreateCategoryCommand("Test Category", overwrites=None),
        CreateChannelCommand("Test Voice Channel", overwrites=None, type=discord.ChannelType.voice, category=category)
    ]

def test_delete_voice_channel():
    channel_set_old = ChannelSet()
    category = channel_set_old.create_category("Test Category")
    channel_set_old.create_voice_channel("Test Voice Channel", category=category)

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Test Category")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Test Voice Channel")
    ]

def test_change_topic():
    channel_set_old = ChannelSet()
    channel_set_old.create_text_channel(
        "Test Channel",
        category=channel_set_old.create_category("Test Category"),
        topic="Old Topic"
    )

    channel_set_new = ChannelSet()
    channel_set_new.create_text_channel(
        "Test Channel",
        category=channel_set_new.create_category("Test Category"),
        topic="New Topic"
    )

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Test Channel", new_name="Test Channel", topic="New Topic"),
    ]

def test_change_overwrites():
    channel_set_old = ChannelSet()
    role = Mock(discord.Role)
    channel_set_old.create_text_channel(
        "Test Channel",
        category=channel_set_old.create_category("Test Category"),
        overwrites={role: discord.PermissionOverwrite(read_messages=True)}
    )

    channel_set_new = ChannelSet()
    category = channel_set_new.create_category("Test Category")
    overwrites = {role: discord.PermissionOverwrite(read_messages=False)}
    channel_set_new.create_text_channel("Test Channel", category=category, overwrites=overwrites)

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Test Channel", new_name="Test Channel", overwrites=overwrites),
    ]

def test_change_topic_and_overwrites():
    channel_set_old = ChannelSet()
    role = Mock(discord.Role)
    channel_set_old.create_text_channel(
        "Test Channel",
        category=channel_set_old.create_category("Test Category"),
        topic="Old Topic",
        overwrites={role: discord.PermissionOverwrite(read_messages=True)}
    )

    channel_set_new = ChannelSet()
    category = channel_set_new.create_category("Test Category")
    overwrites = {role: discord.PermissionOverwrite(read_messages=False)}
    channel_set_new.create_text_channel("Test Channel", category=category, topic="New Topic", overwrites=overwrites)

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        AlterChannelCommand(old_name="Test Channel", new_name="Test Channel", topic="New Topic", overwrites=overwrites),
    ]

def test_category_and_channel_name_collision():
    channel_set_old = ChannelSet()
    old_category = channel_set_old.create_category("Test Category")
    channel_set_old.create_text_channel("Test Channel", category=old_category)

    channel_set_new = ChannelSet()
    channel_set_new.create_category("Test Category")
    channel_set_new.create_category("Test Channel")

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Test Channel"),
        CreateCategoryCommand("Test Channel", overwrites=None),
    ]

def test_channel_and_category_name_collision():
    channel_set_old = ChannelSet()
    channel_set_old.create_category("Test Category 1")
    channel_set_old.create_category("Test Category 2")

    channel_set_new = ChannelSet()
    category = channel_set_new.create_category("Test Category 1")
    channel_set_new.create_text_channel("Test Category 2", category=category)

    commands = ChannelSet.diff(channel_set_old, channel_set_new)

    assert commands == [
        DeleteChannelCommand("Test Category 2"),
        CreateChannelCommand("Test Category 2", category=category, overwrites=None, type=discord.ChannelType.text),
    ]
