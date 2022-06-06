from types import SimpleNamespace

import discord

from .delegate import delegate


def last_message_id(self) -> None:
    return None


def get_partial_message(self, message_id) -> discord.PartialMessage:
    ret = discord.TextChannel.get_partial_message(
        SimpleNamespace(type=discord.ChannelType.text, _state=self._state), message_id
    )
    ret.channel = self
    return ret


DESCRIPTORS = [
    delegate(discord.abc.Messageable, "send"),
    delegate(discord.abc.Messageable, "trigger_typing"),
    delegate(discord.abc.Messageable, "typing"),
    delegate(discord.abc.Messageable, "fetch_message"),
    delegate(discord.abc.Messageable, "pins"),
    delegate(discord.abc.Messageable, "history"),
    delegate(discord.TextChannel, "_get_channel"),
    property(last_message_id),
    delegate(discord.TextChannel, "last_message"),
    get_partial_message,
    delegate(discord.TextChannel, "delete_messages"),
    delegate(discord.TextChannel, "purge"),
    delegate(discord.TextChannel, "webhooks"),
    delegate(discord.TextChannel, "create_webhook"),
]


def _tiv_load() -> None:
    for desc in DESCRIPTORS:
        setattr(discord.VoiceChannel, desc.fget.__name__, desc)


def _tiv_unload() -> None:
    for desc in DESCRIPTORS:
        delattr(discord.VoiceChannel, desc.fget.__name__)
