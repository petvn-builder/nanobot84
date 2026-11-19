"""Group observation never dispatches; only numeric owners explicitly tagging may act."""
from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram import TelegramChannel, TelegramConfig

OWNER = 5810260871
MESSAGE_IDS = count(1)


def message(text='hello', *, sender=OWNER, group=-1001, topic=None, reply=False):
    user = SimpleNamespace(id=sender, username='tester', first_name='Member', is_bot=False)
    msg = SimpleNamespace(
        text=text, caption=None, entities=[], caption_entities=[], chat_id=group,
        chat=SimpleNamespace(type='supergroup' if group < 0 else 'private'),
        message_id=next(MESSAGE_IDS), message_thread_id=topic, location=None, media_group_id=None,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=999)) if reply else None,
        reply_text=AsyncMock(), date=None,
    )
    if '@test_bot' in text:
        msg.entities = [SimpleNamespace(type='mention', offset=text.index('@test_bot'), length=9)]
    return SimpleNamespace(message=msg, effective_user=user)


@pytest.fixture
def channel(tmp_path, monkeypatch):
    monkeypatch.setattr('nanobot.config.loader.get_config_path', lambda: tmp_path / 'config.json')
    monkeypatch.setattr('nanobot.channels.base.is_approved', lambda *args: False)
    config = TelegramConfig(allow_from=[str(OWNER)], observe_group_messages=True)
    ch = TelegramChannel(config, MessageBus())
    ch._bot_user_id, ch._bot_username = 999, 'test_bot'
    ch._start_typing = Mock()
    ch._add_reaction = AsyncMock()
    ch._download_message_media = AsyncMock(return_value=([], []))
    return ch


@pytest.mark.asyncio
async def test_everyone_is_observed_and_owner_tag_reaches_real_bus(channel):
    await channel._on_message(message('meeting is Friday', sender=222), None)
    await channel._on_message(message('@test_bot run a task', sender=222), None)
    assert channel.bus.inbound_size == 0
    channel._start_typing.assert_not_called()
    channel._add_reaction.assert_not_awaited()
    await channel._on_message(message('@test_bot when is the meeting?'), None)
    event = channel.bus.inbound.get_nowait()
    assert 'meeting is Friday' in event.content
    assert 'context only' in event.content.lower()
    assert event.session_key == 'telegram:-1001'
    assert event.sender_id.startswith(str(OWNER))


@pytest.mark.asyncio
async def test_owner_reply_without_tag_is_observed(channel):
    await channel._on_message(message('a reply', reply=True), None)
    assert channel.bus.inbound_size == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('name,text', [('_forward_command', '/new'), ('_on_start', '/start'),
                                       ('_on_help', '/help')])
async def test_untagged_owner_commands_cannot_bypass_group_gate(channel, name, text):
    update = message(text)
    await getattr(channel, name)(update, None)
    assert channel.bus.inbound_size == 0
    update.message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_groups_topics_and_dms_do_not_share_observed_context(channel):
    await channel._on_message(message('private-group-context', sender=222, group=-2002, topic=10), None)
    await channel._on_message(message('@test_bot hello', group=-2002, topic=20), None)
    assert 'private-group-context' not in channel.bus.inbound.get_nowait().content
    await channel._on_message(message('hello in DM', group=OWNER), None)
    assert 'private-group-context' not in channel.bus.inbound.get_nowait().content


@pytest.mark.asyncio
async def test_group_pairing_grants_do_not_make_other_members_owners(channel, monkeypatch):
    monkeypatch.setattr('nanobot.channels.base.is_approved', lambda *args: True)
    await channel._on_message(message('@test_bot unauthorized', sender=222), None)
    assert channel.bus.inbound_size == 0


@pytest.mark.asyncio
async def test_other_member_commands_are_available_as_observed_context(channel):
    await channel._forward_command(message('/new@test_bot', sender=222), None)
    assert channel.bus.inbound_size == 0
    await channel._on_message(message('@test_bot summarize'), None)
    assert '/new@test_bot' in channel.bus.inbound.get_nowait().content


@pytest.mark.asyncio
async def test_observation_is_persistent_and_bounded_without_media_downloads(channel):
    for _ in range(60):
        update = message('long context ' * 200, sender=222)
        update.message.photo = [SimpleNamespace(file_id='photo')]
        await channel._on_message(update, None)
    store = channel._group_observation
    restored = type(store)(store.root)
    ctx = restored.context(update.message)
    assert len(ctx) < 12500
    assert 'not downloaded' in ctx
    channel._download_message_media.assert_not_awaited()
    import json
    path = next(store.root.glob('*.json'))
    assert len(json.loads(path.read_text())) <= 40
    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_raw_handle_without_telegram_mention_entity_is_only_context(channel):
    update = message('@test_bot quoted in code')
    update.message.entities = []
    await channel._on_message(update, None)
    assert channel.bus.inbound_size == 0


@pytest.mark.asyncio
async def test_owner_command_with_explicit_bot_suffix_still_works(channel):
    update = message('/new@test_bot')
    update.message.entities = [SimpleNamespace(type='bot_command', offset=0, length=13)]
    await channel._forward_command(update, None)
    assert channel.bus.inbound.get_nowait().content == '/new'


@pytest.mark.asyncio
async def test_other_members_cannot_use_inline_buttons_even_if_paired(channel, monkeypatch):
    monkeypatch.setattr('nanobot.channels.base.is_approved', lambda *args: True)
    update = message('', sender=222)
    update.callback_query = SimpleNamespace(message=update.message, data='run', answer=AsyncMock())
    await channel._on_callback_query(update, None)
    assert channel.bus.inbound_size == 0
    update.callback_query.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_new_resets_only_the_current_observed_topic(channel):
    await channel._on_message(message('old topic context', sender=222, topic=10), None)
    await channel._on_message(message('other topic context', sender=222, topic=20), None)
    update = message('/new@test_bot', topic=10)
    update.message.entities = [SimpleNamespace(type='bot_command', offset=0, length=13)]
    await channel._forward_command(update, None)
    channel.bus.inbound.get_nowait()
    assert not channel._group_observation.context(update.message)
    assert 'other topic context' in channel._group_observation.context(message('', topic=20).message)


@pytest.mark.asyncio
async def test_malformed_snapshot_does_not_block_owner_mentions(channel):
    update = message('new context', sender=222)
    path = channel._group_observation._path(update.message)
    path.write_text('["broken entry"]')
    await channel._on_message(update, None)
    await channel._on_message(message('@test_bot hello'), None)
    assert 'new context' in channel.bus.inbound.get_nowait().content
