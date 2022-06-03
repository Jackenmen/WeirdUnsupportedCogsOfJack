import discord

from .delegate import delegate


DESCRIPTORS = [
    delegate(discord.abc.Messageable, "send"),
    delegate(discord.abc.Messageable, "trigger_typing"),
    delegate(discord.abc.Messageable, "typing"),
    delegate(discord.abc.Messageable, "fetch_message"),
    delegate(discord.abc.Messageable, "pins"),
    delegate(discord.abc.Messageable, "history"),
    delegate(discord.TextChannel, "_get_channel"),
    # this is needed to support whole ABC but it's impossible to do without last_message_id attr
    #
    # delegate(discord.TextChannel, "last_message"),
    delegate(discord.TextChannel, "get_partial_message"),
    delegate(discord.TextChannel, "delete_messages"),
    delegate(discord.TextChannel, "purge"),
    delegate(discord.TextChannel, "webhooks"),
    delegate(discord.TextChannel, "create_webhook"),
]


def _tiv_load() -> None:
    for desc in DESCRIPTORS:
        setattr(discord.VoiceChannel, desc.__name__, desc)


def _tiv_unload() -> None:
    for desc in DESCRIPTORS:
        delattr(discord.VoiceChannel, desc.__name__)
