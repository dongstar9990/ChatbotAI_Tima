import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.conversation import send_message_to_zalo
from app.schemas.message import SendMessageRequest, ZaloSendMessageRequest


class SendZaloMessageApiTests(unittest.IsolatedAsyncioTestCase):
    def test_zalo_request_rejects_text_longer_than_2000_characters(self):
        with self.assertRaises(ValueError):
            ZaloSendMessageRequest(content="x" * 2001, username="Agent")

    async def test_sends_to_zalo_and_persists_outbound_message(self):
        conversation = SimpleNamespace(
            id=42,
            external_conversation_id="zalo-user-1",
            channel_account_id=7,
        )
        account = SimpleNamespace(
            status=1,
            channel_id="zalo",
            access_token="zalo-token",
        )
        saved_message = SimpleNamespace(id=99, external_message_id="zalo-message-1")

        with (
            patch("app.api.conversation.get_conversation", AsyncMock(return_value=conversation)),
            patch("app.api.conversation.get_channel_account", AsyncMock(return_value=account)),
            patch(
                "app.api.conversation.send_zalo_text",
                AsyncMock(return_value="zalo-message-1"),
            ) as send,
            patch(
                "app.api.conversation.upsert_message",
                AsyncMock(return_value=saved_message),
            ) as save,
        ):
            result = await send_message_to_zalo(
                conversation_id=42,
                payload=SendMessageRequest(content="Xin chào", username="Agent"),
                db=AsyncMock(),
            )

        self.assertIs(result, saved_message)
        send.assert_awaited_once_with(
            access_token="zalo-token",
            recipient_id="zalo-user-1",
            text="Xin chào",
        )
        save.assert_awaited_once()
        self.assertEqual(save.call_args.args[1].external_message_id, "zalo-message-1")

    async def test_rejects_non_zalo_channel_account(self):
        conversation = SimpleNamespace(
            id=42,
            external_conversation_id="user-1",
            channel_account_id=7,
        )
        account = SimpleNamespace(status=1, channel_id="facebook", access_token="token")

        with (
            patch("app.api.conversation.get_conversation", AsyncMock(return_value=conversation)),
            patch("app.api.conversation.get_channel_account", AsyncMock(return_value=account)),
        ):
            with self.assertRaises(HTTPException) as context:
                await send_message_to_zalo(
                    conversation_id=42,
                    payload=SendMessageRequest(content="Xin chào", username="Agent"),
                    db=AsyncMock(),
                )

        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
