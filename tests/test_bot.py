import asyncio
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ── Устанавливаем env до импорта бота ──────────────────────────────────
os.environ["BOT_TOKEN"] = "123:test_token"
os.environ["LLM_API_KEY"] = "sk-test-key"
os.environ["BOT_USERNAME"] = "test_bot"
os.environ["LLM_BASE_URL"] = "https://api.test.com/v1"
os.environ["LLM_MODEL"] = "test-model"
os.environ["BOT_PROXY"] = ""
os.environ["TAUNT_CHAT_ID"] = ""

import bot


# ── Фикстуры ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_global_state():
    bot.message_history.clear()
    bot.last_response_time.clear()
    bot.bot_message_ids.clear()


@pytest.fixture
def mock_message():
    """Создаёт фейковое aiogram Message с настраиваемыми полями."""
    user = MagicMock()
    user.id = 999
    user.username = "testuser"
    user.full_name = "Test User"

    chat = MagicMock()
    chat.id = -100111
    chat.type = "supergroup"

    msg = MagicMock(spec=bot.Message)
    msg.message_id = 1
    msg.from_user = user
    msg.chat = chat
    msg.text = "test message"
    msg.caption = None
    msg.forward_origin = None
    msg.reply_to_message = None
    msg.reply = AsyncMock(return_value=MagicMock(message_id=100))
    msg.delete = AsyncMock()
    msg.html_text = "test message"
    msg.md_text = "test message"
    return msg


@pytest.fixture
def mock_reaction():
    """Создаёт фейковое MessageReactionUpdated."""
    user = MagicMock()
    user.id = 999
    user.username = "testuser"
    user.full_name = "Test User"

    chat = MagicMock()
    chat.id = -100111
    chat.type = "supergroup"

    r_type = MagicMock()
    r_type.type = "emoji"
    r_type.emoji = "👍"

    reaction = MagicMock(spec=bot.MessageReactionUpdated)
    reaction.message_id = 100
    reaction.user = user
    reaction.chat = chat
    reaction.new_reaction = [r_type]
    reaction.old_reaction = []
    reaction.date = datetime.now()
    return reaction


@pytest.fixture
def mock_bot():
    with patch.object(bot, "bot") as mock:
        type(mock).id = PropertyMock(return_value=123456789)
        mock.send_chat_action = AsyncMock()
        mock.send_message = AsyncMock(return_value=MagicMock(message_id=200))
        yield mock


# ── Тесты strip_markdown ─────────────────────────────────────────────────

class TestStripMarkdown:
    def test_removes_asterisks(self):
        assert bot.strip_markdown("*bold* text") == "bold text"

    def test_removes_underscores(self):
        assert bot.strip_markdown("_italic_ text") == "italic text"

    def test_removes_backticks(self):
        assert bot.strip_markdown("`code` here") == "code here"

    def test_removes_tildes(self):
        assert bot.strip_markdown("~strike~") == "strike"

    def test_removes_square_brackets(self):
        assert bot.strip_markdown("[link](url)") == "linkurl"

    def test_removes_multiple_markers(self):
        assert bot.strip_markdown("*_`~>#") == ""

    def test_strips_whitespace(self):
        assert bot.strip_markdown("  hello  ") == "hello"

    def test_handles_empty_string(self):
        assert bot.strip_markdown("") == ""

    def test_handles_only_markdown(self):
        assert bot.strip_markdown("***___```") == ""

    def test_keeps_normal_text(self):
        assert bot.strip_markdown("Hello, world!") == "Hello, world!"


# ── Тесты should_respond ─────────────────────────────────────────────────

class TestShouldRespond:
    def test_private_chat_always_responds(self, mock_message):
        mock_message.chat.type = "private"
        assert bot.should_respond(mock_message) is True

    def test_channel_ignored(self, mock_message):
        mock_message.chat.type = "channel"
        assert bot.should_respond(mock_message) is False

    def test_mention_triggers(self, mock_message):
        mock_message.text = f"hello @{bot.BOT_USERNAME} world"
        assert bot.should_respond(mock_message) is True

    def test_mention_at_start(self, mock_message):
        mock_message.text = f"@{bot.BOT_USERNAME} help me"
        assert bot.should_respond(mock_message) is True

    def test_bo_sinn_triggers(self, mock_message):
        mock_message.text = "Бо Синн, привет"
        assert bot.should_respond(mock_message) is True

    def test_reply_to_bot_triggers(self, mock_message):
        reply_from = MagicMock()
        reply_from.id = bot.bot.id
        mock_message.reply_to_message = MagicMock(from_user=reply_from)
        mock_message.text = "answer me"
        assert bot.should_respond(mock_message) is True

    def test_reply_to_other_ignored(self, mock_message):
        reply_from = MagicMock()
        reply_from.id = 99999
        mock_message.reply_to_message = MagicMock(from_user=reply_from)
        mock_message.text = "hello"
        assert bot.should_respond(mock_message) is False

    def test_no_text_ignored(self, mock_message):
        mock_message.text = None
        mock_message.forward_origin = None
        assert bot.should_respond(mock_message) is False

    def test_forward_in_taunt_chat_triggers(self, mock_message):
        bot.TAUNT_CHAT_ID = "-100111"
        mock_message.forward_origin = MagicMock()
        mock_message.text = "forwarded content"
        assert bot.should_respond(mock_message) is True
        bot.TAUNT_CHAT_ID = ""

    def test_forward_outside_taunt_chat_ignored(self, mock_message):
        bot.TAUNT_CHAT_ID = "-100222"
        mock_message.forward_origin = MagicMock()
        mock_message.text = "forwarded content"
        # chat.id is -100111, TAUNT_CHAT_ID is -100222
        assert bot.should_respond(mock_message) is False
        bot.TAUNT_CHAT_ID = ""

    def test_group_no_trigger_ignored(self, mock_message):
        mock_message.text = "just a normal message"
        assert bot.should_respond(mock_message) is False


# ── Тесты is_rate_limited ────────────────────────────────────────────────

class TestIsRateLimited:
    def test_first_call_not_limited(self):
        bot.last_response_time.clear()
        assert bot.is_rate_limited(1) is False

    def test_second_call_within_10s_limited(self):
        bot.last_response_time.clear()
        bot.is_rate_limited(1)
        assert bot.is_rate_limited(1) is True

    def test_different_chats_independent(self):
        bot.last_response_time.clear()
        bot.is_rate_limited(1)
        assert bot.is_rate_limited(2) is False

    def test_after_10s_not_limited(self):
        bot.last_response_time.clear()
        bot.last_response_time[1] = datetime.now() - timedelta(seconds=11)
        assert bot.is_rate_limited(1) is False

    def test_records_timestamp(self):
        bot.last_response_time.clear()
        before = datetime.now()
        bot.is_rate_limited(1)
        after = datetime.now()
        ts = bot.last_response_time[1]
        assert before <= ts <= after


# ── Тесты format_history_for_llm ────────────────────────────────────────

class TestFormatHistoryForLLM:
    def test_empty_history(self):
        bot.message_history.clear()
        assert bot.format_history_for_llm(1) == ""

    def test_single_message(self):
        bot.message_history.clear()
        bot.message_history[1].append((datetime.now(), "Alice", "hello"))
        result = bot.format_history_for_llm(1)
        assert "Alice: hello" in result

    def test_multiple_messages(self):
        bot.message_history.clear()
        bot.message_history[1].append((datetime.now(), "Alice", "hi"))
        bot.message_history[1].append((datetime.now(), "Bob", "hey"))
        result = bot.format_history_for_llm(1)
        assert "Alice: hi" in result
        assert "Bob: hey" in result
        assert result.index("Alice: hi") < result.index("Bob: hey")

    def test_different_chats(self):
        bot.message_history.clear()
        bot.message_history[1].append((datetime.now(), "Alice", "chat1"))
        bot.message_history[2].append((datetime.now(), "Bob", "chat2"))
        assert "chat1" in bot.format_history_for_llm(1)
        assert "chat2" not in bot.format_history_for_llm(1)
        assert "chat2" in bot.format_history_for_llm(2)


# ── Тесты store_message ──────────────────────────────────────────────────

class TestStoreMessage:
    def test_stores_text(self, mock_message):
        bot.message_history.clear()
        asyncio.run(bot.store_message(mock_message))
        assert len(bot.message_history[-100111]) == 1
        _, name, text = bot.message_history[-100111][0]
        assert name == "Test User"
        assert text == "test message"

    def test_skips_private_chat(self, mock_message):
        mock_message.chat.type = "private"
        bot.message_history.clear()
        asyncio.run(bot.store_message(mock_message))
        assert -100111 not in bot.message_history

    def test_skips_no_from_user(self, mock_message):
        mock_message.from_user = None
        bot.message_history.clear()
        asyncio.run(bot.store_message(mock_message))
        assert len(bot.message_history.get(-100111, [])) == 0

    def test_uses_caption_when_no_text(self, mock_message):
        mock_message.text = None
        mock_message.caption = "photo caption"
        bot.message_history.clear()
        asyncio.run(bot.store_message(mock_message))
        _, _, text = bot.message_history[-100111][0]
        assert text == "photo caption"

    def test_skips_empty_text_and_caption(self, mock_message):
        mock_message.text = None
        mock_message.caption = None
        bot.message_history.clear()
        asyncio.run(bot.store_message(mock_message))
        assert len(bot.message_history.get(-100111, [])) == 0

    def test_respects_history_size(self, mock_message):
        bot.message_history.clear()
        bot.HISTORY_SIZE = 3
        for i in range(5):
            msg = MagicMock()
            msg.chat.type = "supergroup"
            msg.chat.id = -100111
            msg.from_user = MagicMock(username=f"user{i}", full_name=f"User {i}")
            msg.text = f"message {i}"
            msg.caption = None
            msg.forward_origin = None
            asyncio.run(bot.store_message(msg))
        assert len(bot.message_history[-100111]) == 3
        assert bot.message_history[-100111][-1][2] == "message 4"
        bot.HISTORY_SIZE = 50


# ── Тесты query_llm ──────────────────────────────────────────────────────

class TestQueryLLM:
    @patch("aiohttp.ClientSession.post")
    def test_successful_response(self, mock_post):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Иди нахуй, тупой."}}]
        })
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)

        result = asyncio.run(bot.query_llm("context", "user message"))
        assert result == "Иди нахуй, тупой."

    @patch("aiohttp.ClientSession.post")
    def test_api_error_returns_none(self, mock_post):
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="Internal Server Error")
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)

        result = asyncio.run(bot.query_llm("context", "user message"))
        assert result is None

    @patch("aiohttp.ClientSession.post")
    def test_timeout_returns_none(self, mock_post):
        mock_post.return_value.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)

        result = asyncio.run(bot.query_llm("context", "user message"))
        assert result is None

    @patch("aiohttp.ClientSession.post")
    def test_uses_system_override(self, mock_post):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "ok"}}]
        })
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)

        override = "You are nice"
        asyncio.run(bot.query_llm("", "hi", system_override=override))
        call_kwargs = mock_post.call_args[1]
        sent_messages = call_kwargs["json"]["messages"]
        assert sent_messages[0]["content"] == override

    @patch("aiohttp.ClientSession.post")
    def test_sends_context(self, mock_post):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "ok"}}]
        })
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)

        asyncio.run(bot.query_llm("Alice: hi\nBob: hello", "user msg"))
        call_kwargs = mock_post.call_args[1]
        msgs = call_kwargs["json"]["messages"]
        assert any("Alice: hi" in m["content"] for m in msgs)
        assert any("user msg" in m["content"] for m in msgs)

    @patch("aiohttp.ClientSession.post")
    def test_empty_context_omits_context_message(self, mock_post):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "ok"}}]
        })
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)

        asyncio.run(bot.query_llm("", "user msg"))
        call_kwargs = mock_post.call_args[1]
        msgs = call_kwargs["json"]["messages"]
        assert len(msgs) == 2  # system + user


# ── Тесты handle_message ─────────────────────────────────────────────────

class TestHandleMessage:
    @pytest.mark.usefixtures("mock_bot")
    def test_ignores_bot_own_message(self, mock_message):
        mock_message.from_user.id = bot.bot.id
        asyncio.run(bot.handle_message(mock_message))
        mock_message.reply.assert_not_called()

    @pytest.mark.usefixtures("mock_bot")
    def test_stores_and_ignores_non_trigger(self, mock_message):
        bot.message_history.clear()
        mock_message.text = "random message"
        asyncio.run(bot.handle_message(mock_message))
        assert len(bot.message_history[-100111]) == 1
        mock_message.reply.assert_not_called()

    @pytest.mark.usefixtures("mock_bot")
    def test_responds_to_mention(self, mock_message):
        mock_message.text = f"@{bot.BOT_USERNAME} hey"
        asyncio.run(bot.handle_message(mock_message))
        mock_message.reply.assert_called_once()

    @pytest.mark.usefixtures("mock_bot")
    def test_responds_to_reply(self, mock_message):
        reply_from = MagicMock()
        reply_from.id = bot.bot.id
        mock_message.reply_to_message = MagicMock(from_user=reply_from)
        mock_message.text = "answer this"
        asyncio.run(bot.handle_message(mock_message))
        mock_message.reply.assert_called_once()

    @pytest.mark.usefixtures("mock_bot")
    def test_rate_limit_skips_response(self, mock_message):
        bot.last_response_time.clear()
        mock_message.text = f"@{bot.BOT_USERNAME} first"
        asyncio.run(bot.handle_message(mock_message))
        mock_message.reply.assert_called_once()

        mock_message.reply.reset_mock()
        mock_message.message_id = 2
        mock_message.text = f"@{bot.BOT_USERNAME} second"
        asyncio.run(bot.handle_message(mock_message))
        mock_message.reply.assert_not_called()

    @pytest.mark.usefixtures("mock_bot")
    def test_fallback_on_llm_failure(self, mock_message):
        mock_message.text = f"@{bot.BOT_USERNAME} hi"
        mock_message.reply = AsyncMock(return_value=MagicMock(message_id=100))
        with patch.object(bot, "query_llm", AsyncMock(return_value=None)):
            asyncio.run(bot.handle_message(mock_message))
            mock_message.reply.assert_called_once()
            reply_text = mock_message.reply.call_args[0][0]
            assert any(word in reply_text for word in ["блядь", "нахуй", "пидор", "тошно"])

    @pytest.mark.usefixtures("mock_bot")
    def test_tracks_message_id_after_reply(self, mock_message):
        bot.bot_message_ids.clear()
        mock_message.text = f"@{bot.BOT_USERNAME} hi"
        replied = MagicMock(message_id=555)
        mock_message.reply = AsyncMock(return_value=replied)
        asyncio.run(bot.handle_message(mock_message))
        assert 555 in bot.bot_message_ids[-100111]

    @pytest.mark.usefixtures("mock_bot")
    def test_psyho_delic_gets_nice_prompt(self, mock_message):
        mock_message.from_user.username = "psyho_delic"
        mock_message.text = f"@{bot.BOT_USERNAME} hello"
        mock_message.reply = AsyncMock(return_value=MagicMock(message_id=100))
        with patch.object(bot, "query_llm") as mock_q:
            mock_q.return_value = "Ты лучший!"
            asyncio.run(bot.handle_message(mock_message))
            _, kwargs = mock_q.call_args
            assert kwargs["system_override"] is not None
            assert "добрый" in kwargs["system_override"]

    @pytest.mark.usefixtures("mock_bot")
    def test_taunt_chat_uses_full_prompt(self, mock_message):
        bot.TAUNT_CHAT_ID = "-100111"
        mock_message.text = f"@{bot.BOT_USERNAME} hello"
        mock_message.reply = AsyncMock(return_value=MagicMock(message_id=100))
        with patch.object(bot, "query_llm") as mock_q:
            mock_q.return_value = "Иди нахуй"
            asyncio.run(bot.handle_message(mock_message))
            _, kwargs = mock_q.call_args
            assert kwargs["system_override"] == bot.SYSTEM_PROMPT_FULL
        bot.TAUNT_CHAT_ID = ""

    @pytest.mark.usefixtures("mock_bot")
    def test_forwarded_in_taunt_chat(self, mock_message):
        bot.TAUNT_CHAT_ID = "-100111"
        mock_message.text = "some forward text"
        mock_message.forward_origin = MagicMock()
        mock_message.reply = AsyncMock(return_value=MagicMock(message_id=100))
        with patch.object(bot, "query_llm") as mock_q:
            mock_q.return_value = "shut up"
            asyncio.run(bot.handle_message(mock_message))
            prompt_arg = mock_q.call_args[0][1]
            assert "переслал" in prompt_arg
        bot.TAUNT_CHAT_ID = ""


# ── Тесты handle_reaction ────────────────────────────────────────────────

class TestHandleReaction:
    @pytest.mark.usefixtures("mock_bot")
    def test_ignores_reaction_not_on_bot_message(self, mock_reaction):
        bot.bot_message_ids.clear()
        asyncio.run(bot.handle_reaction(mock_reaction))
        bot.bot.send_message.assert_not_called()

    @pytest.mark.usefixtures("mock_bot")
    def test_responds_to_reaction_on_bot_message(self, mock_reaction):
        bot.bot_message_ids.clear()
        bot.bot_message_ids[-100111].add(100)
        bot.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))
        with patch.object(bot, "query_llm", AsyncMock(return_value="чё поставил")):
            asyncio.run(bot.handle_reaction(mock_reaction))
            bot.bot.send_message.assert_called_once()

    @pytest.mark.usefixtures("mock_bot")
    def test_ignores_reaction_removal(self, mock_reaction):
        bot.bot_message_ids[-100111].add(100)
        mock_reaction.new_reaction = []
        asyncio.run(bot.handle_reaction(mock_reaction))
        bot.bot.send_message.assert_not_called()

    @pytest.mark.usefixtures("mock_bot")
    def test_ignores_private_chat_reaction(self, mock_reaction):
        mock_reaction.chat.type = "private"
        bot.bot_message_ids[-100111].add(100)
        bot.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))
        with patch.object(bot, "query_llm", AsyncMock(return_value="reaction answer")):
            asyncio.run(bot.handle_reaction(mock_reaction))
            bot.bot.send_message.assert_called_once()

    @pytest.mark.usefixtures("mock_bot")
    def test_tracks_sent_message_id(self, mock_reaction):
        bot.bot_message_ids.clear()
        bot.bot_message_ids[-100111].add(100)
        sent = MagicMock(message_id=300)
        bot.bot.send_message = AsyncMock(return_value=sent)
        with patch.object(bot, "query_llm", AsyncMock(return_value="ok")):
            asyncio.run(bot.handle_reaction(mock_reaction))
            assert 300 in bot.bot_message_ids[-100111]

    @pytest.mark.usefixtures("mock_bot")
    def test_psyho_delic_gets_nice_reaction(self, mock_reaction):
        bot.bot_message_ids[-100111].add(100)
        mock_reaction.user.username = "psyho_delic"
        bot.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))
        with patch.object(bot, "query_llm") as mock_q:
            mock_q.return_value = "спасибо, друг!"
            asyncio.run(bot.handle_reaction(mock_reaction))
            _, kwargs = mock_q.call_args
            assert "добрый" in kwargs["system_override"]


# ── Тесты команд ─────────────────────────────────────────────────────────

class TestCommands:
    @pytest.mark.usefixtures("mock_bot")
    def test_cmd_start_replies(self, mock_message):
        bot.bot_message_ids.clear()
        mock_message.text = "/start"
        sent = MagicMock(message_id=42)
        mock_message.reply = AsyncMock(return_value=sent)
        asyncio.run(bot.cmd_start(mock_message))
        mock_message.reply.assert_called_once_with("Чё надо, блядь? Написал мне, пиздец. Работаю я, не видно?")
        assert 42 in bot.bot_message_ids[mock_message.chat.id]

    @pytest.mark.usefixtures("mock_bot")
    def test_cmd_say_sends_text(self, mock_message):
        bot.bot_message_ids.clear()
        mock_message.text = "/say Hello from bot"
        sent = MagicMock(message_id=77)
        bot.bot.send_message = AsyncMock(return_value=sent)
        asyncio.run(bot.cmd_say(mock_message))
        bot.bot.send_message.assert_called_once_with(mock_message.chat.id, "Hello from bot")
        mock_message.delete.assert_called_once()
        assert 77 in bot.bot_message_ids[mock_message.chat.id]

    @pytest.mark.usefixtures("mock_bot")
    def test_cmd_say_empty_text_ignored(self, mock_message):
        mock_message.text = "/say"
        asyncio.run(bot.cmd_say(mock_message))
        bot.bot.send_message.assert_not_called()
