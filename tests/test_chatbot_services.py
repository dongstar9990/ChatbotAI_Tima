import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import chatbot_services


def message(sender_type, content, message_id=1):
    return SimpleNamespace(
        id=message_id,
        sender_type=sender_type,
        sender_id="sender",
        content=content,
        external_message_id=f"external-{message_id}",
    )


class UnansweredConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_customer_message_without_later_outbound_message_is_unanswered(self):
        messages = [message("bot", "Xin chào"), message("customer", "Tôi cần tư vấn")]

        self.assertTrue(chatbot_services._is_unanswered(messages))

    async def test_customer_message_with_later_agent_message_is_answered(self):
        messages = [
            message("customer", "Tôi cần tư vấn"),
            message("agent", "Em hỗ trợ anh chị đây ạ"),
        ]

        self.assertFalse(chatbot_services._is_unanswered(messages))

    async def test_process_sends_before_saving_bot_message(self):
        db = AsyncMock()
        conversation = SimpleNamespace(
            id=42,
            external_conversation_id="psid-42",
            channel_account_id=7,
        )
        account = SimpleNamespace(
            status=1,
            external_page_id="page-7",
            access_token="token-7",
        )
        history = [message("customer", "Tôi muốn vay", message_id=3)]

        with (
            patch.object(chatbot_services, "get_channel_account", AsyncMock(return_value=account)),
            patch.object(chatbot_services, "list_messages", AsyncMock(return_value=(1, history))),
            patch.object(chatbot_services, "send_facebook_text", AsyncMock(return_value="fb-reply-1")) as send,
            patch.object(chatbot_services, "_generate_reply", AsyncMock(return_value="Dạ em hỗ trợ anh chị ạ")),
            patch.object(chatbot_services, "upsert_message", AsyncMock()) as save,
        ):
            result = await chatbot_services.process_unanswered_conversation(db, conversation)

        self.assertEqual(result["status"], "replied")
        send.assert_awaited_once_with(
            page_id="page-7",
            access_token="token-7",
            recipient_id="psid-42",
            text="Dạ em hỗ trợ anh chị ạ",
        )
        save.assert_awaited_once()
        self.assertEqual(save.call_args.args[1].external_message_id, "fb-reply-1")

    async def test_reply_unanswered_continues_after_one_conversation_fails(self):
        conversations = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        with (
            patch.object(
                chatbot_services,
                "list_unanswered_conversations",
                AsyncMock(return_value=conversations),
            ),
            patch.object(
                chatbot_services,
                "process_unanswered_conversation",
                AsyncMock(
                    side_effect=[
                        RuntimeError("Facebook timeout"),
                        {"status": "replied", "reply": "Đã hỗ trợ ạ"},
                    ]
                ),
            ) as process,
            patch.object(chatbot_services.logger, "exception"),
        ):
            result = await chatbot_services.reply_unanswered_messages(AsyncMock(), limit=2)

        self.assertEqual(result["scanned"], 2)
        self.assertEqual(result["replied"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"][0]["conversation_id"], 1)
        self.assertEqual(process.await_count, 2)


if __name__ == "__main__":
    unittest.main()
