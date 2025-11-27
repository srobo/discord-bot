from typing import TextIO

import yaml

from sr.discord_bot.schema import ChannelDefinition
from sr.discord_bot.channel import ChannelSet


def diff_configs(old_config: TextIO, new_config: TextIO) -> None:
    old_channels = [ChannelDefinition.load(ch) for ch in yaml.load(old_config.read(), Loader=yaml.Loader)]
    new_channels = [ChannelDefinition.load(ch) for ch in yaml.load(new_config.read(), Loader=yaml.Loader)]
    old = ChannelSet.from_definitions(old_channels)
    new = ChannelSet.from_definitions(new_channels)
    diff = ChannelSet.diff(old, new)
    if len(diff) > 0:
        for change in diff:
            print(change)
    else:
        print("No changes found.")
