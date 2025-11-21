from discord import ChannelType
from yaml import load, Loader

from sr.discord_bot.schema import ChannelDefinition, ChannelUseCase


def load_data(filename='channels.example.yml') -> list[dict]:
    with open(filename, 'r+') as f:
        data = load(f, Loader=Loader)
    return data

def test_channel_load() -> None:
    data = load_data()
    definition = ChannelDefinition.load(data[0]['channels'][0], None)
    assert definition is not None
    assert definition.name == 'welcome-and-rules'
    assert definition.topic == ''
    assert definition.channel_type == ChannelType.text
    assert definition.use_case == ChannelUseCase.RULES
    assert definition.category is None

def test_channel_permissions() -> None:
    pass

def test_category_load() -> None:
    data = load_data()
    definition = ChannelDefinition.load(data[0])
    assert definition is not None
    assert definition.name == 'Information'
    assert len(definition.channels) == 3
