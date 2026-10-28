import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.zalo_services import ZaloSendError, send_zalo_text


class ZaloSendTextTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_consultation_text_and_returns_message_id(self):
        response = httpx.Response(
            200,
            json={"error": 0, "message": "Success", "data": {"message_id": "zalo-1"}},
            request=httpx.Request("POST", "https://openapi.zalo.me/v3.0/oa/message/cs"),
        )
        client = AsyncMock()
        client.post.return_value = response

        with patch("app.services.zalo_services.httpx.AsyncClient") as client_factory:
            client_factory.return_value.__aenter__ = AsyncMock(return_value=client)
            client_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await send_zalo_text(
                access_token="token-1",
                recipient_id="user-1",
                text="Xin chào",
            )

        self.assertEqual(result, "zalo-1")
        client.post.assert_awaited_once_with(
            "https://openapi.zalo.me/v3.0/oa/message/cs",
            headers={
                "access_token": "token-1",
                "Content-Type": "application/json",
            },
            json={
                "recipient": {"user_id": "user-1"},
                "message": {"text": "Xin chào"},
            },
        )

    async def test_raises_zalo_send_error_for_api_error(self):
        response = httpx.Response(
            400,
            json={"error": -201, "message": "Invalid access token"},
            request=httpx.Request("POST", "https://openapi.zalo.me/v3.0/oa/message/cs"),
        )
        client = AsyncMock()
        client.post.return_value = response

        with patch("app.services.zalo_services.httpx.AsyncClient") as client_factory:
            client_factory.return_value.__aenter__ = AsyncMock(return_value=client)
            client_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            with self.assertRaisesRegex(ZaloSendError, "Invalid access token"):
                await send_zalo_text(
                    access_token="expired-token",
                    recipient_id="user-1",
                    text="Xin chào",
                )


if __name__ == "__main__":
    unittest.main()
